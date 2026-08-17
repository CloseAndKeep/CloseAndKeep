"""Seller (AE) status emails: shipped, delivered, and address-hold expired."""

from __future__ import annotations

import pytest

_SELLER = "AE@Example.COM"
_SELLER_LOWER = "ae@example.com"
_PROSPECT = "prospect@buyer.example"
_ORDER_URL = "https://example.com/orders/42"


def _capture_send(monkeypatch, module):
    captured: dict = {}
    calls: list[dict] = []

    def fake_send(**kwargs):
        captured.clear()
        captured.update(kwargs)
        calls.append(kwargs)

    monkeypatch.setattr(module, "_send", fake_send)
    return captured, calls


@pytest.fixture
def oe(monkeypatch):
    import app.order_email as module

    captured, calls = _capture_send(monkeypatch, module)
    module._captured = captured
    module._calls = calls
    return module


def _shipped_kwargs(**overrides):
    base = dict(
        order_id=42,
        seller_email=_SELLER,
        recipient_name="Dana Buyer",
        gift_label="4 cookies",
        tracking_number="1Z999",
        order_url=_ORDER_URL,
    )
    base.update(overrides)
    return base


def _delivered_kwargs(**overrides):
    return _shipped_kwargs(**overrides)


def _expired_kwargs(**overrides):
    base = dict(
        order_id=42,
        seller_email=_SELLER,
        recipient_name="Dana Buyer",
        gift_label="4 cookies",
        order_url=_ORDER_URL,
    )
    base.update(overrides)
    return base


def test_shipped_sends_to_seller_not_prospect(oe):
    oe.send_seller_order_shipped(**_shipped_kwargs())

    assert oe._calls
    assert oe._captured["to"] == _SELLER_LOWER
    assert _PROSPECT not in oe._captured["to"]
    assert _PROSPECT not in oe._captured["text_body"]
    assert oe._captured["subject"] == "Cookies shipped — order #42"
    assert oe._captured["context"] == "seller-order-shipped order_id=42"
    assert "Dana Buyer" in oe._captured["text_body"]
    assert "4 cookies" in oe._captured["text_body"]
    assert "View order" in oe._captured["html_body"]
    assert _ORDER_URL in oe._captured["html_body"]
    assert "#8B5E3C" in oe._captured["html_body"]


def test_delivered_sends_to_seller_not_prospect(oe):
    oe.send_seller_order_delivered(**_delivered_kwargs())

    assert oe._calls
    assert oe._captured["to"] == _SELLER_LOWER
    assert _PROSPECT not in oe._captured["to"]
    assert _PROSPECT not in oe._captured["text_body"]
    assert oe._captured["subject"] == "Cookies delivered — order #42"
    assert oe._captured["context"] == "seller-order-delivered order_id=42"
    assert "Dana Buyer" in oe._captured["text_body"]
    assert "4 cookies" in oe._captured["text_body"]
    assert "View order" in oe._captured["html_body"]
    assert "#8B5E3C" in oe._captured["html_body"]


def test_hold_expired_sends_to_seller_not_prospect(oe):
    oe.send_seller_address_hold_expired(**_expired_kwargs())

    assert oe._calls
    assert oe._captured["to"] == _SELLER_LOWER
    assert _PROSPECT not in oe._captured["to"]
    assert _PROSPECT not in oe._captured["text_body"]
    assert oe._captured["subject"] == "Address link expired — order #42"
    assert oe._captured["context"] == "seller-address-hold-expired order_id=42"
    assert "Dana Buyer" in oe._captured["text_body"]
    assert "4 cookies" in oe._captured["text_body"]
    assert "View order" in oe._captured["html_body"]
    assert "#8B5E3C" in oe._captured["html_body"]


@pytest.mark.parametrize(
    "fn_name,kwargs",
    [
        ("send_seller_order_shipped", _shipped_kwargs(seller_email="")),
        ("send_seller_order_shipped", _shipped_kwargs(seller_email="   ")),
        ("send_seller_order_delivered", _delivered_kwargs(seller_email="")),
        ("send_seller_address_hold_expired", _expired_kwargs(seller_email="")),
    ],
)
def test_empty_seller_email_skips_send(oe, fn_name, kwargs):
    getattr(oe, fn_name)(**kwargs)
    assert oe._calls == []


def test_shipped_includes_tracking_when_set(oe):
    oe.send_seller_order_shipped(**_shipped_kwargs(tracking_number="1Z999AA"))

    assert "1Z999AA" in oe._captured["text_body"]
    assert "Tracking number" in oe._captured["text_body"]
    assert "1Z999AA" in oe._captured["html_body"]


def test_shipped_omits_tracking_when_none(oe):
    oe.send_seller_order_shipped(**_shipped_kwargs(tracking_number=None))

    assert "Tracking number" not in oe._captured["text_body"]
    assert "Tracking number" not in oe._captured["html_body"]


def test_delivered_includes_tracking_when_set(oe):
    oe.send_seller_order_delivered(**_delivered_kwargs(tracking_number="9400-1111"))

    assert "9400-1111" in oe._captured["text_body"]
    assert "Tracking number" in oe._captured["html_body"]


def test_delivered_omits_tracking_when_none(oe):
    oe.send_seller_order_delivered(**_delivered_kwargs(tracking_number=None))

    assert "Tracking number" not in oe._captured["text_body"]
    assert "Tracking number" not in oe._captured["html_body"]


def test_hold_expired_mentions_expired_and_canceled(oe):
    oe.send_seller_address_hold_expired(**_expired_kwargs())

    subject = oe._captured["subject"].lower()
    text = oe._captured["text_body"].lower()
    html_body = oe._captured["html_body"].lower()
    assert "expired" in subject
    assert "expired" in text
    assert "canceled" in text
    assert "expired" in html_body
    assert "canceled" in html_body
    assert "new order" in text


def test_html_escapes_recipient_and_gift(oe):
    oe.send_seller_order_shipped(
        **_shipped_kwargs(
            recipient_name='<script>alert(1)</script>',
            gift_label='4 cookies & "milk"',
            tracking_number="1Z<>",
        )
    )

    html_body = oe._captured["html_body"]
    assert "<script>" not in html_body
    assert "&amp;" in html_body
    assert "&lt;script&gt;" in html_body
    assert "1Z&lt;&gt;" in html_body
