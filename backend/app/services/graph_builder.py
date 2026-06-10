from typing import Dict, List, Any
from datetime import datetime

class GraphBuilder:
    def __init__(self, neo4j_client):
        self.neo4j = neo4j_client

    def link_decision_to_rationale(self, decision_id: str, rationale: str, evidence: List[str]) -> Dict:
        return {
            'decision': decision_id,
            'rationale': rationale,
            'evidence': evidence,
            'relationship': 'JUSTIFIED_BY'
        }

    def link_project_artifacts(self, project_id: str, artifacts: List[str], contributors: List[str]) -> Dict:
        links = []
        for artifact in artifacts:
            links.append({'from': project_id, 'to': artifact, 'type': 'HAS_ARTIFACT'})
        for contributor in contributors:
            links.append({'from': project_id, 'to': contributor, 'type': 'HAS_CONTRIBUTOR'})
        return {'project': project_id, 'links': links}

    def link_task_dependencies(self, task_id: str, owner: str, dependencies: List[str]) -> Dict:
        links = [
            {'from': task_id, 'to': owner, 'type': 'OWNED_BY'},
        ]
        for dep in dependencies:
            links.append({'from': task_id, 'to': dep, 'type': 'DEPENDS_ON'})
        return {'task': task_id, 'links': links}

    def link_concept_definition(self, concept: str, definition: str, examples: List[str]) -> Dict:
        return {
            'concept': concept,
            'definition': definition,
            'examples': examples,
            'relationships': [
                {'type': 'DEFINED_AS', 'target': definition},
                *[{'type': 'EXAMPLE_OF', 'target': ex} for ex in examples]
            ]
        }

    def track_temporal_relationships(self, event1: Dict, event2: Dict) -> Dict:
        time_diff = (event2['timestamp'] - event1['timestamp']).total_seconds()
        return {
            'from': event1['id'],
            'to': event2['id'],
            'type': 'HAPPENED_BEFORE' if time_diff > 0 else 'HAPPENED_AFTER',
            'time_diff_seconds': abs(time_diff)
        }

    def infer_causal_relationships(self, events: List[Dict]) -> List[Dict]:
        causal_links = []
        for i, event1 in enumerate(events):
            for event2 in events[i+1:]:
                if self._is_causal(event1, event2):
                    causal_links.append({
                        'cause': event1['id'],
                        'effect': event2['id'],
                        'confidence': 0.7
                    })
        return causal_links

    def optimize_query(self, query: str) -> str:
        # Add indexes and query hints
        if 'MATCH' in query and 'WHERE' in query:
            return query.replace('MATCH', 'MATCH (n) USING INDEX n:Label(property)')
        return query

    def prepare_visualization_data(self, graph: Dict) -> Dict:
        nodes = [{'id': n['id'], 'label': n.get('label', ''), 'type': n.get('type')} for n in graph.get('nodes', [])]
        edges = [{'source': e['from'], 'target': e['to'], 'label': e.get('type')} for e in graph.get('edges', [])]
        return {
            'nodes': nodes,
            'edges': edges,
            'layout': 'force-directed'
        }

    def create_graph_nodes(self, entities: List[Dict]) -> List[Dict]:
        nodes = []
        for entity in entities:
            nodes.append({
                'id': entity['id'],
                'type': entity['type'],
                'properties': entity.get('properties', {}),
                'created_at': datetime.now()
            })
        return nodes

    def create_graph_edges(self, relationships: List[Dict]) -> List[Dict]:
        edges = []
        for rel in relationships:
            edges.append({
                'from': rel['from'],
                'to': rel['to'],
                'type': rel['type'],
                'properties': rel.get('properties', {}),
                'created_at': datetime.now()
            })
        return edges

    def _is_causal(self, event1: Dict, event2: Dict) -> bool:
        # Simple heuristic: temporal proximity and keyword matching
        time_diff = abs((event2.get('timestamp', datetime.now()) - event1.get('timestamp', datetime.now())).total_seconds())
        if time_diff < 3600:  # Within 1 hour
            causal_keywords = ['caused', 'led to', 'resulted in', 'because of']
            text = event2.get('text', '')
            return any(kw in text.lower() for kw in causal_keywords)
        return False
