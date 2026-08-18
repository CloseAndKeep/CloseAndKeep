"""CRM stage recipes: persist, match, and choose pack."""

from __future__ import annotations

from unittest.mock import patch

from app.db import SessionLocal
from app.integrations.crypto import encrypt_token
from app.integrations.reminders import (
    default_stage_recipes,
    effective_stage_recipes,
    match_stage_recipe,
)
from app.integrations.salesforce import _soql_stage_clause, upsert_connection_from_oauth
from app.models import IntegrationConnectionModel, UserModel


def _seed_connection(
    user_id: int,
    *,
    provider: str = "salesforce",
    stage: str = "Demo Completed",
    recipes: list[dict] | None = None,
) -> int:
    db = SessionLocal()
    try:
        row = IntegrationConnectionModel(
            owner_user_id=user_id,
            provider=provider,
            external_org_id="00DTESTORG" if provider == "salesforce" else "12345678",
            instance_url=(
                "https://example.my.salesforce.com"
                if provider == "salesforce"
                else "https://api.hubapi.com"
            ),
            access_token_encrypted=encrypt_token("access-token"),
            refresh_token_encrypted=encrypt_token("refresh-token"),
            trigger_stage_name=stage,
            stage_recipes=recipes,
            enabled=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _enable_auto_order(user_id: int, *, gift_id: str = "cookies-4") -> None:
    db = SessionLocal()
    try:
        user = db.get(UserModel, user_id)
        assert user is not None
        user.billing_mode = "monthly"
        user.stripe_customer_id = "cus_test_123"
        user.stripe_default_payment_method_id = "pm_test_card"
        user.auto_order_enabled = True
        user.auto_order_gift_id = gift_id
        db.add(user)
        db.commit()
    finally:
        db.close()


def test_effective_recipes_fallback_when_unset():
    row = IntegrationConnectionModel(
        owner_user_id=1,
        provider="salesforce",
        trigger_stage_name="Demo Completed",
        stage_recipes=None,
    )
    recipes = effective_stage_recipes(row, fallback_gift_id="cookies-12")
    assert recipes == [
        {"stage_name": "Demo Completed", "gift_id": "cookies-12", "note": None}
    ]
    assert match_stage_recipe(row, "demo completed") is not None
    assert match_stage_recipe(row, "Closed Won") is None


def test_match_stage_recipe_case_insensitive():
    row = IntegrationConnectionModel(
        owner_user_id=1,
        provider="hubspot",
        trigger_stage_name="Demo Completed",
        stage_recipes=default_stage_recipes(),
    )
    won = match_stage_recipe(row, "closed won")
    assert won is not None
    assert won["gift_id"] == "cookies-12"
    renewal = match_stage_recipe(row, "RENEWAL")
    assert renewal is not None
    assert renewal["gift_id"] == "cookies-4"
    assert match_stage_recipe(row, "Prospecting") is None


def test_soql_clause_uses_all_recipe_stages():
    row = IntegrationConnectionModel(
        owner_user_id=1,
        provider="salesforce",
        trigger_stage_name="Demo Completed",
        stage_recipes=default_stage_recipes(),
    )
    clause = _soql_stage_clause(row)
    assert "IN (" in clause
    assert "Demo Completed" in clause
    assert "Closed Won" in clause
    assert "Renewal" in clause


def test_list_returns_fallback_recipe_when_unset(auth_client):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"])

    listed = auth_client.get("/integrations")
    assert listed.status_code == 200
    body = listed.json()[0]
    assert body["trigger_stage_name"] == "Demo Completed"
    assert body["stage_recipes"] == [
        {"stage_name": "Demo Completed", "gift_id": "cookies-4", "note": None}
    ]


def test_patch_stage_recipes_persists(auth_client):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])

    recipes = [
        {"stage_name": "Demo Completed", "gift_id": "cookies-4"},
        {"stage_name": "Closed Won", "gift_id": "cookies-12", "note": "Congrats on the close!"},
        {"stage_name": "Renewal", "gift_id": "cookies-4"},
    ]
    patched = auth_client.patch(
        f"/integrations/{connection_id}",
        json={"stage_recipes": recipes},
    )
    assert patched.status_code == 200, patched.text
    saved = patched.json()["stage_recipes"]
    assert len(saved) == 3
    assert saved[1]["stage_name"] == "Closed Won"
    assert saved[1]["gift_id"] == "cookies-12"
    assert saved[1]["note"] == "Congrats on the close!"
    assert patched.json()["trigger_stage_name"] == "Demo Completed"

    listed = auth_client.get("/integrations").json()[0]
    assert listed["stage_recipes"][1]["gift_id"] == "cookies-12"


def test_patch_rejects_invalid_gift_and_duplicate_stages(auth_client):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])

    bad_gift = auth_client.patch(
        f"/integrations/{connection_id}",
        json={"stage_recipes": [{"stage_name": "Demo Completed", "gift_id": "cookies-99"}]},
    )
    assert bad_gift.status_code == 422

    empty = auth_client.patch(
        f"/integrations/{connection_id}",
        json={"stage_recipes": []},
    )
    assert empty.status_code == 422

    dupes = auth_client.patch(
        f"/integrations/{connection_id}",
        json={
            "stage_recipes": [
                {"stage_name": "Closed Won", "gift_id": "cookies-4"},
                {"stage_name": "closed won", "gift_id": "cookies-12"},
            ]
        },
    )
    assert dupes.status_code == 422


def test_closed_won_recipe_auto_orders_cookies_12(auth_client, stripe_stub):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(
        me["user_id"],
        recipes=default_stage_recipes(),
    )
    _enable_auto_order(me["user_id"], gift_id="cookies-4")

    with patch("app.main.sf.verify_webhook_secret", return_value=True):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006CLOSEDWON1",
                "stage_name": "Closed Won",
                "contact_name": "Alex Buyer",
                "contact_email": "alex@acme.com",
            },
            headers={"X-Webhook-Secret": "test-secret"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "auto_ordered"
    orders = auth_client.get("/gift-orders").json()
    match = next(o for o in orders if o["id"] == body["order_id"])
    assert match["gift_id"] == "cookies-12"


def test_demo_recipe_auto_orders_cookies_4(auth_client, stripe_stub):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(
        me["user_id"],
        recipes=default_stage_recipes(),
    )
    _enable_auto_order(me["user_id"], gift_id="cookies-12")

    with patch("app.main.sf.verify_webhook_secret", return_value=True):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006DEMO1",
                "stage_name": "demo completed",
                "contact_name": "Alex Buyer",
                "contact_email": "alex@acme.com",
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "auto_ordered"
    orders = auth_client.get("/gift-orders").json()
    match = next(o for o in orders if o["id"] == body["order_id"])
    assert match["gift_id"] == "cookies-4"


def test_hubspot_renewal_uses_same_recipe_logic(auth_client, stripe_stub):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(
        me["user_id"],
        provider="hubspot",
        recipes=default_stage_recipes(),
    )
    _enable_auto_order(me["user_id"], gift_id="cookies-12")

    with patch("app.main.hs.verify_webhook_secret", return_value=True):
        resp = auth_client.post(
            "/integrations/hubspot/events",
            json={
                "connection_id": connection_id,
                "deal_id": "deal-renewal-1",
                "stage_name": "Renewal",
                "contact_name": "Jordan Buyer",
                "contact_email": "jordan@acme.com",
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "auto_ordered"
    orders = auth_client.get("/gift-orders").json()
    match = next(o for o in orders if o["id"] == body["order_id"])
    assert match["gift_id"] == "cookies-4"


def test_unmatched_stage_ignored_when_recipes_set(auth_client):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(
        me["user_id"],
        recipes=default_stage_recipes(),
    )

    with patch("app.main.sf.verify_webhook_secret", return_value=True), patch(
        "app.integrations.reminders.send_cookie_reminder"
    ) as send_mock:
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006PROSPECTING",
                "stage_name": "Prospecting",
                "contact_name": "Sam",
                "contact_email": "sam@example.com",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    send_mock.assert_not_called()


def test_fallback_single_stage_still_uses_profile_pack(auth_client, stripe_stub):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])
    _enable_auto_order(me["user_id"], gift_id="cookies-12")

    with patch("app.main.sf.verify_webhook_secret", return_value=True):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006FALLBACK1",
                "stage_name": "Demo Completed",
                "contact_name": "Alex Buyer",
                "contact_email": "alex@acme.com",
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "auto_ordered"
    orders = auth_client.get("/gift-orders").json()
    match = next(o for o in orders if o["id"] == body["order_id"])
    assert match["gift_id"] == "cookies-12"


def test_recipe_note_used_when_crm_note_blank(auth_client, stripe_stub):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(
        me["user_id"],
        recipes=[
            {
                "stage_name": "Closed Won",
                "gift_id": "cookies-12",
                "note": "Congrats — cookies on us!",
            }
        ],
    )
    _enable_auto_order(me["user_id"])

    with patch("app.main.sf.verify_webhook_secret", return_value=True):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006NOTE1",
                "stage_name": "Closed Won",
                "contact_name": "Alex Buyer",
                "contact_email": "alex@acme.com",
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    orders = auth_client.get("/gift-orders").json()
    match = next(o for o in orders if o["id"] == body["order_id"])
    assert match["note"] == "Congrats — cookies on us!"


def test_crm_note_wins_over_recipe_note(auth_client, stripe_stub):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(
        me["user_id"],
        recipes=[
            {
                "stage_name": "Closed Won",
                "gift_id": "cookies-12",
                "note": "Recipe fallback note",
            }
        ],
    )
    _enable_auto_order(me["user_id"])

    with patch("app.main.sf.verify_webhook_secret", return_value=True):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006NOTE2",
                "stage_name": "Closed Won",
                "contact_name": "Alex Buyer",
                "contact_email": "alex@acme.com",
                "cookie_note": "Great close — enjoy these!",
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    orders = auth_client.get("/gift-orders").json()
    match = next(o for o in orders if o["id"] == body["order_id"])
    assert match["note"] == "Great close — enjoy these!"


def test_reminder_url_includes_recipe_pack(auth_client):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(
        me["user_id"],
        recipes=default_stage_recipes(),
    )

    sent: list[dict] = []
    with patch("app.main.sf.verify_webhook_secret", return_value=True), patch(
        "app.integrations.reminders.send_cookie_reminder",
        side_effect=lambda **kwargs: sent.append(kwargs),
    ):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006REMIND12",
                "stage_name": "Closed Won",
                "contact_name": "Sam",
                "contact_email": "sam@example.com",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"
    assert "gift_id=cookies-12" in sent[0]["order_url"]


def test_first_connect_seeds_default_recipes(auth_client):
    me = auth_client.get("/auth/me").json()
    db = SessionLocal()
    try:
        row = upsert_connection_from_oauth(
            db,
            user_id=me["user_id"],
            token_payload={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "instance_url": "https://example.my.salesforce.com",
                "id": "https://login.salesforce.com/id/00Dxx/005xx",
            },
        )
        names = [item["stage_name"] for item in row.stage_recipes]
        assert names == ["Demo Completed", "Closed Won", "Renewal"]
        assert row.stage_recipes[1]["gift_id"] == "cookies-12"
    finally:
        db.close()

    listed = auth_client.get("/integrations").json()
    assert listed[0]["stage_recipes"][0]["gift_id"] == "cookies-4"
