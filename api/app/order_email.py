"""Notify operations when a gift order is created (Resend)."""

from __future__ import annotations

import html
import logging
from datetime import datetime

import resend

from .config import settings

logger = logging.getLogger(__name__)


def _lines(**fields: str) -> str:
    return "\n".join(f"{k}: {v}" for k, v in fields.items())


def send_new_order_notification(
    *,
    order_id: int,
    requested_at: datetime,
    gift_id: str,
    recipient_name: str,
    shipping_address: str,
    note: str,
    status: str,
    prospect_name: str,
    prospect_company: str,
    prospect_title: str,
    prospect_email: str,
    prospect_deal_status: str,
    placed_by_email: str,
) -> None:
    key = (settings.resend_api_key or "").strip()
    if not key:
        logger.warning("RESEND_API_KEY is not set; skipping new-order notification email.")
        return

    to = (settings.order_notification_to or "").strip().lower()
    if not to:
        logger.warning("ORDER_NOTIFICATION_TO is empty; skipping new-order notification email.")
        return

    # Resend test sender only delivers to your Resend account email; that match is case-sensitive.
    if not from_addr:
        logger.warning("RESEND_FROM is empty; skipping new-order notification email.")
        return

    resend.api_key = key
    subject = f"New cookie order #{order_id}"
    when = requested_at.isoformat(timespec="seconds")

    text_body = _lines(
        Order_ID=str(order_id),
        Requested_at=when,
        Status=status,
        Placed_by_account=placed_by_email,
        Gift_or_pack_id=gift_id,
        Prospect_name=prospect_name,
        Prospect_company=prospect_company,
        Prospect_title=prospect_title,
        Prospect_email=prospect_email,
        Prospect_deal_status=prospect_deal_status,
        Recipient_name=recipient_name,
        Shipping_address=shipping_address,
        Gift_note=note,
    )

    esc = html.escape
    rows_parts: list[str] = []

    def row(label: str, value: str, *, html_multiline: bool = False) -> None:
        v_esc = esc(value)
        if html_multiline:
            v_html = v_esc.replace("\n", "<br/>")
        else:
            v_html = v_esc
        rows_parts.append(
            f"<tr><th align='left' style='padding:4px 12px 4px 0;vertical-align:top'>{esc(label)}</th>"
            f"<td style='padding:4px 0;{ 'white-space:pre-wrap' if html_multiline else '' }'>{v_html}</td></tr>"
        )

    row("Order ID", str(order_id))
    row("Requested at", when)
    row("Status", status)
    row("Placed by (account)", placed_by_email)
    row("Gift / pack ID", gift_id)
    row("Prospect name", prospect_name)
    row("Prospect company", prospect_company)
    row("Prospect title", prospect_title)
    row("Prospect email", prospect_email)
    row("Prospect deal status", prospect_deal_status)
    row("Recipient name", recipient_name)
    row("Shipping address", shipping_address, html_multiline=True)
    row("Gift note", note, html_multiline=True)

    rows = "".join(rows_parts)
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px'>"
        "<h2 style='margin:0 0 12px'>New cookie order</h2>"
        "<table style='border-collapse:collapse'>"
        f"{rows}"
        "</table></body></html>"
    )

    try:
        resend.Emails.send(
            {
                "from": from_addr,
                "to": [to],
                "subject": subject,
                "text": text_body,
                "html": html_body,
            }
        )
        logger.info(
            "Order notification email accepted by Resend for order_id=%s to=%s",
            order_id,
            to,
        )
    except Exception:
        logger.exception("Failed to send order notification email for order_id=%s", order_id)
