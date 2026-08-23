"""Default store profile + scoring weights.

These are seeded into the `store_configuration` table on first boot and are
editable at runtime via PATCH /api/config/store — nothing here is hardcoded
into the conversation logic.
"""
from typing import Any, Dict

DEFAULT_STORE_PROFILE: Dict[str, Any] = {
    "store_name": "SwapCircle",
    "agent_name": "Ananya",
    "location": "Delhi NCR",
    "tagline": "Refresh your wardrobe for less — buy, sell, swap or donate pre-owned fashion.",
    "services": [
        "Buy quality pre-owned clothes",
        "Sell clothes lying unused in your wardrobe",
        "Swap clothes 1-for-1 at our swap events",
        "Donate clothes to verified NGOs",
    ],
    "target_customers": [
        "Students",
        "Young professionals",
        "Fashion-conscious customers",
        "Budget shoppers",
    ],
    "price_range": {"min": 199, "max": 2499, "currency": "INR"},
    "catalog_url": "https://swapcircle.example/catalog",
    "swap_event": "Every Saturday, 11am-7pm, Hauz Khas",
    "delivery": "Free delivery across Delhi NCR on orders above Rs.999, 3-5 days pan-India",
    "returns": "7-day no-questions return window on every order",
    "hygiene": "Every item is professionally dry-cleaned, steam-sanitised and quality-graded A/B/C before listing",
}

# Deterministic lead-scoring weights. Fully configurable at runtime.
DEFAULT_SCORING_WEIGHTS: Dict[str, int] = {
    "clear_buying_intent": 25,
    "specific_budget": 15,
    "specific_product": 15,
    "urgent_timeline": 15,
    "requests_catalog": 20,
    "requests_store_visit": 20,
    "agrees_to_callback": 10,
    "wants_to_sell_or_swap": 22,
    "shared_location": 5,
    "positive_sentiment": 5,
    "engaged_question": 8,
    "budget_objection": -5,
    "needs_to_ask_someone": -5,
    "trust_or_hygiene_concern": -3,
    "just_browsing": -20,
    "no_interest": -40,
    "do_not_call": -60,
}

DEFAULT_THRESHOLDS: Dict[str, int] = {"hot": 60, "warm": 20}

# Short knowledge base used for retrieval-augmented objection handling.
DEFAULT_FAQ = [
    {
        "q": "Are the clothes clean and hygienic?",
        "tags": ["hygiene", "clean", "smell", "used", "dirty", "saaf", "ganda"],
        "a": "Every single item is professionally dry-cleaned and steam-sanitised before it is listed, and we grade each piece A, B or C for condition so you know exactly what you're getting.",
        "a_hinglish": "Har single item professionally dry-clean aur steam-sanitise hota hai, aur hum har piece ko A, B ya C condition grade dete hain.",
    },
    {
        "q": "Why should I buy used clothes?",
        "tags": ["why", "used", "second hand", "purana"],
        "a": "You get brands like Zara, H&M and Levi's at 60 to 80 percent off, and you keep good clothing out of landfill. Most of our pieces have been worn only a handful of times.",
        "a_hinglish": "Zara, H&M, Levi's jaise brands 60 se 80 percent kam mein mil jaate hain, aur achhe kapde landfill mein nahi jaate.",
    },
    {
        "q": "Is this genuine? Who are you?",
        "tags": ["genuine", "scam", "fraud", "real", "trust", "kaun"],
        "a": "We're SwapCircle, a registered thrift and clothing-swap platform based in Delhi NCR. I can WhatsApp you our store page and Instagram right now so you can check us out yourself.",
        "a_hinglish": "Hum SwapCircle hain, Delhi NCR ka registered thrift aur clothing-swap platform. Main abhi store page aur Instagram WhatsApp kar deti hoon.",
    },
    {
        "q": "Can I return items?",
        "tags": ["return", "refund", "exchange", "wapas"],
        "a": "Yes, there's a 7-day no-questions-asked return window on every order, and returns pickup is free in Delhi NCR.",
        "a_hinglish": "Haan ji, 7 din ka no-questions return milta hai, aur Delhi NCR mein pickup bilkul free hai.",
    },
    {
        "q": "How does swapping work?",
        "tags": ["swap", "exchange", "badal"],
        "a": "You bring clothes in good condition, we grade them and give you swap points, and you pick anything of equal points from the rack. Our swap meet runs every Saturday in Hauz Khas.",
        "a_hinglish": "Aap achhi condition ke kapde laayiye, hum grade karke swap points dete hain, aur aap utne points ka kuch bhi rack se le sakte ho. Swap meet har Saturday Hauz Khas mein.",
    },
    {
        "q": "How do I sell my clothes?",
        "tags": ["sell", "sale", "bech", "paise"],
        "a": "Share photos on WhatsApp, we quote a price within a day, arrange free pickup in Delhi NCR, and pay out by UPI within 48 hours of the quality check.",
        "a_hinglish": "WhatsApp pe photos bhejiye, ek din mein price quote karte hain, Delhi NCR mein free pickup, aur quality check ke 48 ghante mein UPI se payment.",
    },
    {
        "q": "What are the prices?",
        "tags": ["price", "cost", "kitna", "rate", "budget", "expensive"],
        "a": "Most pieces sit between 199 and 1499 rupees. Tops and tees usually start around 249, jackets and denim around 699.",
        "a_hinglish": "Zyadatar pieces 199 se 1499 ke beech hote hain. Tops aur tees 249 se shuru, jackets aur denim 699 se.",
    },
    {
        "q": "Where are you located / delivery?",
        "tags": ["location", "where", "delivery", "kahan", "address", "shipping"],
        "a": "Our studio is in Hauz Khas, Delhi. We deliver free across Delhi NCR above 999 rupees, and ship pan-India in 3 to 5 days.",
        "a_hinglish": "Humara studio Hauz Khas, Delhi mein hai. Delhi NCR mein 999 se upar free delivery, aur pan-India 3 se 5 din mein ship karte hain.",
    },
]
