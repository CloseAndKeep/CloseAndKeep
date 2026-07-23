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
