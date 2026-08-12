"""Structured shipping address helpers (street / city / state / postal).

Orders still store a formatted ``shipping_address`` string for email, admin
display, and older API clients. Structured columns are the source of truth
when the caller sends traditional address pieces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_COUNTRY = "US"
_US_COUNTRY_ALIASES = {"US", "USA", "UNITED STATES", "UNITED STATES OF AMERICA"}

ADDRESS_COLUMN_NAMES = (
    "shipping_street",
    "shipping_street2",
    "shipping_city",
    "shipping_state",
    "shipping_postal_code",
    "shipping_country",
    "shipping_address",
)

INCOMPLETE_STRUCTURED_ADDRESS_MESSAGE = (
    "shipping_street, shipping_city, shipping_state, and shipping_postal_code "
    "are required together"
)
MISSING_ADDRESS_MESSAGE = (
    "shipping street, city, state, and postal code are required unless "
    "requesting an address from the recipient"
)


@dataclass(frozen=True)
class ShippingAddressParts:
    street: str
    city: str
    state: str
    postal_code: str
    street2: str | None = None
    country: str | None = None

    def any_set(self) -> bool:
        return bool(
            self.street
            or self.street2
            or self.city
            or self.state
            or self.postal_code
            or self.country
        )

    def is_complete(self) -> bool:
        return bool(self.street and self.city and self.state and self.postal_code)


def _clean(value: str | None) -> str:
    return (value or "").strip()


def parts_from_optional(
    *,
    street: str | None = None,
    street2: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
) -> ShippingAddressParts | None:
    parts = ShippingAddressParts(
        street=_clean(street),
        street2=_clean(street2) or None,
        city=_clean(city),
        state=_clean(state),
        postal_code=_clean(postal_code),
        country=_clean(country) or None,
    )
    if not parts.any_set():
        return None
    return parts


def format_shipping_address(parts: ShippingAddressParts) -> str:
    """US-style multiline address for display, email, and legacy clients."""
    lines = [parts.street.strip()]
    if (parts.street2 or "").strip():
        lines.append(parts.street2.strip())
    city = parts.city.strip()
    state = parts.state.strip()
    postal = parts.postal_code.strip()
    city_state = ", ".join(piece for piece in (city, state) if piece)
    locality = " ".join(piece for piece in (city_state, postal) if piece)
    if locality:
        lines.append(locality)
    country = (parts.country or "").strip()
    if country and country.upper() not in _US_COUNTRY_ALIASES:
        lines.append(country)
    return "\n".join(line for line in lines if line)


def empty_shipping_address_values() -> dict[str, str | None]:
    return {name: None for name in ADDRESS_COLUMN_NAMES}


def shipping_address_values(
    *,
    parts: ShippingAddressParts | None = None,
    blob: str | None = None,
) -> dict[str, str | None]:
    """Column values for a gift order.

    Complete structured parts win. Otherwise the legacy ``shipping_address``
    blob is stored and structured columns stay empty.
    """
    if parts and parts.is_complete():
        country = (parts.country or "").strip() or DEFAULT_COUNTRY
        complete = ShippingAddressParts(
            street=parts.street.strip(),
            street2=(parts.street2 or "").strip() or None,
            city=parts.city.strip(),
            state=parts.state.strip(),
            postal_code=parts.postal_code.strip(),
            country=country,
        )
        formatted = format_shipping_address(complete)[:1000]
        return {
            "shipping_street": complete.street[:255],
            "shipping_street2": (complete.street2[:255] if complete.street2 else None),
            "shipping_city": complete.city[:100],
            "shipping_state": complete.state[:64],
            "shipping_postal_code": complete.postal_code[:20],
            "shipping_country": country[:64],
            "shipping_address": formatted,
        }

    cleaned = _clean(blob)
    if cleaned:
        values = empty_shipping_address_values()
        values["shipping_address"] = cleaned[:1000]
        return values

    return empty_shipping_address_values()


def apply_shipping_address(target: Any, values: dict[str, str | None]) -> None:
    for name, value in values.items():
        setattr(target, name, value)


def parts_from_shipping_payload(payload: Any) -> ShippingAddressParts | None:
    return parts_from_optional(
        street=getattr(payload, "shipping_street", None),
        street2=getattr(payload, "shipping_street2", None),
        city=getattr(payload, "shipping_city", None),
        state=getattr(payload, "shipping_state", None),
        postal_code=getattr(payload, "shipping_postal_code", None),
        country=getattr(payload, "shipping_country", None),
    )


def parts_from_cookie_fields(
    *,
    street: str | None = None,
    street2: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
) -> ShippingAddressParts | None:
    return parts_from_optional(
        street=street,
        street2=street2,
        city=city,
        state=state,
        postal_code=postal_code,
        country=country,
    )
