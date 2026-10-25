"""Pydantic models shared by vision, rules, and the orchestrator."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """One camera, satellite, or hotspot artifact backing a decision."""

    id: str
    source: Literal["hpwren", "alertca", "caltrans", "goes", "firms"]
    camera_id: str | None = None
    s3_uri: str
    captured_at: datetime
    license: str
    overlay_allowed: bool


class FireAssessment(BaseModel):
    """What Fire Ops believes about spread and smoke."""

    incident_id: str
    front_geojson: dict | None = None
    spread_bearing_deg: float | None = None
    spread_kmh: float | None = None
    eta_min_by_zone: dict[str, int] = Field(default_factory=dict)
    smoke_confirmed: bool
    firms_detected: bool | None = None
    firms_confidence: str | None = None
    firms_distance_km: float | None = None
    firms_satellite: str | None = None
    confidence: float
    evidence_ids: list[str] = Field(default_factory=list)


class RouteStatus(BaseModel):
    """One evacuation road, judged from recent camera frames."""

    route_id: str
    status: Literal["clear", "slow", "blocked", "unknown"]
    vehicles: int
    stalled_ratio: float
    haze_score: float
    evidence_id: str | None = None
    age_s: int


class EvacAssessment(BaseModel):
    """Gaps and roads from Evacuation and Traffic."""

    gap_zones: list[str] = Field(default_factory=list)
    routes: list[RouteStatus] = Field(default_factory=list)
    recommended_route: str | None = None
    confidence: float


class HealthAssessment(BaseModel):
    """Care sites and vulnerable zones from Public Health."""

    priority_sites: list[dict] = Field(default_factory=list)
    assisted_evac_zones: list[str] = Field(default_factory=list)
    guidance: list[str] = Field(default_factory=list)
    confidence: float


class ActionPlan(BaseModel):
    """The plan after rules have the last word."""

    zones_to_warn: list[str] = Field(default_factory=list)
    urgency: Literal["advisory", "urgent"]
    route: str | None = None
    care_sites_first: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    rule_hits: list[str] = Field(default_factory=list)
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)


class DraftMessage(BaseModel):
    """One language draft for one zone. SMS and voice are stored, not sent."""

    zone_id: str
    lang: Literal["en", "es"]
    voice_ssml: str
    sms: str
    long_text: str
    evidence_url: str | None = None


class Decision(BaseModel):
    """One cycle, waiting for a person unless a newer cycle superseded it."""

    incident_id: str
    cycle_ts: str
    fire: FireAssessment
    evac: EvacAssessment
    health: HealthAssessment
    plan: ActionPlan
    messages: list[DraftMessage] = Field(default_factory=list)
    status: Literal["DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED", "SUPERSEDED"]
    diff_from_prev: dict = Field(default_factory=dict)
