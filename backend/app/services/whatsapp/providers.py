"""WhatsApp providers.

MockWhatsAppProvider   FREE      - renders into the dashboard's WhatsApp simulator
TwilioWhatsAppProvider FREE-TIER - Twilio WhatsApp sandbox (no cost, needs opt-in)
"""
import asyncio
import uuid
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.twilio_auth import twilio_auth, twilio_configured, twilio_credential_style
from app.services.whatsapp.base import WhatsAppProvider

log = get_logger(__name__)


class MockWhatsAppProvider(WhatsAppProvider):
    """Pretends to send, with a realistic latency so the UI shows 'sending'."""

    name = "mock"
    is_live = False

    async def send_message(self, to_number: str, body: str) -> Dict[str, Any]:
        await asyncio.sleep(0.4)
        message_id = f"MOCK{uuid.uuid4().hex[:16].upper()}"
        log.info("[MOCK WhatsApp] -> %s: %s", to_number, body[:80])
        return {"status": "sent", "provider": self.name, "message_id": message_id, "simulated": True}

    async def send_media(
        self, to_number: str, media_url: str, caption: Optional[str] = None
    ) -> Dict[str, Any]:
        await asyncio.sleep(0.4)
        message_id = f"MOCK{uuid.uuid4().hex[:16].upper()}"
        log.info("[MOCK WhatsApp media] -> %s: %s", to_number, media_url)
        return {
            "status": "sent",
            "provider": self.name,
            "message_id": message_id,
            "media_url": media_url,
            "simulated": True,
        }


class TwilioWhatsAppProvider(WhatsAppProvider):
    name = "twilio"
    is_live = True

    def __init__(self) -> None:
        self.sid = settings.TWILIO_ACCOUNT_SID
        self.token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_WHATSAPP_FROM
        self.base = f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json"

    @staticmethod
    def _wa(number: str) -> str:
        number = number.strip()
        return number if number.startswith("whatsapp:") else f"whatsapp:{number}"

    async def _post(self, data: Dict[str, str]) -> Dict[str, Any]:
        if not twilio_configured():
            return {"status": "failed", "provider": self.name, "error": "Twilio credentials missing"}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(self.base, data=data, auth=twilio_auth())
            payload = resp.json()
            if resp.status_code >= 400:
                return {
                    "status": "failed",
                    "provider": self.name,
                    "error": payload.get("message", resp.text[:200]),
                }
            return {
                "status": payload.get("status", "queued"),
                "provider": self.name,
                "message_id": payload.get("sid"),
            }
        except Exception as exc:  # noqa: BLE001
            log.error("Twilio WhatsApp send failed: %s", exc)
            return {"status": "failed", "provider": self.name, "error": str(exc)[:200]}

    async def send_message(self, to_number: str, body: str) -> Dict[str, Any]:
        return await self._post(
            {"From": self._wa(self.from_number), "To": self._wa(to_number), "Body": body}
        )

    async def send_media(
        self, to_number: str, media_url: str, caption: Optional[str] = None
    ) -> Dict[str, Any]:
        data = {
            "From": self._wa(self.from_number),
            "To": self._wa(to_number),
            "MediaUrl": media_url,
        }
        if caption:
            data["Body"] = caption
        return await self._post(data)

    async def health(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "live": True,
            "configured": twilio_configured(),
            "credential_style": twilio_credential_style(),
            "from": self.from_number,
        }
