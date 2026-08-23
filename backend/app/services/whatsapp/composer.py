"""Builds the WhatsApp follow-up from what the customer *actually said*.

Rule: a generic template is only allowed when we genuinely learned nothing.
Every known fact (item, budget, size, timeline, barrier) must show up in the
message, in the customer's own language.
"""
from typing import Any, Dict, List, Optional

from app.schemas.nlu import CustomerMemory
from app.utils.text import first_name

CATEGORY_LABEL = {
    "tshirt": "t-shirts",
    "jeans": "denim",
    "partywear": "party wear",
    "winterwear": "winter wear",
}


def _items_phrase(memory: CustomerMemory) -> str:
    bits: List[str] = []
    if memory.brands:
        bits.append(", ".join(b.title() for b in memory.brands[:3]))
    if memory.clothing_categories:
        cats = [CATEGORY_LABEL.get(c, c + "s" if not c.endswith("s") else c) for c in memory.clothing_categories[:3]]
        bits.append(", ".join(cats))
    return " ".join(bits).strip()


def _budget_phrase(memory: CustomerMemory, lang: str) -> str:
    if not memory.budget:
        return ""
    qualifier = memory.budget_qualifier or "around"
    if lang == "english":
        word = {"under": "under", "around": "around", "above": "above"}.get(qualifier, "around")
        return f"{word} Rs.{memory.budget}"
    word = {"under": "ke andar", "around": "ke aas-paas", "above": "se upar"}.get(qualifier, "ke aas-paas")
    return f"Rs.{memory.budget} {word}"


BARRIER_LINE = {
    "budget_concern": {
        "english": "I've filtered the list to our most affordable pieces.",
        "hinglish": "Maine sabse affordable pieces filter kar diye hain.",
        "hindi": "Maine sabse sasti cheezein chun kar bheji hain.",
    },
    "hygiene_concern": {
        "english": "Every piece is dry-cleaned, steam-sanitised and condition-graded before listing.",
        "hinglish": "Har piece dry-clean, steam-sanitise aur condition-grade hota hai.",
        "hindi": "Har kapda dry-clean aur sanitise karke hi list hota hai.",
    },
    "trust_concern": {
        "english": "Here's our store page and customer reviews so you can check us out.",
        "hinglish": "Ye raha humara store page aur reviews, aap khud dekh lijiye.",
        "hindi": "Ye humara store page aur reviews hain, aap dekh sakte hain.",
    },
    "wants_to_see_inventory": {
        "english": "Here's the full current collection to browse.",
        "hinglish": "Ye poora current collection hai, dekh lijiye.",
        "hindi": "Ye poora collection hai, dekh lijiye.",
    },
    "needs_permission": {
        "english": "Feel free to share this with them before deciding.",
        "hinglish": "Aap ye unhe dikha kar decide kar sakte ho.",
        "hindi": "Aap ye unhe dikha kar faisla kar sakte hain.",
    },
    "return_concern": {
        "english": "Reminder: 7-day returns on everything, free pickup in Delhi NCR.",
        "hinglish": "Yaad rahe: 7 din ka return, Delhi NCR mein free pickup.",
        "hindi": "Yaad rakhiye: 7 din ka return aur free pickup.",
    },
}


def compose(
    memory: CustomerMemory,
    lead_status: str,
    profile: Dict[str, Any],
    callback_human_time: Optional[str] = None,
) -> Dict[str, str]:
    """Return {body, template_kind, media_url}."""
    lang = memory.language if memory.language in ("english", "hindi", "hinglish") else "english"
    name = first_name(memory.customer_name or "")
    store = profile.get("store_name", "SwapCircle")
    catalog = profile.get("catalog_url", "")
    items = _items_phrase(memory)
    budget = _budget_phrase(memory, lang)
    status = (lead_status or "WARM").upper()

    greeting = {
        "english": f"Hey {name}!" if name else "Hey!",
        "hinglish": f"Hi {name}!" if name else "Hi!",
        "hindi": f"Namaste {name} ji!" if name else "Namaste!",
    }[lang]

    opener = {
        "english": "Great speaking with you just now - thanks for your time.",
        "hinglish": "Abhi baat karke achha laga!",
        "hindi": "Abhi baat karke achha laga!",
    }[lang]

    lines: List[str] = [f"{greeting} {opener}".strip()]

    if status == "HOT":
        want = _want_sentence(lang, items, budget, memory)
        if want:
            lines.append(want)
        lines.append(
            {
                "english": f"I've put our current collection here: {catalog}",
                "hinglish": f"Humara current collection yahan hai: {catalog}",
                "hindi": f"Humara collection yahan dekhiye: {catalog}",
            }[lang]
        )
        lines.append(
            {
                "english": "Tell me which pieces you like and I'll hold them for you.",
                "hinglish": "Jo pasand aaye bata dena, main hold kar deti hoon.",
                "hindi": "Jo pasand aaye bataiyega, main rakh dungi.",
            }[lang]
        )
    elif status == "WARM":
        blocker = memory.barriers[0] if memory.barriers else None
        want = _want_sentence(lang, items, budget, memory)
        if want:
            lines.append(want)
        if blocker and blocker in BARRIER_LINE:
            lines.append(BARRIER_LINE[blocker][lang])
        if callback_human_time:
            lines.append(
                {
                    "english": f"As discussed, I'll call you back on {callback_human_time}.",
                    "hinglish": f"Jaisa baat hui, main {callback_human_time} call karungi.",
                    "hindi": f"Jaisa tay hua, main {callback_human_time} phone karungi.",
                }[lang]
            )
        lines.append(
            {
                "english": f"Meanwhile here's the collection: {catalog}",
                "hinglish": f"Tab tak collection dekh lijiye: {catalog}",
                "hindi": f"Tab tak collection dekhiye: {catalog}",
            }[lang]
        )
    else:  # COLD
        lines = [
            {
                "english": f"{greeting} Thanks for hearing me out today.",
                "hinglish": f"{greeting} Aaj sunne ke liye thank you.",
                "hindi": f"{greeting} Aaj sunne ke liye dhanyavaad.",
            }[lang],
            {
                "english": f"Whenever you feel like refreshing your wardrobe affordably, {store} is here: {catalog}",
                "hinglish": f"Jab bhi wardrobe refresh karna ho, {store} yahin hai: {catalog}",
                "hindi": f"Jab bhi zaroorat ho, {store} yahan hai: {catalog}",
            }[lang],
        ]

    body = "\n\n".join(line for line in lines if line)
    return {"body": body, "template_kind": status, "media_url": catalog}


def _want_sentence(lang: str, items: str, budget: str, memory: CustomerMemory) -> str:
    if not (items or budget):
        return ""
    timeline = {
        "today": {"english": "today", "hinglish": "aaj", "hindi": "aaj"},
        "this_week": {"english": "this week", "hinglish": "is hafte", "hindi": "is hafte"},
        "this_month": {"english": "this month", "hinglish": "is mahine", "hindi": "is mahine"},
    }.get(memory.timeline or "", {}).get(lang, "")

    size = f" (size {memory.size})" if memory.size else ""

    if lang == "english":
        parts = ["Based on what you said, you're looking for"]
        parts.append(items or "some pieces")
        if budget:
            parts.append(budget)
        if timeline:
            parts.append(timeline)
        return " ".join(parts).strip() + size + "."
    if lang == "hindi":
        chunk = f"Aapko {items or 'kuch cheezein'}"
        if budget:
            chunk += f" {budget}"
        if timeline:
            chunk += f" {timeline}"
        return chunk + size + " chahiye thi."
    chunk = f"Aapne bola tha ki aapko {items or 'kuch pieces'}"
    if budget:
        chunk += f" {budget}"
    if timeline:
        chunk += f" {timeline}"
    return chunk + size + " chahiye."
