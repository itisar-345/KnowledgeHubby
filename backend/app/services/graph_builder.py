from __future__ import annotations

from typing import Any, Dict, List


class GraphBuilder:
    """
    Lightweight graph helper. Only prepare_visualization_data is wired into
    the API — it is used as the SQLite fallback in GET /knowledge/graph when
    Neo4j is unavailable.
    """

    def __init__(self, neo4j_client: Any) -> None:
        self.neo4j = neo4j_client

    def prepare_visualization_data(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = [
            {"id": n["id"], "label": n.get("label", ""), "type": n.get("type")}
            for n in graph.get("nodes", [])
        ]
        edges: List[Dict[str, Any]] = [
            {"source": e["from"], "target": e["to"], "label": e.get("type")}
            for e in graph.get("edges", [])
        ]
        return {"nodes": nodes, "edges": edges, "layout": "force-directed"}
