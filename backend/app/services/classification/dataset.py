"""Synthetic training-data generator for the lead classifier.

Real call recordings are the ideal training set, but you cannot start there.
This generator produces realistic Indian thrift-store utterances across English,
Hindi and Hinglish - including code-switching, indirect intent, budget
objections and vague answers - which is enough to train a strong first model
and to bootstrap labelling of real calls later.
"""
import random
from typing import Dict, List

ITEMS_EN = ["jackets", "hoodies", "jeans", "t-shirts", "kurtis", "dresses", "sweaters", "blazers", "sneakers", "party wear"]
ITEMS_HI = ["jacket", "hoodie", "jeans", "kurti", "shirt", "sweater", "blazer", "saree", "jute", "winter wear"]
BRANDS = ["Zara", "H&M", "Levis", "Nike", "Adidas", "Puma", "Uniqlo", "Biba", "Roadster", "Wrogn"]
BUDGETS = [300, 500, 700, 800, 1000, 1200, 1500, 2000, 2500]
SOON_EN = ["today", "this week", "by the weekend", "in the next two days", "as soon as possible"]
SOON_HI = ["aaj", "is hafte", "weekend tak", "do din mein", "jaldi"]
LATER_EN = ["next month", "after some time", "maybe later", "in a few weeks", "after Diwali"]
LATER_HI = ["agle mahine", "baad mein", "kuch time baad", "kuch hafte baad"]
SIZES = ["S", "M", "L", "XL", "32", "34"]

# --------------------------------------------------------------------------
# HOT - ready to transact now
# --------------------------------------------------------------------------
HOT_TEMPLATES = [
    "I need some {item} and my budget is around {budget}, I want them {soon}.",
    "Can you send me the {item} available under {budget}?",
    "Send me the catalog on WhatsApp, I'm looking for {brand} {item}.",
    "Do you have {brand} {item} in size {size}? I want to buy {soon}.",
    "I want to buy {item} {soon}. What do you have under {budget}?",
    "Share the collection link, I'll pick a few {item} today itself.",
    "How soon can I get these {item}? I need them {soon}.",
    "I'd like to visit the store {soon}. What's the address?",
    "Book me for the swap event, I have around ten pieces to swap.",
    "Please WhatsApp me photos of {item}, budget is {budget} max.",
    "Yes I'm interested, send the list. I need {item} for {budget} or less.",
    "Mujhe {item} chahiye {budget} ke andar, {soon_hi} chahiye.",
    "{item} bhej do WhatsApp pe, budget {budget} hai.",
    "Budget around {budget} hai but mujhe branded {item} chahiye.",
    "{brand} ke {item} hain kya? {soon_hi} chahiye mujhe.",
    "Haan mujhe lena hai, catalogue bhej dijiye abhi.",
    "Kitne ka milega {item}? {soon_hi} chahiye, order kar dunga.",
    "Store ka address bhej do, main {soon_hi} aa jaunga.",
    "Main aaj hi kharidna chahta hoon, list share karo.",
    "Size {size} mein {item} available hai? Payment aaj kar dunga.",
    "मुझे {item} चाहिए, बजट {budget} है, इसी हफ्ते चाहिए।",
    "कैटलॉग व्हाट्सएप पर भेज दीजिए, मैं आज ही ऑर्डर करूंगा।",
    "Swap event mein aana hai mujhe, kaise register karun?",
    "I have clothes to sell, please arrange pickup this week.",
    "Mere paas {brand} ke kapde hain bechne ke liye, {soon_hi} pickup kara do.",
    "Pickup kab ho sakta hai? Main {soon_hi} free hoon.",
    "Perfect, I'll take it. Send me the payment link.",
    "Ye to badhiya deal hai, abhi book kar do mere liye.",
    "Kal aa raha hoon store pe, timing bata dijiye.",
    "I want two {item} and one {item}, total budget {budget}.",
]

# --------------------------------------------------------------------------
# WARM - interested but blocked
# --------------------------------------------------------------------------
WARM_TEMPLATES = [
    "I'm interested but maybe {later}.",
    "Sounds good, but I need to check my wardrobe first.",
    "Let me think about it and get back to you.",
    "Can you call me {later}? I'm driving right now.",
    "I like the idea but I have to ask my wife before deciding.",
    "Send me some details, I'll look at them when I get time.",
    "Maybe, but {budget} is a bit much for me right now.",
    "I'm interested in swapping but I need to sort my clothes first.",
    "Call me tomorrow morning, I'll have a better idea then.",
    "Not right now, but definitely {later}.",
    "I need to see what you have before I decide anything.",
    "Depends on what you have. Can you show me some options?",
    "I'll check with my sister and let you know.",
    "Right now I'm busy, call me after 6.",
    "Interesting, but I usually buy new clothes. Let me think.",
    "Idea achha hai par pehle main apni wardrobe check karungi.",
    "{later_hi} dekhte hain, abhi budget nahi hai.",
    "Abhi busy hoon, {later_hi} call karna.",
    "Ghar mein puchhna padega, phir batati hoon.",
    "Thoda sochna padega, aap details bhej dijiye.",
    "{budget} thoda zyada hai, kuch sasta ho to batao.",
    "Kal shaam call kar lena, tab detail mein baat karte hain.",
    "Pehle photos dekhni padengi, phir decide karungi.",
    "Interested to hoon par abhi paise nahi hain.",
    "Swap karna hai par pehle dekhna padega kya kya de sakta hoon.",
    "Mujhe soch kar batana padega, thoda time dijiye.",
    "अभी नहीं, अगले महीने देखते हैं।",
    "मुझे पहले घर में पूछना पड़ेगा, फिर बताती हूँ।",
    "Abhi to nahi le sakta, par {later_hi} zaroor.",
    "Aap WhatsApp pe bhej do, main fursat mein dekh lunga.",
    "Sunday ko free hoon, tab baat karte hain.",
]

# --------------------------------------------------------------------------
# COLD - no need, no interest, opt-out
# --------------------------------------------------------------------------
COLD_TEMPLATES = [
    "No, I was just checking what you do.",
    "I'm not looking for anything right now.",
    "Not interested, thanks.",
    "I don't buy second-hand clothes.",
    "Sorry, wrong number.",
    "I was just curious about the concept, that's all.",
    "No thanks, I have enough clothes.",
    "Please don't call me again.",
    "Remove my number from your list.",
    "How did you get my number? Don't call me.",
    "I'm not interested in this at all.",
    "No need, I already shop somewhere else.",
    "Just browsing, nothing specific.",
    "Not really my thing, thank you.",
    "I don't have time for this.",
    "Nahi bhai, mujhe kuch nahi chahiye.",
    "Bas aise hi puch raha tha, kuch lena nahi hai.",
    "Interest nahi hai, thank you.",
    "Purane kapde nahi lete hum.",
    "Abhi koi zaroorat nahi hai.",
    "Call mat kijiye dobara, please.",
    "Mera number list se hata dijiye.",
    "Nahi nahi, mujhe nahi chahiye kuch bhi.",
    "Time nahi hai mere paas, rakhta hoon.",
    "Galat number lag gaya aapka.",
    "मुझे कुछ नहीं चाहिए, धन्यवाद।",
    "दोबारा फ़ोन मत कीजिए।",
    "Bas jaanna tha ki aap log karte kya ho.",
    "Sirf dekh raha tha, kharidna nahi hai.",
    "Hum second hand nahi lete, sorry.",
]

LABEL_TEMPLATES: Dict[str, List[str]] = {
    "HOT": HOT_TEMPLATES,
    "WARM": WARM_TEMPLATES,
    "COLD": COLD_TEMPLATES,
}


def _fill(template: str, rng: random.Random) -> str:
    # Hinglish/Hindi templates read better with singular Hindi item words.
    pool = ITEMS_EN if template.isascii() and not any(w in template for w in ("chahiye", "hai", "do ", "karo")) else ITEMS_HI
    return template.format(
        item=rng.choice(pool),
        brand=rng.choice(BRANDS),
        budget=rng.choice(BUDGETS),
        size=rng.choice(SIZES),
        soon=rng.choice(SOON_EN),
        soon_hi=rng.choice(SOON_HI),
        later=rng.choice(LATER_EN),
        later_hi=rng.choice(LATER_HI),
    )


def _language_of(text: str) -> str:
    from app.utils.text import detect_language

    return detect_language(text)


def generate_dataset(samples_per_label: int = 180, seed: int = 42) -> List[Dict[str, str]]:
    """Return a shuffled, de-duplicated list of {utterance, label, language}."""
    rng = random.Random(seed)
    rows: List[Dict[str, str]] = []

    for label, templates in LABEL_TEMPLATES.items():
        seen = set()
        attempts = 0
        while len(seen) < samples_per_label and attempts < samples_per_label * 40:
            attempts += 1
            index = rng.randrange(len(templates))
            text = _augment(_fill(templates[index], rng), rng)
            if text in seen:
                continue
            seen.add(text)
            rows.append(
                {
                    "utterance": text,
                    "label": label,
                    "language": _language_of(text),
                    # Recorded so evaluation can hold out whole templates and
                    # avoid the leakage that makes synthetic data look perfect.
                    "template_id": f"{label}:{index}",
                }
            )

    rng.shuffle(rows)
    return rows


FILLERS_EN = ["Hmm, ", "Okay so ", "Actually ", "See, ", "Listen, ", ""]
FILLERS_HI = ["Haan ", "Achha ", "Dekhiye ", "Arre ", "Ji ", ""]
TAILS = [" thanks.", " ok?", "", "", "", " please."]


def _augment(text: str, rng: random.Random) -> str:
    """Light noise so the model does not memorise template prefixes."""
    roll = rng.random()
    if roll < 0.22:
        prefix = rng.choice(FILLERS_HI if not text.isascii() or rng.random() < 0.5 else FILLERS_EN)
        text = prefix + text[0].lower() + text[1:] if prefix else text
    if rng.random() < 0.15:
        text = text + rng.choice(TAILS)
    if rng.random() < 0.08:
        text = text.lower()
    return text.strip()


def dataset_stats(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, int]]:
    labels: Dict[str, int] = {}
    languages: Dict[str, int] = {}
    for row in rows:
        labels[row["label"]] = labels.get(row["label"], 0) + 1
        languages[row["language"]] = languages.get(row["language"], 0) + 1
    return {"by_label": labels, "by_language": languages, "total": {"rows": len(rows)}}
