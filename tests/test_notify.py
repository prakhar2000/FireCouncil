"""Outbox, kill switch, and caregiver escalation."""

import json
from pathlib import Path

from services.ack.check_acks import check_acks
from services.ack.escalate import escalate
from services.agents.orchestrator import run_replay
from services.agents.replay import load_replay
from services.agents.store import JsonStore
from services.notify.dispatcher import dispatch


def test_outbox_skips_unwarned_residents_and_honors_the_kill_switch(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FC_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.delenv("PERSONA_MODEL_ID", raising=False)
    monkeypatch.delenv("APPROVAL_EVENTS", raising=False)
    decision = run_replay("route_block")[1]
    residents = load_replay("route_block").residents
    outbox = tmp_path / "outbox.jsonl"
    rows = dispatch(decision, residents, kill_switch=False, outbox_path=outbox)
    assert [row["resident_id"] for row in rows] == ["r-vulnerable"]
    assert "Capistrano" in outbox.read_text()

    blocked = tmp_path / "blocked.jsonl"
    assert dispatch(decision, residents, kill_switch=True, outbox_path=blocked) == []
    assert not blocked.exists()


def test_approval_publishes_one_event(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FC_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setenv("APPROVAL_EVENTS", "1")
    monkeypatch.delenv("PERSONA_MODEL_ID", raising=False)
    decision = run_replay("route_block")[1]
    captured = {}

    class Events:
        def put_events(self, Entries):
            captured["entries"] = Entries
            return {"FailedEntryCount": 0, "Entries": [{"EventId": "evt-test"}]}

    monkeypatch.setitem(
        __import__("sys").modules,
        "boto3",
        type("Boto", (), {"client": staticmethod(lambda *_args, **_kwargs: Events())}),
    )
    outbox = tmp_path / "outbox.jsonl"
    rows = dispatch(decision, load_replay("route_block").residents, False, outbox)
    assert [row["resident_id"] for row in rows] == ["r-vulnerable"]
    event = json.loads(outbox.read_text().strip().splitlines()[-1])
    assert event["event_id"] == "evt-test"
    assert captured["entries"][0]["Source"] == "firecouncil.approval"
    assert captured["entries"][0]["DetailType"] == "WarningApproved"


def test_vulnerable_resident_escalates_until_they_ack(tmp_path: Path):
    resident = {
        "resident_id": "r-vulnerable",
        "vulnerable": True,
        "caregiver_email": "caregiver@example.com",
    }
    assert escalate(resident, None, elapsed_s=120, window_s=60) == "caregiver@example.com"
    assert escalate(resident, None, elapsed_s=10, window_s=60) is None
    assert escalate({**resident, "vulnerable": False}, None, elapsed_s=120, window_s=60) is None

    store = JsonStore(tmp_path / "state.json")
    ack = check_acks(store, "decision-1", "r-vulnerable")
    assert escalate(resident, ack, elapsed_s=120, window_s=60) is None
    assert store.get_ack("decision-1", "r-vulnerable")["escalation_state"] == "acked"
