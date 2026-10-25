"""The camera sequence marks smoke only after the frames show a plume."""

from pathlib import Path

import cv2
import numpy as np

from services.api.dashboard import _camera_bank, _live_player
from services.api.live_feed import (
    _usable_box,
    alert_from_views,
    build_live_frames,
    build_views,
    ready_frames,
    ready_views,
)


def test_rising_frames_end_with_a_box(tmp_path: Path):
    source = Path("tests/fixtures/smoke/rise")
    frames = build_live_frames(source, tmp_path)
    assert len(frames) == 8
    assert frames[0]["label"] == "Watching. No smoke yet."
    assert frames[-1]["label"] == "Smoke marked on the plume."
    assert ready_frames(tmp_path) == frames
    page = _live_player(frames)
    assert "ev-live-00.png" in page
    assert "Frame 1 of 8" in page
    assert "setInterval" in page


def test_three_cameras_play_the_same_frame_count(tmp_path: Path):
    source = Path("tests/fixtures/smoke/rise")
    cameras = [
        {"id": "hp-n", "name": "High Point, looking north", "source": source},
        {"id": "hp-w", "name": "High Point, looking west", "source": source},
        {"id": "rm-e", "name": "Red Mountain, looking east", "source": source},
    ]
    views = build_views(cameras, tmp_path)
    assert [view["name"] for view in views] == [camera["name"] for camera in cameras]
    assert ready_views(tmp_path) == views
    assert (tmp_path / "ev-hp-n-00.png").is_file()
    assert (tmp_path / "ev-rm-e-07.png").is_file()
    page = _camera_bank(views)
    assert page.count("Frame 1 of 8") == 3
    assert "High Point, looking west" in page
    assert "Red Mountain, looking east" in page
    assert "HPWREN (hpwren.ucsd.edu)" in page


def test_one_marked_camera_raises_the_alert():
    views = [
        {"name": "Red Mountain, looking north", "frames": [{"label": "Smoke marked on the plume."}]},
        {"name": "Santa Margarita", "frames": [{"label": "No smoke marked from this camera."}]},
        {"name": "Boucher Hill, looking north", "frames": [{"label": "No smoke marked from this camera."}]},
    ]
    alert = alert_from_views(views)
    assert alert == (
        "Smoke marked on Red Mountain, looking north. One camera is enough to raise this alert."
    )
    assert alert_from_views(views[1:]) == "No camera marked smoke."


def test_a_bright_sky_box_is_not_drawn():
    sky = np.full((480, 640, 3), 255, np.uint8)
    assert _usable_box(sky, (0, 0, 330, 202)) is False
    plume = np.full((480, 640, 3), (140, 140, 140), np.uint8)
    assert _usable_box(plume, (600, 180, 36, 90)) is True
    assert cv2.cvtColor(plume, cv2.COLOR_BGR2HSV)[:, :, 2].mean() < 215
