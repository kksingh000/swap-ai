"""Text helpers: language detection for English / Hindi / Hinglish, plus tokenising."""
import re
import unicodedata
from typing import List

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

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
    """Return english | hindi | hinglish.

    Devanagari script wins outright. Otherwise we look at how many romanised
    Hindi markers appear relative to the sentence length.
    """
    text = normalize(text)
    if not text:
        return "english"

    devanagari_chars = len(DEVANAGARI.findall(text))
    latin_chars = len(re.findall(r"[A-Za-z]", text))

    if devanagari_chars and devanagari_chars >= latin_chars:
        return "hindi"
    if devanagari_chars and latin_chars:
        return "hinglish"

    toks = tokens(text)
    if not toks:
        return "english"
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
