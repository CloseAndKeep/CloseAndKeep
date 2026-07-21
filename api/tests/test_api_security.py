"""Security hardening: API keys cannot hit admin; create paths are rate-limited."""

from __future__ import annotations

from conftest import create_prospect, make_order_payload, signup


def test_admin_api_key_cannot_list_admin_orders(make_client, stripe_stub):
    admin = make_client()
    signup(admin, "admin@example.com", "admin-strong-pass")
    created = admin.post("/api-keys", json={"name": "Ops agent"}).json()
    raw_key = created["api_key"]

    api = make_client()
    resp = api.get(
        "/admin/gift-orders",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp.status_code == 403
    assert "API key" in resp.json()["detail"]


def test_admin_session_still_can_list_admin_orders(admin_client):
    resp = admin_client.get("/admin/gift-orders")
    assert resp.status_code == 200


def test_order_create_rate_limit(auth_client, prospect_id, stripe_stub, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_order_create", 2)
    monkeypatch.setattr(settings, "rate_limit_order_create_ip", 100)

    payload = make_order_payload(prospect_id)
    assert auth_client.post("/gift-orders", json=payload).status_code == 201
    assert auth_client.post("/gift-orders", json=payload).status_code == 201
    limited = auth_client.post("/gift-orders", json=payload)
    assert limited.status_code == 429
    assert limited.headers.get("Retry-After")


def test_api_key_create_rate_limit(auth_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_api_key_create", 2)

    assert auth_client.post("/api-keys", json={"name": "one"}).status_code == 201
    assert auth_client.post("/api-keys", json={"name": "two"}).status_code == 201
    limited = auth_client.post("/api-keys", json={"name": "three"})
    assert limited.status_code == 429
