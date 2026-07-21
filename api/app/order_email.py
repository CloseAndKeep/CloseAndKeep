"""Transactional emails for gift orders (Resend)."""

from __future__ import annotations

import html
import logging
from datetime import datetime

import resend

from .config import settings

logger = logging.getLogger(__name__)


def _resend_ready() -> tuple[str, str] | None:
    """Return (api_key, from_addr) when Resend can send, else None."""
    key = (settings.resend_api_key or "").strip()
    if not key:
        logger.warning("RESEND_API_KEY is not set; skipping email.")
        return None
    from_addr = (settings.resend_from or "").strip()
    if not from_addr:
        logger.warning("RESEND_FROM is empty; skipping email.")
        return None
    return key, from_addr


def _lines(**fields: str) -> str:
    return "\n".join(f"{k}: {v}" for k, v in fields.items())


def _send(*, to: str, subject: str, text_body: str, html_body: str, context: str) -> None:
    ready = _resend_ready()
    if not ready:
        return
    key, from_addr = ready
    resend.api_key = key
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
        logger.info("Email accepted by Resend (%s) to=%s", context, to)
    except Exception:
        logger.exception("Failed to send email (%s) to=%s", context, to)


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
    to = (settings.order_notification_to or "").strip().lower()
    if not to:
        logger.warning("ORDER_NOTIFICATION_TO is empty; skipping new-order notification email.")
        return

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

    _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context=f"ops-new-order order_id={order_id}",
    )


def send_recipient_address_request(
    *,
    recipient_name: str,
    recipient_email: str,
    address_form_url: str,
    gift_id: str,
    note: str,
) -> None:
    """Ask the gift recipient to enter the shipping address via a magic link."""
    to = recipient_email.strip().lower()
    if not to:
        logger.warning("Recipient email empty; skipping address-request email.")
        return

    subject = "Please share your shipping address for a gift"
    text_body = (
        f"Hi {recipient_name},\n\n"
        "Someone ordered cookies for you through Close & Keep.\n"
        "Use this link to enter the address where we should send them:\n\n"
        f"{address_form_url}\n\n"
        f"Gift: {gift_id}\n"
        f"Note from the sender:\n{note}\n"
    )
    esc = html.escape
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;line-height:1.5'>"
        f"<p>Hi {esc(recipient_name)},</p>"
        "<p>Someone ordered cookies for you through Close &amp; Keep.</p>"
        "<p>Use the button below to enter the address where we should send them.</p>"
        f"<p><a href='{esc(address_form_url)}' style='display:inline-block;padding:10px 16px;"
        "background:#8B5E3C;color:#fff;text-decoration:none;border-radius:8px'>"
        "Enter shipping address</a></p>"
        f"<p style='color:#666;font-size:13px'>Gift: {esc(gift_id)}</p>"
        f"<p style='white-space:pre-wrap'><strong>Note from the sender:</strong><br/>{esc(note)}</p>"
        "</body></html>"
    )
    _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context="recipient-address-request",
    )


def send_orderer_address_received(
    *,
    order_id: int,
    orderer_email: str,
    recipient_name: str,
    shipping_address: str,
    order_url: str,
) -> None:
    """Confirm to the person who ordered that address was received and payment captured."""
    to = orderer_email.strip().lower()
    if not to:
        logger.warning("Orderer email empty; skipping address-received confirmation.")
        return

    subject = f"Address received — order #{order_id} is confirmed"
    text_body = (
        f"Good news — {recipient_name} submitted a shipping address for order #{order_id}.\n\n"
        f"Shipping address:\n{shipping_address}\n\n"
        "Your payment has been completed and the order is queued for fulfillment.\n"
        f"View order: {order_url}\n"
    )
    esc = html.escape
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;line-height:1.5'>"
        f"<p>Good news — <strong>{esc(recipient_name)}</strong> submitted a shipping address "
        f"for order #{order_id}.</p>"
        f"<p style='white-space:pre-wrap'><strong>Shipping address:</strong><br/>{esc(shipping_address)}</p>"
        "<p>Your payment has been completed and the order is queued for fulfillment.</p>"
        f"<p><a href='{esc(order_url)}' style='display:inline-block;padding:10px 16px;"
        "background:#8B5E3C;color:#fff;text-decoration:none;border-radius:8px'>"
        "View order</a></p>"
        "</body></html>"
    )
    _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context=f"orderer-address-received order_id={order_id}",
    )


def send_cookie_reminder(
    *,
    to_email: str,
    prospect_name: str,
    prospect_company: str,
    prospect_title: str,
    stage_name: str,
    order_url: str,
    crm_name: str = "Salesforce",
) -> None:
    """Remind the salesperson to order cookies after a CRM demo stage change."""
    to = to_email.strip().lower()
    if not to:
        logger.warning("Salesperson email empty; skipping cookie reminder.")
        return

    crm = (crm_name or "CRM").strip() or "CRM"
    deal_word = "deal" if crm.casefold() == "hubspot" else "opportunity"
    subject = f"Demo done — send cookies to {prospect_name}?"
    text_body = (
        f"Your {crm} {deal_word} for {prospect_name} at {prospect_company} "
        f"moved to “{stage_name}”.\n\n"
        "Order cookies while the pitch is fresh — and add a personal note on the gift "
        "so they remember you.\n\n"
        f"Order cookies: {order_url}\n"
    )
    esc = html.escape
    title_bit = (
        f" ({esc(prospect_title)})"
        if prospect_title and prospect_title != "—"
        else ""
    )
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;line-height:1.5'>"
        f"<p>Your {esc(crm)} {esc(deal_word)} for <strong>{esc(prospect_name)}</strong>"
        f"{title_bit}"
        f" at <strong>{esc(prospect_company)}</strong> moved to "
        f"<strong>{esc(stage_name)}</strong>.</p>"
        "<p>Order cookies while the pitch is fresh — and "
        "<strong>add a personal note</strong> on the gift so they remember you.</p>"
        f"<p><a href='{esc(order_url)}' style='display:inline-block;padding:10px 16px;"
        "background:#8B5E3C;color:#fff;text-decoration:none;border-radius:8px'>"
        "Order cookies</a></p>"
        "</body></html>"
    )
    _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context=f"cookie-reminder-{crm.casefold().replace(' ', '-')}",
    )
