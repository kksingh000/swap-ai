"""Speech providers.

Default is `browser`: the dashboard uses the Web Speech API, which is FREE,
needs no install, runs on-device and already supports en-IN and hi-IN. That is
why demo mode costs nothing.

Server-side options are here for when you need STT/TTS off the browser
(recorded audio, telephony without Twilio's built-in STT). They import their
heavy dependencies lazily so the app still starts when they are not installed.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class SpeechToTextProvider(ABC):
    name = "base"

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> Dict[str, Any]:
        ...


class TextToSpeechProvider(ABC):
    name = "base"

    @abstractmethod
    async def synthesize(self, text: str, language: Optional[str] = None) -> Dict[str, Any]:
        ...


class BrowserSTT(SpeechToTextProvider):
    """No-op: transcription happens in the browser and arrives as text."""

    name = "browser"

    async def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> Dict[str, Any]:
        return {
            "text": "",
            "provider": self.name,
            "note": "Browser Web Speech API performs recognition client-side; POST text instead.",
        }


class BrowserTTS(TextToSpeechProvider):
    """No-op: speechSynthesis runs in the browser, so we return the text."""

    name = "browser"

    async def synthesize(self, text: str, language: Optional[str] = None) -> Dict[str, Any]:
        return {"audio_url": None, "text": text, "provider": self.name, "client_side": True}


class FasterWhisperSTT(SpeechToTextProvider):
    """FREE local STT. `pip install faster-whisper` to enable."""

    name = "faster_whisper"

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # noqa: PLC0415

            self._model = WhisperModel(settings.WHISPER_MODEL, device="cpu", compute_type="int8")
            log.info("faster-whisper model '%s' loaded", settings.WHISPER_MODEL)
        return self._model

    async def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> Dict[str, Any]:
        import io  # noqa: PLC0415

        model = self._load()
        lang = {"hindi": "hi", "hinglish": "hi", "english": "en"}.get(language or "", None)
        segments, info = model.transcribe(io.BytesIO(audio_bytes), language=lang, beam_size=1)
        text = " ".join(segment.text for segment in segments).strip()
        return {
            "text": text,
            "provider": self.name,
            "detected_language": getattr(info, "language", None),
        }


class PiperTTS(TextToSpeechProvider):
    """FREE local neural TTS. Requires the `piper` binary + a voice model."""

    name = "piper"

    async def synthesize(self, text: str, language: Optional[str] = None) -> Dict[str, Any]:
        import asyncio  # noqa: PLC0415
        import base64  # noqa: PLC0415

        if not settings.PIPER_VOICE:
            return {"error": "PIPER_VOICE not configured", "provider": self.name}
        process = await asyncio.create_subprocess_exec(
            "piper", "--model", settings.PIPER_VOICE, "--output_file", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate(text.encode("utf-8"))
        if process.returncode != 0:
            return {"error": stderr.decode()[:200], "provider": self.name}
        return {
            "audio_base64": base64.b64encode(stdout).decode(),
            "mime": "audio/wav",
            "provider": self.name,
        }


def get_stt() -> SpeechToTextProvider:
    if settings.STT_PROVIDER == "faster_whisper":
        return FasterWhisperSTT()
    return BrowserSTT()


def get_tts() -> TextToSpeechProvider:
    if settings.TTS_PROVIDER == "piper":
        return PiperTTS()
    return BrowserTTS()
