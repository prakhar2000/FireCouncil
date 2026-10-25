"""Public Health lists care sites and zones that have a vulnerable resident.

A model call replaces the draft only when BEDROCK_CALLS=1.
"""

import json

from services.agents.personas.llm import PersonaCall
from services.agents.replay import Replay
from services.agents.schemas import HealthAssessment

_SYSTEM = """You are the Public Health analyst on a wildfire warning desk.

Your job is to say who needs extra help if a warning is sent. You do not choose a road, you do not estimate fire spread, and you do not order an evacuation. A human duty officer approves the warning. Your note is for that officer and for the people who need more than a general message.

What you are given was already listed:
- priority_sites are care sites already in the incident. Each has an id, a zone_id, and a name. Do not invent a hospital, a shelter, or a phone number.
- assisted_evac_zones are zones that already have a vulnerable resident. Do not add a zone because it sounds close to the fire. Do not drop a zone that has a vulnerable resident.
- guidance is the practical note those residents should receive. It may mention medications, a written care plan, and a caregiver. Keep it short enough to send. Do not promise a pickup time, a bus, or a safe destination.

How to judge:
- If a care site sits in an assisted zone, mention that site by the name already in the draft.
- If a zone is listed as assisted, the guidance must still tell a vulnerable resident to bring medications and a written care plan.
- Confidence is how complete this care picture is, from 0 to 1. A named site plus a vulnerable zone is a usable picture. An empty site list means you should lower confidence, not fill the gap with a guessed facility.

Return one JSON object and no other text. Keep every key: priority_sites, assisted_evac_zones, guidance, confidence. You may rewrite guidance and change confidence. Leave the sites and the assisted zones as they were given.
"""


def propose(replay: Replay) -> HealthAssessment:
    """Care sites in the replay, and zones that need assisted evacuation."""
    assisted = sorted({person["zone_id"] for person in replay.residents if person.get("vulnerable")})
    drafted = HealthAssessment(
        priority_sites=list(replay.care_sites),
        assisted_evac_zones=assisted,
        guidance=["Bring medications and a written care plan."],
        confidence=0.7,
    )
    from services.agents.personas.llm import apply_model

    return apply_model(drafted, call_for(drafted), HealthAssessment)


def call_for(assessment: HealthAssessment) -> PersonaCall:
    """The public-health request. The replay does not send it."""
    return PersonaCall(
        persona="public_health",
        model_id_env="PERSONA_MODEL_ID",
        system=_SYSTEM,
        user=(
            "Duty-officer packet. Care sites and assisted zones are already listed. "
            "Review them under your public-health rules and return the full JSON object.\n"
            + json.dumps(assessment.model_dump(mode="json"), sort_keys=True)
        ),
    )
