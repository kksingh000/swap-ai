"""Hybrid NLU: deterministic rules first, LLM on top, rules win on hard facts.

Money, opt-outs and callback requests are too important to leave to a 3B model,
so even when the LLM is available its output is merged *under* the regex layer.
"""
import time
from typing import Any, Dict, Optional, Tuple

from app.core.logging import get_logger
from app.schemas.nlu import TurnExtraction
from app.services.conversation import rules_nlu
from app.services.conversation.prompts import EXTRACTION_FEWSHOT, EXTRACTION_SYSTEM
from app.services.llm.base import LLMProvider

log = get_logger(__name__)


async def extract(
    text: str, llm: Optional[LLMProvider] = None, agent_asked: Optional[str] = None
) -> Tuple[TurnExtraction, Dict[str, Any]]:
    """Return (extraction, debug_info)."""
    started = time.perf_counter()
    rule_turn = rules_nlu.extract_turn(text, agent_asked=agent_asked)
    debug: Dict[str, Any] = {"rules_ms": int((time.perf_counter() - started) * 1000)}

    if llm is None or not llm.available:
        debug["llm_used"] = False
        return rule_turn, debug

    messages = (
        [{"role": "system", "content": EXTRACTION_SYSTEM}]
        + EXTRACTION_FEWSHOT
        + [{"role": "user", "content": f'Customer said: "{text}"'}]
    )

    llm_started = time.perf_counter()
    try:
        payload = await llm.complete_json(messages, max_tokens=420)
        debug["llm_ms"] = int((time.perf_counter() - llm_started) * 1000)
        if not payload:
            debug["llm_used"] = False
            debug["llm_error"] = "unparseable json"
            return rule_turn, debug

        llm_turn = TurnExtraction(**{**payload, "source": "llm"})
        merged = merge(rule_turn, llm_turn)
        debug["llm_used"] = True
        debug["llm_raw"] = payload
        return merged, debug
    except Exception as exc:  # noqa: BLE001 - never let NLU take the call down
        log.warning("LLM extraction failed (%s); using rules only", exc)
        debug["llm_used"] = False
        debug["llm_error"] = str(exc)[:200]
        return rule_turn, debug


def merge(rules: TurnExtraction, llm: TurnExtraction) -> TurnExtraction:
    """Rules are authoritative for money/opt-out/callback; the LLM adds nuance."""
    out = llm.model_copy(deep=True)
    out.source = "merged"

    # Hard facts: regex wins whenever it found something.
    if rules.budget.amount:
        out.budget = rules.budget
    if rules.do_not_call:
        out.do_not_call = True
        out.intent = "do_not_call"
    if rules.requires_callback:
        out.requires_callback = True
        out.callback_time_text = out.callback_time_text or rules.callback_time_text
    if rules.requires_whatsapp:
        out.requires_whatsapp = True
    if rules.wants_to_end_call:
        out.wants_to_end_call = True

    # Additive fields: union of both views.
    out.product_categories = _union(rules.product_categories, out.product_categories)
    out.brands = _union(rules.brands, out.brands)
    out.barriers = _union(rules.barriers, out.barriers)
    out.secondary_intents = _union(rules.secondary_intents, out.secondary_intents)

    out.size = out.size or rules.size
    out.location = out.location or rules.location
    out.gender_preference = out.gender_preference or rules.gender_preference
    out.customer_name = out.customer_name or rules.customer_name
    out.asked_question = out.asked_question or rules.asked_question

    if out.urgency == "unknown" and rules.urgency != "unknown":
        out.urgency = rules.urgency
    if out.intent == "other" and rules.intent != "other":
        out.intent = rules.intent
    if rules.language != "english":
        out.language = rules.language

    # Blend the two confidence views rather than trusting either alone.
    out.buying_intent = round((rules.buying_intent * 0.5) + (llm.buying_intent * 0.5), 2)
    return out


def _union(a: list, b: list) -> list:
    seen = list(a)
    for item in b:
        if item not in seen:
            seen.append(item)
    return seen
