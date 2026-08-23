"""Lead management: list, filter, drill down, manual override."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    Action,
    Call,
    Callback,
    ConversationMessage,
    Customer,
    DoNotCallEntry,
    Lead,
    LeadScore,
    WhatsAppMessage,
)
from app.schemas.api import CallOut, LeadDetail, LeadOut, LeadPatch, MessageOut
from app.utils.timeutil import human_ist

router = APIRouter(prefix="/leads", tags=["leads"])


def _decorate(db: Session, lead: Lead) -> LeadOut:
    customer = db.get(Customer, lead.customer_id)
    out = LeadOut.model_validate(lead)
    out.customer_name = customer.name if customer else None
    out.phone_number = customer.phone_number if customer else None
    out.do_not_call = bool(customer and customer.do_not_call)

    callback = (
        db.query(Callback)
        .filter(Callback.lead_id == lead.id, Callback.status.in_(["scheduled", "due"]))
        .order_by(Callback.scheduled_time)
        .first()
    )
    out.next_callback = human_ist(callback.scheduled_time) if callback else None
    return out


@router.get("", response_model=List[LeadOut])
async def list_leads(
    status: Optional[str] = Query(default=None, description="HOT | WARM | COLD | UNKNOWN"),
    search: Optional[str] = None,
    min_score: Optional[int] = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
) -> List[LeadOut]:
    query = db.query(Lead)
    if status:
        query = query.filter(Lead.status == status.upper())
    if min_score is not None:
        query = query.filter(Lead.score >= min_score)
    if search:
        pattern = f"%{search.lower()}%"
        customer_ids = [
            c.id
            for c in db.query(Customer).filter(
                (Customer.name.ilike(pattern)) | (Customer.phone_number.ilike(pattern))
            )
        ]
        query = query.filter(Lead.customer_id.in_(customer_ids or [-1]))

    leads = query.order_by(Lead.score.desc(), Lead.id.desc()).limit(limit).all()
    return [_decorate(db, lead) for lead in leads]


@router.get("/{lead_id}", response_model=LeadDetail)
async def get_lead(lead_id: int, db: Session = Depends(get_db)) -> LeadDetail:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    base = _decorate(db, lead)
    detail = LeadDetail(**base.model_dump())
    detail.memory = lead.memory or {}

    calls = db.query(Call).filter(Call.lead_id == lead.id).order_by(Call.id.desc()).all()
    detail.calls = [CallOut.model_validate(c) for c in calls]

    call_ids = [c.id for c in calls] or [-1]
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.call_id.in_(call_ids))
        .order_by(ConversationMessage.id)
        .all()
    )
    detail.transcript = [MessageOut.model_validate(m) for m in messages]

    detail.score_history = [
        {
            "id": s.id,
            "score": s.score,
            "classification": s.classification,
            "reasons": s.reasons,
            "signals": s.signals,
            "rules_label": s.rules_label,
            "ml_label": s.ml_label,
            "ml_confidence": s.ml_confidence,
            "llm_label": s.llm_label,
            "ensemble_detail": s.ensemble_detail,
            "created_at": s.created_at,
        }
        for s in db.query(LeadScore).filter(LeadScore.lead_id == lead.id).order_by(LeadScore.id).all()
    ]

    detail.actions = [
        {
            "id": a.id,
            "action_type": a.action_type,
            "status": a.status,
            "reason": a.trigger_reason,
            "result": a.result,
            "error": a.error,
            "created_at": a.created_at,
        }
        for a in db.query(Action).filter(Action.lead_id == lead.id).order_by(Action.id).all()
    ]

    detail.whatsapp_messages = [
        {
            "id": w.id,
            "to": w.to_number,
            "body": w.body,
            "template_kind": w.template_kind,
            "status": w.status,
            "provider": w.provider,
            "media_url": w.media_url,
            "created_at": w.created_at,
        }
        for w in db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.customer_id == lead.customer_id)
        .order_by(WhatsAppMessage.id)
        .all()
    ]

    detail.callbacks = [
        {
            "id": c.id,
            "scheduled_time": human_ist(c.scheduled_time),
            "original_text": c.original_text,
            "interpretation": c.interpretation,
            "confidence": c.confidence,
            "status": c.status,
        }
        for c in db.query(Callback).filter(Callback.lead_id == lead.id).order_by(Callback.id).all()
    ]
    return detail


@router.patch("/{lead_id}", response_model=LeadOut)
async def patch_lead(lead_id: int, payload: LeadPatch, db: Session = Depends(get_db)) -> LeadOut:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    customer = db.get(Customer, lead.customer_id)

    data = payload.model_dump(exclude_unset=True)
    notes = data.pop("notes", None)
    do_not_call = data.pop("do_not_call", None)

    if "status" in data and data["status"]:
        data["status"] = str(data["status"]).upper()

    for field, value in data.items():
        setattr(lead, field, value)

    if customer:
        if notes is not None:
            customer.notes = notes
        if do_not_call is not None:
            customer.do_not_call = bool(do_not_call)
            existing = (
                db.query(DoNotCallEntry)
                .filter(DoNotCallEntry.phone_number == customer.phone_number)
                .first()
            )
            if do_not_call and not existing:
                db.add(
                    DoNotCallEntry(
                        phone_number=customer.phone_number,
                        reason="Marked manually from the dashboard",
                        source="manual",
                    )
                )
            elif not do_not_call and existing:
                db.delete(existing)

    db.commit()
    db.refresh(lead)
    return _decorate(db, lead)


@router.get("/{lead_id}/score-explanation")
async def score_explanation(lead_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Why is this lead HOT/WARM/COLD - the full audit trail."""
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    latest = (
        db.query(LeadScore)
        .filter(LeadScore.lead_id == lead_id)
        .order_by(LeadScore.id.desc())
        .first()
    )
    return {
        "lead_id": lead_id,
        "score": lead.score,
        "classification": lead.status,
        "reasons": lead.score_reasons,
        "signals": latest.signals if latest else {},
        "voters": {
            "rules": latest.rules_label if latest else None,
            "classifier": {"label": latest.ml_label, "confidence": latest.ml_confidence}
            if latest
            else None,
            "llm": latest.llm_label if latest else None,
        },
        "ensemble_detail": latest.ensemble_detail if latest else {},
    }
