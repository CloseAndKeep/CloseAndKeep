"""User-owned API keys for server-to-server access (Option 1 order API).

Keys are shown once at creation. Only a SHA-256 hash is stored. Format:
``cak_<40-char url-safe secret>``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from secrets import token_urlsafe

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ApiKeyModel, UserModel

API_KEY_PREFIX = "cak_"
# token_urlsafe(30) ≈ 40 chars; full key stays under common header limits.
_SECRET_BYTES = 30


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return ``(raw_key, key_prefix, key_hash)``.

    ``key_prefix`` is the leading fragment shown in the UI (never enough to auth).
    """
    secret = token_urlsafe(_SECRET_BYTES)
    raw_key = f"{API_KEY_PREFIX}{secret}"
    key_prefix = raw_key[:12]
    return raw_key, key_prefix, hash_api_key(raw_key)


def create_api_key(
    *,
    owner: UserModel,
    name: str,
    db: Session,
) -> tuple[ApiKeyModel, str]:
    if owner.role == "guest":
        raise HTTPException(
            status_code=403,
            detail="Guest accounts cannot create API keys. Sign up for a full account.",
        )
    raw_key, key_prefix, key_hash = generate_api_key()
    record = ApiKeyModel(
        owner_user_id=owner.id,
        name=name.strip(),
        key_prefix=key_prefix,
        key_hash=key_hash,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, raw_key


def list_api_keys(owner: UserModel, db: Session) -> list[ApiKeyModel]:
    return list(
        db.scalars(
            select(ApiKeyModel)
            .where(ApiKeyModel.owner_user_id == owner.id)
            .order_by(ApiKeyModel.created_at.desc())
        ).all()
    )


def revoke_api_key(*, owner: UserModel, key_id: int, db: Session) -> ApiKeyModel:
    record = db.get(ApiKeyModel, key_id)
    if not record or record.owner_user_id != owner.id:
        raise HTTPException(status_code=404, detail="API key not found.")
    if record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


def authenticate_api_key(raw_key: str, db: Session) -> UserModel | None:
    raw_key = raw_key.strip()
    if not raw_key.startswith(API_KEY_PREFIX) or len(raw_key) < 20:
        return None

    key_hash = hash_api_key(raw_key)
    record = db.scalar(select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash))
    if record is None or record.revoked_at is not None:
        return None

    user = db.get(UserModel, record.owner_user_id)
    if user is None or user.role == "guest":
        return None

    record.last_used_at = datetime.now(UTC)
    db.add(record)
    db.commit()
    return user
