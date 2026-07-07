"""
GraphRAG pipeline — local-first.

Stages
------
1. Query transformation   – rewrite into sub-queries (+ HyDE when LLM available)
2. Query routing          – classify intent → pick retrieval strategy
3. Fusion retrieval       – vector ANN + BM25 merged with RRF
4. Summary index          – inject artifact-level summaries as context prefix
5. Graph expansion        – walk CONTAINS / RELATED_TO neighbours
6. Reranking              – LLM cross-encoder rerank of top candidates
7. Context assembly       – structured window: summaries | ranked items | neighbours
8. LLM generation         – grounded answer with multi-turn history support

Embedding and LLM calls are routed through embeddings.py / llm_client.py,
which default to sentence-transformers + Ollama and upgrade to OpenAI when
the appropriate env vars are set.
"""
from __future__ import annotations

import json
import logging
import math
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from app.services import embeddings as emb
from app.services import llm_client

logger = logging.getLogger(__name__)

# ── route → system prompt ────────────────────────────────────────────────────
_SYSTEM: Dict[str, str] = {
    "factual": (
        "You are a precise knowledge assistant. "
        "Answer directly and concisely using ONLY the provided context nodes. "
        "Cite every fact as [item_id]. Do not hallucinate."
    ),
    "exploratory": (
        "You are a knowledge assistant helping with open-ended exploration. "
        "Synthesise insights across the context nodes, highlight connections, "
        "and cite sources as [item_id]. Acknowledge gaps honestly."
    ),
    "comparative": (
        "You are a knowledge assistant specialised in comparison. "
        "Structure your answer as a comparison across the retrieved items. "
        "Cite each point as [item_id]."
    ),
    "procedural": (
        "You are a knowledge assistant specialised in step-by-step guidance. "
        "Present the answer as an ordered procedure using the context nodes. "
        "Cite each step as [item_id]."
    ),
}
_SYSTEM["fallback"] = _SYSTEM["factual"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Embedding helpers (delegated to embeddings.py)
# ─────────────────────────────────────────────────────────────────────────────

async def embed(text: str) -> Optional[List[float]]:
    return await emb.embed(text)


async def embed_items(items: List[Dict[str, Any]]) -> List[Tuple[str, List[float]]]:
    if not items:
        return []
    texts = [_item_text(i) for i in items]
    vecs = await emb.embed_batch(texts)
    return [(items[i]["id"], v) for i, v in enumerate(vecs) if v is not None]


def _item_text(item: Dict[str, Any]) -> str:
    parts = [item.get("title", ""), item.get("type", "")]
    for v in (item.get("details") or {}).values():
        if isinstance(v, str) and v:
            parts.append(v)
    return " ".join(parts)[:2000]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Query transformation  (sub-queries + HyDE)
# ─────────────────────────────────────────────────────────────────────────────

async def transform_query(question: str) -> Dict[str, Any]:
    prompt = (
        "Given the user question below, produce a JSON object with two keys:\n"
        "  sub_queries: list of 3 distinct rewritten versions that cover different "
        "angles (synonyms, specificity levels, related concepts).\n"
        "  hyde_doc: a short hypothetical answer document (2-3 sentences) that "
        "a perfect knowledge base would contain.\n"
        "Return ONLY the JSON object.\n\n"
        f"Question: {question}"
    )
    content = await llm_client.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        json_mode=True,
    )
    if content:
        try:
            data = json.loads(content)
            sub_queries = data.get("sub_queries") or [question]
            hyde_doc    = data.get("hyde_doc") or question
            if question not in sub_queries:
                sub_queries = [question] + sub_queries[:3]
            return {"sub_queries": sub_queries[:4], "hyde_doc": hyde_doc}
        except Exception as exc:
            logger.warning("transform_query() parse failed: %s", exc)
    return {"sub_queries": [question], "hyde_doc": question}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Query routing
# ─────────────────────────────────────────────────────────────────────────────

_ROUTE_HINTS = {
    "factual":     ["what is", "who is", "when did", "define", "which"],
    "comparative": ["compare", "difference", "versus", "vs", "better", "pros and cons"],
    "procedural":  ["how to", "steps", "process", "guide", "implement", "set up"],
    "exploratory": ["why", "explain", "tell me about", "overview", "discuss"],
}


def route_query(question: str) -> str:
    q = question.lower()
    for route, hints in _ROUTE_HINTS.items():
        if any(h in q for h in hints):
            return route
    return "exploratory"


async def route_query_llm(question: str) -> str:
    prompt = (
        "Classify the following question into exactly one category: "
        "factual | exploratory | comparative | procedural\n"
        "Return only the category word.\n\n"
        f"Question: {question}"
    )
    content = await llm_client.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10,
    )
    if content:
        label = content.strip().lower()
        if label in _SYSTEM:
            return label
    return route_query(question)


# ─────────────────────────────────────────────────────────────────────────────
# 4. BM25 index (in-memory)
# ─────────────────────────────────────────────────────────────────────────────

def _tokenise(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9]{2,}", text.lower())


def _build_bm25_scores(
    query_tokens: List[str],
    items: List[Dict[str, Any]],
    k1: float = 1.5,
    b: float = 0.75,
) -> List[Tuple[float, Dict[str, Any]]]:
    if not query_tokens or not items:
        return []
    corpus = [_tokenise(_item_text(i)) for i in items]
    avg_dl = sum(len(d) for d in corpus) / max(len(corpus), 1)
    df: Dict[str, int] = defaultdict(int)
    for doc in corpus:
        for t in set(doc):
            df[t] += 1
    N = len(corpus)
    idf = {t: math.log((N - df[t] + 0.5) / (df[t] + 0.5) + 1) for t in df}
    scored = []
    for item, doc in zip(items, corpus):
        tf_map: Dict[str, int] = defaultdict(int)
        for t in doc:
            tf_map[t] += 1
        dl = len(doc)
        score = sum(
            idf[t] * (tf_map.get(t, 0) * (k1 + 1))
            / (tf_map.get(t, 0) + k1 * (1 - b + b * dl / avg_dl))
            for t in query_tokens if t in idf
        )
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


# ─────────────────────────────────────────────────────────────────────────────
# 5. Cosine vector search (SQLite fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _sqlite_vector_search(
    query_vec: List[float],
    items: List[Dict[str, Any]],
    top_k: int,
) -> List[Tuple[float, Dict[str, Any]]]:
    scored = [
        (_cosine(query_vec, item["embedding"]), item)
        for item in items
        if item.get("embedding") and len(item["embedding"]) == len(query_vec)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


# ─────────────────────────────────────────────────────────────────────────────
# 6. Reciprocal Rank Fusion
# ─────────────────────────────────────────────────────────────────────────────

def _rrf(ranked_lists: List[List[Dict[str, Any]]], k: int = 60) -> List[Dict[str, Any]]:
    scores: Dict[str, float] = defaultdict(float)
    items_by_id: Dict[str, Dict[str, Any]] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            iid = item.get("id", "")
            if not iid:
                continue
            scores[iid] += 1.0 / (k + rank)
            items_by_id[iid] = item
    merged = sorted(items_by_id.values(), key=lambda i: scores[i["id"]], reverse=True)
    for item in merged:
        item["rrf_score"] = scores[item["id"]]
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# 7. Graph expansion (SQLite cross-link fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _sqlite_graph_expand(
    seed_ids: List[str],
    cross_links: List[Dict[str, Any]],
    item_map: Dict[str, Dict[str, Any]],
    seed_scores: Dict[str, float],
) -> List[Dict[str, Any]]:
    seen = set(seed_ids)
    expanded: List[Dict[str, Any]] = []
    for link in cross_links:
        a, b = link["item_id_a"], link["item_id_b"]
        candidate_id = b if a in seed_ids and b not in seen else (
            a if b in seed_ids and a not in seen else None
        )
        source_id = a if candidate_id == b else b
        if candidate_id and candidate_id in item_map:
            seen.add(candidate_id)
            expanded.append({
                **item_map[candidate_id],
                "rrf_score": seed_scores.get(source_id, 0.0) * 0.7,
                "retrieved_by": "sqlite_graph",
            })
    return sorted(expanded, key=lambda n: n.get("rrf_score") or 0.0, reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# 8. LLM reranking
# ─────────────────────────────────────────────────────────────────────────────

async def rerank(
    question: str,
    candidates: List[Dict[str, Any]],
    top_n: int = 8,
) -> List[Dict[str, Any]]:
    if len(candidates) <= top_n:
        return candidates[:top_n]

    snippets = [
        f"{i}: [{c.get('kind') or c.get('type', '')}] {c.get('title') or c.get('label', '')}"
        for i, c in enumerate(candidates)
    ]
    prompt = (
        f"Question: {question}\n\n"
        "Rate each candidate's relevance to the question from 0 (irrelevant) "
        "to 10 (highly relevant). Return ONLY a JSON array of integers in the "
        "same order, e.g. [8,3,10,...].\n\n"
        "Candidates:\n" + "\n".join(snippets)
    )
    content = await llm_client.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=256,
        json_mode=True,
    )
    if content:
        try:
            raw = json.loads(content)
            scores: List[int] = raw if isinstance(raw, list) else raw.get("scores", [])
            if len(scores) == len(candidates):
                paired = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
                return [c for _, c in paired[:top_n]]
        except Exception as exc:
            logger.warning("rerank() parse failed: %s — using RRF order", exc)
    return candidates[:top_n]


# ─────────────────────────────────────────────────────────────────────────────
# 9. Context assembly
# ─────────────────────────────────────────────────────────────────────────────

def _build_context(
    summaries: List[Dict[str, Any]],
    ranked_items: List[Dict[str, Any]],
    graph_neighbours: List[Dict[str, Any]],
) -> str:
    parts: List[str] = []
    if summaries:
        lines = ["=== ARTIFACT SUMMARIES ==="]
        for s in summaries:
            lines.append(f"[{s.get('artifact_id','?')}] {s.get('title','')}: {s.get('summary','')}")
        parts.append("\n".join(lines))
    if ranked_items:
        lines = ["=== KNOWLEDGE ITEMS ==="]
        for n in ranked_items:
            nid   = n.get("id", "?")
            title = n.get("title") or n.get("label", "")
            kind  = n.get("kind") or n.get("type", "")
            score = n.get("rrf_score") or n.get("score") or 0.0
            lines.append(f"[{nid}] ({kind}) relevance={score:.3f}: {title}")
            for k, v in (n.get("details") or {}).items():
                if isinstance(v, str) and v and k not in ("evidence", "confidence"):
                    lines.append(f"  {k}: {v}")
        parts.append("\n".join(lines))
    if graph_neighbours:
        lines = ["=== RELATED CONTEXT (graph) ==="]
        for n in graph_neighbours:
            lines.append(f"[{n.get('id','?')}] ({n.get('kind') or n.get('type','')}): {n.get('title') or n.get('label','')}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# 10. LLM generation
# ─────────────────────────────────────────────────────────────────────────────

async def _generate(
    question: str,
    context: str,
    route: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    system = _SYSTEM.get(route, _SYSTEM["factual"])
    user_msg = f"Context:\n{context}\n\nQuestion: {question}"
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": user_msg})

    content = await llm_client.chat(messages=messages, temperature=0.2, max_tokens=1000)
    if content:
        return content
    # offline fallback — surface context directly
    preview = context[:600].replace("\n", " ")
    return f"[LLM unavailable] Relevant context for '{question}':\n{preview}"


# ─────────────────────────────────────────────────────────────────────────────
# 11. Citation extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_citations(answer: str, nodes: List[Dict[str, Any]]) -> List[str]:
    brackets = re.findall(r"\[([^\]]+)\]", answer)
    cited: List[str] = []
    for node in nodes:
        nid = node.get("id", "")
        if not nid:
            continue
        prefix = nid.split("_")[0]
        for token in brackets:
            if token == nid or nid.startswith(token) or token.startswith(prefix):
                cited.append(nid)
                break
    return cited


# ─────────────────────────────────────────────────────────────────────────────
# 12. Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def graphrag_query(
    question: str,
    neo4j_store,
    fallback_items: Optional[List[Dict[str, Any]]] = None,
    cross_links:    Optional[List[Dict[str, Any]]] = None,
    artifact_summaries: Optional[List[Dict[str, Any]]] = None,
    history:        Optional[List[Dict[str, str]]] = None,
    top_k:          int = 8,
) -> Dict[str, Any]:
    t0 = time.monotonic()

    transformed = await transform_query(question)
    sub_queries  = transformed["sub_queries"]
    hyde_doc     = transformed["hyde_doc"]

    route = await route_query_llm(question)

    all_context_nodes: List[Dict[str, Any]] = []
    retrieval_mode = "none"
    summaries_used: List[Dict[str, Any]] = []

    query_vecs = [v for v in [
        await emb.embed(question),
        await emb.embed(hyde_doc) if hyde_doc != question else None,
    ] if v is not None]

    # ── PRIMARY: Neo4j ──────────────────────────────────────────────────────
    if neo4j_store.enabled and query_vecs:
        vec_lists: List[List[Dict[str, Any]]] = []
        for qv in query_vecs:
            hits = neo4j_store.retrieve_for_rag(qv, top_k=top_k)
            if hits:
                vec_lists.append(hits)
        for sq in sub_queries[1:3]:
            sqv = await emb.embed(sq)
            if sqv:
                hits = neo4j_store.vector_search(sqv, top_k=top_k // 2)
                if hits:
                    vec_lists.append(hits)
        if vec_lists:
            all_context_nodes = _rrf(vec_lists)
            retrieval_mode = "neo4j_graphrag_fusion"
        if query_vecs:
            summaries_used = neo4j_store.summary_vector_search(query_vecs[0], top_k=3)

    # ── FALLBACK: SQLite ────────────────────────────────────────────────────
    if not all_context_nodes and fallback_items:
        item_map = {i["id"]: i for i in fallback_items}
        vec_lists = []
        for qv in query_vecs:
            hits = _sqlite_vector_search(qv, fallback_items, top_k)
            if hits:
                vec_lists.append([{**item, "score": score, "retrieved_by": "sqlite_vector"}
                                   for score, item in hits])
        q_tokens = _tokenise(question)
        bm25_hits = _build_bm25_scores(q_tokens, fallback_items)
        if bm25_hits:
            vec_lists.append([{**item, "score": score, "retrieved_by": "bm25"}
                               for score, item in bm25_hits[:top_k]])
        if vec_lists:
            fused = _rrf(vec_lists)
            seed_ids    = [n["id"] for n in fused[:top_k]]
            seed_scores = {n["id"]: n.get("rrf_score", 0.0) for n in fused[:top_k]}
            neighbours: List[Dict[str, Any]] = []
            if cross_links:
                neighbours = _sqlite_graph_expand(seed_ids, cross_links, item_map, seed_scores)
            seen = {n["id"] for n in fused}
            for nb in neighbours:
                if nb["id"] not in seen:
                    seen.add(nb["id"])
                    fused.append(nb)
            all_context_nodes = fused
            retrieval_mode = "sqlite_fusion_graph" if query_vecs else "bm25_graph"
        if artifact_summaries and query_vecs:
            sv = _sqlite_vector_search(query_vecs[0], artifact_summaries, 3)
            summaries_used = [item for _, item in sv]

    if not all_context_nodes:
        return {
            "answer": "No relevant knowledge found for this question.",
            "citations": [],
            "context_nodes": [],
            "summaries": [],
            "route": route,
            "sub_queries": sub_queries,
            "retrieval_mode": "none",
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }

    reranked  = await rerank(question, all_context_nodes, top_n=top_k)
    primary   = [n for n in reranked if "graph" not in n.get("retrieved_by", "")]
    graph_nbr = [n for n in reranked if "graph" in n.get("retrieved_by", "")]

    context   = _build_context(summaries_used, primary, graph_nbr)
    answer    = await _generate(question, context, route, history)
    citations = _extract_citations(answer, reranked)

    return {
        "answer": answer,
        "citations": citations,
        "context_nodes": reranked,
        "summaries": summaries_used,
        "route": route,
        "sub_queries": sub_queries,
        "hyde_doc": hyde_doc,
        "retrieval_mode": retrieval_mode,
        "latency_ms": int((time.monotonic() - t0) * 1000),
    }
