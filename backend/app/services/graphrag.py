from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_RAG_SYSTEM = """You are a knowledge assistant. Answer the user's question using ONLY the context nodes provided.
Each context node has an id, title, type, and optional details.
Rules:
- Ground every claim in a context node. Cite it as [id].
- If the context is insufficient, say so — do not hallucinate.
- Be concise. Use bullet points when listing multiple items.
- Return plain text, no markdown headers."""


async def embed(text: str) -> Optional[List[float]]:
    """Return an embedding vector for text, or None if unavailable."""
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.embeddings.create(model=EMBED_MODEL, input=text[:8000])
        return response.data[0].embedding
    except Exception:
        return None


async def embed_items(items: List[Dict[str, Any]]) -> List[tuple[str, List[float]]]:
    """
    Batch-embed a list of knowledge item dicts.
    Returns [(item_id, vector), ...] for items that succeeded.
    """
    if not OPENAI_API_KEY:
        return []
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        texts = [_item_text(item) for item in items]
        response = await client.embeddings.create(model=EMBED_MODEL, input=texts)
        return [(items[i]["id"], data.embedding) for i, data in enumerate(response.data)]
    except Exception:
        return []


def _item_text(item: Dict[str, Any]) -> str:
    parts = [item.get("title", ""), item.get("type", "")]
    details = item.get("details", {})
    for v in details.values():
        if isinstance(v, str) and v:
            parts.append(v)
    return " ".join(parts)[:2000]


async def graphrag_query(
    question: str,
    neo4j_store,  # Neo4jGraphStore instance
    fallback_items: Optional[List[Dict[str, Any]]] = None,
    top_k: int = 8,
) -> Dict[str, Any]:
    """
    Full GraphRAG pipeline:
      1. Embed the question
      2. Retrieve from Neo4j (vector + graph walk)  OR  keyword fallback
      3. Build grounded prompt
      4. Call LLM and return answer + citations
    """
    query_vec = await embed(question)

    # --- Retrieval ---
    context_nodes: List[Dict[str, Any]] = []

    if query_vec and neo4j_store.enabled:
        context_nodes = neo4j_store.retrieve_for_rag(query_vec, top_k=top_k)

    # Keyword fallback: use SQLite items when Neo4j unavailable or returned nothing
    if not context_nodes and fallback_items:
        q_lower = question.lower()
        scored = []
        for item in fallback_items:
            text = _item_text(item).lower()
            hits = sum(1 for word in q_lower.split() if len(word) > 3 and word in text)
            if hits:
                scored.append((hits, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        context_nodes = [item for _, item in scored[:top_k]]

    if not context_nodes:
        return {
            "answer": "No relevant knowledge found for this question.",
            "citations": [],
            "context_nodes": [],
            "retrieval_mode": "none",
        }

    retrieval_mode = "graphrag" if (query_vec and neo4j_store.enabled) else "keyword_fallback"

    # --- Generation ---
    if not OPENAI_API_KEY:
        return {
            "answer": _offline_answer(question, context_nodes),
            "citations": [n.get("id", "") for n in context_nodes],
            "context_nodes": context_nodes,
            "retrieval_mode": retrieval_mode,
        }

    context_text = _build_context_block(context_nodes)
    user_message = f"Context nodes:\n{context_text}\n\nQuestion: {question}"

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": _RAG_SYSTEM},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as exc:
        answer = f"LLM error: {exc}\n\n{_offline_answer(question, context_nodes)}"

    cited_ids = [n.get("id", "") for n in context_nodes if n.get("id") and n["id"] in answer]

    return {
        "answer": answer,
        "citations": cited_ids,
        "context_nodes": context_nodes,
        "retrieval_mode": retrieval_mode,
    }


def _build_context_block(nodes: List[Dict[str, Any]]) -> str:
    lines = []
    for n in nodes:
        node_id = n.get("id", "?")
        title = n.get("title") or n.get("label", "")
        kind = n.get("kind") or n.get("type", "")
        score = n.get("score")
        score_str = f" (score={score:.3f})" if score else ""
        lines.append(f"[{node_id}] ({kind}){score_str}: {title}")
        # Include detail fields if small enough
        details = n.get("details") or {}
        for k, v in details.items():
            if isinstance(v, str) and v and k not in ("evidence", "confidence"):
                lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _offline_answer(question: str, nodes: List[Dict[str, Any]]) -> str:
    """Plain-text answer when no API key is set — just lists the relevant items."""
    lines = [f"Relevant knowledge for: '{question}'\n"]
    for n in nodes:
        lines.append(f"• [{n.get('id', '?')}] {n.get('title') or n.get('label', '')} ({n.get('kind') or n.get('type', '')})")
    return "\n".join(lines)
