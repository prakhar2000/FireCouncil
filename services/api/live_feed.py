"""Play the camera frames in order. The box appears only after the smoke check marks a plume."""

import json
from pathlib import Path

import cv2

from services.vision.cv.smoke import _read_color, _resize, _stabilize, check_frames

_SOURCE = Path("data/raw/figlib/20160604_FIRE_rm-n-mobo-c")
_EVIDENCE = Path("data/local/evidence")
_WHEN = "Fairview Fire, September 5, 2022"
_CAMERAS = (
    {
        "id": "smer",
        "name": "Santa Margarita",
        "source": Path("data/raw/figlib/20220905-FairviewFire-smer-tcs3-mobo-c"),
        "when": _WHEN,
    },
    {
        "id": "bh-n",
        "name": "Boucher Hill, looking north",
        "source": Path("data/raw/figlib/20220905-FairviewFire-bh-n-mobo-c"),
        "when": _WHEN,
    },
    {
        "id": "tp-w",
        "name": "Toro Peak, looking west",
        "source": Path("data/raw/figlib/20220905-FairviewFire-tp-w-mobo-c"),
        "when": _WHEN,
    },
)


def build_live_frames(
    source: Path | None = None,
    dest: Path | None = None,
    prefix: str = "ev-live",
    reject_glare: bool = False,
) -> list[dict]:
    """Write one image per camera frame, with a box on the frames the check accepts."""
    folder = source or _SOURCE
    out = dest or _EVIDENCE
    paths = sorted(folder.glob("*.jpg")) + sorted(folder.glob("*.png"))
    if len(paths) < 2:
        return []
    stable = _stabilize([_resize(_read_color(str(path))) for path in paths])
    out.mkdir(parents=True, exist_ok=True)
    frames: list[dict] = []
    for index, image in enumerate(stable):
        drawn = image.copy()
        marked = False
        if index >= 1:
            result = check_frames([str(path) for path in paths[: index + 1]], 180, 60, overlay_allowed=False)
            box = result["bbox"] if result["smoke_prob"] > 0 else None
            if box and (not reject_glare or _usable_box(drawn, box)):
                x, y, width, height = box
                cv2.rectangle(drawn, (x, y), (x + width, y + height), (0, 255, 255), 2)
                marked = True
        name = f"{prefix}-{index:02d}.png"
        cv2.imwrite(str(out / name), drawn)
        if marked:
            label = "Smoke marked on the plume."
        elif reject_glare:
            label = "No box on this frame."
        else:
            label = "Watching. No smoke yet."
        frames.append({"file": name, "label": label})
    if prefix == "ev-live":
        (out / "ev-live.json").write_text(json.dumps(frames))
    return frames


def build_views(cameras: list[dict] | None = None, dest: Path | None = None) -> list[dict]:
    """Build one playing sequence for each camera of the same ignition."""
    chosen = list(cameras) if cameras is not None else [dict(item) for item in _CAMERAS]
    out = dest or _EVIDENCE
    views = []
    for camera in chosen:
        frames = build_live_frames(
            Path(camera["source"]),
            out,
            prefix=f"ev-{camera['id']}",
            reject_glare=True,
        )
        if len(frames) < 2:
            continue
        view = {"id": camera["id"], "name": camera["name"], "frames": frames}
        if camera.get("when"):
            view["when"] = camera["when"]
        views.append(view)
    (out / "ev-cameras.json").write_text(json.dumps(views))
    return views


def alert_from_views(views: list[dict]) -> str | None:
    """Name every camera that marked smoke. One camera is enough to raise the alert."""
    if len(views) < 2:
        return None
    marked = [
        view["name"]
        for view in views
        if any(str(frame.get("label", "")).startswith("Smoke marked") for frame in view["frames"])
    ]
    if not marked:
        return "No camera marked smoke."
    if len(marked) == 1:
        names = marked[0]
    elif len(marked) == 2:
        names = f"{marked[0]} and {marked[1]}"
    else:
        names = ", ".join(marked[:-1]) + f", and {marked[-1]}"
    return f"Smoke marked on {names}. One camera is enough to raise this alert."


def _usable_box(image, box: tuple[int, int, int, int]) -> bool:
    """Keep a plume. Drop a box that covers the sky or sits on the sun."""
    x, y, width, height = box
    frame_h, frame_w = image.shape[:2]
    if width > frame_w * 0.45 or height > frame_h * 0.40:
        return False
    if y > frame_h * 0.04:
        return True
    crop = image[y : y + height, x : x + width]
    if crop.size == 0:
        return False
    value = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 2].mean()
    return float(value) < 220


def ready_views(dest: Path | None = None) -> list[dict]:
    """Return the saved cameras when every frame file is present."""
    out = dest or _EVIDENCE
    manifest = out / "ev-cameras.json"
    if not manifest.is_file():
        return []
    views = json.loads(manifest.read_text())
    if len(views) < 2:
        return []
    for view in views:
        if any(not (out / frame["file"]).is_file() for frame in view["frames"]):
            return []
    return views


def ready_frames(dest: Path | None = None) -> list[dict]:
    """Return the saved sequence when every frame file is present."""
    out = dest or _EVIDENCE
    manifest = out / "ev-live.json"
    if not manifest.is_file():
        return []
    frames = json.loads(manifest.read_text())
    if not frames or any(not (out / frame["file"]).is_file() for frame in frames):
        return []
    return frames
