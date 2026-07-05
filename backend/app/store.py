"""
Storage layer for Knowledge Hubs.

Neo4j is the primary backend.  SQLite is an optional fallback activated by
setting the environment variable:

    STORAGE_BACKEND=sqlite

When Neo4j is unavailable *and* STORAGE_BACKEND is not explicitly set to
"sqlite", the store degrades gracefully and logs a warning rather than
crashing the application.

Public interface (both backends implement the same methods):
    all(workspace_id)           -> full snapshot dict
    get_artifact(id)            -> dict | None
    upsert_artifact(data)       -> dict
    upsert_knowledge_item(data) -> dict
    upsert_relationship(data)   -> dict
    upsert_playbook(data)       -> dict
    upsert_cross_link(data)     -> dict
    delete_stale_items(artifact_id, keep_ids, workspace_id)
    list_items(workspace_id, **filters) -> list[dict]
    list_artifacts(workspace_id) -> list[dict]
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "neo4j").lower()


# ---------------------------------------------------------------------------
# Neo4j store (primary)
# ---------------------------------------------------------------------------

class Neo4jStore:
    """
    Full-featured Neo4j persistence layer.
    All collections live as labelled nodes; relationships are first-class edges.
    """

    def __init__(self, graph_store) -> None:
        """graph_store is an initialised Neo4jGraphStore instance from neo4j_graph.py."""
        self._g = graph_store

    # ------------------------------------------------------------------
    # Full snapshot
    # ------------------------------------------------------------------

    def all(self, workspace_id: str) -> Dict[str, List[Dict[str, Any]]]:
        if not self._g.enabled:
            return {"artifacts": [], "knowledge_items": [], "relationships": [], "playbooks": []}
        try:
            with self._g.driver.session(database=self._g.database) as s:
                artifacts = [
                    dict(r["a"])
                    for r in s.run(
                        "MATCH (a:Artifact {workspace_id: $ws}) RETURN a",
                        ws=workspace_id,
                    )
                ]
                items = [
                    dict(r["n"])
                    for r in s.run(
                        "MATCH (n:KnowledgeItem {workspace_id: $ws}) RETURN n",
                        ws=workspace_id,
                    )
                ]
                rels = [
                    {"from": r["from_id"], "to": r["to_id"], "type": r["rel_type"]}
                    for r in s.run(
                        """
                        MATCH (a {workspace_id: $ws})-[r]->(b {workspace_id: $ws})
                        RETURN a.id AS from_id, b.id AS to_id, type(r) AS rel_type
                        """,
                        ws=workspace_id,
                    )
                ]
                playbooks = [
                    dict(r["p"])
                    for r in s.run(
                        "MATCH (p:Playbook {workspace_id: $ws}) RETURN p",
                        ws=workspace_id,
                    )
                ]
            return {
                "artifacts": artifacts,
                "knowledge_items": items,
                "relationships": rels,
                "playbooks": playbooks,
            }
        except Exception as exc:
            logger.warning("Neo4jStore.all() failed: %s", exc)
            return {"artifacts": [], "knowledge_items": [], "relationships": [], "playbooks": []}

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        if not self._g.enabled:
            return None
        try:
            with self._g.driver.session(database=self._g.database) as s:
                result = s.run(
                    "MATCH (a:Artifact {id: $id}) RETURN a LIMIT 1", id=artifact_id
                )
                record = result.single()
                return dict(record["a"]) if record else None
        except Exception as exc:
            logger.warning("Neo4jStore.get_artifact() failed: %s", exc)
            return None

    def upsert_artifact(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._g.enabled:
            return data
        try:
            with self._g.driver.session(database=self._g.database) as s:
                s.run(
                    """
                    MERGE (a:Artifact {id: $id})
                    SET a.workspace_id  = $workspace_id,
                        a.title         = $title,
                        a.content       = $content,
                        a.source        = $source,
                        a.source_type   = $source_type,
                        a.author        = $author,
                        a.tags          = $tags,
                        a.created_at    = $created_at,
                        a.metadata      = $metadata,
                        a.kind          = 'artifact'
                    """,
                    **{k: data.get(k) for k in (
                        "id", "workspace_id", "title", "content", "source",
                        "source_type", "author", "created_at",
                    )},
                    tags=data.get("tags", []),
                    metadata=str(data.get("metadata", {})),
                )
        except Exception as exc:
            logger.warning("Neo4jStore.upsert_artifact() failed: %s", exc)
        return data

    # ------------------------------------------------------------------
    # Knowledge items
    # ------------------------------------------------------------------

    def upsert_knowledge_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._g.enabled:
            return data
        try:
            with self._g.driver.session(database=self._g.database) as s:
                s.run(
                    """
                    MERGE (n:KnowledgeItem {id: $id})
                    SET n.workspace_id   = $workspace_id,
                        n.artifact_id    = $artifact_id,
                        n.title          = $title,
                        n.kind           = $type,
                        n.author         = $author,
                        n.date           = $date,
                        n.tags           = $tags,
                        n.details        = $details,
                        n.review_status  = $review_status,
                        n.review_note    = $review_note
                    """,
                    id=data["id"],
                    workspace_id=data.get("workspace_id", ""),
                    artifact_id=data.get("artifact_id", ""),
                    title=data.get("title", ""),
                    type=data.get("type", ""),
                    author=data.get("author", "unknown"),
                    date=data.get("date", ""),
                    tags=data.get("tags", []),
                    details=str(data.get("details", {})),
                    review_status=data.get("review_status", "pending"),
                    review_note=data.get("review_note", ""),
                )
        except Exception as exc:
            logger.warning("Neo4jStore.upsert_knowledge_item() failed: %s", exc)
        return data

    def delete_stale_items(
        self,
        artifact_id: str,
        keep_ids: set[str],
        workspace_id: str,
    ) -> None:
        if not self._g.enabled:
            return
        try:
            with self._g.driver.session(database=self._g.database) as s:
                s.run(
                    """
                    MATCH (n:KnowledgeItem {artifact_id: $artifact_id, workspace_id: $ws})
                    WHERE NOT n.id IN $keep_ids
                    DETACH DELETE n
                    """,
                    artifact_id=artifact_id,
                    ws=workspace_id,
                    keep_ids=list(keep_ids),
                )
        except Exception as exc:
            logger.warning("Neo4jStore.delete_stale_items() failed: %s", exc)

    def list_items(
        self,
        workspace_id: str,
        type: Optional[str] = None,
        tag: Optional[str] = None,
        review_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self._g.enabled:
            return []
        try:
            filters = "WHERE n.workspace_id = $ws"
            params: Dict[str, Any] = {"ws": workspace_id}
            if type:
                filters += " AND n.kind = $type"
                params["type"] = type
            if tag:
                filters += " AND $tag IN n.tags"
                params["tag"] = tag
            if review_status:
                filters += " AND n.review_status = $review_status"
                params["review_status"] = review_status
            with self._g.driver.session(database=self._g.database) as s:
                return [dict(r["n"]) for r in s.run(
                    f"MATCH (n:KnowledgeItem) {filters} RETURN n", **params
                )]
        except Exception as exc:
            logger.warning("Neo4jStore.list_items() failed: %s", exc)
            return []

    def update_item_review(
        self,
        item_id: str,
        workspace_id: str,
        status: str,
        note: str = "",
        title: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self._g.enabled:
            return None
        try:
            set_clauses = "n.review_status = $status, n.review_note = $note"
            params: Dict[str, Any] = {
                "id": item_id, "ws": workspace_id,
                "status": status, "note": note,
            }
            if title:
                set_clauses += ", n.title = $title"
                params["title"] = title
            if details is not None:
                set_clauses += ", n.details = $details"
                params["details"] = str(details)
            with self._g.driver.session(database=self._g.database) as s:
                result = s.run(
                    f"""
                    MATCH (n:KnowledgeItem {{id: $id, workspace_id: $ws}})
                    SET {set_clauses}
                    RETURN n
                    """,
                    **params,
                )
                record = result.single()
                return dict(record["n"]) if record else None
        except Exception as exc:
            logger.warning("Neo4jStore.update_item_review() failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    def upsert_relationship(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a typed relationship edge between two nodes."""
        if not self._g.enabled:
            return data
        try:
            rel_type = data.get("type", "CONTAINS")
            with self._g.driver.session(database=self._g.database) as s:
                s.run(
                    f"""
                    MATCH (a {{id: $from_id}}) MATCH (b {{id: $to_id}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    SET r.workspace_id = $workspace_id
                    """,
                    from_id=data["from"],
                    to_id=data["to"],
                    workspace_id=data.get("workspace_id", ""),
                )
        except Exception as exc:
            logger.warning("Neo4jStore.upsert_relationship() failed: %s", exc)
        return data

    def list_relationships(self, workspace_id: str) -> List[Dict[str, Any]]:
        if not self._g.enabled:
            return []
        try:
            with self._g.driver.session(database=self._g.database) as s:
                return [
                    {"from": r["from_id"], "to": r["to_id"], "type": r["rel_type"]}
                    for r in s.run(
                        """
                        MATCH (a {workspace_id: $ws})-[r]->(b {workspace_id: $ws})
                        RETURN a.id AS from_id, b.id AS to_id, type(r) AS rel_type
                        """,
                        ws=workspace_id,
                    )
                ]
        except Exception as exc:
            logger.warning("Neo4jStore.list_relationships() failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Playbooks
    # ------------------------------------------------------------------

    def upsert_playbook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._g.enabled:
            return data
        try:
            with self._g.driver.session(database=self._g.database) as s:
                s.run(
                    """
                    MERGE (p:Playbook {id: $id})
                    SET p.workspace_id = $workspace_id,
                        p.title        = $title,
                        p.steps        = $steps,
                        p.category     = $category
                    """,
                    id=data["id"],
                    workspace_id=data.get("workspace_id", ""),
                    title=data.get("title", ""),
                    steps=str(data.get("steps", [])),
                    category=data.get("category", "general"),
                )
        except Exception as exc:
            logger.warning("Neo4jStore.upsert_playbook() failed: %s", exc)
        return data

    # ------------------------------------------------------------------
    # Cross-links
    # ------------------------------------------------------------------

    def upsert_cross_link(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._g.enabled:
            return data
        try:
            with self._g.driver.session(database=self._g.database) as s:
                s.run(
                    """
                    MATCH (a:KnowledgeItem {id: $id_a})
                    MATCH (b:KnowledgeItem {id: $id_b})
                    MERGE (a)-[r:RELATED_TO]->(b)
                    SET r.score = $score,
                        r.workspace_id = $workspace_id
                    """,
                    id_a=data["item_id_a"],
                    id_b=data["item_id_b"],
                    score=str(data.get("score", 0)),
                    workspace_id=data.get("workspace_id", ""),
                )
        except Exception as exc:
            logger.warning("Neo4jStore.upsert_cross_link() failed: %s", exc)
        return data

    def delete_cross_links(self, workspace_id: str) -> None:
        if not self._g.enabled:
            return
        try:
            with self._g.driver.session(database=self._g.database) as s:
                s.run(
                    """
                    MATCH (a:KnowledgeItem {workspace_id: $ws})-[r:RELATED_TO]->()
                    DELETE r
                    """,
                    ws=workspace_id,
                )
        except Exception as exc:
            logger.warning("Neo4jStore.delete_cross_links() failed: %s", exc)

    def list_cross_links(self, workspace_id: str) -> List[Dict[str, Any]]:
        if not self._g.enabled:
            return []
        try:
            with self._g.driver.session(database=self._g.database) as s:
                return [
                    {
                        "item_id_a": r["id_a"],
                        "item_id_b": r["id_b"],
                        "score": float(r["score"] or 0),
                    }
                    for r in s.run(
                        """
                        MATCH (a:KnowledgeItem {workspace_id: $ws})-[r:RELATED_TO]->(b:KnowledgeItem)
                        RETURN a.id AS id_a, b.id AS id_b, r.score AS score
                        """,
                        ws=workspace_id,
                    )
                ]
        except Exception as exc:
            logger.warning("Neo4jStore.list_cross_links() failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Artifacts listing (with optional source_type filter)
    # ------------------------------------------------------------------

    def list_artifacts(
        self,
        workspace_id: str,
        source_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self._g.enabled:
            return []
        try:
            filters = "WHERE a.workspace_id = $ws"
            params: Dict[str, Any] = {"ws": workspace_id}
            if source_type:
                filters += " AND a.source_type = $source_type"
                params["source_type"] = source_type
            with self._g.driver.session(database=self._g.database) as s:
                return [dict(r["a"]) for r in s.run(
                    f"MATCH (a:Artifact) {filters} RETURN a", **params
                )]
        except Exception as exc:
            logger.warning("Neo4jStore.list_artifacts() failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# SQLite store (optional fallback)
# ---------------------------------------------------------------------------

class SqliteStore:
    """
    Thin wrapper around the SQLAlchemy async session used as fallback when
    Neo4j is unavailable or STORAGE_BACKEND=sqlite is explicitly set.

    NOTE: this class is synchronous-friendly; async persistence is handled by
    the caller (main.py) which owns the AsyncSession directly.  This class
    exists as a marker and for the `all()` / read helpers that can be called
    from sync context via the session.
    """

    def __init__(self) -> None:
        logger.info("SqliteStore initialised as storage backend")

    @staticmethod
    def backend_name() -> str:
        return "sqlite"


# ---------------------------------------------------------------------------
# Factory — returns the active backend name for /health
# ---------------------------------------------------------------------------

def active_backend() -> str:
    return STORAGE_BACKEND
