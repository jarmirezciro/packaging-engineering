"""Contact-email delivery through SMTP or Brevo's HTTPS API."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import send_mail


class EmailDeliveryError(RuntimeError):
    """Raised when the configured contact-email transport cannot deliver."""


def send_contact_email(*, subject: str, body: str, recipient: str, reply_to: str | None = None):
    """Send a contact message using the configured transport."""
    transport = getattr(settings, "EMAIL_TRANSPORT", "smtp").strip().lower()
    if transport == "brevo_api":
        return _send_with_brevo_api(
            subject=subject,
            body=body,
            recipient=recipient,
            reply_to=reply_to,
        )
    if transport != "smtp":
        raise EmailDeliveryError(f"Unsupported email transport: {transport}")

    return send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[recipient],
        fail_silently=False,
    )


def _send_with_brevo_api(*, subject: str, body: str, recipient: str, reply_to: str | None = None):
    api_key = getattr(settings, "BREVO_API_KEY", "")
    if not api_key:
        raise EmailDeliveryError("BREVO_API_KEY is not configured.")

    payload = {
        "sender": {
            "name": getattr(settings, "BREVO_SENDER_NAME", "KolliLabs"),
            "email": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
        },
        "to": [{"email": recipient}],
        "subject": subject,
        "textContent": body,
    }
    if reply_to:
        payload["replyTo"] = {"email": reply_to}

    request = Request(
        getattr(settings, "BREVO_API_URL", "https://api.brevo.com/v3/smtp/email"),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=getattr(settings, "BREVO_API_TIMEOUT", 20)) as response:
            status = getattr(response, "status", response.getcode())
            if not 200 <= status < 300:
                raise EmailDeliveryError(f"Brevo API returned HTTP {status}.")
            return 1
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")[:500]
        raise EmailDeliveryError(
            f"Brevo API returned HTTP {exc.code}: {details}"
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise EmailDeliveryError(f"Brevo API connection failed: {exc}") from exc
