"""Local vision HTTP API. Bind it to localhost."""

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from services.vision.cv.goes_track import track_masks
from services.vision.cv.route_status import assess_route
from services.vision.cv.runtime import runtime_info
from services.vision.cv.smoke import check_frames

app = FastAPI(title="FireCouncil vision")
_EVIDENCE = Path("data/local/evidence")


class RouteRequest(BaseModel):
    route_id: str
    frame_paths: list[str]
    age_s: int = 0


class GoesRequest(BaseModel):
    mask_paths: list[str]
    km_per_pixel: float = 2.0


class SmokeRequest(BaseModel):
    frame_paths: list[str]
    azimuth_deg: float
    hfov_deg: float
    overlay_allowed: bool = True


@app.get("/health")
def health() -> dict:
    """Report which OpenCV build answered."""
    return runtime_info()


@app.post("/routes/status")
def routes_status(body: RouteRequest) -> dict:
    """Classify one road from local frame files."""
    result = assess_route(body.route_id, body.frame_paths, evidence_dir=_EVIDENCE, age_s=body.age_s)
    result["status"] = result["status"].model_dump()
    return result


@app.post("/goes/track")
def goes_track(body: GoesRequest) -> dict:
    """Track a fire front across saved masks."""
    return track_masks(body.mask_paths, body.km_per_pixel)


@app.post("/smoke/check")
def smoke_check(body: SmokeRequest) -> dict:
    """Score frames for rising smoke."""
    return check_frames(
        body.frame_paths,
        body.azimuth_deg,
        body.hfov_deg,
        overlay_allowed=body.overlay_allowed,
        evidence_dir=_EVIDENCE if body.overlay_allowed else None,
    )
