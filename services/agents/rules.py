"""Deterministic decision rules. These override persona proposals."""

from services.agents.schemas import (
    ActionPlan,
    EvacAssessment,
    FireAssessment,
    HealthAssessment,
    RouteStatus,
)

_ROUTE_MAX_AGE_S = 600


def apply(
    fire: FireAssessment,
    evac: EvacAssessment,
    health: HealthAssessment,
    zones: dict[str, str],
    care_sites: list[dict],
) -> ActionPlan:
    """Return the plan the rules require.

    ``zones`` maps zone id to official status. ``care_sites`` items have
    ``id``, ``zone_id``, and ``name``.
    """
    hits: list[str] = []
    if not fire.eta_min_by_zone and fire.smoke_confirmed:
        _hit(hits, "R7")
        return ActionPlan(
            zones_to_warn=[],
            urgency="advisory",
            route=None,
            care_sites_first=[],
            conflicts=[],
            rule_hits=hits,
            rationale="Smoke only. Health guidance only.",
            evidence_ids=list(fire.evidence_ids),
        )

    gaps: list[str] = []
    for zone_id, eta in fire.eta_min_by_zone.items():
        status = zones.get(zone_id, "none")
        if status == "order":
            _hit(hits, "R5")
            continue
        if eta <= 120 and status in {"none", "advisory"}:
            gaps.append(zone_id)
    if gaps:
        _hit(hits, "R2")

    care_zones = {site["zone_id"] for site in care_sites}
    vulnerable = set(health.assisted_evac_zones)
    if any(zone_id in care_zones or zone_id in vulnerable for zone_id in gaps):
        _hit(hits, "R1")
    zones_to_warn = sorted(gaps, key=lambda zone_id: _life_key(zone_id, fire, care_zones, vulnerable))

    urgency: str = "advisory"
    if zones_to_warn:
        _hit(hits, "R3")
        if any(fire.eta_min_by_zone.get(zone_id, 10_000) <= 60 for zone_id in zones_to_warn):
            urgency = "urgent"

    chosen, chosen_status = _choose_route(evac.routes)
    _hit(hits, "R4")
    rationale = f"Warn {', '.join(zones_to_warn) or 'nobody'}. Route {chosen or 'none'}."
    if chosen is None:
        rationale = f"{rationale} route unknown — follow officials"

    care_first = [site["id"] for site in care_sites if site["zone_id"] in set(gaps)]
    if care_first:
        _hit(hits, "R6")

    conflicts: list[str] = []
    if set(evac.gap_zones) != set(gaps):
        conflicts.append(
            f"Evac gap zones {sorted(evac.gap_zones)} differ from rules {sorted(gaps)}; R2 resolved it"
        )
        _hit(hits, "R8")
    if evac.recommended_route != chosen:
        conflicts.append(
            f"Evac route {evac.recommended_route} differs from rules {chosen}; R4 resolved it"
        )
        _hit(hits, "R8")

    evidence = list(fire.evidence_ids)
    if chosen_status is not None and chosen_status.evidence_id:
        evidence.append(chosen_status.evidence_id)

    return ActionPlan(
        zones_to_warn=zones_to_warn,
        urgency=urgency,  # type: ignore[arg-type]
        route=chosen,
        care_sites_first=care_first,
        conflicts=conflicts,
        rule_hits=hits,
        rationale=rationale,
        evidence_ids=evidence,
    )


def _life_key(
    zone_id: str,
    fire: FireAssessment,
    care_zones: set[str],
    vulnerable: set[str],
) -> tuple[int, int]:
    life_first = 0 if zone_id in care_zones or zone_id in vulnerable else 1
    return (life_first, fire.eta_min_by_zone.get(zone_id, 10_000))


def _choose_route(routes: list[RouteStatus]) -> tuple[str | None, RouteStatus | None]:
    usable = [route for route in routes if route.status in {"clear", "slow"} and route.age_s <= _ROUTE_MAX_AGE_S]
    usable.sort(key=lambda route: (0 if route.status == "clear" else 1, route.age_s))
    if not usable:
        return None, None
    return usable[0].route_id, usable[0]


def _hit(hits: list[str], rule_id: str) -> None:
    if rule_id not in hits:
        hits.append(rule_id)
