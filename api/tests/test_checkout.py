"""Integration tests for the Stripe checkout flow.

Covers Test.MD §3.1 (Checkout), §3.2 (Webhooks), and the gift-order payment
paths in §7, plus the TEST-RISK replay/idempotency guarantee. Stripe itself is
stubbed via the ``stripe_stub`` fixture (see conftest).
"""

from __future__ import annotations

import stripe

from conftest import make_order_payload


def _create_order(auth_client, prospect_id, gift_id="cookies-4"):
    resp = auth_client.post("/gift-orders", json=make_order_payload(prospect_id, gift_id))
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- §3.1 Checkout: session creation -----------------------------------------


def test_order_create_starts_checkout_with_correct_price(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    monkeypatch.setenv("STRIPE_PRICE_COOKIES_4", "price_cookies_4")

    body = _create_order(auth_client, prospect_id, gift_id="cookies-4")

    # The order is created but not yet paid or queued.
    assert body["payment_status"] == "pending"
    assert body["status"] == "pending_payment"
    assert body["checkout_url"] == stripe_stub.created_session["url"]

    # Exactly one checkout session was created with the gift's price id.
    assert len(stripe_stub.session_create_calls) == 1
    params = stripe_stub.session_create_calls[0]
    assert params["mode"] == "payment"
    assert params["line_items"] == [{"price": "price_cookies_4", "quantity": 1}]
    assert params["metadata"]["gift_order_id"] == str(body["id"])
    assert f"/orders/{body['id']}?payment=success" in params["success_url"]
    assert f"/orders/{body['id']}?payment=cancel" in params["cancel_url"]


def test_checkout_replaces_customer_from_other_stripe_mode(
    auth_client, prospect_id, stripe_stub
):
    """A stored test-mode customer id must be re-minted under live keys.

    Reproduces the "No such customer" failure seen when switching from test to
    live Stripe keys: the id saved on the user no longer resolves, so checkout
    must create a fresh customer instead of erroring.
    """
    # First order creates and persists a customer id on the user.
    _create_order(auth_client, prospect_id)
    assert len(stripe_stub.customer_create_calls) == 1

    # Simulate that stored id not existing in the current Stripe mode.
    stripe_stub.retrieved_customer = None

    # A subsequent order must not 500; it should re-mint the customer instead.
    body = _create_order(auth_client, prospect_id)

    assert body["payment_status"] == "pending"
    assert stripe_stub.customer_retrieve_calls[-1] == "cus_test_123"
    # A replacement customer was created rather than raising a 500.
    assert len(stripe_stub.customer_create_calls) == 2


def test_checkout_endpoint_returns_url(auth_client, prospect_id, stripe_stub):
    order = _create_order(auth_client, prospect_id)

    resp = auth_client.post(f"/gift-orders/{order['id']}/checkout")

    assert resp.status_code == 200, resp.text
    assert resp.json()["checkout_url"] == stripe_stub.created_session["url"]


def test_checkout_reuses_open_session(auth_client, prospect_id, stripe_stub):
    """Repeat checkout attempts must not create a second payable session."""
    order = _create_order(auth_client, prospect_id)
    assert len(stripe_stub.session_create_calls) == 1

    # The order's existing session is still open, so it should be reused.
    stripe_stub.retrieved_session = {
        "id": "cs_test_created",
        "status": "open",
        "url": "https://checkout.stripe.test/pay/cs_test_created",
    }

    resp = auth_client.post(f"/gift-orders/{order['id']}/checkout")

    assert resp.status_code == 200, resp.text
    assert resp.json()["checkout_url"] == stripe_stub.retrieved_session["url"]
    # No new session was created.
    assert len(stripe_stub.session_create_calls) == 1


def test_checkout_creates_new_session_when_previous_expired(
    auth_client, prospect_id, stripe_stub
):
    order = _create_order(auth_client, prospect_id)
    assert len(stripe_stub.session_create_calls) == 1

    # Previous session is no longer open -> a fresh one must be created.
    stripe_stub.retrieved_session = {"id": "cs_test_created", "status": "expired"}
    stripe_stub.created_session = {
        "id": "cs_test_second",
        "url": "https://checkout.stripe.test/pay/cs_test_second",
    }

    resp = auth_client.post(f"/gift-orders/{order['id']}/checkout")

    assert resp.status_code == 200, resp.text
    assert resp.json()["checkout_url"] == "https://checkout.stripe.test/pay/cs_test_second"
    assert len(stripe_stub.session_create_calls) == 2


# --- §3.1 Checkout: guards ----------------------------------------------------


def test_order_create_rolls_back_when_stripe_not_configured(
    auth_client, prospect_id, monkeypatch
):
    from app.config import settings

    monkeypatch.setattr(settings, "stripe_secret_key", "")

    resp = auth_client.post("/gift-orders", json=make_order_payload(prospect_id))

    assert resp.status_code == 503, resp.text
    # The unpayable pending order must not be left behind.
    listing = auth_client.get("/gift-orders")
    assert listing.status_code == 200
    assert listing.json() == []


def test_checkout_rejects_unknown_gift(auth_client, prospect_id, stripe_stub):
    resp = auth_client.post("/gift-orders", json=make_order_payload(prospect_id, "cookies-999"))
    assert resp.status_code == 400
    assert stripe_stub.session_create_calls == []


def test_checkout_rejects_already_paid_order(auth_client, prospect_id, stripe_stub):
    order = _create_order(auth_client, prospect_id)

    # Mark the order paid out of band via a completed webhook.
    _post_completed_webhook(auth_client, order["id"], monkeypatch=None)

    resp = auth_client.post(f"/gift-orders/{order['id']}/checkout")
    assert resp.status_code == 400
    assert "already paid" in resp.json()["detail"].lower()


def test_checkout_foreign_order_returns_404(client, prospect_id, stripe_stub):
    # `prospect_id` fixture authenticated `client` as seller@example.com and
    # created an order-eligible prospect; make an order as that user first.
    order = _create_order(client, prospect_id)

    # Switch to a different user.
    client.post("/auth/logout")
    resp = client.post(
        "/auth/signup",
        json={"email": "other@example.com", "password": "another-strong-pass"},
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(f"/gift-orders/{order['id']}/checkout")
    assert resp.status_code == 404


def test_checkout_requires_authentication(client, stripe_stub):
    resp = client.post("/gift-orders/1/checkout")
    assert resp.status_code == 401


# --- §3.2 Webhooks ------------------------------------------------------------


def _completed_event(order_id: int, session_id: str = "cs_test_created") -> dict:
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "mode": "payment",
                "metadata": {"gift_order_id": str(order_id)},
                "payment_status": "paid",
            }
        },
    }


def _post_completed_webhook(auth_client, order_id, monkeypatch, session_id="cs_test_created"):
    """Send a checkout.session.completed webhook for ``order_id``.

    When ``monkeypatch`` is None a local monkeypatch context is created so this
    helper can also be used from tests that don't take the fixture.
    """
    import contextlib

    from _pytest.monkeypatch import MonkeyPatch

    ctx = contextlib.nullcontext(monkeypatch) if monkeypatch else MonkeyPatch().context()
    with ctx as mp:
        mp.setattr(
            stripe.Webhook,
            "construct_event",
            staticmethod(lambda payload, sig, secret: _completed_event(order_id, session_id)),
        )
        return auth_client.post(
            "/billing/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "t=1,v1=validsig"},
        )


def test_webhook_marks_order_paid_and_queued(auth_client, prospect_id, stripe_stub, monkeypatch):
    order = _create_order(auth_client, prospect_id)

    resp = _post_completed_webhook(auth_client, order["id"], monkeypatch)

    assert resp.status_code == 200
    assert resp.json() == {"received": True}

    fetched = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert fetched["payment_status"] == "paid"
    assert fetched["status"] == "queued"


def test_webhook_invalid_signature_returns_400_and_no_change(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    order = _create_order(auth_client, prospect_id)

    def _raise(payload, sig, secret):
        raise stripe.error.SignatureVerificationError("bad signature", sig)

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(_raise))

    resp = auth_client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=bogus"},
    )
    assert resp.status_code == 400

    # Order must remain unpaid.
    fetched = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert fetched["payment_status"] == "pending"
    assert fetched["status"] == "pending_payment"


def test_webhook_missing_signature_returns_400(auth_client, prospect_id, stripe_stub):
    order = _create_order(auth_client, prospect_id)
    resp = auth_client.post("/billing/webhook", content=b"{}")
    assert resp.status_code == 400

    fetched = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert fetched["payment_status"] == "pending"


def test_webhook_replay_does_not_double_process(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    """TEST-RISK: duplicate webhook delivery must not re-fulfill an order."""
    order = _create_order(auth_client, prospect_id)

    notifications: list[int] = []
    import app.fulfillment as fulfillment

    monkeypatch.setattr(
        fulfillment,
        "send_new_order_notification",
        lambda **kwargs: notifications.append(kwargs.get("order_id")),
    )

    first = _post_completed_webhook(auth_client, order["id"], monkeypatch)
    second = _post_completed_webhook(auth_client, order["id"], monkeypatch)

    assert first.status_code == 200
    assert second.status_code == 200
    # The order is fulfilled exactly once despite two deliveries.
    assert notifications == [order["id"]]

    fetched = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert fetched["payment_status"] == "paid"


def test_webhook_ignores_unknown_order(auth_client, prospect_id, stripe_stub, monkeypatch):
    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        staticmethod(lambda payload, sig, secret: _completed_event(999_999)),
    )
    resp = auth_client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=validsig"},
    )
    # Unknown order id is silently ignored; the endpoint still ACKs Stripe.
    assert resp.status_code == 200
    assert resp.json() == {"received": True}


# --- Payment sync on read (GET /gift-orders/{id}) ----------------------------


def test_get_order_syncs_paid_status_from_stripe(
    auth_client, prospect_id, stripe_stub
):
    """If the webhook was missed, reading the order reconciles from Stripe."""
    order = _create_order(auth_client, prospect_id)

    # Stripe now reports the session as paid.
    stripe_stub.retrieved_session = {
        "id": "cs_test_created",
        "status": "complete",
        "payment_status": "paid",
    }

    fetched = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert fetched["payment_status"] == "paid"
    assert fetched["status"] == "queued"


def test_get_order_stays_pending_when_stripe_unpaid(auth_client, prospect_id, stripe_stub):
    order = _create_order(auth_client, prospect_id)

    # Default retrieved_session is open/unpaid.
    fetched = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert fetched["payment_status"] == "pending"
    assert fetched["status"] == "pending_payment"


def test_webhook_ignores_unrelated_event_types(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    order = _create_order(auth_client, prospect_id)

    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        staticmethod(
            lambda payload, sig, secret: {
                "type": "customer.created",
                "data": {"object": {"id": "cus_x"}},
            }
        ),
    )
    resp = auth_client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=validsig"},
    )
    assert resp.status_code == 200
    fetched = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert fetched["payment_status"] == "pending"


def test_webhook_invalid_json_body_returns_400(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    order = _create_order(auth_client, prospect_id)

    def _raise(payload, sig, secret):
        raise ValueError("Invalid payload")

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(_raise))
    resp = auth_client.post(
        "/billing/webhook",
        content=b"not-json",
        headers={"Stripe-Signature": "t=1,v1=validsig"},
    )
    assert resp.status_code == 400
    fetched = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert fetched["payment_status"] == "pending"


def test_webhook_passes_raw_body_to_construct_event(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    """Signature verification must see the exact raw request body (TEST.MD §12.2)."""
    order = _create_order(auth_client, prospect_id)
    seen: dict = {}

    def _capture(payload, sig, secret):
        seen["payload"] = payload
        seen["sig"] = sig
        seen["secret"] = secret
        return _completed_event(order["id"])

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(_capture))
    raw = b'{"id":"evt_test_raw_body"}'
    resp = auth_client.post(
        "/billing/webhook",
        content=raw,
        headers={"Stripe-Signature": "t=1,v1=validsig"},
    )
    assert resp.status_code == 200
    assert seen["payload"] == raw
    assert seen["sig"] == "t=1,v1=validsig"


def test_list_gift_orders_sync_not_required_for_listing(
    auth_client, prospect_id, stripe_stub
):
    """Listing does not auto-reconcile; detail GET does."""
    order = _create_order(auth_client, prospect_id)
    stripe_stub.retrieved_session = {
        "id": "cs_test_created",
        "status": "complete",
        "payment_status": "paid",
    }

    listed = auth_client.get("/gift-orders").json()
    assert listed[0]["payment_status"] == "pending"

    detail = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert detail["payment_status"] == "paid"
