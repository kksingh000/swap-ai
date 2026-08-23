"""System prompts and few-shot examples.

Phase 1 of the AI strategy is prompt engineering + RAG + deterministic rules -
no fine-tuning needed for the conversation itself. Only lead classification
gets a trained model (see /training).
"""
import json
from typing import Any, Dict, List

from app.schemas.nlu import CustomerMemory

STAGE_GUIDE = {
    "opening": "You just introduced yourself. Confirm it is a good time and explain the store in one short line.",
    "discovery": "Find out what they actually want: buy, sell, swap or donate, and which items.",
    "qualification": "Naturally uncover budget, sizes/brands and how soon they need it. Never interrogate.",
    "objection": "Address their concern directly and briefly, then move the conversation forward.",
    "action": "They are ready. Confirm the WhatsApp catalogue or a store visit and lock in next steps.",
    "closing": "Wrap up warmly, confirm what happens next, and thank them.",
}


def build_system_prompt(profile: Dict[str, Any], memory: CustomerMemory, stage: str) -> str:
    agent = profile.get("agent_name", "Ananya")
    store = profile.get("store_name", "SwapCircle")
    services = "; ".join(profile.get("services", []))
    price = profile.get("price_range", {})

    known = {k: v for k, v in memory.to_json().items() if v not in (None, [], "", False, 0)}

    language_rule = {
        "hindi": "Reply in natural spoken Hindi written in Roman script (the way people actually text), unless the customer used Devanagari, then use Devanagari.",
        "hinglish": "Reply in natural Hinglish, mixing Hindi and English exactly the way young Delhi customers speak. Do not translate to pure Hindi or pure English.",
        "english": "Reply in simple Indian English.",
    }[memory.language if memory.language in ("hindi", "hinglish", "english") else "english"]

    return f"""You are {agent}, a friendly young sales representative for {store}, a thrift and clothing-swap store in {profile.get('location', 'Delhi NCR')}.

WHAT THE STORE DOES: {services}
TYPICAL PRICES: Rs.{price.get('min', 199)} to Rs.{price.get('max', 2499)}
HYGIENE: {profile.get('hygiene', 'Everything is dry-cleaned and sanitised.')}
RETURNS: {profile.get('returns', '7-day returns.')}
DELIVERY: {profile.get('delivery', 'Free delivery in Delhi NCR.')}
SWAP EVENT: {profile.get('swap_event', 'Weekly swap meet.')}

HOW YOU TALK:
- You are on a live PHONE CALL. Keep every reply under 35 words. One idea per turn.
- Sound human: contractions, small acknowledgements ("got it", "makes sense"), never robotic.
- {language_rule}
- Ask at most ONE question per turn, and only if it moves the sale forward.
- Never read a script, never list bullet points, never say you are an AI unless asked directly.
- If they object, acknowledge it in a few words, answer honestly, then continue.
- If they are not interested or ask you to stop calling, be gracious and close immediately.
- Never invent stock, prices or discounts beyond what is listed above.

CURRENT STAGE: {stage} - {STAGE_GUIDE.get(stage, '')}

WHAT YOU ALREADY KNOW ABOUT THIS CUSTOMER (never ask about these again):
{json.dumps(known, ensure_ascii=False) if known else "nothing yet"}

Reply with ONLY what you say next on the call. No stage directions, no quotes, no labels."""


EXTRACTION_SYSTEM = """You extract structured data from one customer utterance in an Indian thrift-store sales call.
The customer may speak English, Hindi, or Hinglish (code-switched).
Return ONLY a JSON object. No prose, no markdown.

Schema:
{
  "language": "english|hindi|hinglish",
  "intent": "buy_thrift_clothes|sell_clothes|swap_clothes|donate_clothes|request_catalog|request_store_visit|request_callback|learn_more|just_browsing|not_interested|do_not_call|objection|question|greeting|other",
  "budget": {"amount": number or null, "currency": "INR", "qualifier": "under|around|above|null"},
  "product_categories": ["jacket", "jeans", ...],
  "brands": [...],
  "size": string or null,
  "gender_preference": "men|women|unisex|null",
  "urgency": "today|this_week|this_month|later|exploring|unknown",
  "location": string or null,
  "barriers": ["budget_concern","trust_concern","hygiene_concern","needs_permission","no_time","wants_to_see_inventory","return_concern"],
  "customer_name": string or null,
  "sentiment": "positive|neutral|negative",
  "buying_intent": 0.0 to 1.0,
  "requires_whatsapp": boolean,
  "requires_callback": boolean,
  "callback_time_text": string or null,
  "wants_to_end_call": boolean,
  "do_not_call": boolean
}"""

EXTRACTION_FEWSHOT: List[Dict[str, str]] = [
    {
        "role": "user",
        "content": "Customer said: \"Budget around 1000 hai but mujhe branded jackets chahiye, is week chahiye\"",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "language": "hinglish",
                "intent": "buy_thrift_clothes",
                "budget": {"amount": 1000, "currency": "INR", "qualifier": "around"},
                "product_categories": ["jacket"],
                "brands": [],
                "size": None,
                "gender_preference": None,
                "urgency": "this_week",
                "location": None,
                "barriers": [],
                "customer_name": None,
                "sentiment": "positive",
                "buying_intent": 0.85,
                "requires_whatsapp": False,
                "requires_callback": False,
                "callback_time_text": None,
                "wants_to_end_call": False,
                "do_not_call": False,
            }
        ),
    },
    {
        "role": "user",
        "content": "Customer said: \"Achha idea hai par pehle main apni wardrobe check karungi. Kal shaam call karna.\"",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "language": "hinglish",
                "intent": "request_callback",
                "budget": {"amount": None, "currency": "INR", "qualifier": None},
                "product_categories": [],
                "brands": [],
                "size": None,
                "gender_preference": None,
                "urgency": "later",
                "location": None,
                "barriers": ["wants_to_see_inventory"],
                "customer_name": None,
                "sentiment": "positive",
                "buying_intent": 0.45,
                "requires_whatsapp": False,
                "requires_callback": True,
                "callback_time_text": "kal shaam",
                "wants_to_end_call": False,
                "do_not_call": False,
            }
        ),
    },
    {
        "role": "user",
        "content": "Customer said: \"No I was just curious what you people do. Not looking for anything.\"",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "language": "english",
                "intent": "just_browsing",
                "budget": {"amount": None, "currency": "INR", "qualifier": None},
                "product_categories": [],
                "brands": [],
                "size": None,
                "gender_preference": None,
                "urgency": "exploring",
                "location": None,
                "barriers": [],
                "customer_name": None,
                "sentiment": "neutral",
                "buying_intent": 0.1,
                "requires_whatsapp": False,
                "requires_callback": False,
                "callback_time_text": None,
                "wants_to_end_call": True,
                "do_not_call": False,
            }
        ),
    },
]

CLASSIFY_SYSTEM = """You are a sales lead classifier for a thrift-clothing store in India.
Given the conversation so far, classify the lead as HOT, WARM or COLD.

HOT  = wants to buy/sell/swap now, has budget or specific items, asks for catalogue or a visit.
WARM = genuinely interested but blocked: needs to check something, wants a callback, budget concern.
COLD = just browsing, no need, or not interested.

Return ONLY JSON: {"label": "HOT|WARM|COLD", "confidence": 0.0-1.0, "reason": "one short sentence"}"""

SUMMARY_SYSTEM = """Summarise this thrift-store sales call in 2 short sentences for a CRM.
Mention what the customer wants, their budget/timeline if known, and the agreed next step.
Return plain text only."""
