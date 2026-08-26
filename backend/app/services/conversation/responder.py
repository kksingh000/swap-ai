"""Deterministic natural-language generation.

This is the fallback that runs when no LLM is configured - and the safety net
when the LLM errors mid-call. It is a conversation state machine with several
phrasings per slot in English / Hindi / Hinglish, so it never sounds like the
same recording twice.
"""
import random
import re
from typing import Any, Dict, List, Optional

from app.schemas.nlu import CustomerMemory, TurnExtraction
from app.utils.text import first_name

Lang = str


def _pick(options: Dict[Lang, List[str]], lang: Lang, **fmt: Any) -> str:
    bucket = options.get(lang) or options.get("english") or [""]
    return random.choice(bucket).format(**fmt)


STOP_TOKENS = {"aapko", "aapke", "chahiye", "karna", "kaise", "hain", "what", "which", "your", "you"}


def _repeats(existing: List[str], candidate: str) -> bool:
    """True if the candidate line re-treads content we already said this turn."""
    said = set(re.findall(r"[a-z]{5,}", " ".join(existing).lower())) - STOP_TOKENS
    new = set(re.findall(r"[a-z]{5,}", candidate.lower())) - STOP_TOKENS
    return len(said & new) >= 2


ACK = {
    "english": ["Got it.", "Perfect.", "Nice.", "Sure.", "Makes sense."],
    "hinglish": ["Got it.", "Perfect.", "Achha theek hai.", "Sahi hai.", "Bilkul."],
    "hindi": ["Theek hai.", "Bahut badhiya.", "Samajh gaya.", "Ji bilkul."],
}

OPENING = {
    "english": [
        "Hi {name}, this is {agent} from {store}. Is this a good time to talk for a minute?",
        "Hello {name}! {agent} here from {store}. Do you have a quick minute?",
    ],
    "hinglish": [
        "Hi {name}, main {agent} from {store}. Ek minute baat kar sakte hain?",
        "Hello {name}! {agent} bol rahi hoon {store} se. Abhi baat karne ka time hai?",
    ],
    "hindi": [
        "Namaste {name} ji, main {agent} {store} se bol rahi hoon. Kya abhi ek minute baat kar sakte hain?",
    ],
}

PITCH = {
    "english": [
        "We're a thrift and clothing-swap platform in {location} - you can buy quality pre-owned clothes, sell what you don't wear, or swap them. Which of those sounds useful to you?",
        "{store} helps you refresh your wardrobe affordably: buy pre-owned pieces, sell yours, or swap at our weekly meet. What would interest you more?",
    ],
    "hinglish": [
        "Hum {location} mein thrift aur clothing-swap platform hain - aap quality pre-owned clothes buy kar sakte ho, apne purane kapde sell kar sakte ho, ya swap kar sakte ho. Inme se kya interesting lagta hai?",
        "{store} pe aap sasti branded pre-owned clothes le sakte ho, apne kapde bech sakte ho ya swap kar sakte ho. Aapke liye kya useful rahega?",
    ],
    "hindi": [
        "Hum {location} mein ek thrift aur kapde swap karne ka platform hain. Aap achhe pre-owned kapde kharid sakte hain, apne kapde bech sakte hain, ya badal sakte hain. Aapko kya theek lagega?",
    ],
}

ASK_CATEGORY = {
    "english": [
        "What kind of pieces are you usually after - jackets, denim, ethnic, or everyday wear?",
        "What are you mostly looking for? Jackets and denim move fastest with us.",
    ],
    "hinglish": [
        "Aap kis type ke pieces dhoondh rahe ho - jackets, denim, ethnic ya casual wear?",
        "Kya chahiye mostly? Jackets aur denim sabse jaldi jaate hain humare paas.",
    ],
    "hindi": [
        "Aap kis tarah ke kapde dhoondh rahe hain - jacket, jeans, ethnic ya rozmarra ke?",
    ],
}

ASK_BUDGET = {
    "english": [
        "Do you have a rough budget in mind for {item}?",
        "What sort of budget were you thinking for {item}?",
    ],
    "hinglish": [
        "{item} ke liye koi rough budget socha hai?",
        "{item} ke liye budget kitna rakhoge approx?",
    ],
    "hindi": ["{item} ke liye aapka budget kitna hai lagbhag?"],
}

ASK_TIMELINE = {
    "english": [
        "And how soon do you need it - this week, or are you planning ahead?",
        "Are you looking to pick something up soon, or just planning?",
    ],
    "hinglish": [
        "Aur kab tak chahiye - is hafte ya abhi plan kar rahe ho?",
        "Jaldi chahiye ya abhi bas dekh rahe ho?",
    ],
    "hindi": ["Aapko kab tak chahiye - is hafte ya abhi dekh rahe hain?"],
}

ASK_SIZE = {
    "english": ["What size do you usually wear? I'll filter the list for you."],
    "hinglish": ["Aapki size kya rehti hai? Main list filter kar deti hoon."],
    "hindi": ["Aap kaunsa size pehente hain? Main list chhaant deti hoon."],
}

ASK_SELL_DETAILS = {
    "english": [
        "Nice - what kind of pieces are you looking to sell, and roughly how many?",
        "Great. Which brands are they, and are they in wearable condition?",
    ],
    "hinglish": [
        "Badhiya - kis type ke kapde bechne hain aur approx kitne pieces hain?",
        "Achha, kaunse brands hain aur condition kaisi hai?",
    ],
    "hindi": ["Achha, kis tarah ke kapde bechne hain aur kitne hain lagbhag?"],
}

ASK_SWAP_DETAILS = {
    "english": [
        "Our swap meet runs {swap_event}. What kind of clothes would you bring to swap?",
    ],
    "hinglish": [
        "Humara swap meet hota hai {swap_event}. Aap kya swap karna chahoge?",
    ],
    "hindi": ["Humara swap {swap_event} hota hai. Aap kaunse kapde swap karna chahenge?"],
}

WHATSAPP_SENT = {
    "english": [
        "Done - I've just sent our current collection to your WhatsApp. Have a look and tell me which ones you like.",
        "Sent it on WhatsApp just now. Check it whenever you get a moment and ping me your favourites.",
    ],
    "hinglish": [
        "Ho gaya - abhi WhatsApp pe collection bhej diya hai. Dekh ke bata dena kaunse pasand aaye.",
        "WhatsApp pe abhi share kar diya. Dekh lena aur jo pasand aaye wo bata dena.",
    ],
    "hindi": [
        "Maine abhi WhatsApp par collection bhej diya hai. Dekh kar bataiyega kaunse pasand aaye.",
    ],
}

WHATSAPP_ALREADY_SENT = {
    "english": [
        "I've already sent it across on WhatsApp - it should be sitting in your chat now.",
        "It's already on your WhatsApp, sent it a moment ago.",
    ],
    "hinglish": [
        "Wo maine abhi WhatsApp pe bhej diya hai, chat mein aa gaya hoga.",
        "Already bhej diya hai WhatsApp pe, check kar lijiye.",
    ],
    "hindi": ["Wo maine abhi WhatsApp par bhej diya hai, dekh lijiyega."],
}

NEXT_STEP = {
    "english": [
        "Anything specific you'd like me to hold for you?",
        "Shall I keep a couple of these aside for you?",
        "Anything else I can look up for you while we're on the call?",
    ],
    "hinglish": [
        "Koi specific piece hold kar doon aapke liye?",
        "Do-teen pieces alag rakh doon aapke liye?",
        "Aur kuch dekh doon aapke liye?",
    ],
    "hindi": [
        "Koi khaas cheez aapke liye rakh doon?",
        "Aur kuch dekhna chahenge aap?",
    ],
}

CALLBACK_CONFIRMED = {
    "english": ["Perfect, I'll call you back {when}. Thanks for your time!"],
    "hinglish": ["Perfect, main aapko {when} call kar lungi. Thank you!"],
    "hindi": ["Theek hai, main aapko {when} phone karungi. Dhanyavaad!"],
}

VISIT = {
    "english": [
        "Lovely - we're in Hauz Khas, Delhi, open till 8pm. I'll WhatsApp you the location pin.",
    ],
    "hinglish": [
        "Badhiya - hum Hauz Khas, Delhi mein hain, 8 baje tak open. Location WhatsApp kar deti hoon.",
    ],
    "hindi": ["Hum Hauz Khas, Delhi mein hain, raat 8 baje tak khula hai. Location bhej deti hoon."],
}

COLD_CLOSE = {
    "english": [
        "No problem at all - thanks for hearing me out. Whenever you feel like refreshing your wardrobe, we're here!",
    ],
    "hinglish": [
        "Koi baat nahi - sunne ke liye thank you. Jab bhi wardrobe refresh karna ho, hum yahin hain!",
    ],
    "hindi": ["Koi baat nahi, sunne ke liye dhanyavaad. Jab bhi zaroorat ho, hum yahan hain!"],
}

DNC_CLOSE = {
    "english": [
        "Understood, I'm sorry for the disturbance. I've removed your number from our list - you won't get another call. Have a good day.",
    ],
    "hinglish": [
        "Bilkul samajh gayi, disturb karne ke liye sorry. Aapka number list se hata diya hai, dobara call nahi aayega. Good day!",
    ],
    "hindi": [
        "Ji samajh gayi, pareshan karne ke liye maafi. Aapka number hata diya gaya hai, dobara call nahi karenge.",
    ],
}

CLOSING = {
    "english": ["Great talking to you, {name}. Have a lovely day!"],
    "hinglish": ["Baat karke achha laga {name}. Have a great day!"],
    "hindi": ["Aapse baat karke achha laga {name} ji. Aapka din shubh ho!"],
}

BARRIER_REPLIES = {
    "budget_concern": {
        "english": [
            "Totally fair - most of our pieces sit between 249 and 999, so there's plenty under a tight budget.",
        ],
        "hinglish": [
            "Bilkul samajh sakti hoon - humare zyada tar pieces 249 se 999 ke beech hote hain, to budget mein mil jayega.",
        ],
        "hindi": ["Samajh sakti hoon - zyadatar kapde 249 se 999 ke beech hain, budget mein aa jayega."],
    },
    "trust_concern": {
        "english": [
            "Fair question - we're a registered store in Hauz Khas with 2,000+ customers. I can WhatsApp you our page and reviews right now.",
        ],
        "hinglish": [
            "Sahi sawaal hai - hum Hauz Khas mein registered store hain, 2000+ customers ke saath. Main abhi page aur reviews WhatsApp kar deti hoon.",
        ],
        "hindi": ["Sahi sawaal hai - hum Hauz Khas mein registered store hain. Main reviews bhej deti hoon."],
    },
    "hygiene_concern": {
        "english": [
            "Every piece is professionally dry-cleaned and steam-sanitised, and we grade condition A, B or C before listing.",
        ],
        "hinglish": [
            "Har piece professionally dry-clean aur steam-sanitise hota hai, aur condition A, B, C grade karke hi list karte hain.",
        ],
        "hindi": ["Har kapda dry-clean aur sanitise hota hai, aur condition grade karke hi list karte hain."],
    },
    "needs_permission": {
        "english": ["Of course, take your time to check. Should I send the collection so you can show them?"],
        "hinglish": ["Bilkul, aaram se puch lijiye. Collection bhej doon taaki aap dikha sako?"],
        "hindi": ["Bilkul, aaram se puch lijiye. Kya main collection bhej doon?"],
    },
    "no_time": {
        "english": ["No worries at all - when would be a better time to call you back?"],
        "hinglish": ["Koi baat nahi - kab call karun jo aapke liye theek rahe?"],
        "hindi": ["Koi baat nahi - kis samay call karun aapko?"],
    },
    "wants_to_see_inventory": {
        "english": ["Makes sense - let me WhatsApp you the current collection so you can see it yourself."],
        "hinglish": ["Sahi hai - main current collection WhatsApp kar deti hoon, khud dekh lijiye."],
        "hindi": ["Theek hai - main abhi collection WhatsApp par bhej deti hoon."],
    },
    "return_concern": {
        "english": ["You get a 7-day no-questions return window, and pickup is free in Delhi NCR."],
        "hinglish": ["7 din ka no-questions return milta hai, aur Delhi NCR mein pickup free hai."],
        "hindi": ["7 din ka return milta hai aur Delhi NCR mein pickup free hai."],
    },
}


def _install_indic_banks() -> None:
    """Merge the Telugu and Kannada banks into the dictionaries above.

    They live in their own module so this file stays readable rather than
    carrying five languages inline for every single prompt.
    """
    from app.services.conversation.responder_indic import BANKS

    for language, banks in BANKS.items():
        for name, value in banks.items():
            target = globals().get(name)
            if not isinstance(target, dict):
                continue
            if name == "BARRIER_REPLIES":
                for barrier, lines in value.items():
                    target.setdefault(barrier, {})[language] = lines
            else:
                target[language] = value


_install_indic_banks()


class TemplateResponder:
    """Generates the agent's next line without any model."""

    def __init__(self, profile: Dict[str, Any]) -> None:
        self.profile = profile

    # -- public API ---------------------------------------------------------

    def opening(self, customer_name: Optional[str], language: str = "english") -> str:
        name = first_name(customer_name or "") or ("ji" if language == "hindi" else "there")
        line = _pick(
            OPENING,
            language,
            name=name,
            agent=self.profile.get("agent_name", "Ananya"),
            store=self.profile.get("store_name", "SwapCircle"),
        )
        pitch = _pick(
            PITCH,
            language,
            store=self.profile.get("store_name", "SwapCircle"),
            location=self.profile.get("location", "Delhi NCR"),
        )
        return f"{line} {pitch}"

    def reply(
        self,
        memory: CustomerMemory,
        turn: TurnExtraction,
        stage: str,
        faq_answer: Optional[str] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
        already_done: Optional[List[str]] = None,
        last_agent_line: str = "",
    ) -> str:
        lang = memory.language if memory.language in ACK else "english"
        actions = actions or []
        already_done = already_done or []
        action_types = {a.get("action_type") for a in actions}

        # 1. Hard exits first.
        if turn.do_not_call:
            return _pick(DNC_CLOSE, lang)
        if turn.intent == "not_interested":
            return _pick(COLD_CLOSE, lang)

        parts: List[str] = []

        # 2. Anything we just DID gets narrated, because the customer asked for it.
        if "send_whatsapp" in action_types:
            parts.append(_pick(WHATSAPP_SENT, lang))
        elif turn.requires_whatsapp and "send_whatsapp" in already_done:
            # They asked again for something we already sent - say so, don't re-send.
            parts.append(_pick(WHATSAPP_ALREADY_SENT, lang))
        if "schedule_callback" in action_types:
            when = next(
                (a.get("result", {}).get("human_time") for a in actions if a.get("action_type") == "schedule_callback"),
                None,
            )
            parts.append(_pick(CALLBACK_CONFIRMED, lang, when=when or "soon"))
            return " ".join(parts)

        # 3. Objections and questions get answered before we push forward.
        if turn.barriers:
            barrier = turn.barriers[0]
            if barrier in BARRIER_REPLIES and "send_whatsapp" not in action_types:
                parts.append(_pick(BARRIER_REPLIES[barrier], lang))
        elif faq_answer and turn.asked_question:
            parts.append(faq_answer)
        elif not parts:
            parts.append(_pick(ACK, lang))

        # 4. Then the single next question that moves the sale forward.
        follow_up = self._next_question(
            memory, turn, stage, lang, action_types, answered_faq=bool(faq_answer)
        )

        # Asking the identical question two turns running is the clearest tell
        # that there is a machine on the line, so fall through to alternatives.
        said_before = parts + ([last_agent_line] if last_agent_line else [])
        candidates = [
            follow_up,
            _pick(NEXT_STEP, lang),
            _pick(ASK_SIZE, lang) if not memory.size else None,
            _pick(ASK_CATEGORY, lang) if not memory.clothing_categories else None,
        ]
        follow_up = next(
            (c for c in candidates if c and not _repeats(said_before, c)),
            None if stage not in ("action", "qualification") else _pick(NEXT_STEP, lang),
        )
        if follow_up:
            parts.append(follow_up)

        text = " ".join(p for p in parts if p).strip()
        return text or _pick(ACK, lang)

    def closing(self, memory: CustomerMemory) -> str:
        lang = memory.language if memory.language in CLOSING else "english"
        return _pick(CLOSING, lang, name=first_name(memory.customer_name or "") or "")

    # -- internals ----------------------------------------------------------

    def _next_question(
        self,
        memory: CustomerMemory,
        turn: TurnExtraction,
        stage: str,
        lang: str,
        action_types: set,
        answered_faq: bool = False,
    ) -> Optional[str]:
        # If we just answered a store-info question, don't follow it with another
        # blurb of store info - move to a slot question instead.
        if not answered_faq:
            topical = self._topical_question(memory, turn, stage, lang)
            if topical:
                return topical
        return self._slot_question(memory, lang, action_types)

    def _topical_question(
        self, memory: CustomerMemory, turn: TurnExtraction, stage: str, lang: str
    ) -> Optional[str]:
        if turn.intent == "request_store_visit" or "request_store_visit" in memory.intent:
            if "visit" not in memory.features_requested:
                return _pick(VISIT, lang)

        if "sell_clothes" in memory.intent and not memory.brands and not memory.clothing_categories:
            return _pick(ASK_SELL_DETAILS, lang)

        if "swap_clothes" in memory.intent and not memory.clothing_categories:
            return _pick(
                ASK_SWAP_DETAILS, lang, swap_event=self.profile.get("swap_event", "every Saturday")
            )

        if stage in ("opening", "discovery") and not memory.intent:
            return _pick(ASK_CATEGORY, lang)
        return None

    def _slot_question(self, memory: CustomerMemory, lang: str, action_types: set) -> Optional[str]:
        if not memory.clothing_categories:
            return _pick(ASK_CATEGORY, lang)

        item = memory.clothing_categories[0] if memory.clothing_categories else "that"
        if not memory.budget:
            return _pick(ASK_BUDGET, lang, item=item)
        if not memory.timeline:
            return _pick(ASK_TIMELINE, lang)
        if not memory.size and "send_whatsapp" not in action_types:
            return _pick(ASK_SIZE, lang)
        return None
