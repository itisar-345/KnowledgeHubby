from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None


EMBEDDING_DIM = 1536  # text-embedding-3-small dimension


class Neo4jGraphStore:
    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self.uri = uri or os.getenv("NEO4J_URI")
        self.username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.driver = None

        if GraphDatabase and self.uri and self.password:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))

    @property
    def enabled(self) -> bool:
        return self.driver is not None

    def close(self) -> None:
        if self.driver:
            self.driver.close()

    def verify(self) -> bool:
        if not self.driver:
            return False
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Vector index bootstrap
    # ------------------------------------------------------------------

    def ensure_vector_index(self) -> None:
        """Create the Neo4j vector index for KnowledgeItem embeddings if absent."""
        if not self.driver:
            return
        with self.driver.session(database=self.database) as session:
            session.run("""
                CREATE VECTOR INDEX knowledge_item_embeddings IF NOT EXISTS
                FOR (n:KnowledgeItem)
                ON n.embedding
                OPTIONS {
                    indexConfig: {
                        `vector.dimensions`: $dim,
                        `vector.similarity_function`: 'cosine'
                    }
                }
            """, dim=EMBEDDING_DIM)

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
        with self.driver.session(database=self.database) as session:
            session.execute_write(self._upsert_artifact_graph, artifact, items, relationships)

    def upsert_item_embedding(self, item_id: str, embedding: List[float]) -> None:
        """Store a pre-computed embedding vector on a KnowledgeItem node."""
        if not self.driver:
            return
        with self.driver.session(database=self.database) as session:
            session.run(
                """
                MATCH (n:KnowledgeItem {id: $id})
                CALL db.create.setNodeVectorProperty(n, 'embedding', $embedding)
                """,
                id=item_id,
                embedding=embedding,
            )

    # ------------------------------------------------------------------
    # GraphRAG retrieval
    # ------------------------------------------------------------------

    def vector_search(self, query_embedding: List[float], top_k: int = 8) -> List[Dict[str, Any]]:
        """
        Return the top_k KnowledgeItem nodes most similar to the query embedding.
        Each result: {id, title, kind, score}
        """
        if not self.driver:
            return []
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                CALL db.index.vector.queryNodes('knowledge_item_embeddings', $top_k, $embedding)
                YIELD node, score
                RETURN node.id AS id,
                       node.title AS title,
                       node.kind AS kind,
                       node.artifact_id AS artifact_id,
                       node.tags AS tags,
                       score
                """,
                top_k=top_k,
                embedding=query_embedding,
            )
            return [dict(r) for r in result]

    def graph_expand(self, item_ids: List[str], hops: int = 2) -> List[Dict[str, Any]]:
        """
        Starting from seed item_ids, walk up to `hops` relationship hops
        and return neighbouring nodes with their relationship context.
        """
        if not self.driver or not item_ids:
            return []
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (seed:KnowledgeItem)
                WHERE seed.id IN $ids
                CALL apoc.path.subgraphNodes(seed, {
                    maxLevel: $hops,
                    labelFilter: 'KnowledgeItem|Artifact'
                })
                YIELD node
                RETURN DISTINCT
                    node.id        AS id,
                    node.title     AS title,
                    node.kind      AS kind,
                    node.artifact_id AS artifact_id,
                    labels(node)   AS labels
                """,
                ids=item_ids,
                hops=hops,
            )
            return [dict(r) for r in result]

    def graph_expand_fallback(self, item_ids: List[str]) -> List[Dict[str, Any]]:
        """
        APOC-free neighbour expansion — used when APOC is not installed.
        Walks one hop via any relationship from seed nodes.
        """
        if not self.driver or not item_ids:
            return []
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (seed:KnowledgeItem)-[r]-(neighbour)
                WHERE seed.id IN $ids
                  AND (neighbour:KnowledgeItem OR neighbour:Artifact)
                RETURN DISTINCT
                    neighbour.id        AS id,
                    neighbour.title     AS title,
                    neighbour.kind      AS kind,
                    neighbour.artifact_id AS artifact_id,
                    labels(neighbour)   AS labels
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
          1. Vector similarity search → seed nodes
          2. Graph expansion from seeds → neighbourhood context
          3. Deduplicate and return unified context list
        """
        seeds = self.vector_search(query_embedding, top_k=top_k)
        seed_ids = [s["id"] for s in seeds]

        try:
            neighbours = self.graph_expand(seed_ids, hops=expand_hops)
        except Exception:
            neighbours = self.graph_expand_fallback(seed_ids)

        seen: set[str] = set()
        combined: List[Dict[str, Any]] = []
        for node in seeds:
            if node["id"] not in seen:
                seen.add(node["id"])
                combined.append({**node, "retrieved_by": "vector"})
        for node in neighbours:
            if node.get("id") and node["id"] not in seen:
                seen.add(node["id"])
                combined.append({**node, "retrieved_by": "graph", "score": 0.0})
        return combined

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def visualization_data(self) -> Dict[str, Any]:
        if not self.driver:
            return {"nodes": [], "edges": [], "layout": "force-directed"}

        query = """
        MATCH (n)
        WHERE n:Artifact OR n:KnowledgeItem
        OPTIONAL MATCH (n)-[r]->(m)
        WHERE m:Artifact OR m:KnowledgeItem
        RETURN
          collect(DISTINCT {
            id: n.id,
            label: coalesce(n.title, n.id),
            type: coalesce(n.kind, CASE WHEN n:Artifact THEN 'artifact' ELSE 'knowledge-item' END)
          }) AS nodes,
          collect(DISTINCT {
            source: n.id,
            target: m.id,
            label: type(r)
          }) AS edges
        """
        with self.driver.session(database=self.database) as session:
            record = session.run(query).single()
            if not record:
                return {"nodes": [], "edges": [], "layout": "force-directed"}
            edges = [e for e in record["edges"] if e.get("source") and e.get("target")]
            return {"nodes": record["nodes"], "edges": edges, "layout": "force-directed"}

    # ------------------------------------------------------------------
    # Internal write
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
            SET a.title = $title, a.source = $source, a.source_type = $source_type,
                a.author = $author, a.created_at = $created_at,
                a.tags = $tags, a.kind = 'artifact'
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
                MATCH (s {id: $from_id})
                MATCH (t {id: $to_id})
                MERGE (s)-[r:CONTAINS]->(t)
                SET r.kind = $kind
                """,
                from_id=rel["from"],
                to_id=rel["to"],
                kind=rel.get("type", "CONTAINS"),
            )
