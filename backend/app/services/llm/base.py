"""LLM provider abstraction.

Every provider takes OpenAI-style messages and returns a plain string, so the
conversation engine never knows or cares which one is plugged in.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

log = get_logger(__name__)

Message = Dict[str, str]


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str = "base"
    #: False for the deterministic fallback, which has no generative model.
    available: bool = True

    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        temperature: float = 0.6,
        max_tokens: int = 320,
        json_mode: bool = False,
    ) -> str:
        ...

    async def complete_json(
        self, messages: List[Message], max_tokens: int = 400
    ) -> Optional[Dict[str, Any]]:
        """Ask for JSON, repair it, retry once with a stricter nudge."""
        from app.utils.json_repair import extract_json

        raw = await self.chat(messages, temperature=0.1, max_tokens=max_tokens, json_mode=True)
        parsed = extract_json(raw)
        if parsed is not None:
            return parsed

        log.warning("%s returned unparseable JSON, retrying once", self.name)
        retry = messages + [
            {"role": "assistant", "content": raw[:500]},
            {
                "role": "user",
                "content": "That was not valid JSON. Reply with ONLY the JSON object, no prose, no markdown fences.",
            },
        ]
        raw = await self.chat(retry, temperature=0.0, max_tokens=max_tokens, json_mode=True)
        return extract_json(raw)

    async def health(self) -> Dict[str, Any]:
        return {"provider": self.name, "available": self.available}

    async def aclose(self) -> None:
        return None
