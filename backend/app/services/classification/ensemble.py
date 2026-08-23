"""Three voters, one decision.

    rules      -> deterministic business logic, always available, fully explainable
    classifier -> trained on 500+ Hinglish utterances, fast, catches phrasing rules miss
    llm        -> reads the whole conversation, catches nuance the other two miss

Weighted vote, with hard overrides for do-not-call / no-interest because those
are compliance decisions, not predictions.
"""
import json
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.core.store_profile import DEFAULT_THRESHOLDS
from app.schemas.nlu import CustomerMemory, TurnExtraction
from app.services.classification.ml_classifier import get_classifier
from app.services.classification.scoring import ScoreResult, score_lead
from app.services.conversation.prompts import CLASSIFY_SYSTEM
from app.services.llm.base import LLMProvider

log = get_logger(__name__)

LABELS = ("HOT", "WARM", "COLD")
BAND_CENTER = {"HOT": 75, "WARM": 42, "COLD": 12}


async def classify(
    memory: CustomerMemory,
    turns: List[TurnExtraction],
    last_utterance: str,
    transcript: Optional[List[Dict[str, str]]] = None,
    llm: Optional[LLMProvider] = None,
    weights: Optional[Dict[str, int]] = None,
    thresholds: Optional[Dict[str, int]] = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    rules: ScoreResult = score_lead(memory, turns, weights, thresholds)

    ml_label: Optional[str] = None
    ml_confidence: Optional[float] = None
    prediction = get_classifier().predict(last_utterance)
    if prediction:
        ml_label, ml_confidence = prediction

    llm_label: Optional[str] = None
    llm_confidence: Optional[float] = None
    llm_reason: Optional[str] = None
    if use_llm and llm is not None and llm.available and transcript:
        result = await _llm_classify(llm, transcript)
        if result:
            llm_label = result.get("label")
            llm_confidence = result.get("confidence")
            llm_reason = result.get("reason")

    # Each voter contributes at most its configured weight, scaled by its own
    # confidence. Inflating the model votes here would let a confident guess
    # outrank the deterministic business rules, which is never what we want.
    votes: Dict[str, float] = {label: 0.0 for label in LABELS}
    if rules.classification in votes:
        votes[rules.classification] += settings.ENSEMBLE_WEIGHT_RULES
    if ml_label in votes:
        votes[ml_label] += settings.ENSEMBLE_WEIGHT_ML * float(ml_confidence or 0.5)
    if llm_label in votes:
        votes[llm_label] += settings.ENSEMBLE_WEIGHT_LLM * float(llm_confidence or 0.7)

    if all(v == 0 for v in votes.values()):
        # No voter committed yet (a single neutral opening turn) - stay UNKNOWN
        # rather than manufacturing a COLD label.
        final_label = "UNKNOWN"
    else:
        best = max(votes.values())
        # On a tie the deterministic engine wins: it is the auditable one.
        final_label = (
            rules.classification
            if rules.classification in votes and votes[rules.classification] == best
            else max(votes, key=votes.get)
        )

    # HOT triggers a real customer-facing action (the WhatsApp send), so it has
    # to be earned with deterministic business signals - never on a model hunch.
    if final_label == "HOT" and rules.classification != "HOT" and rules.score < thresholds["warm"]:
        final_label = "WARM" if rules.classification != "COLD" else "COLD"

    # Compliance overrides beat every model.
    if memory.do_not_call or "not_interested" in memory.intent:
        final_label = "COLD"

    # Keep the displayed score consistent with the label the ensemble picked.
    score = rules.score
    if final_label == "UNKNOWN":
        pass
    elif final_label != rules.classification and rules.classification != "UNKNOWN":
        score = int(round((score + BAND_CENTER[final_label]) / 2))
        if final_label == "HOT":
            score = max(score, thresholds["hot"])
        elif final_label == "WARM":
            score = max(min(score, thresholds["hot"] - 1), thresholds["warm"])
        else:
            score = min(score, thresholds["warm"] - 1)
    elif rules.classification == "UNKNOWN" and final_label != "UNKNOWN" and turns:
        score = max(score, BAND_CENTER[final_label] // 2)

    reasons = list(rules.reasons)
    if llm_reason:
        reasons.append(f"AI read of the call: {llm_reason}")
    if ml_label and ml_label != rules.classification:
        reasons.append(
            f"Trained classifier read the last message as {ml_label} ({int((ml_confidence or 0) * 100)}% confident)"
        )

    return {
        "score": max(0, min(100, score)),
        "classification": final_label,
        "reasons": reasons,
        "signals": rules.signals,
        "rules_label": rules.classification,
        "rules_score": rules.score,
        "ml_label": ml_label,
        "ml_confidence": ml_confidence,
        "llm_label": llm_label,
        "ensemble_detail": {
            "votes": {k: round(v, 3) for k, v in votes.items()},
            "weights": {
                "rules": settings.ENSEMBLE_WEIGHT_RULES,
                "ml": settings.ENSEMBLE_WEIGHT_ML,
                "llm": settings.ENSEMBLE_WEIGHT_LLM,
            },
            "llm_reason": llm_reason,
            "voters_available": {
                "rules": True,
                "ml": ml_label is not None,
                "llm": llm_label is not None,
            },
        },
    }


async def _llm_classify(llm: LLMProvider, transcript: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in transcript[-10:])
    try:
        payload = await llm.complete_json(
            [
                {"role": "system", "content": CLASSIFY_SYSTEM},
                {"role": "user", "content": convo},
            ],
            max_tokens=150,
        )
        if not payload:
            return None
        label = str(payload.get("label", "")).upper().strip()
        if label not in LABELS:
            return None
        try:
            confidence = float(payload.get("confidence", 0.7))
        except (TypeError, ValueError):
            confidence = 0.7
        return {
            "label": label,
            "confidence": max(0.0, min(1.0, confidence)),
            "reason": str(payload.get("reason", ""))[:200] or None,
        }
    except Exception as exc:  # noqa: BLE001
        log.debug("LLM classification skipped: %s", exc)
        return None


def compare_methods(utterance: str, memory: CustomerMemory, turns: List[TurnExtraction]) -> Dict[str, Any]:
    """Used by /api/training/results to show rules vs classifier side by side."""
    rules = score_lead(memory, turns)
    prediction = get_classifier().predict(utterance)
    return {
        "utterance": utterance,
        "rules": {"label": rules.classification, "score": rules.score, "reasons": rules.reasons},
        "classifier": (
            {"label": prediction[0], "confidence": prediction[1]} if prediction else None
        ),
    }
