"""Route status from a short camera window. Classical OpenCV only."""

import time
from pathlib import Path

import cv2
import numpy as np

from services.agents.schemas import RouteStatus
from services.vision.cv.runtime import runtime_info

_MAX_SIDE = 640


def status_for_frames(
    route_id: str,
    frame_paths: list[str],
    evidence_dir: Path | None = None,
    age_s: int = 0,
    evidence_id: str | None = None,
) -> RouteStatus:
    """Classify a road as clear, slow, blocked, or unknown."""
    return assess_route(
        route_id,
        frame_paths,
        evidence_dir=evidence_dir,
        age_s=age_s,
        evidence_id=evidence_id,
    )["status"]


def assess_route(
    route_id: str,
    frame_paths: list[str],
    evidence_dir: Path | None = None,
    age_s: int = 0,
    evidence_id: str | None = None,
) -> dict:
    """Return a RouteStatus plus per-stage timings in milliseconds."""
    started = time.perf_counter()
    frames = [_resize_gray(_read_gray(path)) for path in frame_paths]
    height = min(frame.shape[0] for frame in frames)
    width = min(frame.shape[1] for frame in frames)
    frames = [frame[:height, :width] for frame in frames]
    load_ms = _ms(started)

    started = time.perf_counter()
    motion = _motion_energy(frames)
    stalled_ratio = _persistent_fraction(frames)
    vehicles = _moving_blobs(frames)
    haze_score = _haze(frames[-1])
    measure_ms = _ms(started)

    started = time.perf_counter()
    status = _classify(frames[0], motion, stalled_ratio)
    classify_ms = _ms(started)

    evidence_id = evidence_id or f"ev-{route_id}"
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(evidence_dir / f"{evidence_id}.png"), frames[-1])

    route = RouteStatus(
        route_id=route_id,
        status=status,
        vehicles=vehicles,
        stalled_ratio=round(stalled_ratio, 4),
        haze_score=round(haze_score, 4),
        evidence_id=evidence_id,
        age_s=age_s,
    )
    return {
        "status": route,
        "timings_ms": {"load": load_ms, "measure": measure_ms, "classify": classify_ms},
        "runtime": runtime_info(),
        "evidence_id": evidence_id,
    }


def _read_gray(path: str) -> np.ndarray:
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image


def _resize_gray(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    scale = _MAX_SIDE / max(height, width)
    if scale >= 1:
        return image
    return cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)


def _motion_energy(frames: list[np.ndarray]) -> float:
    if len(frames) < 2:
        return 0.0
    diffs = [float(cv2.absdiff(frames[index], frames[index + 1]).mean()) for index in range(len(frames) - 1)]
    return float(np.mean(diffs))


def _persistent_fraction(frames: list[np.ndarray]) -> float:
    bright = [(frame > 180).astype(np.uint8) for frame in frames]
    persistent = bright[0]
    for mask in bright[1:]:
        persistent = cv2.bitwise_and(persistent, mask)
    return float(persistent.mean())


def _moving_blobs(frames: list[np.ndarray]) -> int:
    if len(frames) < 2:
        return 0
    diff = cv2.absdiff(frames[0], frames[-1])
    _, mask = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
    count, _, _, _ = cv2.connectedComponentsWithStats(mask)
    return max(0, int(count) - 1)


def _haze(frame: np.ndarray) -> float:
    variance = float(cv2.Laplacian(frame, cv2.CV_64F).var())
    return float(max(0.0, min(1.0, 1.0 - variance / 500.0)))


def _classify(frame: np.ndarray, motion: float, stalled_ratio: float) -> str:
    if float(np.std(frame)) < 5 and stalled_ratio < 0.02:
        return "unknown"
    if stalled_ratio >= 0.08 and motion < 8:
        return "blocked"
    if motion >= 4 and stalled_ratio < 0.05:
        return "clear"
    if motion >= 1:
        return "slow"
    return "unknown"


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
