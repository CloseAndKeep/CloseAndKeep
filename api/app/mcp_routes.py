"""HTTP routes for MCP Connect: OAuth metadata/token + Streamable HTTP MCP."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import SessionLocal
from .mcp_oauth import (
    as_issuer,
    authenticate_mcp_bearer,
    authorization_server_metadata,
    build_redirect_url,
    client_label,
    create_auth_code,
    eligibility_error,
    exchange_authorization_code,
    list_user_grants,
    mcp_resource_url,
    normalize_scopes,
    protected_resource_metadata,
    refresh_access_token,
    register_client,
    revoke_grant,
    revoke_token,
    user_eligible_for_mcp,
)
from .mcp_tools import TOOL_DEFINITIONS, call_tool, tool_result_content
from .models import UserModel

router = APIRouter(tags=["mcp"])

MCP_PROTOCOL_VERSION = "2025-03-26"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _www_authenticate() -> str:
    resource = mcp_resource_url()
    return (
        f'Bearer FAKESECRET_k4l5m6n7o8p9q0r1s2t3="{resource}/.well-known/oauth-protected-resource", '
        f'resource="{resource}"'
    )


def _bearer_from_request(request: Request) -> str | None:
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": "unauthorized", "error_description": "Bearer token required"},
        headers={"WWW-Authenticate": _www_authenticate()},
    )


# --- Discovery ---------------------------------------------------------------


@router.get("/.well-known/oauth-protected-resource")
@router.get("/mcp/.well-known/oauth-protected-resource")
def oauth_protected_resource() -> dict:
    return protected_resource_metadata()


@router.get("/.well-known/oauth-authorization-server")
def oauth_authorization_server() -> dict:
    return authorization_server_metadata()


# --- OAuth AS (API host) -----------------------------------------------------


class RegisterRequest(BaseModel):
    client_name: str | None = None
    redirect_uris: list[str] = Field(default_factory=list)
    token_endpoint_auth_method: str | None = "none"
    grant_types: list[str] | None = None
    response_types: list[str] | None = None


@router.post("/oauth/register")
def oauth_register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    return register_client(
        db=db,
        client_name=payload.client_name,
        redirect_uris=payload.redirect_uris,
        token_endpoint_auth_method=payload.token_endpoint_auth_method,
    )


@router.post("/oauth/token")
async def oauth_token(request: Request, db: Session = Depends(get_db)) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
    else:
        body = (await request.body()).decode("utf-8")
        parsed = parse_qs(body, keep_blank_values=True)
        data = {k: v[0] if v else "" for k, v in parsed.items()}

    grant_type = str(data.get("grant_type") or "")
    client_id = str(data.get("client_id") or "")
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id required")

    client_secret = data.get("client_secret")
    resource = data.get("resource")

    if grant_type == "authorization_code":
        return exchange_authorization_code(
            db=db,
            code=str(data.get("code") or ""),
            client_id=client_id,
            redirect_uri=str(data.get("redirect_uri") or ""),
            code_verifier=str(data.get("code_verifier") or ""),
            resource=str(resource) if resource else None,
            client_secret=str(client_secret) if client_secret else None,
        )
    if grant_type == "refresh_token":
        return refresh_access_token(
            db=db,
            refresh_token=str(data.get("refresh_token") or ""),
            client_id=client_id,
            resource=str(resource) if resource else None,
            client_secret=str(client_secret) if client_secret else None,
        )
    raise HTTPException(status_code=400, detail="unsupported_grant_type")


@router.post("/oauth/revoke")
async def oauth_revoke(request: Request, db: Session = Depends(get_db)) -> Response:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
    else:
        body = (await request.body()).decode("utf-8")
        parsed = parse_qs(body, keep_blank_values=True)
        data = {k: v[0] if v else "" for k, v in parsed.items()}
    token = str(data.get("token") or "")
    client_id = data.get("client_id")
    if token:
        revoke_token(
            db=db,
            token=token,
            client_id=str(client_id) if client_id else None,
        )
    return Response(status_code=200)


class ConsentRequest(BaseModel):
    client_id: str
    redirect_uri: str
    scope: str | None = None
    state: str | None = None
    code_challenge: str
    code_challenge_method: str = "S256"
    resource: str | None = None
    client_name: str | None = None


class ConsentResponse(BaseModel):
    redirect_url: str


def mint_consent_redirect(
    payload: ConsentRequest,
    current_user: UserModel,
    db: Session,
) -> ConsentResponse:
    err = eligibility_error(current_user)
    if err:
        raise HTTPException(status_code=403, detail=err)
    resource = payload.resource or mcp_resource_url()
    scopes = normalize_scopes(payload.scope)
    code = create_auth_code(
        db=db,
        user=current_user,
        client_id=payload.client_id,
        redirect_uri=payload.redirect_uri,
        scopes=scopes,
        resource=resource,
        code_challenge=payload.code_challenge,
        code_challenge_method=payload.code_challenge_method or "S256",
    )
    return ConsentResponse(
        redirect_url=build_redirect_url(
            redirect_uri=payload.redirect_uri,
            code=code,
            state=payload.state,
        )
    )


class McpConnectionRow(BaseModel):
    id: int
    client_id: str
    client_label: str
    scopes: str
    created_at: str
    last_used_at: str | None
    access_expires_at: str


def connections_list(current_user: UserModel, db: Session) -> list[McpConnectionRow]:
    if not user_eligible_for_mcp(current_user):
        return []
    rows = []
    for grant in list_user_grants(db, current_user.id):
        rows.append(
            McpConnectionRow(
                id=grant.id,
                client_id=grant.client_id,
                client_label=client_label(db, grant.client_id),
                scopes=grant.scopes,
                created_at=grant.created_at.isoformat(),
                last_used_at=grant.last_used_at.isoformat() if grant.last_used_at else None,
                access_expires_at=grant.access_expires_at.isoformat(),
            )
        )
    return rows


# --- MCP JSON-RPC ------------------------------------------------------------


def _jsonrpc_result(req_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _handle_mcp_message(message: dict, auth, db: Session) -> dict | None:
    if message.get("jsonrpc") != "2.0":
        return _jsonrpc_error(message.get("id"), -32600, "Invalid Request")

    method = message.get("method")
    req_id = message.get("id")
    params = message.get("params") or {}

    # Notifications have no id
    if req_id is None and method:
        return None

    if method == "initialize":
        return _jsonrpc_result(
            req_id,
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "closeandkeep-orders",
                    "version": "1.0.0",
                },
                "instructions": (
                    "CloseAndKeep places post-pitch cookie gifts for sales teams. "
                    "Creating a gift requires draft_gift_order then confirm_gift_order "
                    "with a valid draft_id (server-enforced). "
                    "Cards are paid by the seller on Stripe Checkout; never collect PAN/CVV. "
                    "Only share checkout_url values returned by tools."
                ),
            },
        )

    if method == "ping":
        return _jsonrpc_result(req_id, {})

    if method == "tools/list":
        return _jsonrpc_result(req_id, {"tools": TOOL_DEFINITIONS})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = call_tool(str(name), arguments, auth, db)
            return _jsonrpc_result(
                req_id,
                {
                    "content": tool_result_content(result),
                    "structuredContent": result,
                    "isError": False,
                },
            )
        except HTTPException as exc:
            return _jsonrpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": str(exc.detail)}],
                    "isError": True,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return _jsonrpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": f"Tool error: {exc}"}],
                    "isError": True,
                },
            )

    if method == "resources/list":
        return _jsonrpc_result(req_id, {"resources": []})

    if method == "prompts/list":
        return _jsonrpc_result(req_id, {"prompts": []})

    return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")


@router.api_route("/mcp", methods=["GET", "POST", "DELETE"])
async def mcp_endpoint(request: Request, db: Session = Depends(get_db)):
    raw = _bearer_from_request(request)
    if not raw:
        return _unauthorized()
    auth = authenticate_mcp_bearer(raw, db)
    if auth is None:
        return _unauthorized()

    if request.method == "GET":
        # Minimal probe for hosts that GET the MCP URL after connect.
        return JSONResponse(
            {
                "ok": True,
                "resource": mcp_resource_url(),
                "issuer": as_issuer(),
                "protocolVersion": MCP_PROTOCOL_VERSION,
            }
        )

    if request.method == "DELETE":
        return Response(status_code=204)

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from None

    if isinstance(payload, list):
        responses = []
        for message in payload:
            if not isinstance(message, dict):
                continue
            result = _handle_mcp_message(message, auth, db)
            if result is not None:
                responses.append(result)
        return JSONResponse(responses)

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON-RPC payload")

    # Notification-only
    if payload.get("method") and payload.get("id") is None:
        _handle_mcp_message(payload, auth, db)
        return Response(status_code=202)

    result = _handle_mcp_message(payload, auth, db)
    if result is None:
        return Response(status_code=202)
    return JSONResponse(result)
