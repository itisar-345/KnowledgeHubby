from __future__ import annotations

import re
from typing import List, Tuple


def _keywords(text: str) -> set[str]:
    """Extract meaningful lowercase words (4+ chars) from text."""
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    stopwords = {"this", "that", "with", "from", "have", "will", "been", "were",
                 "they", "their", "would", "could", "should", "which", "what",
                 "when", "where", "there", "about", "also", "into", "some"}
    return set(w for w in words if w not in stopwords)


def score_similarity(text_a: str, text_b: str) -> float:
    """Jaccard similarity between keyword sets of two texts."""
    kw_a = _keywords(text_a)
    kw_b = _keywords(text_b)
    if not kw_a or not kw_b:
        return 0.0
    intersection = kw_a & kw_b
    union = kw_a | kw_b
    return round(len(intersection) / len(union), 3)


def find_cross_links(
    items: List[dict],
    threshold: float = 0.12,
) -> List[Tuple[str, str, float]]:
    """
    Compare every pair of knowledge items from *different* artifacts.
    Returns (item_id_a, item_id_b, score) tuples above the threshold.
    """
    links: List[Tuple[str, str, float]] = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if a.get("artifact_id") == b.get("artifact_id"):
                continue  # only cross-artifact links
            score = score_similarity(a.get("title", ""), b.get("title", ""))
            if score >= threshold:
                links.append((a["id"], b["id"], score))
    return links
