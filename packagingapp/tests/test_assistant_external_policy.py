from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from packagingapp.assistant.configuration import (
    EXTERNAL_DISCLOSURE_POLICY_VERSION,
    load_external_provider_configuration,
)
from packagingapp.assistant.contracts import (
    ASSISTANT_RESPONSE_SCHEMA_VERSION,
)
from packagingapp.assistant.knowledge import retrieve_knowledge_context
from packagingapp.assistant.policy import (
    AUTHENTICATION_REQUIRED,
    ASSISTANT_NOT_ENTITLED,
    INVALID_CONFIGURATION,
    INVALID_EXTERNAL_REQUEST,
    MISSING_KNOWLEDGE_PRIVACY_POLICY,
    MISSING_PRIVACY_POLICY,
    MISSING_PROVIDER_CONFIG,
    MISSING_SECRET,
    MISSING_SHARED_CACHE,
    NOT_ENABLED,
    PROVIDER_CONFIGURATION_MISMATCH,
    READY,
    UNSUPPORTED_PROVIDER,
    ExternalAssistantRequestError,
    build_external_assistant_request,
    evaluate_external_provider_gate,
    evaluate_external_provider_readiness,
)
from packagingapp.assistant.providers.fake import FakeAssistantProvider
from packagingapp.assistant.service import ask_external
from packagingapp.assistant.throttle import (
    AssistantThrottle,
    CACHE_PROBE_READY,
    CacheBackendProbe,
    DeterministicAtomicCounterBackend,
    DjangoCacheAtomicCounterBackend,
    THROTTLE_RATE_LIMITED,
    THROTTLE_UNAVAILABLE,
)
from packagingapp.tools.container.assistant import build_container_tool_context
from packagingapp.tools.container.state import default_container_config


VALID_SETTINGS = {
    "AI_EXTERNAL_PROVIDER_ENABLED": True,
    "AI_EXTERNAL_PROVIDER_ID": "fake",
    "AI_EXTERNAL_PROVIDER_MODEL": "fake-read-only-model",
    "AI_EXTERNAL_PROVIDER_SECRET_ENV": "KOLLIPACK_TEST_PROVIDER_SECRET",
    "AI_EXTERNAL_PROVIDER_TIMEOUT_SECONDS": 5,
    "AI_ASSISTANT_THROTTLE_CACHE_ALIAS": "assistant",
    "AI_ASSISTANT_RATE_LIMIT_REQUESTS": 2,
    "AI_ASSISTANT_RATE_LIMIT_WINDOW_SECONDS": 60,
    "AI_EXTERNAL_PROVIDER_PRIVACY_APPROVED": True,
    "AI_EXTERNAL_DISCLOSURE_POLICY_VERSION": EXTERNAL_DISCLOSURE_POLICY_VERSION,
    "AI_EXTERNAL_PROVIDER_TRAINING_OPT_OUT_CONFIRMED": True,
    "AI_EXTERNAL_PROVIDER_RETENTION_POLICY": "approved-retention-v1",
    "AI_EXTERNAL_PROVIDER_DATA_RESIDENCY_POLICY": "approved-region-v1",
    "AI_EXTERNAL_PROVIDER_DELETION_POLICY": "approved-deletion-v1",
    "AI_EXTERNAL_PROVIDER_INCIDENT_POLICY": "approved-incident-v1",
    "AI_EXTERNAL_PROVIDER_USER_DISCLOSURE_VERSION": "assistant-disclosure-v1",
    "AI_ASSISTANT_KNOWLEDGE_EXTERNAL_APPROVED": True,
}


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
    return build_container_tool_context(config=config)


def entitled_user(pk=7001):
    return SimpleNamespace(
        is_authenticated=True,
        is_staff=True,
        is_superuser=False,
        pk=pk,
    )


def unentitled_user(pk=7002):
    return SimpleNamespace(
        is_authenticated=True,
        is_staff=False,
        is_superuser=False,
        pk=pk,
        subscription=None,
    )


def shared_throttle(*, requests=2, backend=None):
    backend = backend or DeterministicAtomicCounterBackend(
        deployment_shared=True,
    )
    return AssistantThrottle(
        requests=requests,
        window_seconds=60,
        backend=backend,
    )


@override_settings(**VALID_SETTINGS)
class ExternalProviderConfigurationTests(SimpleTestCase):
    def configured(self, *, secret=True):
        environment = (
            {"KOLLIPACK_TEST_PROVIDER_SECRET": "placeholder-test-secret"}
            if secret
            else {}
        )
        return load_external_provider_configuration(environment=environment)

    def test_complete_configuration_can_report_ready_with_shared_throttle(self):
        readiness = evaluate_external_provider_readiness(
            config=self.configured(),
            throttle=shared_throttle(),
        )
        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.outcome, READY)
        self.assertEqual(readiness.provider_id, "fake")

    @override_settings(
        CACHES={
            "assistant": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": "redis://example.invalid:6379/0",
            }
        }
    )
    def test_configured_shared_cache_must_pass_live_probe(self):
        with patch.object(
            DjangoCacheAtomicCounterBackend,
            "probe",
            return_value=CacheBackendProbe(True, CACHE_PROBE_READY),
        ):
            readiness = evaluate_external_provider_readiness(
                config=self.configured(),
            )
        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.outcome, READY)

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        }
    )
    def test_missing_unknown_and_unsafe_cache_aliases_fail_closed(self):
        valid = self.configured()
        for alias in ("assistant", "default", "unknown"):
            with self.subTest(alias=alias):
                readiness = evaluate_external_provider_readiness(
                    config=replace(valid, throttle_cache_alias=alias),
                )
                self.assertFalse(readiness.ready)
                self.assertEqual(readiness.outcome, MISSING_SHARED_CACHE)

    @override_settings(
        CACHES={
            "assistant": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": "",
                "OPTIONS": {
                    "socket_connect_timeout": 0.1,
                    "socket_timeout": 0.1,
                },
            }
        }
    )
    def test_redis_backend_without_connection_url_fails_closed(self):
        readiness = evaluate_external_provider_readiness(
            config=self.configured(),
        )
        self.assertFalse(readiness.ready)
        self.assertEqual(readiness.outcome, MISSING_SHARED_CACHE)

    def test_readiness_has_explicit_fail_closed_outcomes(self):
        valid = self.configured()
        cases = (
            (replace(valid, enabled=False), NOT_ENABLED, shared_throttle()),
            (
                replace(valid, model_id=""),
                MISSING_PROVIDER_CONFIG,
                shared_throttle(),
            ),
            (
                replace(valid, provider_id="unregistered"),
                UNSUPPORTED_PROVIDER,
                shared_throttle(),
            ),
            (replace(valid, secret_present=False), MISSING_SECRET, shared_throttle()),
            (
                replace(valid, privacy=replace(valid.privacy, approved=False)),
                MISSING_PRIVACY_POLICY,
                shared_throttle(),
            ),
            (
                replace(
                    valid,
                    privacy=replace(
                        valid.privacy,
                        knowledge_external_approved=False,
                    ),
                ),
                MISSING_KNOWLEDGE_PRIVACY_POLICY,
                shared_throttle(),
            ),
            (
                valid,
                MISSING_SHARED_CACHE,
                shared_throttle(
                    backend=DeterministicAtomicCounterBackend(
                        deployment_shared=False,
                    )
                ),
            ),
        )
        for config, expected, throttle in cases:
            with self.subTest(expected=expected):
                readiness = evaluate_external_provider_readiness(
                    config=config,
                    throttle=throttle,
                )
                self.assertFalse(readiness.ready)
                self.assertEqual(readiness.outcome, expected)

    @override_settings(
        AI_EXTERNAL_PROVIDER_ENABLED="sometimes",
        AI_ASSISTANT_RATE_LIMIT_REQUESTS="many",
        AI_ASSISTANT_RATE_LIMIT_WINDOW_SECONDS=0,
        AI_EXTERNAL_PROVIDER_TIMEOUT_SECONDS=31,
        AI_EXTERNAL_PROVIDER_MAX_OUTPUT_TOKENS=0,
        AI_EXTERNAL_PROVIDER_REASONING_EFFORT="extreme",
    )
    def test_malformed_configuration_is_recorded_not_silently_defaulted(self):
        config = self.configured()
        self.assertTrue(config.errors)
        self.assertIn("provider_max_output_tokens_invalid", config.errors)
        self.assertIn("provider_reasoning_effort_invalid", config.errors)
        readiness = evaluate_external_provider_readiness(
            config=config,
            throttle=shared_throttle(),
        )
        self.assertEqual(readiness.outcome, INVALID_CONFIGURATION)

    @override_settings(
        AI_EXTERNAL_PROVIDER_ENABLED=False,
        AI_EXTERNAL_PROVIDER_ID="",
        AI_EXTERNAL_PROVIDER_MODEL="",
        AI_EXTERNAL_PROVIDER_SECRET_ENV="",
        AI_EXTERNAL_PROVIDER_PRIVACY_APPROVED=False,
        AI_EXTERNAL_PROVIDER_TRAINING_OPT_OUT_CONFIRMED=False,
    )
    def test_absent_external_configuration_defaults_to_disabled(self):
        config = load_external_provider_configuration(environment={})
        self.assertFalse(config.enabled)
        self.assertFalse(config.secret_present)
        readiness = evaluate_external_provider_readiness(
            config=config,
            throttle=shared_throttle(),
        )
        self.assertEqual(readiness.outcome, NOT_ENABLED)

    @override_settings(
        AI_EXTERNAL_PROVIDER_ENABLED=False,
        AI_EXTERNAL_PROVIDER_ID="",
        AI_EXTERNAL_PROVIDER_MODEL="",
        AI_EXTERNAL_PROVIDER_SECRET_ENV="",
        AI_EXTERNAL_PROVIDER_PRIVACY_APPROVED=False,
        AI_EXTERNAL_PROVIDER_TRAINING_OPT_OUT_CONFIRMED=False,
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        },
    )
    def test_missing_cache_precedes_disabled_state_until_infrastructure_is_ready(self):
        config = load_external_provider_configuration(environment={})
        without_cache = evaluate_external_provider_readiness(config=config)
        with_shared_cache = evaluate_external_provider_readiness(
            config=config,
            throttle=shared_throttle(),
        )
        self.assertEqual(without_cache.outcome, MISSING_SHARED_CACHE)
        self.assertEqual(with_shared_cache.outcome, NOT_ENABLED)


@override_settings(**VALID_SETTINGS)
class ExternalProviderGateTests(SimpleTestCase):
    def setUp(self):
        self.config = load_external_provider_configuration(
            environment={
                "KOLLIPACK_TEST_PROVIDER_SECRET": "RAW-TEST-PROVIDER-SECRET"
            }
        )
        self.context = ready_context()

    def test_allowed_request_invokes_fake_only_after_gate(self):
        provider = FakeAssistantProvider()
        response = ask_external(
            user=entitled_user(),
            message="Explain the current state.",
            tool_context=self.context,
            provider=provider,
            config=self.config,
            throttle=shared_throttle(),
        )
        self.assertEqual(response["type"], "answer")
        self.assertEqual(provider.call_count, 1)

    def test_configured_provider_is_selected_inside_service_after_gate(self):
        provider = FakeAssistantProvider()
        with patch(
            "packagingapp.assistant.service.get_assistant_provider",
            return_value=provider,
        ) as provider_registry:
            response = ask_external(
                user=entitled_user(),
                message="Explain the current state.",
                tool_context=self.context,
                config=self.config,
                throttle=shared_throttle(),
            )

        self.assertEqual(response["type"], "answer")
        provider_registry.assert_called_once_with("fake")
        self.assertEqual(provider.call_count, 1)

    def test_gate_denials_never_invoke_provider(self):
        cases = (
            (
                "not_authenticated",
                SimpleNamespace(is_authenticated=False, pk=None),
                self.config,
                shared_throttle(),
                AUTHENTICATION_REQUIRED,
            ),
            (
                "not_entitled",
                unentitled_user(),
                self.config,
                shared_throttle(),
                ASSISTANT_NOT_ENTITLED,
            ),
            (
                "disabled",
                entitled_user(),
                replace(self.config, enabled=False),
                shared_throttle(),
                NOT_ENABLED,
            ),
            (
                "missing_provider_config",
                entitled_user(),
                replace(self.config, model_id=""),
                shared_throttle(),
                MISSING_PROVIDER_CONFIG,
            ),
            (
                "missing_privacy",
                entitled_user(),
                replace(
                    self.config,
                    privacy=replace(self.config.privacy, approved=False),
                ),
                shared_throttle(),
                MISSING_PRIVACY_POLICY,
            ),
            (
                "unsupported_provider",
                entitled_user(),
                replace(self.config, provider_id="unregistered"),
                shared_throttle(),
                UNSUPPORTED_PROVIDER,
            ),
            (
                "missing_shared_cache",
                entitled_user(),
                self.config,
                shared_throttle(
                    backend=DeterministicAtomicCounterBackend(
                        deployment_shared=False,
                    )
                ),
                MISSING_SHARED_CACHE,
            ),
        )
        external_request = build_external_assistant_request(
            message="Explain safely.",
            tool_context=self.context,
        )
        for name, user, config, throttle, expected in cases:
            with self.subTest(name=name):
                decision = evaluate_external_provider_gate(
                    user=user,
                    request=external_request,
                    config=config,
                    throttle=throttle,
                )
                self.assertEqual(decision.outcome, expected)

                provider = FakeAssistantProvider()
                with self.assertLogs(
                    "packagingapp.assistant.service", level="WARNING"
                ):
                    response = ask_external(
                        user=user,
                        message="Explain safely.",
                        tool_context=self.context,
                        provider=provider,
                        config=config,
                        throttle=throttle,
                    )
                self.assertEqual(response["type"], "unavailable")
                self.assertEqual(provider.call_count, 0)

    def test_rate_limit_rejects_before_second_provider_invocation(self):
        provider = FakeAssistantProvider()
        throttle = shared_throttle(requests=1)

        first = ask_external(
            user=entitled_user(),
            message="First explanation.",
            tool_context=self.context,
            provider=provider,
            config=self.config,
            throttle=throttle,
        )
        with self.assertLogs(
            "packagingapp.assistant.service", level="WARNING"
        ) as captured:
            second = ask_external(
                user=entitled_user(),
                message="Second explanation.",
                tool_context=self.context,
                provider=provider,
                config=self.config,
                throttle=throttle,
            )

        self.assertEqual(first["type"], "answer")
        self.assertEqual(second["type"], "unavailable")
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(captured.records[0].assistant_gate_outcome, THROTTLE_RATE_LIMITED)

    def test_cache_failure_rejects_before_provider_invocation(self):
        class FailingBackend:
            is_deployment_shared = True

            def increment(self, key, *, ttl_seconds):
                raise RuntimeError("RAW-CACHE-FAILURE")

        provider = FakeAssistantProvider()
        throttle = shared_throttle(backend=FailingBackend())
        with self.assertLogs(
            "packagingapp.assistant.service", level="WARNING"
        ) as captured:
            response = ask_external(
                user=entitled_user(),
                message="Explain safely.",
                tool_context=self.context,
                provider=provider,
                config=self.config,
                throttle=throttle,
            )

        self.assertEqual(response["type"], "unavailable")
        self.assertEqual(provider.call_count, 0)
        self.assertEqual(captured.records[0].assistant_gate_outcome, THROTTLE_UNAVAILABLE)
        self.assertNotIn("RAW-CACHE-FAILURE", captured.records[0].getMessage())

    def test_configured_provider_must_match_injected_adapter(self):
        class WrongProvider(FakeAssistantProvider):
            provider_id = "wrong"

        provider = WrongProvider()
        with self.assertLogs(
            "packagingapp.assistant.service", level="WARNING"
        ) as captured:
            response = ask_external(
                user=entitled_user(),
                message="Explain safely.",
                tool_context=self.context,
                provider=provider,
                config=self.config,
                throttle=shared_throttle(),
            )
        self.assertEqual(response["type"], "unavailable")
        self.assertEqual(provider.call_count, 0)
        self.assertEqual(
            captured.records[0].assistant_gate_outcome,
            PROVIDER_CONFIGURATION_MISMATCH,
        )

    def test_external_request_rejects_private_catalogue_identity_fields(self):
        unsafe = deepcopy(self.context)
        unsafe["inputs"]["product"]["part_number"] = "PRIVATE-123"
        with self.assertRaises(ExternalAssistantRequestError) as raised:
            build_external_assistant_request(
                message="Compare this item.",
                tool_context=unsafe,
            )
        self.assertEqual(raised.exception.code, INVALID_EXTERNAL_REQUEST)

    def test_external_request_carries_only_validated_approved_knowledge(self):
        knowledge = retrieve_knowledge_context(
            "What is sealing margin?",
            active_tool="container_selection",
        )

        request = build_external_assistant_request(
            message="What is sealing margin?",
            tool_context=self.context,
            knowledge_context=knowledge,
        )

        self.assertEqual(request.knowledge_context["status"], "available")
        self.assertTrue(request.knowledge_context["sections"])
        serialized = repr(request.knowledge_context)
        self.assertNotIn("C:\\PackagingEngineering", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("session", serialized)

    def test_provider_payload_excludes_user_session_and_secret_data(self):
        class CapturingProvider:
            provider_id = "fake"
            call_count = 0

            def generate(self, **kwargs):
                self.call_count += 1
                self.kwargs = kwargs
                return {
                    "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                    "type": "answer",
                    "message": "The current inputs are ready for calculation.",
                    "fact_refs": [],
                }

        provider = CapturingProvider()
        user = entitled_user(pk=987654321)
        response = ask_external(
            user=user,
            message="Explain current state.",
            tool_context=self.context,
            provider=provider,
            config=self.config,
            throttle=shared_throttle(),
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
        transmitted = repr(provider.kwargs)
        for excluded in (
            "987654321",
            "RAW-TEST-PROVIDER-SECRET",
            "user_id",
            "email",
            "session_id",
            "part_number",
            "catalogue_name",
            "'threejs_scene':",
            "'placements':",
        ):
            self.assertNotIn(excluded, transmitted)
