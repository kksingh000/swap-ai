"""Text helpers: language detection for English / Hindi / Hinglish, plus tokenising."""
import re
import unicodedata
from typing import List

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Each major Indian script has its own Unicode block, so the script alone
# identifies the language - except Devanagari, which Hindi and Marathi share.
INDIC_SCRIPTS = [
    ("bengali", re.compile(r"[ঀ-৿]")),
    ("punjabi", re.compile(r"[਀-੿]")),
    ("gujarati", re.compile(r"[઀-૿]")),
    ("odia", re.compile(r"[଀-୿]")),
    ("tamil", re.compile(r"[஀-௿]")),
    ("telugu", re.compile(r"[ఀ-౿]")),
    ("kannada", re.compile(r"[ಀ-೿]")),
    ("malayalam", re.compile(r"[ഀ-ൿ]")),
]

# Hindi and Marathi are both written in Devanagari, so the script cannot
# separate them - these are words that only really appear in Marathi.
MARATHI_MARKERS = {
    "आहे", "आहेत", "मला", "तुम्ही", "तुला", "पाहिजे", "नको", "काय", "कसं",
    "कशी", "कुठे", "छान", "बरं", "होय", "करा", "मी", "आम्ही", "किंवा", "पण",
    "aahe", "ahe", "mala", "tumhi", "pahije", "nako", "kasa", "kase", "kay",
    "barr", "khup", "aamhi", "tula",
}

# Romanised Hindi markers that show up constantly in Indian phone conversations.
HINGLISH_MARKERS = {
    "hai", "hain", "haan", "han", "nahi", "nai", "nahin", "kya", "kyu", "kyun",
    "mujhe", "mujhko", "mera", "meri", "mere", "aap", "aapka", "aapko", "tum",
    "kitna", "kitne", "kitni", "chahiye", "chahiye,", "karna", "karo", "karke",
    "acha", "accha", "theek", "thik", "bhai", "yaar", "abhi", "baad", "kal",
    "aaj", "paise", "paisa", "rupaye", "rupay", "sasta", "mehnga", "dekh",
    "dekhna", "bata", "batao", "bhej", "bhejo", "bhejna", "lena", "lunga",
    "loonga", "hoga", "hogi", "raha", "rahi", "rahe", "koi", "kuch", "sirf",
    "lekin", "par", "aur", "phir", "wapas", "milega", "milegi", "chalega",
    "bilkul", "zaroorat", "zarurat", "jarurat", "sochunga", "sochke", "dena",
    "kaise", "kahan", "kab", "kaun", "matlab", "samajh", "bolo", "bol",
    "thoda", "bahut", "bohot", "jyada", "zyada", "kam", "wale", "wala", "wali",
}

STOPWORDS = {
    "the", "a", "an", "is", "are", "am", "i", "you", "we", "to", "of", "and",
    "for", "in", "on", "it", "this", "that", "my", "me", "do", "so", "but",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> List[str]:
    return re.findall(r"[\wऀ-ॿ]+", (text or "").lower())


def detect_language(text: str) -> str:
    """Identify the language of one utterance.

    Returns english | hindi | hinglish | marathi | bengali | telugu | kannada |
    tamil | gujarati | punjabi | malayalam | odia.

    Script detection is reliable for the non-Devanagari languages. Romanised
    input (someone typing Telugu in Latin letters) is NOT detected - it falls
    through to english/hinglish, which is a known limitation.
    """
    text = normalize(text)
    if not text:
        return "english"

    # A distinct script is decisive.
    for language, pattern in INDIC_SCRIPTS:
        if pattern.search(text):
            return language

    devanagari_chars = len(DEVANAGARI.findall(text))
    if devanagari_chars:
        if any(marker in text for marker in MARATHI_MARKERS):
            return "marathi"
    latin_chars = len(re.findall(r"[A-Za-z]", text))

    if devanagari_chars and devanagari_chars >= latin_chars:
        return "hindi"
    if devanagari_chars and latin_chars:
        return "hinglish"

    toks = tokens(text)
    if not toks:
        return "english"

    if sum(1 for t in toks if t in MARATHI_MARKERS) >= 2:
        return "marathi"

    hits = sum(1 for t in toks if t in HINGLISH_MARKERS)
    if hits == 0:
        return "english"
    ratio = hits / len(toks)
    # Almost everything romanised-Hindi in practice is code-switched Hinglish.
    if ratio >= 0.55 and len(toks) >= 4:
        return "hindi"
    return "hinglish"


def contains_any(text: str, needles: List[str]) -> bool:
    low = (text or "").lower()
    return any(n in low for n in needles)


def first_name(full_name: str) -> str:
    return (full_name or "").strip().split(" ")[0] if full_name else ""


def truncate(text: str, limit: int = 400) -> str:
    text = normalize(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"
