"""Merge persona assessments. Rules replace this draft."""

from services.agents.schemas import (
    ActionPlan,
    EvacAssessment,
    FireAssessment,
    HealthAssessment,
)


def merge(fire: FireAssessment, evac: EvacAssessment, health: HealthAssessment) -> ActionPlan:
    """Copy the persona fields into a draft plan."""
    return ActionPlan(
        zones_to_warn=list(evac.gap_zones),
        urgency="advisory",
        route=evac.recommended_route,
        care_sites_first=[site["id"] for site in health.priority_sites],
        conflicts=[],
        rule_hits=[],
        rationale="Planner draft from the three assessments.",
        evidence_ids=list(fire.evidence_ids),
    )
