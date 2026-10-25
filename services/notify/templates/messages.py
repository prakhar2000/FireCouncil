"""English and Spanish warning drafts. Nothing here sends a message."""

from services.agents.schemas import ActionPlan, DraftMessage

_COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
_ORDER_EN = "Evacuation ORDER in effect (official) — leave now"


def compass(bearing_deg: float | None) -> str:
    """Map a bearing in degrees to an 8-point compass label."""
    if bearing_deg is None:
        return "unknown"
    index = int((bearing_deg % 360) / 45 + 0.5) % 8
    return _COMPASS[index]


def render(
    plan: ActionPlan,
    zone_id: str,
    zone_name: str,
    lang: str,
    when: str,
    evidence_url: str | None,
    ack_link: str,
    official_link: str,
    *,
    eta_min: int | None,
    direction: str,
    route_status: str,
    official_status: str = "none",
) -> DraftMessage:
    """Fill one draft. SMS is the same facts trimmed to 300 characters."""
    prefix = "URGENT" if plan.urgency == "urgent" else "ADVISORY"
    route = plan.route or "route unknown — follow officials"
    eta = "unknown" if eta_min is None else str(eta_min)
    if official_status == "order":
        long_text = _order_text(lang, official_link, ack_link)
        voice = f"<speak>{_ORDER_EN}. Call 911.</speak>"
    elif lang == "es":
        long_text = (
            f"[{'URGENTE' if prefix == 'URGENT' else 'AVISO'}] {zone_name}: incendio acercándose "
            f"desde el {direction}, a unos {eta} min (a las {when}). "
            f"Salga ahora por {route} ({route_status} en la cámara a las {when}). "
            f"Lleve medicinas, identificación y mascotas. Órdenes oficiales: {official_link}. "
            f"¿En peligro ahora? Llame al 911. Confirme que recibió esto: {ack_link}"
        )
        voice = (
            f"<speak>{zone_name}. Incendio desde el {direction}, a unos {eta} minutos. "
            f"Salga por {route}. Llame al 911.</speak>"
        )
    else:
        long_text = (
            f"[{prefix}] {zone_name}: fire approaching from the {direction}, "
            f"about {eta} min away (as of {when}). "
            f"Leave now via {route} ({route_status} on camera at {when}). "
            f"Bring meds, ID, pets. Official orders: {official_link}. "
            f"In danger now? Call 911. Confirm you got this: {ack_link}"
        )
        voice = (
            f"<speak>{zone_name}. Fire approaching from the {direction}, about {eta} minutes away. "
            f"Leave now via {route}. Call 911.</speak>"
        )
    sms = long_text if len(long_text) <= 300 else long_text[:297] + "..."
    return DraftMessage(
        zone_id=zone_id,
        lang=lang,  # type: ignore[arg-type]
        voice_ssml=voice,
        sms=sms,
        long_text=long_text,
        evidence_url=evidence_url,
    )


def _order_text(lang: str, official_link: str, ack_link: str) -> str:
    if lang == "es":
        return (
            "ORDEN de evacuación vigente (oficial) — salga ahora. "
            f"Órdenes oficiales: {official_link}. ¿En peligro ahora? Llame al 911. "
            f"Confirme que recibió esto: {ack_link}"
        )
    return (
        f"{_ORDER_EN}. Official orders: {official_link}. "
        f"In danger now? Call 911. Confirm you got this: {ack_link}"
    )
