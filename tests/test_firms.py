"""Saved FIRMS rows. This test does not call NASA."""

from services.agents.firms import nearest_hotspot

_ROOT = "data/fixtures/firms"
_FILES = [
    f"{_ROOT}/2026-10-16-viirs-noaa20.csv",
    f"{_ROOT}/2026-10-16-modis.csv",
]


def test_nearest_saved_hotspot_is_low_confidence_near_capistrano():
    hotspot = nearest_hotspot(_FILES, 33.5017, -117.6628, "2026-10-16")
    assert hotspot is not None
    assert hotspot.confidence == "low"
    assert hotspot.distance_km < 5
    assert hotspot.satellite == "VIIRS NOAA-20"
    assert hotspot.acquired == "2026-10-16"


def test_a_different_day_has_no_saved_hotspot():
    assert nearest_hotspot(_FILES, 33.5017, -117.6628, "2026-01-01") is None
