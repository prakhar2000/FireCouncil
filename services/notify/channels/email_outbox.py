"""Local stand-in for email. Appends one JSON line per send."""

import json
from pathlib import Path


class EmailChannel:
    """Write the message body to an outbox file instead of calling SES."""

    def __init__(self, outbox_path: Path) -> None:
        self.outbox_path = Path(outbox_path)

    def send(self, resident_id: str, body: str) -> dict:
        row = {
            "channel": "email",
            "resident_id": resident_id,
            "body": body,
            "simulated": True,
        }
        self.outbox_path.parent.mkdir(parents=True, exist_ok=True)
        with self.outbox_path.open("a") as handle:
            handle.write(json.dumps(row) + "\n")
        return row
