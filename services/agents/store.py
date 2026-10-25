"""JSON file store. Tests pass a temporary directory."""

import json
from pathlib import Path
from typing import Protocol

from services.agents.schemas import Decision


class Store(Protocol):
    def save_decision(self, decision: Decision) -> None: ...

    def list_decisions(self, incident_id: str) -> list[Decision]: ...


class JsonStore:
    """Decisions, residents, and acks in one JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def save_decision(self, decision: Decision) -> None:
        payload = self._read()
        rows = [row for row in payload["decisions"] if not _same(row, decision)]
        rows.append(decision.model_dump(mode="json"))
        payload["decisions"] = rows
        self._write(payload)

    def list_decisions(self, incident_id: str) -> list[Decision]:
        payload = self._read()
        return [
            Decision.model_validate(row)
            for row in payload["decisions"]
            if row["incident_id"] == incident_id
        ]

    def save_residents(self, residents: list[dict]) -> None:
        payload = self._read()
        payload["residents"] = residents
        self._write(payload)

    def residents(self) -> list[dict]:
        return list(self._read()["residents"])

    def save_ack(self, decision_id: str, resident_id: str, ack: dict) -> None:
        payload = self._read()
        payload["acks"][f"{decision_id}:{resident_id}"] = ack
        self._write(payload)

    def get_ack(self, decision_id: str, resident_id: str) -> dict | None:
        return self._read()["acks"].get(f"{decision_id}:{resident_id}")

    def _read(self) -> dict:
        if not self.path.exists():
            return {"decisions": [], "residents": [], "acks": {}}
        return json.loads(self.path.read_text())

    def _write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2))


def _same(row: dict, decision: Decision) -> bool:
    return row["incident_id"] == decision.incident_id and row["cycle_ts"] == decision.cycle_ts
