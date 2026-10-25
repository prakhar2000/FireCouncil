"""Measure the plume, then ask the three reviewers. Run this on the COOL machine."""

import json
import os
from pathlib import Path

from services.agents.orchestrator import run_replay
from services.vision.cv.plume_speed import measure_fairview
from services.vision.cv.runtime import runtime_info


def main() -> None:
    os.environ["PLUME_SPEED"] = "1"
    decisions = list(run_replay("route_block"))
    measured = measure_fairview()
    if measured is not None:
        for decision in decisions:
            decision.fire.spread_kmh = measured["speed_kmh"]
            decision.fire.spread_bearing_deg = measured["bearing_deg"]
    latest = decisions[-1]
    out = Path("data/local")
    out.mkdir(parents=True, exist_ok=True)
    (out / "graviton-decisions.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in decisions], indent=2)
    )
    info = runtime_info()
    (out / "cool_verify.json").write_text(
        json.dumps(
            {
                "cv2_version": info.get("cv2_version"),
                "cv2_path": info.get("cv2_path"),
                "host_arch": info.get("host_arch"),
                "spread_kmh": latest.fire.spread_kmh,
                "spread_bearing_deg": latest.fire.spread_bearing_deg,
                "status": latest.status,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
