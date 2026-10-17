import json
from html.parser import HTMLParser
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from packagingapp.models import UserSubscription
from packagingapp.tools.container.state import default_container_config


class _AssistantMarkupParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.form_depth = 0
        self.assistant_form_depths = []
        self.assistant_openers = []
        self.json_scripts = {}
        self._current_json_script = None
        self._current_json_parts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "form":
            self.form_depth += 1
        if "data-kollipack-assistant" in attributes:
            self.assistant_form_depths.append(self.form_depth)
        if "data-kollipack-assistant-open" in attributes:
            self.assistant_openers.append(attributes)
        if tag == "script" and attributes.get("type") == "application/json":
            script_id = attributes.get("id")
            if script_id and script_id.startswith("containerAssistantStateFields"):
                self._current_json_script = script_id
                self._current_json_parts = []

    def handle_endtag(self, tag):
        if tag == "script" and self._current_json_script:
            self.json_scripts[self._current_json_script] = "".join(
                self._current_json_parts
            )
            self._current_json_script = None
            self._current_json_parts = []
        if tag == "form":
            self.form_depth -= 1

    def handle_data(self, data):
        if self._current_json_script:
            self._current_json_parts.append(data)


class AssistantUiTemplateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.plus_user = User.objects.create_user(
            username="assistant-ui-plus",
            password="test-password",
        )
        UserSubscription.objects.create(
            user=self.plus_user,
            plan=UserSubscription.Plan.PLUS,
        )
        self.free_user = User.objects.create_user(
            username="assistant-ui-free",
            password="test-password",
        )
        UserSubscription.objects.create(
            user=self.free_user,
            plan=UserSubscription.Plan.FREE,
        )

    @staticmethod
    def _parse(response):
        parser = _AssistantMarkupParser()
        parser.feed(response.content.decode("utf-8"))
        return parser

    def test_entitled_standalone_page_renders_shell_workspace_outside_tool_form(self):
        self.client.force_login(self.plus_user)

        response = self.client.get(reverse("container_selection_mode1"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["assistant_ui_enabled"])
        self.assertContains(response, "data-kollipack-assistant", count=2)
        self.assertContains(response, "data-kollipack-assistant-open", count=1)
        self.assertContains(response, 'data-assistant-surface="standalone"', count=1)
        self.assertContains(
            response,
            f'data-assistant-ask-url="{reverse("assistant_ask")}"',
            count=1,
        )
        self.assertContains(
            response,
            f'data-assistant-apply-url="{reverse("assistant_apply_proposal")}"',
            count=1,
        )
        self.assertContains(response, "js/kollipack_assistant.js", count=1)

        parser = self._parse(response)
        self.assertEqual(parser.assistant_form_depths, [0])
        self.assertEqual(parser.assistant_openers[0]["type"], "button")

    def test_standalone_state_map_uses_the_shared_semantic_contract(self):
        self.client.force_login(self.plus_user)

        response = self.client.get(reverse("container_selection_mode1"))
        parser = self._parse(response)
        fields = json.loads(parser.json_scripts["containerAssistantStateFields"])

        expected_keys = [
            key for key in default_container_config().keys() if key != "action"
        ]
        self.assertEqual([field["key"] for field in fields], expected_keys)
        self.assertEqual(
            {field["key"] for field in fields if field["kind"] == "boolean"},
            {"r1", "r2", "r3"},
        )
        self.assertEqual(
            {field["key"]: field["name"] for field in fields},
            {key: key for key in expected_keys},
        )

    def test_free_and_anonymous_users_receive_no_active_assistant_surface(self):
        for user in (None, self.free_user):
            with self.subTest(user=getattr(user, "username", "anonymous")):
                self.client.logout()
                if user is not None:
                    self.client.force_login(user)
                response = self.client.get(reverse("container_selection_mode1"))
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context["assistant_ui_enabled"])
                self.assertNotContains(response, "data-kollipack-assistant")
                self.assertNotContains(response, "data-kollipack-assistant-open")
                self.assertNotContains(response, "js/kollipack_assistant.js")

    def test_public_box_size_calculator_remains_assistant_free(self):
        self.client.force_login(self.plus_user)

        response = self.client.get(reverse("container_selection_calculator"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["assistant_ui_enabled"])
        self.assertNotContains(response, "data-kollipack-assistant")
        self.assertNotContains(response, "data-kollipack-assistant-open")
        self.assertNotContains(response, "js/kollipack_assistant.js")

    def test_workflow_open_control_binds_explicitly_to_prefixed_container_step(self):
        self.client.force_login(self.plus_user)
        add_response = self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "container"},
        )
        self.assertEqual(add_response.status_code, 302)

        response = self.client.get(reverse("full_packaging_mode"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["assistant_ui_enabled"])
        parser = self._parse(response)
        self.assertEqual(parser.assistant_form_depths, [0])
        self.assertEqual(len(parser.assistant_openers), 1)
        opener = parser.assistant_openers[0]
        step = response.context["steps"][0]
        self.assertEqual(opener["type"], "button")
        self.assertEqual(opener["data-assistant-surface"], "workflow")
        self.assertEqual(opener["data-assistant-state-root-id"], "containerSelectionRoot_0")
        self.assertEqual(opener["data-assistant-step-ref"], step["assistant_step_ref"])
        self.assertNotContains(response, f">{step['assistant_step_ref']}<")

        fields = json.loads(parser.json_scripts["containerAssistantStateFields_0"])
        self.assertTrue(all(field["name"].endswith("_0") for field in fields))
        self.assertEqual(
            {field["key"] for field in fields},
            set(default_container_config()) - {"action"},
        )

    def test_workflow_free_user_receives_no_assistant_controls(self):
        self.client.force_login(self.free_user)
        self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "container"},
        )

        response = self.client.get(reverse("full_packaging_mode"))

        self.assertFalse(response.context["assistant_ui_enabled"])
        self.assertNotContains(response, "data-kollipack-assistant")
        self.assertNotContains(response, "data-kollipack-assistant-open")

    def test_rendered_configuration_exposes_no_provider_controls_or_secrets(self):
        self.client.force_login(self.plus_user)
        response = self.client.get(reverse("container_selection_mode1"))
        html = response.content.decode("utf-8")

        for forbidden in (
            "data-assistant-provider",
            "data-assistant-model",
            "OPENAI_API_KEY",
            "AI_EXTERNAL_PROVIDER_ID",
            "AI_EXTERNAL_PROVIDER_MODEL",
            "REDIS_URL",
            "reasoning_effort",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, html)

    def test_client_renders_provider_messages_with_text_content_only(self):
        self.client.force_login(self.plus_user)
        response = self.client.get(reverse("container_selection_mode1"))
        script = (
            Path(__file__).resolve().parents[2]
            / "static"
            / "js"
            / "kollipack_assistant.js"
        ).read_text(encoding="utf-8")

        self.assertIn("responseNode.textContent = response.message", script)
        self.assertIn("responseNode.replaceChildren(wrapper)", script)
        self.assertNotIn("responseNode.innerHTML", script)
        self.assertIn("applyApprovedFields(stateRoot, applied.fields)", script)
        self.assertIn('applyButton.textContent = "Apply changes"', script)
        self.assertIn('applyButton.className = "btn btn-app-outline kpa-apply"', script)
        self.assertIn('scrollNode.scrollTo({', script)
        self.assertIn('revealLatestInteraction();', script)
        self.assertIn('"Set product length to 320 mm."', script)
        self.assertIn('"Use R1 and R3 only."', script)
        self.assertIn(
            "This proposal has expired. Ask KolliPack Assistant again to create a new proposal.",
            script,
        )
        self.assertNotIn(">Apply changes<", response.content.decode("utf-8"))
        self.assertIn('event.preventDefault();\n            sendQuestion();', script)
        self.assertIn('latestResponseType === "proposal_preview"', script)
        self.assertIn(
            "Inputs changed since this proposal. Ask again to create a proposal for the current state.",
            script,
        )
        self.assertNotIn("sendQuestion();\n            }\n            markAnswerStale", script)
