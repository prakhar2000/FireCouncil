"""Send a decision to residents in warned zones, or stop when the switch is on."""

import os
from pathlib import Path

from services.agents.schemas import Decision
from services.notify.approval_event import publish_approval
from services.notify.channels.email_outbox import EmailChannel


def kill_switch_on() -> bool:
    """True when KILL_SWITCH=true in the environment."""
    return os.environ.get("KILL_SWITCH", "false").strip().lower() == "true"


def dispatch(
    decision: Decision,
    residents: list[dict],
    kill_switch: bool,
    outbox_path: Path | None = None,
) -> list[dict]:
    """Record one outbox row per resident in a warned zone.

    A true kill switch returns before any write.
    """
    if kill_switch:
        return []
    channel = EmailChannel(outbox_path or Path("data/local/outbox.jsonl"))
    warned = set(decision.plan.zones_to_warn)
    rows = []
    for resident in residents:
        if resident.get("zone_id") not in warned:
            continue
        lang = resident.get("language", "en")
        message = next(
            item
            for item in decision.messages
            if item.zone_id == resident["zone_id"] and item.lang == lang
        )
        rows.append(channel.send(resident["resident_id"], message.long_text))
    publish_approval(decision, len(rows), outbox_path)
    return rows
