"""Local approval page. A person reads the decision and approves it here."""

import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from services.agents.review import hold_warning
from services.agents.schemas import Decision
from services.api.live_feed import alert_from_views, ready_frames, ready_views
from services.notify.templates.messages import compass

_EVIDENCE = Path("data/local/evidence")
_PACIFIC = ZoneInfo("America/Los_Angeles")

_INCIDENTS = {
    "norte-replay": ("Norte Fire", "Orange County", "California"),
}
_ZONES = {
    "capistrano": "San Juan Capistrano",
    "san_clemente": "San Clemente",
}
_ROADS = {
    "sr74": ("Ortega Highway", "SR-74"),
    "i5": ("Interstate 5", "I-5"),
}
_TRAFFIC = {
    "clear": "open",
    "slow": "slow, but moving",
    "blocked": "blocked",
    "unknown": "not known from the camera",
}
_STATUS = {
    "PENDING_APPROVAL": "Waiting for you",
    "APPROVED": "Approved",
    "REJECTED": "Rejected",
    "SUPERSEDED": "Replaced",
    "DRAFT": "Draft",
}


def render_dashboard(
    decision: Decision | None,
    previous: Decision | None,
    sent: list[dict],
) -> str:
    """Return the approval page for the newest decision."""
    body = _empty() if decision is None else _decision(decision, previous, sent)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FireCouncil</title>
<style>
  body {{ margin: 0; background: #eaeded; color: #0f1111; font: 14px/1.4 Arial, Helvetica, sans-serif; }}
  .nav {{ background: #131921; color: #fff; padding: 12px 18px; font-size: 13px; }}
  .wrap {{ max-width: 1200px; margin: 0 auto; padding: 12px; }}
  .screen {{ display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 16px; align-items: start;
    background: #fff; padding: 12px 14px 16px; }}
  .views {{ position: sticky; top: 8px; }}
  .product {{ display: grid; grid-template-columns: minmax(280px, 1.3fr) minmax(280px, 0.8fr); gap: 20px;
    background: #fff; padding: 16px 18px 20px; }}
  h1 {{ font-size: 21px; font-weight: 400; line-height: 1.3; margin: 4px 0 8px; }}
  h2 {{ font-size: 18px; font-weight: 700; margin: 0 0 10px; }}
  p {{ margin: 6px 0; }}
  img {{ width: 100%; height: auto; display: block; border: 1px solid #ddd; background: #fff; }}
  figcaption {{ color: #565959; font-size: 13px; margin-top: 8px; }}
  .buy {{ border: 1px solid #d5d9d9; border-radius: 8px; padding: 14px 16px 16px; }}
  .status {{ color: #007600; font-size: 18px; margin: 0 0 6px; }}
  .status.waiting {{ color: #b12704; }}
  .status.rejected {{ color: #b12704; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td {{ padding: 5px 12px 5px 0; vertical-align: top; }}
  td.k {{ color: #565959; width: 88px; }}
  .panel {{ background: #fff; margin-top: 12px; padding: 16px 18px; }}
  pre {{ white-space: pre-wrap; font: inherit; margin: 0; }}
  button {{ font: inherit; min-height: 31px; width: 100%; border-radius: 20px; cursor: pointer; margin-top: 8px; }}
  button.approve {{ background: #ffd814; border: 1px solid #fcd200; color: #0f1111; }}
  button.reject, button.again {{ background: #fff; border: 1px solid #d5d9d9; color: #0f1111; }}
  .fine {{ color: #565959; font-size: 12px; }}
  a {{ color: #007185; }}
  .bank {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }}
  .bank img {{ height: 30vh; min-height: 160px; max-height: 250px; object-fit: contain; background: #111; }}
  .bank figcaption {{ font-size: 12px; line-height: 1.3; margin-top: 4px; }}
  .crew {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 14px; }}
  .agent {{ border: 1px solid #d5d9d9; border-radius: 8px; background: #f7f8f8; padding: 12px 12px 14px; }}
  .agent svg {{ width: 92px; height: 92px; display: block; margin: 0 auto 6px; }}
  .agent h3 {{ font-size: 14px; font-weight: 700; text-align: center; margin: 0; }}
  .agent .role {{ color: #565959; font-size: 12px; text-align: center; margin: 2px 0 8px; }}
  .agent .says, .agent .still {{ font-size: 13px; margin: 0; }}
  .still, .while-checking {{ display: none; }}
  .finding .when-ready, .finding .says, .finding ~ .after-check {{ display: none; }}
  .finding .while-checking, .finding .still {{ display: block; }}
  .finding.agents-in .says {{ display: block; }}
  .finding.agents-in .still {{ display: none; }}
  figure.cam {{ position: relative; margin: 0; }}
  a.shot {{ position: relative; display: block; }}
  .osd {{
    position: absolute; top: 4px; left: 4px; right: auto; max-width: calc(100% - 8px);
    display: flex; gap: 8px;
    padding: 2px 6px; background: rgba(0, 0, 0, 0.62); color: #fff;
    font: 11px/1.3 ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    pointer-events: none;
  }}
  @media (max-width: 720px) {{
    .product, .screen {{ grid-template-columns: 1fr; }}
    .views {{ position: static; }}
    .bank img {{ height: 16vh; min-height: 88px; }}
    .crew {{ grid-template-columns: 1fr; }}
  }}
</style>
<script>
  function revealFindings() {{
    const screen = document.querySelector(".screen");
    if (!screen || !screen.classList.contains("finding")) return;
    screen.classList.add("agents-in");
    setTimeout(() => screen.classList.remove("finding"), 800);
  }}
</script>
</head>
<body>
<div class="nav">DEMO ZONES — not official</div>
<div class="wrap">
{body}
</div>
</body>
</html>
"""


def _empty() -> str:
    return """
<p>No warning is waiting.</p>
<form method="post" action="/replay/route_block">
  <button class="approve" type="submit">Run the route check</button>
</form>
"""


def _decision(decision: Decision, previous: Decision | None, sent: list[dict]) -> str:
    english = next((message for message in decision.messages if message.lang == "en"), None)
    spanish = any(message.lang == "es" for message in decision.messages)
    incident, county, state = _INCIDENTS.get(decision.incident_id, (decision.incident_id, "", ""))
    place = _where(decision)
    when = _when(decision.cycle_ts)
    eta = _eta(decision)
    smoke = "confirmed for this check" if decision.fire.smoke_confirmed else "not confirmed"
    camera_alert = alert_from_views(ready_views())
    fire_detail = (
        f"{_speed(decision)} {eta} {camera_alert}"
        if camera_alert
        else f"{_speed(decision)} {eta} Smoke is {smoke}."
    )
    roads = "".join(_road_row(route, decision.plan.route) for route in decision.evac.routes)
    draft = _e(english.long_text) if english else ""
    spanish_note = "<p>A Spanish version of this message is included.</p>" if spanish else ""
    hits = ", ".join(decision.plan.rule_hits)
    region = ", ".join(part for part in (county, state) if part)
    views = f"{_gallery(decision, county)}{_reviewers(decision)}"
    playing = _cameras_play() and not hold_warning()
    if hold_warning():
        return f"""
<div class="screen">
  <div class="views">{views}</div>
  <aside class="buy">
    <p class="status waiting">Finishing the check</p>
    <h1>Smoke is marked. This warning stays off until the Graviton machine finishes the check.</h1>
    <p>{_e(incident)}{_e(_place_tail(place, county, state))}. The cameras started the check. The approval appears after the machine measures the speed and the three reviewers answer.</p>
  </aside>
</div>
"""
    tone = "waiting" if decision.status in {"PENDING_APPROVAL", "REJECTED"} else ""
    screen = "screen finding" if playing else "screen"
    checking = """
    <div class="while-checking">
      <p class="status waiting">Checking the cameras</p>
      <h1>The warning stays blank until this clip is checked and the three reviewers answer.</h1>
      <p>Place, the fire, the road, and who is told fill in after that.</p>
    </div>
"""
    ready = f"""
    <div class="when-ready">
      <p class="status {tone}">{_e(_STATUS.get(decision.status, decision.status))}</p>
      <h1>{_e(_lead(decision))}</h1>
      <p>{_e(incident)}{_e(_place_tail(place, county, state))}. Checked at {_e(when)}.</p>
      <table>
        <tr><td class="k">Place</td><td>{_e(place)}, {_e(region)}</td></tr>
        <tr><td class="k">Fire</td><td>{_e(fire_detail)}</td></tr>
        <tr><td class="k">NASA</td><td>{_e(_nasa(decision))}</td></tr>
        <tr><td class="k">Camera</td><td>{_e(_camera_line(decision))}</td></tr>
        <tr><td class="k">Way out</td><td>{_e(_road(decision.plan.route))}. {_e(_why(decision))}</td></tr>
        <tr><td class="k">Who is told</td><td>{_e(_who(decision))} Saved on this computer. It is not emailed.</td></tr>
      </table>
      {_buttons(decision)}
    </div>
"""
    return f"""
<div class="{screen}">
  <div class="views">{views}</div>
  <aside class="buy">
    {checking if playing else ""}
    {ready}
  </aside>
</div>
<div class="after-check">
<section class="panel">
  <h2>Roads</h2>
  <table>{roads}</table>
</section>
<section class="panel">
  <h2>Message they would get</h2>
  <pre>{draft}</pre>
  {spanish_note}
</section>
{_outbox(decision, sent)}
<p class="fine">Safety checks recorded: {_e(hits or "none")}.</p>
<form method="post" action="/replay/route_block">
  <button class="again" type="submit">Run this check again</button>
</form>
</div>
"""


def approval_view(decision: Decision, sent: list[dict]) -> dict:
    """Text the page swaps in after Approve, without replaying the cameras."""
    return {
        "status": decision.status,
        "label": _STATUS.get(decision.status, decision.status),
        "lead": _lead(decision),
        "saved": _outbox(decision, sent),
    }


def _lead(decision: Decision) -> str:
    road = _road(decision.plan.route)
    place = _where(decision)
    if decision.status == "APPROVED":
        return f"You approved the warning for {place}. The way out is {road}."
    if decision.status == "REJECTED":
        return f"You rejected the warning for {place}. Nothing was sent."
    diff = decision.diff_from_prev.get("route") or {}
    if diff.get("from") and diff.get("to") and diff.get("from") != diff.get("to"):
        return (
            f"{_road(diff.get('from'))} is blocked. "
            f"Send the {place} warning with {_road(diff.get('to'))} instead?"
        )
    return f"Send the {place} warning with {road}?"


def _where(decision: Decision) -> str:
    if decision.plan.zones_to_warn:
        return ", ".join(_zone(zone_id) for zone_id in decision.plan.zones_to_warn)
    return "the watched zone"


def _place_tail(place: str, county: str, state: str) -> str:
    tail = ", ".join(part for part in (county, state) if part)
    if place and tail:
        return f", {tail}"
    return tail


def _speed(decision: Decision) -> str:
    fire = decision.fire
    if fire.spread_kmh is None or fire.spread_bearing_deg is None:
        return "Speed was not measured."
    return f"Moving {compass(fire.spread_bearing_deg)} at {fire.spread_kmh} km/h."


def _nasa(decision: Decision) -> str:
    fire = decision.fire
    if fire.firms_detected is None:
        return "NASA FIRMS hotspot was not checked."
    if not fire.firms_detected:
        return "NASA FIRMS: no hotspot in the saved check."
    distance = ""
    if fire.firms_distance_km is not None:
        distance = f" About {_km(fire.firms_distance_km)} km from this place."
    satellite = f" Seen by {fire.firms_satellite}." if fire.firms_satellite else ""
    return f"NASA FIRMS: hotspot detected. Confidence {fire.firms_confidence}.{distance}{satellite}"


def _km(distance: float) -> str:
    rounded = round(distance, 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return str(rounded)


def _eta(decision: Decision) -> str:
    parts = []
    for zone_id in decision.plan.zones_to_warn:
        minutes = decision.fire.eta_min_by_zone.get(zone_id)
        if minutes is None:
            continue
        parts.append(f"About {minutes} minutes from {_zone(zone_id)}.")
    return " ".join(parts)


def _camera_line(decision: Decision) -> str:
    views = ready_views()
    if len(views) >= 2:
        return (
            f"{len(views)} cameras, different directions. "
            "A mark on any one of them raises the fire alert. "
            "The other views stay on screen so you can confirm."
        )
    watched = [route for route in decision.evac.routes if route.route_id != decision.plan.route]
    subject = watched[0] if watched else (decision.evac.routes[0] if decision.evac.routes else None)
    if subject is None:
        return "No camera frame is attached."
    return (
        f"Demo camera on {_road(subject.route_id)}, looking for stopped traffic. "
        f"This check: {_traffic(subject.status)}. "
        "The picture is a stand-in, not a live freeway camera."
    )


def _why(decision: Decision) -> str:
    suggested = decision.evac.recommended_route
    chosen = decision.plan.route
    if suggested and chosen and suggested != chosen:
        return (
            f"The first suggestion was {_road(suggested)}. "
            f"That road is {_traffic(_status_of(decision, suggested))}, so the warning uses {_road(chosen)}."
        )
    return f"The camera calls this road {_traffic(_status_of(decision, chosen))}."


def _who(decision: Decision) -> str:
    zones = [_zone(zone_id) for zone_id in decision.health.assisted_evac_zones]
    if zones:
        who = f"One resident who needs extra help in {', '.join(zones)}."
    else:
        who = "Residents in the warned zone."
    sites = []
    for site in decision.health.priority_sites:
        name = str(site.get("name") or site.get("id") or "a care site")
        zone_id = site.get("zone_id")
        sites.append(f"{name} in {_zone(zone_id)}" if zone_id else name)
    if sites:
        who += f" Care site on this draft: {', '.join(sites)}."
    return who


def _road_row(route, chosen: str | None) -> str:
    note = "This is the road named in the message." if route.route_id == chosen else ""
    return (
        "<tr>"
        f"<td class=\"k\">{_e(_road(route.route_id))}</td>"
        f"<td>{_e(_traffic(route.status))}. {_e(note)}</td>"
        "</tr>"
    )


def _reviewers(decision: Decision) -> str:
    """Three specialist cards under the cameras. Each line is that reviewer's own answer."""
    if hold_warning():
        waiting = "Still writing. The warning stays off until this answer is in."
        lines = (waiting, waiting, waiting)
    else:
        lines = (_fire_says(decision), _evac_says(decision), _health_says(decision))
    cards = [
        ("fire", "Fire department", "Smoke, speed, and the NASA hotspot", lines[0]),
        ("road", "Evacuation and traffic", "Which road is still open", lines[1]),
        ("care", "Public health", "People who need extra help", lines[2]),
    ]
    body = "\n".join(
        f"""
<article class="agent">
  {_portrait(kind)}
  <h3>{_e(title)}</h3>
  <p class="role">{_e(role)}</p>
  <p class="still">Still looking at the frames.</p>
  <p class="says">{_e(line)}</p>
</article>"""
        for kind, title, role, line in cards
    )
    return f'<section class="crew" aria-label="Three reviewers">{body}</section>'


def _fire_says(decision: Decision) -> str:
    smoke = "Smoke is marked." if decision.fire.smoke_confirmed else "Smoke is not confirmed on this check."
    return f"{smoke} {_speed(decision)} {_nasa(decision)}"


def _evac_says(decision: Decision) -> str:
    diff = decision.diff_from_prev.get("route") or {}
    previous = diff.get("from")
    chosen = diff.get("to") or decision.plan.route
    if previous and chosen and previous != chosen:
        return f"{_road(previous)} is blocked. This draft sends people on {_road(chosen)}."
    if chosen:
        return f"This draft sends people on {_road(chosen)}."
    return "No road is named on this draft."


def _health_says(decision: Decision) -> str:
    note = " ".join(decision.health.guidance).strip()
    zones = [_zone(zone_id) for zone_id in decision.health.assisted_evac_zones]
    if zones and note:
        return f"Extra help in {', '.join(zones)}. {note}"
    if zones:
        return f"Extra help in {', '.join(zones)}."
    return note or "No care note on this draft."


_ICON_STROKE = "#4a7eae"


def _portrait(kind: str) -> str:
    """A line icon for one reviewer. Same stroke, a different job on each."""
    marks = {
        "fire": f"""
    <path d="M36 4c4 6 1.2 9 1.2 13.2 0 4.6-3 7.4-6.6 7.4s-6.6-2.8-6.6-7.4c0-4.2 2.2-6 3.6-10.2 1.2 2.4 3.4 1.8 8.4-3z"/>
    <rect x="16" y="32" width="40" height="28" rx="9"/>
    <path d="M16 44H10M56 44h6"/>
    <circle cx="30" cy="44" r="1.7" fill="{_ICON_STROKE}" stroke="none"/>
    <circle cx="42" cy="44" r="1.7" fill="{_ICON_STROKE}" stroke="none"/>
    <path d="M28 53h16"/>""",
        "road": f"""
    <rect x="6" y="14" width="26" height="22" rx="7"/>
    <path d="M14 14l-2-6M24 14l2-6"/>
    <circle cx="12" cy="8" r="1.5" fill="{_ICON_STROKE}" stroke="none"/>
    <circle cx="26" cy="8" r="1.5" fill="{_ICON_STROKE}" stroke="none"/>
    <circle cx="15" cy="23" r="1.6" fill="{_ICON_STROKE}" stroke="none"/>
    <circle cx="24" cy="23" r="1.6" fill="{_ICON_STROKE}" stroke="none"/>
    <path d="M14 30h10"/>
    <path d="M12 48h12c8 0 10-10 18-10h12"/>
    <path d="M48 32l8 6-8 6"/>""",
        "care": f"""
    <circle cx="36" cy="16" r="9"/>
    <path d="M36 7V3"/>
    <circle cx="36" cy="3" r="1.5" fill="{_ICON_STROKE}" stroke="none"/>
    <circle cx="32" cy="15" r="1.5" fill="{_ICON_STROKE}" stroke="none"/>
    <circle cx="40" cy="15" r="1.5" fill="{_ICON_STROKE}" stroke="none"/>
    <path d="M33 20h6"/>
    <rect x="20" y="30" width="32" height="28" rx="8"/>
    <path d="M36 38v14M29 45h14"/>""",
    }[kind]
    return f"""<svg viewBox="0 0 72 72" aria-hidden="true">
  <g fill="none" stroke="{_ICON_STROKE}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    {marks}
  </g>
</svg>"""


def _cameras_play() -> bool:
    """True when the page will step through saved camera frames."""
    return len(ready_views()) >= 2 or len(ready_frames()) >= 2


def _gallery(decision: Decision, county: str) -> str:
    """Play the camera sequence when it has been built. A single still is the fallback."""
    views = ready_views()
    if len(views) >= 2:
        return _camera_bank(views)
    frames = ready_frames()
    if len(frames) >= 2:
        return _live_player(frames)
    if (_EVIDENCE / "ev-smoke.png").is_file():
        return _figure(
            "ev-smoke.png",
            "HPWREN camera, Red Mountain North, San Diego County. June 4, 2016. "
            "The box is on the smoke plume. Click the photo to open it.",
            camera="Red Mountain North",
        )
    for route in decision.evac.routes:
        frame = _image(route.route_id, route.evidence_id, county)
        if frame:
            return frame
    return "<p>No camera image is attached to this check.</p>"


def _buttons(decision: Decision) -> str:
    if decision.status != "PENDING_APPROVAL":
        return ""
    payload = json.dumps({"incident_id": decision.incident_id, "cycle_ts": decision.cycle_ts})
    return f"""
<div class="actions">
  <button class="approve" type="button" id="approve">Approve this warning</button>
  <button class="reject" type="button" id="reject">Do not send</button>
</div>
<script id="decision" type="application/json">{payload}</script>
<script>
  const decision = JSON.parse(document.getElementById("decision").textContent);
  async function act(action) {{
    const path = "/decisions/" + encodeURIComponent(decision.incident_id)
      + "/" + encodeURIComponent(decision.cycle_ts) + "/" + action;
    const response = await fetch(path, {{ method: "POST" }});
    const body = await response.json();
    const screen = document.querySelector(".screen");
    if (screen) screen.classList.remove("finding");
    const ready = document.querySelector(".when-ready");
    const status = ready.querySelector(".status");
    status.textContent = body.label;
    status.classList.toggle("waiting", body.status !== "APPROVED");
    ready.querySelector("h1").textContent = body.lead;
    const actions = document.querySelector(".actions");
    if (actions) actions.remove();
    const after = document.querySelector(".after-check");
    if (after && body.saved) after.insertAdjacentHTML("beforeend", body.saved);
  }}
  document.getElementById("approve").onclick = () => act("approve");
  document.getElementById("reject").onclick = () => act("reject");
</script>
"""


def _outbox(decision: Decision, sent: list[dict]) -> str:
    if decision.status != "APPROVED" or not sent:
        return ""
    lines = "".join(
        f"<li>Resident who needs extra help ({_e(row.get('resident_id'))}): {_e(row.get('body'))}</li>"
        for row in sent
        if row.get("channel") != "approval-event"
    )
    event = next((row for row in sent if row.get("channel") == "approval-event"), None)
    note = ""
    if event and event.get("event_id"):
        note = f"<p>Approval event sent. Id {_e(event.get('event_id'))}.</p>"
    return f'<section class="panel"><h2>Saved on this computer</h2><ul>{lines}</ul>{note}</section>'


def _image(route_id: str, evidence_id: str | None, county: str) -> str:
    if not evidence_id:
        return ""
    path = _EVIDENCE / f"{evidence_id}.png"
    if not path.is_file():
        return ""
    where = f", {county}" if county else ""
    caption = (
        f"Road diagram, {_road(route_id)}{where}. "
        "The white block is stopped traffic. This sketch is not a photograph."
    )
    return _figure(f"{evidence_id}.png", caption)


def _camera_note(views: list[dict]) -> str:
    """Credit line under the cameras. A mark on any one of them raises the alert."""
    word = {2: "Two", 3: "Three"}.get(len(views), str(len(views)))
    when = next((view.get("when") for view in views if view.get("when")), "")
    place = f", {when}" if when else ""
    return (
        f"{word} HPWREN cameras{place}. Same ignition, different directions. "
        "A mark on any one of them raises the fire alert. HPWREN (hpwren.ucsd.edu)."
    )


def _camera_bank(views: list[dict]) -> str:
    """Play every camera together, then hold the last frame of each."""
    payload = json.dumps(views)
    figures = []
    for view in views:
        first = view["frames"][0]
        figures.append(
            f"""
<figure class="cam">
  <a class="shot" href="/evidence/{_e(first["file"])}">
    <img class="live-frame" alt="{_e(view["name"])}" src="/evidence/{_e(first["file"])}">
    <span class="osd"><span>{_e(view["name"])}</span></span>
  </a>
  <figcaption class="live-status">Frame 1 of {len(view["frames"])}. {_e(first["label"])}</figcaption>
</figure>"""
        )
    body = "\n".join(figures)
    columns = min(len(views), 3)
    return f"""
<div class="bank" style="grid-template-columns: repeat({columns}, minmax(0, 1fr))">
{body}
</div>
<p class="fine">{_e(_camera_note(views))} <time class="live-clock">--</time></p>
<script id="live-views" type="application/json">{payload}</script>
<script>
  const views = JSON.parse(document.getElementById("live-views").textContent);
  const images = Array.from(document.querySelectorAll(".live-frame"));
  const captions = Array.from(document.querySelectorAll(".live-status"));
  const links = Array.from(document.querySelectorAll("a.shot"));
  const clocks = Array.from(document.querySelectorAll(".live-clock"));
  const fmt = new Intl.DateTimeFormat("en-US", {{
    timeZone: "America/Los_Angeles",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hourCycle: "h23"
  }});
  function tick() {{
    const parts = fmt.formatToParts(new Date());
    const get = (type) => parts.find((part) => part.type === type).value;
    const text = get("year") + "-" + get("month") + "-" + get("day")
      + " " + get("hour") + ":" + get("minute") + ":" + get("second") + " PT";
    clocks.forEach((clock) => {{ clock.textContent = text; }});
  }}
  tick();
  setInterval(tick, 1000);
  let index = 0;
  const count = views[0].frames.length;
  const timer = setInterval(() => {{
    index += 1;
    if (index >= count) {{
      clearInterval(timer);
      return;
    }}
    views.forEach((view, camera) => {{
      const frame = view.frames[index];
      images[camera].src = "/evidence/" + frame.file;
      links[camera].href = images[camera].src;
      captions[camera].textContent = "Frame " + (index + 1) + " of " + view.frames.length + ". " + frame.label;
    }});
    if (index === count - 1) {{
      clearInterval(timer);
      revealFindings();
    }}
  }}, 900);
</script>
"""


def _live_player(frames: list[dict]) -> str:
    """Step through the camera frames, then hold the last one."""
    payload = json.dumps(frames)
    first = frames[0]["file"]
    caption = (
        "HPWREN camera, Red Mountain North, San Diego County. June 4, 2016. "
        "The frames play in order. The box appears when the check marks the plume."
    )
    return f"""
<figure class="cam">
  <a class="shot" id="live-link" href="/evidence/{_e(first)}">
    <img id="live-frame" alt="{_e(caption)}" src="/evidence/{_e(first)}">
    <span class="osd"><span>Red Mountain North</span><time id="live-clock">--</time></span>
  </a>
  <figcaption id="live-status">Frame 1 of {len(frames)}. {_e(frames[0]["label"])}</figcaption>
</figure>
<script id="live-frames" type="application/json">{payload}</script>
<script>
  const frames = JSON.parse(document.getElementById("live-frames").textContent);
  const frame = document.getElementById("live-frame");
  const status = document.getElementById("live-status");
  const link = document.getElementById("live-link");
  const clock = document.getElementById("live-clock");
  const fmt = new Intl.DateTimeFormat("en-US", {{
    timeZone: "America/Los_Angeles",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hourCycle: "h23"
  }});
  function tick() {{
    const parts = fmt.formatToParts(new Date());
    const get = (type) => parts.find((part) => part.type === type).value;
    clock.textContent = get("year") + "-" + get("month") + "-" + get("day")
      + " " + get("hour") + ":" + get("minute") + ":" + get("second") + " PT";
  }}
  tick();
  setInterval(tick, 1000);
  let index = 0;
  const timer = setInterval(() => {{
    index += 1;
    if (index >= frames.length) {{
      clearInterval(timer);
      return;
    }}
    frame.src = "/evidence/" + frames[index].file;
    link.href = frame.src;
    status.textContent = "Frame " + (index + 1) + " of " + frames.length + ". " + frames[index].label;
    if (index === frames.length - 1) {{
      clearInterval(timer);
      revealFindings();
    }}
  }}, 900);
  status.textContent = "Frame 1 of " + frames.length + ". " + frames[0].label;
</script>
"""


def _figure(filename: str, caption: str, camera: str | None = None) -> str:
    src = f"/evidence/{filename}"
    overlay = ""
    script = ""
    if camera:
        overlay = f'<span class="osd"><span>{_e(camera)}</span><time id="live-clock">--</time></span>'
        script = """
<script>
  const clock = document.getElementById("live-clock");
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hourCycle: "h23"
  });
  function tick() {
    const parts = fmt.formatToParts(new Date());
    const get = (type) => parts.find((part) => part.type === type).value;
    clock.textContent = get("year") + "-" + get("month") + "-" + get("day")
      + " " + get("hour") + ":" + get("minute") + ":" + get("second") + " PT";
  }
  tick();
  setInterval(tick, 1000);
</script>
"""
    klass = "cam" if camera else ""
    link = "shot" if camera else ""
    return (
        f'<figure class="{klass}"><a class="{link}" href="{_e(src)}">'
        f'<img alt="{_e(caption)}" src="{_e(src)}">{overlay}</a>'
        f"<figcaption>{_e(caption)}</figcaption>{script}</figure>"
    )


def _road(route_id: str | None) -> str:
    if not route_id:
        return "no road chosen"
    name, code = _ROADS.get(route_id, (route_id, route_id))
    if name == code:
        return name
    return f"{name} ({code.replace('-', chr(0x2011))})"


def _zone(zone_id: str) -> str:
    if not zone_id:
        return ""
    return _ZONES.get(zone_id, zone_id.replace("_", " ").title())


def _traffic(status: str | None) -> str:
    return _TRAFFIC.get(status or "", status or "not known")


def _status_of(decision: Decision, route_id: str | None) -> str | None:
    for route in decision.evac.routes:
        if route.route_id == route_id:
            return route.status
    return None


def _when(cycle_ts: str) -> str:
    try:
        parsed = datetime.fromisoformat(cycle_ts)
    except ValueError:
        return cycle_ts
    local = parsed.astimezone(_PACIFIC)
    clock = local.strftime("%I:%M %p").lstrip("0")
    return f"{local.strftime('%B')} {local.day}, {local.year}, {clock} Pacific"


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value))
