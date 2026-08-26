"""Twilio voice webhooks.

Flow per turn:
    Twilio POSTs SpeechResult -> engine.handle_turn -> TwiML <Say> + <Gather>
The customer hears the reply and the next <Gather> captures their answer, so
one HTTP round-trip per conversational turn. No media streaming required.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.events import bus
from app.core.logging import get_logger
from app.db.session import get_db
from app.models import Call, Customer
from app.services import customer_service
from app.services.conversation.engine import ConversationEngine
from app.services.telephony.providers import twiml_say_and_gather, twiml_say_and_hangup

log = get_logger(__name__)
router = APIRouter(prefix="/telephony", tags=["telephony"])

XML = "application/xml"


def _action_url(call_id: int) -> str:
    """Absolute https webhook URL for the next turn.

    Built from PUBLIC_BASE_URL rather than request.url: behind a TLS-
    terminating proxy the request scheme reads as http, and Twilio POSTing to
    http would hit a 301 that silently breaks the conversation.
    """
    return (
        f"{settings.PUBLIC_BASE_URL.rstrip('/')}"
        f"{settings.API_PREFIX}/telephony/twilio/voice?call_id={call_id}"
    )


def _find_call(db: Session, call_id: Optional[int], call_sid: Optional[str]) -> Optional[Call]:
    if call_id:
        call = db.get(Call, call_id)
        if call:
            return call
    if call_sid:
        return db.query(Call).filter(Call.provider_call_sid == call_sid).first()
    return None


@router.post("/twilio/voice")
async def twilio_voice(
    request: Request,
    call_id: Optional[int] = Query(default=None),
    no_input: Optional[int] = Query(default=None),
    CallSid: str = Form(default=""),
    From: str = Form(default=""),
    To: str = Form(default=""),
    SpeechResult: str = Form(default=""),
    Confidence: float = Form(default=0.0),
    AnsweredBy: str = Form(default=""),
    db: Session = Depends(get_db),
) -> Response:
    """Single webhook that handles both the greeting and every subsequent turn."""
    call = _find_call(db, call_id, CallSid)

    # Voicemail: leave nothing, hang up, keep the lead untouched.
    if AnsweredBy.startswith("machine"):
        if call:
            call.outcome = "voicemail"
            call.status = "completed"
            db.commit()
        return Response(content=twiml_say_and_hangup("Sorry to miss you. We'll try again later."), media_type=XML)

    if call is None:
        # Inbound call, or an outbound call we lost track of: create one.
        customer = customer_service.get_or_create(db, From or To or "+910000000000")
        engine = ConversationEngine(db)
        call, opening = await engine.start_call(
            customer, mode="phone", provider="twilio", provider_call_sid=CallSid
        )
        return Response(
            content=twiml_say_and_gather(opening, _action_url(call.id), customer.preferred_language),
            media_type=XML,
        )

    if call.provider_call_sid is None and CallSid:
        call.provider_call_sid = CallSid
        db.commit()

    customer = db.get(Customer, call.customer_id)
    engine = ConversationEngine(db)

    # First webhook of an outbound call: speak the opening we already generated.
    if not SpeechResult and call.turn_count == 0 and not no_input:
        last_agent = [m for m in call.messages if m.role == "agent"]
        opening = last_agent[-1].content if last_agent else engine.responder.opening(customer.name)
        return Response(
            content=twiml_say_and_gather(opening, _action_url(call.id), customer.preferred_language),
            media_type=XML,
        )

    if not SpeechResult:
        # Silence: nudge once, then close politely.
        if call.turn_count >= 2 or no_input:
            reply = "I'll let you go for now. Thanks for your time, have a great day!"
            await engine.end_call(call, outcome="no_response")
            return Response(content=twiml_say_and_hangup(reply, customer.preferred_language), media_type=XML)
        nudge = "Sorry, I didn't catch that. Are you there?"
        return Response(
            content=twiml_say_and_gather(nudge, _action_url(call.id), customer.preferred_language),
            media_type=XML,
        )

    await bus.broadcast(
        "telephony.speech",
        {"call_id": call.id, "text": SpeechResult, "confidence": Confidence},
        call_id=call.id,
    )

    result = await engine.handle_turn(call, SpeechResult)
    language = result["memory"].get("language", "english")

    if result["should_end"]:
        return Response(content=twiml_say_and_hangup(result["reply"], language), media_type=XML)
    return Response(
        content=twiml_say_and_gather(result["reply"], _action_url(call.id), language),
        media_type=XML,
    )


@router.post("/twilio/status")
async def twilio_status(
    CallSid: str = Form(default=""),
    CallStatus: str = Form(default=""),
    CallDuration: int = Form(default=0),
    db: Session = Depends(get_db),
) -> dict:
    call = db.query(Call).filter(Call.provider_call_sid == CallSid).first()
    if not call:
        return {"ok": True, "note": "unknown call sid"}

    if CallStatus in ("completed", "failed", "busy", "no-answer", "canceled"):
        call.duration_seconds = CallDuration or call.duration_seconds
        if call.status != "completed":
            engine = ConversationEngine(db)
            await engine.end_call(call, outcome=CallStatus)
    else:
        call.status = "active" if CallStatus == "in-progress" else call.status
        db.commit()

    await bus.broadcast(
        "call.status", {"call_id": call.id, "status": CallStatus, "duration": CallDuration}, call_id=call.id
    )
    return {"ok": True}
