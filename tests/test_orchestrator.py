"""route_block produces a route change and a trace of that change."""

import json
from pathlib import Path

from services.agents.orchestrator import run_replay


def test_route_block_supersedes_the_first_route(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FC_TRACE_DIR", str(tmp_path))
    monkeypatch.delenv("PERSONA_MODEL_ID", raising=False)
    decisions = run_replay("route_block")
    first, second = decisions
    assert first.status == "SUPERSEDED"
    assert first.plan.route == "sr74"
    assert second.status == "PENDING_APPROVAL"
    assert second.plan.route == "i5"
    assert second.plan.zones_to_warn == ["capistrano"]
    assert second.plan.care_sites_first == ["care-1"]
    assert second.diff_from_prev["route"] == {"from": "sr74", "to": "i5"}
    langs = {message.lang for message in second.messages}
    assert langs == {"en", "es"}
    english = next(message for message in second.messages if message.lang == "en")
    assert "Call 911" in english.long_text
    assert "i5" in english.long_text
    assert len(english.sms) <= 300

    traces = list(tmp_path.rglob("*.jsonl"))
    assert traces
    blob = "\n".join(path.read_text() for path in traces)
    diff_rows = [json.loads(line) for line in blob.splitlines() if '"diff"' in line]
    assert diff_rows
    assert diff_rows[-1]["diff_from_prev"]["route"]["from"] == "sr74"
    assert diff_rows[-1]["diff_from_prev"]["route"]["to"] == "i5"
