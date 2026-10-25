"""Mark a resident as having confirmed a decision."""

from datetime import UTC, datetime

from services.agents.store import JsonStore


def check_acks(store: JsonStore, decision_id: str, resident_id: str, channel: str = "web") -> dict:
    """Store an acknowledgement timestamp for one resident."""
    ack = {
        "decision_id": decision_id,
        "resident_id": resident_id,
        "ack_at": datetime.now(UTC).isoformat(),
        "channel": channel,
        "escalation_state": "acked",
    }
    store.save_ack(decision_id, resident_id, ack)
    return ack
