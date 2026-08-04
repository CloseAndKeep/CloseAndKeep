"""Auth transactional emails (Resend)."""

from __future__ import annotations

import html
import logging

from .order_email import _send

logger = logging.getLogger(__name__)


def send_email_verification(
    *,
    to_email: str,
    verify_url: str,
    name: str | None = None,
) -> bool:
    """Send the signup email-verification link. Returns True if Resend accepted it."""
    to = (to_email or "").strip().lower()
    if not to:
        logger.warning("Verification email empty; skipping.")
        return False

    first = (name or "").strip().split()[0] if (name or "").strip() else "there"
    subject = "Verify your Close & Keep email"
    text_body = (
        f"Hi {first},\n\n"
        "Thanks for signing up for Close & Keep. Confirm your email address to "
        "activate your account:\n\n"
        f"{verify_url}\n\n"
        "This link expires in 24 hours. If you did not create an account, you can "
        "ignore this message.\n"
    )
    esc = html.escape
    html_body = (
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;font-size:14px;"
        "line-height:1.5;color:#1c1917'>"
        f"<p>Hi {esc(first)},</p>"
        "<p>Thanks for signing up for Close &amp; Keep. Confirm your email address to "
        "activate your account:</p>"
        f"<p><a href='{esc(verify_url)}' style='display:inline-block;padding:10px 16px;"
        "background:#8B5E3C;color:#fff;text-decoration:none;border-radius:8px'>"
        "Verify email</a></p>"
        "<p style='color:#57534e;font-size:13px'>This link expires in 24 hours. If you "
        "did not create an account, you can ignore this message.</p>"
        "</body></html>"
    )
    return _send(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        context="email-verification",
    )
