from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable, AuthError
except ImportError:
    GraphDatabase = None  # type: ignore
    ServiceUnavailable = Exception  # type: ignore
    AuthError = Exception  # type: ignore

# Dimension and provider signature sourced from the active EmbeddingProvider.
from app.services.embeddings import EMBEDDING_DIM, EMBEDDING_PROVIDER_NAME


class Neo4jGraphStore:
    """
    Primary graph + vector store backed by Neo4j.

    Connection is attempted eagerly on init. If Neo4j is unreachable the
    instance stays in a degraded state (`enabled=False`) and every method
    returns an empty result so callers can fall through to the SQLite backup.
    All failures are logged at WARNING level so they are visible in the server
    log without crashing the application.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ) -> None:
        self.uri = uri or os.getenv("NEO4J_URI")
        self.username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.driver = None
        self._live = False
        self._item_index = "knowledge_items_local_all_MiniLM_L6_v2"
        self._summary_index = "artifact_summaries_local_all_MiniLM_L6_v2"

        if not GraphDatabase:
            logger.warning("neo4j driver package not installed — graph store disabled")
            return
        if not self.uri or not self.password:
            logger.warning(
                "NEO4J_URI / NEO4J_PASSWORD not set — graph store disabled. "
                "Set these env vars to enable GraphRAG."
            )
            return

        try:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.username, self.password)
            )
            self.driver.verify_connectivity()
            self._live = True
            logger.info("Neo4j connected: %s (db=%s)", self.uri, self.database)
        except (ServiceUnavailable, AuthError, Exception) as exc:
            logger.warning("Neo4j connection failed (%s) — falling back to SQLite vectors", exc)
            if self.driver:
                try:
                    self.driver.close()
                except Exception:
                    pass
            self.driver = None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._live

    def close(self) -> None:
        if self.driver:
            self.driver.close()

    def verify(self) -> bool:
        """Re-check live connectivity (used by /health)."""
        if not self.driver:
            return False
        try:
            self.driver.verify_connectivity()
            self._live = True
            return True
        except Exception as exc:
            logger.warning("Neo4j connectivity check failed: %s", exc)
            self._live = False
            return False

    # ------------------------------------------------------------------
    # Vector index bootstrap
    # ------------------------------------------------------------------

    def ensure_vector_index(self) -> None:
        """
        Create vector indexes named by provider signature so switching providers
        never silently corrupts an existing index (Phase 2 requirement).
        Index names: knowledge_items_{provider_sig}, artifact_summaries_{provider_sig}
        """
        if not self.driver:
            return
        sig = EMBEDDING_PROVIDER_NAME.replace(":", "_").replace("-", "_").replace(".", "_")
        item_index = f"knowledge_items_{sig}"
        summary_index = f"artifact_summaries_{sig}"
        try:
            with self.driver.session(database=self.database) as session:
                session.run(
                    f"""
                    CREATE VECTOR INDEX {item_index} IF NOT EXISTS
                    FOR (n:KnowledgeItem) ON n.embedding
                    OPTIONS {{
                        indexConfig: {{
                            `vector.dimensions`: $dim,
                            `vector.similarity_function`: 'cosine'
                        }}
                    }}
                    """,
                    dim=EMBEDDING_DIM,
                )
                session.run(
                    f"""
                    CREATE VECTOR INDEX {summary_index} IF NOT EXISTS
                    FOR (n:Artifact) ON n.summary_embedding
                    OPTIONS {{
                        indexConfig: {{
                            `vector.dimensions`: $dim,
                            `vector.similarity_function`: 'cosine'
                        }}
                    }}
                    """,
                    dim=EMBEDDING_DIM,
                )
            logger.info(
                "Neo4j vector indexes ensured: %s, %s (dim=%d)",
                item_index, summary_index, EMBEDDING_DIM,
            )
            # store active index names for retrieval queries
            self._item_index = item_index
            self._summary_index = summary_index
        except Exception as exc:
            logger.warning("Could not create vector index: %s", exc)

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def upsert_artifact_graph(
        self,
        artifact: Dict[str, Any],
        items: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> None:
        if not self.driver:
            return
        try:
            with self.driver.session(database=self.database) as session:
                session.execute_write(
                    self._upsert_artifact_graph, artifact, items, relationships
                )
        except Exception as exc:
            logger.warning("Neo4j upsert_artifact_graph failed: %s", exc)

    def upsert_item_embedding(self, item_id: str, embedding: List[float]) -> None:
        if not self.driver:
            return
        try:
            with self.driver.session(database=self.database) as session:
                session.run(
                    """
                    MATCH (n:KnowledgeItem {id: $id})
                    CALL db.create.setNodeVectorProperty(n, 'embedding', $embedding)
                    """,
                    id=item_id,
                    embedding=embedding,
                )
        except Exception as exc:
            logger.warning("Neo4j upsert_item_embedding failed for %s: %s", item_id, exc)

    def upsert_artifact_summary(self, artifact_id: str, summary: str, embedding: List[float]) -> None:
        """Store condensed summary text + embedding on the Artifact node (summary index)."""
        if not self.driver:
            return
        try:
            with self.driver.session(database=self.database) as session:
                session.run(
                    """
                    MATCH (a:Artifact {id: $id})
                    SET a.summary = $summary
                    CALL db.create.setNodeVectorProperty(a, 'summary_embedding', $embedding)
                    """,
                    id=artifact_id,
                    summary=summary,
                    embedding=embedding,
                )
        except Exception as exc:
            logger.warning("Neo4j upsert_artifact_summary failed for %s: %s", artifact_id, exc)

    def summary_vector_search(
        self, query_embedding: List[float], top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """Retrieve top-k artifact summaries by vector similarity."""
        if not self.driver:
            return []
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(
                    f"""
                    CALL db.index.vector.queryNodes(
                        '{self._summary_index}', $top_k, $embedding
                    )
                    YIELD node, score
                    RETURN node.id      AS artifact_id,
                           node.title   AS title,
                           node.summary AS summary,
                           score
                    """,
                    top_k=top_k,
                    embedding=query_embedding,
                )
                return [dict(r) for r in result]
        except Exception as exc:
            logger.warning("Neo4j summary_vector_search failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # GraphRAG retrieval
    # ------------------------------------------------------------------

    def vector_search(
        self, query_embedding: List[float], top_k: int = 8
    ) -> List[Dict[str, Any]]:
        """Cosine-similarity ANN search over the provider-versioned vector index."""
        if not self.driver:
            return []
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(
                    f"""
                    CALL db.index.vector.queryNodes(
                        '{self._item_index}', $top_k, $embedding
                    )
                    YIELD node, score
                    RETURN node.id          AS id,
                           node.title       AS title,
                           node.kind        AS kind,
                           node.artifact_id AS artifact_id,
                           node.tags        AS tags,
                           score
                    """,
                    top_k=top_k,
                    embedding=query_embedding,
                )
                return [dict(r) for r in result]
        except Exception as exc:
            logger.warning("Neo4j vector_search failed: %s", exc)
            return []

    def graph_expand(
        self, item_ids: List[str], hops: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Walk up to `hops` relationship hops from seed nodes.
        Tries APOC first; falls back to plain Cypher on failure.
        """
        if not self.driver or not item_ids:
            return []
        try:
            return self._graph_expand_apoc(item_ids, hops)
        except Exception:
            try:
                return self._graph_expand_plain(item_ids)
            except Exception as exc:
                logger.warning("Neo4j graph_expand failed: %s", exc)
                return []

    def _graph_expand_apoc(
        self, item_ids: List[str], hops: int
    ) -> List[Dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (seed:KnowledgeItem) WHERE seed.id IN $ids
                CALL apoc.path.subgraphNodes(seed, {
                    maxLevel: $hops,
                    labelFilter: 'KnowledgeItem|Artifact'
                })
                YIELD node
                RETURN DISTINCT
                    node.id          AS id,
                    node.title       AS title,
                    node.kind        AS kind,
                    node.artifact_id AS artifact_id,
                    labels(node)     AS labels
                """,
                ids=item_ids,
                hops=hops,
            )
            return [dict(r) for r in result]

    def _graph_expand_plain(self, item_ids: List[str]) -> List[Dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (seed:KnowledgeItem)-[r]-(neighbour)
                WHERE seed.id IN $ids
                  AND (neighbour:KnowledgeItem OR neighbour:Artifact)
                RETURN DISTINCT
                    neighbour.id          AS id,
                    neighbour.title       AS title,
                    neighbour.kind        AS kind,
                    neighbour.artifact_id AS artifact_id,
                    labels(neighbour)     AS labels
                """,
                ids=item_ids,
            )
            return [dict(r) for r in result]

    def retrieve_for_rag(
        self,
        query_embedding: List[float],
        top_k: int = 8,
        expand_hops: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Full GraphRAG retrieval:
          1. Vector ANN → seed nodes (with cosine scores)
          2. Graph walk from seeds → neighbourhood nodes
          3. Rerank: seeds keep their cosine score; neighbours get a
             proximity-discounted score (seed_score * 0.7) so the
             final list is ordered by relevance, not arbitrary graph order
        """
        seeds = self.vector_search(query_embedding, top_k=top_k)
        if not seeds:
            return []

        seed_score_map = {s["id"]: s.get("score", 0.0) for s in seeds}
        seed_ids = list(seed_score_map)

        neighbours = self.graph_expand(seed_ids, hops=expand_hops)

        seen: set[str] = set()
        combined: List[Dict[str, Any]] = []

        for node in seeds:
            if node["id"] not in seen:
                seen.add(node["id"])
                combined.append({**node, "retrieved_by": "vector"})

        for node in neighbours:
            nid = node.get("id")
            if nid and nid not in seen:
                seen.add(nid)
                # find the highest-scoring seed that reached this neighbour
                proximity_score = max(seed_score_map.values(), default=0.0) * 0.7
                combined.append({
                    **node,
                    "retrieved_by": "graph",
                    "score": proximity_score,
                })

        # sort descending by score
        combined.sort(key=lambda n: n.get("score") or 0.0, reverse=True)
        return combined

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def visualization_data(self) -> Dict[str, Any]:
        if not self.driver:
            return {"nodes": [], "edges": [], "layout": "force-directed"}
        try:
            query = """
            MATCH (n) WHERE n:Artifact OR n:KnowledgeItem
            OPTIONAL MATCH (n)-[r]->(m) WHERE m:Artifact OR m:KnowledgeItem
            RETURN
              collect(DISTINCT {
                id: n.id,
                label: coalesce(n.title, n.id),
                type: coalesce(n.kind, CASE WHEN n:Artifact THEN 'artifact'
                                            ELSE 'knowledge-item' END)
              }) AS nodes,
              collect(DISTINCT {
                source: n.id, target: m.id, label: type(r)
              }) AS edges
            """
            with self.driver.session(database=self.database) as session:
                record = session.run(query).single()
                if not record:
                    return {"nodes": [], "edges": [], "layout": "force-directed"}
                edges = [
                    e for e in record["edges"]
                    if e.get("source") and e.get("target")
                ]
                return {
                    "nodes": record["nodes"],
                    "edges": edges,
                    "layout": "force-directed",
                }
        except Exception as exc:
            logger.warning("Neo4j visualization_data failed: %s", exc)
            return {"nodes": [], "edges": [], "layout": "force-directed"}

    # ------------------------------------------------------------------
    # Internal write transaction
    # ------------------------------------------------------------------

    @staticmethod
    def _upsert_artifact_graph(
        tx,
        artifact: Dict[str, Any],
        items: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> None:
        tx.run(
            """
            MERGE (a:Artifact {id: $id})
            SET a.title = $title, a.source = $source,
                a.source_type = $source_type, a.author = $author,
                a.created_at = $created_at, a.tags = $tags, a.kind = 'artifact'
            """,
            id=artifact["id"],
            title=artifact["title"],
            source=artifact.get("source", "manual"),
            source_type=artifact.get("source_type", "manual"),
            author=artifact.get("author", "unknown"),
            created_at=artifact.get("created_at"),
            tags=artifact.get("tags", []),
        )
        for item in items:
            tx.run(
                """
                MERGE (n:KnowledgeItem {id: $id})
                SET n.title = $title, n.kind = $kind, n.author = $author,
                    n.date = $date, n.tags = $tags,
                    n.confidence = $confidence, n.artifact_id = $artifact_id
                """,
                id=item["id"],
                title=item["title"],
                kind=item["type"],
                author=item.get("author", "unknown"),
                date=item.get("date"),
                tags=item.get("tags", []),
                confidence=item.get("details", {}).get("confidence"),
                artifact_id=item.get("artifact_id"),
            )
        for rel in relationships:
            tx.run(
                """
                MATCH (s {id: $from_id}) MATCH (t {id: $to_id})
                MERGE (s)-[r:CONTAINS]->(t)
                SET r.kind = $kind
                """,
                from_id=rel["from"],
                to_id=rel["to"],
                kind=rel.get("type", "CONTAINS"),
            )
