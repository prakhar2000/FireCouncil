"""Measure plume motion with the same formula the satellite tracker uses."""

import math
from pathlib import Path

import cv2
import numpy as np

from services.vision.cv.goes_track import motion_from_centroids
from services.vision.cv.smoke import _plume_box, _read_color, _resize, _stabilize

# Santa Margarita Ecological Reserve, SMER TCS3. HPWREN lists this site as
# 33°27'N, 117°10'W, rounded to the minute.
_CAMERA_LAT = 33.45
_CAMERA_LON = -(117 + 10 / 60)
# CAL FIRE Fairview incident point, 5 September 2022.
_FIRE_LAT = 33.717062
_FIRE_LON = -116.893227
# HPWREN fixed-color cameras use a 90° horizontal view.
_HFOV_DEG = 90.0
_EARTH_KM = 6371.0
_FAIRVIEW = Path("data/raw/figlib/20220905-FairviewFire-smer-tcs3-mobo-c")

_cached: dict | None = None


def measure_fairview() -> dict | None:
    """Speed and bearing of the Santa Margarita plume. None when the frames are absent."""
    global _cached
    if _cached is not None:
        return _cached
    paths = sorted(_FAIRVIEW.glob("*.jpg"))
    if len(paths) < 2:
        return None
    measured = measure_frames([str(path) for path in paths])
    if measured is not None:
        _cached = measured
    return measured


def measure_frames(frame_paths: list[str]) -> dict | None:
    """Follow the bright core of the plume and convert that pixel motion to km/h."""
    frames = _stabilize([_resize(_read_color(path)) for path in frame_paths])
    box = _plume_box(frames)
    if box is None:
        return None
    epochs = [_epoch(path) for path in frame_paths]
    centroids: list[tuple[float, float]] = []
    kept: list[int] = []
    x, y, width, height = box
    for index, frame in enumerate(frames):
        centroid = _core(frame[y : y + height, x : x + width])
        if centroid is None:
            continue
        centroids.append((x + centroid[0], y + centroid[1]))
        kept.append(epochs[index])
    if len(centroids) < 2 or kept[-1] <= kept[0]:
        return None
    elapsed_hours = (kept[-1] - kept[0]) / 3600
    step_hours = elapsed_hours / (len(centroids) - 1)
    scale = km_per_pixel(frames[0].shape[1])
    motion = motion_from_centroids(centroids, scale, step_hours)
    motion["km_per_pixel"] = round(scale, 6)
    return motion


def km_per_pixel(width_px: int) -> float:
    """Kilometres on the ground per pixel at the Fairview point, from Santa Margarita."""
    if width_px <= 0:
        raise ValueError("width_px must be positive")
    lat1 = math.radians(_CAMERA_LAT)
    lon1 = math.radians(_CAMERA_LON)
    lat2 = math.radians(_FIRE_LAT)
    lon2 = math.radians(_FIRE_LON)
    east = (lon2 - lon1) * math.cos((lat1 + lat2) / 2)
    north = lat2 - lat1
    distance_km = math.hypot(east, north) * _EARTH_KM
    scene_km = 2 * distance_km * math.tan(math.radians(_HFOV_DEG / 2))
    return scene_km / width_px


def _core(crop: np.ndarray) -> tuple[float, float] | None:
    """Centroid of the brighter pixels inside the plume box."""
    if crop.size == 0:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    cutoff = float(np.percentile(gray, 60))
    mask = (gray >= cutoff).astype(np.uint8)
    moments = cv2.moments(mask)
    if moments["m00"] <= 0:
        return None
    return moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]


def _epoch(path: str) -> int:
    stem = Path(path).name.split("_", 1)[0]
    if not stem.isdigit():
        raise ValueError(f"frame name has no timestamp: {path}")
    return int(stem)
