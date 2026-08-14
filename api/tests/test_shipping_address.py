"""Unit tests for structured shipping address formatting."""

from __future__ import annotations

from app.shipping_address import (
    format_shipping_address,
    parts_from_optional,
    shipping_address_values,
)


def test_format_includes_street2_and_omits_us_country():
    parts = parts_from_optional(
        street="123 Main St",
        street2="Apt 2",
        city="Springfield",
        state="IL",
        postal_code="62704",
        country="US",
    )
    assert parts is not None
    assert format_shipping_address(parts) == "123 Main St\nApt 2\nSpringfield, IL 62704"


def test_format_includes_optional_company_first():
    parts = parts_from_optional(
        company="Acme Corp",
        street="123 Main St",
        street2="Floor 42",
        city="Chicago",
        state="IL",
        postal_code="60601",
    )
    assert parts is not None
    assert format_shipping_address(parts) == "Acme Corp\n123 Main St\nFloor 42\nChicago, IL 60601"


def test_structured_values_win_over_blob():
    parts = parts_from_optional(
        street="123 Main St",
        city="Springfield",
        state="IL",
        postal_code="62704",
    )
    values = shipping_address_values(parts=parts, blob="ignore me")
    assert values["shipping_street"] == "123 Main St"
    assert values["shipping_city"] == "Springfield"
    assert values["shipping_state"] == "IL"
    assert values["shipping_postal_code"] == "62704"
    assert values["shipping_country"] == "US"
    assert values["shipping_address"] == "123 Main St\nSpringfield, IL 62704"
    assert values["shipping_company"] is None


def test_structured_values_include_company():
    parts = parts_from_optional(
        company="Acme Corp",
        street="123 Main St",
        city="Springfield",
        state="IL",
        postal_code="62704",
    )
    values = shipping_address_values(parts=parts)
    assert values["shipping_company"] == "Acme Corp"
    assert values["shipping_address"] == "Acme Corp\n123 Main St\nSpringfield, IL 62704"


def test_blob_used_when_structured_missing():
    values = shipping_address_values(parts=None, blob="  99 Redeem Lane  ")
    assert values["shipping_address"] == "99 Redeem Lane"
    assert values["shipping_street"] is None


def test_incomplete_structured_falls_back_to_blob():
    parts = parts_from_optional(street="123 Main St", city="Springfield")
    values = shipping_address_values(parts=parts, blob="legacy blob")
    assert values["shipping_address"] == "legacy blob"
    assert values["shipping_street"] is None
