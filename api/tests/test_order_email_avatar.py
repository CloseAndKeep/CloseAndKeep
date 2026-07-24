"""Buyer avatar is embedded as a CID attachment in address-request emails."""

from __future__ import annotations

import base64

_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_address_request_embeds_sender_avatar(monkeypatch):
    import app.order_email as oe

    captured: dict = {}

    def fake_send(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(oe, "_send", fake_send)
    monkeypatch.setattr(oe, "_resend_ready", lambda: ("re_test", "from@example.com"))

    oe.send_recipient_address_request(
        recipient_name="Dana Buyer",
        recipient_email="dana@example.com",
        address_form_url="https://example.com/ship/tok",
        redeem_url="https://example.com/redeem",
        redeem_code="CK-12345",
        gift_label="4 cookies",
        note="Thanks!",
        sender_name="Test Seller",
        sender_company="CloseAndKeep Test",
        sender_avatar_data=_TINY_PNG,
        sender_avatar_content_type="image/png",
    )

    assert "cid:sender-photo" in captured["html_body"]
    assert captured["attachments"]
    attachment = captured["attachments"][0]
    assert attachment["content_id"] == "sender-photo"
    assert attachment["content_type"] == "image/png"
    assert base64.b64decode(attachment["content"]) == _TINY_PNG


def test_address_request_omits_avatar_when_missing(monkeypatch):
    import app.order_email as oe

    captured: dict = {}
    monkeypatch.setattr(oe, "_send", lambda **kwargs: captured.update(kwargs))

    oe.send_recipient_address_request(
        recipient_name="Dana Buyer",
        recipient_email="dana@example.com",
        address_form_url="https://example.com/ship/tok",
        redeem_url="https://example.com/redeem",
        redeem_code="CK-12345",
        gift_label="4 cookies",
        note="Thanks!",
        sender_name="Test Seller",
        sender_company="CloseAndKeep Test",
    )

    assert "cid:sender-photo" not in captured["html_body"]
    assert captured.get("attachments") in (None, [])
