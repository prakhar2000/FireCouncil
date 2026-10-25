"""Three persona calls are prepared. Bedrock is not contacted."""

import json

import pytest

from services.agents.orchestrator import run_replay
from services.agents.personas.llm import invoke
from services.agents.replay import load_replay


def test_three_persona_calls_differ_and_are_not_sent(monkeypatch, tmp_path):
    monkeypatch.setenv("FC_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv("PERSONA_MODEL_ID", "us.amazon.nova-micro-v1:0")
    monkeypatch.delenv("BEDROCK_CALLS", raising=False)

    def refuse(*_args, **_kwargs):
        raise AssertionError("boto3 was called")

    monkeypatch.setitem(__import__("sys").modules, "boto3", type("Boto", (), {"client": staticmethod(refuse)}))
    decisions = run_replay("route_block")
    assert decisions[1].plan.route == "i5"
    assert decisions[1].fire.firms_confidence == "low"
    assert decisions[1].health.assisted_evac_zones == ["capistrano"]

    rows = []
    for path in tmp_path.rglob("*.jsonl"):
        rows.extend(json.loads(line) for line in path.read_text().splitlines())
    prepared = [row for row in rows if row.get("type") == "persona_call"]
    assert [row["persona"] for row in prepared] == [
        "fire_ops",
        "evac_traffic",
        "public_health",
        "fire_ops",
        "evac_traffic",
        "public_health",
    ]
    assert all(row["invoked"] is False for row in prepared)


def test_each_prompt_asks_for_a_different_job():
    replay = load_replay("route_block")
    cycle = replay.cycles[1]
    from services.agents.personas.evac_traffic import call_for as evac_call
    from services.agents.personas.evac_traffic import propose as propose_evac
    from services.agents.personas.fire_ops import call_for as fire_call
    from services.agents.personas.fire_ops import propose as propose_fire
    from services.agents.personas.public_health import call_for as health_call
    from services.agents.personas.public_health import propose as propose_health

    calls = [
        fire_call(propose_fire(replay, cycle)),
        evac_call(propose_evac(replay, cycle)),
        health_call(propose_health(replay)),
    ]
    assert [call.persona for call in calls] == ["fire_ops", "evac_traffic", "public_health"]
    assert len({call.system for call in calls}) == 3
    assert all(call.model_id_env == "PERSONA_MODEL_ID" for call in calls)
    assert "NASA" in calls[0].system
    assert "blocked road" in calls[1].system
    assert "vulnerable" in calls[2].system
    assert all(len(call.system) > 800 for call in calls)
    assert all("duty officer" in call.system.lower() for call in calls)
    assert "low" in calls[0].user
    assert "blocked" in calls[1].user
    assert "capistrano" in calls[2].user


def test_a_model_reply_replaces_the_draft_without_aws(monkeypatch):
    monkeypatch.delenv("BEDROCK_CALLS", raising=False)
    replay = load_replay("route_block")
    from services.agents.personas.fire_ops import call_for
    from services.agents.personas.fire_ops import propose as propose_fire
    from services.agents.personas.llm import apply_model
    from services.agents.schemas import FireAssessment

    drafted = propose_fire(replay, replay.cycles[1])
    body = drafted.model_dump(mode="json")
    body["confidence"] = 0.42

    def fake_invoke(_call):
        return json.dumps(body)

    monkeypatch.setenv("BEDROCK_CALLS", "1")
    monkeypatch.setattr("services.agents.personas.llm.invoke", fake_invoke)
    updated = apply_model(drafted, call_for(drafted), FireAssessment)
    assert updated.confidence == 0.42
    assert updated.firms_confidence == "low"


def test_invoke_refuses_without_the_switch():
    from services.agents.personas.llm import PersonaCall

    call = PersonaCall("fire_ops", "PERSONA_MODEL_ID", "system", "user")
    with pytest.raises(RuntimeError, match="Bedrock calls are off"):
        invoke(call)
