"""The route_block file matches the scenario the rules are locked to."""

from services.agents.personas.evac_traffic import propose
from services.agents.replay import load_replay


def test_route_block_cycles_and_etas():
    replay = load_replay("route_block")
    assert replay.incident_id == "norte-replay"
    assert [zone.eta_min for zone in replay.zones] == [45, 180]
    assert replay.zone_map()["capistrano"] == "none"
    assert len(replay.cycles) == 2
    assert replay.cycles[0].routes[0].route_id == "sr74"
    assert replay.cycles[0].routes[0].status == "clear"
    assert replay.cycles[1].routes[0].status == "blocked"
    assert len(replay.cycles[1].frames["sr74"]) == 4
    assert replay.care_sites[0]["id"] == "care-1"
    assert replay.residents[0]["vulnerable"] is True


def test_opencv_marks_the_second_camera_blocked():
    replay = load_replay("route_block")
    second = propose(replay, replay.cycles[1])
    statuses = {route.route_id: route.status for route in second.routes}
    assert statuses["sr74"] == "blocked"
    assert statuses["i5"] == "slow"
    assert second.recommended_route == "sr74"
