"""Gift note constraints shared by CSV import, API validation, and CRM auto-order.

Crumbl's delivery checkout caps the printed gift note at 150 characters (sticker /
enclosure). CloseAndKeep keeps the same budget so notes fit bakery fulfillment,
including Levain fallback when an address is out of Crumbl delivery.
"""

GIFT_NOTE_MAX_LENGTH = 150

_FROM_PREFIX = "From "


def _one_line(value: str | None) -> str:
    return " ".join((value or "").split())


def sender_label(*, company: str | None, name: str | None) -> str | None:
    """Company on the account, or the person's name when company is blank."""
    company_text = _one_line(company)
    if company_text:
        return company_text
    name_text = _one_line(name)
    return name_text or None


def from_line_for_sender(*, company: str | None, name: str | None) -> str | None:
    """``From Acme Corp`` sized so the line itself fits the bakery sticker."""
    label = sender_label(company=company, name=name)
    if not label:
        return None
    room = GIFT_NOTE_MAX_LENGTH - len(_FROM_PREFIX)
    if room <= 0:
        return None
    if len(label) > room:
        label = label[:room].rstrip()
    if not label:
        return None
    return f"{_FROM_PREFIX}{label}"


def note_with_from_line(note: str, *, company: str | None, name: str | None) -> str:
    """Append ``From {company or name}`` and keep the sticker within 150 characters.

    The personal message is shortened when it would push the from line past the
    Crumbl limit. A note that already ends with that line is left as-is.
    """
    body = (note or "").strip()
    line = from_line_for_sender(company=company, name=name)
    if not line:
        return body[:GIFT_NOTE_MAX_LENGTH]
    if body.casefold().endswith(line.casefold()):
        return body[:GIFT_NOTE_MAX_LENGTH]
    if not body:
        return line
    suffix = f"\n{line}"
    if len(body) + len(suffix) <= GIFT_NOTE_MAX_LENGTH:
        return f"{body}{suffix}"
    room = GIFT_NOTE_MAX_LENGTH - len(suffix)
    if room <= 0:
        return line
    trimmed = body[:room].rstrip()
    if not trimmed:
        return line
    return f"{trimmed}{suffix}"
