"""Central application policy for external assistant transmission."""

from __future__ import annotations

from dataclasses import dataclass
import json

from ..entitlements import AI_ASSISTANT, has_feature
from .configuration import (
    ExternalProviderConfiguration,
    is_supported_external_provider,
    load_external_provider_configuration,
)
from .contracts import (
    TOOL_CONTEXT_SCHEMA_VERSION,
    AssistantMessageValidationError,
    ToolContext,
    ToolContextValidationError,
    canonical_json,
    validate_tool_context,
    validate_user_message,
)
from .prompts import (
    READ_ONLY_CAPABILITY,
    AssistantInstructions,
    get_assistant_instructions,
)
from .clarification import (
    ClarificationContext,
    ClarificationContextError,
    canonical_clarification_json,
    validate_clarification_context,
)
from .knowledge import (
    KnowledgeContext,
    KnowledgeContextValidationError,
    canonical_knowledge_json,
    empty_knowledge_context,
    validate_knowledge_context,
)
from .throttle import (
    AssistantThrottle,
    DjangoCacheAtomicCounterBackend,
    THROTTLE_RATE_LIMITED,
    THROTTLE_UNAVAILABLE,
    derive_opaque_user_key,
)


READY = "ready"
NOT_ENABLED = "not_enabled"
INVALID_CONFIGURATION = "invalid_configuration"
MISSING_SHARED_CACHE = "missing_shared_cache"
MISSING_PROVIDER_CONFIG = "missing_provider_config"
MISSING_SECRET = "missing_secret"
MISSING_PRIVACY_POLICY = "missing_privacy_policy"
MISSING_KNOWLEDGE_PRIVACY_POLICY = "missing_knowledge_privacy_policy"
UNSUPPORTED_PROVIDER = "unsupported_provider"

AUTHENTICATION_REQUIRED = "authentication_required"
ASSISTANT_NOT_ENTITLED = "assistant_not_entitled"
UNSUPPORTED_CAPABILITY = "unsupported_capability"
UNSUPPORTED_CONTEXT_VERSION = "unsupported_context_version"
INVALID_EXTERNAL_REQUEST = "invalid_external_request"
PROVIDER_CONFIGURATION_MISMATCH = "provider_configuration_mismatch"
ALLOWED = "allowed"

# Tool Context remains the primary outbound allow-list.  These additional
# external-only denials make the initial private-catalogue policy explicit and
# mechanically enforceable before any provider adapter exists.
EXTERNAL_CONTEXT_FORBIDDEN_KEYS = frozenset(
    {
        "catalogue_name",
        "description",
        "material_name",
        "part_number",
        "private_name",
        "product_name",
    }
)


@dataclass(frozen=True)
class ExternalAssistantRequest:
    """The complete and exclusive payload eligible for provider transmission."""

    instructions: AssistantInstructions
    message: str
    tool_context: ToolContext
    knowledge_context: KnowledgeContext
    clarification_context: ClarificationContext | None


@dataclass(frozen=True)
class ExternalProviderReadiness:
    ready: bool
    outcome: str
    provider_id: str = ""
    model_id: str = ""
    timeout_seconds: float = 0.0


@dataclass(frozen=True)
class ExternalProviderDecision:
    allowed: bool
    outcome: str
    provider_id: str = ""
    model_id: str = ""
    timeout_seconds: float = 0.0
    retry_after_seconds: int | None = None


class ExternalAssistantRequestError(ValueError):
    def __init__(self, code: str, safe_message: str):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


def _validate_external_disclosure(value, *, path: str = "tool_context") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in EXTERNAL_CONTEXT_FORBIDDEN_KEYS:
                raise ExternalAssistantRequestError(
                    INVALID_EXTERNAL_REQUEST,
                    "Current Tool Context contains data excluded by external policy.",
                )
            _validate_external_disclosure(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_external_disclosure(child, path=f"{path}[{index}]")


def build_external_assistant_request(
    *,
    message: str,
    tool_context: ToolContext,
    knowledge_context: KnowledgeContext | None = None,
    clarification_context: ClarificationContext | None = None,
    capability: str = READ_ONLY_CAPABILITY,
) -> ExternalAssistantRequest:
    """Validate and detach the only data that an external adapter may receive."""
    try:
        validated_message = validate_user_message(message)
    except AssistantMessageValidationError as exc:
        raise ExternalAssistantRequestError(
            INVALID_EXTERNAL_REQUEST,
            "Assistant message is invalid.",
        ) from exc
    if capability != READ_ONLY_CAPABILITY:
        raise ExternalAssistantRequestError(
            UNSUPPORTED_CAPABILITY,
            "Assistant capability is not supported for external transmission.",
        )
    if not isinstance(tool_context, dict) or (
        tool_context.get("schema_version") != TOOL_CONTEXT_SCHEMA_VERSION
    ):
        raise ExternalAssistantRequestError(
            UNSUPPORTED_CONTEXT_VERSION,
            "Current Tool Context version is not supported.",
        )
    try:
        validated_context = validate_tool_context(tool_context)
        detached_context = json.loads(canonical_json(validated_context))
        _validate_external_disclosure(detached_context)
    except ToolContextValidationError as exc:
        raise ExternalAssistantRequestError(
            INVALID_EXTERNAL_REQUEST,
            "Current Tool Context is invalid.",
        ) from exc
    try:
        validated_knowledge = validate_knowledge_context(
            knowledge_context or empty_knowledge_context()
        )
        detached_knowledge = json.loads(canonical_knowledge_json(validated_knowledge))
    except KnowledgeContextValidationError as exc:
        raise ExternalAssistantRequestError(
            INVALID_EXTERNAL_REQUEST,
            "KolliPack Knowledge Context is invalid.",
        ) from exc
    detached_clarification = None
    if clarification_context is not None:
        try:
            validated_clarification = validate_clarification_context(
                clarification_context
            )
            detached_clarification = json.loads(
                canonical_clarification_json(validated_clarification)
            )
        except ClarificationContextError as exc:
            raise ExternalAssistantRequestError(
                INVALID_EXTERNAL_REQUEST,
                "Clarification Context is invalid.",
            ) from exc
    return ExternalAssistantRequest(
        instructions=get_assistant_instructions(capability),
        message=validated_message,
        tool_context=detached_context,
        knowledge_context=detached_knowledge,
        clarification_context=detached_clarification,
    )


def _build_throttle(config: ExternalProviderConfiguration) -> AssistantThrottle:
    return AssistantThrottle(
        requests=config.rate_limit_requests,
        window_seconds=config.rate_limit_window_seconds,
        backend=DjangoCacheAtomicCounterBackend(config.throttle_cache_alias),
    )


def evaluate_external_provider_readiness(
    *,
    config: ExternalProviderConfiguration | None = None,
    throttle: AssistantThrottle | None = None,
) -> ExternalProviderReadiness:
    """Evaluate static production prerequisites without raising or sending data."""
    config = config or load_external_provider_configuration()
    if config.errors:
        return ExternalProviderReadiness(False, INVALID_CONFIGURATION)
    try:
        throttle = throttle or _build_throttle(config)
    except Exception:
        return ExternalProviderReadiness(False, MISSING_SHARED_CACHE)
    if not throttle.is_deployment_safe:
        return ExternalProviderReadiness(False, MISSING_SHARED_CACHE)
    if not throttle.probe_backend().ready:
        return ExternalProviderReadiness(False, MISSING_SHARED_CACHE)
    if not config.enabled:
        return ExternalProviderReadiness(False, NOT_ENABLED)
    if not config.provider_id or not config.model_id or not config.secret_env_name:
        return ExternalProviderReadiness(False, MISSING_PROVIDER_CONFIG)
    if not is_supported_external_provider(config.provider_id):
        return ExternalProviderReadiness(False, UNSUPPORTED_PROVIDER)
    if not config.secret_present:
        return ExternalProviderReadiness(False, MISSING_SECRET)
    if not config.privacy.base_complete:
        return ExternalProviderReadiness(False, MISSING_PRIVACY_POLICY)
    if not config.privacy.knowledge_external_approved:
        return ExternalProviderReadiness(False, MISSING_KNOWLEDGE_PRIVACY_POLICY)
    return ExternalProviderReadiness(
        True,
        READY,
        provider_id=config.provider_id,
        model_id=config.model_id,
        timeout_seconds=config.timeout_seconds,
    )


def evaluate_external_provider_gate(
    *,
    user,
    request: ExternalAssistantRequest,
    config: ExternalProviderConfiguration | None = None,
    throttle: AssistantThrottle | None = None,
) -> ExternalProviderDecision:
    """Make the sole allow/deny decision before a provider adapter is invoked."""
    if not getattr(user, "is_authenticated", False):
        return ExternalProviderDecision(False, AUTHENTICATION_REQUIRED)
    if not has_feature(user, AI_ASSISTANT):
        return ExternalProviderDecision(False, ASSISTANT_NOT_ENTITLED)
    if request.instructions.capability != READ_ONLY_CAPABILITY:
        return ExternalProviderDecision(False, UNSUPPORTED_CAPABILITY)
    if request.tool_context.get("schema_version") != TOOL_CONTEXT_SCHEMA_VERSION:
        return ExternalProviderDecision(False, UNSUPPORTED_CONTEXT_VERSION)

    config = config or load_external_provider_configuration()
    try:
        throttle = throttle or _build_throttle(config)
    except Exception:
        return ExternalProviderDecision(False, MISSING_SHARED_CACHE)
    readiness = evaluate_external_provider_readiness(
        config=config,
        throttle=throttle,
    )
    if not readiness.ready:
        return ExternalProviderDecision(False, readiness.outcome)

    try:
        user_key = derive_opaque_user_key(getattr(user, "pk", None))
    except ValueError:
        return ExternalProviderDecision(False, AUTHENTICATION_REQUIRED)
    throttle_decision = throttle.check_and_consume(
        user_key=user_key,
        capability=request.instructions.capability,
    )
    if throttle_decision.outcome == THROTTLE_RATE_LIMITED:
        return ExternalProviderDecision(
            False,
            THROTTLE_RATE_LIMITED,
            provider_id=readiness.provider_id,
            model_id=readiness.model_id,
            timeout_seconds=readiness.timeout_seconds,
            retry_after_seconds=throttle_decision.retry_after_seconds,
        )
    if throttle_decision.outcome == THROTTLE_UNAVAILABLE:
        return ExternalProviderDecision(
            False,
            THROTTLE_UNAVAILABLE,
            provider_id=readiness.provider_id,
            model_id=readiness.model_id,
            timeout_seconds=readiness.timeout_seconds,
        )
    return ExternalProviderDecision(
        True,
        ALLOWED,
        provider_id=readiness.provider_id,
        model_id=readiness.model_id,
        timeout_seconds=readiness.timeout_seconds,
    )


__all__ = [
    "ExternalAssistantRequest",
    "ExternalAssistantRequestError",
    "ExternalProviderDecision",
    "ExternalProviderReadiness",
    "MISSING_KNOWLEDGE_PRIVACY_POLICY",
    "build_external_assistant_request",
    "evaluate_external_provider_gate",
    "evaluate_external_provider_readiness",
]
