from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from packagingapp.services.email_delivery import send_contact_email


class ContactEmailDeliveryTests(SimpleTestCase):
    @override_settings(
        EMAIL_TRANSPORT="smtp",
        DEFAULT_FROM_EMAIL="sender@example.com",
    )
    @patch("packagingapp.services.email_delivery.send_mail", return_value=1)
    def test_smtp_transport_preserves_existing_django_mail_delivery(self, send_mail):
        result = send_contact_email(
            subject="Subject",
            body="Body",
            recipient="recipient@example.com",
        )

        self.assertEqual(result, 1)
        send_mail.assert_called_once_with(
            subject="Subject",
            message="Body",
            from_email="sender@example.com",
            recipient_list=["recipient@example.com"],
            fail_silently=False,
        )

    @override_settings(
        EMAIL_TRANSPORT="brevo_api",
        BREVO_API_KEY="test-api-key",
        BREVO_API_URL="https://api.example.test/v3/smtp/email",
        BREVO_API_TIMEOUT=5,
        BREVO_SENDER_NAME="KolliLabs",
        DEFAULT_FROM_EMAIL="sender@example.com",
    )
    @patch("packagingapp.services.email_delivery.urlopen")
    def test_brevo_api_transport_posts_plain_text_message(self, urlopen):
        response = MagicMock()
        response.status = 201
        response.__enter__.return_value = response
        urlopen.return_value = response

        result = send_contact_email(
            subject="Subject",
            body="Body",
            recipient="recipient@example.com",
            reply_to="visitor@example.com",
        )

        self.assertEqual(result, 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.example.test/v3/smtp/email")
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "sender": {"name": "KolliLabs", "email": "sender@example.com"},
                "to": [{"email": "recipient@example.com"}],
                "subject": "Subject",
                "textContent": "Body",
                "replyTo": {"email": "visitor@example.com"},
            },
        )
        self.assertEqual(dict(request.header_items())["Api-key"], "test-api-key")
