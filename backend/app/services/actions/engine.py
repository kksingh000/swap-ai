"""Mid-call action engine.

The rule that matters: **decide synchronously, execute in the background.**
The agent tells the customer "I've sent it on WhatsApp" on the same turn, while
the actual API call happens in a task. A slow WhatsApp API can never stall the
conversation.
"""
import asyncio
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.events import bus
from app.core.logging import get_logger
from app.models import Action, Call, Callback, Customer, DoNotCallEntry, Lead, WhatsAppMessage
from app.schemas.nlu import CustomerMemory, TurnExtraction
from app.services.scheduling.nlp_time import parse_callback_time
from app.services.scheduling.scheduler import cancel_callback_job, schedule_callback_job
from app.services.whatsapp.composer import compose
from app.services.whatsapp.factory import get_whatsapp
from app.utils.timeutil import as_utc, human_ist, now_utc

log = get_logger(__name__)

SEND_WHATSAPP = "send_whatsapp"
SCHEDULE_CALLBACK = "schedule_callback"
MARK_DNC = "mark_do_not_call"
END_CALL = "end_call"


def decide(
    turn: TurnExtraction,
    memory: CustomerMemory,
    classification: str,
    already_done: List[str],
) -> List[Dict[str, Any]]:
    """Pure decision function - no I/O, trivially unit-testable."""
    decisions: List[Dict[str, Any]] = []

    if turn.do_not_call:
        decisions.append({"action_type": MARK_DNC, "reason": "Customer asked not to be called again"})
        decisions.append({"action_type": END_CALL, "reason": "Do-not-call request"})
        return decisions

    wants_catalog = turn.requires_whatsapp or "request_catalog" in turn.secondary_intents
    hot_enough = classification == "HOT" and bool(
        memory.clothing_categories or memory.brands or memory.budget
    )

    if (wants_catalog or hot_enough) and SEND_WHATSAPP not in already_done:
        decisions.append(
            {
                "action_type": SEND_WHATSAPP,
                "reason": (
                    "Customer explicitly asked for the catalogue"
                    if wants_catalog
                    else "Lead turned HOT with specific requirements"
                ),
            }
        )

    if turn.requires_callback and SCHEDULE_CALLBACK not in already_done:
        decisions.append(
            {
                "action_type": SCHEDULE_CALLBACK,
                "reason": "Customer asked to be called back",
                "time_text": turn.callback_time_text or "",
            }
        )

    if turn.wants_to_end_call or turn.intent == "not_interested":
        # A cold lead still gets one courtesy message, if we have their consent
        # signal (they stayed on the call and did not opt out).
        if classification == "COLD" and SEND_WHATSAPP not in already_done and turn.sentiment != "negative":
            decisions.append(
                {"action_type": SEND_WHATSAPP, "reason": "Courtesy brochure for a cold lead"}
            )
        decisions.append({"action_type": END_CALL, "reason": "Customer wants to end the call"})

    return decisions


async def dispatch(
    db: Session,
    call: Call,
    lead: Lead,
    customer: Customer,
    memory: CustomerMemory,
    classification: str,
    decisions: List[Dict[str, Any]],
    profile: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Persist each decision as a queued Action and kick off background work."""
    results: List[Dict[str, Any]] = []

    for decision in decisions:
        action = Action(
            call_id=call.id,
            lead_id=lead.id,
            action_type=decision["action_type"],
            status="queued",
            trigger_reason=decision.get("reason"),
            payload={k: v for k, v in decision.items() if k != "action_type"},
        )
        db.add(action)
        db.commit()
        db.refresh(action)

        record: Dict[str, Any] = {
            "action_id": action.id,
            "action_type": action.action_type,
            "status": "queued",
            "reason": action.trigger_reason,
            "result": {},
        }

        if action.action_type == SCHEDULE_CALLBACK:
            # Resolved inline: the agent must state the exact time it booked.
            parsed = parse_callback_time(decision.get("time_text") or "")
            callback = _persist_callback(db, call, lead, customer, parsed)
            schedule_callback_job(callback.id, parsed["scheduled_time"])
            action.status = "done"
            action.result = {
                "callback_id": callback.id,
                "human_time": parsed["human_time"],
                "scheduled_time": parsed["scheduled_time_iso"],
                "confidence": parsed["confidence"],
                "interpretation": parsed["interpretation"],
            }
            db.commit()
            record.update(status="done", result=action.result)
            await bus.broadcast("action.completed", record, call_id=call.id)

        elif action.action_type == MARK_DNC:
            _mark_dnc(db, customer, lead)
            action.status = "done"
            action.result = {"phone_number": customer.phone_number, "do_not_call": True}
            db.commit()
            record.update(status="done", result=action.result)
            await bus.broadcast("action.completed", record, call_id=call.id)

        elif action.action_type == SEND_WHATSAPP:
            message = compose(
                memory,
                classification,
                profile,
                callback_human_time=_latest_callback_time(db, lead.id),
            )
            wa = WhatsAppMessage(
                customer_id=customer.id,
                call_id=call.id,
                action_id=action.id,
                to_number=customer.phone_number,
                body=message["body"],
                media_url=message["media_url"],
                template_kind=message["template_kind"],
                provider=get_whatsapp().name,
                status="queued",
            )
            db.add(wa)
            db.commit()
            db.refresh(wa)

            record["result"] = {
                "whatsapp_message_id": wa.id,
                "body": wa.body,
                "template_kind": wa.template_kind,
                "to": wa.to_number,
            }
            await bus.broadcast("action.queued", record, call_id=call.id)
            # Fire and forget - the conversation continues immediately.
            asyncio.create_task(_send_whatsapp_bg(action.id, wa.id, call.id))

        elif action.action_type == END_CALL:
            record.update(status="done")
            action.status = "done"
            db.commit()
            await bus.broadcast("action.completed", record, call_id=call.id)

        results.append(record)

    return results


async def _send_whatsapp_bg(action_id: int, message_id: int, call_id: int) -> None:
    """Background sender. Owns its own DB session; never raises into the caller."""
    from app.db.session import session_scope

    provider = get_whatsapp()
    db = session_scope()
    try:
        wa = db.get(WhatsAppMessage, message_id)
        action = db.get(Action, action_id)
        if not wa or not action:
            return

        action.status = "running"
        db.commit()

        result = await provider.send_message(wa.to_number, wa.body)

        wa.status = result.get("status", "unknown")
        wa.provider = result.get("provider", provider.name)
        wa.provider_message_id = result.get("message_id")
        wa.error = result.get("error")
        action.status = "done" if wa.status in ("sent", "queued", "delivered") else "failed"
        action.result = {**(action.result or {}), **result, "whatsapp_message_id": wa.id}
        action.error = result.get("error")
        action.completed_at = now_utc()
        db.commit()

        await bus.broadcast(
            "whatsapp.sent",
            {
                "action_id": action.id,
                "message_id": wa.id,
                "to": wa.to_number,
                "body": wa.body,
                "status": wa.status,
                "provider": wa.provider,
                "template_kind": wa.template_kind,
                "simulated": bool(result.get("simulated")),
                "error": wa.error,
            },
            call_id=call_id,
        )
        log.info("WhatsApp %s -> %s (%s)", wa.status, wa.to_number, wa.provider)
    except Exception as exc:  # noqa: BLE001
        log.error("Background WhatsApp send failed: %s", exc)
        try:
            action = db.get(Action, action_id)
            if action:
                action.status = "failed"
                action.error = str(exc)[:300]
                db.commit()
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


def _persist_callback(
    db: Session, call: Call, lead: Lead, customer: Customer, parsed: Dict[str, Any]
) -> Callback:
    # One active callback per customer: reschedule rather than pile up.
    existing = (
        db.query(Callback)
        .filter(Callback.customer_id == customer.id, Callback.status == "scheduled")
        .all()
    )
    for old in existing:
        old.status = "cancelled"
        cancel_callback_job(old.id)

    callback = Callback(
        customer_id=customer.id,
        lead_id=lead.id,
        call_id=call.id,
        original_text=parsed["original_text"],
        scheduled_time=as_utc(parsed["scheduled_time"]),
        timezone_name=parsed["timezone"],
        confidence=parsed["confidence"],
        interpretation=parsed["interpretation"],
        status="scheduled",
    )
    db.add(callback)
    db.commit()
    db.refresh(callback)
    return callback


def _latest_callback_time(db: Session, lead_id: int) -> Optional[str]:
    callback = (
        db.query(Callback)
        .filter(Callback.lead_id == lead_id, Callback.status == "scheduled")
        .order_by(Callback.id.desc())
        .first()
    )
    return human_ist(callback.scheduled_time) if callback else None


def _mark_dnc(db: Session, customer: Customer, lead: Lead) -> None:
    customer.do_not_call = True
    lead.status = "COLD"
    existing = (
        db.query(DoNotCallEntry)
        .filter(DoNotCallEntry.phone_number == customer.phone_number)
        .first()
    )
    if not existing:
        db.add(
            DoNotCallEntry(
                phone_number=customer.phone_number,
                reason="Customer requested during call",
                source="call",
            )
        )
    for callback in db.query(Callback).filter(
        Callback.customer_id == customer.id, Callback.status == "scheduled"
    ):
        callback.status = "cancelled"
        cancel_callback_job(callback.id)
    db.commit()
