"""Chooses an LLM provider from config, with an `auto` mode that degrades safely.

auto order:  Groq/OpenAI-compatible key -> HF token -> local Ollama -> rules
So the app always boots, whatever the machine has.
"""
import socket
from typing import Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm.base import LLMProvider
from app.services.llm.providers import (
    HuggingFaceProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    RuleBasedProvider,
)

log = get_logger(__name__)

_instance: Optional[LLMProvider] = None


def _port_open(url: str, timeout: float = 0.6) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def build_provider(kind: Optional[str] = None) -> LLMProvider:
    kind = (kind or settings.LLM_PROVIDER or "auto").lower()

    if kind == "auto":
        if settings.OPENAI_API_KEY:
            kind = "openai_compatible"
        elif settings.HF_API_TOKEN:
            kind = "huggingface"
        elif _port_open(settings.OLLAMA_BASE_URL):
            kind = "ollama"
        else:
            kind = "rules"
        log.info("LLM_PROVIDER=auto resolved to '%s'", kind)

    if kind == "ollama":
        return OllamaProvider()
    if kind == "huggingface":
        return HuggingFaceProvider()
    if kind in ("openai_compatible", "openai", "groq"):
        return OpenAICompatibleProvider()
    if kind != "rules":
        log.warning("Unknown LLM_PROVIDER '%s', falling back to rules", kind)
    return RuleBasedProvider()


def get_llm() -> LLMProvider:
    global _instance
    if _instance is None:
        _instance = build_provider()
    return _instance


def set_llm(provider: LLMProvider) -> None:
    """Used by the runtime provider switcher and by tests."""
    global _instance
    _instance = provider


async def reset_llm() -> None:
    global _instance
    if _instance is not None:
        await _instance.aclose()
    _instance = None
