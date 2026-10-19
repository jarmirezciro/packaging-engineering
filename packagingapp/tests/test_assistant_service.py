import json
from copy import deepcopy
from unittest.mock import patch

from django.test import SimpleTestCase

from packagingapp.assistant.contracts import (
    ASSISTANT_KNOWLEDGE_GAP_MESSAGE,
    ASSISTANT_RESPONSE_SCHEMA_VERSION,
    MAX_ASSISTANT_MESSAGE_LENGTH,
    MAX_USER_MESSAGE_LENGTH,
    AssistantMessageValidationError,
    AssistantResponseTooLargeError,
    AssistantResponseValidationError,
    parse_assistant_response,
    validate_assistant_response,
    validate_tool_context,
    validate_user_message,
)
from packagingapp.assistant.prompts import (
    ASSISTANT_INSTRUCTIONS_SCHEMA_VERSION,
    READ_ONLY_CAPABILITY,
)
from packagingapp.assistant.providers import (
    UnknownAssistantProvider,
    get_assistant_provider,
)
from packagingapp.assistant.providers.fake import FakeAssistantProvider
from packagingapp.assistant.service import (
    ASSISTANT_INVALID_REQUEST,
    PROVIDER_INVALID_RESPONSE,
    PROVIDER_RESPONSE_TOO_LARGE,
    PROVIDER_TIMEOUT,
    PROVIDER_UNAVAILABLE,
    UNSUPPORTED_CONTEXT_VERSION,
    AssistantServiceError,
    ask,
)
from packagingapp.tools.container.assistant import build_container_tool_context
from packagingapp.tools.container.state import default_container_config


def ready_context():
    config = default_container_config()
    config.update(
        {
            "mode": "single",
            "product_source": "manual",
            "product_l": "10",
            "product_w": "8",
            "product_h": "6",
            "desired_qty": "4",
            "r1": True,
            "r2": True,
            "r3": True,
            "container_source": "manual",
            "box_l": "40",
            "box_w": "30",
            "box_h": "20",
        }
    )
    context = build_container_tool_context(config=config)
    assert context["tool"]["calculation_status"] == "ready"
    return context


def complete_context():
    context = deepcopy(ready_context())
    context["tool"]["calculation_status"] = "complete"
    context["result"] = {
        "kind": "selection",
        "max_quantity": {"value": 24, "unit": "pcs"},
    }
    context["explanation_facts"].append(
        {
            "code": "maximum_geometric_quantity",
            "value": 24,
            "unit": "pcs",
            "basis": "engine_output",
        }
    )
    return validate_tool_context(context)


class AssistantResponseContractTests(SimpleTestCase):
    def setUp(self):
        self.context = complete_context()

    def test_answer_accepts_only_existing_explanation_fact_codes(self):
        response = validate_assistant_response(
            {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "answer",
                "message": "The current result reports 24 units.",
                "fact_refs": ["maximum_geometric_quantity"],
            },
            tool_context=self.context,
        )

        self.assertEqual(response["fact_refs"], ["maximum_geometric_quantity"])

        invalid = dict(response)
        invalid["fact_refs"] = ["invented_capacity_fact"]
        with self.assertRaises(AssistantResponseValidationError):
            validate_assistant_response(invalid, tool_context=self.context)

    def test_response_schema_rejects_missing_extra_and_unknown_fields(self):
        invalid_responses = (
            {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "answer",
                "fact_refs": [],
            },
            {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "answer",
                "message": "Safe text.",
                "fact_refs": [],
                "chain_of_thought": "must never enter the contract",
            },
            {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "run_calculation",
                "message": "Unsafe action.",
            },
            {
                "schema_version": "2.0",
                "type": "clarifying_question",
                "message": "Question?",
            },
            {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "unavailable",
                "message": "Provider internals are unavailable: secret detail.",
            },
        )
        for response in invalid_responses:
            with self.subTest(response=response), self.assertRaises(
                AssistantResponseValidationError
            ):
                validate_assistant_response(response, tool_context=self.context)

    def test_provider_text_rejects_html_urls_controls_and_overlong_content(self):
        messages = (
            "<script>alert('x')</script>",
            "Open https://example.test/unsafe",
            "Unsafe\x00control",
        )
        for message in messages:
            with self.subTest(message=message), self.assertRaises(
                AssistantResponseValidationError
            ):
                validate_assistant_response(
                    {
                        "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                        "type": "clarifying_question",
                        "message": message,
                    },
                    tool_context=self.context,
                )

        with self.assertRaises(AssistantResponseTooLargeError):
            validate_assistant_response(
                {
                    "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                    "type": "answer",
                    "message": "x" * (MAX_ASSISTANT_MESSAGE_LENGTH + 1),
                    "fact_refs": [],
                },
                tool_context=self.context,
            )

    def test_knowledge_gap_is_typed_and_requires_application_owned_wording(self):
        response = validate_assistant_response(
            {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "knowledge_gap",
                "message": ASSISTANT_KNOWLEDGE_GAP_MESSAGE,
            },
            tool_context=self.context,
        )
        self.assertEqual(response["type"], "knowledge_gap")
        self.assertNotIn("fact_refs", response)

        with self.assertRaises(AssistantResponseValidationError):
            validate_assistant_response(
                {
                    "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                    "type": "knowledge_gap",
                    "message": "Store this question with provider-selected metadata.",
                },
                tool_context=self.context,
            )

    def test_json_parsing_is_strict_and_bounded(self):
        serialized = json.dumps(
            {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "clarifying_question",
                "message": "What should I explain?",
            }
        )
        parsed = parse_assistant_response(serialized, tool_context=self.context)
        self.assertEqual(parsed["type"], "clarifying_question")

        for candidate in ("{bad-json", "[]", b"\xff"):
            with self.subTest(candidate=candidate), self.assertRaises(
                AssistantResponseValidationError
            ):
                parse_assistant_response(candidate, tool_context=self.context)

    def test_user_message_contract_is_explicit(self):
        self.assertEqual(validate_user_message("  Explain this.  "), "Explain this.")
        for value in (None, "", "   ", "bad\x00text", "x" * (MAX_USER_MESSAGE_LENGTH + 1)):
            with self.subTest(value=type(value).__name__), self.assertRaises(
                AssistantMessageValidationError
            ):
                validate_user_message(value)


class AssistantServiceTests(SimpleTestCase):
    def test_fake_provider_success_modes_return_valid_contracts(self):
        answer_provider = FakeAssistantProvider("success_answer")
        answer = ask(
            message="Explain the capacity.",
            tool_context=complete_context(),
            provider=answer_provider,
            timeout_seconds=2.5,
        )
        self.assertEqual(answer["type"], "answer")
        self.assertEqual(answer["fact_refs"], ["maximum_geometric_quantity"])
        self.assertEqual(answer_provider.call_count, 1)
        self.assertEqual(answer_provider.last_timeout_seconds, 2.5)

        clarification = ask(
            message="Help me.",
            tool_context=ready_context(),
            provider=FakeAssistantProvider("success_clarification"),
        )
        self.assertEqual(clarification["type"], "clarifying_question")

        knowledge_gap = ask(
            message="Ask an unsupported knowledge question.",
            tool_context=ready_context(),
            provider=FakeAssistantProvider("success_knowledge_gap"),
        )
        self.assertEqual(knowledge_gap["type"], "knowledge_gap")
        self.assertEqual(knowledge_gap["message"], ASSISTANT_KNOWLEDGE_GAP_MESSAGE)

    def test_fake_answer_respects_every_tool_context_status(self):
        contexts = {}
        empty = build_container_tool_context(config=default_container_config())
        contexts["empty"] = empty

        partial_config = default_container_config()
        partial_config["product_l"] = "10"
        contexts["partial"] = build_container_tool_context(config=partial_config)

        invalid_config = default_container_config()
        invalid_config.update({"action": "run_single", "product_l": "bad"})
        contexts["invalid"] = build_container_tool_context(config=invalid_config)
        contexts["ready"] = ready_context()
        contexts["complete"] = complete_context()

        stale = deepcopy(ready_context())
        stale["tool"]["calculation_status"] = "stale"
        contexts["stale"] = validate_tool_context(stale)

        for status, context in contexts.items():
            with self.subTest(status=status):
                response = ask(
                    message="Explain the current state.",
                    tool_context=context,
                    provider=FakeAssistantProvider(),
                )
                self.assertEqual(response["type"], "answer")
                if status != "complete":
                    self.assertNotIn("24 units", response["message"])

    def test_fake_provider_covers_valid_and_stale_proposal_candidates(self):
        context = ready_context()
        for mode, expected_count in (
            ("valid_single_proposal", 1),
            ("valid_multi_proposal", 3),
        ):
            with self.subTest(mode=mode):
                response = ask(
                    message="Set the requested inputs.",
                    tool_context=context,
                    provider=FakeAssistantProvider(mode),
                )
                self.assertEqual(response["type"], "propose_input_changes")
                self.assertEqual(len(response["changes"]), expected_count)
                self.assertEqual(
                    response["state_fingerprint"],
                    context["tool"]["state_fingerprint"],
                )

        stale = ask(
            message="Set product length to 320 mm.",
            tool_context=context,
            provider=FakeAssistantProvider("stale_proposal_fingerprint"),
        )
        self.assertEqual(stale["type"], "propose_input_changes")
        self.assertNotEqual(
            stale["state_fingerprint"], context["tool"]["state_fingerprint"]
        )

    def test_every_fake_failure_mode_fails_closed(self):
        expected_categories = {
            "malformed_response": PROVIDER_INVALID_RESPONSE,
            "unknown_response_type": PROVIDER_INVALID_RESPONSE,
            "missing_required_field": PROVIDER_INVALID_RESPONSE,
            "oversized_response": PROVIDER_RESPONSE_TOO_LARGE,
            "timeout": PROVIDER_TIMEOUT,
            "provider_error": PROVIDER_UNAVAILABLE,
            "invalid_fact_reference": PROVIDER_INVALID_RESPONSE,
            "unknown_proposal_field": PROVIDER_INVALID_RESPONSE,
            "invalid_proposal_unit": PROVIDER_INVALID_RESPONSE,
            "invalid_proposal_value_type": PROVIDER_INVALID_RESPONSE,
            "too_many_proposal_changes": PROVIDER_INVALID_RESPONSE,
            "extra_proposal_property": PROVIDER_INVALID_RESPONSE,
            "malformed_proposal": PROVIDER_INVALID_RESPONSE,
        }
        for mode, category in expected_categories.items():
            provider = FakeAssistantProvider(mode)
            with self.subTest(mode=mode), self.assertLogs(
                "packagingapp.assistant.service", level="WARNING"
            ) as captured:
                response = ask(
                    message="Explain safely.",
                    tool_context=complete_context(),
                    provider=provider,
                )
            self.assertEqual(
                response,
                {
                    "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                    "type": "unavailable",
                    "message": "The assistant is temporarily unavailable.",
                },
            )
            self.assertEqual(
                captured.records[0].assistant_failure_category,
                category,
            )
            self.assertEqual(provider.call_count, 1)

    def test_invalid_request_and_context_never_invoke_provider(self):
        provider = FakeAssistantProvider()
        cases = (
            ({"message": "", "tool_context": ready_context()}, ASSISTANT_INVALID_REQUEST),
            ({"message": "Explain.", "tool_context": {}}, UNSUPPORTED_CONTEXT_VERSION),
            (
                {
                    "message": "Explain.",
                    "tool_context": {
                        **ready_context(),
                        "unexpected_provider_field": "not allowed",
                    },
                },
                ASSISTANT_INVALID_REQUEST,
            ),
            (
                {
                    "message": "Explain.",
                    "tool_context": ready_context(),
                    "capability": "apply_changes",
                },
                ASSISTANT_INVALID_REQUEST,
            ),
        )
        for kwargs, expected_code in cases:
            with self.subTest(expected_code=expected_code), self.assertRaises(
                AssistantServiceError
            ) as raised:
                ask(provider=provider, **kwargs)
            self.assertEqual(raised.exception.code, expected_code)
        self.assertEqual(provider.call_count, 0)

    def test_provider_receives_only_detached_validated_inputs_and_instructions(self):
        class CapturingProvider:
            provider_id = "capture"

            def generate(self, **kwargs):
                self.kwargs = kwargs
                kwargs["tool_context"]["inputs"]["provider_mutation"] = True
                return {
                    "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                    "type": "answer",
                    "message": "The current inputs are ready for calculation.",
                    "fact_refs": [],
                }

        original = ready_context()
        provider = CapturingProvider()
        response = ask(
            message="  Explain current state.  ",
            tool_context=original,
            provider=provider,
        )

        self.assertEqual(response["type"], "answer")
        self.assertEqual(
            set(provider.kwargs),
            {
                "message",
                "tool_context",
                "knowledge_context",
                "instructions",
                "timeout_seconds",
            },
        )
        self.assertEqual(provider.kwargs["message"], "Explain current state.")
        self.assertEqual(
            provider.kwargs["instructions"].schema_version,
            ASSISTANT_INSTRUCTIONS_SCHEMA_VERSION,
        )
        self.assertEqual(provider.kwargs["instructions"].capability, READ_ONLY_CAPABILITY)
        self.assertNotIn("provider_mutation", original["inputs"])

    def test_failures_do_not_expose_or_log_raw_sensitive_content(self):
        class FailingProvider:
            provider_id = "unsafe provider id with secret"

            def generate(self, **_kwargs):
                raise RuntimeError("RAW-PROVIDER-SECRET")

        with self.assertLogs(
            "packagingapp.assistant.service", level="WARNING"
        ) as captured:
            response = ask(
                message="RAW-USER-MESSAGE-SECRET",
                tool_context=ready_context(),
                provider=FailingProvider(),
            )

        self.assertEqual(response["type"], "unavailable")
        logged = " ".join(record.getMessage() for record in captured.records)
        self.assertNotIn("RAW-USER-MESSAGE-SECRET", logged)
        self.assertNotIn("RAW-PROVIDER-SECRET", logged)
        self.assertEqual(captured.records[0].assistant_provider, "unknown")

    def test_service_does_not_call_container_calculation_engines(self):
        with patch(
            "packagingapp.tools.container.service.run_mode1_and_render"
        ) as render_engine, patch(
            "packagingapp.tools.container.service.compute_max_quantity_only"
        ) as capacity_engine:
            response = ask(
                message="Explain readiness.",
                tool_context=ready_context(),
                provider=FakeAssistantProvider(),
            )
        self.assertEqual(response["type"], "answer")
        render_engine.assert_not_called()
        capacity_engine.assert_not_called()

    def test_unknown_provider_name_fails_closed_and_registry_is_allow_listed(self):
        with self.assertRaises(UnknownAssistantProvider):
            get_assistant_provider("module.path.ArbitraryProvider")

        with self.assertLogs(
            "packagingapp.assistant.service", level="WARNING"
        ) as captured:
            response = ask(
                message="Explain readiness.",
                tool_context=ready_context(),
                provider_name="module.path.ArbitraryProvider",
            )
        self.assertEqual(response["type"], "unavailable")
        self.assertEqual(
            captured.records[0].assistant_failure_category,
            PROVIDER_UNAVAILABLE,
        )
