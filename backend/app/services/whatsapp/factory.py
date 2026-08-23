from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.services.whatsapp.base import WhatsAppProvider
from app.services.whatsapp.providers import MockWhatsAppProvider, TwilioWhatsAppProvider

log = get_logger(__name__)

_instance: Optional[WhatsAppProvider] = None


def build_provider(kind: Optional[str] = None) -> WhatsAppProvider:
    kind = (kind or settings.WHATSAPP_PROVIDER or "mock").lower()
    if kind == "twilio":
        if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
            log.warning("WHATSAPP_PROVIDER=twilio but credentials are missing; using mock")
            return MockWhatsAppProvider()
        return TwilioWhatsAppProvider()
    return MockWhatsAppProvider()


def get_whatsapp() -> WhatsAppProvider:
    global _instance
    if _instance is None:
        _instance = build_provider()
    return _instance


def set_whatsapp(provider: WhatsAppProvider) -> None:
    global _instance
    _instance = provider
