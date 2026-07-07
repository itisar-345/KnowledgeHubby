"""
LLM client — local-first.

Default: Ollama (http://localhost:11434) with llama3.1:8b
Upgrade:  set LLM_PROVIDER=openai + OPENAI_API_KEY to use GPT models

Both providers expose the same async interface used by llm_extraction.py
and graphrag.py.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

LLM_PROVIDER   = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_BASE    = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _use_openai() -> bool:
    return LLM_PROVIDER == "openai" and bool(OPENAI_API_KEY)


async def chat(
    messages: List[Dict[str, str]],
    temperature: float = 0,
    max_tokens: int = 1000,
    json_mode: bool = False,
) -> Optional[str]:
    """
    Send a chat request and return the assistant message content.
    Returns None on failure so callers can apply their own fallback.
    """
    if _use_openai():
        return await _openai_chat(messages, temperature, max_tokens, json_mode)
    return await _ollama_chat(messages, temperature, max_tokens, json_mode)


async def _ollama_chat(
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> Optional[str]:
    try:
        import httpx
        payload: Dict[str, Any] = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
    except Exception as exc:
        logger.warning("Ollama chat() failed: %s", exc)
        return None


async def _openai_chat(
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> Optional[str]:
    try:
        from openai import AsyncOpenAI
        kwargs: Dict[str, Any] = dict(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        r = await AsyncOpenAI(api_key=OPENAI_API_KEY).chat.completions.create(**kwargs)
        return r.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("OpenAI chat() failed: %s", exc)
        return None
