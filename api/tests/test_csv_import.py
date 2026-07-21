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

    by_email = {o["recipient_email"]: o for o in data["created"]}
    jane = by_email["jane@example.com"]
    assert jane["gift_id"] == "cookies-4"
    assert jane["status"] == "pending_payment"
    assert "123 Main St" in (jane["shipping_address"] or "")
    assert jane["checkout_url"]

    bob = by_email["bob@example.com"]
    assert bob["gift_id"] == "cookies-1"
    assert bob["status"] == "no_address"
    assert bob["shipping_address"] is None
    assert bob["checkout_url"]

    alex = by_email["alex@example.com"]
    assert alex["gift_id"] == "cookies-12"
    assert alex["status"] == "pending_payment"

    # Address-request rows use manual capture; known-address rows do not.
    defer_flags = [
        call.get("metadata", {}).get("defer_capture") for call in stripe_stub.session_create_calls
    ]
    assert defer_flags.count("true") == 1
    assert len(stripe_stub.session_create_calls) == 3


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
