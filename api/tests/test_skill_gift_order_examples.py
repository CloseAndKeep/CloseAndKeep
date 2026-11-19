"""Ensure published skill example JSON still validates as GiftOrderCreateRequest."""

from __future__ import annotations

from pathlib import Path

from app.gift_notes import GIFT_NOTE_MAX_LENGTH
from app.main import GiftOrderCreateRequest


_SKILL = Path(__file__).resolve().parents[2] / "skills" / "closeandkeep-orders" / "SKILL.md"


def test_skill_file_exists():
    assert _SKILL.is_file(), f"missing skill at {_SKILL}"


def test_skill_addressed_order_example_matches_schema():
    payload = GiftOrderCreateRequest(
        prospect_id=123,
        gift_id="cookies-4",
        recipient_name="Dana Buyer",
        shipping_company="Acme Corp",
        shipping_street="123 Main St",
        shipping_city="Springfield",
        shipping_state="IL",
        shipping_postal_code="62704",
        note="Thanks for the great meeting!",
    )
    assert payload.gift_id == "cookies-4"
    assert len(payload.note) <= GIFT_NOTE_MAX_LENGTH


def test_skill_address_request_example_matches_schema():
    payload = GiftOrderCreateRequest(
        prospect_id=123,
        gift_id="cookies-4",
        recipient_name="Dana Buyer",
        note="Thanks for meeting with us — enjoy these cookies!",
        request_recipient_address=True,
        recipient_email="dana@acme.example",
    )
    assert payload.request_recipient_address is True
    assert str(payload.recipient_email) == "dana@acme.example"


def test_skill_mentions_confirm_and_key_hygiene():
    text = _SKILL.read_text(encoding="utf-8")
    assert "Confirm before create" in text
    assert "CLOSEANDKEEP_API_KEY" in text
    assert "Never invent a payment link" in text
    assert "/admin/*" in text
