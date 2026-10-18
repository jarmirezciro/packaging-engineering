"""Dedicated policy boundary for anonymous Public Expert provider calls."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping

from django.conf import settings

from .configuration import (
    ExternalProviderConfiguration,
    is_supported_external_provider,
    load_external_provider_configuration,
)
from .prompts import AssistantInstructions
from .clarification import (
    ClarificationContext,
    ClarificationContextError,
    canonical_clarification_json,
    validate_clarification_context,
)
from .public_contracts import (
    PUBLIC_EXPERT_CAPABILITY,
    PublicExpertContext,
    PublicExpertValidationError,
    PublicKnowledgeContext,
    canonical_public_json,
    validate_public_expert_context,
    validate_public_knowledge_context,
    validate_public_user_message,
)
from .public_prompts import get_public_expert_instructions
from .public_throttle import (
    PUBLIC_THROTTLE_ALLOWED,
    PublicExpertThrottle,
)
from .throttle import DjangoCacheAtomicCounterBackend


PUBLIC_READY = "public_ready"
PUBLIC_NOT_ENABLED = "public_not_enabled"
PUBLIC_INVALID_CONFIGURATION = "public_invalid_configuration"
PUBLIC_MISSING_SHARED_CACHE = "public_missing_shared_cache"
PUBLIC_MISSING_PROVIDER_CONFIG = "public_missing_provider_config"
PUBLIC_MISSING_SECRET = "public_missing_secret"
PUBLIC_MISSING_PRIVACY_POLICY = "public_missing_privacy_policy"
PUBLIC_UNSUPPORTED_PROVIDER = "public_unsupported_provider"
PUBLIC_UNSUPPORTED_CAPABILITY = "public_unsupported_capability"
PUBLIC_INVALID_EXTERNAL_REQUEST = "public_invalid_external_request"
PUBLIC_PROVIDER_CONFIGURATION_MISMATCH = "public_provider_configuration_mismatch"
PUBLIC_ALLOWED = "public_allowed"


@dataclass(frozen=True)
class PublicExpertConfiguration:
    enabled: bool
    throttle_cache_alias: str
    session_rate_limit_requests: int
    session_rate_limit_window_seconds: int
    global_rate_limit_requests: int
    global_rate_limit_window_seconds: int
    max_output_tokens: int
    provider: ExternalProviderConfiguration
    errors: tuple[str, ...]


@dataclass(frozen=True)
class PublicExternalAssistantRequest:
    """The complete and exclusive public payload eligible for transmission."""

    instructions: AssistantInstructions
    message: str
    expert_context: PublicExpertContext
    knowledge_context: PublicKnowledgeContext
    clarification_context: ClarificationContext | None


@dataclass(frozen=True)
class PublicProviderDecision:
    allowed: bool
    outcome: str
    provider_id: str = ""
    model_id: str = ""
    timeout_seconds: float = 0.0
    max_output_tokens: int = 0
    retry_after_seconds: int | None = None


class PublicExternalRequestError(ValueError):
    def __init__(self, code: str, safe_message: str):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


def _strict_bool(value, name: str, errors: list[str]) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    errors.append(f"{name}_invalid")
    return False


def _positive_int(value, name: str, errors: list[str], *, maximum: int) -> int:
    if isinstance(value, bool):
        errors.append(f"{name}_invalid")
        return 0
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value)
    else:
        errors.append(f"{name}_invalid")
        return 0
    if parsed <= 0 or parsed > maximum:
        errors.append(f"{name}_invalid")
        return 0
    return parsed


def _bounded_string(value, name: str, errors: list[str], *, maximum: int) -> str:
    if not isinstance(value, str):
        errors.append(f"{name}_invalid")
        return ""
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or any(ord(char) < 32 for char in normalized):
        errors.append(f"{name}_invalid")
        return ""
    return normalized


def load_public_expert_configuration(
    *,
    environment: Mapping[str, str] | None = None,
) -> PublicExpertConfiguration:
    errors: list[str] = []
    provider = load_external_provider_configuration(environment=environment)
    enabled = _strict_bool(
        getattr(settings, "AI_PUBLIC_EXPERT_ENABLED", False),
        "public_expert_enabled",
        errors,
    )
    cache_alias = _bounded_string(
        getattr(
            settings,
            "AI_PUBLIC_EXPERT_THROTTLE_CACHE_ALIAS",
            getattr(settings, "AI_ASSISTANT_THROTTLE_CACHE_ALIAS", "assistant"),
        ),
        "public_throttle_cache_alias",
        errors,
        maximum=64,
    )
    session_requests = _positive_int(
        getattr(settings, "AI_PUBLIC_EXPERT_SESSION_RATE_LIMIT_REQUESTS", 6),
        "public_session_rate_limit_requests",
        errors,
        maximum=10_000,
    )
    session_window = _positive_int(
        getattr(settings, "AI_PUBLIC_EXPERT_SESSION_RATE_LIMIT_WINDOW_SECONDS", 600),
        "public_session_rate_limit_window_seconds",
        errors,
        maximum=86_400,
    )
    global_requests = _positive_int(
        getattr(settings, "AI_PUBLIC_EXPERT_GLOBAL_RATE_LIMIT_REQUESTS", 120),
        "public_global_rate_limit_requests",
        errors,
        maximum=100_000,
    )
    global_window = _positive_int(
        getattr(settings, "AI_PUBLIC_EXPERT_GLOBAL_RATE_LIMIT_WINDOW_SECONDS", 3_600),
        "public_global_rate_limit_window_seconds",
        errors,
        maximum=86_400,
    )
    max_output_tokens = _positive_int(
        getattr(settings, "AI_PUBLIC_EXPERT_MAX_OUTPUT_TOKENS", 1_000),
        "public_max_output_tokens",
        errors,
        maximum=2_000,
    )
    return PublicExpertConfiguration(
        enabled=enabled,
        throttle_cache_alias=cache_alias,
        session_rate_limit_requests=session_requests,
        session_rate_limit_window_seconds=session_window,
        global_rate_limit_requests=global_requests,
        global_rate_limit_window_seconds=global_window,
        max_output_tokens=max_output_tokens,
        provider=provider,
        errors=tuple(sorted(set(errors))),
    )


def public_expert_feature_enabled() -> bool:
    errors: list[str] = []
    enabled = _strict_bool(
        getattr(settings, "AI_PUBLIC_EXPERT_ENABLED", False),
        "public_expert_enabled",
        errors,
    )
    return enabled and not errors


def build_public_external_request(
    *,
    message: str,
    expert_context: PublicExpertContext,
    knowledge_context: PublicKnowledgeContext,
    clarification_context: ClarificationContext | None = None,
    capability: str = PUBLIC_EXPERT_CAPABILITY,
) -> PublicExternalAssistantRequest:
    if capability != PUBLIC_EXPERT_CAPABILITY:
        raise PublicExternalRequestError(
            PUBLIC_UNSUPPORTED_CAPABILITY,
            "Public Expert capability is not supported.",
        )
    try:
        validated_message = validate_public_user_message(message)
        validated_expert = validate_public_expert_context(expert_context)
        validated_knowledge = validate_public_knowledge_context(knowledge_context)
        detached_expert = json.loads(canonical_public_json(validated_expert))
        detached_knowledge = json.loads(canonical_public_json(validated_knowledge))
    except PublicExpertValidationError as exc:
        raise PublicExternalRequestError(
            PUBLIC_INVALID_EXTERNAL_REQUEST,
            "Public Expert request is invalid.",
        ) from exc
    detached_clarification = None
    if clarification_context is not None:
        try:
            detached_clarification = json.loads(
                canonical_clarification_json(
                    validate_clarification_context(clarification_context)
                )
            )
        except ClarificationContextError as exc:
            raise PublicExternalRequestError(
                PUBLIC_INVALID_EXTERNAL_REQUEST,
                "Public Clarification Context is invalid.",
            ) from exc
    return PublicExternalAssistantRequest(
        instructions=get_public_expert_instructions(),
        message=validated_message,
        expert_context=detached_expert,
        knowledge_context=detached_knowledge,
        clarification_context=detached_clarification,
    )


def build_public_throttle(config: PublicExpertConfiguration) -> PublicExpertThrottle:
    backend = DjangoCacheAtomicCounterBackend(config.throttle_cache_alias)
    return PublicExpertThrottle(
        session_requests=config.session_rate_limit_requests,
        session_window_seconds=config.session_rate_limit_window_seconds,
        global_requests=config.global_rate_limit_requests,
        global_window_seconds=config.global_rate_limit_window_seconds,
        backend=backend,
    )


def evaluate_public_provider_gate(
    *,
    session_key: str,
    request: PublicExternalAssistantRequest,
    config: PublicExpertConfiguration | None = None,
    throttle: PublicExpertThrottle | None = None,
) -> PublicProviderDecision:
    if request.instructions.capability != PUBLIC_EXPERT_CAPABILITY:
        return PublicProviderDecision(False, PUBLIC_UNSUPPORTED_CAPABILITY)
    config = config or load_public_expert_configuration()
    if config.errors or config.provider.errors:
        return PublicProviderDecision(False, PUBLIC_INVALID_CONFIGURATION)
    if not config.enabled:
        return PublicProviderDecision(False, PUBLIC_NOT_ENABLED)
    try:
        throttle = throttle or build_public_throttle(config)
    except Exception:
        return PublicProviderDecision(False, PUBLIC_MISSING_SHARED_CACHE)
    if not throttle.is_deployment_safe or not throttle.probe_backend().ready:
        return PublicProviderDecision(False, PUBLIC_MISSING_SHARED_CACHE)

    throttle_decision = throttle.check_and_consume(session_key=session_key)
    if throttle_decision.outcome != PUBLIC_THROTTLE_ALLOWED:
        return PublicProviderDecision(
            False,
            throttle_decision.outcome,
            retry_after_seconds=throttle_decision.retry_after_seconds,
        )

    provider = config.provider
    if not provider.enabled:
        return PublicProviderDecision(False, PUBLIC_NOT_ENABLED)
    if not provider.provider_id or not provider.model_id or not provider.secret_env_name:
        return PublicProviderDecision(False, PUBLIC_MISSING_PROVIDER_CONFIG)
    if not is_supported_external_provider(provider.provider_id):
        return PublicProviderDecision(False, PUBLIC_UNSUPPORTED_PROVIDER)
    if not provider.secret_present:
        return PublicProviderDecision(False, PUBLIC_MISSING_SECRET)
    if not provider.privacy.complete:
        return PublicProviderDecision(False, PUBLIC_MISSING_PRIVACY_POLICY)
    return PublicProviderDecision(
        True,
        PUBLIC_ALLOWED,
        provider_id=provider.provider_id,
        model_id=provider.model_id,
        timeout_seconds=provider.timeout_seconds,
        max_output_tokens=config.max_output_tokens,
    )


__all__ = [
    "PUBLIC_ALLOWED",
    "PUBLIC_INVALID_EXTERNAL_REQUEST",
    "PUBLIC_NOT_ENABLED",
    "PUBLIC_PROVIDER_CONFIGURATION_MISMATCH",
    "PublicExpertConfiguration",
    "PublicExternalAssistantRequest",
    "PublicExternalRequestError",
    "PublicProviderDecision",
    "build_public_external_request",
    "build_public_throttle",
    "evaluate_public_provider_gate",
    "load_public_expert_configuration",
    "public_expert_feature_enabled",
]
