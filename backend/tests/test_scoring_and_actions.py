"""Lead scoring, callback parsing and the action decision layer."""
from datetime import datetime

import pytest

from app.schemas.nlu import CustomerMemory
from app.services.actions.engine import MARK_DNC, SCHEDULE_CALLBACK, SEND_WHATSAPP, decide
from app.services.classification.scoring import score_lead
from app.services.conversation.rules_nlu import extract_turn
from app.services.scheduling.nlp_time import IST, parse_callback_time


def build(lines):
    memory = CustomerMemory()
    turns = []
    for line in lines:
        turn = extract_turn(line)
        turns.append(turn)
        memory.merge_turn(turn)
    return memory, turns


def test_hot_lead_scores_high():
    memory, turns = build([
        "I need branded jackets and hoodies",
        "Budget is around 1500 and I need them this week",
        "Send me the catalog on WhatsApp",
    ])
    result = score_lead(memory, turns)
    assert result.classification == "HOT"
    assert result.score >= 60
    assert any("1500" in reason for reason in result.reasons)


def test_cold_lead_scores_low():
    memory, turns = build(["Oh I was just curious, I'm not looking for anything right now"])
    result = score_lead(memory, turns)
    assert result.classification == "COLD"


def test_do_not_call_is_always_cold():
    memory, turns = build(["I need jackets under 2000 today", "Actually don't call me again"])
    result = score_lead(memory, turns)
    assert result.classification == "COLD"


def test_first_neutral_turn_is_unknown_not_cold():
    memory, turns = build(["Yeah sure, I have a minute"])
    assert score_lead(memory, turns).classification == "UNKNOWN"


def test_scoring_is_explainable():
    memory, turns = build(["I want jackets around 1000 this week"])
    result = score_lead(memory, turns)
    assert result.reasons
    assert all("(" in reason for reason in result.reasons)  # every reason carries its points


def test_weights_are_configurable():
    memory, turns = build(["I want jackets around 1000 this week"])
    default = score_lead(memory, turns).score
    boosted = score_lead(memory, turns, weights={"specific_budget": 40}).score
    assert boosted > default


# ---------------------------------------------------------------- callbacks --

@pytest.mark.parametrize(
    "text",
    ["call me tomorrow morning", "kal shaam 6 baje", "next Monday", "this weekend", "after 6"],
)
def test_callback_parsing_returns_future_time(text):
    result = parse_callback_time(text)
    assert result["scheduled_time"] > datetime.now(IST)
    assert 0 < result["confidence"] <= 1
    assert result["interpretation"]


def test_tomorrow_morning_defaults_to_ten():
    now = datetime(2026, 8, 23, 15, 0, tzinfo=IST)
    result = parse_callback_time("call me tomorrow morning", now=now)
    assert result["scheduled_time"].day == 24
    assert result["scheduled_time"].hour == 10


def test_hinglish_evening_is_pm():
    now = datetime(2026, 8, 23, 12, 0, tzinfo=IST)
    result = parse_callback_time("kal shaam 6 baje call karna", now=now)
    assert result["scheduled_time"].hour == 18


def test_callbacks_never_land_outside_calling_hours():
    now = datetime(2026, 8, 23, 12, 0, tzinfo=IST)
    result = parse_callback_time("call me at 11 pm", now=now)
    assert 9 <= result["scheduled_time"].hour < 21


def test_vague_time_has_lower_confidence():
    vague = parse_callback_time("call me sometime")["confidence"]
    precise = parse_callback_time("call me tomorrow at 4 pm")["confidence"]
    assert vague < precise


# ------------------------------------------------------------------ actions --

def test_catalog_request_triggers_whatsapp():
    memory, turns = build(["Send me the catalog on WhatsApp, I want jackets under 1000"])
    decisions = decide(turns[-1], memory, "HOT", already_done=[])
    assert any(d["action_type"] == SEND_WHATSAPP for d in decisions)


def test_whatsapp_is_not_sent_twice():
    memory, turns = build(["Send me the catalog on WhatsApp"])
    decisions = decide(turns[-1], memory, "HOT", already_done=[SEND_WHATSAPP])
    assert not any(d["action_type"] == SEND_WHATSAPP for d in decisions)


def test_callback_request_is_scheduled():
    memory, turns = build(["Call me tomorrow evening"])
    decisions = decide(turns[-1], memory, "WARM", already_done=[])
    assert any(d["action_type"] == SCHEDULE_CALLBACK for d in decisions)


def test_opt_out_marks_do_not_call_and_ends_call():
    memory, turns = build(["Please don't call me again"])
    decisions = decide(turns[-1], memory, "COLD", already_done=[])
    types = [d["action_type"] for d in decisions]
    assert MARK_DNC in types
    assert "end_call" in types
    # An opted-out customer must never be messaged.
    assert SEND_WHATSAPP not in types
