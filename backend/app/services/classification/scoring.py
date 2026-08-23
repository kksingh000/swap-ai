"""Deterministic, explainable lead scoring.

Business rules live here - not in the model - so the score is auditable and a
sales lead can be re-scored identically tomorrow. Weights are configurable at
runtime from the store_configuration table.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.store_profile import DEFAULT_SCORING_WEIGHTS, DEFAULT_THRESHOLDS
from app.schemas.nlu import CustomerMemory, TurnExtraction

TIMELINE_LABEL = {
    "today": "today",
    "this_week": "this week",
    "this_month": "this month",
    "later": "later",
    "exploring": "just exploring",
}


@dataclass
class ScoreResult:
    score: int
    classification: str
    reasons: List[str] = field(default_factory=list)
    signals: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "classification": self.classification,
            "reasons": self.reasons,
            "signals": self.signals,
        }


def detect_signals(memory: CustomerMemory, turns: List[TurnExtraction]) -> Dict[str, bool]:
    intents = set(memory.intent)
    for t in turns:
        intents.add(t.intent)
        intents.update(t.secondary_intents)

    max_buying_intent = max((t.buying_intent for t in turns), default=0.0)
    barriers = set(memory.barriers)

    return {
        "clear_buying_intent": bool(
            {"buy_thrift_clothes", "request_catalog", "request_store_visit"} & intents
        )
        or max_buying_intent >= 0.65,
        "specific_budget": memory.budget is not None,
        "specific_product": bool(memory.clothing_categories or memory.brands),
        "urgent_timeline": memory.timeline in ("today", "this_week"),
        "requests_catalog": "request_catalog" in intents
        or "whatsapp_catalog" in memory.features_requested,
        "requests_store_visit": "request_store_visit" in intents,
        "agrees_to_callback": memory.callback_requested,
        "wants_to_sell_or_swap": bool(
            {"sell_clothes", "swap_clothes", "donate_clothes"} & intents
        ),
        "shared_location": memory.location is not None,
        "positive_sentiment": memory.sentiment == "positive",
        # Objections and product questions mean they are still engaged.
        "engaged_question": bool({"question", "objection"} & intents) or bool(memory.questions_asked),
        "budget_objection": "budget_concern" in barriers,
        "needs_to_ask_someone": "needs_permission" in barriers,
        "trust_or_hygiene_concern": bool({"trust_concern", "hygiene_concern"} & barriers),
        "just_browsing": "just_browsing" in intents,
        "no_interest": "not_interested" in intents,
        "do_not_call": memory.do_not_call or "do_not_call" in intents,
    }


def _reason_text(signal: str, memory: CustomerMemory, points: int) -> str:
    sign = "+" if points >= 0 else ""
    detail = {
        "clear_buying_intent": "Customer showed clear buying intent",
        "specific_budget": f"Customer mentioned a Rs.{memory.budget} budget",
        "specific_product": "Customer asked for "
        + (", ".join(memory.brands + memory.clothing_categories) or "specific items"),
        "urgent_timeline": f"Customer needs it {TIMELINE_LABEL.get(memory.timeline or '', memory.timeline or 'soon')}",
        "requests_catalog": "Customer requested the catalogue on WhatsApp",
        "requests_store_visit": "Customer wants to visit the store",
        "agrees_to_callback": "Customer agreed to a callback",
        "wants_to_sell_or_swap": "Customer wants to sell or swap their clothes",
        "shared_location": f"Customer shared location ({memory.location})",
        "positive_sentiment": "Customer sounded positive",
        "engaged_question": "Customer asked questions about the product",
        "budget_objection": "Customer raised a budget objection",
        "needs_to_ask_someone": "Customer needs to check with someone else",
        "trust_or_hygiene_concern": "Customer raised a trust or hygiene concern",
        "just_browsing": "Customer is just browsing",
        "no_interest": "Customer said they are not interested",
        "do_not_call": "Customer asked not to be called again",
    }.get(signal, signal.replace("_", " ").title())
    return f"{detail} ({sign}{points})"


def score_lead(
    memory: CustomerMemory,
    turns: List[TurnExtraction],
    weights: Optional[Dict[str, int]] = None,
    thresholds: Optional[Dict[str, int]] = None,
) -> ScoreResult:
    weights = {**DEFAULT_SCORING_WEIGHTS, **(weights or {})}
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    signals = detect_signals(memory, turns)
    total = 0
    reasons: List[str] = []

    for signal, fired in signals.items():
        if not fired:
            continue
        points = int(weights.get(signal, 0))
        if points == 0:
            continue
        total += points
        reasons.append(_reason_text(signal, memory, points))

    score = max(0, min(100, total))

    negative_signal = any(
        signals[key]
        for key in ("do_not_call", "no_interest", "just_browsing", "budget_objection")
    )

    if signals["do_not_call"] or signals["no_interest"]:
        classification = "COLD"
    elif score >= thresholds["hot"]:
        classification = "HOT"
    elif score >= thresholds["warm"]:
        classification = "WARM"
    elif negative_signal or len(turns) >= 3:
        classification = "COLD"
    else:
        # An early, low-signal conversation is unknown - not cold. Calling it
        # COLD too early would suppress follow-up on a lead still warming up.
        classification = "UNKNOWN"

    if not reasons:
        reasons = ["No qualifying signals detected yet"]

    return ScoreResult(
        score=score,
        classification=classification,
        reasons=reasons,
        signals={k: v for k, v in signals.items() if v},
    )
