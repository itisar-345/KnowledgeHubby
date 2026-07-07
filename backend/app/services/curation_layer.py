from __future__ import annotations

from typing import Any, Dict, List


class CurationLayer:
    """
    Playbook builder. Only build_playbook is wired into the API
    (POST /knowledge/playbooks).
    """

    def build_playbook(self, title: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "id": f"playbook_{abs(hash(title)) % 10**8:08d}",
            "title": title,
            "steps": steps,
            "category": self._categorize(title),
        }

    @staticmethod
    def _categorize(title: str) -> str:
        t = title.lower()
        if any(k in t for k in ("event", "planning", "conference")):
            return "event"
        if any(k in t for k in ("lab", "protocol", "experiment")):
            return "lab"
        if any(k in t for k in ("onboarding", "training", "new hire")):
            return "onboarding"
        return "general"
