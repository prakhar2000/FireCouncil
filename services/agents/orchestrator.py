"""Run one replay cycle: personas, rules, drafts, then a pending decision."""

import argparse
import json
import os
import time

from services.agents.personas.evac_traffic import call_for as evac_call
from services.agents.personas.evac_traffic import propose as propose_evac
from services.agents.personas.fire_ops import call_for as fire_call
from services.agents.personas.fire_ops import propose as propose_fire
from services.agents.personas.planner import merge
from services.agents.personas.public_health import call_for as health_call
from services.agents.personas.public_health import propose as propose_health
from services.agents.personas.public_info import draft
from services.agents.replay import Cycle, Replay, load_replay
from services.agents.rules import apply
from services.agents.schemas import Decision
from services.agents.trace import append, start_cycle, trace_directory


def run_cycle(replay: Replay, cycle: Cycle, previous: Decision | None) -> Decision:
    """Produce a pending decision. A previous pending decision becomes superseded."""
    directory = trace_directory()
    start_cycle(replay.incident_id, cycle.ts, directory)
    fire = _tool(replay, cycle.ts, "fire_ops", lambda: propose_fire(replay, cycle), directory)
    evac = _tool(replay, cycle.ts, "evac_traffic", lambda: propose_evac(replay, cycle), directory)
    health = _tool(replay, cycle.ts, "public_health", lambda: propose_health(replay), directory)
    for prepared in (fire_call(fire), evac_call(evac), health_call(health)):
        append(
            replay.incident_id,
            cycle.ts,
            {
                "type": "persona_call",
                "persona": prepared.persona,
                "invoked": os.environ.get("BEDROCK_CALLS") == "1",
            },
            directory,
        )
    draft_plan = merge(fire, evac, health)
    plan = apply(fire, evac, health, replay.zone_map(), replay.care_sites)
    append(
        replay.incident_id,
        cycle.ts,
        {"type": "planner", "route": draft_plan.route},
        directory,
    )
    append(
        replay.incident_id,
        cycle.ts,
        {"type": "rules", "rule_hits": plan.rule_hits, "route": plan.route},
        directory,
    )
    messages = draft(replay, plan, cycle.ts, cycle.routes)
    diff: dict = {}
    if previous is not None:
        diff = {
            "route": {"from": previous.plan.route, "to": plan.route},
            "zones_to_warn": {"from": list(previous.plan.zones_to_warn), "to": list(plan.zones_to_warn)},
        }
        previous.status = "SUPERSEDED"
        append(
            replay.incident_id,
            cycle.ts,
            {"type": "diff", "diff_from_prev": diff},
            directory,
        )
    _ = draft_plan
    return Decision(
        incident_id=replay.incident_id,
        cycle_ts=cycle.ts,
        fire=fire,
        evac=evac,
        health=health,
        plan=plan,
        messages=messages,
        status="PENDING_APPROVAL",
        diff_from_prev=diff,
    )


def run_replay(name: str) -> list[Decision]:
    """Run every cycle in a replay file. Earlier decisions are superseded."""
    replay = load_replay(name)
    decisions: list[Decision] = []
    previous: Decision | None = None
    for cycle in replay.cycles:
        decision = run_cycle(replay, cycle, previous)
        decisions.append(decision)
        previous = decision
    return decisions


def _tool(replay: Replay, cycle_ts: str, name: str, call, directory):
    started = time.perf_counter()
    result = call()
    elapsed = round((time.perf_counter() - started) * 1000, 3)
    evidence = getattr(result, "evidence_ids", None)
    append(
        replay.incident_id,
        cycle_ts,
        {
            "type": "tool",
            "name": name,
            "args": {"incident_id": replay.incident_id, "cycle_ts": cycle_ts},
            "latency_ms": elapsed,
            "evidence_id": evidence[0] if evidence else None,
        },
        directory,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local FireCouncil replay")
    parser.add_argument("--replay", required=True)
    args = parser.parse_args()
    decisions = run_replay(args.replay)
    print(json.dumps([decision.model_dump(mode="json") for decision in decisions], indent=2))


if __name__ == "__main__":
    main()
