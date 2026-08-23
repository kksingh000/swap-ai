"""Concrete LLM providers.

  OllamaProvider          FREE  - fully local (llama3.2 / qwen2.5 / gemma2)
  OpenAICompatibleProvider FREE-TIER - Groq, OpenRouter, Together, LM Studio, vLLM
  HuggingFaceProvider     FREE-TIER - HF Inference router (OpenAI-compatible)
  RuleBasedProvider       FREE  - no model at all; engine falls back to templates
"""
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm.base import LLMError, LLMProvider, Message

log = get_logger(__name__)


class OllamaProvider(LLMProvider):
    """Local models via Ollama. Zero cost, zero data leaving the machine."""

    name = "ollama"

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self._client = httpx.AsyncClient(timeout=settings.LLM_TIMEOUT)

    async def chat(
        self,
        messages: List[Message],
        temperature: float = 0.6,
        max_tokens: int = 320,
        json_mode: bool = False,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        try:
            resp = await self._client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return (resp.json().get("message") or {}).get("content", "").strip()
        except Exception as exc:  # noqa: BLE001 - surfaced as LLMError to the engine
            raise LLMError(f"ollama chat failed: {exc}") from exc

    async def health(self) -> Dict[str, Any]:
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags", timeout=3)
            models = [m["name"] for m in resp.json().get("models", [])]
            return {
                "provider": self.name,
                "available": True,
                "model": self.model,
                "installed_models": models,
                "model_installed": any(m.split(":")[0] == self.model.split(":")[0] for m in models),
            }
        except Exception as exc:  # noqa: BLE001
            return {"provider": self.name, "available": False, "error": str(exc)}

    async def aclose(self) -> None:
        await self._client.aclose()


class OpenAICompatibleProvider(LLMProvider):
    """Anything speaking the OpenAI chat-completions API.

    Groq's free tier is the sweet spot here: very fast, generous limits, and it
    handles Hinglish well.
    """

    name = "openai_compatible"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        label: Optional[str] = None,
    ) -> None:
        self.base_url = (base_url or settings.OPENAI_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        if label:
            self.name = label
        self._client = httpx.AsyncClient(
            timeout=settings.LLM_TIMEOUT,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )

    async def chat(
        self,
        messages: List[Message],
        temperature: float = 0.6,
        max_tokens: int = 320,
        json_mode: bool = False,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = await self._client.post(f"{self.base_url}/chat/completions", json=payload)
            if resp.status_code >= 400:
                raise LLMError(f"{resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            return (data["choices"][0]["message"]["content"] or "").strip()
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"{self.name} chat failed: {exc}") from exc

    async def health(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "available": bool(self.api_key),
            "model": self.model,
            "base_url": self.base_url,
        }

    async def aclose(self) -> None:
        await self._client.aclose()


class HuggingFaceProvider(OpenAICompatibleProvider):
    """HF Inference router, which is OpenAI-compatible - so we just reconfigure."""

    name = "huggingface"

    def __init__(self) -> None:
        super().__init__(
            base_url=settings.HF_BASE_URL,
            api_key=settings.HF_API_TOKEN,
            model=settings.HF_MODEL,
            label="huggingface",
        )


class RuleBasedProvider(LLMProvider):
    """The zero-dependency fallback.

    It is deliberately *not* a fake LLM: `available` is False, which tells the
    conversation engine to use its deterministic extractor and template response
    generator instead. That is what makes the project runnable with no model,
    no keys and no internet.
    """

    name = "rules"
    available = False

    async def chat(
        self,
        messages: List[Message],
        temperature: float = 0.6,
        max_tokens: int = 320,
        json_mode: bool = False,
    ) -> str:
        raise LLMError("No LLM configured - deterministic engine handles this turn")

    async def health(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "available": False,
            "note": "Deterministic mode: rule-based NLU + template NLG + ML classifier",
        }
