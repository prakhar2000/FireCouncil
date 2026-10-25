"""Approval writes the outbox. Reject does not."""

from pathlib import Path

from fastapi.testclient import TestClient

from services.agents.orchestrator import run_replay
from services.agents.replay import load_replay
from services.agents.store import JsonStore
from services.api.handlers import create_app


def test_reject_does_not_send_and_approve_does(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FC_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.delenv("PERSONA_MODEL_ID", raising=False)
    monkeypatch.delenv("KILL_SWITCH", raising=False)
    monkeypatch.delenv("APPROVAL_EVENTS", raising=False)
    decision = run_replay("route_block")[1]
    store = JsonStore(tmp_path / "state.json")
    store.save_decision(decision)
    store.save_residents(load_replay("route_block").residents)
    outbox = tmp_path / "outbox.jsonl"
    client = TestClient(create_app(store, outbox))

    rejected = client.post(f"/decisions/{decision.incident_id}/{decision.cycle_ts}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert not outbox.exists()

    store.save_decision(decision)
    edited = client.post(
        f"/decisions/{decision.incident_id}/{decision.cycle_ts}/edit",
        json={"route": "i5"},
    )
    assert edited.json()["status"] == "PENDING_APPROVAL"
    assert edited.json()["plan"]["route"] == "i5"

    approved = client.post(f"/decisions/{decision.incident_id}/{decision.cycle_ts}/approve")
    assert approved.status_code == 200
    assert approved.json()["sent"] == 1
    assert "r-vulnerable" in outbox.read_text()

    listing = client.get(f"/decisions/{decision.incident_id}")
    assert listing.json()[0]["status"] == "APPROVED"


def test_smoke_mark_waits_for_graviton(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FC_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.delenv("PERSONA_MODEL_ID", raising=False)
    monkeypatch.delenv("GRAVITON_LAUNCH", raising=False)
    monkeypatch.setattr("services.api.dashboard.hold_warning", lambda: True)
    store = JsonStore(tmp_path / "state.json")
    with TestClient(create_app(store, tmp_path / "outbox.jsonl", seed=True)) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Finishing the check" in page.text
        assert "Approve this warning" not in page.text
        assert "Graviton" in page.text


def test_home_shows_the_route_change(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FC_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.delenv("PERSONA_MODEL_ID", raising=False)
    store = JsonStore(tmp_path / "state.json")
    with TestClient(create_app(store, tmp_path / "outbox.jsonl", seed=True)) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Interstate 5" in page.text
        assert "Ortega Highway" in page.text
        assert "Orange County" in page.text
        assert "San Juan Capistrano" in page.text
        assert "Approve this warning" in page.text
        assert "NASA FIRMS: hotspot detected" in page.text
        assert "Confidence low" in page.text
        assert "Speed was not measured" in page.text
        assert "3.0 km/h" not in page.text
        assert "Fire department" in page.text
        assert "Evacuation and traffic" in page.text
        assert "Public health" in page.text
        assert "This draft sends people on Interstate 5" in page.text
        approved = client.post("/decisions/norte-replay/2026-10-16T19:10:00Z/approve")
        assert approved.json()["sent"] == 1
        assert "You approved the warning" in approved.json()["lead"]
        assert "r-vulnerable" in approved.json()["saved"]
        reset = client.get("/")
        assert "You approved the warning" not in reset.text
        assert "Approve this warning" in reset.text
