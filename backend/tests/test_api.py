"""End-to-end API tests against a throwaway SQLite database."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Point the app at a temp DB before anything imports the engine.
_TMP_DB = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["SCHEDULER_ENABLED"] = "false"

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/api/dashboard/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_hot_demo_call_end_to_end(client):
    started = client.post("/api/calls/demo/start", json={"scenario": "hot"})
    assert started.status_code == 201
    call_id = started.json()["call_id"]
    assert started.json()["opening_message"]

    turn = client.post(
        f"/api/calls/{call_id}/turn",
        json={"text": "I need branded jackets, budget around 1500, need them this week"},
    )
    assert turn.status_code == 200
    payload = turn.json()

    assert payload["lead"]["classification"] == "HOT"
    assert payload["lead"]["score"] >= 60
    assert payload["memory"]["budget"] == 1500
    assert "jacket" in payload["memory"]["clothing_categories"]
    assert any(a["action_type"] == "send_whatsapp" for a in payload["actions"])

    ended = client.post(f"/api/calls/{call_id}/end")
    assert ended.status_code == 200
    assert ended.json()["final_status"] == "HOT"

    transcript = client.get(f"/api/calls/{call_id}/transcript")
    assert transcript.status_code == 200
    assert "CUSTOMER:" in transcript.json()["text"]


def test_callback_is_scheduled_from_natural_language(client):
    call_id = client.post("/api/calls/demo/start", json={"scenario": "warm"}).json()["call_id"]
    payload = client.post(
        f"/api/calls/{call_id}/turn", json={"text": "Call me tomorrow evening at 6"}
    ).json()

    callback = next(a for a in payload["actions"] if a["action_type"] == "schedule_callback")
    assert callback["result"]["human_time"]
    assert callback["result"]["confidence"] > 0.5

    listed = client.get("/api/callbacks").json()
    assert any(c["call_id"] == call_id for c in listed)


def test_opt_out_blocks_future_calls(client):
    started = client.post(
        "/api/calls/demo/start", json={"customer_name": "Optout", "phone_number": "+919999000111"}
    ).json()
    client.post(
        f"/api/calls/{started['call_id']}/turn", json={"text": "Please don't call me again"}
    )

    blocked = client.post(
        "/api/calls/start", json={"phone_number": "+919999000111", "customer_name": "Optout"}
    )
    assert blocked.status_code == 403
    assert "do-not-call" in blocked.json()["detail"].lower()


def test_leads_and_dashboard(client):
    leads = client.get("/api/leads").json()
    assert isinstance(leads, list) and leads

    detail = client.get(f"/api/leads/{leads[0]['id']}").json()
    assert "score_history" in detail and "transcript" in detail

    explanation = client.get(f"/api/leads/{leads[0]['id']}/score-explanation").json()
    assert "voters" in explanation

    stats = client.get("/api/dashboard/stats").json()
    assert stats["total_calls"] >= 1


def test_time_parser_endpoint(client):
    parsed = client.post("/api/callbacks/parse", json={"text": "kal shaam 6 baje"}).json()
    assert parsed["confidence"] > 0.5
    assert parsed["timezone"] == "Asia/Kolkata"


def test_classify_endpoint_compares_methods(client):
    result = client.post(
        "/api/training/classify", json={"text": "Mujhe jackets chahiye 1000 tak, is hafte"}
    ).json()
    assert result["methods"]["rules"]["label"] in ("HOT", "WARM", "COLD", "UNKNOWN")
    assert result["extracted"]["budget"]["amount"] == 1000


def test_store_config_is_editable(client):
    updated = client.patch(
        "/api/config/store", json={"profile": {"store_name": "ThriftLoop"}}
    ).json()
    assert updated["profile"]["store_name"] == "ThriftLoop"
    client.patch("/api/config/store", json={"profile": {"store_name": "SwapCircle"}})
