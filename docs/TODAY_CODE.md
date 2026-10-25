# Local code — Tuesday Oct 20

Write this on your laptop while [TODAY_AWS.md](TODAY_AWS.md) runs. Tests use files on disk. They do not call AWS.

The AWS account for this build is Budgets, Bedrock, and one S3 bucket, all in `us-east-2`. Vision runs on this laptop with stock OpenCV 5 from PyPI. COOL is a later host for the same `import cv2` code, after you choose to spend credits. There is no EC2 instance in this pass.

| Concern | Where it lives tonight |
|---|---|
| Decisions, messages, acks | `data/local/*.json` |
| Off switch, model ids, FIRMS key | `.env` from the AWS doc. `KILL_SWITCH=false`. Blank model ids mean rules only. |
| Evidence images | `data/local/evidence/` |
| Vision | This laptop, `opencv-python-headless==5.0.0.93` |
| Bedrock | Skipped until `PERSONA_MODEL_ID` is set. Tests leave it unset. |
| S3 | The bucket can exist. Uploading evidence into it comes after the replay works. Copy the same files to `s3://$FC_BUCKET/evidence/`. |

Python 3.12. `runtime_info()` records `cv2.__version__` and `cv2.__file__` on every vision call. That line is how a later COOL run shows `/opt/cool` without a second code path.

## Done when

`pytest` passes, and one local command prints two decisions for the `route_block` replay:

1. Pending, recommended route `sr74`.
2. A new pending decision, recommended route `i5`, and the first decision `SUPERSEDED`.

That second decision is the demo. Steps 7–10 below are still tonight if that command already works.

## Scenario the tests lock in

Incident `norte-replay`. Two demo zones, labeled demo, not official.

| Zone | ETA | Official status | Who is there |
|---|---|---|---|
| `capistrano` | 45 min | `none` | Care site `care-1`, vulnerable resident `r-vulnerable` |
| `san_clemente` | 180 min | `advisory` | Resident `r-ok`, not vulnerable |

Routes, evidence age in seconds:

| Cycle | sr74 (Ortega Hwy) | i5 |
|---|---|---|
| 1 | `clear`, 60s, evidence `ev-sr74-1` | `slow`, 60s, `ev-i5-1` |
| 2 | `blocked`, 30s, `ev-sr74-2` | `slow`, 30s, `ev-i5-2` |

What the rules must produce:

- Cycle 1 warns `capistrano` only. `san_clemente` is outside 120 minutes, so it is not a gap. Urgency is `urgent` because 45 ≤ 60. Route is `sr74`. `care-1` is first. Messages exist in `en` and `es`.
- Cycle 2 route is `i5`, because a blocked road cannot be the recommendation and `i5` is `slow` with evidence newer than 10 minutes. Cycle 1 becomes `SUPERSEDED`. The plan diff names the route change.

## 0. Tooling

From the repo root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements-dev.txt`

```text
pydantic>=2.9
pytest>=8.3
ruff>=0.7
black>=24.10
fastapi>=0.115
uvicorn>=0.32
numpy>=2.1
opencv-python-headless==5.0.0.93
pyyaml>=6.0
```

`requirements.txt` carries the same OpenCV pin, plus pydantic, fastapi, uvicorn, numpy, and pyyaml. Dev tools stay in the dev file. Install only one OpenCV package in the venv. If pip says this platform has no headless wheel, install `opencv-python==5.0.0.93` instead and remove the headless line.

After install, this must print a `5.0` version:

```bash
python -c "import cv2; print(cv2.__version__, cv2.__file__)"
```

Do not add `boto3` tonight. There is no DynamoDB client and no SES client in this pass.

Add `data/local/` to `.gitignore`. That directory holds decisions, the outbox, and evidence images.

`Makefile`

```make
.PHONY: setup test replay

setup:
	python3.12 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

test:
	.venv/bin/pytest -q

replay:
	.venv/bin/python -m services.agents.orchestrator --replay route_block
```

Add empty `__init__.py` files in `services`, `services/agents`, `services/agents/personas`, `services/vision`, `services/vision/cv`, `services/notify`, `services/api`, and `tests`.

## 1. Schemas — `services/agents/schemas.py`

Pydantic models from [PLAN.md](../PLAN.md) section 7: `Evidence`, `FireAssessment`, `RouteStatus`, `EvacAssessment`, `HealthAssessment`, `ActionPlan`, `DraftMessage`.

Add the decision the orchestrator writes:

```python
class Decision(BaseModel):
    incident_id: str
    cycle_ts: str
    fire: FireAssessment
    evac: EvacAssessment
    health: HealthAssessment
    plan: ActionPlan
    messages: list[DraftMessage]
    status: Literal["DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED", "SUPERSEDED"]
    diff_from_prev: dict
```

## 2. Rules — `services/agents/rules.py`

```python
def apply(fire, evac, health, zones, care_sites) -> ActionPlan:
    ...
```

`zones` maps zone id → official status (`none`, `advisory`, `warning`, `order`). `care_sites` is a list of `{id, zone_id, name}`.

| Rule | Behavior |
|---|---|
| R1 | Life safety first. Sort `zones_to_warn` so a zone with a care site or a vulnerable resident comes before the others, then by smaller ETA. |
| R2 | A zone with ETA ≤ 120 and status `none` or `advisory` is a gap and is in `zones_to_warn`. Add it even if Evac omitted it. |
| R3 | Any warned zone with ETA ≤ 60 sets `urgency` to `urgent`. Otherwise `advisory`. |
| R4 | The route must be `clear` or `slow`, with `age_s` ≤ 600. Otherwise take the next route that qualifies. If none qualify, `route` is null and the rationale contains `route unknown — follow officials`. |
| R5 | A zone already under an official `order` is not a gap. We never create an order. If that zone is mentioned, the copy is `Evacuation ORDER in effect (official) — leave now`. |
| R6 | Care sites whose zone is a gap go in `care_sites_first`. |
| R7 | If no zone has an ETA and `smoke_confirmed` is true, warn nobody and keep health guidance only. |
| R8 | If Evac's gap list or route differs from the rule result, append a conflict string and the rule id that resolved it. |

`rule_hits` lists the rule ids that fired. `evidence_ids` comes from the fire assessment plus the chosen route's evidence id.

`tests/test_rules.py` covers the scenario table above, plus: an `order` zone is not added as a gap, stale evidence (`age_s` 700) drops the route, and smoke with no ETAs warns nobody.

## 3. Templates — `services/notify/templates/messages.py`

```python
def render(plan, zone_name, lang, when, evidence_url, ack_link, official_link) -> DraftMessage:
    ...
```

English body, then the same facts in Spanish. Prefix `[ADVISORY]` or `[URGENT]` from `plan.urgency`. One R5 zone uses the official-order sentence instead.

Facts every body includes: zone, direction, ETA minutes, time, route and its camera status, evidence link, official-orders link, `Call 911`, and the ack link. SMS is the same facts trimmed to 300 characters. `voice_ssml` is a short speakable version of that sentence.

Direction is a compass word from `spread_bearing_deg` (N, NE, E, SE, S, SW, W, NW).

## 4. Vision — `services/vision/cv/`

Each function returns JSON plus an evidence id, and a timings dict with stage names in milliseconds. A helper `runtime_info()` returns `cv2.__version__`, `cv2.__file__`, and `platform.machine()`.

Build fixtures in the test with NumPy, then write them under `tests/fixtures/`. Tests load those files. They do not generate images on the fly after the first save, so the run is stable.

**`route_status.py`** — `status_for_frames(route_id, frame_paths) -> RouteStatus`

Tonight's detector, using real OpenCV:

- Resize the long side to at most 640 px.
- `cv2.absdiff` across the window, then motion energy.
- A large region that stays put while the rest of the frame is quiet counts as stalled. High stalled ratio → `blocked`.
- Some motion and a small stalled ratio → `clear` or `slow`.
- Nearly identical frames, or a flat "no image" frame → `unknown`.

`tests/fixtures/routes/clear/` is moving bright rectangles on a gray road. `tests/fixtures/routes/blocked/` is one large rectangle that does not move. The test expects `clear` and `blocked`. Record in `services/vision/models/LICENSES.md` that tonight's detector is classical OpenCV and an ONNX detector is not wired yet.

**`goes_track.py`** — `track_masks(mask_paths, km_per_pixel) -> dict`

Per mask: threshold, morphology open and close, `connectedComponentsWithStats`, `findContours`, convex hull. Track the largest component's centroid. Bearing and km/h come from the centroid step and `km_per_pixel`. Return a GeoJSON polygon for the last hull.

Fixture: `tests/fixtures/goes/moving_blob.npz`, three masks whose blob moves northeast. The test expects a bearing in the northeast quadrant and a positive speed.

**`smoke.py`** — only after the two tests above pass.

`check_frames(frame_paths, azimuth_deg, hfov_deg) -> dict` with `smoke_prob`, `bbox`, `bearing_deg`. Stabilize with `cv2.phaseCorrelate`, background with `cv2.createBackgroundSubtractorMOG2`, keep low-saturation blobs, and require upward motion from `cv2.DISOpticalFlow`. Draw an evidence image only when `overlay_allowed` is true.

**`services/vision/app.py`**

FastAPI. `GET /health` returns `runtime_info()`. `POST /routes/status`, `POST /goes/track`, and `POST /smoke/check` call the functions above. Bind `127.0.0.1:8080`.

Write evidence images under `data/local/evidence/`. The message link is that local path tonight. Tomorrow, when `FC_BUCKET` is set, copy the same file to `s3://$FC_BUCKET/evidence/` and use that URL. The vision functions stay the same either way.

## 5. Replay file — `data/replays/route_block.yaml`

Encode the scenario table: incident id, two cycles, both routes, both zones, `care-1`, and the two residents. `official_status` on every zone stays `manual` / demo. Include `captured_at` timestamps so evidence age is computable.

`services/agents/replay.py` loads that YAML into the dataclasses the orchestrator accepts. A test loads it and checks both cycles and the zone ETAs.

## 6. Orchestrator — `services/agents/orchestrator.py`

```python
def run_cycle(snapshot, previous: Decision | None) -> Decision:
    ...
```

`snapshot` is one replay cycle plus the zones, care sites, and residents.

Order:

1. Fire, Evac, and Health build their assessments from the snapshot. These are plain functions in `services/agents/personas/`. Each one may call the local vision functions on the fixture paths in the replay. They call Bedrock only when `PERSONA_MODEL_ID` is set, which tests do not do.
2. A planner function merges them into a draft `ActionPlan`.
3. `rules.apply` replaces the planner's zones, urgency, route, and care sites.
4. `render` writes `en` and `es` messages for each zone in `zones_to_warn`.
5. Status is `PENDING_APPROVAL`.
6. If `previous` exists, set `previous.status` to `SUPERSEDED` and set `diff_from_prev` to the changed route and zone list.

`python -m services.agents.orchestrator --replay route_block` prints both decisions as JSON.

`tests/test_orchestrator.py` asserts the route flip, the superseded status, both languages, and `care-1` in `care_sites_first`.

When `PERSONA_MODEL_ID` is set, a persona may call Bedrock and must parse into the same Pydantic model. One failed parse retries once, then the plain function runs. An empty model id skips Bedrock. That is the only AWS call in this codebase, and it is off for the local tests.

## 7. Store — `services/agents/store.py`

```python
class Store(Protocol):
    def save_decision(self, decision: Decision) -> None: ...
    def list_decisions(self, incident_id: str) -> list[Decision]: ...
```

`JsonStore` is the store. It writes `data/local/decisions.json`. Tests use a temp directory. There is no DynamoDB table and no second implementation. Residents and acks for this replay can live in the same JSON file or in the replay YAML. The approval API reads them back from `JsonStore`.

## 8. Approval API — `services/api/handlers.py`

FastAPI, or routes on the vision app if that is less to run.

- `GET /decisions/{incident_id}` returns the decisions, newest first.
- `POST /decisions/{incident_id}/{cycle_ts}/approve`
- `POST /decisions/{incident_id}/{cycle_ts}/reject`
- `POST /decisions/{incident_id}/{cycle_ts}/edit` updates the route or the zone list, then leaves status `PENDING_APPROVAL`.

Approve calls the dispatcher. A test uses `JsonStore` and checks reject never calls it.

## 9. Notify — `services/notify/dispatcher.py`

```python
def dispatch(decision, residents, kill_switch: bool) -> list[dict]:
    ...
```

Read `KILL_SWITCH` from the environment. The string `true` returns before any send. Default is `false`, matching `.env`. For each resident in a warned zone, record a message row (`channel`, `resident_id`, body).

`EmailChannel.send` appends the body to `data/local/outbox.jsonl`. That file is the demo send. Tests assert the outbox line exists, and assert that `KILL_SWITCH=true` leaves the file empty. SES is a later swap of this function, after the replay works, and only to a verified inbox. Do not import SES tonight.

The `sms` and `voice_ssml` fields are still filled by the template so the draft is complete. Nothing sends them.

Ack: `services/ack/check_acks.py` marks a resident acknowledged in the JSON store. `escalate` returns the caregiver address when the resident is vulnerable and the ack window passed. A test covers that pair. The window value is `ACK_WINDOW_SECONDS` from `.env` (60 for the demo).

## 10. Trace — `services/agents/trace.py`

Append JSON lines to `docs/traces/{incident_id}/{cycle_ts}.jsonl`. Each tool line has name, args, latency milliseconds, evidence id, and `runtime_info()`. One line lists `rule_hits`. One line is `diff_from_prev`. The test runs `route_block` and checks the second cycle's diff says `sr74` → `i5`.

## Leave for later

Copy evidence images to `s3://$FC_BUCKET/evidence/` from this laptop. Screen-share the approval page on `localhost`.

The COOL switch happens only when you choose to spend the credits. Launch the Graviton COOL image, run this same code inside `/opt/cool/venvs/python_3.12`, and save the `runtime_info()` line. Do not pip-install OpenCV on that host. Until then, every run uses the PyPI package.

Optional once the replay works: send the outbox through SES.

Still out of this build, so this code does not grow clients for them: DynamoDB, SSM Parameter Store, Lambda, API Gateway, CloudFront, Cognito, Step Functions, EventBridge, SQS, SNS, SMS, and Polly. Live FIRMS and camera polling stay off. The replay file is the trigger.
