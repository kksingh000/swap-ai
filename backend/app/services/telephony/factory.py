from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.services.telephony.base import TelephonyProvider
from app.services.telephony.providers import MockTelephonyProvider, TwilioProvider

log = get_logger(__name__)

_instance: Optional[TelephonyProvider] = None


def build_provider(kind: Optional[str] = None) -> TelephonyProvider:
    kind = (kind or settings.TELEPHONY_PROVIDER or "mock").lower()
    if kind == "twilio":
        provider = TwilioProvider()
        if not provider.configured:
            log.warning("TELEPHONY_PROVIDER=twilio but credentials are missing; using mock")
            return MockTelephonyProvider()
        return provider
    return MockTelephonyProvider()


def get_telephony() -> TelephonyProvider:
    global _instance
    if _instance is None:
        _instance = build_provider()
    return _instance


def set_telephony(provider: TelephonyProvider) -> None:
    global _instance
    _instance = provider
