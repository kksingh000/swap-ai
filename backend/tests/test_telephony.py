"""Twilio webhook tests.

These cover the path that only runs in production, where a mistake is expensive:
a malformed TwiML action URL silently kills a live phone call.
"""
import os
import tempfile
import xml.dom.minidom as minidom

import pytest
from fastapi.testclient import TestClient

_TMP_DB = os.path.join(tempfile.mkdtemp(), "tel.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["SCHEDULER_ENABLED"] = "false"
from app.api.routes.telephony import _action_url  # noqa: E402
from app.main import app  # noqa: E402
from app.services.telephony.providers import (  # noqa: E402
    twiml_say_and_gather,
    twiml_say_and_hangup,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_action_url_is_absolute_https(monkeypatch):
    """Behind Render's TLS proxy request.url reads http; we must not use it.

    settings is a module-level singleton, so patch the attribute rather than
    the environment - otherwise this depends on test import order.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://swap-ai-backend.onrender.com")
    url = _action_url(42)
    assert url.startswith("https://")
    assert url == "https://swap-ai-backend.onrender.com/api/telephony/twilio/voice?call_id=42"


def test_action_url_tolerates_trailing_slash(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://example.com/")
    assert _action_url(3) == "https://example.com/api/telephony/twilio/voice?call_id=3"


def test_gather_twiml_is_valid_xml():
    xml = twiml_say_and_gather("Hi there", _action_url(1), "english")
    minidom.parseString(xml)  # raises on malformed XML
    assert "<Gather" in xml and 'input="speech"' in xml


def test_redirect_url_does_not_double_up_query_separator():
    """?call_id=1?no_input=1 would make call_id fail int validation (422)."""
    xml = twiml_say_and_gather("Hi", _action_url(1), "english")
    document = minidom.parseString(xml)
    redirect = document.getElementsByTagName("Redirect")[0].firstChild.data

    assert redirect.count("?") == 1
    assert "call_id=1&no_input=1" in redirect


def test_redirect_uses_question_mark_when_url_has_no_query():
    xml = twiml_say_and_gather("Hi", "https://example.com/voice", "english")
    redirect = minidom.parseString(xml).getElementsByTagName("Redirect")[0].firstChild.data
    assert redirect == "https://example.com/voice?no_input=1"


def test_hindi_uses_hindi_voice_and_locale():
    xml = twiml_say_and_gather("Namaste", _action_url(1), "hindi")
    assert 'language="hi-IN"' in xml
    minidom.parseString(xml)


def test_hangup_twiml_is_valid():
    xml = twiml_say_and_hangup("Goodbye", "english")
    minidom.parseString(xml)
    assert "<Hangup/>" in xml


def test_voicemail_hangs_up_without_leaving_a_lead(client):
    response = client.post(
        "/api/telephony/twilio/voice",
        data={"CallSid": "CAtest_vm", "From": "+919812345699", "AnsweredBy": "machine_start"},
    )
    assert response.status_code == 200
    assert "<Hangup/>" in response.text
    minidom.parseString(response.text)


def test_inbound_call_creates_a_call_and_greets(client):
    response = client.post(
        "/api/telephony/twilio/voice",
        data={"CallSid": "CAtest_inbound", "From": "+919812345698"},
    )
    assert response.status_code == 200
    assert "<Gather" in response.text
    minidom.parseString(response.text)


def test_speech_result_drives_a_conversation_turn(client):
    client.post(
        "/api/telephony/twilio/voice",
        data={"CallSid": "CAtest_convo", "From": "+919812345697"},
    )
    response = client.post(
        "/api/telephony/twilio/voice",
        data={
            "CallSid": "CAtest_convo",
            "From": "+919812345697",
            "SpeechResult": "I need jackets under 1500 this week",
            "Confidence": "0.92",
        },
    )
    assert response.status_code == 200
    minidom.parseString(response.text)
    # The agent should still be listening, not hanging up on a hot lead.
    assert "<Gather" in response.text


def test_opt_out_on_a_live_call_hangs_up(client):
    client.post(
        "/api/telephony/twilio/voice",
        data={"CallSid": "CAtest_dnc", "From": "+919812345696"},
    )
    response = client.post(
        "/api/telephony/twilio/voice",
        data={
            "CallSid": "CAtest_dnc",
            "From": "+919812345696",
            "SpeechResult": "Please don't call me again, remove my number",
        },
    )
    assert response.status_code == 200
    assert "<Hangup/>" in response.text


def test_status_callback_finalises_the_call(client):
    client.post(
        "/api/telephony/twilio/voice",
        data={"CallSid": "CAtest_status", "From": "+919812345695"},
    )
    response = client.post(
        "/api/telephony/twilio/status",
        data={"CallSid": "CAtest_status", "CallStatus": "completed", "CallDuration": "47"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
