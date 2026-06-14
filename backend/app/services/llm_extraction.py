from __future__ import annotations

import json
import os
from typing import Any, Dict, List

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

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
    if not OPENAI_API_KEY:
        return _fallback(text)

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text[:12000]},  # ~3k tokens safety cap
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as exc:
        # degrade gracefully – fall back to regex extraction
        return {**_fallback(text), "llm_error": str(exc)}


def _fallback(text: str) -> Dict[str, Any]:
    """Regex fallback when no API key is set."""
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
        "llm_error": "no API key – regex fallback used",
    }
