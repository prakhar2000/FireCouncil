"""Decide whether a vulnerable resident's caregiver should be contacted."""


def escalate(resident: dict, ack: dict | None, elapsed_s: int, window_s: int) -> str | None:
    """Return the caregiver email when the ack window has passed.

    Residents who are not vulnerable, and anyone who already acknowledged,
    do not escalate.
    """
    if not resident.get("vulnerable"):
        return None
    if ack and ack.get("ack_at"):
        return None
    if elapsed_s >= window_s:
        return resident.get("caregiver_email") or None
    return None
