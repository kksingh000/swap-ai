"""Deterministic NLU for Indian thrift-store phone conversations.

This is what makes the project work with **no LLM at all**, and it also acts as
a safety net when the LLM hallucinates: whatever the model says, these regexes
are the ground truth for money, dates and opt-outs.

Everything is tuned for English + Hindi + Hinglish code-switching.
"""
import re
from typing import Dict, List, Optional, Tuple

from app.schemas.nlu import BudgetInfo, TurnExtraction
from app.utils.text import detect_language, normalize

# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

CATEGORY_PATTERNS: Dict[str, List[str]] = {
    "jacket": ["jacket", "jackets", "jaket", "जैकेट"],
    "hoodie": ["hoodie", "hoodies", "sweatshirt", "हूडी"],
    "jeans": ["jeans", "denim", "jean", "जींस"],
    "shirt": ["shirt", "shirts", "formal shirt", "शर्ट"],
    "tshirt": ["t-shirt", "tshirt", "t shirt", "tee", "tees", "टीशर्ट"],
    "kurta": ["kurta", "kurti", "kurtas", "kurtis", "कुर्ता", "कुर्ती"],
    "saree": ["saree", "sari", "sarees", "साड़ी"],
    "dress": ["dress", "dresses", "gown", "frock", "ड्रेस"],
    "top": ["top", "tops", "crop top", "टॉप"],
    "trousers": ["trouser", "trousers", "pants", "chinos", "cargo"],
    "sweater": ["sweater", "pullover", "cardigan", "स्वेटर"],
    "blazer": ["blazer", "coat", "suit", "ब्लेज़र"],
    "ethnic": ["ethnic", "lehenga", "sherwani", "salwar", "suit piece", "एथनिक"],
    "shoes": ["shoes", "sneakers", "footwear", "juta", "jutti", "जूते"],
    "bags": ["bag", "bags", "handbag", "backpack", "बैग"],
    "winterwear": ["winter", "woolen", "woollen", "thermals", "sardi", "जाड़ा"],
    "partywear": ["party wear", "partywear", "party", "wedding", "shaadi", "shadi"],
}

BRANDS = [
    "zara", "h&m", "hm", "levis", "levi's", "nike", "adidas", "puma", "uniqlo",
    "forever 21", "forever21", "mango", "allen solly", "van heusen", "peter england",
    "ucb", "united colors", "gap", "tommy", "calvin klein", "ck", "biba", "w",
    "fabindia", "global desi", "roadster", "hrx", "wrogn", "bewakoof", "superdry",
    "jack and jones", "vero moda", "only", "decathlon", "reebok", "lee", "wrangler",
]

SIZE_PATTERN = re.compile(
    r"\b(?:size\s*(?:is|:)?\s*)?(xxs|xs|small|medium|large|s|m|l|xl|xxl|xxxl|2xl|3xl|"
    r"28|30|32|34|36|38|40|42|44)\b",
    re.I,
)
SIZE_CONTEXT = re.compile(r"\b(size|saiz|waist|number)\b", re.I)

GENDER_PATTERNS = {
    "men": ["men", "mens", "men's", "male", "boys", "ladka", "gents", "पुरुष"],
    "women": ["women", "womens", "women's", "female", "girls", "ladies", "ladki", "महिला"],
    "unisex": ["unisex", "both", "dono"],
}

# --------------------------------------------------------------------------
# Intent keyword banks (English + Hindi + romanised Hindi)
# --------------------------------------------------------------------------

DNC_PATTERNS = [
    "don't call", "dont call", "do not call", "stop calling", "never call",
    "remove my number", "remove me", "unsubscribe", "take me off",
    "call mat", "mat call", "phone mat", "dobara mat", "dubara mat",
    "band karo", "band kar", "pareshan mat", "मत करो", "फोन मत",
]

NOT_INTERESTED = [
    "not interested", "no interest", "no thanks", "no thank you", "not for me",
    "nahi chahiye", "nai chahiye", "nahin chahiye", "interest nahi", "koi interest",
    "nahi bhai", "no need", "not required", "zarurat nahi", "zaroorat nahi",
    "not looking for", "nothing right now", "nothing at the moment", "im good",
    "i'm good", "leave it", "rehne do", "chhodo",
    "नहीं चाहिए", "रुचि नहीं",
]

JUST_BROWSING = [
    "just checking", "just curious", "just browsing", "just looking", "just asking",
    "only asking", "just wanted to know", "just exploring", "timepass",
    "bas dekh", "dekh raha", "dekh rahi", "puch raha", "puchh raha", "pooch rahi",
    "aise hi", "waise hi", "bas jaanna", "bas janna", "सिर्फ देख",
]

BUY_PATTERNS = [
    "want to buy", "looking for", "need some", "i need", "interested in buying",
    "do you have", "you have", "anything under", "what options", "options under",
    "kya milega", "mil jayega", "chahiye", "chaiye", "lena hai",
    "lenge", "kharid", "buy", "purchase", "order", "shopping", "खरीद", "चाहिए",
]

SELL_PATTERNS = [
    "want to sell", "sell my", "selling", "i have clothes", "bech", "bechna",
    "sell kar", "paise mil", "how much will you pay", "kitna doge", "kitne ka",
    "quote", "pickup my", "बेच",
]

SWAP_PATTERNS = [
    "swap", "exchange", "trade", "badal", "badalna", "exchange kar", "swap kar",
    "अदला", "बदल",
]

DONATE_PATTERNS = ["donate", "donation", "give away", "daan", "de dena", "charity", "दान"]

CATALOG_PATTERNS = [
    "send me", "share the", "share it", "show me", "let me see", "can i see",
    "whatsapp", "catalog", "catalogue",
    "collection", "link", "photos", "pictures", "pics", "images", "list",
    "bhej do", "bhej dena", "bhejo", "bhej dijiye", "send kar", "share kar",
    "dikha do", "dikhao", "भेज", "दिखा",
]

VISIT_PATTERNS = [
    "visit", "come to", "come over", "store", "address", "location", "shop",
    "aa jaunga", "aaunga", "aungi", "aa sakta", "aa sakti", "kahan hai",
    "kahaan", "store aa", "आ जाऊंगा", "पता",
]

CALLBACK_PATTERNS = [
    "call me", "call back", "callback", "ring me", "phone me", "call kar",
    "call karna", "baad me call", "phir call", "kal call", "call kijiye",
    "बाद में", "कॉल कर",
]

URGENT_PATTERNS = {
    "today": ["today", "right now", "immediately", "asap", "abhi", "aaj", "turant", "आज", "अभी"],
    "this_week": [
        "this week", "few days", "couple of days", "by friday", "by sunday",
        "weekend", "is hafte", "hafte", "jaldi", "is week", "इस हफ्ते",
    ],
    "this_month": ["this month", "few weeks", "is mahine", "mahine", "इस महीने"],
    "later": [
        "next month", "later", "after some time", "baad me", "baad mein",
        "agle mahine", "abhi nahi", "not right now", "some other time", "बाद में",
    ],
}

BARRIER_PATTERNS = {
    "budget_concern": [
        "too expensive", "costly", "mehnga", "mehanga", "budget nahi", "no budget",
        "tight budget", "cheaper", "sasta", "kam paise", "महंगा",
    ],
    "trust_concern": [
        "is this genuine", "genuine hai", "scam", "fraud", "fake", "real hai",
        "trust", "bharosa", "sach me", "asli", "verify", "धोखा", "असली",
    ],
    "hygiene_concern": [
        "clean", "hygiene", "hygienic", "washed", "smell", "dirty", "used clothes",
        "someone else", "saaf", "ganda", "gande", "dhula", "सफाई", "गंदा",
    ],
    "needs_permission": [
        "ask my", "check with", "my wife", "my husband", "my mom", "my mother",
        "my dad", "parents", "poochna", "puchna hoga", "ghar me", "pucch ke",
        "पूछ", "घर में",
    ],
    "no_time": [
        "busy", "no time", "in a meeting", "driving", "later please", "abhi busy",
        "time nahi", "kaam", "व्यस्त", "समय नहीं",
    ],
    "wants_to_see_inventory": [
        "see first", "show me first", "what do you have", "dekhna hoga",
        "pehle dekh", "inventory", "stock", "photos dekh",
    ],
    "return_concern": ["return", "refund", "exchange policy", "wapas", "वापस"],
}

QUESTION_MARKERS = [
    "what", "how", "where", "when", "why", "who", "can i", "do you", "is it",
    "are you", "kya", "kaise", "kahan", "kab", "kaun", "kyun", "kitna", "kitne",
    "क्या", "कैसे", "कहाँ",
]

# Word-boundary matched: substring matching turned "WhatsApp" into "what".
QUESTION_RE = re.compile(
    r"(?<![\w])(" + "|".join(re.escape(m) for m in QUESTION_MARKERS) + r")(?![\w])", re.I
)

POSITIVE = [
    "yes", "yeah", "yep", "sure", "great", "nice", "good", "awesome", "perfect",
    "interested", "sounds good", "haan", "han", "ha ji", "ji haan", "bilkul",
    "theek hai", "thik hai", "acha", "accha", "achha", "achcha", "badhiya",
    "sahi", "interesting", "sounds interesting", "हाँ", "अच्छा",
]
NEGATIVE = [
    "no", "not", "don't", "dont", "never", "bad", "waste", "useless", "annoying",
    "busy", "nahi", "nahin", "mat", "bekar", "faltu", "नहीं", "बेकार",
]

END_CALL = [
    "bye", "goodbye", "thank you bye", "have to go", "gotta go", "hang up",
    "rakhta hu", "rakhti hu", "rakhta hoon", "phone rakh", "chalo bye",
    "बाय", "रखता",
]

# --------------------------------------------------------------------------
# Money parsing
# --------------------------------------------------------------------------

_NUM_WORDS = {
    "hazar": 1000, "hazaar": 1000, "hajar": 1000, "thousand": 1000, "k": 1000,
    "sau": 100, "hundred": 100, "lakh": 100000,
}

_MONEY_RE = re.compile(
    r"(?P<qual>under|below|less than|upto|up to|max|maximum|around|about|approx|approximately|"
    r"near|nearly|over|above|more than|minimum|at least|se kam|ke andar|tak|se upar)?"
    r"\s*(?:rs\.?|inr|₹)?\s*"
    # Comma-grouped form must come first, or "1000" would match as "100".
    r"(?P<num>\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
    r"(?P<unit>k\b|hazar|hazaar|hajar|thousand|sau|hundred|lakh)?",
    re.I,
)

_TRAILING_QUAL = re.compile(
    r"(se kam|ke andar|ke under|tak|se upar|se zyada|se jyada|ke aas paas|ke around)", re.I
)

_NON_MONEY_CONTEXT = re.compile(
    r"\b(size|number|phone|call me at|baje|o'?clock|am|pm|year|saal|age|percent|%)\b", re.I
)


def parse_budget(text: str) -> BudgetInfo:
    """Pull a rupee amount out of free text, including Hinglish forms.

    Handles: 'under 500', 'around 1k', '₹1,500', '2 hazar tak', '1000 ke andar'.
    """
    low = normalize(text).lower()
    if not low:
        return BudgetInfo()

    has_money_cue = bool(
        re.search(r"(rs\.?|inr|₹|budget|price|rupee|rupay|rupaye|paise|spend|cost|rate)", low)
    ) or bool(
        re.search(
            r"(under|below|less than|upto|up to|around|about|approx|max|se kam|ke andar|tak|hazar|hazaar|thousand|\bk\b)",
            low,
        )
    )

    best: Optional[Tuple[int, Optional[str]]] = None
    for match in _MONEY_RE.finditer(low):
        raw_num = match.group("num")
        if not raw_num:
            continue
        window = low[max(0, match.start() - 18) : match.end() + 18]
        if _NON_MONEY_CONTEXT.search(window) and not re.search(r"(rs|₹|inr|budget)", window):
            continue

        try:
            value = float(raw_num.replace(",", ""))
        except ValueError:
            continue

        unit = (match.group("unit") or "").strip().lower()
        if unit:
            value *= _NUM_WORDS.get(unit, 1)
        elif value <= 20 and not re.search(r"(rs|₹|inr)", window):
            continue  # bare small numbers are counts, not budgets

        if not has_money_cue and value < 100:
            continue
        if value < 50 or value > 5_000_000:
            continue

        qualifier = (match.group("qual") or "").strip().lower() or None
        if not qualifier:
            tail = low[match.end() : match.end() + 20]
            trailing = _TRAILING_QUAL.search(tail)
            if trailing:
                qualifier = trailing.group(1).lower()

        qualifier = _normalise_qualifier(qualifier)
        candidate = (int(value), qualifier)
        if best is None or candidate[0] > best[0]:
            best = candidate

    if best is None:
        return BudgetInfo()
    return BudgetInfo(amount=best[0], currency="INR", qualifier=best[1])


def _normalise_qualifier(q: Optional[str]) -> Optional[str]:
    if not q:
        return None
    if q in ("under", "below", "less than", "upto", "up to", "max", "maximum", "se kam", "ke andar", "ke under", "tak"):
        return "under"
    if q in ("around", "about", "approx", "approximately", "near", "nearly", "ke aas paas", "ke around"):
        return "around"
    if q in ("over", "above", "more than", "minimum", "at least", "se upar", "se zyada", "se jyada"):
        return "above"
    return None


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def _hits(low: str, patterns: List[str]) -> bool:
    return any(p in low for p in patterns)


def _extract_categories(low: str) -> List[str]:
    found: List[str] = []
    for canonical, variants in CATEGORY_PATTERNS.items():
        if any(v in low for v in variants) and canonical not in found:
            found.append(canonical)
    return found


def _extract_brands(low: str) -> List[str]:
    found: List[str] = []
    for brand in BRANDS:
        if len(brand) <= 2:
            if re.search(rf"\b{re.escape(brand)}\b", low):
                found.append(brand)
        elif brand in low:
            found.append(brand)
    # de-dup near-identical brand spellings
    canonical = {"levi's": "levis", "hm": "h&m", "forever21": "forever 21", "united colors": "ucb", "ck": "calvin klein"}
    return list(dict.fromkeys(canonical.get(b, b) for b in found))


def _extract_size(text: str) -> Optional[str]:
    if not SIZE_CONTEXT.search(text):
        return None
    match = SIZE_PATTERN.search(text)
    return match.group(1).upper() if match else None


def _extract_gender(low: str) -> Optional[str]:
    for gender, variants in GENDER_PATTERNS.items():
        if any(re.search(rf"\b{re.escape(v)}\b", low) for v in variants):
            return gender
    return None


def _extract_urgency(low: str) -> str:
    for timeline, variants in URGENT_PATTERNS.items():
        if _hits(low, variants):
            return timeline
    return "unknown"


def _extract_barriers(low: str) -> List[str]:
    return [name for name, variants in BARRIER_PATTERNS.items() if _hits(low, variants)]


NAME_RE = re.compile(
    r"\b(?:my name is|i am|i'm|this is|myself|naam|mera naam)\s+([A-Za-z][A-Za-z\.']{1,20})",
    re.I,
)

# "I am planning to pick up soon" must not make the customer's name "Planning".
# These are the words that commonly follow "I am" without being a name.
NOT_A_NAME = {
    "planning", "looking", "interested", "calling", "trying", "thinking", "going",
    "buying", "selling", "checking", "asking", "waiting", "working", "driving",
    "speaking", "listening", "wondering", "hoping", "busy", "sorry", "fine",
    "good", "great", "okay", "ok", "sure", "free", "available", "here", "there",
    "just", "not", "still", "really", "actually", "from", "in", "at", "on",
    "a", "an", "the", "so", "very", "too", "quite", "done", "ready", "afraid",
    "glad", "happy", "keen", "curious", "new", "same", "with", "confused",
}


def _valid_name(candidate: str) -> bool:
    token = candidate.strip(".'").lower()
    return len(token) >= 2 and token.isalpha() and token not in NOT_A_NAME


CITY_RE = re.compile(
    r"\b(delhi|new delhi|noida|greater noida|gurgaon|gurugram|ghaziabad|faridabad|"
    r"mumbai|pune|bangalore|bengaluru|hyderabad|chennai|kolkata|jaipur|lucknow|"
    r"chandigarh|indore|ahmedabad|bhopal|patna|dwarka|rohini|saket|hauz khas|"
    r"laxmi nagar|karol bagh|janakpuri|vasant kunj|pitampura)\b",
    re.I,
)


def extract_turn(text: str, agent_asked: Optional[str] = None) -> TurnExtraction:
    """Rule-based understanding of one customer utterance."""
    clean = normalize(text)
    low = clean.lower()

    language = detect_language(clean)
    categories = _extract_categories(low)
    brands = _extract_brands(low)
    budget = parse_budget(clean)
    urgency = _extract_urgency(low)
    barriers = _extract_barriers(low)

    dnc = _hits(low, DNC_PATTERNS)
    not_interested = _hits(low, NOT_INTERESTED)
    browsing = _hits(low, JUST_BROWSING)
    wants_catalog = _hits(low, CATALOG_PATTERNS) and not not_interested
    wants_visit = _hits(low, VISIT_PATTERNS)
    wants_callback = _hits(low, CALLBACK_PATTERNS)
    wants_buy = (
        _hits(low, BUY_PATTERNS)
        or bool(categories and not (browsing or not_interested))
        or bool(budget.amount and not (browsing or not_interested or dnc))
    )
    wants_sell = _hits(low, SELL_PATTERNS)
    wants_swap = _hits(low, SWAP_PATTERNS)
    wants_donate = _hits(low, DONATE_PATTERNS)
    is_question = "?" in clean or bool(QUESTION_RE.search(low))

    # Primary intent, most decisive first.
    if dnc:
        intent = "do_not_call"
    elif not_interested:
        intent = "not_interested"
    elif wants_catalog and (categories or budget.amount or wants_buy):
        intent = "request_catalog"
    elif wants_sell:
        intent = "sell_clothes"
    elif wants_swap:
        intent = "swap_clothes"
    elif wants_donate:
        intent = "donate_clothes"
    elif wants_visit and not browsing:
        intent = "request_store_visit"
    elif wants_buy and not browsing:
        intent = "buy_thrift_clothes"
    elif wants_catalog:
        intent = "request_catalog"
    elif wants_callback:
        intent = "request_callback"
    elif browsing:
        intent = "just_browsing"
    elif barriers:
        intent = "objection"
    elif is_question:
        intent = "question"
    elif _hits(low, POSITIVE):
        intent = "learn_more"
    else:
        intent = "other"

    secondary: List[str] = []
    for flag, name in (
        (wants_buy, "buy_thrift_clothes"),
        (wants_sell, "sell_clothes"),
        (wants_swap, "swap_clothes"),
        (wants_donate, "donate_clothes"),
        (wants_catalog, "request_catalog"),
        (wants_visit, "request_store_visit"),
        (wants_callback, "request_callback"),
    ):
        if flag and name != intent:
            secondary.append(name)

    # Sentiment
    pos_hits = sum(1 for p in POSITIVE if p in low)
    neg_hits = sum(1 for n in NEGATIVE if n in low)
    if dnc or not_interested:
        sentiment = "negative"
    elif pos_hits > neg_hits:
        sentiment = "positive"
    elif neg_hits > pos_hits:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    buying_intent = _buying_intent_score(
        intent=intent,
        has_budget=bool(budget.amount),
        has_category=bool(categories),
        urgency=urgency,
        wants_catalog=wants_catalog,
        wants_visit=wants_visit,
        browsing=browsing,
        not_interested=not_interested or dnc,
    )

    name_match = NAME_RE.search(clean)
    city_match = CITY_RE.search(clean)

    # A disengaged customer has no timeline and is not asking for a callback,
    # even if the words "right now" or "call me" appear in their brush-off.
    disengaged = intent in ("just_browsing", "not_interested", "do_not_call")
    if disengaged:
        urgency = "exploring"
        wants_callback = False
        wants_catalog = False

    return TurnExtraction(
        language=language,
        intent=intent,
        secondary_intents=secondary,
        budget=budget,
        product_categories=categories,
        brands=brands,
        size=_extract_size(clean),
        gender_preference=_extract_gender(low),
        urgency=urgency,
        location=city_match.group(1).title() if city_match else None,
        barriers=barriers,
        customer_name=(
            name_match.group(1).title()
            if name_match and _valid_name(name_match.group(1))
            else None
        ),
        sentiment=sentiment,
        buying_intent=buying_intent,
        requires_whatsapp=wants_catalog,
        requires_callback=wants_callback or (urgency == "later" and not disengaged),
        callback_time_text=clean if wants_callback else None,
        asked_question=clean if is_question else None,
        wants_to_end_call=_hits(low, END_CALL) or not_interested or dnc,
        do_not_call=dnc,
        source="rules",
    )


def _buying_intent_score(
    *,
    intent: str,
    has_budget: bool,
    has_category: bool,
    urgency: str,
    wants_catalog: bool,
    wants_visit: bool,
    browsing: bool,
    not_interested: bool,
) -> float:
    if not_interested:
        return 0.0
    score = 0.15
    if intent in ("buy_thrift_clothes", "request_catalog", "request_store_visit"):
        score += 0.35
    elif intent in ("sell_clothes", "swap_clothes"):
        score += 0.3
    elif intent == "learn_more":
        score += 0.15
    if has_budget:
        score += 0.15
    if has_category:
        score += 0.12
    if urgency in ("today", "this_week"):
        score += 0.15
    elif urgency == "this_month":
        score += 0.05
    if wants_catalog:
        score += 0.1
    if wants_visit:
        score += 0.1
    if browsing:
        score -= 0.35
    return round(max(0.0, min(1.0, score)), 2)
