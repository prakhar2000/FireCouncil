"""Evacuation and Traffic. The first listed road is the persona's pick.

Rules may replace that pick when the road is blocked or the evidence is stale.
When a route lists camera frames, OpenCV replaces the status written in the replay.
A model call replaces the draft only when BEDROCK_CALLS=1.
"""

import json
from pathlib import Path

from services.agents.personas.llm import PersonaCall
from services.agents.replay import Cycle, Replay
from services.agents.schemas import EvacAssessment, RouteStatus
from services.vision.cv.route_status import status_for_frames

_SYSTEM = """You are the Evacuation and Traffic analyst on a wildfire warning desk.

Your job is to review the roads a duty officer might name in a warning. You do not order an evacuation. You do not estimate how fast the fire is moving. A later rules check has the last word, and a human still has to approve the warning.

What you are given was already measured:
- Each road has a status from OpenCV on recent camera frames: clear, slow, blocked, or unknown. vehicles, stalled_ratio, and haze_score come from those frames. Do not change them. Do not override a blocked road by marking it clear.
- age_s is how old that camera look is. evidence_id is the frame set. Leave both as given.
- gap_zones are places with a short ETA and no official evacuation order yet. Do not add a zone that is not listed.
- recommended_route is the road this desk would name. The list order is the preference order.

How to judge:
- If the current recommended road is blocked, choose the next road in the list whose status is not blocked.
- If no listed road is clear or slow, keep the first road and lower confidence. Do not invent a road name.
- Do not prefer a road that is missing from routes.
- Confidence is how usable the camera picture is, from 0 to 1. Fresh frames and a road that is not blocked support a higher confidence. A blocked road as the only option supports a lower one.

Return one JSON object and no other text. Keep every key: gap_zones, routes, recommended_route, confidence. Each route keeps route_id, status, vehicles, stalled_ratio, haze_score, evidence_id, and age_s. You may change recommended_route and confidence. Leave every camera measurement as it was.
"""

_EVIDENCE = Path("data/local/evidence")


def propose(replay: Replay, cycle: Cycle) -> EvacAssessment:
    """Propose gaps from ETA and recommend the first road in the cycle."""
    gaps = [
        zone.zone_id
        for zone in replay.zones
        if zone.eta_min <= 120 and zone.official_status in {"none", "advisory"}
    ]
    routes = [_with_vision(route, cycle.frames.get(route.route_id, [])) for route in cycle.routes]
    recommended = routes[0].route_id if routes else None
    drafted = EvacAssessment(
        gap_zones=gaps,
        routes=routes,
        recommended_route=recommended,
        confidence=0.75,
    )
    from services.agents.personas.llm import apply_model

    return apply_model(drafted, call_for(drafted), EvacAssessment)


def call_for(assessment: EvacAssessment) -> PersonaCall:
    """The evacuation request. The replay does not send it."""
    return PersonaCall(
        persona="evac_traffic",
        model_id_env="PERSONA_MODEL_ID",
        system=_SYSTEM,
        user=(
            "Duty-officer packet. Camera status is already filled in. "
            "Review the roads under your traffic rules and return the full JSON object.\n"
            + json.dumps(assessment.model_dump(mode="json"), sort_keys=True)
        ),
    )


def _with_vision(route: RouteStatus, frames: list[str]) -> RouteStatus:
    if not frames:
        return route
    seen = status_for_frames(
        route.route_id,
        frames,
        evidence_dir=_EVIDENCE,
        age_s=route.age_s,
        evidence_id=route.evidence_id,
    )
    return route.model_copy(
        update={
            "status": seen.status,
            "vehicles": seen.vehicles,
            "stalled_ratio": seen.stalled_ratio,
            "haze_score": seen.haze_score,
        }
    )
