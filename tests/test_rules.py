"""Rule coverage for the route_block scenario and the edge cases."""

from services.agents.rules import apply
from services.agents.schemas import (
    EvacAssessment,
    FireAssessment,
    HealthAssessment,
    RouteStatus,
)


def _fire(**overrides) -> FireAssessment:
    payload = {
        "incident_id": "norte-replay",
        "spread_bearing_deg": 45,
        "spread_kmh": 3.0,
        "eta_min_by_zone": {"capistrano": 45, "san_clemente": 180},
        "smoke_confirmed": True,
        "confidence": 0.8,
        "evidence_ids": ["goes-1"],
    }
    payload.update(overrides)
    return FireAssessment(**payload)


def _route(route_id: str, status: str, age_s: int, evidence_id: str) -> RouteStatus:
    return RouteStatus(
        route_id=route_id,
        status=status,
        vehicles=4,
        stalled_ratio=0.1,
        haze_score=0.1,
        evidence_id=evidence_id,
        age_s=age_s,
    )


def _evac(routes: list[RouteStatus], recommended: str | None, gaps: list[str] | None = None) -> EvacAssessment:
    return EvacAssessment(
        gap_zones=gaps if gaps is not None else ["capistrano"],
        routes=routes,
        recommended_route=recommended,
        confidence=0.7,
    )


def _health() -> HealthAssessment:
    return HealthAssessment(
        priority_sites=[{"id": "care-1", "zone_id": "capistrano", "name": "Demo Care"}],
        assisted_evac_zones=["capistrano"],
        guidance=["Bring medications."],
        confidence=0.7,
    )


_ZONES = {"capistrano": "none", "san_clemente": "advisory"}
_CARE = [{"id": "care-1", "zone_id": "capistrano", "name": "Demo Care"}]


def test_cycle_one_warns_capistrano_via_sr74():
    routes = [_route("sr74", "clear", 60, "ev-sr74-1"), _route("i5", "slow", 60, "ev-i5-1")]
    plan = apply(_fire(), _evac(routes, "sr74"), _health(), _ZONES, _CARE)
    assert plan.zones_to_warn == ["capistrano"]
    assert plan.urgency == "urgent"
    assert plan.route == "sr74"
    assert plan.care_sites_first == ["care-1"]
    assert "ev-sr74-1" in plan.evidence_ids


def test_cycle_two_switches_to_i5_when_sr74_is_blocked():
    routes = [_route("sr74", "blocked", 30, "ev-sr74-2"), _route("i5", "slow", 30, "ev-i5-2")]
    plan = apply(_fire(), _evac(routes, "sr74"), _health(), _ZONES, _CARE)
    assert plan.route == "i5"
    assert "R4" in plan.rule_hits
    assert "R8" in plan.rule_hits


def test_order_zone_is_not_a_gap():
    fire = _fire(eta_min_by_zone={"west": 20})
    plan = apply(fire, _evac([], None, gaps=["west"]), _health(), {"west": "order"}, [])
    assert plan.zones_to_warn == []
    assert "R5" in plan.rule_hits


def test_stale_evidence_drops_the_route():
    routes = [_route("sr74", "clear", 700, "ev-old")]
    plan = apply(_fire(), _evac(routes, "sr74"), _health(), _ZONES, _CARE)
    assert plan.route is None
    assert "route unknown — follow officials" in plan.rationale


def test_smoke_without_etas_warns_nobody():
    fire = _fire(eta_min_by_zone={}, smoke_confirmed=True)
    plan = apply(fire, _evac([], None, gaps=[]), _health(), {}, [])
    assert plan.zones_to_warn == []
    assert "R7" in plan.rule_hits


def test_care_site_sorts_ahead_of_a_sooner_zone():
    fire = _fire(eta_min_by_zone={"soon": 30, "capistrano": 50})
    zones = {"soon": "none", "capistrano": "none"}
    plan = apply(fire, _evac([], None, gaps=[]), _health(), zones, _CARE)
    assert plan.zones_to_warn[0] == "capistrano"
