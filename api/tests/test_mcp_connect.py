"""MCP Connect: OAuth PKCE, audience binding, draft→confirm tools."""

from __future__ import annotations

import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest


def _pkce_pair() -> tuple[str, str]:
    verifier = "a" * 64
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    return verifier, challenge


def test_oauth_metadata(client):
    prm = client.get("/.well-known/oauth-protected-resource")
    assert prm.status_code == 200
    assert prm.json()["resource"].endswith("/mcp")

    asm = client.get("/.well-known/oauth-authorization-server")
    assert asm.status_code == 200
    body = asm.json()
    assert "authorization_endpoint" in body
    assert body["authorization_endpoint"].endswith("/oauth/mcp/authorize")
    assert body["token_endpoint"].endswith("/oauth/token")
    assert "S256" in body["code_challenge_methods_supported"]
    assert body.get("client_id_metadata_document_supported") is True


def test_mcp_requires_bearer(client):
    res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert res.status_code == 401
    assert "WWW-Authenticate" in res.headers


def test_dcr_register(client):
    res = client.post(
        "/oauth/register",
        json={
            "client_name": "Test Claude",
            "redirect_uris": ["http://127.0.0.1:8787/callback"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["client_id"].startswith("mcp_")
    assert body["redirect_uris"] == ["http://127.0.0.1:8787/callback"]


def test_pkce_consent_token_and_tools(auth_client, client, stripe_stub):
    reg = client.post(
        "/oauth/register",
        json={
            "client_name": "Cursor Test",
            "redirect_uris": ["http://localhost:8787/callback"],
            "token_endpoint_auth_method": "none",
        },
    )
    client_id = reg.json()["client_id"]
    verifier, challenge = _pkce_pair()
    resource = client.get("/.well-known/oauth-protected-resource").json()["resource"]

    consent = auth_client.post(
        "/oauth/mcp/consent",
        json={
            "client_id": client_id,
            "redirect_uri": "http://localhost:8787/callback",
            "scope": "orders:read orders:write",
            "state": "xyz",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": resource,
        },
    )
    assert consent.status_code == 200, consent.text
    redirect_url = consent.json()["redirect_url"]
    qs = parse_qs(urlparse(redirect_url).query)
    code = qs["code"][0]
    assert qs["state"] == ["xyz"]
    assert "iss" in qs

    token_res = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:8787/callback",
            "client_id": client_id,
            "code_verifier": verifier,
            "resource": resource,
        },
    )
    assert token_res.status_code == 200, token_res.text
    tokens = token_res.json()
    assert tokens["access_token"].startswith("mct_")
    assert tokens["resource"] == resource

    # Wrong audience resource on refresh-style check: craft token with wrong resource rejected
    # by minting another code and exchanging with wrong resource should fail.
    verifier2, challenge2 = _pkce_pair()
    consent2 = auth_client.post(
        "/oauth/mcp/consent",
        json={
            "client_id": client_id,
            "redirect_uri": "http://localhost:8787/callback",
            "code_challenge": challenge2,
            "code_challenge_method": "S256",
            "resource": resource,
        },
    )
    code2 = parse_qs(urlparse(consent2.json()["redirect_url"]).query)["code"][0]
    bad = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code2,
            "redirect_uri": "http://localhost:8787/callback",
            "client_id": client_id,
            "code_verifier": verifier2,
            "resource": "https://evil.example/mcp",
        },
    )
    assert bad.status_code == 400

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    init = client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert init.status_code == 200
    assert init.json()["result"]["serverInfo"]["name"] == "closeandkeep-orders"

    tools = client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )
    names = {t["name"] for t in tools.json()["result"]["tools"]}
    assert "draft_gift_order" in names
    assert "confirm_gift_order" in names

    # Create prospect + draft + confirm via tools
    created = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "create_prospect",
                "arguments": {
                    "name": "Dana Buyer",
                    "email": "dana@acme.example",
                },
            },
        },
    )
    assert created.status_code == 200
    prospect_id = created.json()["result"]["structuredContent"]["id"]

    draft = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "draft_gift_order",
                "arguments": {
                    "prospect_id": prospect_id,
                    "gift_id": "cookies-4",
                    "recipient_name": "Dana Buyer",
                    "note": "Thanks for the demo!",
                    "request_recipient_address": True,
                    "recipient_email": "dana@acme.example",
                },
            },
        },
    )
    assert draft.status_code == 200, draft.text
    draft_body = draft.json()["result"]
    assert draft_body["isError"] is False
    draft_id = draft_body["structuredContent"]["draft_id"]

    # Confirm without draft should fail
    bad_confirm = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "confirm_gift_order", "arguments": {"draft_id": "drf_nope"}},
        },
    )
    assert bad_confirm.json()["result"]["isError"] is True

    confirm = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "confirm_gift_order",
                "arguments": {"draft_id": draft_id},
            },
        },
    )
    assert confirm.status_code == 200, confirm.text
    conf = confirm.json()["result"]
    assert conf["isError"] is False, conf
    assert conf["structuredContent"]["checkout_url"]
    assert conf["structuredContent"]["order"]["id"]

    # Reuse draft fails
    reuse = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "confirm_gift_order",
                "arguments": {"draft_id": draft_id},
            },
        },
    )
    assert reuse.json()["result"]["isError"] is True

    # Connections list + disconnect
    conns = auth_client.get("/mcp/connections")
    assert conns.status_code == 200
    assert len(conns.json()) >= 1
    token_id = conns.json()[0]["id"]
    deleted = auth_client.delete(f"/mcp/connections/{token_id}")
    assert deleted.status_code == 204

    after = client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 8, "method": "tools/list"},
    )
    assert after.status_code == 401


def test_guest_cannot_consent(client, make_client):
    # Guest login
    guest = client.post("/auth/guest")
    assert guest.status_code == 200
    reg = client.post(
        "/oauth/register",
        json={
            "client_name": "X",
            "redirect_uris": ["http://127.0.0.1:9/cb"],
            "token_endpoint_auth_method": "none",
        },
    )
    _, challenge = _pkce_pair()
    resource = client.get("/.well-known/oauth-protected-resource").json()["resource"]
    consent = client.post(
        "/oauth/mcp/consent",
        json={
            "client_id": reg.json()["client_id"],
            "redirect_uri": "http://127.0.0.1:9/cb",
            "code_challenge": challenge,
            "resource": resource,
        },
    )
    assert consent.status_code == 403


def test_api_key_can_call_mcp(auth_client, make_client, stripe_stub):
    created = auth_client.post("/api-keys", json={"name": "MCP key"})
    assert created.status_code == 201
    raw = created.json()["api_key"]
    mcp_client = make_client()
    headers = {"Authorization": f"Bearer {raw}"}
    res = mcp_client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert res.status_code == 200
    assert "tools" in res.json()["result"]
