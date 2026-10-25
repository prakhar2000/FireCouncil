"""Smoke check: stabilize, then mark the plume that keeps changing shape."""

import time
from pathlib import Path

import cv2
import numpy as np

from services.vision.cv.runtime import runtime_info

_MAX_SIDE = 640


def check_frames(
    frame_paths: list[str],
    azimuth_deg: float,
    hfov_deg: float,
    overlay_allowed: bool = True,
    evidence_dir: Path | None = None,
) -> dict:
    """Score a short color sequence. A plume already in the frame still counts."""
    started = time.perf_counter()
    frames = [_resize(_read_color(path)) for path in frame_paths]
    frames = _stabilize(frames)
    stabilize_ms = _ms(started)

    started = time.perf_counter()
    bbox = _plume_box(frames)
    mask_ms = _ms(started)
    fg_ms = 0.0
    flow_ms = 0.0
    prob = 0.85 if bbox is not None else 0.0
    bearing = _bearing(bbox, frames[-1].shape[1], azimuth_deg, hfov_deg)
    evidence_id = "ev-smoke"
    evidence_path = None
    if overlay_allowed and evidence_dir is not None and bbox is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        drawn = frames[-1].copy()
        x, y, width, height = bbox
        cv2.rectangle(drawn, (x, y), (x + width, y + height), (0, 255, 255), 2)
        evidence_path = str(evidence_dir / f"{evidence_id}.png")
        cv2.imwrite(evidence_path, drawn)
    return {
        "smoke_prob": prob,
        "bbox": bbox,
        "bearing_deg": bearing,
        "evidence_id": evidence_id,
        "evidence_path": evidence_path,
        "timings_ms": {
            "stabilize": stabilize_ms,
            "foreground": fg_ms,
            "mask": mask_ms,
            "flow": flow_ms,
        },
        "runtime": runtime_info(),
    }


def _read_color(path: str) -> np.ndarray:
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return image


def _stabilize(frames: list[np.ndarray]) -> list[np.ndarray]:
    if len(frames) < 2:
        return frames
    base = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY).astype(np.float32)
    height, width = frames[0].shape[:2]
    stabilized = [frames[0]]
    for frame in frames[1:]:
        current = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        shift, _response = cv2.phaseCorrelate(base, current)
        # A large shift is the plume moving, not the camera. Leave that frame as it is.
        if max(abs(float(shift[0])), abs(float(shift[1]))) > 3:
            stabilized.append(frame)
            continue
        matrix = np.float32([[1, 0, shift[0]], [0, 1, shift[1]]])
        stabilized.append(cv2.warpAffine(frame, matrix, (width, height)))
    return stabilized


def _resize(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    scale = _MAX_SIDE / max(height, width)
    if scale >= 1:
        return image
    return cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)


def _plume_box(frames: list[np.ndarray]) -> list[int] | None:
    """Box the changing region closest to the ground. A standing column still moves."""
    if len(frames) < 2:
        return None
    stack = np.stack([cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) for frame in frames])
    hot = (stack.std(axis=0) >= 5.0).astype(np.uint8) * 255
    height, width = hot.shape
    hot[int(height * 0.70) :, :] = 0
    hot[:4, :] = 0
    hot = _clean(hot)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats((hot > 0).astype(np.uint8))
    best: tuple[int, int, int, int] | None = None
    best_bottom = -1
    for index in range(1, count):
        x, y, box_w, box_h, area = (int(value) for value in stats[index])
        if area < 200 or box_h < 14 or box_w < 8 or box_w > width * 0.45:
            continue
        crop = frames[-1][y : y + box_h, x : x + box_w]
        if crop.size == 0:
            continue
        value = float(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 2].mean())
        if value < 130 or (y <= 8 and value >= 210):
            continue
        bottom = y + box_h
        if bottom > best_bottom:
            best_bottom = bottom
            best = (x, y, box_w, box_h)
    if best is None:
        return None
    return [best[0], best[1], best[2], best[3]]


def _clean(mask: np.ndarray) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)


def _bearing(bbox: list[int] | None, width: int, azimuth_deg: float, hfov_deg: float) -> float | None:
    if bbox is None or width <= 0:
        return None
    center = bbox[0] + bbox[2] / 2
    offset = (center - width / 2) / width
    return round(azimuth_deg + offset * hfov_deg, 3)


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
