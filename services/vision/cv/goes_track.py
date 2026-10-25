"""Track a fire front across GOES-style binary masks."""

import math
import time
from pathlib import Path

import cv2
import numpy as np

from services.vision.cv.runtime import runtime_info

# One mask step stands in for a 5-minute GOES image.
_STEP_HOURS = 5 / 60


def track_masks(mask_paths: list[str], km_per_pixel: float, step_hours: float | None = None) -> dict:
    """Threshold, clean, and follow the largest fire component.

    A ``.npz`` file with a ``masks`` array of shape ``(n, h, w)`` is expanded
    into one mask per step.
    """
    started = time.perf_counter()
    masks = _load_masks(mask_paths)
    load_ms = _ms(started)

    started = time.perf_counter()
    centroids: list[tuple[float, float]] = []
    last_hull: np.ndarray | None = None
    for mask in masks:
        centroid, hull = _component(mask)
        centroids.append(centroid)
        last_hull = hull
    track_ms = _ms(started)

    motion = (
        motion_from_centroids(centroids, km_per_pixel, step_hours or _STEP_HOURS)
        if len(centroids) >= 2
        else {"bearing_deg": None, "speed_kmh": 0.0}
    )
    bearing = motion["bearing_deg"]
    speed = motion["speed_kmh"]
    return {
        "bearing_deg": bearing,
        "speed_kmh": speed,
        "front_geojson": _polygon(last_hull),
        "centroids": centroids,
        "timings_ms": {"load": load_ms, "track": track_ms},
        "runtime": runtime_info(),
        "evidence_id": "goes-front",
    }


def _load_masks(mask_paths: list[str]) -> list[np.ndarray]:
    masks: list[np.ndarray] = []
    for path in mask_paths:
        if path.endswith(".npz"):
            array = np.load(path)["masks"]
            masks.extend(array[index] for index in range(array.shape[0]))
        else:
            image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise FileNotFoundError(path)
            masks.append(image)
    if len(masks) < 2:
        raise ValueError("track_masks needs at least two masks")
    return masks


def _component(mask: np.ndarray) -> tuple[tuple[float, float], np.ndarray]:
    binary = np.where(mask > 127, 255, 0).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    _count, _labels, stats, centroids = cv2.connectedComponentsWithStats(binary)
    if len(stats) <= 1:
        raise ValueError("mask has no fire component")
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    centroid = (float(centroids[largest][0]), float(centroids[largest][1]))
    contours, _hierarchy = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("mask has no contour")
    hull = cv2.convexHull(max(contours, key=cv2.contourArea))
    return centroid, hull


def motion_from_centroids(
    centroids: list[tuple[float, float]],
    km_per_pixel: float,
    step_hours: float = _STEP_HOURS,
) -> dict:
    """Same speed and bearing the satellite tracker uses, for any time step."""
    return {
        "bearing_deg": _bearing(centroids[0], centroids[-1]),
        "speed_kmh": _speed_kmh(centroids, km_per_pixel, step_hours),
    }


def _bearing(start: tuple[float, float], end: tuple[float, float]) -> float:
    east = end[0] - start[0]
    north = start[1] - end[1]
    return round(math.degrees(math.atan2(east, north)) % 360, 3)


def _speed_kmh(
    centroids: list[tuple[float, float]],
    km_per_pixel: float,
    step_hours: float = _STEP_HOURS,
) -> float:
    start, end = centroids[0], centroids[-1]
    pixels = math.hypot(end[0] - start[0], end[1] - start[1])
    hours = step_hours * (len(centroids) - 1)
    if hours <= 0:
        return 0.0
    return round(pixels * km_per_pixel / hours, 3)


def _polygon(hull: np.ndarray | None) -> dict | None:
    if hull is None:
        return None
    points = [[float(point[0][0]), float(point[0][1])] for point in hull]
    if points and points[0] != points[-1]:
        points.append(points[0])
    return {"type": "Polygon", "coordinates": [points]}


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def save_fixture(path: Path) -> None:
    """Write the northeast-moving blob used by the tests."""
    masks = np.zeros((3, 64, 64), np.uint8)
    centers = ((20, 44), (28, 36), (36, 28))
    for index, (cx, cy) in enumerate(centers):
        masks[index, cy - 4 : cy + 4, cx - 4 : cx + 4] = 255
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, masks=masks)
