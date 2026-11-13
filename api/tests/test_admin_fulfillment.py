"""Admin fulfillment tests — Test.MD §8 (queue/detail, status, tracking) and §7.2."""

from __future__ import annotations

from conftest import create_order, create_prospect, mark_order_paid_db, signup


def _paid_order(make_client):
    """Create a paid/queued order owned by a regular user; return (owner, order)."""
    owner = signup(make_client(), "owner@example.com")
    prospect = create_prospect(owner, email="p@example.com")
    order = create_order(owner, prospect["id"])
    mark_order_paid_db(order["id"])
    return owner, order


# --- §8.1 Queue and detail ---------------------------------------------------


def test_admin_sees_queued_order_with_fulfillment_fields(admin_client, make_client, stripe_stub):
    _, order = _paid_order(make_client)

    listing = admin_client.get("/admin/gift-orders", params={"status": "queued"})
    assert listing.status_code == 200
    rows = listing.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == order["id"]
    assert row["recipient_name"] == order["recipient_name"]
    assert row["shipping_address"] == order["shipping_address"]
    assert row["note"] == order["note"]
    # Admin view is enriched with owner/prospect context.
    assert row["owner_email"] == "owner@example.com"
    assert row["prospect_email"] == "p@example.com"


def test_admin_status_filter_excludes_other_statuses(admin_client, make_client, stripe_stub):
    _paid_order(make_client)
    assert len(admin_client.get("/admin/gift-orders", params={"status": "queued"}).json()) == 1
    assert admin_client.get("/admin/gift-orders", params={"status": "shipped"}).json() == []
    assert len(admin_client.get("/admin/gift-orders", params={"status": "all"}).json()) == 1


def test_admin_get_missing_order_returns_404(admin_client):
    assert admin_client.get("/admin/gift-orders/999999").status_code == 404


# --- §8.1 Status update + tracking -------------------------------------------


def test_admin_updates_status_and_tracking(admin_client, make_client, stripe_stub):
    owner, order = _paid_order(make_client)

    resp = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "shipped", "tracking_number": "1Z999AA10123456784"},
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["status"] == "shipped"
    assert updated["tracking_number"] == "1Z999AA10123456784"

    # §7.2 — the owner sees the status change on their order.
    owner_view = owner.get(f"/gift-orders/{order['id']}").json()
    assert owner_view["status"] == "shipped"
    assert owner_view["tracking_number"] == "1Z999AA10123456784"


def test_admin_rejects_invalid_status_value(admin_client, make_client, stripe_stub):
    _, order = _paid_order(make_client)
    resp = admin_client.patch(
        f"/admin/gift-orders/{order['id']}", json={"status": "teleported"}
    )
    assert resp.status_code == 422


# --- §7.2 Status lifecycle guards --------------------------------------------


def test_unpaid_order_cannot_advance_to_fulfillment(admin_client, make_client, stripe_stub):
    owner = signup(make_client(), "owner@example.com")
    prospect = create_prospect(owner, email="p@example.com")
    order = create_order(owner, prospect["id"])  # left unpaid

    resp = admin_client.patch(
        f"/admin/gift-orders/{order['id']}", json={"status": "shipped"}
    )
    assert resp.status_code == 400
    assert "paid" in resp.json()["detail"].lower()


def test_unpaid_order_can_be_canceled(admin_client, make_client, stripe_stub):
    owner = signup(make_client(), "owner@example.com")
    prospect = create_prospect(owner, email="p@example.com")
    order = create_order(owner, prospect["id"])  # unpaid

    resp = admin_client.patch(
        f"/admin/gift-orders/{order['id']}", json={"status": "canceled"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "canceled"


def test_paid_order_cannot_return_to_prepayment_status(
    admin_client, make_client, stripe_stub
):
    _, order = _paid_order(make_client)
    resp = admin_client.patch(
        f"/admin/gift-orders/{order['id']}", json={"status": "pending_payment"}
    )
    assert resp.status_code == 400
    assert "pre-payment" in resp.json()["detail"].lower() or "paid" in resp.json()["detail"].lower()


def test_admin_can_set_ordered_then_delivered(admin_client, make_client, stripe_stub):
    _, order = _paid_order(make_client)

    ordered = admin_client.patch(
        f"/admin/gift-orders/{order['id']}", json={"status": "ordered"}
    )
    assert ordered.status_code == 200
    assert ordered.json()["status"] == "ordered"

    delivered = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "delivered", "tracking_number": "  TRACK-123  ", "admin_notes": "  left porch  "},
    )
    assert delivered.status_code == 200
    body = delivered.json()
    assert body["status"] == "delivered"
    assert body["tracking_number"] == "TRACK-123"
    assert body["admin_notes"] == "left porch"


def test_admin_detail_includes_owner_and_prospect_context(
    admin_client, make_client, stripe_stub
):
    _, order = _paid_order(make_client)
    detail = admin_client.get(f"/admin/gift-orders/{order['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["owner_email"] == "owner@example.com"
    assert body["prospect_email"] == "p@example.com"
    assert body["prospect_name"]


def test_clearing_tracking_number_sets_null(admin_client, make_client, stripe_stub):
    _, order = _paid_order(make_client)
    admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"tracking_number": "ABC"},
    )
    cleared = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"tracking_number": "   "},
    )
    assert cleared.status_code == 200
    assert cleared.json()["tracking_number"] is None


# --- Seller status emails (shipped / delivered) ------------------------------


def _capture_seller_emails(monkeypatch):
    shipped: list[dict] = []
    delivered: list[dict] = []
    monkeypatch.setattr(
        "app.fulfillment.send_seller_order_shipped",
        lambda **kw: shipped.append(kw),
    )
    monkeypatch.setattr(
        "app.fulfillment.send_seller_order_delivered",
        lambda **kw: delivered.append(kw),
    )
    return shipped, delivered


def test_admin_shipped_emails_seller(admin_client, make_client, stripe_stub, monkeypatch):
    shipped, delivered = _capture_seller_emails(monkeypatch)
    _, order = _paid_order(make_client)

    resp = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "shipped", "tracking_number": "1Z999AA10123456784"},
    )
    assert resp.status_code == 200, resp.text
    assert len(shipped) == 1
    assert delivered == []
    mail = shipped[0]
    assert mail["seller_email"] == "owner@example.com"
    assert mail["order_id"] == order["id"]
    assert mail["tracking_number"] == "1Z999AA10123456784"
    assert mail["recipient_name"] == order["recipient_name"]
    assert mail["gift_label"]
    assert str(order["id"]) in mail["order_url"]


def test_admin_delivered_emails_seller(admin_client, make_client, stripe_stub, monkeypatch):
    shipped, delivered = _capture_seller_emails(monkeypatch)
    _, order = _paid_order(make_client)

    resp = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "delivered"},
    )
    assert resp.status_code == 200, resp.text
    assert shipped == []
    assert len(delivered) == 1
    assert delivered[0]["seller_email"] == "owner@example.com"
    assert delivered[0]["order_id"] == order["id"]


def test_admin_tracking_only_does_not_resend_seller_email(
    admin_client, make_client, stripe_stub, monkeypatch
):
    shipped, delivered = _capture_seller_emails(monkeypatch)
    _, order = _paid_order(make_client)

    first = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "shipped", "tracking_number": "AAA"},
    )
    assert first.status_code == 200, first.text
    assert len(shipped) == 1

    tracking_only = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"tracking_number": "BBB"},
    )
    assert tracking_only.status_code == 200, tracking_only.text
    assert len(shipped) == 1

    already_shipped = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "shipped", "tracking_number": "CCC"},
    )
    assert already_shipped.status_code == 200, already_shipped.text
    assert len(shipped) == 1
    assert delivered == []


def test_admin_ordered_does_not_send_seller_status_emails(
    admin_client, make_client, stripe_stub, monkeypatch
):
    shipped, delivered = _capture_seller_emails(monkeypatch)
    _, order = _paid_order(make_client)

    ordered = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "ordered"},
    )
    assert ordered.status_code == 200, ordered.text
    canceled = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "canceled"},
    )
    assert canceled.status_code == 200, canceled.text
    assert shipped == []
    assert delivered == []


def test_seller_status_email_failure_does_not_fail_patch(
    admin_client, make_client, stripe_stub, monkeypatch
):
    def _boom(**_kw):
        raise RuntimeError("resend down")

    monkeypatch.setattr("app.fulfillment.send_seller_order_shipped", _boom)
    _, order = _paid_order(make_client)

    resp = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "shipped"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "shipped"


# --- Admin-entered shipping address ------------------------------------------


_ADMIN_ADDRESS = {
    "shipping_company": "Acme Corp",
    "shipping_street": "456 Oak Ave",
    "shipping_city": "Austin",
    "shipping_state": "TX",
    "shipping_postal_code": "78701",
}


def _address_request_order(owner):
    prospect = create_prospect(owner, email="p@example.com")
    created = owner.post(
        "/gift-orders",
        json={
            "prospect_id": prospect["id"],
            "gift_id": "cookies-4",
            "recipient_name": "Dana Buyer",
            "note": "Thanks for the great meeting!",
            "request_recipient_address": True,
            "recipient_email": "dana@example.com",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _authorize_held_order(order_id: int) -> None:
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    with SessionLocal() as db:
        order = db.get(GiftOrderModel, order_id)
        session = {
            "id": order.stripe_checkout_session_id or "cs_test_created",
            "mode": "payment",
            "status": "complete",
            "payment_status": "unpaid",
            "payment_intent": "pi_test_123",
            "amount_total": 100,
            "currency": "usd",
            "metadata": {
                "gift_order_id": str(order_id),
                "defer_capture": "true",
            },
        }
        sp.fulfill_order_from_checkout_session(session, db)


def test_admin_enters_address_on_authorized_order(
    admin_client, make_client, stripe_stub, monkeypatch
):
    import app.fulfillment as fulfillment
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    monkeypatch.setattr(sp, "send_orderer_receipt", lambda **kw: None)
    monkeypatch.setattr(fulfillment, "send_new_order_notification", lambda **kw: None)

    owner = signup(make_client(), "owner@example.com")
    order = _address_request_order(owner)
    _authorize_held_order(order["id"])

    resp = admin_client.post(
        f"/admin/gift-orders/{order['id']}/shipping-address",
        json=_ADMIN_ADDRESS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["payment_status"] == "paid"
    assert body["shipping_company"] == "Acme Corp"
    assert body["shipping_street"] == "456 Oak Ave"
    assert body["shipping_city"] == "Austin"
    assert body["shipping_state"] == "TX"
    assert body["shipping_postal_code"] == "78701"
    assert body["shipping_address"] == "Acme Corp\n456 Oak Ave\nAustin, TX 78701"
    assert len(stripe_stub.payment_intent_capture_calls) == 1
    assert stripe_stub.payment_intent_capture_calls[0]["id"] == "pi_test_123"

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order["id"])
        assert row.address_request_token is None
        assert row.redeem_code is None

    owner_view = owner.get(f"/gift-orders/{order['id']}").json()
    assert owner_view["status"] == "queued"
    assert owner_view["payment_status"] == "paid"
    assert owner_view["shipping_street"] == "456 Oak Ave"


def test_admin_enters_address_on_owed_order_queues_without_capture(
    admin_client, make_client, stripe_stub, monkeypatch
):
    import app.fulfillment as fulfillment
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(fulfillment, "send_new_order_notification", lambda **kw: None)

    owner = signup(make_client(), "owner@example.com")
    order = create_order(owner, create_prospect(owner, email="p@example.com")["id"])
    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order["id"])
        row.payment_status = "owed"
        row.status = "no_address"
        row.shipping_address = None
        row.shipping_company = None
        row.shipping_street = None
        row.shipping_street2 = None
        row.shipping_city = None
        row.shipping_state = None
        row.shipping_postal_code = None
        row.shipping_country = None
        row.stripe_price_id = "price_test"
        row.address_request_token = "tok-admin"
        row.redeem_code = "CK-ADMIN"
        db.add(row)
        db.commit()

    resp = admin_client.post(
        f"/admin/gift-orders/{order['id']}/shipping-address",
        json=_ADMIN_ADDRESS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["payment_status"] == "owed"
    assert body["shipping_street"] == "456 Oak Ave"
    assert stripe_stub.payment_intent_capture_calls == []

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order["id"])
        assert row.address_request_token is None
        assert row.redeem_code is None


def test_admin_updates_address_on_paid_order_without_another_charge(
    admin_client, make_client, stripe_stub
):
    _, order = _paid_order(make_client)
    resp = admin_client.post(
        f"/admin/gift-orders/{order['id']}/shipping-address",
        json=_ADMIN_ADDRESS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["payment_status"] == "paid"
    assert body["shipping_street"] == "456 Oak Ave"
    assert body["shipping_city"] == "Austin"
    assert stripe_stub.payment_intent_capture_calls == []


def test_admin_address_requires_complete_street(
    admin_client, make_client, stripe_stub
):
    _, order = _paid_order(make_client)
    resp = admin_client.post(
        f"/admin/gift-orders/{order['id']}/shipping-address",
        json={"shipping_street": "1 Main St", "shipping_city": "Austin"},
    )
    assert resp.status_code == 422
    assert stripe_stub.payment_intent_capture_calls == []


def test_admin_cannot_enter_address_before_authorization(
    admin_client, make_client, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    owner = signup(make_client(), "owner@example.com")
    order = _address_request_order(owner)

    resp = admin_client.post(
        f"/admin/gift-orders/{order['id']}/shipping-address",
        json=_ADMIN_ADDRESS,
    )
    assert resp.status_code == 400
    assert "authoriz" in resp.json()["detail"].lower()
    assert stripe_stub.payment_intent_capture_calls == []
    assert owner.get(f"/gift-orders/{order['id']}").json()["status"] == "no_address"


def test_non_admin_cannot_set_shipping_address(make_client, stripe_stub):
    owner, order = _paid_order(make_client)
    resp = owner.post(
        f"/admin/gift-orders/{order['id']}/shipping-address",
        json=_ADMIN_ADDRESS,
    )
    assert resp.status_code == 403


def test_admin_address_missing_order_returns_404(admin_client):
    resp = admin_client.post(
        "/admin/gift-orders/999999/shipping-address",
        json=_ADMIN_ADDRESS,
    )
    assert resp.status_code == 404


def test_admin_cannot_change_address_on_canceled_order(
    admin_client, make_client, stripe_stub
):
    _, order = _paid_order(make_client)
    canceled = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "canceled"},
    )
    assert canceled.status_code == 200
    resp = admin_client.post(
        f"/admin/gift-orders/{order['id']}/shipping-address",
        json=_ADMIN_ADDRESS,
    )
    assert resp.status_code == 400
