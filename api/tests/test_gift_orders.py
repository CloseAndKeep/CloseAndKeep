"""Gift-order tests — Test.MD §7 (validation, storage, lifecycle) and §8.2.

Stripe is stubbed via ``stripe_stub``; email via monkeypatch where asserted.
"""

from __future__ import annotations

from conftest import create_prospect, make_order_payload


# --- §7.1 Validation ---------------------------------------------------------


def test_rejects_unknown_gift(auth_client, prospect_id, stripe_stub):
    resp = auth_client.post(
        "/gift-orders", json=make_order_payload(prospect_id, "not-a-real-gift")
    )
    assert resp.status_code == 400
    assert "unknown gift" in resp.json()["detail"].lower()


def test_rejects_blank_recipient_name(auth_client, prospect_id, stripe_stub):
    payload = make_order_payload(prospect_id)
    payload["recipient_name"] = ""
    assert auth_client.post("/gift-orders", json=payload).status_code == 422


def test_rejects_whitespace_only_recipient_name(auth_client, prospect_id, stripe_stub):
    payload = make_order_payload(prospect_id)
    payload["recipient_name"] = "   "
    assert auth_client.post("/gift-orders", json=payload).status_code == 422


def test_rejects_whitespace_only_address(auth_client, prospect_id, stripe_stub):
    payload = make_order_payload(prospect_id)
    payload["shipping_address"] = "   \n  "
    assert auth_client.post("/gift-orders", json=payload).status_code == 422


def test_rejects_whitespace_only_note(auth_client, prospect_id, stripe_stub):
    payload = make_order_payload(prospect_id)
    payload["note"] = "   "
    assert auth_client.post("/gift-orders", json=payload).status_code == 422


def test_order_for_foreign_prospect_returns_404(make_client, stripe_stub):
    from conftest import signup

    owner = signup(make_client(), "owner@example.com")
    intruder = signup(make_client(), "intruder@example.com")
    prospect = create_prospect(owner, email="p@example.com")

    resp = intruder.post("/gift-orders", json=make_order_payload(prospect["id"]))
    assert resp.status_code == 404


# --- §7.1 Storage ------------------------------------------------------------


def test_order_persists_all_fields_and_prospect_fk(auth_client, prospect_id, stripe_stub):
    payload = make_order_payload(prospect_id, "cookies-4")
    resp = auth_client.post("/gift-orders", json=payload)
    assert resp.status_code == 201, resp.text
    order = resp.json()

    assert order["prospect_id"] == prospect_id
    assert order["gift_id"] == "cookies-4"
    assert order["recipient_name"] == payload["recipient_name"]
    assert order["shipping_address"] == payload["shipping_address"]
    assert order["note"] == payload["note"]
    assert order["status"] == "pending_payment"
    assert order["payment_status"] == "pending"


def test_order_trims_whitespace_on_store(auth_client, prospect_id, stripe_stub):
    payload = make_order_payload(prospect_id)
    payload["recipient_name"] = "  Dana Buyer  "
    resp = auth_client.post("/gift-orders", json=payload)
    assert resp.status_code == 201, resp.text
    assert resp.json()["recipient_name"] == "Dana Buyer"


def test_duplicate_submit_creates_distinct_orders(auth_client, prospect_id, stripe_stub):
    """Ordering is intentionally not idempotent — each submit is a new order."""
    first = auth_client.post("/gift-orders", json=make_order_payload(prospect_id))
    second = auth_client.post("/gift-orders", json=make_order_payload(prospect_id))
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert len(auth_client.get("/gift-orders").json()) == 2


# --- §8.2 Notification on fulfillment ----------------------------------------


def test_payment_triggers_notification_with_order_details(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    payload = make_order_payload(prospect_id)
    order = auth_client.post("/gift-orders", json=payload).json()

    captured: dict = {}
    import app.fulfillment as fulfillment

    monkeypatch.setattr(
        fulfillment, "send_new_order_notification", lambda **kw: captured.update(kw)
    )

    # Reading the order reconciles it to paid from Stripe, firing the email job.
    stripe_stub.retrieved_session = {
        "id": "cs_test_created",
        "status": "complete",
        "payment_status": "paid",
        "amount_total": 100,
        "currency": "usd",
    }
    auth_client.get(f"/gift-orders/{order['id']}")

    assert captured["order_id"] == order["id"]
    assert captured["recipient_name"] == payload["recipient_name"]
    assert captured["shipping_address"] == payload["shipping_address"]
    assert captured["note"] == payload["note"]


def test_create_requires_authentication(client, stripe_stub):
    resp = client.post("/gift-orders", json=make_order_payload(1))
    assert resp.status_code == 401


def test_get_missing_order_returns_404(auth_client):
    assert auth_client.get("/gift-orders/999999").status_code == 404


def test_fulfillment_skips_notify_without_shipping_address(monkeypatch):
    """Address-request orders must not email ops until an address exists."""
    from app.fulfillment import ManualEmailFulfillment
    from types import SimpleNamespace

    sent: list = []
    monkeypatch.setattr(
        "app.fulfillment.send_new_order_notification",
        lambda **kw: sent.append(kw),
    )
    provider = ManualEmailFulfillment()
    order = SimpleNamespace(
        id=1,
        shipping_address=None,
        requested_at=None,
        gift_id="cookies-4",
        recipient_name="X",
        note="n",
        status="no_address",
    )
    provider.submit_queued_order(
        order,
        prospect=SimpleNamespace(
            name="P", email="e@x.com", deal_status="open"
        ),
        owner=SimpleNamespace(email="o@x.com"),
        db=None,
    )
    assert sent == []
