"""Dashboard aggregates and system health."""
from datetime import timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import Action, Call, Callback, Customer, Lead, WhatsAppMessage
from app.services.classification.ml_classifier import get_classifier
from app.services.llm.factory import get_llm
from app.services.telephony.factory import get_telephony
from app.services.whatsapp.factory import get_whatsapp
from app.utils.timeutil import human_ist, now_utc

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    counts = dict(
        db.query(Lead.status, func.count(Lead.id)).group_by(Lead.status).all()
    )
    total_calls = db.query(func.count(Call.id)).scalar() or 0
    active_calls = db.query(func.count(Call.id)).filter(Call.status == "active").scalar() or 0
    completed = db.query(func.count(Call.id)).filter(Call.status == "completed").scalar() or 0

    avg_duration = (
        db.query(func.avg(Call.duration_seconds)).filter(Call.duration_seconds.isnot(None)).scalar()
    )
    avg_score = db.query(func.avg(Lead.score)).scalar()

    hot = counts.get("HOT", 0)
    warm = counts.get("WARM", 0)
    cold = counts.get("COLD", 0)
    scored = hot + warm + cold

    since = now_utc() - timedelta(days=7)
    recent_calls = db.query(func.count(Call.id)).filter(Call.started_at >= since).scalar() or 0

    return {
        "total_calls": total_calls,
        "active_calls": active_calls,
        "completed_calls": completed,
        "calls_last_7_days": recent_calls,
        "total_leads": db.query(func.count(Lead.id)).scalar() or 0,
        "hot_leads": hot,
        "warm_leads": warm,
        "cold_leads": cold,
        "unknown_leads": counts.get("UNKNOWN", 0),
        "conversion_rate": round((hot / scored) * 100, 1) if scored else 0.0,
        "whatsapp_sent": db.query(func.count(WhatsAppMessage.id)).scalar() or 0,
        "callbacks_scheduled": db.query(func.count(Callback.id))
        .filter(Callback.status.in_(["scheduled", "due"]))
        .scalar()
        or 0,
        "actions_triggered": db.query(func.count(Action.id)).scalar() or 0,
        "do_not_call_count": db.query(func.count(Customer.id))
        .filter(Customer.do_not_call.is_(True))
        .scalar()
        or 0,
        "avg_call_duration_seconds": int(avg_duration) if avg_duration else 0,
        "avg_lead_score": round(float(avg_score), 1) if avg_score else 0.0,
    }


@router.get("/recent-activity")
async def recent_activity(limit: int = 15, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    activity: List[Dict[str, Any]] = []

    for call in db.query(Call).order_by(Call.id.desc()).limit(limit).all():
        customer = db.get(Customer, call.customer_id)
        activity.append(
            {
                "kind": "call",
                "id": call.id,
                "title": f"Call with {customer.name if customer else 'customer'}",
                "detail": f"{call.final_status} - {call.final_score}/100",
                "status": call.status,
                "at": call.started_at,
            }
        )

    for message in db.query(WhatsAppMessage).order_by(WhatsAppMessage.id.desc()).limit(limit).all():
        activity.append(
            {
                "kind": "whatsapp",
                "id": message.id,
                "title": f"WhatsApp to {message.to_number}",
                "detail": message.template_kind or "message",
                "status": message.status,
                "at": message.created_at,
            }
        )

    for callback in db.query(Callback).order_by(Callback.id.desc()).limit(limit).all():
        activity.append(
            {
                "kind": "callback",
                "id": callback.id,
                "title": "Callback scheduled",
                "detail": human_ist(callback.scheduled_time),
                "status": callback.status,
                "at": callback.created_at,
            }
        )

    activity.sort(key=lambda item: item["at"] or now_utc(), reverse=True)
    return activity[:limit]


@router.get("/funnel")
async def funnel(db: Session = Depends(get_db)) -> Dict[str, Any]:
    total = db.query(func.count(Lead.id)).scalar() or 0
    engaged = db.query(func.count(Lead.id)).filter(Lead.score > 0).scalar() or 0
    qualified = db.query(func.count(Lead.id)).filter(Lead.budget.isnot(None)).scalar() or 0
    actioned = (
        db.query(func.count(func.distinct(Action.lead_id)))
        .filter(Action.action_type == "send_whatsapp")
        .scalar()
        or 0
    )
    hot = db.query(func.count(Lead.id)).filter(Lead.status == "HOT").scalar() or 0
    return {
        "stages": [
            {"label": "Contacted", "value": total},
            {"label": "Engaged", "value": engaged},
            {"label": "Qualified (budget known)", "value": qualified},
            {"label": "Catalogue sent", "value": actioned},
            {"label": "Hot", "value": hot},
        ]
    }


@router.get("/health")
async def health() -> Dict[str, Any]:
    llm = get_llm()
    return {
        "status": "ok",
        "environment": settings.ENV,
        "components": {
            "llm": await llm.health(),
            "telephony": await get_telephony().health(),
            "whatsapp": await get_whatsapp().health(),
            "classifier": get_classifier().info(),
            "scheduler": {"enabled": settings.SCHEDULER_ENABLED, "timezone": settings.TIMEZONE},
            "database": {"url": settings.DATABASE_URL.split("://")[0]},
        },
        "cost_mode": (
            "FREE (no paid provider configured)"
            if not llm.available or llm.name in ("rules", "ollama")
            else f"FREE-TIER ({llm.name})"
        ),
    }
