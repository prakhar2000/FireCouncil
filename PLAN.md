# FireCouncil — MVP Build Plan (OpenCV AI Competition 2026, powered by AWS)

> **Working name.** A multi-agent wildfire warning copilot. OpenCV 5 on AWS turns public camera and satellite imagery into evidence-backed, human-approved, two-way alerts, built for the people phone alerts miss (older and disabled residents).

- **Deadline:** Mon **Oct 26, 2026, 11:45 pm PDT** (time shown on the Devpost page). **Internal freeze: Mon 6:00 pm PDT.**
- **Hard requirements:** OpenCV 5 performs substantive image/video analysis, and a meaningful component runs on AWS.
- **Awards we target:** Grand prizes + **Agentic Vision Award** + **Best Use of COOL Award**.
- **Current build:** stock OpenCV 5 on the laptop (`opencv-python-headless==5.0.0.93`). COOL on Graviton is a later switch for that award. Vision code only does `import cv2`, so the switch is the interpreter.
- **Rules:** https://opencv26.devpost.com/

---

## 0. How Cursor should use this file

1. Build **phase by phase** (Phase 0 → 7). Don't start a phase until the previous phase's **Done when** checks pass.
2. Mirror the checkboxes into `docs/PROGRESS.md` and tick them as you go.
3. Never hardcode secrets, account IDs or model IDs. Read them from env vars or SSM Parameter Store.
4. Anything marked **`VERIFY:`** is an external detail to confirm with a quick `curl`/`aws s3 ls` before writing code against it.
5. **LLMs propose, Python rules decide, a human approves.** No LLM output ever reaches the public directly.
6. Every external data source goes through a **source adapter** with caching, rate limiting, timeouts, and attribution/license metadata.
7. Tests use **saved fixtures** (images, JSON, small GOES subsets) so CI never depends on live feeds.
8. Keep it boring: small functions, typed (Pydantic), docstrings, structured JSON logs.

---

## 1. What we are building (MVP scope)

One loop, end to end:

1. **Trigger.** A fire is known: a NASA FIRMS hotspot inside our watch area, or a replay.
2. **See (OpenCV 5).** Confirm smoke on nearby cameras, track fire growth on GOES-18, and check evacuation routes on Caltrans cameras.
3. **Decide (multi-persona agents).** **Fire Ops**, **Evacuation & Traffic** and **Public Health** each propose. A **Planner** merges the proposals using fixed rules, and **Public Info** drafts the messages.
4. **Human approves.** A duty officer approves on the dashboard. Nothing reaches the public without approval.
5. **Notify.** Email (live, SES), SMS (AWS simulator numbers), web status page (live), and **Alexa (placeholder adapter** that renders the voice message with Polly).
6. **Confirm.** Track acknowledgements. If a registered vulnerable resident hasn't confirmed within N minutes, escalate to their caregiver and flag them on the dashboard.
7. **Re-plan.** New vision evidence (e.g., a route camera turns "blocked") starts a new cycle and supersedes the old draft.

**Demo areas**
- **Live capture + replay:** South Orange County. Replay the **Norte Fire** (OCFA; San Clemente / San Juan Capistrano; started **Oct 16, 2026, 11:33 a.m. PDT** near 33.481, −117.636; 570 acres; orders lifted Oct 17, 6 p.m.).
- **Replay only (GOES):** Eaton Fire night (Jan 7–8, 2025) for the "warning gap" evaluation.

**Out of scope for MVP:**
- a real Alexa skill
- real carrier SMS
- live official evacuation-zone status feeds
- any automatic public alert
- fire-spread modeling beyond simple extrapolation

---

## 2. Why this is different (use in the report and video)

The January 2025 LA failures were mostly about **decision speed and message quality**, not phone delivery:

- LA County's independent after-action review found the path from an evacuation decision to a public alert was slow and convoluted. It also found staffing and outdated-policy gaps, alerts that required clicking a link for details, and older residents who weren't monitoring alerts. https://www.npr.org/2025/09/26/nx-s1-5554173/la-county-response-fires
- Eaton Fire: 18 of the 19 people who died lived in west Altadena, most of them elderly or disabled. Orders there came hours after the east side's. https://www.smartcitiesdive.com/news/california-doj-civil-rights-violations-eaton-fire-west-altadena/812309/
- In west Altadena, the county began expanding orders at 2:18 a.m., but the messages didn't go out until 3:25 a.m.: **67 minutes from starting the order to the public alert**. Pre-drafted, pre-checked warnings target exactly this gap. https://www.fireengineering.com/firefighting/wildland-firefighting/eaton-fire-no-misconduct-delay-in-evacuation-notices-to-west-altadena-ca-report-says/
- On Jan 9, 2025, an alert meant for one area went to ~10M LA County phones. Trust took a hit. https://abc7.com/15784516
- On Jan 8, 2025, SCE power shutoffs hit 141,276 customers. No power means no Wi-Fi or Echo, so Echo can't be the whole answer. https://hoodline.com/2025/01/over-55-000-socal-edison-customers-lose-power-as-santa-ana-winds-cause-widespread-outages-in-southern-california/
- ALERTCalifornia's ~1,300 AI cameras already alert CAL FIRE dispatchers, and humans confirm. **We don't compete on ignition detection. We're decision support.** https://gvwire.com/2026/10/12/how-california-is-using-ai-and-cameras-to-stop-wildfires/

**Differentiators (what the demo must show):**
1. **Gap detector.** It compares the fire's projected path against which zones are already warned, then puts a pre-drafted, evidence-backed warning in front of the humans with authority.
2. **Complete, specific messages.** Every message names the zone, the threat and its direction, the time, the action, a camera-verified route and evidence. No "click a link to find out more."
3. **Verifiable.** Each message links to the camera frame it is based on.
4. **Two-way.** Acknowledgement tracking, with escalation to caregivers for vulnerable residents.
5. **Channel-agnostic.** Echo is one channel among email, SMS, web and (future) voice. It isn't the product.

---

## 3. Architecture

```
PUBLIC DATA SOURCES
  NASA FIRMS API | GOES-18 (S3 + SNS) | HPWREN cams | ALERTCalifornia cams | Caltrans CCTV | CAL FIRE/FIRIS perimeters | NWS wind
        │                  │                    │
        ▼                  ▼                    ▼
EventBridge Scheduler ─► Lambda pollers ─► S3 raw/ ◄── replay_feeder (same paths, simulated time)
                           SQS (goes-queue, us-east-2) ◄── SNS arn:aws:sns:us-east-1:123901341784:NewGOES18Object
        │
        ▼
EC2 Graviton4 (c8g, COOL AMI = OpenCV 5 optimized)
  ├─ vision-svc  (FastAPI, runs inside COOL venv)  smoke_check | goes_track | routes_status | annotate
  └─ agents-svc  (Strands Agents + Amazon Bedrock)
        Fire Ops ─┐
        Evac & Traffic ─┼─► Planner ─► rules.py ─► Public Info ─► Decision(PENDING_APPROVAL)
        Public Health ─┘          (deterministic)
        │
        ▼
DynamoDB (incidents, cameras, observations, zones, decisions, messages, residents, acks) + S3 (evidence, traces)
        │
        ▼
API Gateway + Lambda ◄── Dashboard (S3 + CloudFront, Cognito login) ── duty officer APPROVE / EDIT / REJECT
        │
        ▼
Step Functions: Notify ─► Wait(ack window) ─► CheckAcks ─► EscalateCaregiver ─► Report
   ├─ SES email (live)
   ├─ SMS via AWS End User Messaging (simulator numbers)
   ├─ Web zone status page (live)
   └─ AlexaChannel (STUB: SSML ─► Polly MP3 ─► alexa_outbox)  ← "will trigger an Alexa skill"
```

**Region:** `us-east-2`. An SCP restricts this account to us-east-2; Bedrock and Graviton4 run there. GOES objects stay in `s3://noaa-goes18` in `us-east-1` and are read cross-region with `--no-sign-request`. An SQS queue in `us-east-2` subscribes to `arn:aws:sns:us-east-1:123901341784:NewGOES18Object` (cross-region). The queue policy must allow that topic ARN.

---

## 4. AWS services

| Service | Used for | Notes |
|---|---|---|
| **EC2 Graviton4 + COOL AMI** (AWS Marketplace: "Cloud Optimized OpenCV For AWS Graviton4") | vision-svc + agents-svc | `c8g.2xlarge` is enough. COOL v3.1 is built on OpenCV 5.0 and runs on Ubuntu 24.04. Libraries live in `/opt/cool`, venv at `/opt/cool/venvs/python_3.12`. Software fee ~$0.02/hr on c8g.2xlarge **plus** EC2. The 7-day free trial **auto-converts to paid**, so cancel after judging. |
| **EC2 x86** (`c7i.2xlarge`) | COOL benchmark baseline only | Stock OpenCV 5. Run for a few hours, then terminate. |
| **Amazon S3** | raw frames, evidence, GOES subsets, replays, traces, eval results, dashboard | Lifecycle: expire `raw/` after 14 days. |
| **Amazon DynamoDB** | all state (section 7) | On-demand capacity. |
| **AWS Lambda** | pollers, GOES listener, API, notifier, ack handlers | Python 3.12, arm64. |
| **Amazon EventBridge Scheduler** | polling cadence (1–5 min), replay clock | Disable when not demoing. |
| **Amazon SQS** | GOES new-file notifications, vision work queue | Queue in `us-east-2`. Cross-region subscription to `arn:aws:sns:us-east-1:123901341784:NewGOES18Object`. Queue policy must allow that topic ARN. |
| **Amazon Bedrock** | persona, planner and public-info LLM calls | Enable model access in `us-east-2` on day 1. Set model IDs via env. **Don't use Bedrock Agents Classic** (closed to new customers since Jul 30, 2026). |
| **AWS Step Functions** | notify → wait → check acks → escalate | Standard workflow with Wait states. Visual execution looks great in the video. |
| **Amazon API Gateway** (HTTP API) | dashboard API, ack links | |
| **Amazon CloudFront** | HTTPS endpoint for dashboard and public zone pages | This is the judges' "working web endpoint". |
| **Amazon Cognito** | duty-officer login for approve/edit/reject | One user pool, demo user for judges. |
| **Amazon SES** | live email alerts + caregiver escalations | Sandbox: verify each recipient address. |
| **AWS End User Messaging SMS** | SMS channel via **simulator numbers** | Real US SMS requires 10DLC/toll-free registration (up to 15 business days), so it isn't possible by the deadline. Simulator numbers need no registration and generate realistic events. |
| **Amazon Polly** | renders "what the Echo would say" (MP3), EN + ES | Used by the Alexa stub. |
| **Amazon CloudWatch** (+ X-Ray optional) | logs, metrics, per-stage latency dashboard | |
| **SSM Parameter Store / Secrets Manager** | FIRMS MAP_KEY, kill switch, config | |
| **Amazon ECR** | arm64 images (agents-svc, Lambdas if containerized) | |
| **AWS CDK (CloudFormation)** | everything as code | Reproducibility is part of the score. |
| **AWS Budgets** | alerts at 50/80/100% of credits | **Do this first.** |
| *Optional:* Bedrock AgentCore | host agents + built-in observability | Stretch only. |
| *Optional:* Amazon Location Service | basemap / geocoding | Or MapLibre + OSM tiles. |
| *Optional:* EC2 g6 or SageMaker training | fine-tune a smoke classifier | Stretch only. |
| *Not AWS:* Alexa Skills Kit | Echo announcements | **Placeholder adapter in MVP** (section 15). |

---

## 5. Data sources

| # | Source | What we use | Access | License / limits |
|---|---|---|---|---|
| 1 | **NASA FIRMS** | Trigger: active fire hotspots | `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{W,S,E,N}/{DAY_RANGE}[/{YYYY-MM-DD}]` with SOURCE ∈ `VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT, VIIRS_SNPP_NRT, MODIS_NRT, LANDSAT_NRT`. Free MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/map_key/ | Ultra-real-time data arrives <60 s after a satellite overpass for much of the US, but each satellite passes only ~2×/day. Respect transaction limits. |
| 2 | **GOES-18 (GOES-West)** | Fire growth/spread every ~5 min, smoke plume direction | `s3://noaa-goes18` (stays in us-east-1; cross-region read from us-east-2 with `--no-sign-request`). SNS: `arn:aws:sns:us-east-1:123901341784:NewGOES18Object` (SQS in us-east-2 / Lambda only). **VERIFY product prefixes** with `aws s3 ls --no-sign-request s3://noaa-goes18/`. Expected: `ABI-L2-FDCC` (fire detection, CONUS), `ABI-L2-CMIPC` (imagery), `ABI-L1b-RadC`, `ABI-L1b-RadM` (mesoscale). Helpers: `goes2go`, `xarray` + `netCDF4`. | Open. Attribute NOAA; don't imply endorsement. ~2 km pixels: state this limitation. |
| 3 | **HPWREN cameras** | Smoke confirmation (live + archive); evidence images | Archive: `http://c1.hpwren.ucsd.edu/archive/` (color), `http://c2.hpwren.ucsd.edu/archive/` (near-IR); bulk: `http://dl-hpwren.ucsd.edu/archive`; query tool: `http://c1.hpwren.ucsd.edu/tools/fetch-cam-images.html`; camera list: `http://c1.hpwren.ucsd.edu/tools/camera-locations.txt`. Path example: `/archive/{camera}/large/{YYYY}/{YYYYMMDD}/`. **VERIFY:** Santiago Peak `sp-*-mobo-c` cams on Oct 16, 2026 (Norte Fire). | ~1 image/min. San Diego, Orange, Imperial counties. **Attribution "HPWREN (hpwren.ucsd.edu)"** when publishing. Overlays OK. |
| 4 | **FIgLib** | Labeled smoke sequences for tuning/eval (E1) | `http://hpwren.ucsd.edu/HPWREN-FIgLib/` | 315 fire sequences, ~24,800 images, ±40 min around ignition, ~1/min. Attribute HPWREN/UCSD. |
| 5 | **ALERTCalifornia** | Confirmation views near active incidents only | ArcGIS Living Atlas layer (search "ALERTCalifornia": camera location, real-time viewshed, current image) or the Cal OES "California Webcams" layer. | **CC BY-NC-ND 4.0**: non-commercial; credit "ALERTCalifornia \| UC San Diego"; **don't publish modified frames** (show raw + credit, keep overlays internal); don't crop the info bar. Poll ≤1 frame / 2 min / camera, only near incidents. Their site is for confirming fires, not detecting them. Email them for research access. |
| 6 | **Caltrans CCTV** | Evacuation-route status (traffic, stalled cars, smoke haze) | Portal: https://cwwp2.dot.ca.gov. District JSON includes `currentImageURL` plus `referenceImage1UpdateAgoURL` … `referenceImage6UpdatesAgoURL` (last 6 frames). Statewide locations (GeoJSON): `https://gisdata.dot.ca.gov/arcgis/rest/services/CHhighway/CCTV/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson`. **VERIFY** district JSON URLs for D12 (Orange) and D7 (LA). | Read the CWWP2 Conditions of Use. Downscale to ≤640 px; no plate or face extraction. |
| 7 | **Fire perimeters** | Official perimeter context for Fire Ops | CA Perimeters CAL FIRE NIFC FIRIS public view: https://gis.data.cnra.ca.gov/datasets/CALFIRE-Forestry::ca-perimeters-cal-fire-nifc-firis-public-view (GeoJSON/CSV/KML) | Public. |
| 8 | **Evacuation zones** | Zone polygons + official status | Official zones are **Genasys Protect** zones; live status lives there (no public API we rely on). MVP: `data/zones/demo_zones.geojson`, hand-drawn or from a county's static zone layer if published (**VERIFY** Orange/LA County GIS hubs). The duty officer sets official status manually, or the replay script does. | Label **"DEMO ZONES — not official."** Never present as live status. |
| 9 | **Care facilities** | Public Health persona: residential care for the elderly per zone | CDSS Community Care Licensing → "Residential Care Facilities for the Elderly" CSV on data.ca.gov / data.chhs.ca.gov (a geocoded GeoJSON variant is on lab.data.ca.gov). | Public. |
| 10 | **NWS API** | Wind speed/direction for spread extrapolation | `https://api.weather.gov/points/{lat},{lon}` → `forecastGridData` | Requires a `User-Agent` header. |
| 11 | **Residents** | Delivery + acknowledgement simulation | `data/residents.sample.csv` (synthetic) | **Synthetic only.** Team inboxes act as residents and caregivers. |

---

## 6. Repository layout

```
firecouncil/
├─ PLAN.md
├─ README.md                      # quickstart, architecture, how to run replays, demo login
├─ Makefile                       # make setup | test | replay R=<name> | bench | deploy | destroy
├─ infra/                         # AWS CDK (Python)
│  ├─ app.py
│  └─ stacks/ data_stack.py ingest_stack.py api_stack.py notify_stack.py web_stack.py compute_stack.py
├─ services/
│  ├─ vision/                     # FastAPI + OpenCV 5 (COOL on Graviton)
│  │  ├─ app.py                   # REST endpoints
│  │  ├─ mcp_server.py            # same tools via MCP (optional; reusable later by Alexa+ / agents)
│  │  ├─ cv/ stabilize.py smoke.py goes_track.py route_status.py haze.py triangulate.py annotate.py
│  │  ├─ models/                  # ONNX models (+ LICENSES.md)
│  │  ├─ systemd/vision.service   # runs inside /opt/cool/venvs/python_3.12
│  │  └─ requirements.txt         # pinned (no opencv here on Graviton: COOL provides cv2)
│  ├─ agents/
│  │  ├─ orchestrator.py          # Workflow: personas in parallel → planner → rules → public info → approval
│  │  ├─ personas/ fire_ops.py evac_traffic.py public_health.py planner.py public_info.py
│  │  ├─ rules.py                 # deterministic decision rules (no LLM)
│  │  ├─ schemas.py               # Pydantic models (section 7)
│  │  └─ tools.py                 # thin clients: vision-svc, DynamoDB, perimeters, NWS
│  ├─ ingest/ poll_firms.py poll_cameras.py goes_listener.py replay_feeder.py sources/*.py
│  ├─ api/ handlers.py            # incidents, decisions, approve/edit/reject, acks, zones, traces
│  ├─ notify/ dispatcher.py channels/ email_ses.py sms_eum.py alexa_stub.py web.py templates/
│  └─ ack/ statemachine.asl.json check_acks.py escalate.py
├─ dashboard/                     # React + Vite + MapLibre
├─ data/ cameras.yaml zones/demo_zones.geojson residents.sample.csv replays/*.yaml
├─ eval/ e1_smoke_figlib.py e2_routes.py e3_gap_replay.py e4_messages.py e5_ack_sim.py e6_latency_cost.py e7_cool_bench.py results/
├─ tests/ fixtures/ test_*.py
└─ docs/ report.md architecture.mmd agent_workflow.mmd video_script.md PROGRESS.md FUTURE.md traces/
```

---

## 7. Data model

### DynamoDB tables (prefix `fc_`)

| Table | Keys | Main attributes |
|---|---|---|
| `incidents` | pk `incident_id` | name, bbox, status, first_seen, source (`firms\|replay\|manual`), hotspots[], front_geojson_s3, updated_at |
| `cameras` | pk `camera_id` | source (`hpwren\|alertca\|caltrans`), lat, lon, azimuth_deg, hfov_deg, license (`attribution\|cc_by_nc_nd\|caltrans`), overlay_allowed, image_url, corridor_id, mask_s3 |
| `observations` | pk `incident_id`, sk `ts#tool#camera` | tool output JSON, evidence_s3, `cv2_version`, `cv2_path`, host_arch, stage timings |
| `zones` | pk `zone_id` | name, geojson, official_status (`none\|advisory\|warning\|order`), status_source (`manual\|replay`), last_official_change |
| `decisions` | pk `incident_id`, sk `cycle_ts` | persona outputs, plan, rule_hits, diff_from_prev, status (`DRAFT\|PENDING_APPROVAL\|APPROVED\|REJECTED\|SUPERSEDED`), approved_by, approved_at |
| `messages` | pk `decision_id`, sk `channel#resident_id` | body, sent_at, delivery_status, simulated (bool) |
| `residents` | pk `resident_id` | zone_id, vulnerable, language, channels {email, sms_sim, echo, web}, caregiver_email |
| `acks` | pk `decision_id`, sk `resident_id` | ack_at, channel, escalation_state |

### Core schemas (`services/agents/schemas.py`)

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel

class Evidence(BaseModel):
    id: str
    source: Literal["hpwren", "alertca", "caltrans", "goes", "firms"]
    camera_id: str | None = None
    s3_uri: str
    captured_at: datetime
    license: str
    overlay_allowed: bool

class FireAssessment(BaseModel):
    incident_id: str
    front_geojson: dict | None
    spread_bearing_deg: float | None
    spread_kmh: float | None
    eta_min_by_zone: dict[str, int]
    smoke_confirmed: bool
    confidence: float
    evidence_ids: list[str]

class RouteStatus(BaseModel):
    route_id: str
    status: Literal["clear", "slow", "blocked", "unknown"]
    vehicles: int
    stalled_ratio: float
    haze_score: float
    evidence_id: str | None
    age_s: int

class EvacAssessment(BaseModel):
    gap_zones: list[str]          # in projected path AND not yet warned/ordered
    routes: list[RouteStatus]
    recommended_route: str | None
    confidence: float

class HealthAssessment(BaseModel):
    priority_sites: list[dict]    # care facilities in affected zones
    assisted_evac_zones: list[str]
    guidance: list[str]
    confidence: float

class ActionPlan(BaseModel):
    zones_to_warn: list[str]
    urgency: Literal["advisory", "urgent"]
    route: str | None
    care_sites_first: list[str]
    conflicts: list[str]
    rule_hits: list[str]
    rationale: str
    evidence_ids: list[str]

class DraftMessage(BaseModel):
    zone_id: str
    lang: Literal["en", "es"]
    voice_ssml: str               # ≤ 25 s spoken
    sms: str                      # ≤ 300 chars
    long_text: str
    evidence_url: str | None
```

---

## 8. Build phases

### Phase 0 — Setup (Tue AM)
- [ ] Region `us-east-2`. **AWS Budgets** alarms at 50/80/100%.
- [ ] Bedrock: enable model access in `us-east-2` for one **fast** model (personas) and one **stronger** model (planner). Store IDs in env `PERSONA_MODEL_ID`, `PLANNER_MODEL_ID`.
- [ ] SES: verify team inboxes (sandbox is fine).
- [ ] End User Messaging SMS: request a **simulator origination number**; note the US simulator destination numbers.
- [ ] Subscribe to **COOL (Graviton4) AMI** → launch `c8g.2xlarge`, attach an IAM role (S3, DynamoDB, SQS, Bedrock, SSM, CloudWatch).
- [ ] Verify COOL: `source /opt/cool/venvs/python_3.12/bin/activate && python -c "import cv2, platform; print(cv2.__version__, cv2.__file__, platform.machine())"` → expect 5.x, a path under `/opt/cool`, and `aarch64`. **Save this output** (COOL award evidence).
- [ ] Repo scaffold (section 6), `ruff` + `black` + `pytest`, Makefile.
- [ ] CDK skeleton: S3 bucket(s), DynamoDB tables, IAM roles, SSM params. `cdk deploy` works.
- [ ] FIRMS MAP_KEY → SSM `/firecouncil/firms_map_key`. Kill switch → SSM `/firecouncil/kill_switch=false`.

**Done when:** `make test` passes, the data stack is deployed, COOL OpenCV 5 import is verified on Graviton, and the budget alarm is active.

### Phase 1 — Ingest & archive (Tue)
- [ ] Source adapters (`services/ingest/sources/`): `firms.py`, `goes.py`, `hpwren.py`, `alertca.py`, `caltrans.py`, `perimeters.py`, `nws.py`. Each one has a timeout, retry with backoff, an on-disk/S3 cache, and attaches `license` + `attribution` to every artifact.
- [ ] `data/cameras.yaml` watchlist:
  - ~6 HPWREN cams (e.g., Santiago Peak)
  - ~4 ALERTCalifornia cams near San Clemente / San Juan Capistrano
  - ~10 Caltrans D12 cams on I-5, SR-74 (Ortega Hwy), SR-73, PCH
  - a few D7 cams (LA)
  - include azimuth/hfov where known; `always_capture: true` for the corridor cams
- [ ] `poll_firms` (every 5 min): bbox `-120.5,32.5,-114.0,35.5`. Cluster hotspots within 5 km / 6 h into incidents.
- [ ] `poll_cameras` (every 2 min): cameras within 25 km of an active incident, or `always_capture`. Store to `s3://…/raw/{source}/{camera_id}/{YYYY}/{MM}/{DD}/{ts}.jpg` with metadata. **Start capturing today** to get real Santa Ana–season footage.
- [ ] `goes_listener`: SQS subscribed to `NewGOES18Object`. Keep only `ABI-L2-FDCC/` and the `ABI-L2-CMIPC/` bands you need. Crop to the SoCal bbox and save a compact `.npz` to S3. Fallback: poll the bucket prefix every 5 min.
- [ ] `replay_feeder`: reads `data/replays/*.yaml` (frame URIs + original timestamps), writes into the same `raw/` paths at real time or N× speed with simulated `captured_at`, and flips zone `official_status` on the replay's timeline.
- [ ] Pull to S3:
  - a FIgLib subset (~40 sequences)
  - GOES-18 FDCC/CMIPC for **Oct 16, 2026 10:00 → Oct 17 18:00 PDT** (Norte; ignition 11:33 a.m. Oct 16). S3 keys are UTC (`{product}/{YYYY}/{DOY}/{HH}/`): `2026/289/17` → `2026/291/01`
  - GOES-18 FDCC/CMIPC for **Jan 7, 2025 18:00 → Jan 8 08:00 PST** (Eaton night; ignition ~6:18 p.m. Jan 7): `2025/008/02` → `2025/008/16`

**Done when:** FIRMS hotspots appear as incidents, frames accumulate in S3 for watchlist cams, and `make replay R=figlib_001` plays a sequence into S3 at 1 frame/min (or 10×).

### Phase 2 — Vision service, OpenCV 5 (Wed)
All endpoints return JSON + evidence IDs, and log `cv2.__version__`, `cv2.__file__`, the host arch and per-stage milliseconds.

- [ ] `POST /smoke/check {camera_id, frame_uris[]}`
  1. Stabilize against the first frame (`cv2.phaseCorrelate` or ECC).
  2. Apply a per-camera static mask (horizon band, known false sources).
  3. Build a background model (`cv2.createBackgroundSubtractorMOG2`) over the window.
  4. Find candidates: persistent, growing, low-saturation blobs with upward DIS optical flow (`cv2.DISOpticalFlow`).
  5. Score with weighted features. *Stretch:* add an ONNX classifier via `cv2.dnn.readNetFromONNX` (OpenCV 5 engine).
  6. Convert the bbox column to a bearing using the camera azimuth/hfov.
  - **Output:** `smoke_prob`, bbox, `bearing_deg`, evidence image (overlay only if `overlay_allowed`).
- [ ] `POST /goes/track {incident_id, t_start, t_end}`
  - Load the FDCC fire mask/FRP (or BT 3.9 µm − 11.2 µm from CMIP).
  - Grid it to the SoCal bbox.
  - Per time step: OpenCV threshold + morphology + `connectedComponentsWithStats` + `findContours` + convex hull.
  - Track centroids → spread bearing and km/h. *Optional:* DIS flow on a visible band for plume direction.
  - **Output:** front polygon (GeoJSON), per-step polygons, growth, bearing, speed.
- [ ] `POST /routes/status {camera_ids[]}` — for each Caltrans cam, use the current frame + 6 previous frames:
  - vehicle detection via `cv2.dnn` with a **permissively licensed** YOLO ONNX (COCO car/truck/bus); **VERIFY license**, record it in `models/LICENSES.md`
  - stalled ratio (boxes overlapping across frames) and motion energy
  - haze score (dark-channel prior + Laplacian variance vs a per-camera clear-day baseline)
  - offline detection (identical frames / "no image" template)
  - **Output:** `RouteStatus`.
- [ ] `POST /triangulate` (stretch): two bearings → lat/lon.
- [ ] `GET /health`.
- [ ] Fixtures + tests: 3 smoke sequences (positive/negative), 5 Caltrans frame sets, 1 GOES subset.

**Done when:** tests pass on fixtures, a real FIgLib sequence returns a detection with an evidence image, and per-stage timings appear in CloudWatch.

### Phase 3 — Agents, rules & approval (Thu)
- [ ] **Strands Agents** (Python) with `BedrockModel`. One `Agent` per persona, each with its own system prompt and **only its own tools** (scoped access).
  - Orchestration is plain code (the Strands "Workflow" pattern): run Fire Ops, Evac & Traffic and Public Health **in parallel** (asyncio), then Planner → `rules.apply()` → Public Info, then write the Decision as `PENDING_APPROVAL`.
  - *Optional later:* Strands Graph. **VERIFY** the current Strands API in its docs before using.
- [ ] Persona tools:
  - **Fire Ops:** `firms_hotspots`, `goes_track`, `smoke_check(camera_ids)`, `perimeter(incident)`, `wind(lat, lon)` → `FireAssessment`
  - **Evac & Traffic:** `zone_status()`, `zones_in_path(eta_by_zone)`, `routes_status(camera_ids)` → `EvacAssessment`
  - **Public Health:** `care_facilities(zones)`, `vulnerable_residents(zones)`, `smoke_exposure(zones)` (optional) → `HealthAssessment`
  - **Planner:** no tools; merges the assessments → `ActionPlan` (then rules override)
  - **Public Info:** no tools; `ActionPlan` → `DraftMessage[]` (EN + ES)
- [ ] Agents can **request more evidence**: Fire Ops → `smoke_check` on a neighbor camera; Evac → `routes_status` on an alternate corridor.
  - Limits: max 2 extra tool rounds per persona, max 2 cycles per trigger, 60 s budget per cycle.
- [ ] Structured outputs (Pydantic). An invalid output gets one retry, then falls back to a **rule-only plan**.
- [ ] `rules.py` (deterministic; unit-tested):
  - **R1** Life safety outranks property and comfort.
  - **R2** A zone with fire ETA ≤ 120 min and official status `none|advisory` is a **gap** and must be in `zones_to_warn`.
  - **R3** ETA ≤ 60 min → `urgency = urgent`.
  - **R4** The recommended route must be `clear|slow` with evidence ≤ 10 min old. Otherwise use the next best route, or say "route unknown — follow officials".
  - **R5** A zone already under an official **order** gets "Evacuation ORDER in effect (official) — leave now" pointing to the official source. **We never create orders.**
  - **R6** Care facilities in gap zones go to `care_sites_first`.
  - **R7** Smoke-only (no fire ETA) → health guidance only.
  - **R8** When personas disagree, record the conflict and the rule that resolved it.
- [ ] **Trace** per cycle → `docs/traces/{incident}/{cycle}.jsonl` + DynamoDB. Record:
  - inputs (evidence IDs)
  - every tool call (name, args, latency, evidence, cv2 version/path)
  - persona outputs
  - rule hits
  - **plan diff vs the previous cycle**
  - approval event
- [ ] **Re-plan trigger:** an observation that changes a `RouteStatus.status` or adds a gap zone starts a new cycle. The previous pending draft becomes `SUPERSEDED`.

**Done when:** a replay produces a pending decision with 3 persona outputs, a plan, rule hits and EN + ES drafts. Then, when a route camera flips to `blocked`, a **new superseding draft with a different route** appears. That is the Agentic Vision trace.

### Phase 4 — Notify & acknowledge (Fri)
- [ ] `dispatcher.py`: on `APPROVED`, send to every resident in `zones_to_warn` on every enabled channel via adapters, and record `messages`. Check the kill switch first.
- [ ] Channels:
  - `EmailSES` (live)
  - `SmsEndUserMessaging` (simulator numbers, `simulated=true`)
  - `WebStatus` (zone page)
  - `AlexaStub` (section 15)
- [ ] Message template (all channels, EN + ES):
  > [ADVISORY] {Zone}: fire approaching from the {direction}, about {eta} min away (as of {time}). Leave now via {route} ({route_status} on camera at {cam_time}). Bring meds, ID, pets. Official orders: {official_link}. In danger now? Call 911. Confirm you got this: {ack_link}
- [ ] Ack: signed-token links (API Gateway) for email/SMS/web. The dashboard has a "simulate Echo reply" button for the Alexa stub.
- [ ] Step Functions:
  1. **Notify**
  2. **Wait** (`ACK_WINDOW_SECONDS`, default 600; 60 for the demo)
  3. **CheckAcks**
  4. For **vulnerable & unacknowledged** residents: **EscalateCaregiver** (SES) + dashboard flag "needs check"
  5. **Wait** → **Report**

**Done when:** approving a decision sends real emails to test inboxes, simulator SMS events appear in CloudWatch, the Alexa outbox shows an item with a playable Polly MP3, and an unacknowledged vulnerable resident triggers a caregiver email after the window.

### Phase 5 — Dashboard & public page (Fri)
- [ ] React + Vite + MapLibre (OSM tiles or Amazon Location), hosted on S3 + CloudFront, with a Cognito login.
- [ ] Views:
  - **Map:** hotspots, front polygon, zones by official status, **gap zones outlined in red**, cameras with their latest evidence
  - **Decision panel:** 3 persona cards side by side, the planner plan, conflicts + rule hits, evidence thumbnails (with attribution), **Approve / Edit / Reject**
  - **Delivery & acks:** per channel and zone, escalations, Alexa outbox audio player ("what the Echo would say")
  - **Trace viewer:** timeline of tool calls → decisions
  - **Public zone page** `/z/{zone_id}`: plain language, large text, high contrast, EN/ES, evidence image + attribution, ack button
- [ ] Accessibility: contrast, big tap targets, screen-reader labels.

**Done when:** a judge can open the HTTPS URL, log in with the demo account, and approve a replay decision.

### Phase 6 — Replays, evaluation, COOL benchmark (Sat)
- [ ] Replays:
  - **R1** FIgLib smoke sequences (camera path)
  - **R2** Norte Fire, Oct 16, 2026 (GOES + whatever HPWREN/Caltrans frames you captured or archived)
  - **R3** Eaton night, GOES only, with demo zones east/west of Lake Ave and the official alert times as the zone-status timeline
  - **R4** Scripted route blockage (Caltrans frame swap) to trigger a re-plan
- [ ] Run E1–E7 (section 9) → `eval/results/*.json` + charts.
- [ ] COOL benchmark: the **same vision pipeline** on `c8g.2xlarge` (COOL) vs `c7i.2xlarge` (stock OpenCV 5). Also run `github.com/opencv/COOL-Benchmark` for standard ops. Record:
  - instance types
  - COOL version (3.1) and OpenCV version
  - inputs, method, results

**Done when:** results tables exist with real numbers and **≥5 documented failure cases** (images + explanation).

### Phase 7 — Docs & submission (Sun–Mon)
- [ ] `docs/report.md` (technical report):
  - problem, users
  - architecture
  - OpenCV 5 implementation
  - AWS deployment
  - evaluation (incl. failures/limitations)
  - responsible use
  - COOL evidence section
  - Agentic evidence section
- [ ] `docs/architecture.mmd` + PNG (OpenCV 5, AWS, COOL, agents). `docs/agent_workflow.mmd` + PNG (perception → decision → action, human gate).
- [ ] README: pinned deps (`requirements.lock`, `package-lock.json`), build/deploy/test steps, demo login, how to run replays.
- [ ] Video ≤ 5 min (`docs/video_script.md`):
  - team (15 s)
  - problem, with the Jan 2025 facts (30 s)
  - demo (2.5 min): detection → agents' proposals → approval → email / SMS-sim / Alexa audio → ack + caregiver escalation → **re-plan when a route camera shows blockage**
  - architecture (30 s)
  - results + limits (45 s)
- [ ] Devpost: endpoint URL, judge repo access, video link, report.

**Done when:** a teammate who hasn't seen the project can deploy from the README and run R1 in ≤ 30 min.

---

## 9. Evaluation plan

| ID | What | Data | Metrics |
|---|---|---|---|
| E1 | Smoke confirmation | FIgLib held-out (~30 sequences) | detection rate ≤ 10 min after ignition; median time-to-detect; false alarms per camera-hour on pre-ignition frames; breakdown (haze, glare) |
| E2 | Route status | ~200 hand-labeled Caltrans frame sets from your own captures | per-class precision/recall; latency |
| E3 | Gap detection replay | Norte (Oct 16, 2026), Eaton night (Jan 7–8, 2025) | time of first hotspot; time the planner first drafts a warning per demo zone vs the official timeline. State the ~2 km GOES pixel limit honestly. **Eaton benchmark (west Altadena, 18 of 19 deaths):** residents and radio reported fire west of Lake Ave from ~10:50 p.m.; the county began expanding orders at 2:18 a.m.; messages went out at 3:25 a.m.; the county's review puts the main front west of Lake Ave at ~5:13 a.m. The timeline is disputed, so cite both accounts (section 16). |
| E4 | Message completeness | 50 generated drafts | rubric: zone, threat + direction, time, action, route + status, evidence link, official-source link, 911/advisory line. Compare to the Jan 9, 2025 alert, which named no location ("An EVACUATION WARNING has been issued in your area") |
| E5 | Acknowledgement loop | 60 synthetic households (15 vulnerable; mix incl. no smartphone, Echo-only) | % confirmed ≤ 10 min, escalations, time to caregiver contact. Scenarios: normal, **power shutoff** (Echo/Wi-Fi off), cell outage |
| E6 | Latency & cost | replays | frame → draft (p50/p95); Bedrock tokens and $ per cycle; infra $/day |
| E7 | COOL vs x86 | same frames, same pipeline | frames/s, p50/p95 per stage, CPU %, **$ per 1,000 frames** |

---

## 10. Responsible use & guardrails

- **Advisory only.** The system never issues evacuation orders. Every public message is **human-approved** and tells people to follow official orders and call 911 in danger.
- **Licenses:**
  - HPWREN attribution
  - ALERTCalifornia **CC BY-NC-ND** (no modified redistribution, credit, no cropping)
  - Caltrans CWWP2 conditions
  - NOAA attribution
  - FIRMS terms
  - Model licenses recorded in `models/LICENSES.md`
- **Privacy:** synthetic residents only. Caltrans frames downscaled to ≤640 px; blur any person/plate detections before saving evidence. Minimal PII, encryption at rest, 14-day retention on raw frames.
- **Fairness:** gap detection depends only on geometry and time. Add a check that every zone in the projected path is evaluated the same way, with equal EN/ES message quality.
- **Good citizen:** rate limits + caching on public cameras; only near active incidents.
- **Safety switches:** the SSM kill switch stops all sends. Approval is required even in replays. Everything is labeled "DEMO".
- **Future Alexa:** health guidance needs Amazon's disclaimer (not a substitute for medical advice; call emergency services in an emergency).

---

## 11. Submission checklist (from the rules)

- [ ] OpenCV 5 performs substantive image/video analysis (smoke, GOES tracking, routes)
- [ ] Meaningful AWS component
- [ ] Technical report: problem, users, architecture, OpenCV 5 implementation, AWS deployment, evaluation, limitations, responsible use
- [ ] Judge-accessible repo; pinned dependencies; build/deploy/test instructions
- [ ] Architecture diagram showing OpenCV 5 + AWS (+ COOL + agent components)
- [ ] Working web endpoint (CloudFront) or arranged live screen-share
- [ ] Video ≤ 5 min: team, app working, architecture, principal results
- [ ] Evaluation evidence incl. failure cases
- **Best Use of COOL:**
  - [ ] COOL version + instance config
  - [ ] evidence COOL runs the core workload (`cv2.__file__` under `/opt/cool`, `aarch64` in logs)
  - [ ] reproducible benchmark method, inputs, baseline, results
- **Agentic Vision:**
  - [ ] workflow diagram (perception → decision → action, human control)
  - [ ] trace where OpenCV output changes a later tool call/action (route blocked → new route → new draft)
  - [ ] evaluation of task success, failure handling, observability, human control

---

## 12. Risks & fallbacks

| Risk | Fallback |
|---|---|
| No live fire during judging | Replays are first-class; dashboard "Replay" switch |
| Camera feeds change or go offline | Cached fixtures; adapters return `unknown`, never crash |
| GOES smoke vs cloud confusion | Use the FDCC fire mask for fire; smoke is supporting only; document failures |
| LLM latency/flakiness | Small fast model for personas, strict schemas, rule-only fallback plan |
| Real SMS needs registration | Simulator numbers (documented in report) |
| COOL trial converts to paid | Cancel after judging; stop instances when idle |
| Bedrock model access delay | Request on day 1 in `us-east-2`; keep a second model ID ready |
| Cross-region SNS subscription blocked by the SCP | Poll the GOES bucket prefix every 5 minutes |
| Scope creep | Anything outside Phases 0–7 → `docs/FUTURE.md` |

---

## 13. Schedule (PDT)

| Day | Work |
|---|---|
| Tue 10/20 | Phase 0 + Phase 1 (**start camera capture today**) |
| Wed 10/21 | Phase 2 |
| Thu 10/22 | Phase 3 |
| Fri 10/23 | Phase 4 + Phase 5 |
| Sat 10/24 | Phase 6 |
| Sun 10/25 | Phase 7 (report, diagrams, video) |
| Mon 10/26 | Freeze 6:00 pm, submit before 11:45 pm |

---

## 14. Config / env vars

```bash
AWS_REGION=us-east-2
FC_BUCKET=firecouncil-<account>-data
FC_TABLE_PREFIX=fc_
FIRMS_MAP_KEY_PARAM=/firecouncil/firms_map_key
WATCH_BBOX=-120.5,32.5,-114.0,35.5
PERSONA_MODEL_ID=<bedrock model id>
PLANNER_MODEL_ID=<bedrock model id>
VISION_URL=http://localhost:8080
ACK_WINDOW_SECONDS=600          # 60 for the demo
SMS_MODE=simulator              # simulator | off
ALEXA_MODE=stub                 # stub | smart_home | proactive_events (future)
KILL_SWITCH_PARAM=/firecouncil/kill_switch
```

---

## 15. Alexa placeholder — "this will trigger an Alexa skill"

**MVP (`ALEXA_MODE=stub`), implement now:**

```python
class AlexaChannel(Channel):
    """Placeholder. In production this triggers an Alexa skill; in the MVP it renders and records the announcement."""
    def send(self, zone_id: str, msg: DraftMessage) -> DeliveryResult:
        # 1. Validate SSML ≤ 25 s.
        # 2. Synthesize MP3 with Amazon Polly (EN or ES voice) → s3://…/alexa/{decision_id}/{zone_id}.mp3
        # 3. Write alexa_outbox item {zone_id, ssml, audio_url, mechanism: "stub", intended: "smart_home_contact_sensor"}
        # 4. Return DeliveryResult(simulated=True)
        ...
```

The dashboard plays the MP3 as **"what the Echo would say"**, and a button simulates the resident's spoken confirmation.

**Future (after the hackathon):**
- **Spoken push (`smart_home`).** A smart home skill exposes one virtual **contact sensor per zone** ("FireCouncil Zone 9"). On approval, send an `Alexa.ChangeReport` (OPEN). The resident sets up a routine once: "When FireCouncil Zone 9 opens → announce on all devices."
- **Pull.** A custom skill: "Alexa, ask FireCouncil about my area" reads the latest approved plan for the linked address. The Echo Show card shows the unmodified evidence image with attribution.
- **Backup (`proactive_events`).** Notifications chime and show a yellow ring; the user has to ask to hear them, and they must use Amazon's predefined formats. Too passive to rely on alone.
- **Alexa+.** Add-ons are partner-only today. If access opens, `services/vision/mcp_server.py` can be reused as an MCP add-on.
- **Policy.** Include the medical disclaimer for health tips, and never claim the skill contacts emergency services.

---

## 16. Reference links

- Competition: https://opencv26.devpost.com/
- COOL: https://opencv.org/cool/ · Marketplace (Graviton4): https://aws.amazon.com/marketplace/pp/prodview-fdvbfiewzuehs · Benchmark: https://github.com/opencv/cool-benchmark
- OpenCV 5 DNN: https://opencv.org/opencv-dnn-module/
- GOES on AWS: https://registry.opendata.aws/noaa-goes/ · https://github.com/awslabs/open-data-registry/blob/main/datasets/noaa-goes.yaml
- FIRMS API: https://firms.modaps.eosdis.nasa.gov/api/area/
- HPWREN image access: https://www.hpwren.ucsd.edu/news/20180501/ · FIgLib: http://hpwren.ucsd.edu/HPWREN-FIgLib/
- ALERTCalifornia terms: https://alertcalifornia.org/terms/ · images: https://alertcalifornia.org/images-and-video/
- Caltrans CWWP2: https://cwwp2.dot.ca.gov · CCTV fields: https://cwwp2.dot.ca.gov/documentation/cctv/cctv-field-description.htm
- FIRIS perimeters: https://catalog.data.gov/dataset/ca-perimeters-cal-fire-nifc-firis-public-view
- Norte Fire incident page: https://www.fire.ca.gov/incidents/2026/10/16/norte-fire
- Eaton / west Altadena timeline: county review https://recovery.lacounty.gov/2026/05/18/county-of-los-angeles-fire-department-releases-independent-investigation-findings-of-west-altadena-evacuation-decisions/ · https://www.fireengineering.com/firefighting/wildland-firefighting/eaton-fire-no-misconduct-delay-in-evacuation-notices-to-west-altadena-ca-report-says/ · https://www.fireengineering.com/firefighting/wildland-firefighting/report-eaton-fire-marched-toward-west-altadena-hours-before-official-accounts
- SMS simulator: https://docs.aws.amazon.com/sms-voice/latest/userguide/test-phone-numbers.html
- Bedrock Agents Classic status: https://docs.aws.amazon.com/bedrock/latest/userguide/agents-classic-maintenance-mode.html
- Strands multi-agent patterns: https://strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/
- Alexa: Proactive Events https://developer.amazon.com/docs/smapi/proactive-events-api.html · Custom triggers https://developer.amazon.com/en-US/docs/alexa/routines/get-started-custom-triggers-for-routines.html · Skill policy https://developer.amazon.com/en-US/docs/alexa/custom-skills/policy-requirements-for-an-alexa-skill.html
