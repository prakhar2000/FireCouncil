"""Vision detectors on saved fixtures."""

from pathlib import Path

import pytest

from services.vision.cv.goes_track import track_masks
from services.vision.cv.route_status import status_for_frames
from services.vision.cv.runtime import runtime_info
from services.vision.cv.smoke import check_frames
from tests.fixtures.build_fixtures import build

ROOT = Path(__file__).resolve().parent / "fixtures"


def setup_module() -> None:
    build()


def _frames(name: str) -> list[str]:
    return [str(path) for path in sorted((ROOT / "routes" / name).glob("*.png"))]


def test_runtime_is_opencv_5():
    info = runtime_info()
    assert info["cv2_version"].startswith("5.")
    assert info["cv2_path"]


def test_clear_and_blocked_routes():
    assert status_for_frames("clear-road", _frames("clear")).status == "clear"
    assert status_for_frames("blocked-road", _frames("blocked")).status == "blocked"


def test_flat_frames_are_unknown():
    assert status_for_frames("empty", _frames("unknown")).status == "unknown"


def test_goes_blob_moves_northeast():
    result = track_masks([str(ROOT / "goes" / "moving_blob.npz")], km_per_pixel=2.0)
    assert 0 < result["bearing_deg"] < 90
    # 16 px east and 16 px north, 2 km per pixel, two steps of 5 minutes.
    assert result["speed_kmh"] == 271.529
    assert result["front_geojson"]["type"] == "Polygon"
    assert result["runtime"]["cv2_version"].startswith("5.")


def test_speed_uses_the_time_step_you_pass():
    result = track_masks([str(ROOT / "goes" / "moving_blob.npz")], km_per_pixel=2.0, step_hours=1.0)
    assert result["speed_kmh"] == 22.627


def test_rising_smoke_scores_higher_than_a_static_frame():
    rise = [str(path) for path in sorted((ROOT / "smoke" / "rise").glob("*.png"))]
    still = [str(path) for path in sorted((ROOT / "smoke" / "static").glob("*.png"))]
    rising = check_frames(rise, azimuth_deg=180, hfov_deg=60, overlay_allowed=False)
    static = check_frames(still, azimuth_deg=180, hfov_deg=60, overlay_allowed=False)
    assert rising["smoke_prob"] > static["smoke_prob"]
    assert rising["bbox"] is not None


def test_figlib_plume_scores_as_smoke():
    folder = Path("data/raw/figlib/20160604_FIRE_rm-n-mobo-c")
    frames = sorted(folder.glob("*.jpg"))
    if len(frames) < 2:
        pytest.skip("local FIgLib sample is not downloaded")
    result = check_frames(
        [str(path) for path in frames],
        azimuth_deg=0,
        hfov_deg=90,
        evidence_dir=Path("data/local/evidence"),
    )
    assert result["smoke_prob"] >= 0.75
    assert result["bbox"] is not None
    assert result["bbox"][2] < 200
