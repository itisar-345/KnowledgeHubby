from __future__ import annotations

import json
from typing import Any, Dict

from app.services.item_schema import normalize_item_details
from app.services import llm_client

_SYSTEM_PROMPT = """You are a meeting analyst. Extract structured knowledge from the transcript.
Return ONLY valid JSON with this exact shape:
{
  "decisions": [{"what": "...", "why": "...", "who": "..."}],
  "action_items": [{"task": "...", "owner": "...", "due": "..."}],
  "risks": [{"risk": "...", "severity": "low|medium|high"}],
  "summary": "..."
}
Rules:
- decisions: things that were agreed/decided
- action_items: concrete tasks assigned to someone
- risks: concerns or blockers mentioned
- summary: 2-3 sentence summary of the meeting
- Use "" for unknown fields, never null
- Return ONLY the JSON object, no markdown fences"""


async def extract_from_transcript(text: str) -> Dict[str, Any]:
    content = await llm_client.chat(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text[:12000]},
        ],
        temperature=0,
        json_mode=True,
    )
    if content:
        try:
            return _normalize_llm_result(json.loads(content))
        except Exception as exc:
            return {**_normalize_llm_result(_fallback(text)), "llm_error": str(exc)}
    return _fallback(text)


def _fallback(text: str) -> Dict[str, Any]:
    """Regex fallback when no LLM is reachable."""
    import re
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 10]
    decisions = [{"what": s, "why": "", "who": ""} for s in sentences
                 if any(k in s.lower() for k in ("decided", "agreed", "approved", "we will"))]
    actions = [{"task": s, "owner": "", "due": ""} for s in sentences
               if any(k in s.lower() for k in ("action:", "todo:", "will ", "should ", "needs to", "follow up"))]
    return {
        "decisions": decisions[:10],
        "action_items": actions[:10],
        "risks": [],
        "summary": sentences[0] if sentences else "",
        "llm_error": "no LLM reachable – regex fallback used",
    }


def _normalize_llm_result(result: Dict[str, Any]) -> Dict[str, Any]:
    result["decisions"] = [
        normalize_item_details(d, "decision", "llm") for d in result.get("decisions") or []
    ]
    result["action_items"] = [
        normalize_item_details(a, "action-item", "llm") for a in result.get("action_items") or []
    ]
    result["risks"] = [
        normalize_item_details(r, "risk", "llm") for r in result.get("risks") or []
    ]
    return result


async def _summarise_text(text: str) -> str:
    """Return a 2-3 sentence condensed summary for the summary index."""
    content = await llm_client.chat(
        messages=[
            {"role": "system", "content": "Summarise the following document in 2-3 sentences."},
            {"role": "user", "content": text[:8000]},
        ],
        temperature=0,
        max_tokens=120,
    )
    return content if content else text.strip()[:300]
