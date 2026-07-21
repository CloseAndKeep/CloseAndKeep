"""Bulk CSV import for cookie gift orders."""

from __future__ import annotations

import io

from conftest import create_prospect


def _csv_bytes(text: str) -> io.BytesIO:
    return io.BytesIO(text.encode("utf-8"))


def _upload(client, csv_text: str, filename: str = "orders.csv"):
    return client.post(
        "/gift-orders/import",
        files={"file": (filename, _csv_bytes(csv_text), "text/csv")},
    )


def test_template_and_example_downloads(auth_client):
    template = auth_client.get("/gift-orders/import/template")
    assert template.status_code == 200
    assert "text/csv" in template.headers["content-type"]
    assert "cookie-orders-template.csv" in template.headers["content-disposition"]
    assert template.text.startswith("Name,Email,Cookies,Address")
    # Template is headers only (no sample data rows).
    assert template.text.strip().count("\n") == 0 or template.text.count("\n") == 1

    example = auth_client.get("/gift-orders/import/example")
    assert example.status_code == 200
    assert "cookie-orders-example.csv" in example.headers["content-disposition"]
    body = example.text
    assert "Name,Email,Cookies,Address" in body
    assert "jane@example.com" in body
    assert "bob@example.com" in body


def test_import_creates_orders_with_and_without_address(auth_client, stripe_stub):
    csv_text = (
        "Name,Email,Cookies,Address\n"
        'Jane Smith,jane@example.com,4,"123 Main St, Springfield, IL 62704"\n'
        "Bob Jones,bob@example.com,1,\n"
        "Alex Rivera,alex@example.com,12,456 Oak Ave\n"
    )
    resp = _upload(auth_client, csv_text)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert len(data["created"]) == 3
    assert data["errors"] == []
    assert data["batch_checkout_url"] == stripe_stub.created_session["url"]

    by_email = {o["recipient_email"]: o for o in data["created"]}
    jane = by_email["jane@example.com"]
    assert jane["gift_id"] == "cookies-4"
    assert jane["status"] == "pending_payment"
    assert "123 Main St" in (jane["shipping_address"] or "")
    assert jane["checkout_url"] == data["batch_checkout_url"]

    bob = by_email["bob@example.com"]
    assert bob["gift_id"] == "cookies-1"
    assert bob["status"] == "no_address"
    assert bob["shipping_address"] is None
    assert bob["checkout_url"]

    alex = by_email["alex@example.com"]
    assert alex["gift_id"] == "cookies-12"
    assert alex["status"] == "pending_payment"
    assert alex["checkout_url"] == data["batch_checkout_url"]

    # One batched immediate-capture session for Jane+Alex, one manual-capture for Bob.
    assert len(stripe_stub.session_create_calls) == 2
    batch_call = next(
        c for c in stripe_stub.session_create_calls if c["metadata"].get("defer_capture") == "false"
    )
    address_call = next(
        c for c in stripe_stub.session_create_calls if c["metadata"].get("defer_capture") == "true"
    )
    assert len(batch_call["line_items"]) == 2
    assert "payment_intent_data" not in batch_call
    assert address_call["payment_intent_data"] == {"capture_method": "manual"}
    assert set(batch_call["metadata"]["gift_order_ids"].split(",")) == {
        str(jane["id"]),
        str(alex["id"]),
    }


def test_batch_checkout_webhook_marks_all_known_address_orders_paid(
    auth_client, stripe_stub, monkeypatch
):
    csv_text = (
        "Name,Email,Cookies,Address\n"
        "Jane Smith,jane@example.com,4,123 Main St\n"
        "Alex Rivera,alex@example.com,12,456 Oak Ave\n"
    )
    resp = _upload(auth_client, csv_text)
    assert resp.status_code == 201, resp.text
    created = resp.json()["created"]
    order_ids = [o["id"] for o in created]
    session_id = "cs_test_created"

    import stripe
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    with SessionLocal() as db:
        for oid in order_ids:
            order = db.get(GiftOrderModel, oid)
            assert order.stripe_checkout_session_id == session_id

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "mode": "payment",
                "metadata": {
                    "gift_order_ids": ",".join(str(i) for i in order_ids),
                    "gift_order_id": str(order_ids[0]),
                    "defer_capture": "false",
                },
                "payment_status": "paid",
                "amount_total": 200,
                "currency": "usd",
            }
        },
    }
    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        staticmethod(lambda payload, sig, secret: event),
    )
    webhook = auth_client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=validsig"},
    )
    assert webhook.status_code == 200

    for oid in order_ids:
        fetched = auth_client.get(f"/gift-orders/{oid}").json()
        assert fetched["payment_status"] == "paid"
        assert fetched["status"] == "queued"

def test_import_rejects_invalid_cookie_count(auth_client, stripe_stub):
    csv_text = (
        "Name,Email,Cookies,Address\n"
        "Jane Smith,jane@example.com,2,123 Main St\n"
    )
    resp = _upload(auth_client, csv_text)
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["message"].startswith("CSV validation failed")
    assert any("1" in e["message"] and "4" in e["message"] for e in detail["errors"])
    assert stripe_stub.session_create_calls == []

    listed = auth_client.get("/gift-orders")
    assert listed.status_code == 200
    assert listed.json() == []


def test_import_rejects_missing_headers(auth_client):
    resp = _upload(auth_client, "Foo,Bar\n1,2\n")
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert any("Missing required column" in e["message"] for e in detail["errors"])


def test_import_rejects_invalid_email(auth_client):
    csv_text = "Name,Email,Cookies,Address\nJane,not-an-email,4,123 Main\n"
    resp = _upload(auth_client, csv_text)
    assert resp.status_code == 400
    assert any("Invalid email" in e["message"] for e in resp.json()["detail"]["errors"])


def test_import_reuses_prospect_by_email(auth_client, stripe_stub):
    prospect = create_prospect(auth_client, name="Existing", email="jane@example.com")
    csv_text = (
        "Name,Email,Cookies,Address\n"
        "Jane Smith,jane@example.com,4,123 Main St\n"
    )
    resp = _upload(auth_client, csv_text)
    assert resp.status_code == 201, resp.text
    order = resp.json()["created"][0]
    assert order["prospect_id"] == prospect["id"]


def test_guest_cannot_import(client, stripe_stub):
    assert client.post("/auth/guest").status_code == 200
    csv_text = (
        "Name,Email,Cookies,Address\n"
        "Jane Smith,jane@example.com,4,123 Main St\n"
    )
    resp = _upload(client, csv_text)
    assert resp.status_code == 403


def test_import_rejects_non_csv_filename(auth_client):
    resp = auth_client.post(
        "/gift-orders/import",
        files={"file": ("orders.txt", _csv_bytes("Name,Email,Cookies,Address\n"), "text/plain")},
    )
    assert resp.status_code == 400
    assert "csv" in resp.json()["detail"].lower()


def test_import_requires_authentication(client):
    csv_text = "Name,Email,Cookies,Address\nJane,jane@example.com,4,1 Main\n"
    resp = _upload(client, csv_text)
    assert resp.status_code == 401


def test_import_rolls_back_when_stripe_unavailable(auth_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "stripe_secret_key", "")
    csv_text = (
        "Name,Email,Cookies,Address\n"
        "Jane Smith,jane@example.com,4,123 Main St\n"
    )
    resp = _upload(auth_client, csv_text)
    assert resp.status_code == 503
    assert auth_client.get("/gift-orders").json() == []


def test_import_only_address_rows_still_batch_checkouts(auth_client, stripe_stub):
    csv_text = (
        "Name,Email,Cookies,Address\n"
        "Jane Smith,jane@example.com,4,123 Main St\n"
        "Alex Rivera,alex@example.com,12,456 Oak Ave\n"
    )
    resp = _upload(auth_client, csv_text)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["batch_checkout_url"]
    assert all(o["checkout_url"] == data["batch_checkout_url"] for o in data["created"])
    assert len(stripe_stub.session_create_calls) == 1
