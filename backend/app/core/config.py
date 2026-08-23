"""Central configuration. Everything is env-driven; nothing secret is hardcoded."""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # ---------- App ----------
    APP_NAME: str = "SwapCircle AI Voice Sales Agent"
    ENV: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api"
    PUBLIC_BASE_URL: str = "http://localhost:8000"  # ngrok URL when using Twilio
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # ---------- Database ----------
    # SQLite locally (FREE, zero setup) / Postgres in production.
    DATABASE_URL: str = "sqlite:///./swap_agent.db"

    # ---------- LLM ----------
    # auto | rules | ollama | huggingface | openai_compatible
    LLM_PROVIDER: str = "auto"
    LLM_TIMEOUT: int = 45

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b-instruct"

    HF_API_TOKEN: str = ""
    HF_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    HF_BASE_URL: str = "https://router.huggingface.co/v1"

    # Works with Groq / Together / OpenRouter / LM Studio / vLLM / OpenAI
    OPENAI_BASE_URL: str = "https://api.groq.com/openai/v1"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "llama-3.3-70b-versatile"

    # ---------- Telephony ----------
    TELEPHONY_PROVIDER: str = "mock"  # mock | twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_VOICE: str = "Polly.Aditi"  # Indian-English neural-ish voice
    TWILIO_STT_LANGUAGE: str = "en-IN"

    # ---------- WhatsApp ----------
    WHATSAPP_PROVIDER: str = "mock"  # mock | twilio
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"  # Twilio sandbox number
    CATALOG_URL: str = "https://swapcircle.example/catalog"

    # ---------- Speech (server-side, optional) ----------
    STT_PROVIDER: str = "browser"  # browser | faster_whisper
    TTS_PROVIDER: str = "browser"  # browser | piper
    WHISPER_MODEL: str = "base"
    PIPER_VOICE: str = ""

    # ---------- Classifier ----------
    CLASSIFIER_MODEL_PATH: str = "../training/artifacts/lead_classifier.joblib"
    ENSEMBLE_WEIGHT_RULES: float = 0.5
    ENSEMBLE_WEIGHT_ML: float = 0.3
    ENSEMBLE_WEIGHT_LLM: float = 0.2

    # ---------- Scheduling ----------
    TIMEZONE: str = "Asia/Kolkata"
    SCHEDULER_ENABLED: bool = True

    # ---------- Store profile defaults ----------
    STORE_NAME: str = "SwapCircle"
    STORE_LOCATION: str = "Delhi NCR"
    AGENT_NAME: str = "Ananya"

    @property
    def cors_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
