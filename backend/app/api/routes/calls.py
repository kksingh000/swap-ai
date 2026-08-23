"""Call lifecycle endpoints - real phone calls and browser demo calls."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db
from app.models import Action, Call, CallTranscript, ConversationMessage, Customer
from app.schemas.api import (
    CallDetail,
    CallOut,
    MessageOut,
    StartCallRequest,
    StartDemoCallRequest,
    TurnRequest,
    TurnResponse,
)
from app.services import customer_service
from app.services.conversation.engine import ConversationEngine
from app.services.telephony.factory import get_telephony

log = get_logger(__name__)
router = APIRouter(prefix="/calls", tags=["calls"])


DEMO_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "hot",
        "label": "HOT lead - buys now",
        "expected": "HOT",
        "customer_name": "Rahul",
        "language": "english",
        "description": "Specific product, clear budget, urgent timeline, asks for the catalogue.",
        "utterances": [
            "Yeah sure, I have a minute. What is this about?",
            "I need some branded jackets and hoodies. My budget is around 1500 and I need them this week.",
            "Size L. Can you send me the catalog on WhatsApp?",
        ],
    },
    {
        "id": "warm",
        "label": "WARM lead - needs a callback",
        "expected": "WARM",
        "customer_name": "Priya",
        "language": "hinglish",
        "description": "Interested in swapping but wants to check her wardrobe first.",
        "utterances": [
            "Haan bolo, kya hai?",
            "Idea to achha hai par pehle main apni wardrobe check karungi ki kya swap kar sakti hoon.",
            "Kal shaam 6 baje call kar lena.",
        ],
    },
    {
        "id": "cold",
        "label": "COLD lead - just curious",
        "expected": "COLD",
        "customer_name": "Aman",
        "language": "english",
        "description": "No need right now, respectful close, no aggressive follow-up.",
        "utterances": [
            "Who is this?",
            "Oh, I was just curious what you people do. I'm not looking for anything right now.",
        ],
    },
    {
        "id": "hinglish_budget",
        "label": "Hinglish - budget + brands",
        "expected": "HOT",
        "customer_name": "Sneha",
        "language": "hinglish",
        "description": "Code-switched budget extraction: 'Budget around 1000 hai but branded jackets chahiye'.",
        "utterances": [
            "Haan ji boliye.",
            "Budget around 1000 hai but mujhe branded jackets chahiye, Zara ya H&M type.",
            "Is hafte chahiye. WhatsApp pe bhej do collection.",
        ],
    },
    {
        "id": "seller",
        "label": "Seller - wants to sell clothes",
        "expected": "WARM",
        "customer_name": "Karan",
        "language": "hinglish",
        "description": "Wants to sell unused clothes, asks how much he will get.",
        "utterances": [
            "Haan sunn raha hoon.",
            "Mere paas kaafi kapde pade hain jo main pehenta nahi. Bech sakta hoon kya?",
            "Levis ki jeans aur kuch shirts hain. Kitna mil jayega?",
        ],
    },
    {
        "id": "objection",
        "label": "Objection - hygiene + trust",
        "expected": "WARM",
        "customer_name": "Meera",
        "language": "english",
        "description": "Tests the FAQ knowledge base and objection handling.",
        "utterances": [
            "How do I know the clothes are clean? Used clothes sound unhygienic.",
            "And is this genuine? How do I trust you?",
            "Okay that sounds fair. Show me what you have under 800.",
        ],
    },
    {
        "id": "dnc",
        "label": "Do-not-call - compliance",
        "expected": "COLD",
        "customer_name": "Vikram",
        "language": "english",
        "description": "Customer opts out; the agent must confirm, log it and hang up.",
        "utterances": ["Please don't call me again. Remove my number."],
    },
]


def _engine(db: Session) -> ConversationEngine:
    return ConversationEngine(db)


def _get_call(db: Session, call_id: int) -> Call:
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call


@router.post("/start", status_code=201)
async def start_call(payload: StartCallRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Start a real outbound phone call (mock provider unless Twilio is configured)."""
    blocked, reason = customer_service.is_do_not_call(db, payload.phone_number)
    if blocked:
        raise HTTPException(status_code=403, detail=f"Cannot call this number: {reason}")

    customer = customer_service.get_or_create(
        db, payload.phone_number, payload.customer_name, payload.language
    )
    telephony = get_telephony()
    engine = _engine(db)
    call, opening = await engine.start_call(customer, mode="phone", provider=telephony.name)

    result = await telephony.make_call(
        customer_name=customer.name or "there",
        phone_number=customer.phone_number,
        campaign_type=payload.campaign_type,
        call_id=call.id,
    )

    call.provider_call_sid = result.get("call_sid")
    if result.get("status") == "failed":
        call.status = "failed"
        call.outcome = result.get("error", "provider error")
    db.commit()

    return {
        "call_id": call.id,
        "opening_message": opening,
        "telephony": result,
        "customer": {"id": customer.id, "name": customer.name, "phone_number": customer.phone_number},
    }


@router.post("/demo/start", status_code=201)
async def start_demo_call(
    payload: StartDemoCallRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Start a browser demo call. No telephony, no cost, full pipeline."""
    scenario = next((s for s in DEMO_SCENARIOS if s["id"] == payload.scenario), None)
    name = payload.customer_name or (scenario or {}).get("customer_name") or "Demo Customer"
    language = payload.language or (scenario or {}).get("language") or "english"
    phone = payload.phone_number or customer_service.demo_phone()

    customer = customer_service.get_or_create(db, phone, name, language)
    customer.do_not_call = False  # a demo run should never be blocked by an earlier demo
    db.commit()

    engine = _engine(db)
    call, opening = await engine.start_call(customer, mode="demo", provider="browser")

    return {
        "call_id": call.id,
        "opening_message": opening,
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "phone_number": customer.phone_number,
            "language": customer.preferred_language,
        },
        "scenario": scenario,
    }


@router.get("/demo/scenarios")
async def list_scenarios() -> Dict[str, Any]:
    return {"scenarios": DEMO_SCENARIOS}


@router.post("/{call_id}/turn", response_model=TurnResponse)
async def submit_turn(
    call_id: int, payload: TurnRequest, db: Session = Depends(get_db)
) -> TurnResponse:
    """Feed one customer utterance (from mic, text box or phone) into the engine."""
    call = _get_call(db, call_id)
    if call.status == "completed":
        raise HTTPException(status_code=409, detail="This call has already ended")

    engine = _engine(db)
    result = await engine.handle_turn(call, payload.text)
    return TurnResponse(**result)


@router.post("/{call_id}/end")
async def end_call(
    call_id: int, outcome: str = Query(default="completed"), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    call = _get_call(db, call_id)
    engine = _engine(db)
    result = await engine.end_call(call, outcome=outcome)

    if call.mode == "phone" and call.provider_call_sid:
        try:
            await get_telephony().end_call(call.provider_call_sid)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not hang up provider call: %s", exc)
    return result


@router.get("", response_model=List[CallOut])
async def list_calls(
    status: Optional[str] = None,
    mode: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> List[Call]:
    query = db.query(Call)
    if status:
        query = query.filter(Call.status == status)
    if mode:
        query = query.filter(Call.mode == mode)
    return query.order_by(Call.id.desc()).limit(limit).all()


@router.get("/{call_id}", response_model=CallDetail)
async def get_call(call_id: int, db: Session = Depends(get_db)) -> CallDetail:
    call = _get_call(db, call_id)
    customer = db.get(Customer, call.customer_id)
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.call_id == call.id)
        .order_by(ConversationMessage.id)
        .all()
    )
    actions = db.query(Action).filter(Action.call_id == call.id).order_by(Action.id).all()

    detail = CallDetail.model_validate(call)
    detail.customer_name = customer.name if customer else None
    detail.phone_number = customer.phone_number if customer else None
    detail.messages = [MessageOut.model_validate(m) for m in messages]
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
        for a in actions
    ]
    return detail


@router.get("/{call_id}/transcript")
async def get_transcript(call_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    call = _get_call(db, call_id)
    stored = db.query(CallTranscript).filter(CallTranscript.call_id == call_id).first()
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.call_id == call_id)
        .order_by(ConversationMessage.id)
        .all()
    )
    text = stored.text if stored else "\n".join(
        f"{'AGENT' if m.role == 'agent' else 'CUSTOMER'}: {m.content}" for m in messages
    )
    return {
        "call_id": call_id,
        "text": text,
        "word_count": len(text.split()),
        "turns": [
            {
                "role": m.role,
                "content": m.content,
                "language": m.language,
                "intent": m.intent,
                "sentiment": m.sentiment,
                "score_after": m.score_after,
                "created_at": m.created_at,
            }
            for m in messages
        ],
        "summary": call.summary,
    }
