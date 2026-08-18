"""Saved cookie-note templates — owner-scoped CRUD."""

from __future__ import annotations

from conftest import signup


def _create_template(client, *, name: str = "After demo", body: str = "Thanks for the time — enjoy these cookies!") -> dict:
    resp = client.post("/note-templates", json={"name": name, "body": body})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_lists_and_round_trips(auth_client):
    created = _create_template(auth_client, name="Closed won", body="Congrats on the close — cookies on us.")
    assert created["name"] == "Closed won"
    assert created["body"] == "Congrats on the close — cookies on us."
    assert created["id"] > 0
    assert created["created_at"]

    listed = auth_client.get("/note-templates")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["id"] == created["id"]
    assert body[0]["name"] == "Closed won"
    assert body[0]["body"] == created["body"]

    detail = auth_client.get(f"/note-templates/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["body"] == created["body"]


def test_list_empty_for_new_user(auth_client):
    resp = auth_client.get("/note-templates")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_requires_authentication(client):
    resp = client.post(
        "/note-templates",
        json={"name": "Nope", "body": "Should not persist."},
    )
    assert resp.status_code == 401


def test_list_requires_authentication(client):
    assert client.get("/note-templates").status_code == 401


def test_create_rejects_blank_name_and_body(auth_client):
    assert auth_client.post("/note-templates", json={"name": "   ", "body": "Hello"}).status_code == 422
    assert auth_client.post("/note-templates", json={"name": "Hello", "body": "   "}).status_code == 422
    assert auth_client.post("/note-templates", json={"name": "Hello"}).status_code == 422


def test_create_rejects_body_over_1000(auth_client):
    resp = auth_client.post(
        "/note-templates",
        json={"name": "Too long", "body": "x" * 1001},
    )
    assert resp.status_code == 422


def test_create_strips_name_and_body(auth_client):
    created = _create_template(auth_client, name="  After demo  ", body="  Thanks!  ")
    assert created["name"] == "After demo"
    assert created["body"] == "Thanks!"


def test_update_own_template(auth_client):
    created = _create_template(auth_client)
    resp = auth_client.patch(
        f"/note-templates/{created['id']}",
        json={"name": "Renewal", "body": "Great year — a small thank-you."},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["id"] == created["id"]
    assert updated["name"] == "Renewal"
    assert updated["body"] == "Great year — a small thank-you."


def test_update_partial_name_only(auth_client):
    created = _create_template(auth_client, body="Keep this body.")
    resp = auth_client.patch(f"/note-templates/{created['id']}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    assert resp.json()["body"] == "Keep this body."


def test_update_rejects_blank_fields(auth_client):
    created = _create_template(auth_client)
    assert auth_client.patch(f"/note-templates/{created['id']}", json={"name": "  "}).status_code == 422
    assert auth_client.patch(f"/note-templates/{created['id']}", json={"body": "  "}).status_code == 422


def test_delete_own_template(auth_client):
    created = _create_template(auth_client)
    deleted = auth_client.delete(f"/note-templates/{created['id']}")
    assert deleted.status_code == 204
    assert auth_client.get("/note-templates").json() == []
    assert auth_client.delete(f"/note-templates/{created['id']}").status_code == 404


def test_missing_template_returns_404(auth_client):
    assert auth_client.get("/note-templates/999999").status_code == 404
    assert auth_client.patch("/note-templates/999999", json={"name": "X"}).status_code == 404
    assert auth_client.delete("/note-templates/999999").status_code == 404


def test_list_and_mutate_are_scoped_to_owner(make_client):
    owner = signup(make_client(), "owner-notes@example.com")
    other = signup(make_client(), "other-notes@example.com")
    created = _create_template(owner, name="Owned", body="Only I should see this.")

    assert len(owner.get("/note-templates").json()) == 1
    assert other.get("/note-templates").json() == []
    assert other.get(f"/note-templates/{created['id']}").status_code == 404
    assert other.patch(f"/note-templates/{created['id']}", json={"name": "Stolen"}).status_code == 404
    assert other.delete(f"/note-templates/{created['id']}").status_code == 404

    still = owner.get("/note-templates").json()
    assert len(still) == 1
    assert still[0]["name"] == "Owned"


def test_cap_at_20_templates(auth_client):
    for i in range(20):
        _create_template(auth_client, name=f"Note {i}", body=f"Body {i}")
    resp = auth_client.post("/note-templates", json={"name": "One more", "body": "Nope."})
    assert resp.status_code == 400
    assert "20" in resp.json()["detail"]
    assert len(auth_client.get("/note-templates").json()) == 20
