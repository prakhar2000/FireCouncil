"""Approve, edit, or reject a stored decision. Approve writes the local outbox."""

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel

from services.agents.orchestrator import run_replay
from services.agents.replay import load_replay
from services.agents.store import JsonStore
from services.api.dashboard import approval_view, render_dashboard
from services.notify.dispatcher import dispatch, kill_switch_on

_DEFAULT_STORE = Path("data/local/decisions.json")
_DEFAULT_OUTBOX = Path("data/local/outbox.jsonl")
_EVIDENCE = Path("data/local/evidence")


class EditBody(BaseModel):
    route: str | None = None
    zones_to_warn: list[str] | None = None


def seed_if_empty(store: JsonStore, name: str = "route_block") -> None:
    """Run the replay once so the approval page has a decision to show."""
    replay = load_replay(name)
    if store.list_decisions(replay.incident_id):
        return
    for decision in run_replay(name):
        store.save_decision(decision)
    store.save_residents(replay.residents)


def create_app(store: JsonStore, outbox_path: Path | None = None, seed: bool = False) -> FastAPI:
    """Build the approval API against a JSON store."""
    outbox = outbox_path or _DEFAULT_OUTBOX

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if seed:
            seed_if_empty(store)
        yield

    app = FastAPI(title="FireCouncil decisions", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        from services.agents.review import ensure_graviton, hold_warning

        if hold_warning():
            ensure_graviton()
        current, previous = _latest(store)
        if current is not None and current.status in {"APPROVED", "REJECTED"}:
            current.status = "PENDING_APPROVAL"
            store.save_decision(current)
        return render_dashboard(current, previous, _outbox_rows(outbox))

    @app.post("/replay/{name}")
    def replay(name: str) -> RedirectResponse:
        loaded = load_replay(name)
        for decision in run_replay(name):
            store.save_decision(decision)
        store.save_residents(loaded.residents)
        outbox.write_text("")
        return RedirectResponse("/", status_code=303)

    @app.get("/evidence/{name}")
    def evidence(name: str) -> FileResponse:
        if Path(name).name != name or not name.endswith(".png"):
            raise HTTPException(status_code=404, detail="evidence not found")
        path = _EVIDENCE / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="evidence not found")
        return FileResponse(path)

    @app.get("/decisions/{incident_id}")
    def list_decisions(incident_id: str) -> list[dict]:
        decisions = store.list_decisions(incident_id)
        decisions.sort(key=lambda item: item.cycle_ts, reverse=True)
        return [item.model_dump(mode="json") for item in decisions]

    @app.post("/decisions/{incident_id}/{cycle_ts}/approve")
    def approve(incident_id: str, cycle_ts: str) -> dict:
        decision = _require(store, incident_id, cycle_ts)
        decision.status = "APPROVED"
        store.save_decision(decision)
        rows = dispatch(decision, store.residents(), kill_switch_on(), outbox)
        payload = approval_view(decision, rows)
        payload["sent"] = len(rows)
        return payload

    @app.post("/decisions/{incident_id}/{cycle_ts}/reject")
    def reject(incident_id: str, cycle_ts: str) -> dict:
        decision = _require(store, incident_id, cycle_ts)
        decision.status = "REJECTED"
        store.save_decision(decision)
        return approval_view(decision, [])

    @app.post("/decisions/{incident_id}/{cycle_ts}/edit")
    def edit(incident_id: str, cycle_ts: str, body: EditBody) -> dict:
        decision = _require(store, incident_id, cycle_ts)
        if body.route is not None:
            decision.plan.route = body.route
        if body.zones_to_warn is not None:
            decision.plan.zones_to_warn = body.zones_to_warn
        decision.status = "PENDING_APPROVAL"
        store.save_decision(decision)
        return decision.model_dump(mode="json")

    return app


def _latest(store: JsonStore):
    grouped: dict[str, list] = {}
    if not store.path.exists():
        return None, None
    raw = json.loads(store.path.read_text() or "{}")
    for item in raw.get("decisions", []):
        grouped.setdefault(item["incident_id"], []).append(item)
    if not grouped:
        return None, None
    incident_id = next(iter(grouped))
    decisions = store.list_decisions(incident_id)
    decisions.sort(key=lambda item: item.cycle_ts)
    previous = decisions[-2] if len(decisions) > 1 else None
    return decisions[-1], previous


def _outbox_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _require(store: JsonStore, incident_id: str, cycle_ts: str):
    for decision in store.list_decisions(incident_id):
        if decision.cycle_ts == cycle_ts:
            return decision
    raise HTTPException(status_code=404, detail="decision not found")


app = create_app(JsonStore(_DEFAULT_STORE), seed=True)
