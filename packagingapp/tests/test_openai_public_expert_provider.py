import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from packagingapp.assistant.public_contracts import (
    build_public_expert_context,
    build_public_expert_response_json_schema,
)
from packagingapp.assistant.public_knowledge import retrieve_public_knowledge_context
from packagingapp.assistant.public_prompts import get_public_expert_instructions
from packagingapp.assistant.providers.openai import (
    OPENAI_PUBLIC_RESPONSE_SCHEMA_NAME,
    OpenAIAssistantProvider,
)


OPENAI_SETTINGS = {
    "AI_EXTERNAL_PROVIDER_ENABLED": True,
    "AI_EXTERNAL_PROVIDER_ID": "openai",
    "AI_EXTERNAL_PROVIDER_MODEL": "test-public-model",
    "AI_EXTERNAL_PROVIDER_SECRET_ENV": "KOLLIPACK_TEST_PUBLIC_OPENAI_KEY",
    "AI_EXTERNAL_PROVIDER_TIMEOUT_SECONDS": 5,
    "AI_EXTERNAL_PROVIDER_MAX_OUTPUT_TOKENS": 3000,
    "AI_EXTERNAL_PROVIDER_REASONING_EFFORT": "low",
}


def structured_response(payload):
    return SimpleNamespace(
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                status="completed",
                role="assistant",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text=json.dumps(payload, separators=(",", ":")),
                    )
                ],
            )
        ],
    )


@override_settings(**OPENAI_SETTINGS)
class OpenAIPublicExpertProviderTests(SimpleTestCase):
    def setUp(self):
        self.environment = patch.dict(
            "os.environ",
            {"KOLLIPACK_TEST_PUBLIC_OPENAI_KEY": "transport-only-test-key"},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_public_call_reuses_stateless_transport_with_narrow_schema_and_payload(self):
        client = SimpleNamespace(
            responses=SimpleNamespace(
                create=Mock(
                    return_value=structured_response(
                        {
                            "schema_version": "1.0",
                            "type": "answer",
                            "message": "KolliPack uses deterministic tools.",
                        }
                    )
                )
            )
        )
        factory = Mock(return_value=client)
        provider = OpenAIAssistantProvider(client_factory=factory)
        question = "What does KolliPack do?"
        expert_context = build_public_expert_context("global")
        knowledge_context = retrieve_public_knowledge_context(
            question, knowledge_scope="global"
        )

        candidate = provider.generate_public(
            message=question,
            expert_context=expert_context,
            instructions=get_public_expert_instructions(),
            timeout_seconds=4.5,
            max_output_tokens=1000,
            knowledge_context=knowledge_context,
        )

        self.assertEqual(candidate["type"], "answer")
        factory.assert_called_once_with(
            api_key="transport-only-test-key",
            timeout=4.5,
            max_retries=0,
        )
        request = client.responses.create.call_args.kwargs
        self.assertFalse(request["store"])
        self.assertEqual(request["max_output_tokens"], 1000)
        self.assertEqual(request["timeout"], 4.5)
        self.assertEqual(request["reasoning"], {"effort": "low"})
        self.assertEqual(
            request["text"]["format"],
            {
                "type": "json_schema",
                "name": OPENAI_PUBLIC_RESPONSE_SCHEMA_NAME,
                "strict": True,
                "schema": build_public_expert_response_json_schema(),
            },
        )
        self.assertEqual(
            [item["role"] for item in request["input"]],
            ["developer", "developer", "user"],
        )
        self.assertIn("Public Expert Context", request["input"][0]["content"][0]["text"])
        self.assertIn("Public Knowledge Context", request["input"][1]["content"][0]["text"])
        self.assertEqual(request["input"][2]["content"][0]["text"], question)
        for forbidden in (
            "tools",
            "tool_choice",
            "conversation",
            "previous_response_id",
            "background",
        ):
            self.assertNotIn(forbidden, request)
        transmitted = repr(request).lower()
        for forbidden in (
            "transport-only-test-key",
            "tool context json",
            "state_fingerprint",
            "session_key",
            "user_id",
            "catalogue_id",
            "threejs_scene",
            "placements",
        ):
            self.assertNotIn(forbidden, transmitted)

    def test_public_schema_cannot_accept_proposal_output(self):
        client = SimpleNamespace(
            responses=SimpleNamespace(
                create=Mock(
                    return_value=structured_response(
                        {
                            "schema_version": "1.0",
                            "type": "propose_input_changes",
                            "message": "",
                            "changes": [],
                        }
                    )
                )
            )
        )
        provider = OpenAIAssistantProvider(client_factory=Mock(return_value=client))
        candidate = provider.generate_public(
            message="Set width to 300 mm.",
            expert_context=build_public_expert_context("container_selection"),
            instructions=get_public_expert_instructions(),
            timeout_seconds=4.5,
            max_output_tokens=1000,
            knowledge_context=retrieve_public_knowledge_context(
                "Set width to 300 mm.", knowledge_scope="container_selection"
            ),
        )
        self.assertEqual(candidate["type"], "propose_input_changes")
        self.assertNotIn(
            "propose_input_changes",
            build_public_expert_response_json_schema()["properties"]["type"]["enum"],
        )
