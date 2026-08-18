"""Post-connect Check setup — Cookie fields and trigger stage (mocked CRM HTTP)."""

from __future__ import annotations

from unittest.mock import patch

from conftest import signup
from app.db import SessionLocal
from app.integrations.crypto import encrypt_token
from app.models import IntegrationConnectionModel

SF_COOKIE_FIELDS = (
    "Cookie_Note__c",
    "Cookie_Company__c",
    "Cookie_Street__c",
    "Cookie_City__c",
    "Cookie_State__c",
    "Cookie_Postal_Code__c",
)

HS_COOKIE_PROPS = (
    "cookie_note",
    "cookie_company",
    "cookie_street",
    "cookie_city",
    "cookie_state",
    "cookie_postal_code",
)


def _seed_connection(
    user_id: int,
    *,
    provider: str,
    stage: str = "Demo Completed",
    with_token: bool = True,
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
            access_token_encrypted=encrypt_token("access-token") if with_token else None,
            refresh_token_encrypted=encrypt_token("refresh-token") if with_token else None,
            trigger_stage_name=stage,
            enabled=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _sf_describe(*, fields: list[str], stages: list[str]) -> dict:
    describe_fields = [{"name": name} for name in fields]
    describe_fields.append(
        {
            "name": "StageName",
            "picklistValues": [
                {"value": label, "label": label, "active": True} for label in stages
            ],
        }
    )
    return {"fields": describe_fields}


def _hs_properties(names: list[str]) -> dict:
    return {"results": [{"name": name} for name in names]}


def _hs_pipelines(stages: list[str]) -> dict:
    return {
        "results": [
            {
                "stages": [
                    {"id": f"stage-{index}", "label": label}
                    for index, label in enumerate(stages)
                ]
            }
        ]
    }


def _configure_salesforce(monkeypatch) -> None:
    monkeypatch.setattr("app.integrations.salesforce.settings.salesforce_client_id", "sf-id")
    monkeypatch.setattr(
        "app.integrations.salesforce.settings.salesforce_client_secret", "sf-secret"
    )


def _configure_hubspot(monkeypatch) -> None:
    monkeypatch.setattr("app.integrations.hubspot.settings.hubspot_client_id", "hs-id")
    monkeypatch.setattr(
        "app.integrations.hubspot.settings.hubspot_client_secret", "hs-secret"
    )


def test_salesforce_check_setup_ok(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"], provider="salesforce")
    _configure_salesforce(monkeypatch)

    with patch(
        "app.integrations.salesforce.salesforce_request",
        return_value=_sf_describe(fields=list(SF_COOKIE_FIELDS), stages=["Demo Completed"]),
    ) as request_mock:
        resp = auth_client.post("/integrations/salesforce/check-setup")

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "salesforce"
    assert body["ok"] is True
    assert body["missing_fields"] == []
    assert body["unknown_stage"] is False
    assert body["trigger_stage_name"] == "Demo Completed"
    assert any("Setup looks good" in message for message in body["messages"])
    request_mock.assert_called_once()
    assert request_mock.call_args.args[2] == "GET"
    assert request_mock.call_args.args[3] == "/services/data/v59.0/sobjects/Opportunity/describe"


def test_salesforce_check_setup_missing_fields_and_unknown_stage(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"], provider="salesforce", stage="Demo Completed")
    _configure_salesforce(monkeypatch)

    with patch(
        "app.integrations.salesforce.salesforce_request",
        return_value=_sf_describe(
            fields=["Cookie_Company__c", "Cookie_Address__c"],
            stages=["Prospecting"],
        ),
    ):
        resp = auth_client.post("/integrations/salesforce/check-setup")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "Cookie_Note__c" in body["missing_fields"]
    assert "Cookie_Street__c" in body["missing_fields"]
    assert body["unknown_stage"] is True
    assert any("Cookie_Note__c is missing" in message for message in body["messages"])
    assert any("Demo Completed" in message and "not found" in message for message in body["messages"])
    assert any("Cookie_Address__c is present as a fallback" in message for message in body["messages"])


def test_salesforce_check_setup_requires_config(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"], provider="salesforce")
    monkeypatch.setattr("app.integrations.salesforce.settings.salesforce_client_id", "")
    monkeypatch.setattr("app.integrations.salesforce.settings.salesforce_client_secret", "")
    resp = auth_client.post("/integrations/salesforce/check-setup")
    assert resp.status_code == 503


def test_salesforce_check_setup_requires_connection(auth_client, monkeypatch):
    _configure_salesforce(monkeypatch)
    resp = auth_client.post("/integrations/salesforce/check-setup")
    assert resp.status_code == 404


def test_salesforce_check_setup_requires_token(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"], provider="salesforce", with_token=False)
    _configure_salesforce(monkeypatch)
    resp = auth_client.post("/integrations/salesforce/check-setup")
    assert resp.status_code == 401


def test_salesforce_check_setup_unauthenticated(client, monkeypatch):
    _configure_salesforce(monkeypatch)
    resp = client.post("/integrations/salesforce/check-setup")
    assert resp.status_code == 401


def test_hubspot_check_setup_ok(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"], provider="hubspot")
    _configure_hubspot(monkeypatch)

    def _fake_request(_connection, _db, method, path, **_kwargs):
        assert method == "GET"
        if path == "/crm/v3/properties/deals":
            return _hs_properties(list(HS_COOKIE_PROPS))
        if path == "/crm/v3/pipelines/deals":
            return _hs_pipelines(["Appointments scheduled", "Demo Completed"])
        raise AssertionError(path)

    with patch("app.integrations.hubspot.hubspot_request", side_effect=_fake_request):
        resp = auth_client.post("/integrations/hubspot/check-setup")

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "hubspot"
    assert body["ok"] is True
    assert body["missing_fields"] == []
    assert body["unknown_stage"] is False
    assert any("Setup looks good" in message for message in body["messages"])


def test_hubspot_check_setup_missing_fields_and_unknown_stage(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"], provider="hubspot", stage="Demo Completed")
    _configure_hubspot(monkeypatch)

    def _fake_request(_connection, _db, method, path, **_kwargs):
        if path == "/crm/v3/properties/deals":
            return _hs_properties(["cookie_company", "cookie_address"])
        if path == "/crm/v3/pipelines/deals":
            return _hs_pipelines(["Qualified"])
        raise AssertionError(path)

    with patch("app.integrations.hubspot.hubspot_request", side_effect=_fake_request):
        resp = auth_client.post("/integrations/hubspot/check-setup")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "cookie_note" in body["missing_fields"]
    assert "cookie_street" in body["missing_fields"]
    assert body["unknown_stage"] is True
    assert any("cookie_note is missing" in message for message in body["messages"])
    assert any("cookie_address is present as a fallback" in message for message in body["messages"])


def test_hubspot_check_setup_requires_config(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"], provider="hubspot")
    monkeypatch.setattr("app.integrations.hubspot.settings.hubspot_client_id", "")
    monkeypatch.setattr("app.integrations.hubspot.settings.hubspot_client_secret", "")
    resp = auth_client.post("/integrations/hubspot/check-setup")
    assert resp.status_code == 503


def test_hubspot_check_setup_requires_token(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"], provider="hubspot", with_token=False)
    _configure_hubspot(monkeypatch)
    resp = auth_client.post("/integrations/hubspot/check-setup")
    assert resp.status_code == 401


def test_guest_cannot_check_setup(client, monkeypatch):
    _configure_salesforce(monkeypatch)
    client.post("/auth/guest")
    resp = client.post("/integrations/salesforce/check-setup")
    assert resp.status_code == 403


def test_check_setup_scoped_to_owner(make_client, monkeypatch):
    _configure_salesforce(monkeypatch)
    owner = signup(make_client(), "check-owner@example.com")
    other = signup(make_client(), "check-other@example.com")
    owner_id = owner.get("/auth/me").json()["user_id"]
    _seed_connection(owner_id, provider="salesforce")

    assert other.post("/integrations/salesforce/check-setup").status_code == 404
