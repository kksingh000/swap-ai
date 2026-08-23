"""Tiny retrieval layer over the store FAQ.

Deliberately dependency-free: a bag-of-words + tag scorer is enough for a ~10
entry knowledge base and it costs nothing at runtime. The interface matches
what a vector store would expose, so swapping in Chroma later is a one-file job.
"""
from typing import Any, Dict, List, Optional

from app.utils.text import tokens

STOP = {"the", "a", "an", "is", "are", "do", "you", "i", "my", "me", "to", "of", "and", "it"}


class FAQRetriever:
    def __init__(self, entries: List[Dict[str, Any]]) -> None:
        self.entries = entries or []

    def search(self, query: str, top_k: int = 2, min_score: float = 0.15) -> List[Dict[str, Any]]:
        q_tokens = {t for t in tokens(query) if t not in STOP and len(t) > 2}
        low = (query or "").lower()
        if not q_tokens:
            return []

        scored: List[tuple] = []
        for entry in self.entries:
            tags = [t.lower() for t in entry.get("tags", [])]
            tag_hits = sum(1 for t in tags if t in low)
            q_entry_tokens = {t for t in tokens(entry.get("q", "")) if t not in STOP and len(t) > 2}
            overlap = len(q_tokens & q_entry_tokens)
            denom = max(1, len(q_entry_tokens))
            score = (tag_hits * 0.45) + (overlap / denom) * 0.55
            if score >= min_score:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {**entry, "relevance": round(score, 3)} for score, entry in scored[:top_k]
        ]

    def best_answer(self, query: str, language: str = "english") -> Optional[str]:
        """Answer in the customer's language when we have a localised version."""
        hits = self.search(query, top_k=1, min_score=0.28)
        if not hits:
            return None
        entry = hits[0]
        if language in ("hinglish", "hindi") and entry.get("a_hinglish"):
            return entry["a_hinglish"]
        return entry.get("a")

    def as_context(self, query: str, top_k: int = 2) -> str:
        hits = self.search(query, top_k=top_k)
        if not hits:
            return ""
        return "\n".join(f"Q: {h['q']}\nA: {h['a']}" for h in hits)
