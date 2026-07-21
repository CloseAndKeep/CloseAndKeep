"""API key auth tests — Option 1 public order API (create order + Checkout URL)."""

from __future__ import annotations

from conftest import create_prospect, make_order_payload, signup


def _create_key(client, name: str = "Agent"):
    resp = client.post("/api-keys", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_lists_and_revokes_api_key(auth_client):
    created = _create_key(auth_client, "CRM sync")
    assert created["api_key"].startswith("cak_")
    assert created["key_prefix"] == created["api_key"][:12]
    assert created["name"] == "CRM sync"
    assert created["revoked_at"] is None

    listed = auth_client.get("/api-keys")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert "api_key" not in body[0]
    assert body[0]["key_prefix"] == created["key_prefix"]

    revoked = auth_client.delete(f"/api-keys/{created['id']}")
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None


def test_bearer_key_can_create_prospect_and_order(make_client, stripe_stub):
    browser = make_client()
    signup(browser, "api-owner@example.com")
    created = _create_key(browser, "Zapier")
    raw_key = created["api_key"]

    # Separate client with no session cookie — auth only via Bearer.
    api = make_client()
    headers = {"Authorization": f"Bearer {raw_key}"}

    prospect_resp = api.post(
        "/prospects",
        headers=headers,
        json={
            "name": "Alex Prospect",
            "title": "CEO",
            "company": "Northwind",
            "email": "alex@northwind.example",
            "deal_status": "open",
        },
    )
    assert prospect_resp.status_code == 201, prospect_resp.text
    prospect_id = prospect_resp.json()["id"]

    order_resp = api.post(
        "/gift-orders",
        headers=headers,
        json=make_order_payload(prospect_id),
    )
    assert order_resp.status_code == 201, order_resp.text
    data = order_resp.json()
    assert data["checkout_url"].startswith("https://checkout.stripe.test/")
    assert data["status"] == "pending_payment"
    assert data["payment_status"] == "pending"
    assert len(stripe_stub.session_create_calls) == 1

    get_resp = api.get(f"/gift-orders/{data['id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == data["id"]


def test_revoked_key_is_rejected(make_client, stripe_stub):
    browser = make_client()
    signup(browser, "revoke-me@example.com")
    created = _create_key(browser)
    raw_key = created["api_key"]
    browser.delete(f"/api-keys/{created['id']}")

    api = make_client()
    resp = api.get("/auth/me", headers={"Authorization": f"Bearer {raw_key}"})
    assert resp.status_code == 401


def test_invalid_bearer_rejected(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer cak_not_a_real_key"})
    assert resp.status_code == 401


def test_guest_cannot_create_api_key(client):
    guest = client.post("/auth/guest")
    assert guest.status_code == 200
    resp = client.post("/api-keys", json={"name": "Nope"})
    assert resp.status_code == 403


def test_api_key_cannot_access_other_users_prospect(make_client, stripe_stub):
    owner_a = make_client()
    signup(owner_a, "owner-a@example.com")
    prospect = create_prospect(owner_a)
    key_a = _create_key(owner_a)["api_key"]

    owner_b = make_client()
    signup(owner_b, "owner-b@example.com")
    key_b = _create_key(owner_b)["api_key"]

    # B cannot create an order against A's prospect.
    api_b = make_client()
    resp = api_b.post(
        "/gift-orders",
        headers={"Authorization": f"Bearer {key_b}"},
        json=make_order_payload(prospect["id"]),
    )
    assert resp.status_code == 404

    # A still can.
    api_a = make_client()
    ok = api_a.post(
        "/gift-orders",
        headers={"Authorization": f"Bearer {key_a}"},
        json=make_order_payload(prospect["id"]),
    )
    assert ok.status_code == 201, ok.text


def test_cannot_revoke_another_users_api_key(make_client):
    owner_a = make_client()
    signup(owner_a, "owner-a@example.com")
    key_a = _create_key(owner_a)

    owner_b = make_client()
    signup(owner_b, "owner-b@example.com")

    resp = owner_b.delete(f"/api-keys/{key_a['id']}")
    assert resp.status_code == 404

    # Key still works for A.
    api = make_client()
    me = api.get("/auth/me", headers={"Authorization": f"Bearer {key_a['api_key']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "owner-a@example.com"


def test_blank_api_key_name_rejected(auth_client):
    assert auth_client.post("/api-keys", json={"name": "   "}).status_code == 422


def test_api_key_usage_updates_last_used_at(make_client, stripe_stub):
    browser = make_client()
    signup(browser, "usage@example.com")
    created = _create_key(browser)
    assert created["last_used_at"] is None

    api = make_client()
    assert api.get("/auth/me", headers={"Authorization": f"Bearer {created['api_key']}"}).status_code == 200

    listed = browser.get("/api-keys").json()
    assert listed[0]["last_used_at"] is not None


def test_revoke_is_idempotent(auth_client):
    created = _create_key(auth_client)
    first = auth_client.delete(f"/api-keys/{created['id']}")
    second = auth_client.delete(f"/api-keys/{created['id']}")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["revoked_at"] is not None
