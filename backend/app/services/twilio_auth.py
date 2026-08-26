"""Resolves Twilio HTTP basic-auth credentials.

Twilio accepts two credential styles on the REST API:

    (AccountSid, AuthToken)        - the account's master credentials
    (ApiKeySid, ApiKeySecret)      - a scoped, revocable API key (SK...)

API keys are preferred: they can be revoked individually without rotating the
account-wide auth token. Either way the Account SID still identifies the
account in the request path, so it is always required.
"""
from typing import Optional, Tuple

from app.core.config import settings


def twilio_auth() -> Optional[Tuple[str, str]]:
    """Return an (username, password) pair for httpx basic auth, or None."""
    if settings.TWILIO_API_KEY_SID and settings.TWILIO_API_KEY_SECRET:
        return (settings.TWILIO_API_KEY_SID, settings.TWILIO_API_KEY_SECRET)
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        return (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    return None


def twilio_credential_style() -> str:
    if settings.TWILIO_API_KEY_SID and settings.TWILIO_API_KEY_SECRET:
        return "api_key"
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        return "auth_token"
    return "missing"


def twilio_configured() -> bool:
    """Account SID is required for the URL path, plus one valid credential pair."""
    return bool(settings.TWILIO_ACCOUNT_SID) and twilio_auth() is not None
