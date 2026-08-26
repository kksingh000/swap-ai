"""Telugu and Kannada response banks for the deterministic responder.

Kept in their own module so responder.py stays readable rather than carrying
five languages inline. These are merged into the main banks at import time by
`responder._install_indic_banks()`.

Style notes, which matter more than literal translation here:
  * Short sentences. This is a phone call, not a brochure.
  * Retail English loanwords stay in English - budget, size, collection,
    WhatsApp, jacket, jeans, store - because that is how people actually
    speak in Hyderabad and Bengaluru. Translating them would sound stilted.
  * Polite register (గారు / ಅವರೇ, తీసుకోండి / ಮಾಡುತ್ತೇನೆ) since this is a
    cold call to a stranger.
"""
from typing import Dict, List

TELUGU: Dict[str, object] = {
    "ACK": ["సరే.", "బాగుంది.", "అర్థమైంది.", "మంచిది.", "సరే మరి."],
    "OPENING": [
        "నమస్కారం {name} గారు, నేను {agent}, {store} నుండి మాట్లాడుతున్నాను. ఒక నిమిషం మాట్లాడవచ్చా?",
        "హలో {name} గారు! నేను {agent}, {store} నుండి. ఇప్పుడు ఒక నిమిషం టైం ఉందా?",
    ],
    "PITCH": [
        "మేము {location} లో thrift మరియు clothing-swap platform. మీరు మంచి pre-owned బట్టలు కొనొచ్చు, "
        "మీ పాత బట్టలు అమ్మొచ్చు, లేదా swap చేసుకోవచ్చు. వీటిలో మీకు ఏది ఉపయోగంగా ఉంటుంది?",
        "{store} లో తక్కువ ధరకి branded pre-owned బట్టలు దొరుకుతాయి, మీ బట్టలు అమ్మొచ్చు లేదా swap చేయొచ్చు. "
        "మీకు ఏది నచ్చుతుంది?",
    ],
    "ASK_CATEGORY": [
        "మీకు ఏ రకమైన బట్టలు కావాలి - jackets, jeans, ethnic లేదా daily wear?",
        "ఎక్కువగా ఏమి వెతుకుతున్నారు? Jackets, jeans మా దగ్గర త్వరగా అయిపోతాయి.",
    ],
    "ASK_BUDGET": [
        "{item} కోసం మీ budget ఎంత అనుకుంటున్నారు?",
        "{item} కి approximately ఎంత budget పెడతారు?",
    ],
    "ASK_TIMELINE": [
        "ఎప్పటికి కావాలి - ఈ వారంలోనా, లేక తర్వాత చూద్దామనా?",
        "త్వరగా కావాలా, లేక ఇప్పుడే చూస్తున్నారా?",
    ],
    "ASK_SIZE": ["మీ size ఏంటి? నేను list filter చేసి పంపిస్తాను."],
    "ASK_SELL_DETAILS": [
        "బాగుంది - ఏ రకమైన బట్టలు అమ్మాలనుకుంటున్నారు, సుమారు ఎన్ని ఉన్నాయి?",
        "సరే, ఏ brands ఉన్నాయి, condition ఎలా ఉంది?",
    ],
    "ASK_SWAP_DETAILS": [
        "మా swap meet {swap_event} జరుగుతుంది. మీరు ఏమి swap చేయాలనుకుంటున్నారు?",
    ],
    "WHATSAPP_SENT": [
        "పంపించాను - మా current collection మీ WhatsApp కి పంపాను. చూసి ఏవి నచ్చాయో చెప్పండి.",
        "ఇప్పుడే WhatsApp లో share చేశాను. తీరిక ఉన్నప్పుడు చూసి చెప్పండి.",
    ],
    "WHATSAPP_ALREADY_SENT": [
        "అది ఇప్పుడే WhatsApp కి పంపించాను, మీ chat లో ఉండాలి.",
        "అప్పుడే పంపేశాను WhatsApp కి, ఒకసారి చూడండి.",
    ],
    "NEXT_STEP": [
        "మీ కోసం ఏదైనా ప్రత్యేకంగా పక్కన పెట్టమంటారా?",
        "రెండు మూడు pieces మీ కోసం పక్కన పెట్టనా?",
        "ఇంకేమైనా చూడమంటారా?",
    ],
    "CALLBACK_CONFIRMED": ["సరే, నేను మీకు {when} కాల్ చేస్తాను. ధన్యవాదాలు!"],
    "VISIT": [
        "మా store Hauz Khas, Delhi లో ఉంది, రాత్రి 8 వరకు open. Location WhatsApp చేస్తాను.",
    ],
    "COLD_CLOSE": [
        "పర్వాలేదు - విన్నందుకు ధన్యవాదాలు. ఎప్పుడైనా అవసరమైతే మేము ఉన్నాము!",
    ],
    "DNC_CLOSE": [
        "అర్థమైంది, ఇబ్బంది పెట్టినందుకు క్షమించండి. మీ నంబర్ మా list నుండి తీసేశాను, "
        "మళ్ళీ కాల్ రాదు. మంచి రోజు!",
    ],
    "CLOSING": ["మీతో మాట్లాడటం బాగుంది {name}. మంచి రోజు కావాలని కోరుకుంటున్నాను!"],
    "BARRIER_REPLIES": {
        "budget_concern": [
            "అర్థమైంది - మా ఎక్కువ pieces 249 నుండి 999 మధ్యలో ఉంటాయి, budget లోనే దొరుకుతాయి."
        ],
        "trust_concern": [
            "సరైన ప్రశ్న - మేము Hauz Khas లో registered store, 2000+ customers ఉన్నారు. "
            "మా page మరియు reviews ఇప్పుడే WhatsApp చేస్తాను."
        ],
        "hygiene_concern": [
            "ప్రతి piece professional గా dry-clean మరియు steam-sanitise చేస్తాము, "
            "condition A, B, C grade చేసిన తర్వాతే list చేస్తాము."
        ],
        "needs_permission": [
            "తప్పకుండా, అడిగి చెప్పండి. Collection పంపనా, వాళ్ళకి చూపించడానికి?"
        ],
        "no_time": ["పర్వాలేదు - ఎప్పుడు కాల్ చేస్తే మీకు వీలుగా ఉంటుంది?"],
        "wants_to_see_inventory": [
            "సరే - మా current collection WhatsApp చేస్తాను, మీరే చూడండి."
        ],
        "return_concern": ["7 రోజుల return ఉంటుంది, Delhi NCR లో pickup కూడా free."],
    },
}

KANNADA: Dict[str, object] = {
    "ACK": ["ಸರಿ.", "ಚೆನ್ನಾಗಿದೆ.", "ಅರ್ಥವಾಯಿತು.", "ಆಯ್ತು.", "ಸರಿ ಹಾಗಾದರೆ."],
    "OPENING": [
        "ನಮಸ್ಕಾರ {name} ಅವರೇ, ನಾನು {agent}, {store} ಇಂದ ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ. ಒಂದು ನಿಮಿಷ ಮಾತನಾಡಬಹುದೇ?",
        "ಹಲೋ {name} ಅವರೇ! ನಾನು {agent}, {store} ಇಂದ. ಈಗ ಒಂದು ನಿಮಿಷ ಸಮಯ ಇದೆಯೇ?",
    ],
    "PITCH": [
        "ನಾವು {location} ನಲ್ಲಿ thrift ಮತ್ತು clothing-swap platform. ನೀವು ಒಳ್ಳೆಯ pre-owned ಬಟ್ಟೆ "
        "ಖರೀದಿಸಬಹುದು, ನಿಮ್ಮ ಹಳೆಯ ಬಟ್ಟೆ ಮಾರಬಹುದು, ಅಥವಾ swap ಮಾಡಬಹುದು. ಯಾವುದು ನಿಮಗೆ ಉಪಯೋಗ?",
        "{store} ನಲ್ಲಿ ಕಡಿಮೆ ಬೆಲೆಗೆ branded pre-owned ಬಟ್ಟೆ ಸಿಗುತ್ತದೆ, ನಿಮ್ಮ ಬಟ್ಟೆ ಮಾರಬಹುದು "
        "ಅಥವಾ swap ಮಾಡಬಹುದು. ನಿಮಗೆ ಯಾವುದು ಇಷ್ಟ?",
    ],
    "ASK_CATEGORY": [
        "ನಿಮಗೆ ಯಾವ ರೀತಿಯ ಬಟ್ಟೆ ಬೇಕು - jackets, jeans, ethnic ಅಥವಾ daily wear?",
        "ಹೆಚ್ಚಾಗಿ ಏನು ಹುಡುಕುತ್ತಿದ್ದೀರಿ? Jackets, jeans ನಮ್ಮಲ್ಲಿ ಬೇಗ ಖಾಲಿಯಾಗುತ್ತವೆ.",
    ],
    "ASK_BUDGET": [
        "{item} ಗೆ ನಿಮ್ಮ budget ಎಷ್ಟು ಅಂದುಕೊಂಡಿದ್ದೀರಿ?",
        "{item} ಗೆ ಸುಮಾರು ಎಷ್ಟು budget ಇಡುತ್ತೀರಿ?",
    ],
    "ASK_TIMELINE": [
        "ಯಾವಾಗ ಬೇಕು - ಈ ವಾರವೇ, ಅಥವಾ ನಂತರ ನೋಡೋಣವೇ?",
        "ಬೇಗ ಬೇಕೇ, ಅಥವಾ ಈಗ ನೋಡುತ್ತಿದ್ದೀರಾ?",
    ],
    "ASK_SIZE": ["ನಿಮ್ಮ size ಯಾವುದು? ನಾನು list filter ಮಾಡಿ ಕಳಿಸುತ್ತೇನೆ."],
    "ASK_SELL_DETAILS": [
        "ಚೆನ್ನಾಗಿದೆ - ಯಾವ ರೀತಿಯ ಬಟ್ಟೆ ಮಾರಬೇಕು, ಸುಮಾರು ಎಷ್ಟು ಇವೆ?",
        "ಸರಿ, ಯಾವ brands ಇವೆ, condition ಹೇಗಿದೆ?",
    ],
    "ASK_SWAP_DETAILS": [
        "ನಮ್ಮ swap meet {swap_event} ನಡೆಯುತ್ತದೆ. ನೀವು ಏನು swap ಮಾಡಲು ಬಯಸುತ್ತೀರಿ?",
    ],
    "WHATSAPP_SENT": [
        "ಕಳಿಸಿದ್ದೇನೆ - ನಮ್ಮ current collection ನಿಮ್ಮ WhatsApp ಗೆ ಕಳಿಸಿದೆ. ನೋಡಿ ಯಾವುದು ಇಷ್ಟ ಆಯ್ತು ಹೇಳಿ.",
        "ಈಗಷ್ಟೇ WhatsApp ನಲ್ಲಿ share ಮಾಡಿದೆ. ಸಮಯ ಸಿಕ್ಕಾಗ ನೋಡಿ ಹೇಳಿ.",
    ],
    "WHATSAPP_ALREADY_SENT": [
        "ಅದನ್ನು ಈಗಷ್ಟೇ WhatsApp ಗೆ ಕಳಿಸಿದ್ದೇನೆ, ನಿಮ್ಮ chat ನಲ್ಲಿ ಇರಬೇಕು.",
        "ಆಗಲೇ ಕಳಿಸಿದ್ದೇನೆ WhatsApp ಗೆ, ಒಮ್ಮೆ ನೋಡಿ.",
    ],
    "NEXT_STEP": [
        "ನಿಮಗಾಗಿ ಏನಾದರೂ ವಿಶೇಷವಾಗಿ ತೆಗೆದಿಡಲೇ?",
        "ಎರಡು ಮೂರು pieces ನಿಮಗಾಗಿ ತೆಗೆದಿಡಲೇ?",
        "ಇನ್ನೇನಾದರೂ ನೋಡಲೇ?",
    ],
    "CALLBACK_CONFIRMED": ["ಸರಿ, ನಾನು ನಿಮಗೆ {when} ಕರೆ ಮಾಡುತ್ತೇನೆ. ಧನ್ಯವಾದಗಳು!"],
    "VISIT": [
        "ನಮ್ಮ store Hauz Khas, Delhi ನಲ್ಲಿ ಇದೆ, ರಾತ್ರಿ 8 ರವರೆಗೆ open. Location WhatsApp ಮಾಡುತ್ತೇನೆ.",
    ],
    "COLD_CLOSE": [
        "ಪರವಾಗಿಲ್ಲ - ಕೇಳಿಸಿಕೊಂಡಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದ. ಯಾವಾಗ ಬೇಕಾದರೂ ನಾವು ಇದ್ದೇವೆ!",
    ],
    "DNC_CLOSE": [
        "ಅರ್ಥವಾಯಿತು, ತೊಂದರೆ ಕೊಟ್ಟಿದ್ದಕ್ಕೆ ಕ್ಷಮಿಸಿ. ನಿಮ್ಮ ನಂಬರ್ ನಮ್ಮ list ಇಂದ ತೆಗೆದಿದ್ದೇನೆ, "
        "ಮತ್ತೆ ಕರೆ ಬರುವುದಿಲ್ಲ. ಒಳ್ಳೆಯ ದಿನ!",
    ],
    "CLOSING": ["ನಿಮ್ಮ ಜೊತೆ ಮಾತನಾಡಿ ಸಂತೋಷವಾಯಿತು {name}. ಒಳ್ಳೆಯ ದಿನವಾಗಲಿ!"],
    "BARRIER_REPLIES": {
        "budget_concern": [
            "ಅರ್ಥವಾಯಿತು - ನಮ್ಮ ಹೆಚ್ಚಿನ pieces 249 ರಿಂದ 999 ರ ನಡುವೆ ಇರುತ್ತವೆ, budget ನಲ್ಲೇ ಸಿಗುತ್ತದೆ."
        ],
        "trust_concern": [
            "ಸರಿಯಾದ ಪ್ರಶ್ನೆ - ನಾವು Hauz Khas ನಲ್ಲಿ registered store, 2000+ customers ಇದ್ದಾರೆ. "
            "ನಮ್ಮ page ಮತ್ತು reviews ಈಗಲೇ WhatsApp ಮಾಡುತ್ತೇನೆ."
        ],
        "hygiene_concern": [
            "ಪ್ರತಿ piece professional ಆಗಿ dry-clean ಮತ್ತು steam-sanitise ಆಗುತ್ತದೆ, "
            "condition A, B, C grade ಮಾಡಿದ ನಂತರವೇ list ಮಾಡುತ್ತೇವೆ."
        ],
        "needs_permission": [
            "ಖಂಡಿತ, ಕೇಳಿ ಹೇಳಿ. Collection ಕಳಿಸಲೇ, ಅವರಿಗೆ ತೋರಿಸಲು?"
        ],
        "no_time": ["ಪರವಾಗಿಲ್ಲ - ಯಾವಾಗ ಕರೆ ಮಾಡಿದರೆ ನಿಮಗೆ ಅನುಕೂಲ?"],
        "wants_to_see_inventory": [
            "ಸರಿ - ನಮ್ಮ current collection WhatsApp ಮಾಡುತ್ತೇನೆ, ನೀವೇ ನೋಡಿ."
        ],
        "return_concern": ["7 ದಿನಗಳ return ಇದೆ, Delhi NCR ನಲ್ಲಿ pickup ಕೂಡ free."],
    },
}

BANKS: Dict[str, Dict[str, object]] = {"telugu": TELUGU, "kannada": KANNADA}

# Which languages the deterministic responder can actually hold a conversation
# in. Anything detected outside this set is understood but answered in English
# unless an LLM is configured.
TEMPLATE_LANGUAGES: List[str] = ["english", "hindi", "hinglish", "telugu", "kannada"]
