import json
from copy import deepcopy
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from packagingapp.assistant.public_contracts import MAX_PUBLIC_USER_MESSAGE_LENGTH
from packagingapp.assistant.public_views import MAX_PUBLIC_EXPERT_REQUEST_BYTES


@override_settings(AI_PUBLIC_EXPERT_ENABLED=True)
class PublicExpertEndpointTests(TestCase):
    def setUp(self):
        self.url = reverse("public_expert_ask")

    def post(self, payload, *, client=None, content_type="application/json"):
        return (client or self.client).post(
            self.url,
            data=json.dumps(payload),
            content_type=content_type,
        )

    def payload(self, **overrides):
        value = {"message": "What is KolliPack?", "knowledge_scope": "global"}
        value.update(overrides)
        return value

    def test_anonymous_request_needs_no_entitlement_and_passes_only_public_context(self):
        answer = {
            "schema_version": "1.0",
            "type": "answer",
            "message": "KolliPack is a packaging-engineering application.",
        }
        with patch(
            "packagingapp.assistant.public_views.ask_public_external",
            return_value=answer,
        ) as service:
            response = self.post(self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["response"], answer)
        call = service.call_args.kwargs
        self.assertEqual(
            set(call),
            {
                "session_key",
                "message",
                "expert_context",
                "knowledge_context",
                "config",
            },
        )
        self.assertEqual(call["expert_context"], {
            "schema_version": "1.0",
            "surface": "public_site",
            "knowledge_scope": "global",
        })
        self.assertNotIn("tool_context", call)
        self.assertNotIn("user", call)

    def test_strict_schema_rejects_browser_authority_fields(self):
        forbidden_fields = (
            "state",
            "tool_context",
            "result",
            "knowledge",
            "documents",
            "provider",
            "model",
            "prompt",
            "timeout",
            "reasoning",
            "history",
            "proposal",
            "changes",
            "apply",
            "url",
            "database_id",
        )
        with patch("packagingapp.assistant.public_views.ask_public_external") as service:
            for field in forbidden_fields:
                with self.subTest(field=field):
                    response = self.post(self.payload(**{field: "browser-value"}))
                    self.assertEqual(response.status_code, 400)
            for missing in ("message", "knowledge_scope"):
                payload = self.payload()
                payload.pop(missing)
                self.assertEqual(self.post(payload).status_code, 400)
            self.assertEqual(
                self.post(self.payload(knowledge_scope="corrugated")).status_code,
                400,
            )
            service.assert_not_called()

    def test_method_content_message_and_body_bounds(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(
            self.client.post(self.url, data="{}", content_type="text/plain").status_code,
            415,
        )
        self.assertEqual(
            self.post(self.payload(message="x" * (MAX_PUBLIC_USER_MESSAGE_LENGTH + 1))).status_code,
            400,
        )
        oversized = b"{" + b" " * MAX_PUBLIC_EXPERT_REQUEST_BYTES + b"}"
        response = self.client.post(
            self.url,
            data=oversized,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 413)

    def test_feature_disabled_returns_safe_unavailable_without_session_or_service(self):
        client = Client()
        with override_settings(AI_PUBLIC_EXPERT_ENABLED=False), patch(
            "packagingapp.assistant.public_views.ask_public_external"
        ) as service:
            response = self.post(self.payload(), client=client)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["response"]["type"], "unavailable")
        self.assertNotIn("sessionid", client.cookies)
        service.assert_not_called()

    def test_public_expert_does_not_persist_question_answer_or_engineering_state(self):
        session = self.client.session
        session["existing_calculator_state"] = {"product_l": 300, "result": 45}
        session.save()
        before = deepcopy(dict(self.client.session))
        with patch(
            "packagingapp.assistant.public_views.ask_public_external",
            return_value={
                "schema_version": "1.0",
                "type": "answer",
                "message": "A public answer.",
            },
        ):
            response = self.post(
                self.payload(message="My utilization says 72%. What does that mean?")
            )
        self.assertEqual(response.status_code, 200)
        after = dict(self.client.session)
        self.assertEqual(after, before)
        serialized = json.dumps(after).lower()
        self.assertNotIn("72%", serialized)
        self.assertNotIn("public answer", serialized)
        self.assertNotIn("knowledge_context", serialized)

    def test_csrf_is_required_and_valid_same_origin_token_works(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(reverse("company_home"))
        self.assertEqual(page.status_code, 200)
        token = client.cookies["csrftoken"].value
        with patch(
            "packagingapp.assistant.public_views.ask_public_external",
            return_value={
                "schema_version": "1.0",
                "type": "answer",
                "message": "A public answer.",
            },
        ) as service:
            missing = client.post(
                self.url,
                data=json.dumps(self.payload()),
                content_type="application/json",
            )
            valid = client.post(
                self.url,
                data=json.dumps(self.payload()),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            )
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(valid.status_code, 200)
        service.assert_called_once()

    def test_authenticated_endpoints_remain_private(self):
        for name in ("assistant_context", "assistant_ask", "assistant_apply_proposal"):
            response = self.client.post(
                reverse(name),
                data=json.dumps({}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 401)


class PublicExpertDisabledDefaultTests(TestCase):
    def test_feature_defaults_off(self):
        with override_settings(AI_PUBLIC_EXPERT_ENABLED=False):
            response = self.client.get(reverse("company_home"))
        self.assertNotContains(response, "data-kollipack-public-expert")
