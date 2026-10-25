"""Publish one event when a person approves. Off unless APPROVAL_EVENTS=1."""

import json
import os
from pathlib import Path

from services.agents.schemas import Decision


def publish_approval(decision: Decision, sent: int, path: Path | None = None) -> dict:
    """Record the approval. Send it to EventBridge only when the switch is on."""
    detail = {
        "incident_id": decision.incident_id,
        "cycle_ts": decision.cycle_ts,
        "route": decision.plan.route,
        "zones": list(decision.plan.zones_to_warn),
        "sent": sent,
    }
    record = {
        "channel": "approval-event",
        "source": "firecouncil.approval",
        "detail_type": "WarningApproved",
        "detail": detail,
        "event_id": None,
    }
    if os.environ.get("APPROVAL_EVENTS") != "1":
        return record
    try:
        import boto3

        client = boto3.client("events", region_name=os.environ.get("AWS_REGION", "us-east-2"))
        result = client.put_events(
            Entries=[
                {
                    "Source": record["source"],
                    "DetailType": record["detail_type"],
                    "Detail": json.dumps(detail),
                    "EventBusName": "default",
                }
            ]
        )
        entry = result["Entries"][0]
        record["event_id"] = entry.get("EventId")
        record["error"] = entry.get("ErrorCode")
    except Exception:  # noqa: BLE001  approve must still succeed if EventBridge is down
        record["error"] = "unavailable"
    if path is not None and (record.get("event_id") or record.get("error")):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as handle:
            handle.write(json.dumps(record) + "\n")
    return record
