"""MCP tool implementations for CloseAndKeep gift orders (draft → confirm)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from secrets import token_urlsafe
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from .config import GIFT_CATALOG, is_known_gift, settings
from .gift_notes import GIFT_NOTE_MAX_LENGTH
from .mcp_oauth import DRAFT_TTL, McpAuthContext
from .models import GiftOrderModel, McpOrderDraftModel, ProspectModel, UserModel


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_gifts",
        "description": "List CloseAndKeep cookie pack ids and live prices.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_prospects",
        "description": (
            "List the seller's prospects. Prefer matching by email before create_prospect."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Optional name/email search"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "create_prospect",
        "description": (
            "Create a prospect. Only call after list_prospects finds no email match."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "deal_status": {
                    "type": "string",
                    "enum": ["open", "won", "lost"],
                    "default": "open",
                },
            },
            "required": ["name", "email"],
            "additionalProperties": False,
        },
    },
    {
        "name": "draft_gift_order",
        "description": (
            "Validate gift-order details and return a draft_id + summary. "
            "Does NOT create an order or charge. Restate the summary to the seller "
            "and wait for an explicit yes before confirm_gift_order."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prospect_id": {"type": "integer"},
                "gift_id": {
                    "type": "string",
                    "description": "cookies-4 or cookies-12",
                },
                "recipient_name": {"type": "string"},
                "note": {
                    "type": "string",
                    "description": f"Gift note, max {GIFT_NOTE_MAX_LENGTH} characters",
                },
                "request_recipient_address": {
                    "type": "boolean",
                    "description": "If true, email the recipient for shipping address",
                },
                "recipient_email": {"type": "string"},
                "shipping_company": {"type": "string"},
                "shipping_street": {"type": "string"},
                "shipping_street2": {"type": "string"},
                "shipping_city": {"type": "string"},
                "shipping_state": {"type": "string"},
                "shipping_postal_code": {"type": "string"},
            },
            "required": ["prospect_id", "gift_id", "recipient_name", "note"],
            "additionalProperties": False,
        },
    },
    {
        "name": "confirm_gift_order",
        "description": (
            "Create the gift order for a previously issued draft_id after the seller "
            "explicitly confirms. Returns checkout_url (Stripe) or null if monthly billing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string"},
            },
            "required": ["draft_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_gift_order",
        "description": "Get status for one gift order owned by the seller.",
        "inputSchema": {
            "type": "object",
            "properties": {"order_id": {"type": "integer"}},
            "required": ["order_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_gift_orders",
        "description": "List recent gift orders; optionally filter by recipient email/name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "additionalProperties": False,
        },
    },
]


def _require_scope(auth: McpAuthContext, scope: str) -> None:
    if scope not in auth.scopes:
        raise HTTPException(status_code=403, detail=f"Missing scope {scope}")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _order_dict(order: GiftOrderModel) -> dict[str, Any]:
    return {
        "id": order.id,
        "prospect_id": order.prospect_id,
        "gift_id": order.gift_id,
        "recipient_name": order.recipient_name,
        "note": order.note,
        "status": order.status,
        "payment_status": order.payment_status,
        "recipient_email": order.recipient_email,
    }


def _validate_draft_payload(user: UserModel, args: dict[str, Any], db: Session) -> dict[str, Any]:
    gift_id = str(args.get("gift_id") or "").strip()
    if not is_known_gift(gift_id):
        raise HTTPException(status_code=400, detail="Unknown gift_id. Use cookies-4 or cookies-12.")

    prospect_id = int(args["prospect_id"])
    prospect = db.get(ProspectModel, prospect_id)
    if not prospect or prospect.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Prospect not found.")

    recipient_name = str(args.get("recipient_name") or "").strip()
    note = str(args.get("note") or "").strip()
    if not recipient_name:
        raise HTTPException(status_code=400, detail="recipient_name is required")
    if not note:
        raise HTTPException(status_code=400, detail="note is required")
    if len(note) > GIFT_NOTE_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"note must be at most {GIFT_NOTE_MAX_LENGTH} characters",
        )

    request_address = bool(args.get("request_recipient_address"))
    recipient_email = args.get("recipient_email")
    if recipient_email:
        recipient_email = _normalize_email(str(recipient_email))

    payload: dict[str, Any] = {
        "prospect_id": prospect_id,
        "gift_id": gift_id,
        "recipient_name": recipient_name,
        "note": note,
        "request_recipient_address": request_address,
        "recipient_email": recipient_email,
        "shipping_company": (str(args["shipping_company"]).strip() if args.get("shipping_company") else None),
        "shipping_street": (str(args["shipping_street"]).strip() if args.get("shipping_street") else None),
        "shipping_street2": (str(args["shipping_street2"]).strip() if args.get("shipping_street2") else None),
        "shipping_city": (str(args["shipping_city"]).strip() if args.get("shipping_city") else None),
        "shipping_state": (str(args["shipping_state"]).strip() if args.get("shipping_state") else None),
        "shipping_postal_code": (
            str(args["shipping_postal_code"]).strip() if args.get("shipping_postal_code") else None
        ),
    }

    if request_address:
        if not recipient_email:
            recipient_email = prospect.email
            payload["recipient_email"] = recipient_email
    else:
        street = payload["shipping_street"]
        city = payload["shipping_city"]
        state = payload["shipping_state"]
        postal = payload["shipping_postal_code"]
        if not all([street, city, state, postal]):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Provide shipping_street, shipping_city, shipping_state, and "
                    "shipping_postal_code, or set request_recipient_address true."
                ),
            )

    return payload


def _draft_summary(payload: dict[str, Any], prospect: ProspectModel, monthly: bool) -> str:
    pack = "4-pack" if payload["gift_id"] == "cookies-4" else "12-pack"
    lines = [
        f"Send {pack} cookies to {payload['recipient_name']} ({prospect.email}).",
        f"Note: {payload['note']}",
    ]
    if payload.get("request_recipient_address"):
        lines.append(
            f"Ask {payload.get('recipient_email') or prospect.email} for the shipping address by email."
        )
    else:
        lines.append(
            "Ship to "
            f"{payload.get('shipping_street')}, {payload.get('shipping_city')}, "
            f"{payload.get('shipping_state')} {payload.get('shipping_postal_code')}."
        )
    if monthly:
        lines.append(
            "WARNING: Monthly billing is on — confirming will queue the gift without a "
            "Stripe Checkout click. Prefer per-order payment while using AI."
        )
    else:
        lines.append("After confirm you will get a Stripe Checkout link to pay.")
    lines.append("Reply yes to confirm, or change the details.")
    return "\n".join(lines)


def draft_gift_order(auth: McpAuthContext, args: dict[str, Any], db: Session) -> dict[str, Any]:
    _require_scope(auth, "orders:write")
    payload = _validate_draft_payload(auth.user, args, db)
    prospect = db.get(ProspectModel, payload["prospect_id"])
    assert prospect is not None

    from .stripe_payments import user_has_saved_payment_method, user_uses_monthly_billing

    monthly = user_uses_monthly_billing(auth.user) and user_has_saved_payment_method(auth.user)
    summary = _draft_summary(payload, prospect, monthly)
    draft_id = f"drf_{token_urlsafe(18)}"
    record = McpOrderDraftModel(
        draft_id=draft_id,
        user_id=auth.user.id,
        payload=payload,
        summary=summary,
        expires_at=datetime.now(UTC) + DRAFT_TTL,
    )
    db.add(record)
    db.commit()
    return {
        "draft_id": draft_id,
        "summary": summary,
        "expires_in_seconds": int(DRAFT_TTL.total_seconds()),
        "monthly_billing": monthly,
    }


class _ToolRequest(Request):
    """Minimal ASGI request so create_gift_order can rate-limit and read origin."""

    def __init__(self) -> None:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/mcp",
            "raw_path": b"/mcp",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 0),
            "server": ("mcp", 443),
        }
        super().__init__(scope)


def confirm_gift_order(auth: McpAuthContext, args: dict[str, Any], db: Session) -> dict[str, Any]:
    _require_scope(auth, "orders:write")
    draft_id = str(args.get("draft_id") or "").strip()
    if not draft_id:
        raise HTTPException(status_code=400, detail="draft_id is required")

    record = db.scalar(
        select(McpOrderDraftModel).where(McpOrderDraftModel.draft_id == draft_id)
    )
    if record is None or record.user_id != auth.user.id:
        raise HTTPException(status_code=404, detail="Draft not found.")
    if record.consumed_at is not None:
        raise HTTPException(status_code=400, detail="Draft already used.")
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Draft expired. Create a new draft.")

    # Mark consumed before create to reduce double-submit races.
    record.consumed_at = datetime.now(UTC)
    db.add(record)
    db.commit()

    from .main import GiftOrderCreateRequest, create_gift_order

    payload = GiftOrderCreateRequest(**record.payload)
    result = create_gift_order(
        payload=payload,
        request=_ToolRequest(),
        current_user=auth.user,
        db=db,
    )
    body = result.model_dump()
    return {
        "order": {k: body[k] for k in ("id", "prospect_id", "gift_id", "recipient_name", "status", "payment_status", "note")},
        "checkout_url": body.get("checkout_url"),
        "message": (
            "Pay on the Stripe Checkout link. Do not invent a payment URL."
            if body.get("checkout_url")
            else "Monthly billing is on; the gift was queued without a Checkout link."
        ),
    }


def list_gifts(_auth: McpAuthContext, _args: dict[str, Any], _db: Session) -> dict[str, Any]:
    from .stripe_payments import list_gift_prices

    try:
        gifts = list_gift_prices()
    except Exception:
        gifts = [
            {"id": str(item["id"]), "cookie_count": item.get("cookie_count")}
            for item in GIFT_CATALOG
        ]
    return {"gifts": gifts, "base_url": settings.api_base_url}


def list_prospects(auth: McpAuthContext, args: dict[str, Any], db: Session) -> dict[str, Any]:
    _require_scope(auth, "orders:read")
    q = (args.get("q") or "").strip().lower()
    rows = db.scalars(
        select(ProspectModel)
        .where(ProspectModel.owner_user_id == auth.user.id)
        .order_by(ProspectModel.id.desc())
        .limit(100)
    ).all()
    prospects = []
    for row in rows:
        if q and q not in row.email.lower() and q not in row.name.lower():
            continue
        prospects.append(
            {
                "id": row.id,
                "name": row.name,
                "email": row.email,
                "deal_status": row.deal_status,
            }
        )
    return {"prospects": prospects}


def create_prospect(auth: McpAuthContext, args: dict[str, Any], db: Session) -> dict[str, Any]:
    _require_scope(auth, "orders:write")
    name = str(args.get("name") or "").strip()
    email = _normalize_email(str(args.get("email") or ""))
    if not name or not email:
        raise HTTPException(status_code=400, detail="name and email are required")
    deal_status = str(args.get("deal_status") or "open")
    if deal_status not in {"open", "won", "lost"}:
        raise HTTPException(status_code=400, detail="deal_status must be open, won, or lost")

    existing = db.scalar(
        select(ProspectModel).where(
            ProspectModel.owner_user_id == auth.user.id,
            ProspectModel.email == email,
        )
    )
    if existing:
        return {
            "id": existing.id,
            "name": existing.name,
            "email": existing.email,
            "deal_status": existing.deal_status,
            "reused": True,
        }

    prospect = ProspectModel(
        owner_user_id=auth.user.id,
        name=name,
        email=email,
        deal_status=deal_status,
    )
    db.add(prospect)
    db.commit()
    db.refresh(prospect)
    return {
        "id": prospect.id,
        "name": prospect.name,
        "email": prospect.email,
        "deal_status": prospect.deal_status,
        "reused": False,
    }


def get_gift_order(auth: McpAuthContext, args: dict[str, Any], db: Session) -> dict[str, Any]:
    _require_scope(auth, "orders:read")
    order_id = int(args["order_id"])
    order = db.get(GiftOrderModel, order_id)
    if not order or order.owner_user_id != auth.user.id:
        raise HTTPException(status_code=404, detail="Order not found.")
    return _order_dict(order)


def list_gift_orders(auth: McpAuthContext, args: dict[str, Any], db: Session) -> dict[str, Any]:
    _require_scope(auth, "orders:read")
    q = (args.get("q") or "").strip().lower()
    limit = int(args.get("limit") or 20)
    limit = max(1, min(limit, 50))
    rows = db.scalars(
        select(GiftOrderModel)
        .where(GiftOrderModel.owner_user_id == auth.user.id)
        .order_by(GiftOrderModel.id.desc())
        .limit(100)
    ).all()
    orders = []
    for row in rows:
        if q:
            hay = f"{row.recipient_name} {row.recipient_email or ''}".lower()
            if q not in hay:
                continue
        orders.append(_order_dict(row))
        if len(orders) >= limit:
            break
    return {"orders": orders}


TOOL_HANDLERS = {
    "list_gifts": list_gifts,
    "list_prospects": list_prospects,
    "create_prospect": create_prospect,
    "draft_gift_order": draft_gift_order,
    "confirm_gift_order": confirm_gift_order,
    "get_gift_order": get_gift_order,
    "list_gift_orders": list_gift_orders,
}


def call_tool(
    name: str,
    arguments: dict[str, Any] | None,
    auth: McpAuthContext,
    db: Session,
) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {name}")
    return handler(auth, arguments or {}, db)


def tool_result_content(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"type": "text", "text": json.dumps(result, default=str)}]
