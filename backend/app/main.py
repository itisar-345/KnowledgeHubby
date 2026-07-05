from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    TokenResponse,
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db import (
    Artifact,
    ArtifactSummary,
    CrossLink,
    KnowledgeItem,
    Playbook,
    QueryLog,
    Relationship,
    User,
    get_session,
    init_db,
)
from app.services.cross_source_linker import find_cross_links
from app.services.curation_layer import CurationLayer
from app.services.file_ingestion import extract_text_from_upload, fetch_url
from app.services.graph_builder import GraphBuilder
from app.services.graphrag import embed_items, graphrag_query, embed
from app.services.ingestion_normalization import IngestionNormalization
from app.services.knowledge_extraction import KnowledgeExtraction
from app.services.llm_extraction import extract_from_transcript
from app.services.neo4j_graph import Neo4jGraphStore
from app.services.okf import export_okf_payload, normalize_okf_payload

app = FastAPI(title="Knowledge Hubs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ingestion = IngestionNormalization()
extractor = KnowledgeExtraction()
graph_builder = GraphBuilder(None)
curation = CurationLayer()
neo4j_graph = Neo4jGraphStore()


@app.on_event("startup")
async def startup() -> None:
    await init_db()
    neo4j_graph.ensure_vector_index()


@app.on_event("shutdown")
def shutdown() -> None:
    neo4j_graph.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=6)
    workspace_id: str = Field(min_length=1, max_length=80)


@app.post("/auth/register", status_code=201)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> Dict[str, str]:
    existing = await session.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")
    user = User(
        id=str(uuid.uuid4()),
        username=body.username,
        hashed_password=hash_password(body.password),
        workspace_id=body.workspace_id,
    )
    session.add(user)
    await session.commit()
    return {"user_id": user.id, "workspace_id": user.workspace_id}


@app.post("/auth/token", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    result = await session.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_token(user.id, user.workspace_id))


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "storage": "sqlite",
        "neo4j": "connected" if neo4j_graph.verify() else "disabled",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode()).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _build_items(artifact_id: str, content: str, author: str, tags: List[str], created_at: str) -> List[Dict[str, Any]]:
    extracted = {
        "decisions": extractor.extract_decisions(content),
        "how_tos": extractor.mine_how_to_patterns(content),
        "checklists": extractor.detect_checklists(content),
        "best_practices": extractor.identify_best_practices(content),
        "lessons": extractor.extract_lessons_learned(content),
        "risks": extractor.recognize_risk_patterns(content),
    }
    items: List[Dict[str, Any]] = []
    for label in ["decisions", "how_tos", "lessons", "risks"]:
        for entry in extracted[label]:
            title = entry.get("what") or entry.get("pattern") or entry.get("lesson") or entry.get("risk")
            if title:
                items.append({
                    "id": _stable_id(label, f"{artifact_id}:{title}"),
                    "artifact_id": artifact_id,
                    "title": title[:180],
                    "type": label.rstrip("s").replace("_", "-"),
                    "author": author,
                    "date": created_at,
                    "tags": tags,
                    "details": entry,
                })
    for practice in extracted["best_practices"]:
        items.append({
            "id": _stable_id("practice", f"{artifact_id}:{practice}"),
            "artifact_id": artifact_id,
            "title": practice[:180],
            "type": "best-practice",
            "author": author,
            "date": created_at,
            "tags": tags,
            "details": {"practice": practice},
        })
    for checklist in extracted["checklists"]:
        items.append({
            "id": _stable_id("checklist", f"{artifact_id}:{checklist}"),
            "artifact_id": artifact_id,
            "title": checklist[:180],
            "type": "checklist",
            "author": author,
            "date": created_at,
            "tags": tags,
            "details": {"item": checklist},
        })
    return items


async def _persist_artifact(
    session: AsyncSession,
    workspace_id: str,
    artifact_id: str,
    title: str,
    content: str,
    source: str,
    source_type: str,
    author: str,
    tags: List[str],
    created_at: str,
    metadata: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    existing = await session.get(Artifact, artifact_id)
    if existing:
        existing.title = title
        existing.content = content
        existing.tags = tags
        existing.metadata_ = metadata
    else:
        session.add(Artifact(
            id=artifact_id,
            workspace_id=workspace_id,
            title=title,
            content=content,
            source=source,
            source_type=source_type,
            author=author,
            tags=tags,
            created_at=created_at,
            metadata_=metadata,
        ))

    items = _build_items(artifact_id, content, author, tags, created_at)
    item_ids = {i["id"] for i in items}

    # remove stale items for this artifact that are no longer extracted
    existing_items_result = await session.execute(
        select(KnowledgeItem).where(
            KnowledgeItem.artifact_id == artifact_id,
            KnowledgeItem.workspace_id == workspace_id,
        )
    )
    for old in existing_items_result.scalars():
        if old.id not in item_ids:
            await session.delete(old)

    for item in items:
        ki = await session.get(KnowledgeItem, item["id"])
        if ki:
            ki.title = item["title"]
            ki.details = item["details"]
        else:
            session.add(KnowledgeItem(
                id=item["id"],
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                title=item["title"],
                type=item["type"],
                author=item["author"],
                date=item["date"],
                tags=item["tags"],
                details=item["details"],
                review_status="pending",
            ))

    relationships = [
        {"from": artifact_id, "to": item["id"], "type": "CONTAINS"}
        for item in items
    ]
    existing_rels = await session.execute(
        select(Relationship).where(Relationship.from_id == artifact_id, Relationship.workspace_id == workspace_id)
    )
    existing_rel_keys = {(r.from_id, r.to_id, r.type) for r in existing_rels.scalars()}
    for rel in relationships:
        key = (rel["from"], rel["to"], rel["type"])
        if key not in existing_rel_keys:
            session.add(Relationship(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                from_id=rel["from"],
                to_id=rel["to"],
                type=rel["type"],
            ))

    await session.commit()
    return items, relationships


# ---------------------------------------------------------------------------
# Knowledge – read
# ---------------------------------------------------------------------------

@app.get("/knowledge")
async def list_knowledge(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    ws = current_user.workspace_id
    artifacts = (await session.execute(select(Artifact).where(Artifact.workspace_id == ws))).scalars().all()
    items = (await session.execute(select(KnowledgeItem).where(KnowledgeItem.workspace_id == ws))).scalars().all()
    rels = (await session.execute(select(Relationship).where(Relationship.workspace_id == ws))).scalars().all()
    playbooks = (await session.execute(select(Playbook).where(Playbook.workspace_id == ws))).scalars().all()

    return {
        "artifacts": [_artifact_dict(a) for a in artifacts],
        "knowledge_items": [_item_dict(i) for i in items],
        "relationships": [{"from": r.from_id, "to": r.to_id, "type": r.type} for r in rels],
        "playbooks": [{"id": p.id, "title": p.title, "steps": p.steps, "category": p.category} for p in playbooks],
    }


@app.post("/knowledge/okf/import")
async def import_okf_payload(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    normalized = normalize_okf_payload(payload)
    artifact_id = _stable_id("artifact", f"{normalized['title']}:{normalized['content']}")
    created_at = datetime.utcnow().isoformat()

    artifact_dict = {
        "id": artifact_id,
        "title": normalized["title"],
        "content": normalized["content"],
        "source": normalized["source"],
        "source_type": normalized["source_type"],
        "author": normalized["author"],
        "tags": normalized["tags"],
        "created_at": created_at,
    }
    metadata = {**ingestion.extract_metadata({**artifact_dict, "type": "text"}), **normalized["metadata"]}

    items, relationships = await _persist_artifact(
        session=session,
        workspace_id=current_user.workspace_id,
        artifact_id=artifact_id,
        title=normalized["title"],
        content=normalized["content"],
        source=normalized["source"],
        source_type=normalized["source_type"],
        author=normalized["author"],
        tags=normalized["tags"],
        created_at=created_at,
        metadata=metadata,
    )

    for item in normalized["items"]:
        item_id = _stable_id("okf", f"{artifact_id}:{item['title']}")
        item_payload = {
            "id": item_id,
            "artifact_id": artifact_id,
            "title": item["title"][:180],
            "type": item["type"].replace(" ", "-").lower() or "knowledge-item",
            "author": item.get("author", normalized["author"]),
            "date": created_at,
            "tags": item.get("tags", normalized["tags"]),
            "details": {**item.get("details", {}), "okf_source": item.get("source", normalized["source"]), "okf_original_id": item.get("id")},
            "workspace_id": current_user.workspace_id,
            "review_status": "pending",
        }
        existing = await session.get(KnowledgeItem, item_payload["id"])
        if existing:
            existing.title = item_payload["title"]
            existing.details = item_payload["details"]
            existing.tags = item_payload["tags"]
        else:
            session.add(KnowledgeItem(
                id=item_payload["id"],
                workspace_id=current_user.workspace_id,
                artifact_id=artifact_id,
                title=item_payload["title"],
                type=item_payload["type"],
                author=item_payload["author"],
                date=item_payload["date"],
                tags=item_payload["tags"],
                details=item_payload["details"],
                review_status=item_payload["review_status"],
            ))

    for rel in normalized["relationships"]:
        session.add(Relationship(
            id=str(uuid.uuid4()),
            workspace_id=current_user.workspace_id,
            from_id=rel["source"],
            to_id=rel["target"],
            type=rel["type"],
        ))

    await session.commit()
    neo4j_graph.upsert_artifact_graph(artifact_dict, items, relationships)
    await _embed_and_store(items, session)
    await _build_artifact_summary(session, current_user.workspace_id, artifact_dict, normalized["content"])
    return {"artifact": artifact_dict, "imported_items": len(normalized["items"]), "relationships": len(normalized["relationships"])}


@app.get("/knowledge/okf/export")
async def export_okf(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    ws = current_user.workspace_id
    artifacts = (await session.execute(select(Artifact).where(Artifact.workspace_id == ws))).scalars().all()
    items = (await session.execute(select(KnowledgeItem).where(KnowledgeItem.workspace_id == ws))).scalars().all()
    rels = (await session.execute(select(Relationship).where(Relationship.workspace_id == ws))).scalars().all()
    artifact_payloads = [_artifact_dict(a) for a in artifacts]
    item_payloads = [_item_dict(i) for i in items]
    relationship_payloads = [{"from": r.from_id, "to": r.to_id, "type": r.type} for r in rels]
    return export_okf_payload(ws, artifact_payloads, item_payloads, relationship_payloads)


# ---------------------------------------------------------------------------
# Knowledge – ingest (text)
# ---------------------------------------------------------------------------

class ArtifactRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=100_000)
    source: str = "manual"
    author: str = "unknown"
    tags: List[str] = []


@app.post("/knowledge/artifacts")
async def ingest_artifact(
    request: ArtifactRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    return await _ingest(
        session=session,
        workspace_id=current_user.workspace_id,
        title=request.title,
        content=request.content,
        source=request.source,
        source_type="manual",
        author=request.author,
        tags=request.tags,
    )


# ---------------------------------------------------------------------------
# Knowledge – ingest (file upload)
# ---------------------------------------------------------------------------

@app.post("/knowledge/artifacts/upload")
async def ingest_file(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str = Form("unknown"),
    tags: str = Form(""),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    content = await extract_text_from_upload(file)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    return await _ingest(
        session=session,
        workspace_id=current_user.workspace_id,
        title=title,
        content=content,
        source="file",
        source_type="file",
        author=author,
        tags=tag_list,
    )


# ---------------------------------------------------------------------------
# Knowledge – ingest (URL)
# ---------------------------------------------------------------------------

class UrlIngestRequest(BaseModel):
    url: str
    title: str = Field(min_length=1, max_length=200)
    author: str = "unknown"
    tags: List[str] = []


@app.post("/knowledge/artifacts/url")
async def ingest_url(
    request: UrlIngestRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    content = await fetch_url(request.url)
    return await _ingest(
        session=session,
        workspace_id=current_user.workspace_id,
        title=request.title,
        content=content,
        source=request.url,
        source_type="url",
        author=request.author,
        tags=request.tags,
    )


async def _ingest(
    session: AsyncSession,
    workspace_id: str,
    title: str,
    content: str,
    source: str,
    source_type: str,
    author: str,
    tags: List[str],
) -> Dict[str, Any]:
    artifact_id = _stable_id("artifact", f"{title}:{content}")
    created_at = datetime.utcnow().isoformat()
    artifact_dict = {"id": artifact_id, "title": title, "content": content, "source": source, "source_type": source_type, "author": author, "tags": tags, "created_at": created_at}
    normalized = ingestion.normalize_format({**artifact_dict, "type": "text"})
    metadata = ingestion.extract_metadata(normalized)
    items, relationships = await _persist_artifact(session, workspace_id, artifact_id, title, content, source, source_type, author, tags, created_at, metadata)
    neo4j_graph.upsert_artifact_graph(artifact_dict, items, relationships)
    await _embed_and_store(items, session)
    await _build_artifact_summary(session, workspace_id, artifact_dict, content)
    return {"artifact": artifact_dict, "items": items, "relationships": relationships, "extracted_count": len(items)}


async def _embed_and_store(
    items: List[Dict[str, Any]], session: AsyncSession
) -> None:
    """
    Embed extracted items and persist vectors to both Neo4j (primary) and
    SQLite (backup). SQLite vectors are always written so the keyword+cosine
    fallback path works even when Neo4j is down.
    """
    pairs = await embed_items(items)
    if not pairs:
        return

    for item_id, vector in pairs:
        # always persist to SQLite as backup
        ki = await session.get(KnowledgeItem, item_id)
        if ki:
            ki.embedding = vector

        # push to Neo4j when available
        neo4j_graph.upsert_item_embedding(item_id, vector)

    await session.commit()


async def _build_artifact_summary(
    session: AsyncSession,
    workspace_id: str,
    artifact: Dict[str, Any],
    content: str,
) -> None:
    """Generate and persist a condensed LLM summary for the artifact (summary index)."""
    from app.services.llm_extraction import _summarise_text
    existing = (await session.execute(
        select(ArtifactSummary).where(ArtifactSummary.artifact_id == artifact["id"])
    )).scalar_one_or_none()

    summary_text = await _summarise_text(content)
    if not summary_text:
        return

    summary_vec = await embed(summary_text)
    created_at  = datetime.utcnow().isoformat()

    if existing:
        existing.summary   = summary_text
        existing.embedding = summary_vec
    else:
        session.add(ArtifactSummary(
            workspace_id=workspace_id,
            artifact_id=artifact["id"],
            summary=summary_text,
            embedding=summary_vec,
            created_at=created_at,
        ))
    await session.commit()

    # push to Neo4j summary index
    if summary_vec:
        neo4j_graph.upsert_artifact_summary(artifact["id"], summary_text, summary_vec)


# ---------------------------------------------------------------------------
# Review workflow
# ---------------------------------------------------------------------------

@app.get("/knowledge/review")
async def list_review_queue(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[Dict[str, Any]]:
    result = await session.execute(
        select(KnowledgeItem).where(
            KnowledgeItem.workspace_id == current_user.workspace_id,
            KnowledgeItem.review_status == "pending",
        )
    )
    return [_item_dict(i) for i in result.scalars()]


class ReviewDecision(BaseModel):
    status: str = Field(pattern="^(accepted|rejected)$")
    note: str = ""
    title: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@app.patch("/knowledge/review/{item_id}")
async def review_item(
    item_id: str,
    body: ReviewDecision,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    item = await session.get(KnowledgeItem, item_id)
    if not item or item.workspace_id != current_user.workspace_id:
        raise HTTPException(status_code=404, detail="Item not found")
    item.review_status = body.status
    item.review_note = body.note
    if body.title:
        item.title = body.title
    if body.details is not None:
        item.details = body.details
    await session.commit()
    return _item_dict(item)


# ---------------------------------------------------------------------------
# Transcript ingestion (LLM)
# ---------------------------------------------------------------------------

class TranscriptRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=100_000)
    source_type: str = "transcript"  # transcript | email | slack
    author: str = "unknown"
    tags: List[str] = []


@app.post("/knowledge/artifacts/transcript")
async def ingest_transcript(
    request: TranscriptRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    llm_result = await extract_from_transcript(request.content)

    artifact_id = _stable_id("artifact", f"{request.title}:{request.content}")
    created_at = datetime.utcnow().isoformat()
    artifact_dict = {
        "id": artifact_id, "title": request.title, "content": request.content,
        "source": request.source_type, "source_type": request.source_type,
        "author": request.author, "tags": request.tags, "created_at": created_at,
    }
    normalized = ingestion.normalize_format({**artifact_dict, "type": "text"})
    metadata = {**ingestion.extract_metadata(normalized), "summary": llm_result.get("summary", "")}
    if llm_result.get("llm_error"):
        metadata["llm_error"] = llm_result["llm_error"]

    # Build items from LLM output
    items: List[Dict[str, Any]] = []
    for d in llm_result.get("decisions", []):
        t = d.get("what", "").strip()[:180]
        if t:
            items.append({"id": _stable_id("decision", f"{artifact_id}:{t}"), "artifact_id": artifact_id,
                          "title": t, "type": "decision", "author": d.get("who") or request.author,
                          "date": created_at, "tags": request.tags, "details": d})
    for a in llm_result.get("action_items", []):
        t = a.get("task", "").strip()[:180]
        if t:
            items.append({"id": _stable_id("action", f"{artifact_id}:{t}"), "artifact_id": artifact_id,
                          "title": t, "type": "action-item", "author": a.get("owner") or request.author,
                          "date": created_at, "tags": request.tags, "details": a})
    for r in llm_result.get("risks", []):
        t = r.get("risk", "").strip()[:180]
        if t:
            items.append({"id": _stable_id("risk", f"{artifact_id}:{t}"), "artifact_id": artifact_id,
                          "title": t, "type": "risk", "author": request.author,
                          "date": created_at, "tags": request.tags, "details": r})

    # Persist
    existing = await session.get(Artifact, artifact_id)
    if not existing:
        session.add(Artifact(
            id=artifact_id, workspace_id=current_user.workspace_id,
            title=request.title, content=request.content,
            source=request.source_type, source_type=request.source_type,
            author=request.author, tags=request.tags,
            created_at=created_at, metadata_=metadata,
        ))
    else:
        existing.metadata_ = metadata

    item_ids = {i["id"] for i in items}
    old_items = (await session.execute(
        select(KnowledgeItem).where(KnowledgeItem.artifact_id == artifact_id)
    )).scalars().all()
    for old in old_items:
        if old.id not in item_ids:
            await session.delete(old)

    for item in items:
        ki = await session.get(KnowledgeItem, item["id"])
        if ki:
            ki.title = item["title"]; ki.details = item["details"]
        else:
            session.add(KnowledgeItem(
                id=item["id"], workspace_id=current_user.workspace_id,
                artifact_id=artifact_id, title=item["title"], type=item["type"],
                author=item["author"], date=item["date"], tags=item["tags"],
                details=item["details"], review_status="pending",
            ))

    relationships = [{"from": artifact_id, "to": i["id"], "type": "CONTAINS"} for i in items]
    existing_rel_keys = {
        (r.from_id, r.to_id, r.type)
        for r in (await session.execute(
            select(Relationship).where(Relationship.from_id == artifact_id)
        )).scalars()
    }
    for rel in relationships:
        if (rel["from"], rel["to"], rel["type"]) not in existing_rel_keys:
            session.add(Relationship(
                id=str(uuid.uuid4()), workspace_id=current_user.workspace_id,
                from_id=rel["from"], to_id=rel["to"], type=rel["type"],
            ))

    await session.commit()
    neo4j_graph.upsert_artifact_graph(artifact_dict, items, relationships)
    await _embed_and_store(items, session)
    await _build_artifact_summary(session, current_user.workspace_id, artifact_dict, request.content)

    return {
        "artifact": artifact_dict,
        "items": items,
        "relationships": relationships,
        "extracted_count": len(items),
        "summary": llm_result.get("summary", ""),
        "llm_error": llm_result.get("llm_error"),
    }


# ---------------------------------------------------------------------------
# GraphRAG query
# ---------------------------------------------------------------------------

class GraphRagRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=20)
    history: List[Dict[str, str]] = []   # [{"role": "user"|"assistant", "content": "..."}]


@app.post("/knowledge/graphrag/query")
async def graphrag_query_endpoint(
    request: GraphRagRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    ws = current_user.workspace_id
    t0 = datetime.utcnow()

    all_items = (
        await session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.workspace_id == ws,
                KnowledgeItem.review_status != "rejected",
            )
        )
    ).scalars().all()

    fallback = [{**_item_dict(i), "embedding": i.embedding} for i in all_items]

    cross_links_rows = (
        await session.execute(select(CrossLink).where(CrossLink.workspace_id == ws))
    ).scalars().all()
    cross_links = [{"item_id_a": cl.item_id_a, "item_id_b": cl.item_id_b} for cl in cross_links_rows]

    # load artifact summaries for the summary index fallback
    summary_rows = (
        await session.execute(select(ArtifactSummary).where(ArtifactSummary.workspace_id == ws))
    ).scalars().all()
    artifact_summaries = [
        {"artifact_id": s.artifact_id, "title": "", "summary": s.summary, "embedding": s.embedding}
        for s in summary_rows
    ]

    result = await graphrag_query(
        question=request.question,
        neo4j_store=neo4j_graph,
        fallback_items=fallback,
        cross_links=cross_links,
        artifact_summaries=artifact_summaries,
        history=request.history or None,
        top_k=request.top_k,
    )

    # persist query log
    latency_ms = int((datetime.utcnow() - t0).total_seconds() * 1000)
    session.add(QueryLog(
        workspace_id=ws,
        question=request.question,
        sub_queries=result.get("sub_queries", []),
        hyde_doc=result.get("hyde_doc"),
        route=result.get("route"),
        retrieval_mode=result.get("retrieval_mode"),
        context_node_ids=[n.get("id") for n in result.get("context_nodes", [])],
        citations=result.get("citations", []),
        answer_snippet=result.get("answer", "")[:400],
        latency_ms=result.get("latency_ms", latency_ms),
        created_at=t0.isoformat(),
    ))
    await session.commit()

    return result


# ---------------------------------------------------------------------------
# Cross-source linking
# ---------------------------------------------------------------------------

@app.post("/knowledge/link")
async def run_cross_link(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Scan all knowledge items in the workspace and create cross-source links."""
    ws = current_user.workspace_id
    all_items = (await session.execute(
        select(KnowledgeItem).where(KnowledgeItem.workspace_id == ws)
    )).scalars().all()

    item_dicts = [{"id": i.id, "artifact_id": i.artifact_id, "title": i.title} for i in all_items]
    links = find_cross_links(item_dicts)

    # Remove stale cross-links for this workspace, re-insert fresh ones
    old_links = (await session.execute(
        select(CrossLink).where(CrossLink.workspace_id == ws)
    )).scalars().all()
    for old in old_links:
        await session.delete(old)

    created = []
    for id_a, id_b, score in links:
        cl = CrossLink(
            id=str(uuid.uuid4()),
            workspace_id=ws,
            item_id_a=id_a,
            item_id_b=id_b,
            score=str(score),
        )
        session.add(cl)
        created.append({"item_id_a": id_a, "item_id_b": id_b, "score": score})

        # Also persist as graph relationships
        session.add(Relationship(
            id=str(uuid.uuid4()), workspace_id=ws,
            from_id=id_a, to_id=id_b, type="RELATED_TO",
        ))

    await session.commit()
    return {"links_created": len(created), "links": created}


@app.get("/knowledge/links")
async def get_cross_links(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[Dict[str, Any]]:
    result = await session.execute(
        select(CrossLink).where(CrossLink.workspace_id == current_user.workspace_id)
    )
    return [{"item_id_a": cl.item_id_a, "item_id_b": cl.item_id_b, "score": float(cl.score)}
            for cl in result.scalars()]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@app.get("/knowledge/search")
async def search_knowledge(
    q: str = "",
    type: Optional[str] = None,
    source_type: Optional[str] = None,
    tag: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    ws = current_user.workspace_id
    q_lower = q.strip().lower()

    items_q = select(KnowledgeItem).where(KnowledgeItem.workspace_id == ws)
    if type:
        items_q = items_q.where(KnowledgeItem.type == type)
    all_items = (await session.execute(items_q)).scalars().all()

    artifacts_q = select(Artifact).where(Artifact.workspace_id == ws)
    if source_type:
        artifacts_q = artifacts_q.where(Artifact.source_type == source_type)
    all_artifacts = (await session.execute(artifacts_q)).scalars().all()
    artifact_map = {a.id: a for a in all_artifacts}

    def _matches_item(i: KnowledgeItem) -> bool:
        if source_type and artifact_map.get(i.artifact_id or "") is None:
            return False
        if tag and tag.lower() not in [t.lower() for t in (i.tags or [])]:
            return False
        if not q_lower:
            return True
        haystack = f"{i.title} {' '.join(i.tags or [])} {i.type}".lower()
        return q_lower in haystack

    def _matches_artifact(a: Artifact) -> bool:
        if tag and tag.lower() not in [t.lower() for t in (a.tags or [])]:
            return False
        if not q_lower:
            return True
        haystack = f"{a.title} {a.author} {' '.join(a.tags or [])}".lower()
        return q_lower in haystack

    matched_items = [_item_dict(i) for i in all_items if _matches_item(i)]
    matched_artifacts = [_artifact_dict(a) for a in all_artifacts if _matches_artifact(a)]

    return {
        "query": q,
        "filters": {"type": type, "source_type": source_type, "tag": tag},
        "knowledge_items": matched_items,
        "artifacts": matched_artifacts,
        "total": len(matched_items) + len(matched_artifacts),
    }


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------

class PlaybookRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    steps: List[Dict[str, Any]]


@app.post("/knowledge/playbooks")
async def create_playbook(
    request: PlaybookRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    playbook = curation.build_playbook(request.title, request.steps)
    session.add(Playbook(
        id=playbook["id"],
        workspace_id=current_user.workspace_id,
        title=playbook["title"],
        steps=playbook["steps"],
        category=playbook["category"],
    ))
    await session.commit()
    return playbook


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

@app.get("/knowledge/graph")
async def knowledge_graph(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    if neo4j_graph.enabled and neo4j_graph.verify():
        neo4j_data = neo4j_graph.visualization_data()
        if neo4j_data["nodes"]:
            return neo4j_data

    ws = current_user.workspace_id
    artifacts = (await session.execute(select(Artifact).where(Artifact.workspace_id == ws))).scalars().all()
    items = (await session.execute(select(KnowledgeItem).where(KnowledgeItem.workspace_id == ws))).scalars().all()
    rels = (await session.execute(select(Relationship).where(Relationship.workspace_id == ws))).scalars().all()

    nodes = [{"id": a.id, "label": a.title, "type": "artifact"} for a in artifacts] + \
            [{"id": i.id, "label": i.title, "type": i.type} for i in items]
    edges = [{"from": r.from_id, "to": r.to_id, "type": r.type} for r in rels]
    return graph_builder.prepare_visualization_data({"nodes": nodes, "edges": edges})


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _artifact_dict(a: Artifact) -> Dict[str, Any]:
    return {
        "id": a.id,
        "title": a.title,
        "content": a.content,
        "source": a.source,
        "source_type": a.source_type or "manual",
        "author": a.author,
        "tags": a.tags or [],
        "created_at": a.created_at,
        "metadata": a.metadata_ or {},
    }


def _item_dict(i: KnowledgeItem) -> Dict[str, Any]:
    return {
        "id": i.id,
        "artifact_id": i.artifact_id,
        "title": i.title,
        "type": i.type,
        "author": i.author,
        "date": i.date,
        "tags": i.tags or [],
        "details": i.details or {},
        "review_status": i.review_status,
        "review_note": i.review_note or "",
    }
