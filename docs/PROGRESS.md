# Progress

Mirrors the checkboxes in [PLAN.md](../PLAN.md). Tick an item here only when it is actually done. Do not start a phase until the previous phase's **Done when** checks pass.

## Phase 0 — Setup

- [ ] Region `us-east-2`. AWS Budgets alarms at 50/80/100%.
- [ ] Bedrock: enable model access for one fast model (personas) and one stronger model (planner). Store IDs in `PERSONA_MODEL_ID` and `PLANNER_MODEL_ID`.
- [ ] SES: verify team inboxes (sandbox is fine).
- [ ] End User Messaging SMS: request a simulator origination number; note the US simulator destination numbers.
- [ ] Deferred until credits are available: subscribe to the COOL (Graviton4) AMI, launch `c8g.2xlarge`. Current vision uses stock OpenCV 5 (`opencv-python-headless==5.0.0.93`) on the laptop.
- [ ] Verify COOL when that instance exists: OpenCV 5.x, `cv2.__file__` under `/opt/cool`, `aarch64`. Save the output.
- [ ] Repo scaffold, `ruff` + `black` + `pytest`, Makefile. Layout and README are in place; tooling is not.
- [ ] CDK skeleton: S3 bucket(s), DynamoDB tables, IAM roles, SSM params. `cdk deploy` works.
- [ ] FIRMS MAP_KEY in SSM `/firecouncil/firms_map_key`. Kill switch in SSM `/firecouncil/kill_switch=false`.

**Done when:** `make test` passes on stock OpenCV 5, the bucket exists in `us-east-2`, and the budget alarm is active. COOL verification waits until that instance is launched.

## Phase 1 — Ingest and archive

- [ ] Source adapters in `services/ingest/sources/`: `firms`, `goes`, `hpwren`, `alertca`, `caltrans`, `perimeters`, `nws`. Each has timeout, retry with backoff, cache, and license plus attribution.
- [ ] `data/cameras.yaml` watchlist (HPWREN, ALERTCalifornia, Caltrans D12 and D7).
- [ ] `poll_firms` every 5 min. Cluster hotspots within 5 km / 6 h into incidents.
- [ ] `poll_cameras` every 2 min. Store frames under `raw/{source}/{camera_id}/{YYYY}/{MM}/{DD}/{ts}.jpg`.
- [ ] `goes_listener` on `NewGOES18Object`. Keep FDCC and the CMIPC bands we need. Crop to the SoCal bbox.
- [ ] `replay_feeder` reads `data/replays/*.yaml` and writes the same `raw/` paths.
- [ ] Pull FIgLib subset and GOES-18 windows for Norte (Oct 16–17, 2026) and Eaton night (Jan 7–8, 2025).

**Done when:** FIRMS hotspots appear as incidents, frames accumulate in S3 for watchlist cameras, and `make replay R=figlib_001` plays a sequence into S3.

## Phase 2 — Vision service (OpenCV 5)

- [ ] `POST /smoke/check`
- [ ] `POST /goes/track`
- [ ] `POST /routes/status`
- [ ] `POST /triangulate` (stretch)
- [ ] `GET /health`
- [ ] Fixtures and tests: 3 smoke sequences, 5 Caltrans frame sets, 1 GOES subset.

**Done when:** tests pass on fixtures, a real FIgLib sequence returns a detection with an evidence image, and per-stage timings appear in CloudWatch.

## Phase 3 — Agents, rules, and approval

- [ ] Strands Agents: one agent per persona, own prompt, own tools. Parallel personas, then Planner, `rules.apply()`, Public Info, `PENDING_APPROVAL`.
- [ ] Persona tools scoped as in PLAN.md.
- [ ] Extra-evidence limits: 2 tool rounds per persona, 2 cycles per trigger, 60 s per cycle.
- [ ] Structured outputs. One retry, then a rule-only plan.
- [ ] `rules.py` R1–R8, unit-tested.
- [ ] Trace per cycle in `docs/traces/` and DynamoDB.
- [ ] Re-plan when a route status or gap zone changes. Previous pending draft becomes `SUPERSEDED`.

**Done when:** a replay produces a pending decision with 3 persona outputs, a plan, rule hits, and EN + ES drafts. A route camera flipping to `blocked` produces a new superseding draft with a different route.

## Phase 4 — Notify and acknowledge

- [ ] `dispatcher.py` on `APPROVED`, kill switch checked first.
- [ ] Channels: SES email, SMS simulator, web status, Alexa stub.
- [ ] Message template (EN + ES) names zone, threat, direction, time, action, route, evidence, official source, and 911.
- [ ] Signed-token ack links. Dashboard "simulate Echo reply" button.
- [ ] Step Functions: Notify → Wait → CheckAcks → EscalateCaregiver → Report.

**Done when:** approval sends real email to test inboxes, simulator SMS events appear in CloudWatch, the Alexa outbox has a playable Polly MP3, and an unacknowledged vulnerable resident triggers a caregiver email after the window.

## Phase 5 — Dashboard and public page

- [ ] React + Vite + MapLibre on S3 + CloudFront, Cognito login.
- [ ] Map, decision panel, delivery and acks, trace viewer, public zone page `/z/{zone_id}`.
- [ ] Accessibility: contrast, big tap targets, screen-reader labels.

**Done when:** a judge can open the HTTPS URL, log in with the demo account, and approve a replay decision.

## Phase 6 — Replays, evaluation, COOL benchmark

- [ ] Replays R1 FIgLib, R2 Norte, R3 Eaton night, R4 scripted route blockage.
- [ ] E1–E7 results in `eval/results/`.
- [ ] COOL benchmark: same vision pipeline on `c8g.2xlarge` (COOL) vs `c7i.2xlarge` (stock OpenCV 5).

**Done when:** results tables exist with real numbers and at least 5 documented failure cases.

## Phase 7 — Docs and submission

- [ ] `docs/report.md`
- [ ] `docs/architecture.mmd` and `docs/agent_workflow.mmd` (plus PNGs)
- [ ] README includes pinned deps, build/deploy/test steps, demo login, and how to run replays.
- [ ] `docs/video_script.md` and a video of 5 minutes or less.
- [ ] Devpost: endpoint URL, judge repo access, video link, report.

**Done when:** a teammate who has not seen the project can deploy from the README and run R1 in 30 minutes or less.

## Submission checklist

- [ ] OpenCV 5 performs substantive image and video analysis (smoke, GOES tracking, routes).
- [ ] Meaningful AWS component.
- [ ] Technical report: problem, users, architecture, OpenCV 5, AWS, evaluation, limitations, responsible use.
- [ ] Judge-accessible repo; pinned dependencies; build, deploy, and test instructions.
- [ ] Architecture diagram showing OpenCV 5, AWS, COOL, and agents.
- [ ] Working web endpoint (CloudFront) or a live screen-share.
- [ ] Video of 5 minutes or less: team, app working, architecture, principal results.
- [ ] Evaluation evidence including failure cases.
- [ ] COOL: version, instance config, `cv2.__file__` under `/opt/cool` and `aarch64` in logs, reproducible benchmark.
- [ ] Agentic Vision: workflow diagram, a trace where OpenCV output changes a later action, evaluation of task success, failures, observability, and human control.
