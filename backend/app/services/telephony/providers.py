"""Telephony providers.

MockTelephonyProvider  FREE  - no phone network at all; the browser demo is the "line"
TwilioProvider         PAID  - real outbound PSTN calls (trial credit covers testing)

The Twilio integration deliberately uses <Gather input="speech"> rather than
Media Streams: Twilio does the STT for us, there is no websocket audio pipeline
to host, and it works from a laptop behind ngrok. Swap in Media Streams later
by implementing this same interface.
"""
import uuid
from typing import Any, Dict, Optional
from xml.sax.saxutils import escape

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.telephony.base import TelephonyProvider
from app.services.twilio_auth import twilio_auth, twilio_configured, twilio_credential_style

log = get_logger(__name__)


class MockTelephonyProvider(TelephonyProvider):
    name = "mock"
    is_live = False

    async def make_call(
        self,
        customer_name: str,
        phone_number: str,
        campaign_type: str = "acquisition",
        call_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        sid = f"CAMOCK{uuid.uuid4().hex[:24]}"
        log.info("[MOCK CALL] dialling %s (%s) for campaign=%s", customer_name, phone_number, campaign_type)
        return {
            "status": "initiated",
            "call_sid": sid,
            "provider": self.name,
            "simulated": True,
            "note": "No real phone call was placed. Use Demo Mode in the dashboard to talk to the agent.",
        }

    async def end_call(self, call_sid: str) -> Dict[str, Any]:
        return {"status": "completed", "call_sid": call_sid, "provider": self.name, "simulated": True}


class TwilioProvider(TelephonyProvider):
    name = "twilio"
    is_live = True

    def __init__(self) -> None:
        self.sid = settings.TWILIO_ACCOUNT_SID
        self.token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.base = f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}"

    @property
    def configured(self) -> bool:
        return twilio_configured() and bool(self.from_number)

    async def make_call(
        self,
        customer_name: str,
        phone_number: str,
        campaign_type: str = "acquisition",
        call_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not self.configured:
            return {"status": "failed", "provider": self.name, "error": "Twilio credentials missing"}

        voice_url = f"{settings.PUBLIC_BASE_URL}{settings.API_PREFIX}/telephony/twilio/voice"
        if call_id:
            voice_url += f"?call_id={call_id}"

        data = {
            "To": phone_number,
            "From": self.from_number,
            "Url": voice_url,
            "Method": "POST",
            "StatusCallback": f"{settings.PUBLIC_BASE_URL}{settings.API_PREFIX}/telephony/twilio/status",
            "StatusCallbackEvent": ["initiated", "answered", "completed"],
            "MachineDetection": "Enable",
            "Timeout": "25",
        }

        try:
            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.post(
                    f"{self.base}/Calls.json", data=data, auth=twilio_auth()
                )
            payload = resp.json()
            if resp.status_code >= 400:
                return {
                    "status": "failed",
                    "provider": self.name,
                    "error": payload.get("message", resp.text[:200]),
                }
            return {
                "status": payload.get("status", "queued"),
                "call_sid": payload.get("sid"),
                "provider": self.name,
                "to": phone_number,
            }
        except Exception as exc:  # noqa: BLE001
            log.error("Twilio call failed: %s", exc)
            return {"status": "failed", "provider": self.name, "error": str(exc)[:200]}

    async def end_call(self, call_sid: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base}/Calls/{call_sid}.json",
                    data={"Status": "completed"},
                    auth=twilio_auth(),
                )
            return {"status": "completed" if resp.status_code < 400 else "failed", "call_sid": call_sid}
        except Exception as exc:  # noqa: BLE001
            return {"status": "failed", "error": str(exc)[:200]}

    async def health(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "live": True,
            "configured": self.configured,
            "credential_style": twilio_credential_style(),
            "from": self.from_number,
            "webhook_base": settings.PUBLIC_BASE_URL,
        }


# ---------------------------------------------------------------------------
# TwiML helpers
# ---------------------------------------------------------------------------

# (speech-recognition locale, TTS voice). Twilio recognises all of these
# locales; Google voices cover the languages Amazon Polly does not.
LANG_TO_TWILIO = {
    "english": ("en-IN", settings.TWILIO_VOICE),
    # en-IN handles code-switched Hinglish far better than hi-IN does.
    "hinglish": ("en-IN", settings.TWILIO_VOICE),
    "hindi": ("hi-IN", "Polly.Aditi"),
    "marathi": ("mr-IN", "Google.mr-IN-Standard-A"),
    "bengali": ("bn-IN", "Google.bn-IN-Standard-A"),
    "telugu": ("te-IN", "Google.te-IN-Standard-A"),
    "kannada": ("kn-IN", "Google.kn-IN-Standard-A"),
    "tamil": ("ta-IN", "Google.ta-IN-Standard-A"),
    "gujarati": ("gu-IN", "Google.gu-IN-Standard-A"),
    "punjabi": ("pa-IN", "Google.pa-IN-Standard-A"),
    "malayalam": ("ml-IN", "Google.ml-IN-Standard-A"),
    "odia": ("en-IN", settings.TWILIO_VOICE),  # no Twilio voice for Odia yet
}


def twiml_say_and_gather(
    text: str, action_url: str, language: str = "english", timeout: int = 5
) -> str:
    """Speak a line, then listen for the customer's reply via Twilio's own STT."""
    stt_lang, voice = LANG_TO_TWILIO.get(language, LANG_TO_TWILIO["english"])
    # action_url usually already carries ?call_id=N, so pick the right separator.
    separator = "&" if "?" in action_url else "?"
    no_input_url = f"{action_url}{separator}no_input=1"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="{escape(action_url)}" method="POST" language="{stt_lang}"
          speechTimeout="auto" timeout="{timeout}" enhanced="true" speechModel="phone_call">
    <Say voice="{voice}" language="{stt_lang}">{escape(text)}</Say>
  </Gather>
  <Redirect method="POST">{escape(no_input_url)}</Redirect>
</Response>"""


def twiml_say_and_hangup(text: str, language: str = "english") -> str:
    stt_lang, voice = LANG_TO_TWILIO.get(language, LANG_TO_TWILIO["english"])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="{voice}" language="{stt_lang}">{escape(text)}</Say>
  <Hangup/>
</Response>"""
