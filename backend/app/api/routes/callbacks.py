"""Callback scheduling: create from natural language, list, complete, cancel."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Callback, Customer, Lead
from app.schemas.api import CallbackCreate, CallbackOut, ParseTimeRequest
from app.services import customer_service
from app.services.scheduling.nlp_time import parse_callback_time
from app.services.scheduling.scheduler import cancel_callback_job, schedule_callback_job
from app.utils.timeutil import as_utc, human_ist, to_ist

router = APIRouter(prefix="/callbacks", tags=["callbacks"])


def _serialise(db: Session, callback: Callback) -> CallbackOut:
    customer = db.get(Customer, callback.customer_id)
    local = to_ist(callback.scheduled_time)
    return CallbackOut(
        id=callback.id,
        customer_id=callback.customer_id,
        customer_name=customer.name if customer else None,
        phone_number=customer.phone_number if customer else None,
        lead_id=callback.lead_id,
        call_id=callback.call_id,
        original_text=callback.original_text,
        scheduled_time_utc=as_utc(callback.scheduled_time),
        scheduled_time_ist=local.isoformat() if local else "",
        human_time=human_ist(callback.scheduled_time),
        confidence=callback.confidence,
        interpretation=callback.interpretation,
        status=callback.status,
    )


@router.post("", response_model=CallbackOut, status_code=201)
async def create_callback(payload: CallbackCreate, db: Session = Depends(get_db)) -> CallbackOut:
    customer: Optional[Customer] = None
    lead: Optional[Lead] = db.get(Lead, payload.lead_id) if payload.lead_id else None

    if lead:
        customer = db.get(Customer, lead.customer_id)
    elif payload.customer_id:
        customer = db.get(Customer, payload.customer_id)
    elif payload.phone_number:
        customer = customer_service.get_or_create(db, payload.phone_number)

    if not customer:
        raise HTTPException(status_code=400, detail="Provide lead_id, customer_id or phone_number")

    parsed = parse_callback_time(payload.when_text)
    callback = Callback(
        customer_id=customer.id,
        lead_id=lead.id if lead else None,
        original_text=payload.when_text,
        scheduled_time=as_utc(parsed["scheduled_time"]),
        timezone_name=parsed["timezone"],
        confidence=parsed["confidence"],
        interpretation=parsed["interpretation"],
        notes=payload.notes,
        status="scheduled",
    )
    db.add(callback)
    db.commit()
    db.refresh(callback)

    schedule_callback_job(callback.id, parsed["scheduled_time"])
    return _serialise(db, callback)


@router.get("", response_model=List[CallbackOut])
async def list_callbacks(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
) -> List[CallbackOut]:
    query = db.query(Callback)
    if status:
        query = query.filter(Callback.status == status)
    callbacks = query.order_by(Callback.scheduled_time).limit(limit).all()
    return [_serialise(db, c) for c in callbacks]


@router.post("/parse")
async def parse_time(payload: ParseTimeRequest) -> Dict[str, Any]:
    """Expose the natural-language time parser directly - great for demos/tests."""
    parsed = parse_callback_time(payload.text)
    return {
        "original_text": parsed["original_text"],
        "scheduled_time": parsed["scheduled_time_iso"],
        "human_time": parsed["human_time"],
        "confidence": parsed["confidence"],
        "interpretation": parsed["interpretation"],
        "timezone": parsed["timezone"],
    }


@router.patch("/{callback_id}", response_model=CallbackOut)
async def update_callback(
    callback_id: int,
    status: str = Query(description="scheduled | done | cancelled | missed"),
    db: Session = Depends(get_db),
) -> CallbackOut:
    callback = db.get(Callback, callback_id)
    if not callback:
        raise HTTPException(status_code=404, detail="Callback not found")
    if status not in ("scheduled", "done", "cancelled", "missed", "due"):
        raise HTTPException(status_code=400, detail="Invalid status")

    callback.status = status
    if status in ("cancelled", "done"):
        cancel_callback_job(callback.id)
    db.commit()
    db.refresh(callback)
    return _serialise(db, callback)
