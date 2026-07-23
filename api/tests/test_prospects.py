"""Prospect tests — Test.MD §4 (create / validation / list scope)."""

from __future__ import annotations

from conftest import create_prospect, signup


def test_create_persists_with_owner_and_fields(auth_client):
    body = create_prospect(auth_client, name="Pat Client", email="pat@example.com")
    assert body["name"] == "Pat Client"
    assert body["email"] == "pat@example.com"
    assert body["deal_status"] == "open"

    # Round-trips through detail read.
    detail = auth_client.get(f"/prospects/{body['id']}")
    assert detail.status_code == 200
    assert detail.json() == body


def test_create_requires_authentication(client):
    resp = client.post(
        "/prospects",
        json={
            "name": "X",
            "email": "x@example.com",
            "deal_status": "open",
        },
    )
    assert resp.status_code == 401


def test_create_rejects_invalid_email(auth_client):
    resp = auth_client.post(
        "/prospects",
        json={
            "name": "Bad Email",
            "email": "nope",
            "deal_status": "open",
        },
    )
    assert resp.status_code == 422


def test_create_rejects_missing_required_fields(auth_client):
    resp = auth_client.post("/prospects", json={"name": "Only Name"})
    assert resp.status_code == 422


def test_create_rejects_invalid_deal_status(auth_client):
    resp = auth_client.post(
        "/prospects",
        json={
            "name": "Bad Status",
            "email": "bad@example.com",
            "deal_status": "maybe",
        },
    )
    assert resp.status_code == 422


def test_create_normalizes_email(auth_client):
    body = create_prospect(auth_client, email="UPPER@Example.com")
    assert body["email"] == "upper@example.com"


def test_list_is_scoped_to_owner(make_client):
    owner = signup(make_client(), "owner@example.com")
    other = signup(make_client(), "other@example.com")

    create_prospect(owner, name="Owned", email="owned@example.com")

    assert len(owner.get("/prospects").json()) == 1
    # Another user sees none of the owner's prospects.
    assert other.get("/prospects").json() == []


def test_update_own_prospect(auth_client):
    body = create_prospect(auth_client)
    resp = auth_client.patch(
        f"/prospects/{body['id']}",
        json={"deal_status": "won", "name": "Dana Global"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["deal_status"] == "won"
    assert updated["name"] == "Dana Global"


def test_dashboard_summary_matches_prospect_outcomes(auth_client):
    create_prospect(auth_client, name="A", email="a@example.com", deal_status="open")
    create_prospect(auth_client, name="B", email="b@example.com", deal_status="won")
    create_prospect(auth_client, name="C", email="c@example.com", deal_status="lost")
    create_prospect(auth_client, name="D", email="d@example.com", deal_status="open")

    summary = auth_client.get("/dashboard/summary").json()
    assert summary == {"open_deals": 2, "won": 1, "lost": 1, "total_prospects": 4}


def test_dashboard_summary_empty_for_new_user(auth_client):
    summary = auth_client.get("/dashboard/summary").json()
    assert summary == {"open_deals": 0, "won": 0, "lost": 0, "total_prospects": 0}


def test_dashboard_summary_is_scoped(make_client):
    owner = signup(make_client(), "owner@example.com")
    other = signup(make_client(), "other@example.com")
    create_prospect(owner, name="Owned", email="owned@example.com", deal_status="won")

    assert other.get("/dashboard/summary").json()["total_prospects"] == 0
    assert owner.get("/dashboard/summary").json()["won"] == 1


def test_get_missing_prospect_returns_404(auth_client):
    assert auth_client.get("/prospects/999999").status_code == 404


def test_update_rejects_invalid_deal_status(auth_client):
    body = create_prospect(auth_client)
    resp = auth_client.patch(
        f"/prospects/{body['id']}",
        json={"deal_status": "maybe"},
    )
    assert resp.status_code == 422
