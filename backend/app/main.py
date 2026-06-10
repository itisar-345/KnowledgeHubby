from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.services.curation_layer import CurationLayer
from app.services.graph_builder import GraphBuilder
from app.services.ingestion_normalization import IngestionNormalization
from app.services.knowledge_extraction import KnowledgeExtraction
from app.store import JsonKnowledgeStore


app = FastAPI(title="Knowledge Hubs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = JsonKnowledgeStore()
ingestion = IngestionNormalization()
extractor = KnowledgeExtraction()
graph_builder = GraphBuilder(None)
curation = CurationLayer()


class ArtifactRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=100_000)
    source: str = "manual"
    author: str = "unknown"
    tags: List[str] = []


class PlaybookRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    steps: List[Dict[str, Any]]


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _sentiment_type(label: str) -> str:
    return label.replace("_", "-")


def _build_items(artifact_id: str, artifact: ArtifactRequest) -> List[Dict[str, Any]]:
    text = artifact.content
    extracted = {
        "entities": extractor.extract_entities(text),
        "decisions": extractor.extract_decisions(text),
        "how_tos": extractor.mine_how_to_patterns(text),
        "checklists": extractor.detect_checklists(text),
        "best_practices": extractor.identify_best_practices(text),
        "lessons": extractor.extract_lessons_learned(text),
        "risks": extractor.recognize_risk_patterns(text),
        "success_factors": extractor.identify_success_factors(text),
    }

    items: List[Dict[str, Any]] = []
    created_at = datetime.utcnow().isoformat()

    for label in ["decisions", "how_tos", "lessons", "risks"]:
        for entry in extracted[label]:
            title = entry.get("what") or entry.get("pattern") or entry.get("lesson") or entry.get("risk")
            if title:
                items.append({
                    "id": _stable_id(label, f"{artifact_id}:{title}"),
                    "artifact_id": artifact_id,
                    "title": title[:180],
                    "type": _sentiment_type(label[:-1]),
                    "author": artifact.author,
                    "date": created_at,
                    "tags": artifact.tags,
                    "details": entry,
                })

    for practice in extracted["best_practices"]:
        items.append({
            "id": _stable_id("practice", f"{artifact_id}:{practice}"),
            "artifact_id": artifact_id,
            "title": practice[:180],
            "type": "best-practice",
            "author": artifact.author,
            "date": created_at,
            "tags": artifact.tags,
            "details": {"practice": practice},
        })

    for checklist in extracted["checklists"]:
        items.append({
            "id": _stable_id("checklist", f"{artifact_id}:{checklist}"),
            "artifact_id": artifact_id,
            "title": checklist[:180],
            "type": "checklist",
            "author": artifact.author,
            "date": created_at,
            "tags": artifact.tags,
            "details": {"item": checklist},
        })

    return items


def _build_relationships(artifact_id: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {"from": artifact_id, "to": item["id"], "type": "CONTAINS"}
        for item in items
    ]


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy"}


@app.get("/knowledge")
async def list_knowledge() -> Dict[str, Any]:
    return store.all()


@app.post("/knowledge/artifacts")
async def ingest_artifact(request: ArtifactRequest) -> Dict[str, Any]:
    artifact_id = _stable_id("artifact", f"{request.title}:{request.content}")
    artifact = {
        "id": artifact_id,
        "title": request.title,
        "content": request.content,
        "source": request.source,
        "author": request.author,
        "tags": request.tags,
        "created_at": datetime.utcnow().isoformat(),
    }

    normalized = ingestion.normalize_format({**artifact, "type": "text"})
    metadata = ingestion.extract_metadata(normalized)
    items = _build_items(artifact_id, request)
    relationships = _build_relationships(artifact_id, items)

    data = store.all()
    data["artifacts"] = [a for a in data["artifacts"] if a["id"] != artifact_id] + [{**artifact, "metadata": metadata}]
    existing_item_ids = {item["id"] for item in items}
    data["knowledge_items"] = [
        item for item in data["knowledge_items"] if item["id"] not in existing_item_ids
    ] + items
    data["relationships"].extend(relationships)
    store.replace(data)

    return {
        "artifact": artifact,
        "items": items,
        "relationships": relationships,
    }


@app.post("/knowledge/playbooks")
async def create_playbook(request: PlaybookRequest) -> Dict[str, Any]:
    playbook = curation.build_playbook(request.title, request.steps)
    store.append("playbooks", playbook)
    return playbook


@app.get("/knowledge/graph")
async def knowledge_graph() -> Dict[str, Any]:
    data = store.all()
    nodes = [
        {"id": artifact["id"], "label": artifact["title"], "type": "artifact"}
        for artifact in data["artifacts"]
    ] + [
        {"id": item["id"], "label": item["title"], "type": item["type"]}
        for item in data["knowledge_items"]
    ]
    return graph_builder.prepare_visualization_data({
        "nodes": nodes,
        "edges": data["relationships"],
    })
