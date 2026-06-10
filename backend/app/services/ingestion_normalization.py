from typing import Dict, List, Any
import hashlib
from datetime import datetime

class IngestionNormalization:
    def __init__(self):
        self.seen_hashes = set()

    async def ingest_multi_source(self, sources: List[str]) -> List[Dict]:
        artifacts = []
        for source in sources:
            artifacts.extend(await self._fetch_from_source(source))
        return artifacts

    def deduplicate_artifacts(self, artifacts: List[Dict]) -> List[Dict]:
        unique = []
        for artifact in artifacts:
            content_hash = self._compute_hash(artifact.get('content', ''))
            if content_hash not in self.seen_hashes:
                self.seen_hashes.add(content_hash)
                unique.append(artifact)
        return unique

    def normalize_format(self, artifact: Dict) -> Dict:
        content_type = artifact.get('type', 'text')
        if content_type == 'html':
            artifact['content'] = self._html_to_markdown(artifact['content'])
        elif content_type == 'pdf':
            artifact['content'] = self._pdf_to_text(artifact['content'])
        artifact['normalized_type'] = 'markdown'
        return artifact

    def extract_metadata(self, artifact: Dict) -> Dict:
        return {
            'author': artifact.get('author', 'unknown'),
            'date': artifact.get('created_at', datetime.now()),
            'tags': self._extract_tags(artifact.get('content', '')),
            'project': artifact.get('project'),
            'source': artifact.get('source')
        }

    def track_version(self, artifact_id: str, content: str) -> Dict:
        version_hash = self._compute_hash(content)
        return {
            'artifact_id': artifact_id,
            'version': version_hash,
            'timestamp': datetime.now()
        }

    def compute_diff(self, old_content: str, new_content: str) -> Dict:
        old_lines = old_content.split('\n')
        new_lines = new_content.split('\n')
        added = [line for line in new_lines if line not in old_lines]
        removed = [line for line in old_lines if line not in new_lines]
        return {'added': added, 'removed': removed}

    async def ingest_incremental(self, source: str, last_sync: datetime) -> List[Dict]:
        # Fetch only new/updated items
        return await self._fetch_from_source(source, since=last_sync)

    def optimize_batch(self, artifacts: List[Dict], batch_size: int = 100) -> List[List[Dict]]:
        return [artifacts[i:i+batch_size] for i in range(0, len(artifacts), batch_size)]

    def _compute_hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()

    async def _fetch_from_source(self, source: str, since: datetime = None) -> List[Dict]:
        # Placeholder for source fetching
        return []

    def _html_to_markdown(self, html: str) -> str:
        # Simplified conversion
        return html.replace('<p>', '').replace('</p>', '\n')

    def _pdf_to_text(self, pdf_content: bytes) -> str:
        # Placeholder for PDF extraction
        return "Extracted text from PDF"

    def _extract_tags(self, content: str) -> List[str]:
        # Simple tag extraction
        words = content.split()
        return [w for w in words if w.startswith('#')]
