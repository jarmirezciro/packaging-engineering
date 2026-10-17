"""Explicitly opt-in live OpenAI/Redis integration smoke test."""

import os
import tempfile
import json
from types import SimpleNamespace
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from packagingapp.assistant.configuration import (
    load_external_provider_configuration,
)
from packagingapp.assistant.evaluation import build_container_evaluation_cases
from packagingapp.assistant.policy import evaluate_external_provider_readiness
from packagingapp.assistant.providers import get_assistant_provider
from packagingapp.assistant.service import ask_external
from packagingapp.models import UserSubscription


LIVE_OPENAI = os.environ.get("KOLLIPACK_TEST_OPENAI_LIVE", "").strip() == "1"


@skipUnless(LIVE_OPENAI, "KOLLIPACK_TEST_OPENAI_LIVE=1 is not configured")
class OpenAILiveIntegrationTests(SimpleTestCase):
    def test_real_complete_container_explanation_through_full_gate(self):
        config = load_external_provider_configuration()
        readiness = evaluate_external_provider_readiness(config=config)
        if not readiness.ready:
            self.skipTest(f"External assistant readiness: {readiness.outcome}")
        if readiness.provider_id != "openai":
            self.skipTest("AI_EXTERNAL_PROVIDER_ID is not openai")

        with tempfile.TemporaryDirectory(
            prefix="kollipack-openai-live-test-"
        ) as media_root:
            cases = build_container_evaluation_cases(media_root=media_root)
            case = next(item for item in cases if item.name == "complete_single")
            response = ask_external(
                user=SimpleNamespace(
                    is_authenticated=True,
                    is_staff=True,
                    is_superuser=False,
                    pk="live-openai-integration-test",
                ),
                message=case.question,
                tool_context=case.tool_context,
                provider=get_assistant_provider("openai"),
                config=config,
            )

        self.assertEqual(response["type"], "answer")
        self.assertTrue(response["message"])


@skipUnless(LIVE_OPENAI, "KOLLIPACK_TEST_OPENAI_LIVE=1 is not configured")
class OpenAIAssistantAskEndpointLiveTests(TestCase):
    def test_real_authenticated_endpoint_reconstructs_and_answers(self):
        config = load_external_provider_configuration()
        readiness = evaluate_external_provider_readiness(config=config)
        if not readiness.ready:
            self.skipTest(f"External assistant readiness: {readiness.outcome}")
        if readiness.provider_id != "openai":
            self.skipTest("AI_EXTERNAL_PROVIDER_ID is not openai")

        User = get_user_model()
        user = User.objects.create_user(username="live-endpoint-openai")
        UserSubscription.objects.create(
            user=user,
            plan=UserSubscription.Plan.PLUS,
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)

        state = {
            "mode": "single",
            "action": "refresh",
            "product_source": "manual",
            "product_l": "200",
            "product_w": "100",
            "product_h": "80",
            "product_weight": "",
            "desired_qty": "20",
            "product_shape": "cuboid",
            "r1": True,
            "r2": True,
            "r3": True,
            "container_source": "manual",
            "box_l": "600",
            "box_w": "400",
            "box_h": "300",
            "box_thickness_mm": "",
            "box_weight": "",
            "box_max_payload": "",
        }

        with tempfile.TemporaryDirectory(
            prefix="kollipack-openai-endpoint-live-test-"
        ) as media_root, override_settings(MEDIA_ROOT=media_root):
            page = client.get(reverse("container_selection_mode1"))
            token = client.cookies["csrftoken"].value
            calculation_post = dict(state, action="run_single")
            for rotation in ("r1", "r2", "r3"):
                if calculation_post.pop(rotation):
                    calculation_post[rotation] = "on"
            calculated = client.post(
                reverse("container_selection_mode1"),
                calculation_post,
                HTTP_X_CSRFTOKEN=token,
            )
            self.assertEqual(calculated.status_code, 200)
            self.assertIsNotNone(calculated.context["result"])

            response = client.post(
                reverse("assistant_ask"),
                data=json.dumps(
                    {
                        "tool": "container_selection",
                        "surface": "standalone",
                        "state": state,
                        "message": "Explain this result.",
                    }
                ),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        assistant_response = response.json()["response"]
        self.assertEqual(assistant_response["type"], "answer")
        self.assertTrue(assistant_response["message"])
        self.assertIn("fact_refs", assistant_response)
