"""WhatsApp send + history. Uses the configured provider (mock by default)."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.events import bus
from app.db.session import get_db
from app.models import Callback, Customer, Lead, WhatsAppMessage
from app.schemas.api import WhatsAppSendRequest
from app.schemas.nlu import CustomerMemory
from app.services import config_service, customer_service
from app.services.whatsapp.composer import compose
from app.services.whatsapp.factory import get_whatsapp
from app.utils.timeutil import human_ist

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.post("/send")
async def send_whatsapp(payload: WhatsAppSendRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    lead: Optional[Lead] = db.get(Lead, payload.lead_id) if payload.lead_id else None
    customer: Optional[Customer] = None

    if lead:
        customer = db.get(Customer, lead.customer_id)
    elif payload.phone_number:
        customer = customer_service.get_or_create(db, payload.phone_number)
        lead = db.query(Lead).filter(Lead.customer_id == customer.id).order_by(Lead.id.desc()).first()

    if not customer:
        raise HTTPException(status_code=400, detail="Provide either lead_id or phone_number")
    if customer.do_not_call:
        raise HTTPException(status_code=403, detail="Customer has opted out of contact")

    memory = CustomerMemory(**(lead.memory or {})) if lead else CustomerMemory(
        customer_name=customer.name, phone_number=customer.phone_number
    )
    profile = config_service.get_profile(db)

    if payload.body and not payload.use_template:
        body, kind, media = payload.body, "custom", profile.get("catalog_url")
    else:
        callback = (
            db.query(Callback)
            .filter(Callback.customer_id == customer.id, Callback.status == "scheduled")
            .order_by(Callback.id.desc())
            .first()
        )
        composed = compose(
            memory,
            lead.status if lead else "WARM",
            profile,
            callback_human_time=human_ist(callback.scheduled_time) if callback else None,
        )
        body, kind, media = composed["body"], composed["template_kind"], composed["media_url"]

    provider = get_whatsapp()
    message = WhatsAppMessage(
        customer_id=customer.id,
        call_id=payload.call_id,
        to_number=customer.phone_number,
        body=body,
        media_url=media,
        template_kind=kind,
        provider=provider.name,
        status="queued",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    result = await provider.send_message(customer.phone_number, body)
    message.status = result.get("status", "unknown")
    message.provider_message_id = result.get("message_id")
    message.error = result.get("error")
    db.commit()

    await bus.broadcast(
        "whatsapp.sent",
        {
            "message_id": message.id,
            "to": message.to_number,
            "body": message.body,
            "status": message.status,
            "provider": message.provider,
            "template_kind": message.template_kind,
            "simulated": bool(result.get("simulated")),
        },
        call_id=payload.call_id,
    )

    return {
        "id": message.id,
        "to": message.to_number,
        "body": message.body,
        "template_kind": message.template_kind,
        "status": message.status,
        "provider": message.provider,
        "result": result,
    }


# Twilio's WhatsApp failure codes, translated into what to actually do.
WHATSAPP_ERROR_HINTS = {
    "63016": "Free-form message outside the 24-hour window. The recipient must "
             "message your WhatsApp sender first (for the sandbox, send the join code).",
    "63015": "The recipient has not joined the WhatsApp sandbox.",
    "63007": "The From number is not a valid WhatsApp sender for this account.",
    "63003": "The recipient is not a reachable WhatsApp user.",
    "21211": "The To number is not a valid phone number.",
    "63024": "Invalid message: check the body and sender configuration.",
}


@router.post("/status-callback")
async def whatsapp_status_callback(
    MessageSid: str = Form(default=""),
    MessageStatus: str = Form(default=""),
    ErrorCode: str = Form(default=""),
    ErrorMessage: str = Form(default=""),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Twilio reports the real outcome here: delivered, undelivered or failed.

    The create-message response only ever says 'queued', so without this the
    dashboard could only report that Twilio accepted the request - not that
    anything actually arrived.
    """
    message = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.provider_message_id == MessageSid)
        .first()
    )
    if not message:
        return {"ok": True, "note": "unknown message sid"}

    message.status = MessageStatus or message.status
    if ErrorCode:
        hint = WHATSAPP_ERROR_HINTS.get(str(ErrorCode), "")
        message.error = f"[{ErrorCode}] {ErrorMessage or ''} {hint}".strip()
    db.commit()

    await bus.broadcast(
        "whatsapp.status",
        {
            "message_id": message.id,
            "provider_message_id": MessageSid,
            "status": message.status,
            "error": message.error,
            "to": message.to_number,
        },
        call_id=message.call_id,
    )
    return {"ok": True}


@router.get("/messages")
async def list_messages(
    customer_id: Optional[int] = None,
    call_id: Optional[int] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    query = db.query(WhatsAppMessage)
    if customer_id:
        query = query.filter(WhatsAppMessage.customer_id == customer_id)
    if call_id:
        query = query.filter(WhatsAppMessage.call_id == call_id)

    messages = query.order_by(WhatsAppMessage.id.desc()).limit(limit).all()
    customers = {c.id: c for c in db.query(Customer).all()}
    return [
        {
            "id": m.id,
            "customer_id": m.customer_id,
            "customer_name": customers.get(m.customer_id).name if customers.get(m.customer_id) else None,
            "to": m.to_number,
            "body": m.body,
            "media_url": m.media_url,
            "template_kind": m.template_kind,
            "status": m.status,
            "provider": m.provider,
            "error": m.error,
            "created_at": m.created_at,
        }
        for m in messages
    ]


@router.post("/preview")
async def preview_message(payload: WhatsAppSendRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Render the personalised message without sending it - handy for demos."""
    lead = db.get(Lead, payload.lead_id) if payload.lead_id else None
    memory = CustomerMemory(**(lead.memory or {})) if lead else CustomerMemory()
    composed = compose(memory, lead.status if lead else "WARM", config_service.get_profile(db))
    return composed
