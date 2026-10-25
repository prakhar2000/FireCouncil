"""Fire Ops reads the replay snapshot. A model call replaces it only when BEDROCK_CALLS=1."""

import json
import os

from services.agents.firms import nearest_hotspot
from services.agents.personas.llm import PersonaCall
from services.agents.replay import Cycle, Replay
from services.agents.schemas import FireAssessment
from services.vision.cv.goes_track import track_masks

_SYSTEM = """You are the Fire Ops analyst on a wildfire warning desk.

Your job is to review a measured fire picture for a human duty officer. You do not speak to the public, you do not choose a road, and you do not order an evacuation. Another person approves every warning. Your review is advisory.

What you are given was already measured:
- Smoke comes from OpenCV on fixed camera frames. smoke_confirmed is that result. Do not invent a plume the camera did not mark.
- Spread comes from the tracker. spread_kmh and spread_bearing_deg are null when speed was not measured. When they are numbers, the tracker measured them. Leave them as they are. Do not copy a compass guess, and do not write a speed in km/h from memory.
- The NASA FIRMS line is a separate hotspot, not a speed. firms_confidence is either a word (low, nominal, high) or a percent already written as text. Do not turn a word into a percent. Do not swap in a farther hotspot because its confidence looks higher. firms_distance_km and firms_satellite stay as given.
- eta_min_by_zone is the replay clock for named zones. Do not add a zone and do not change an ETA.
- evidence_ids are the artifacts you may cite. Do not invent an id.

How to judge:
- Raise or lower confidence between 0 and 1. Confidence is how usable this picture is for the duty officer, not a promise that a place will burn.
- A NASA hotspot with confidence low still counts as detected. Say so by leaving firms_detected true. Low means the pixel is weak, not that you should hide it.
- If smoke is confirmed and a hotspot is near the focus point, the picture is usable even when speed was not measured.
- If smoke is not confirmed and no hotspot is present, lower confidence.

Return one JSON object and no other text. Keep every key that was in the draft: incident_id, front_geojson, spread_bearing_deg, spread_kmh, eta_min_by_zone, smoke_confirmed, firms_detected, firms_confidence, firms_distance_km, firms_satellite, confidence, evidence_ids. You may change confidence. Leave the measured fields as they were.
"""


def propose(replay: Replay, cycle: Cycle) -> FireAssessment:
    """Build a fire assessment. A model call replaces it only when BEDROCK_CALLS=1."""
    drafted = _from_replay(replay, cycle)
    from services.agents.personas.llm import apply_model

    return apply_model(drafted, call_for(drafted), FireAssessment)


def call_for(assessment: FireAssessment) -> PersonaCall:
    """The Fire Ops request. The replay does not send it."""
    return PersonaCall(
        persona="fire_ops",
        model_id_env="PERSONA_MODEL_ID",
        system=_SYSTEM,
        user=(
            "Duty-officer packet. These fields were measured. "
            "Review them under your Fire Ops rules and return the full JSON object.\n"
            + json.dumps(assessment.model_dump(mode="json"), sort_keys=True)
        ),
    )


def _from_replay(replay: Replay, cycle: Cycle) -> FireAssessment:
    bearing, speed = _spread(replay)
    hotspot = None
    if replay.focus_lat is not None and replay.focus_lon is not None and replay.firms_csvs:
        hotspot = nearest_hotspot(replay.firms_csvs, replay.focus_lat, replay.focus_lon, cycle.ts[:10])
    return FireAssessment(
        incident_id=replay.incident_id,
        front_geojson=None,
        spread_bearing_deg=bearing,
        spread_kmh=speed,
        eta_min_by_zone={zone.zone_id: zone.eta_min for zone in replay.zones},
        smoke_confirmed=replay.smoke_confirmed,
        firms_detected=None if not replay.firms_csvs else hotspot is not None,
        firms_confidence=None if hotspot is None else hotspot.confidence,
        firms_distance_km=None if hotspot is None else hotspot.distance_km,
        firms_satellite=None if hotspot is None else hotspot.satellite,
        confidence=0.8,
        evidence_ids=[route.evidence_id for route in cycle.routes if route.evidence_id],
    )


def _spread(replay: Replay) -> tuple[float | None, float | None]:
    """Use the satellite tracker when masks exist. The YAML speed is not a measurement."""
    if replay.goes_masks and replay.km_per_pixel is not None:
        tracked = track_masks(replay.goes_masks, replay.km_per_pixel)
        return tracked["bearing_deg"], tracked["speed_kmh"]
    if os.environ.get("PLUME_SPEED") == "1":
        from services.vision.cv.plume_speed import measure_fairview

        measured = measure_fairview()
        if measured is not None:
            return measured["bearing_deg"], measured["speed_kmh"]
    return None, None
