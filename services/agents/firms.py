"""Read a saved NASA FIRMS file. Tests and the page never call NASA."""

import csv
import math
from dataclasses import dataclass
from pathlib import Path

_CONFIDENCE = {
    "l": "low",
    "n": "nominal",
    "h": "high",
    "low": "low",
    "nominal": "nominal",
    "high": "high",
}
_SATELLITE = {
    "N20": "NOAA-20",
    "N21": "NOAA-21",
    "N": "Suomi NPP",
}


@dataclass(frozen=True)
class Hotspot:
    """One saved detection, with confidence copied from the file."""

    confidence: str
    distance_km: float
    satellite: str
    acquired: str


def nearest_hotspot(
    paths: list[str],
    latitude: float,
    longitude: float,
    on_date: str,
) -> Hotspot | None:
    """Return the closest hotspot on ``on_date``, or None when the files have none."""
    best: Hotspot | None = None
    for path in paths:
        for row in _rows(Path(path)):
            if row.get("acq_date") != on_date:
                continue
            distance = _kilometers(
                latitude,
                longitude,
                float(row["latitude"]),
                float(row["longitude"]),
            )
            if best is not None and distance >= best.distance_km:
                continue
            best = Hotspot(
                confidence=_confidence(row.get("confidence", "")),
                distance_km=round(distance, 1),
                satellite=_satellite(row),
                acquired=row["acq_date"],
            )
    return best


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _confidence(raw: str) -> str:
    label = _CONFIDENCE.get(raw.strip().lower())
    if label:
        return label
    if raw.strip().isdigit():
        return f"{int(raw)}%"
    return raw.strip()


def _satellite(row: dict[str, str]) -> str:
    instrument = row.get("instrument", "").strip()
    name = _SATELLITE.get(row.get("satellite", "").strip(), row.get("satellite", "").strip())
    return " ".join(part for part in (instrument, name) if part)


def _kilometers(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    chord = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(chord))
