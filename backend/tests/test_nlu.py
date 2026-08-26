"""NLU tests: the money/intent/language layer that everything else depends on."""
import pytest

from app.schemas.nlu import CustomerMemory
from app.services.conversation.rules_nlu import extract_turn, parse_budget
from app.utils.text import detect_language


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Budget around 1000 hai", 1000),
        ("under 500 me kuch hai?", 500),
        ("My budget is Rs. 1,200", 1200),
        ("around 1.5k", 1500),
        ("2 hazar tak ka dikha do", 2000),
        ("I can spend 2500 max", 2500),
        ("मुझे 800 का चाहिए", 800),
        ("no budget in mind", None),
        ("call me at 6", None),          # a time, not money
        ("size 32 chahiye", None),       # a size, not money
    ],
)
def test_budget_parsing(text, expected):
    assert parse_budget(text).amount == expected


def test_budget_qualifier():
    assert parse_budget("under 500").qualifier == "under"
    assert parse_budget("around 1000").qualifier == "around"
    assert parse_budget("1000 ke andar").qualifier == "under"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("I need some jackets under 1000", "english"),
        ("Budget around 1000 hai but mujhe jackets chahiye", "hinglish"),
        ("मुझे कुर्ती चाहिए", "hindi"),
        # Romanised Hindi with an English loanword is code-switching, not Hindi.
        ("kal shaam call kar lena mujhe", "hinglish"),
        ("mujhe abhi kuch nahi chahiye bhai", "hindi"),
    ],
)
def test_language_detection(text, expected):
    assert detect_language(text) == expected


def test_hinglish_extraction_end_to_end():
    turn = extract_turn("Budget around 1000 hai but mujhe branded jackets chahiye, is week chahiye")
    assert turn.language == "hinglish"
    assert turn.budget.amount == 1000
    assert "jacket" in turn.product_categories
    assert turn.urgency == "this_week"
    assert turn.intent == "buy_thrift_clothes"


def test_catalog_request_is_not_a_question():
    """'WhatsApp' contains 'what' - it must not be read as a question."""
    turn = extract_turn("Send me the catalog on WhatsApp")
    assert turn.requires_whatsapp is True
    assert turn.asked_question is None


def test_do_not_call_wins_over_everything():
    turn = extract_turn("Please don't call me again, remove my number")
    assert turn.do_not_call is True
    assert turn.intent == "do_not_call"
    # "call me" appears in the text but must NOT book a callback.
    assert turn.requires_callback is False


def test_brush_off_is_not_urgent():
    turn = extract_turn("I'm not looking for anything right now")
    assert turn.intent == "not_interested"
    assert turn.urgency == "exploring"


def test_barriers_detected():
    assert "hygiene_concern" in extract_turn("Are these clothes clean?").barriers
    assert "trust_concern" in extract_turn("Is this genuine or a scam?").barriers
    assert "needs_permission" in extract_turn("I'll ask my wife first").barriers


def test_memory_merge_is_additive():
    memory = CustomerMemory()
    memory.merge_turn(extract_turn("I want jackets"))
    memory.merge_turn(extract_turn("Budget is around 1500"))
    memory.merge_turn(extract_turn("I also need hoodies this week"))

    assert memory.budget == 1500
    assert set(memory.clothing_categories) >= {"jacket", "hoodie"}
    assert memory.timeline == "this_week"


# --------------------------------------------------------------------------
# Other Indian languages
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("నాకు జాకెట్ కావాలి", "telugu"),
        ("ನನಗೆ ಜಾಕೆಟ್ ಬೇಕು", "kannada"),
        ("আমার জ্যাকেট দরকার", "bengali"),
        ("எனக்கு ஜாக்கெட் வேண்டும்", "tamil"),
        ("મને જેકેટ જોઈએ છે", "gujarati"),
    ],
)
def test_indic_scripts_are_identified(text, expected):
    assert detect_language(text) == expected


def test_marathi_is_not_mistaken_for_hindi():
    """Both use Devanagari, so the script alone cannot separate them."""
    assert detect_language("मला जॅकेट हवे आहे") == "marathi"
    assert detect_language("मुझे जैकेट चाहिए") == "hindi"
    assert detect_language("mala jacket pahije aahe") == "marathi"


@pytest.mark.parametrize(
    "text",
    [
        "నాకు జాకెట్ కావాలి, బడ్జెట్ 2000",
        "ನನಗೆ ಜಾಕೆಟ್ ಬೇಕು, ಬಜೆಟ್ 2000",
        "আমার জ্যাকেট দরকার, বাজেট 2000",
        "मला जॅकेट हवे आहे, बजेट 2000",
    ],
)
def test_products_and_budget_extract_from_indic_scripts(text):
    turn = extract_turn(text)
    assert "jacket" in turn.product_categories
    assert turn.budget.amount == 2000
