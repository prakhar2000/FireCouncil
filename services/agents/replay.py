"""Load a replay YAML into the objects the orchestrator runs."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from services.agents.schemas import RouteStatus

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Zone:
    zone_id: str
    name: str
    eta_min: int
    official_status: str


@dataclass
class Cycle:
    ts: str
    routes: list[RouteStatus]
    frames: dict[str, list[str]]


@dataclass
class Replay:
    name: str
    incident_id: str
    zones: list[Zone]
    care_sites: list[dict]
    residents: list[dict]
    spread_bearing_deg: float
    spread_kmh: float
    smoke_confirmed: bool
    cycles: list[Cycle]
    firms_csvs: list[str]
    focus_lat: float | None = None
    focus_lon: float | None = None
    goes_masks: list[str] | None = None
    km_per_pixel: float | None = None

    def zone_map(self) -> dict[str, str]:
        return {zone.zone_id: zone.official_status for zone in self.zones}

    def zone_name(self, zone_id: str) -> str:
        for zone in self.zones:
            if zone.zone_id == zone_id:
                return zone.name
        return zone_id

    def eta(self, zone_id: str) -> int | None:
        for zone in self.zones:
            if zone.zone_id == zone_id:
                return zone.eta_min
        return None


def load_replay(name: str, root: Path | None = None) -> Replay:
    """Read ``data/replays/<name>.yaml``."""
    path = (root or REPO_ROOT) / "data" / "replays" / f"{name}.yaml"
    raw = yaml.safe_load(path.read_text())
    zones = [
        Zone(
            zone_id=zone_id,
            name=body["name"],
            eta_min=int(body["eta_min"]),
            official_status=body["official_status"],
        )
        for zone_id, body in raw["zones"].items()
    ]
    base = root or REPO_ROOT
    cycles = []
    for cycle in raw["cycles"]:
        routes = []
        frames: dict[str, list[str]] = {}
        for route_id, fields in cycle["routes"].items():
            raw_fields = dict(fields)
            listed = raw_fields.pop("frames", [])
            routes.append(RouteStatus(route_id=route_id, **raw_fields))
            if listed:
                frames[route_id] = [str(base / relative) for relative in listed]
        cycles.append(Cycle(ts=cycle["ts"], routes=routes, frames=frames))
    return Replay(
        name=raw["name"],
        incident_id=raw["incident_id"],
        zones=zones,
        care_sites=list(raw["care_sites"]),
        residents=list(raw["residents"]),
        spread_bearing_deg=float(raw["spread_bearing_deg"]),
        spread_kmh=float(raw["spread_kmh"]),
        smoke_confirmed=bool(raw["smoke_confirmed"]),
        cycles=cycles,
        firms_csvs=[str(base / relative) for relative in raw.get("firms_csvs", [])],
        focus_lat=raw.get("focus_lat"),
        focus_lon=raw.get("focus_lon"),
        goes_masks=[str(base / relative) for relative in raw.get("goes_masks", [])],
        km_per_pixel=raw.get("km_per_pixel"),
    )
