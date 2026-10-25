"""Write the synthetic images and masks the vision tests load."""

from pathlib import Path

import cv2
import numpy as np

from services.vision.cv.goes_track import save_fixture

ROOT = Path(__file__).resolve().parent


def build() -> None:
    """Create route frames, a GOES npz, and smoke sequences."""
    _routes()
    save_fixture(ROOT / "goes" / "moving_blob.npz")
    _smoke(ROOT / "smoke" / "rise", moving=True)
    _smoke(ROOT / "smoke" / "static", moving=False)


def _routes() -> None:
    clear = ROOT / "routes" / "clear"
    blocked = ROOT / "routes" / "blocked"
    unknown = ROOT / "routes" / "unknown"
    for index in range(4):
        frame = np.full((180, 320), 80, np.uint8)
        x = 20 + index * 50
        cv2.rectangle(frame, (x, 80), (x + 40, 104), 255, thickness=-1)
        _write(clear / f"f{index}.png", frame)

        parked = np.full((180, 320), 80, np.uint8)
        cv2.rectangle(parked, (40, 30), (240, 150), 255, thickness=-1)
        _write(blocked / f"f{index}.png", parked)

        flat = np.full((180, 320), 80, np.uint8)
        _write(unknown / f"f{index}.png", flat)


def _smoke(directory: Path, moving: bool) -> None:
    """Fixed brown hillside, with a small gray plume only on the rising sequence."""
    for index in range(8):
        frame = np.full((120, 160, 3), (180, 120, 70), np.uint8)
        cv2.rectangle(frame, (0, 70), (159, 119), (70, 50, 30), thickness=-1)
        if moving:
            radius = 4 + index
            cy = 78 - index * 6
            cv2.circle(frame, (130, cy), radius, (150, 150, 150), thickness=-1)
        _write(directory / f"f{index}.png", frame)


def _write(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)


if __name__ == "__main__":
    build()
