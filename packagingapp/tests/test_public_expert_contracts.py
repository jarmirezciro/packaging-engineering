import json

from django.test import SimpleTestCase

from packagingapp.assistant.public_contracts import (
    MAX_PUBLIC_USER_MESSAGE_LENGTH,
    PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION,
    PublicExpertValidationError,
    build_public_expert_context,
    build_public_expert_response_json_schema,
    parse_public_expert_response,
    validate_public_user_message,
)


class PublicExpertContractTests(SimpleTestCase):
    def test_context_is_tiny_versioned_and_scope_owned(self):
        self.assertEqual(
            build_public_expert_context("global"),
            {
                "schema_version": "1.0",
                "surface": "public_site",
                "knowledge_scope": "global",
            },
        )
        self.assertEqual(
            build_public_expert_context("container_selection")["surface"],
            "public_tool",
        )
        with self.assertRaises(PublicExpertValidationError):
            build_public_expert_context("invented_tool")

    def test_message_limit_is_smaller_than_authenticated_contract(self):
        self.assertEqual(validate_public_user_message("  What is KolliPack?  "), "What is KolliPack?")
        with self.assertRaises(PublicExpertValidationError):
            validate_public_user_message("x" * (MAX_PUBLIC_USER_MESSAGE_LENGTH + 1))
        for invalid in (None, 1, {}, [], "", "   "):
            with self.subTest(invalid=invalid), self.assertRaises(PublicExpertValidationError):
                validate_public_user_message(invalid)

    def test_public_response_schema_structurally_has_no_action_fields(self):
        schema = build_public_expert_response_json_schema()
        self.assertEqual(
            set(schema["properties"]),
            {"schema_version", "type", "message"},
        )
        self.assertEqual(
            set(schema["properties"]["type"]["enum"]),
            {"answer", "clarifying_question", "unavailable"},
        )
        serialized = json.dumps(schema).lower()
        for forbidden in ("proposal", "apply", "action", "tool_context", "changes"):
            self.assertNotIn(forbidden, serialized)

    def test_response_rejects_html_urls_actions_and_unknown_properties(self):
        valid = {
            "schema_version": PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION,
            "type": "answer",
            "message": "KolliPack uses deterministic engineering tools.",
        }
        self.assertEqual(parse_public_expert_response(json.dumps(valid)), valid)
        invalid = (
            {**valid, "type": "propose_input_changes"},
            {**valid, "proposal": {}},
            {**valid, "message": "<script>alert(1)</script>"},
            {**valid, "message": "Visit https://example.test"},
        )
        for candidate in invalid:
            with self.subTest(candidate=candidate), self.assertRaises(PublicExpertValidationError):
                parse_public_expert_response(candidate)
