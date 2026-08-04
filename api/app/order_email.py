"""Transactional emails for gift orders (Resend)."""

from __future__ import annotations

import base64
import html
import logging
from datetime import datetime
from typing import Any

import resend

from .config import settings

logger = logging.getLogger(__name__)

_SENDER_PHOTO_CID = "sender-photo"
_AVATAR_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_AVATAR_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


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


def _sender_avatar_attachment(
    *,
    data: bytes | None,
    content_type: str | None,
) -> dict[str, Any] | None:
    """Build a Resend inline CID attachment for the buyer's profile photo."""
    if not data:
        return None
    ct = (content_type or "").strip().lower()
    if ct not in _AVATAR_CONTENT_TYPES:
        return None
    return {
        "filename": f"sender.{_AVATAR_EXT[ct]}",
        "content": base64.b64encode(data).decode("ascii"),
        "content_type": ct,
        "content_id": _SENDER_PHOTO_CID,
    }


def _sender_photo_html(*, alt: str) -> str:
    return (
        f"<p style='margin:0 0 16px'>"
        f"<img src='cid:{_SENDER_PHOTO_CID}' alt='{html.escape(alt)}' width='72' height='72' "
        f"style='border-radius:50%;width:72px;height:72px;object-fit:cover;"
        f"display:block;border:1px solid #e7e5e4'/>"
        f"</p>"
    )


def _send(
    *,
    to: str | list[str],
    subject: str,
    text_body: str,
    html_body: str,
    context: str,
    attachments: list[dict[str, Any]] | None = None,
) -> None:
    ready = _resend_ready()
    if not ready:
        return
    recipients = (
        [addr.strip().lower() for addr in to if addr and addr.strip()]
        if isinstance(to, list)
        else [to.strip().lower()]
        if to and to.strip()
        else []
    )
    if not recipients:
        logger.warning("No recipients; skipping email (%s).", context)
        return
    key, from_addr = ready
    resend.api_key = key
    payload: dict[str, Any] = {
        "from": from_addr,
        "to": recipients,
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }
    if attachments:
        payload["attachments"] = attachments
    try:
        resend.Emails.send(payload)
        logger.info("Email accepted by Resend (%s) to=%s", context, recipients)
    except Exception:
        logger.exception("Failed to send email (%s) to=%s", context, recipients)


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
    prospect_email: str,
    prospect_deal_status: str,
    placed_by_email: str,
    payment_status: str | None = None,
) -> None:
    to = list(settings.order_notification_to or [])
    if not to:
        logger.warning("ORDER_NOTIFICATION_TO is empty; skipping new-order notification email.")
        return

    unpaid_monthly = (payment_status or "").strip().lower() == "owed"
    subject = (
        f"New cookie order #{order_id} (monthly / unpaid)"
        if unpaid_monthly
        else f"New cookie order #{order_id}"
    )
    when = requested_at.isoformat(timespec="seconds")

    text_fields: dict[str, str] = {
        "Order_ID": str(order_id),
        "Requested_at": when,
        "Status": status,
        "Placed_by_account": placed_by_email,
        "Gift_or_pack_id": gift_id,
        "Prospect_name": prospect_name,
        "Prospect_email": prospect_email,
        "Prospect_deal_status": prospect_deal_status,
        "Recipient_name": recipient_name,
        "Shipping_address": shipping_address,
        "Gift_note": note,
    }
    if payment_status:
        text_fields["Payment_status"] = payment_status
    text_body = _lines(**text_fields)

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
    if payment_status:
        row("Payment status", payment_status)
    row("Placed by (account)", placed_by_email)
    row("Gift / pack ID", gift_id)
    row("Prospect name", prospect_name)
    row("Prospect email", prospect_email)
    row("Prospect deal status", prospect_deal_status)
    row("Recipient name", recipient_name)
    row("Shipping address", shipping_address, html_multiline=True)
    row("Gift note", note, html_multiline=True)

    rows = "".join(rows_parts)
    heading = "New cookie order (monthly / unpaid)" if unpaid_monthly else "New cookie order"
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px'>"
        f"<h2 style='margin:0 0 12px'>{html.escape(heading)}</h2>"
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
    redeem_url: str,
    redeem_code: str,
    gift_label: str,
    note: str,
    sender_name: str | None,
    sender_company: str | None,
    sender_avatar_data: bytes | None = None,
    sender_avatar_content_type: str | None = None,
    support_email: str = "Agent@closeandkeep.com",
) -> None:
    """Ask the gift recipient to view the gift and share a shipping address."""
    to = recipient_email.strip().lower()
    if not to:
        logger.warning("Recipient email empty; skipping address-request email.")
        return

    first_name = (recipient_name or "").strip().split()[0] if (recipient_name or "").strip() else "there"
    sender = (sender_name or "").strip()
    company = (sender_company or "").strip()
    if sender and company:
        subject = f"{sender} from {company} sent you cookies"
        who = f"{sender} from {company}"
    elif sender:
        subject = f"{sender} sent you cookies"
        who = sender
    elif company:
        subject = f"Someone from {company} sent you cookies"
        who = f"Someone from {company}"
    else:
        subject = "Someone sent you cookies"
        who = "Someone"

    avatar = _sender_avatar_attachment(
        data=sender_avatar_data,
        content_type=sender_avatar_content_type,
    )
    photo_alt = sender or who

    text_body = (
        f"Hi {first_name},\n\n"
        f"{who} purchased a cookie gift for you through Close & Keep.\n\n"
        f"{sender or 'They'} included this message:\n"
        f"“{note}”\n\n"
        "Close & Keep does not yet have your delivery address. You can view the gift "
        "and provide a delivery location on our website. No payment is required, and "
        "you will not be added to a mailing list.\n\n"
        f"View your gift: {address_form_url}\n\n"
        f"Prefer not to click the button? Visit CloseAndKeep.com/redeem and enter code "
        f"{redeem_code}.\n\n"
        f"Not expecting this gift? You can decline it or contact {support_email}.\n"
    )
    esc = html.escape
    note_html = esc(note)
    photo_html = _sender_photo_html(alt=photo_alt) if avatar else ""
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;"
        "line-height:1.5;color:#1c1917'>"
        f"{photo_html}"
        f"<p>Hi {esc(first_name)},</p>"
        f"<p>{esc(who)} purchased a cookie gift for you through Close &amp; Keep.</p>"
        f"<p>{esc(sender) if sender else 'They'} included this message:</p>"
        f"<p style='margin:0 0 1em;padding:12px 16px;border-left:3px solid #8B5E3C;"
        f"background:#faf7f2;font-style:italic'>“{note_html}”</p>"
        "<p>Close &amp; Keep does not yet have your delivery address. You can view the gift "
        "and provide a delivery location on our website. No payment is required, and you "
        "will not be added to a mailing list.</p>"
        f"<p><a href='{esc(address_form_url)}' style='display:inline-block;padding:10px 16px;"
        "background:#8B5E3C;color:#fff;text-decoration:none;border-radius:8px'>"
        "View your gift</a></p>"
        f"<p style='color:#57534e;font-size:13px'>Prefer not to click the button? Visit "
        f"<a href='{esc(redeem_url)}' style='color:#8B5E3C'>CloseAndKeep.com/redeem</a> "
        f"and enter code <strong>{esc(redeem_code)}</strong>.</p>"
        f"<p style='color:#57534e;font-size:13px'>Gift: {esc(gift_label)}</p>"
        f"<p style='color:#57534e;font-size:13px'>Not expecting this gift? You can decline it "
        f"on the redeem page or contact "
        f"<a href='mailto:{esc(support_email)}' style='color:#8B5E3C'>{esc(support_email)}</a>."
        "</p>"
        "</body></html>"
    )
    _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context="recipient-address-request",
        attachments=[avatar] if avatar else None,
    )


def send_recipient_address_followup(
    *,
    recipient_name: str,
    recipient_email: str,
    address_form_url: str,
    redeem_url: str,
    redeem_code: str,
    gift_label: str,
    note: str,
    sender_name: str | None,
    sender_company: str | None,
    sender_avatar_data: bytes | None = None,
    sender_avatar_content_type: str | None = None,
    support_email: str = "Agent@closeandkeep.com",
) -> None:
    """Remind the gift recipient to share a shipping address (after ~72 hours)."""
    to = recipient_email.strip().lower()
    if not to:
        logger.warning("Recipient email empty; skipping address-request follow-up.")
        return

    first_name = (recipient_name or "").strip().split()[0] if (recipient_name or "").strip() else "there"
    sender = (sender_name or "").strip()
    company = (sender_company or "").strip()
    if sender and company:
        subject = f"Reminder: {sender} from {company} sent you cookies"
        who = f"{sender} from {company}"
    elif sender:
        subject = f"Reminder: {sender} sent you cookies"
        who = sender
    elif company:
        subject = f"Reminder: Someone from {company} sent you cookies"
        who = f"Someone from {company}"
    else:
        subject = "Reminder: Someone sent you cookies"
        who = "Someone"

    avatar = _sender_avatar_attachment(
        data=sender_avatar_data,
        content_type=sender_avatar_content_type,
    )
    photo_alt = sender or who

    text_body = (
        f"Hi {first_name},\n\n"
        f"Just a quick reminder — {who} purchased a cookie gift for you through "
        "Close & Keep, and we still need a delivery address to ship it.\n\n"
        f"{sender or 'They'} included this message:\n"
        f"“{note}”\n\n"
        "No payment is required, and you will not be added to a mailing list.\n\n"
        f"View your gift: {address_form_url}\n\n"
        f"Prefer not to click the button? Visit CloseAndKeep.com/redeem and enter code "
        f"{redeem_code}.\n\n"
        f"Not expecting this gift? You can decline it or contact {support_email}.\n"
    )
    esc = html.escape
    note_html = esc(note)
    photo_html = _sender_photo_html(alt=photo_alt) if avatar else ""
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;"
        "line-height:1.5;color:#1c1917'>"
        f"{photo_html}"
        f"<p>Hi {esc(first_name)},</p>"
        f"<p>Just a quick reminder — {esc(who)} purchased a cookie gift for you through "
        "Close &amp; Keep, and we still need a delivery address to ship it.</p>"
        f"<p>{esc(sender) if sender else 'They'} included this message:</p>"
        f"<p style='margin:0 0 1em;padding:12px 16px;border-left:3px solid #8B5E3C;"
        f"background:#faf7f2;font-style:italic'>“{note_html}”</p>"
        "<p>No payment is required, and you will not be added to a mailing list.</p>"
        f"<p><a href='{esc(address_form_url)}' style='display:inline-block;padding:10px 16px;"
        "background:#8B5E3C;color:#fff;text-decoration:none;border-radius:8px'>"
        "View your gift</a></p>"
        f"<p style='color:#57534e;font-size:13px'>Prefer not to click the button? Visit "
        f"<a href='{esc(redeem_url)}' style='color:#8B5E3C'>CloseAndKeep.com/redeem</a> "
        f"and enter code <strong>{esc(redeem_code)}</strong>.</p>"
        f"<p style='color:#57534e;font-size:13px'>Gift: {esc(gift_label)}</p>"
        f"<p style='color:#57534e;font-size:13px'>Not expecting this gift? You can decline it "
        f"on the redeem page or contact "
        f"<a href='mailto:{esc(support_email)}' style='color:#8B5E3C'>{esc(support_email)}</a>."
        "</p>"
        "</body></html>"
    )
    _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context="recipient-address-followup",
        attachments=[avatar] if avatar else None,
    )


def send_orderer_gift_declined(
    *,
    order_id: int,
    orderer_email: str,
    recipient_name: str,
    order_url: str,
) -> None:
    """Notify the buyer that the recipient declined the gift."""
    to = orderer_email.strip().lower()
    if not to:
        logger.warning("Orderer email empty; skipping gift-declined notice.")
        return

    subject = f"Gift declined — order #{order_id}"
    text_body = (
        f"{recipient_name} declined the cookie gift for order #{order_id}.\n\n"
        "The payment authorization has been released and the order was canceled.\n"
        f"View order: {order_url}\n"
    )
    esc = html.escape
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;line-height:1.5'>"
        f"<p><strong>{esc(recipient_name)}</strong> declined the cookie gift for order #{order_id}.</p>"
        "<p>The payment authorization has been released and the order was canceled.</p>"
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
        context=f"orderer-gift-declined order_id={order_id}",
    )


def send_orderer_receipt(
    *,
    order_id: int,
    orderer_email: str,
    gift_label: str,
    recipient_name: str,
    shipping_address: str | None,
    order_url: str,
) -> None:
    """Send the buyer a receipt after payment is completed."""
    to = orderer_email.strip().lower()
    if not to:
        logger.warning("Orderer email empty; skipping receipt.")
        return

    address = (shipping_address or "").strip()
    subject = f"Receipt — order #{order_id}"
    text_parts = [
        f"Thanks for your order #{order_id}.",
        "",
        f"Gift: {gift_label}",
        f"Recipient: {recipient_name}",
    ]
    if address:
        text_parts.extend(["", f"Shipping address:\n{address}"])
    text_parts.extend(
        [
            "",
            "Your payment has been completed and the order is queued for fulfillment.",
            f"View order: {order_url}",
            "",
        ]
    )
    text_body = "\n".join(text_parts)

    esc = html.escape
    address_html = (
        f"<p style='white-space:pre-wrap'><strong>Shipping address:</strong><br/>{esc(address)}</p>"
        if address
        else ""
    )
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;line-height:1.5'>"
        f"<p>Thanks for your order <strong>#{order_id}</strong>.</p>"
        f"<p><strong>Gift:</strong> {esc(gift_label)}<br/>"
        f"<strong>Recipient:</strong> {esc(recipient_name)}</p>"
        f"{address_html}"
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
        context=f"orderer-receipt order_id={order_id}",
    )


def send_monthly_billing_receipt(
    *,
    orderer_email: str,
    order_summaries: list[dict[str, str | int]],
    amount_cents: int,
    currency: str,
    profile_url: str,
) -> None:
    """Receipt after a successful monthly balance charge (Pay now or month-end)."""
    to = orderer_email.strip().lower()
    if not to:
        logger.warning("Orderer email empty; skipping monthly billing receipt.")
        return
    if not order_summaries:
        return

    dollars = f"{amount_cents / 100:.2f}"
    cur = (currency or "usd").upper()
    subject = f"Receipt — monthly cookie billing ({dollars} {cur})"
    lines = [
        "Your card was charged for open cookie orders.",
        "",
        f"Amount: {dollars} {cur}",
        f"Orders: {len(order_summaries)}",
        "",
    ]
    for item in order_summaries:
        lines.append(
            f"- #{item['order_id']}: {item['gift_label']} → {item['recipient_name']}"
        )
    lines.extend(["", f"View profile / billing: {profile_url}", ""])
    text_body = "\n".join(lines)

    esc = html.escape
    items_html = "".join(
        f"<li>#{esc(str(item['order_id']))}: {esc(str(item['gift_label']))} → "
        f"{esc(str(item['recipient_name']))}</li>"
        for item in order_summaries
    )
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;line-height:1.5'>"
        "<p>Your card was charged for open cookie orders.</p>"
        f"<p><strong>Amount:</strong> {esc(dollars)} {esc(cur)}<br/>"
        f"<strong>Orders:</strong> {len(order_summaries)}</p>"
        f"<ul>{items_html}</ul>"
        f"<p><a href='{esc(profile_url)}' style='display:inline-block;padding:10px 16px;"
        "background:#8B5E3C;color:#fff;text-decoration:none;border-radius:8px'>"
        "View profile</a></p>"
        "</body></html>"
    )
    _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context="monthly-billing-receipt",
    )


def send_monthly_charge_failed(
    *,
    orderer_email: str,
    amount_cents: int,
    currency: str,
    order_count: int,
    profile_url: str,
) -> None:
    """Ask the buyer to update their card / Pay now after a failed off-session charge."""
    to = orderer_email.strip().lower()
    if not to:
        return
    dollars = f"{amount_cents / 100:.2f}"
    cur = (currency or "usd").upper()
    subject = "Action needed — cookie billing charge failed"
    text_body = (
        f"We could not charge your saved card for {dollars} {cur} "
        f"across {order_count} open cookie order(s).\n\n"
        "Please update your card or use Pay now on your profile.\n"
        f"{profile_url}\n"
    )
    esc = html.escape
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;line-height:1.5'>"
        f"<p>We could not charge your saved card for <strong>{esc(dollars)} {esc(cur)}</strong> "
        f"across {order_count} open cookie order(s).</p>"
        "<p>Please update your card or use <strong>Pay now</strong> on your profile.</p>"
        f"<p><a href='{esc(profile_url)}' style='display:inline-block;padding:10px 16px;"
        "background:#8B5E3C;color:#fff;text-decoration:none;border-radius:8px'>"
        "Open profile</a></p>"
        "</body></html>"
    )
    _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context="monthly-charge-failed",
    )


def send_monthly_balance_reminder(
    *,
    orderer_email: str,
    amount_cents: int,
    currency: str,
    order_count: int,
    profile_url: str,
) -> None:
    """Short reminder a few days before the automatic month-end charge."""
    to = orderer_email.strip().lower()
    if not to:
        return
    dollars = f"{amount_cents / 100:.2f}"
    cur = (currency or "usd").upper()
    subject = "Reminder — cookie order balance due soon"
    text_body = (
        f"Your open cookie-order balance is {dollars} {cur} "
        f"({order_count} order(s)).\n\n"
        "Your saved card will be charged automatically at the end of the month, "
        "or you can Pay now anytime from your profile.\n"
        f"{profile_url}\n"
    )
    esc = html.escape
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;line-height:1.5'>"
        f"<p>Your open cookie-order balance is <strong>{esc(dollars)} {esc(cur)}</strong> "
        f"({order_count} order(s)).</p>"
        "<p>Your saved card will be charged automatically at the end of the month, "
        "or you can <strong>Pay now</strong> anytime from your profile.</p>"
        f"<p><a href='{esc(profile_url)}' style='display:inline-block;padding:10px 16px;"
        "background:#8B5E3C;color:#fff;text-decoration:none;border-radius:8px'>"
        "Open profile</a></p>"
        "</body></html>"
    )
    _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context="monthly-balance-reminder",
    )


def send_spending_limit_reached(
    *,
    orderer_email: str,
    limit_cents: int,
    balance_cents: int,
    currency: str,
    profile_url: str,
    blocked_recipient_names: list[str] | None = None,
) -> None:
    """Notify the buyer that their max spending limit was hit."""
    to = orderer_email.strip().lower()
    if not to:
        return
    limit_dollars = f"{limit_cents / 100:.2f}"
    balance_dollars = f"{balance_cents / 100:.2f}"
    cur = (currency or "usd").upper()
    names = [n.strip() for n in (blocked_recipient_names or []) if n and n.strip()]
    esc = html.escape
    if len(names) == 1:
        pending_text = (
            f"{names[0]} did not receive a cookie order because of this limit."
        )
        pending_html = (
            f"<p><strong>{esc(names[0])}</strong> did not receive a cookie order "
            "because of this limit.</p>"
        )
    elif len(names) > 1:
        listed = ", ".join(names[:-1]) + f", and {names[-1]}"
        pending_text = (
            f"These people did not receive a cookie order because of this limit: {listed}."
        )
        listed_html = ", ".join(f"<strong>{esc(n)}</strong>" for n in names[:-1])
        listed_html += f", and <strong>{esc(names[-1])}</strong>"
        pending_html = (
            "<p>These people did not receive a cookie order because of this limit: "
            f"{listed_html}.</p>"
        )
    else:
        pending_text = ""
        pending_html = ""

    subject = "Action needed — max spending limit reached"
    pending_block = f"{pending_text}\n\n" if pending_text else ""
    text_body = (
        f"Your open cookie-order balance ({balance_dollars} {cur}) has reached "
        f"your max spending limit of {limit_dollars} {cur}.\n\n"
        f"{pending_block}"
        "Log in to make a payment or raise your max spending limit on your profile "
        "before placing more monthly-billed orders.\n"
        f"{profile_url}\n"
    )
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;line-height:1.5'>"
        f"<p>Your open cookie-order balance (<strong>{esc(balance_dollars)} {esc(cur)}</strong>) "
        f"has reached your max spending limit of <strong>{esc(limit_dollars)} {esc(cur)}</strong>.</p>"
        f"{pending_html}"
        "<p>Log in to make a payment or raise your max spending limit on your profile "
        "before placing more monthly-billed orders.</p>"
        f"<p><a href='{esc(profile_url)}' style='display:inline-block;padding:10px 16px;"
        "background:#8B5E3C;color:#fff;text-decoration:none;border-radius:8px'>"
        "Open profile</a></p>"
        "</body></html>"
    )
    _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context="spending-limit-reached",
    )


def send_auto_order_checkout(
    *,
    to_email: str,
    prospect_name: str,
    gift_label: str,
    checkout_url: str,
    order_url: str,
) -> None:
    """Notify the owner that CRM auto-order created a Checkout-pending order."""
    to = to_email.strip().lower()
    if not to:
        return
    subject = f"Complete payment — cookies for {prospect_name}"
    text_body = (
        f"We automatically started a cookie order for {prospect_name} ({gift_label}).\n\n"
        f"Complete payment to send the address request: {checkout_url}\n"
        f"View order: {order_url}\n"
    )
    esc = html.escape
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;line-height:1.5'>"
        f"<p>We automatically started a cookie order for <strong>{esc(prospect_name)}</strong> "
        f"({esc(gift_label)}).</p>"
        "<p>Complete payment to send the address request to the recipient.</p>"
        f"<p><a href='{esc(checkout_url)}' style='display:inline-block;padding:10px 16px;"
        "background:#8B5E3C;color:#fff;text-decoration:none;border-radius:8px'>"
        "Complete payment</a></p>"
        f"<p><a href='{esc(order_url)}'>View order</a></p>"
        "</body></html>"
    )
    _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context="auto-order-checkout",
    )


def send_cookie_reminder(
    *,
    to_email: str,
    prospect_name: str,
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
        f"Your {crm} {deal_word} for {prospect_name} "
        f"moved to “{stage_name}”.\n\n"
        "Order cookies while the pitch is fresh — and add a personal note on the gift "
        "so they remember you.\n\n"
        f"Order cookies: {order_url}\n"
    )
    esc = html.escape
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;line-height:1.5'>"
        f"<p>Your {esc(crm)} {esc(deal_word)} for <strong>{esc(prospect_name)}</strong>"
        f" moved to "
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
