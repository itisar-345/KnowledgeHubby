from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover - keeps local JSON mode working without the driver
    GraphDatabase = None


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
            edges = [edge for edge in record["edges"] if edge.get("source") and edge.get("target")]
            return {"nodes": record["nodes"], "edges": edges, "layout": "force-directed"}

    @staticmethod
    def _upsert_artifact_graph(tx, artifact: Dict[str, Any], items: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> None:
        tx.run(
            """
            MERGE (artifact:Artifact {id: $id})
            SET artifact.title = $title,
                artifact.source = $source,
                artifact.author = $author,
                artifact.created_at = $created_at,
                artifact.tags = $tags,
                artifact.kind = 'artifact'
            """,
            id=artifact["id"],
            title=artifact["title"],
            source=artifact.get("source", "manual"),
            author=artifact.get("author", "unknown"),
            created_at=artifact.get("created_at"),
            tags=artifact.get("tags", []),
        )

        for item in items:
            tx.run(
                """
                MERGE (item:KnowledgeItem {id: $id})
                SET item.title = $title,
                    item.kind = $kind,
                    item.author = $author,
                    item.date = $date,
                    item.tags = $tags,
                    item.confidence = $confidence,
                    item.artifact_id = $artifact_id
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

        for relationship in relationships:
            tx.run(
                """
                MATCH (source {id: $source_id})
                MATCH (target {id: $target_id})
                MERGE (source)-[rel:CONTAINS]->(target)
                SET rel.kind = $kind
                """,
                source_id=relationship["from"],
                target_id=relationship["to"],
                kind=relationship.get("type", "CONTAINS"),
            )
