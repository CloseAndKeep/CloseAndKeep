"""Security hardening: API keys cannot hit admin; create paths are rate-limited."""

from __future__ import annotations

from conftest import create_prospect, make_order_payload, signup


def test_admin_api_key_cannot_list_admin_orders(make_client, stripe_stub):
    admin = make_client()
    signup(admin, "admin@example.com", "admin-strong-pass-1")
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


def test_xss_payload_stored_and_returned_escaped_as_data(
    auth_client, prospect_id, stripe_stub
):
    """API stores XSS-like strings as plain data; clients must escape on render."""
    payload = make_order_payload(prospect_id)
    payload["recipient_name"] = '<script>alert("xss")</script>'
    payload["note"] = "Thanks <img src=x onerror=alert(1)>"
    payload["shipping_address"] = "123 Main<script>"

    resp = auth_client.post("/gift-orders", json=payload)
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["recipient_name"] == '<script>alert("xss")</script>'
    assert "onerror=alert(1)" in order["note"]

    # Round-trip through GET — still data, not executed (JSON, not HTML).
    fetched = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert fetched["recipient_name"] == order["recipient_name"]
    assert fetched["note"] == order["note"]
    assert fetched["shipping_address"] == "123 Main<script>"


def test_sql_injection_strings_do_not_alter_other_rows(make_client, stripe_stub):
    from conftest import create_prospect, signup

    owner = signup(make_client(), "owner@example.com")
    other = signup(make_client(), "other@example.com")
    victim = create_prospect(other, name="Victim", email="victim@example.com")

    # Injection attempt in prospect name/email fields — must not touch other rows.
    evil = owner.post(
        "/prospects",
        json={
            "name": "Robert'); DROP TABLE prospects;--",
            "email": "evil@example.com",
            "deal_status": "open",
        },
    )
    assert evil.status_code == 201, evil.text

    still_there = other.get(f"/prospects/{victim['id']}")
    assert still_there.status_code == 200
    assert still_there.json()["name"] == "Victim"
    assert len(other.get("/prospects").json()) == 1
    assert len(owner.get("/prospects").json()) == 1
