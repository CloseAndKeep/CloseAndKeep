"""Detect unusable CRM email / address so auto-order can hold or fall back."""

from __future__ import annotations

import re

from email_validator import EmailNotValidError, validate_email

from ..shipping_address import ShippingAddressParts, parts_from_cookie_fields

UNKNOWN_EMAIL_DOMAINS = frozenset({"unknown.salesforce", "unknown.hubspot"})

_NOREPLY_LOCAL = re.compile(
    r"^(no[-._]?reply|do[-._]?not[-._]?reply)",
    re.IGNORECASE,
)

_PLACEHOLDER = frozenset(
    {
        "n/a",
        "n.a",
        "n.a.",
        "na",
        "none",
        "null",
        "nil",
        "unknown",
        "unk",
        "tbd",
        "tba",
        "todo",
        "test",
        "testing",
        "tester",
        "asdf",
        "asdfg",
        "qwerty",
        "xxx",
        "xxxx",
        "xxxxx",
        "foo",
        "bar",
        "baz",
        "fake",
        "nowhere",
        "undefined",
        "dummy",
        "sample",
        "placeholder",
        "not applicable",
        "no address",
        "none given",
    }
)

_FAKE_STREET = re.compile(r"\bfake\b", re.IGNORECASE)
_HAS_DIGIT = re.compile(r"\d")
_HAS_LETTER = re.compile(r"[A-Za-z]")
_ZIP_IN_TEXT = re.compile(r"\b\d{5}(?:-\d{4})?\b")
_FAKE_STATES = frozenset({"xx", "zz"})

ADDRESS_BLANK = "blank"
ADDRESS_USABLE = "usable"
ADDRESS_JUNK = "junk"


def is_junk_crm_email(email: str | None) -> bool:
    """True when the CRM email cannot be used to reach the recipient."""
    raw = (email or "").strip().lower()
    if not raw:
        return True
    domain = raw.rsplit("@", 1)[-1] if "@" in raw else ""
    if domain in UNKNOWN_EMAIL_DOMAINS:
        return True
    try:
        normalized = validate_email(raw, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return True
    local = normalized.split("@", 1)[0]
    local_base = local.split("+", 1)[0]
    return bool(_NOREPLY_LOCAL.match(local_base))


def _normalized_token(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9./]+", " ", (value or "").strip().lower())
    return " ".join(cleaned.split())


def _is_placeholder(value: str | None) -> bool:
    token = _normalized_token(value or "")
    return bool(token) and token in _PLACEHOLDER


def _structured_is_fake(parts: ShippingAddressParts) -> bool:
    if (
        _is_placeholder(parts.street)
        or _is_placeholder(parts.city)
        or _is_placeholder(parts.state)
        or _is_placeholder(parts.postal_code)
    ):
        return True
    if _FAKE_STREET.search(parts.street or ""):
        return True
    if not _HAS_DIGIT.search(parts.postal_code or ""):
        return True
    if (parts.state or "").strip().lower() in _FAKE_STATES:
        return True
    return False


def _blob_is_usable(blob: str) -> bool:
    text = (blob or "").strip()
    if len(text) < 8:
        return False
    if _is_placeholder(text):
        return False
    if _FAKE_STREET.search(text):
        return False
    if not _HAS_DIGIT.search(text) or not _HAS_LETTER.search(text):
        return False
    if "\n" in text or "," in text or _ZIP_IN_TEXT.search(text):
        return True
    return False


def crm_address_quality(
    *,
    company: str | None = None,
    street: str | None = None,
    street2: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
    blob: str | None = None,
) -> str:
    """Classify CRM cookie address fields as blank, usable, or junk.

    Blank (no address parts) is the normal request-address path — not junk.
    Incomplete or clearly fake parts that the CRM *did* send are junk.
    """
    parts = parts_from_cookie_fields(
        company=company,
        street=street,
        street2=street2,
        city=city,
        state=state,
        postal_code=postal_code,
        country=country,
    )
    cleaned_blob = (blob or "").strip()

    if parts and parts.has_location_fields():
        if parts.is_complete():
            return ADDRESS_JUNK if _structured_is_fake(parts) else ADDRESS_USABLE
        if cleaned_blob and _blob_is_usable(cleaned_blob):
            return ADDRESS_USABLE
        return ADDRESS_JUNK

    if cleaned_blob:
        return ADDRESS_USABLE if _blob_is_usable(cleaned_blob) else ADDRESS_JUNK

    return ADDRESS_BLANK
