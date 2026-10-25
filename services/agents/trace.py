"""Append one JSON object per line for a decision cycle."""

import json
import os
from pathlib import Path

from services.vision.cv.runtime import runtime_info

REPO_ROOT = Path(__file__).resolve().parents[2]


def trace_directory() -> Path:
    """Folder for cycle traces. Tests point this at a temp directory."""
    return Path(os.environ.get("FC_TRACE_DIR", REPO_ROOT / "docs" / "traces"))


def start_cycle(incident_id: str, cycle_ts: str, directory: Path | None = None) -> Path:
    """Create an empty trace file for this cycle."""
    path = _path(incident_id, cycle_ts, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


def append(incident_id: str, cycle_ts: str, event: dict, directory: Path | None = None) -> None:
    """Write one event. Tool events include the OpenCV runtime."""
    path = _path(incident_id, cycle_ts, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(event)
    if row.get("type") == "tool":
        row.setdefault("runtime", runtime_info())
    with path.open("a") as handle:
        handle.write(json.dumps(row) + "\n")


def _path(incident_id: str, cycle_ts: str, directory: Path | None) -> Path:
    safe_ts = cycle_ts.replace(":", "-")
    return (directory or trace_directory()) / incident_id / f"{safe_ts}.jsonl"
