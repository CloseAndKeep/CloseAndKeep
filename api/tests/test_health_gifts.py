"""Health and gift-catalog endpoints."""

from __future__ import annotations


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "env" in body


def test_gifts_catalog_lists_known_packs(client, monkeypatch):
    from app.config import GIFT_CATALOG
    import app.main as main

    # Avoid live Stripe price lookups in CI (patch where main bound the import).
    monkeypatch.setattr(
        main,
        "list_gift_prices",
        lambda: [
            {
                "gift_id": str(item["id"]),
                "cookie_count": int(item["cookie_count"]),
                "unit_amount": None,
                "currency": None,
            }
            for item in GIFT_CATALOG
        ],
    )

    resp = client.get("/gifts")
    assert resp.status_code == 200
    body = resp.json()
    assert {row["gift_id"] for row in body} == {"cookies-4", "cookies-12"}
    for row in body:
        assert row["cookie_count"] in {4, 12}
        assert "unit_amount" in row
        assert "currency" in row


def test_gifts_catalog_includes_stripe_amounts_when_available(client, monkeypatch):
    import app.main as main

    monkeypatch.setattr(
        main,
        "list_gift_prices",
        lambda: [
            {
                "gift_id": "cookies-4",
                "cookie_count": 4,
                "unit_amount": 2499,
                "currency": "usd",
            }
        ],
    )
    resp = client.get("/gifts")
    assert resp.status_code == 200
    assert resp.json() == [
        {
            "gift_id": "cookies-4",
            "cookie_count": 4,
            "unit_amount": 2499,
            "currency": "usd",
        }
    ]
