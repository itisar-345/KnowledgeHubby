from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class JsonKnowledgeStore:
    def __init__(self, path: str = "data/knowledge_store.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(self._empty())

    def all(self) -> Dict[str, List[Dict[str, Any]]]:
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def replace(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        self._write(data)

    def append(self, collection: str, item: Dict[str, Any]) -> Dict[str, Any]:
        data = self.all()
        data.setdefault(collection, []).append(item)
        self._write(data)
        return item

    def _write(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, default=str)

    @staticmethod
    def _empty() -> Dict[str, List[Dict[str, Any]]]:
        return {
            "artifacts": [],
            "knowledge_items": [],
            "relationships": [],
            "playbooks": [],
        }
