"""Turn an approved-for-draft plan into English and Spanish messages."""

import os

from services.agents.replay import Replay
from services.agents.schemas import ActionPlan, DraftMessage, RouteStatus
from services.notify.templates.messages import compass, render

_OFFICIAL = "https://www.fire.ca.gov/incidents"


def draft(
    replay: Replay,
    plan: ActionPlan,
    cycle_ts: str,
    routes: list[RouteStatus],
) -> list[DraftMessage]:
    """Write en and es for every zone the rules chose to warn."""
    route_status = "unknown"
    evidence_url = None
    for route in routes:
        if route.route_id == plan.route:
            route_status = route.status
            evidence_url = f"data/local/evidence/{route.evidence_id}.png" if route.evidence_id else None
    direction = compass(_bearing(replay))
    messages: list[DraftMessage] = []
    for zone_id in plan.zones_to_warn:
        official = _official_status(replay, zone_id)
        for lang in ("en", "es"):
            messages.append(
                render(
                    plan,
                    zone_id,
                    replay.zone_name(zone_id),
                    lang,
                    cycle_ts,
                    evidence_url,
                    f"http://localhost:8080/ack/{replay.incident_id}/{cycle_ts}/{zone_id}",
                    _OFFICIAL,
                    eta_min=replay.eta(zone_id),
                    direction=direction,
                    route_status=route_status,
                    official_status=official,
                )
            )
    return messages


def _bearing(replay: Replay) -> float:
    """Use the measured plume bearing when the tracker ran. The YAML figure is not a measurement."""
    if os.environ.get("PLUME_SPEED") == "1":
        from services.vision.cv.plume_speed import measure_fairview

        measured = measure_fairview()
        if measured is not None and measured.get("bearing_deg") is not None:
            return float(measured["bearing_deg"])
    return replay.spread_bearing_deg


def _official_status(replay: Replay, zone_id: str) -> str:
    for zone in replay.zones:
        if zone.zone_id == zone_id:
            return zone.official_status
    return "none"
