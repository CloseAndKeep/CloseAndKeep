"""Authorization & tenancy tests — Test.MD §2 and §16 (cross-tenant leakage)."""

from __future__ import annotations

from conftest import create_order, create_prospect, signup


# --- §2.1 Prospect / order scope ---------------------------------------------


def test_cannot_read_foreign_prospect(make_client):
    owner = signup(make_client(), "owner@example.com")
    intruder = signup(make_client(), "intruder@example.com")

    prospect = create_prospect(owner, email="p@example.com")

    resp = intruder.get(f"/prospects/{prospect['id']}")
    assert resp.status_code == 404  # not 403 — do not confirm existence


def test_cannot_update_foreign_prospect(make_client):
    owner = signup(make_client(), "owner@example.com")
    intruder = signup(make_client(), "intruder@example.com")

    prospect = create_prospect(owner, email="p@example.com")

    resp = intruder.patch(
        f"/prospects/{prospect['id']}",
        json={"deal_status": "won"},
    )
    assert resp.status_code == 404

    # The owner's data is unchanged.
    assert owner.get(f"/prospects/{prospect['id']}").json()["deal_status"] == "open"


def test_gift_order_listing_only_returns_own_rows(make_client, stripe_stub):
    owner = signup(make_client(), "owner@example.com")
    intruder = signup(make_client(), "intruder@example.com")

    prospect = create_prospect(owner, email="p@example.com")
    create_order(owner, prospect["id"])

    assert len(owner.get("/gift-orders").json()) == 1
    assert intruder.get("/gift-orders").json() == []


def test_cannot_read_foreign_gift_order(make_client, stripe_stub):
    owner = signup(make_client(), "owner@example.com")
    intruder = signup(make_client(), "intruder@example.com")

    prospect = create_prospect(owner, email="p@example.com")
    order = create_order(owner, prospect["id"])

    assert intruder.get(f"/gift-orders/{order['id']}").status_code == 404


# --- §2.2 Admin --------------------------------------------------------------


def test_non_admin_forbidden_on_admin_list(auth_client):
    resp = auth_client.get("/admin/gift-orders")
    assert resp.status_code == 403


def test_non_admin_forbidden_on_admin_detail_and_update(make_client, stripe_stub):
    owner = signup(make_client(), "owner@example.com")
    prospect = create_prospect(owner, email="p@example.com")
    order = create_order(owner, prospect["id"])

    assert owner.get(f"/admin/gift-orders/{order['id']}").status_code == 403
    assert (
        owner.patch(
            f"/admin/gift-orders/{order['id']}",
            json={"status": "queued"},
        ).status_code
        == 403
    )


def test_admin_routes_require_authentication(client):
    assert client.get("/admin/gift-orders").status_code == 401


def test_admin_can_access_admin_routes(admin_client):
    assert admin_client.get("/admin/gift-orders").status_code == 200
