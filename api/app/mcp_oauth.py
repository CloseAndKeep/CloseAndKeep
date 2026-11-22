"""MCP Connect OAuth 2.1 authorization server helpers (PKCE, DCR, hashed tokens)."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from urllib.parse import urlencode, urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import (
    McpOAuthAuthCodeModel,
    McpOAuthClientModel,
    McpOAuthTokenModel,
    UserModel,
)

ACCESS_TOKEN_PREFIX = "mct_"
REFRESH_TOKEN_PREFIX = "mcr_"
AUTH_CODE_TTL = timedelta(minutes=10)
ACCESS_TOKEN_TTL = timedelta(hours=1)
REFRESH_TOKEN_TTL = timedelta(days=30)
DRAFT_TTL = timedelta(minutes=10)

SCOPES_SUPPORTED = ("orders:read", "orders:write")
DEFAULT_SCOPES = "orders:read orders:write"


def mcp_resource_url() -> str:
    return f"{settings.api_base_url.rstrip('/')}/mcp"


def as_issuer() -> str:
    return settings.api_base_url.rstrip("/")


def authorization_endpoint() -> str:
    return f"{settings.web_base_url.rstrip('/')}/oauth/mcp/authorize"


def hash_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    """SQLite often returns naive datetimes; normalize before compare."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def user_eligible_for_mcp(user: UserModel) -> bool:
    if user.role == "guest":
        return False
    return user.email_verified_at is not None


def eligibility_error(user: UserModel) -> str | None:
    if user.role == "guest":
        return "Guest accounts cannot connect AI. Sign up for a full account and verify your email."
    if user.email_verified_at is None:
        return "Verify your email before connecting an AI."
    return None


def normalize_scopes(scope: str | None) -> str:
    if not scope or not scope.strip():
        return DEFAULT_SCOPES
    requested = {part for part in scope.split() if part}
    unknown = requested - set(SCOPES_SUPPORTED)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported scope(s): {', '.join(sorted(unknown))}",
        )
    # Always grant both for v1 once any valid scope is requested.
    return DEFAULT_SCOPES


def _is_loopback(host: str) -> bool:
    return host in {"localhost", "127.0.0.1", "[::1]", "::1"}


# Claude hosted surfaces (directory + custom connectors).
CLAUDE_CALLBACK_URIS = (
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
)


def redirect_uri_allowed(client: McpOAuthClientModel, redirect_uri: str) -> bool:
    registered = list(client.redirect_uris or [])
    if redirect_uri in registered:
        return True
    if redirect_uri in CLAUDE_CALLBACK_URIS:
        return True
    # Claude Desktop / Code: port-agnostic localhost / 127.0.0.1 match.
    try:
        parsed = urlparse(redirect_uri)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if not _is_loopback(host):
        return False
    for allowed in registered:
        try:
            other = urlparse(allowed)
        except Exception:
            continue
        other_host = (other.hostname or "").lower()
        if not _is_loopback(other_host):
            continue
        if other.path == parsed.path and other.scheme == parsed.scheme:
            return True
    return False


def protected_resource_metadata() -> dict:
    resource = mcp_resource_url()
    return {
        "resource": resource,
        "authorization_servers": [as_issuer()],
        "scopes_supported": list(SCOPES_SUPPORTED),
        "resource_documentation": f"{settings.web_base_url.rstrip('/')}/developers/ai",
        "bearer_methods_supported": ["header"],
    }


def authorization_server_metadata() -> dict:
    issuer = as_issuer()
    return {
        "issuer": issuer,
        "authorization_endpoint": authorization_endpoint(),
        "token_endpoint": f"{issuer}/oauth/token",
        "registration_endpoint": f"{issuer}/oauth/register",
        "revocation_endpoint": f"{issuer}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "scopes_supported": list(SCOPES_SUPPORTED),
        "client_id_metadata_document_supported": True,
        "authorization_response_iss_parameter_supported": True,
    }


def register_client(
    *,
    db: Session,
    client_name: str | None,
    redirect_uris: list[str],
    token_endpoint_auth_method: str | None = None,
) -> dict:
    if not redirect_uris:
        raise HTTPException(status_code=400, detail="redirect_uris required")
    for uri in redirect_uris:
        parsed = urlparse(uri)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail=f"Invalid redirect_uri: {uri}")
    method = (token_endpoint_auth_method or "none").strip() or "none"
    if method not in {"none", "client_secret_post"}:
        raise HTTPException(status_code=400, detail="Unsupported token_endpoint_auth_method")

    client_id = f"mcp_{token_urlsafe(24)}"
    client_secret: str | None = None
    secret_hash: str | None = None
    if method == "client_secret_post":
        client_secret = token_urlsafe(32)
        secret_hash = hash_secret(client_secret)

    record = McpOAuthClientModel(
        client_id=client_id,
        client_secret_hash=secret_hash,
        client_name=(client_name or "MCP client").strip()[:255] or "MCP client",
        redirect_uris=redirect_uris,
        token_endpoint_auth_method=method,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    body: dict = {
        "client_id": record.client_id,
        "client_name": record.client_name,
        "redirect_uris": record.redirect_uris,
        "token_endpoint_auth_method": record.token_endpoint_auth_method,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }
    if client_secret:
        body["client_secret"] = client_secret
    return body


def get_client(db: Session, client_id: str) -> McpOAuthClientModel | None:
    return db.scalar(
        select(McpOAuthClientModel).where(McpOAuthClientModel.client_id == client_id)
    )


def ensure_client(
    db: Session,
    *,
    client_id: str,
    redirect_uri: str | None = None,
) -> McpOAuthClientModel:
    """Resolve a registered client, or accept CIMD-style https client_id URLs."""
    existing = get_client(db, client_id)
    if existing:
        return existing

    # Client ID Metadata Document: client_id is an https URL the host hosts.
    if client_id.startswith("https://"):
        uris = [redirect_uri] if redirect_uri else []
        record = McpOAuthClientModel(
            client_id=client_id,
            client_secret_hash=None,
            client_name=client_id[:255],
            redirect_uris=uris,
            token_endpoint_auth_method="none",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    raise HTTPException(status_code=400, detail="Unknown client_id")


def create_auth_code(
    *,
    db: Session,
    user: UserModel,
    client_id: str,
    redirect_uri: str,
    scopes: str,
    resource: str,
    code_challenge: str,
    code_challenge_method: str,
) -> str:
    if code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail="Only S256 PKCE is supported")
    if resource.rstrip("/") != mcp_resource_url().rstrip("/"):
        raise HTTPException(
            status_code=400,
            detail=f"resource must be {mcp_resource_url()}",
        )
    err = eligibility_error(user)
    if err:
        raise HTTPException(status_code=403, detail=err)

    client = ensure_client(db, client_id=client_id, redirect_uri=redirect_uri)
    if not redirect_uri_allowed(client, redirect_uri):
        # For CIMD clients, allow first-seen redirect and remember it.
        if client.client_id.startswith("https://"):
            uris = list(client.redirect_uris or [])
            if redirect_uri not in uris:
                uris.append(redirect_uri)
                client.redirect_uris = uris
                db.add(client)
                db.commit()
        if not redirect_uri_allowed(client, redirect_uri):
            raise HTTPException(status_code=400, detail="redirect_uri not registered")

    raw_code = token_urlsafe(32)
    record = McpOAuthAuthCodeModel(
        code_hash=hash_secret(raw_code),
        client_id=client.client_id,
        user_id=user.id,
        redirect_uri=redirect_uri,
        scopes=normalize_scopes(scopes),
        resource=mcp_resource_url(),
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        expires_at=datetime.now(UTC) + AUTH_CODE_TTL,
    )
    db.add(record)
    db.commit()
    return raw_code


def build_redirect_url(
    *,
    redirect_uri: str,
    code: str,
    state: str | None,
) -> str:
    params = {"code": code, "iss": as_issuer()}
    if state:
        params["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return f"{redirect_uri}{sep}{urlencode(params)}"


def _verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return computed == code_challenge


def _issue_token_pair(
    *,
    db: Session,
    user_id: int,
    client_id: str,
    scopes: str,
    resource: str,
) -> dict:
    access_raw = f"{ACCESS_TOKEN_PREFIX}{token_urlsafe(32)}"
    refresh_raw = f"{REFRESH_TOKEN_PREFIX}{token_urlsafe(32)}"
    now = datetime.now(UTC)
    record = McpOAuthTokenModel(
        access_token_hash=hash_secret(access_raw),
        refresh_token_hash=hash_secret(refresh_raw),
        client_id=client_id,
        user_id=user_id,
        scopes=scopes,
        resource=resource,
        access_expires_at=now + ACCESS_TOKEN_TTL,
        refresh_expires_at=now + REFRESH_TOKEN_TTL,
    )
    db.add(record)
    db.commit()
    return {
        "access_token": access_raw,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()),
        "refresh_token": refresh_raw,
        "scope": scopes,
        "resource": resource,
    }


def exchange_authorization_code(
    *,
    db: Session,
    code: str,
    client_id: str,
    redirect_uri: str,
    code_verifier: str,
    resource: str | None,
    client_secret: str | None = None,
) -> dict:
    client = get_client(db, client_id) or ensure_client(
        db, client_id=client_id, redirect_uri=redirect_uri
    )
    if client.token_endpoint_auth_method == "client_secret_post":
        if not client_secret or not client.client_secret_hash:
            raise HTTPException(status_code=401, detail="invalid_client")
        if hash_secret(client_secret) != client.client_secret_hash:
            raise HTTPException(status_code=401, detail="invalid_client")

    record = db.scalar(
        select(McpOAuthAuthCodeModel).where(
            McpOAuthAuthCodeModel.code_hash == hash_secret(code)
        )
    )
    if record is None:
        raise HTTPException(status_code=400, detail="invalid_grant")
    if record.used_at is not None:
        raise HTTPException(status_code=400, detail="invalid_grant")
    if _as_utc(record.expires_at) <= datetime.now(UTC):
        raise HTTPException(status_code=400, detail="invalid_grant")
    if record.client_id != client.client_id:
        raise HTTPException(status_code=400, detail="invalid_grant")
    if record.redirect_uri != redirect_uri:
        raise HTTPException(status_code=400, detail="invalid_grant")
    if not _verify_pkce(code_verifier, record.code_challenge):
        raise HTTPException(status_code=400, detail="invalid_grant")

    expected_resource = mcp_resource_url()
    if resource and resource.rstrip("/") != expected_resource.rstrip("/"):
        raise HTTPException(status_code=400, detail="invalid_resource")
    if record.resource.rstrip("/") != expected_resource.rstrip("/"):
        raise HTTPException(status_code=400, detail="invalid_resource")

    user = db.get(UserModel, record.user_id)
    if user is None or not user_eligible_for_mcp(user):
        raise HTTPException(status_code=400, detail="invalid_grant")

    record.used_at = datetime.now(UTC)
    db.add(record)
    db.commit()

    return _issue_token_pair(
        db=db,
        user_id=user.id,
        client_id=client.client_id,
        scopes=record.scopes,
        resource=expected_resource,
    )


def refresh_access_token(
    *,
    db: Session,
    refresh_token: str,
    client_id: str,
    resource: str | None = None,
    client_secret: str | None = None,
) -> dict:
    client = get_client(db, client_id)
    if client is None:
        raise HTTPException(status_code=401, detail="invalid_client")
    if client.token_endpoint_auth_method == "client_secret_post":
        if not client_secret or hash_secret(client_secret) != client.client_secret_hash:
            raise HTTPException(status_code=401, detail="invalid_client")

    record = db.scalar(
        select(McpOAuthTokenModel).where(
            McpOAuthTokenModel.refresh_token_hash == hash_secret(refresh_token)
        )
    )
    if record is None or record.revoked_at is not None:
        raise HTTPException(status_code=400, detail="invalid_grant")
    if _as_utc(record.refresh_expires_at) <= datetime.now(UTC):
        raise HTTPException(status_code=400, detail="invalid_grant")
    if record.client_id != client.client_id:
        raise HTTPException(status_code=400, detail="invalid_grant")

    expected = mcp_resource_url()
    if resource and resource.rstrip("/") != expected.rstrip("/"):
        raise HTTPException(status_code=400, detail="invalid_resource")

    # Rotate: revoke old pair, issue new.
    record.revoked_at = datetime.now(UTC)
    db.add(record)
    db.commit()

    return _issue_token_pair(
        db=db,
        user_id=record.user_id,
        client_id=record.client_id,
        scopes=record.scopes,
        resource=expected,
    )


def revoke_token(*, db: Session, token: str, client_id: str | None = None) -> None:
    token = token.strip()
    now = datetime.now(UTC)
    access = db.scalar(
        select(McpOAuthTokenModel).where(
            McpOAuthTokenModel.access_token_hash == hash_secret(token)
        )
    )
    refresh = db.scalar(
        select(McpOAuthTokenModel).where(
            McpOAuthTokenModel.refresh_token_hash == hash_secret(token)
        )
    )
    record = access or refresh
    if record is None:
        return
    if client_id and record.client_id != client_id:
        return
    if record.revoked_at is None:
        record.revoked_at = now
        db.add(record)
        db.commit()


@dataclass
class McpAuthContext:
    user: UserModel
    scopes: set[str]
    client_id: str | None
    via: str  # oauth | api_key


def authenticate_mcp_bearer(raw_token: str, db: Session) -> McpAuthContext | None:
    raw_token = raw_token.strip()
    if raw_token.startswith(ACCESS_TOKEN_PREFIX):
        record = db.scalar(
            select(McpOAuthTokenModel).where(
                McpOAuthTokenModel.access_token_hash == hash_secret(raw_token)
            )
        )
        if record is None or record.revoked_at is not None:
            return None
        if _as_utc(record.access_expires_at) <= datetime.now(UTC):
            return None
        if record.resource.rstrip("/") != mcp_resource_url().rstrip("/"):
            return None
        user = db.get(UserModel, record.user_id)
        if user is None or not user_eligible_for_mcp(user):
            return None
        record.last_used_at = datetime.now(UTC)
        db.add(record)
        db.commit()
        return McpAuthContext(
            user=user,
            scopes=set(record.scopes.split()),
            client_id=record.client_id,
            via="oauth",
        )

    # API key fallback (cak_…)
    from .api_keys import authenticate_api_key

    user = authenticate_api_key(raw_token, db)
    if user is None or not user_eligible_for_mcp(user):
        return None
    return McpAuthContext(
        user=user,
        scopes=set(SCOPES_SUPPORTED),
        client_id=None,
        via="api_key",
    )


def list_user_grants(db: Session, user_id: int) -> list[McpOAuthTokenModel]:
    rows = list(
        db.scalars(
            select(McpOAuthTokenModel)
            .where(
                McpOAuthTokenModel.user_id == user_id,
                McpOAuthTokenModel.revoked_at.is_(None),
            )
            .order_by(McpOAuthTokenModel.created_at.desc())
        ).all()
    )
    now = datetime.now(UTC)
    return [row for row in rows if _as_utc(row.refresh_expires_at) > now]


def revoke_grant(*, db: Session, user: UserModel, token_id: int) -> None:
    record = db.get(McpOAuthTokenModel, token_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Connection not found.")
    if record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        db.add(record)
        db.commit()


def client_label(db: Session, client_id: str) -> str:
    client = get_client(db, client_id)
    if client and client.client_name:
        return client.client_name
    lower = client_id.lower()
    if "claude" in lower or "anthropic" in lower:
        return "Claude"
    if "openai" in lower or "chatgpt" in lower:
        return "ChatGPT"
    if "cursor" in lower:
        return "Cursor"
    if client_id.startswith("https://"):
        return client_id
    return client_id[:48]
