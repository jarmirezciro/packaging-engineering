"""Application-owned orchestration for KolliPack's read-only assistant."""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from .contracts import (
    TOOL_CONTEXT_SCHEMA_VERSION,
    AssistantMessageValidationError,
    AssistantResponse,
    AssistantResponseTooLargeError,
    AssistantResponseValidationError,
    ToolContext,
    ToolContextValidationError,
    build_unavailable_response,
    canonical_json,
    validate_tool_context,
    validate_user_message,
)
from .actions import (
    ProviderProposalCandidate,
    parse_assistant_provider_candidate,
)
from .prompts import READ_ONLY_CAPABILITY, get_assistant_instructions
from .knowledge import (
    KnowledgeContext,
    KnowledgeContextValidationError,
    canonical_knowledge_json,
    empty_knowledge_context,
    validate_knowledge_context,
)
from .policy import (
    PROVIDER_CONFIGURATION_MISMATCH,
    ExternalAssistantRequestError,
    build_external_assistant_request,
    evaluate_external_provider_gate,
)
from .providers import DEFAULT_ASSISTANT_PROVIDER, get_assistant_provider
from .providers.base import (
    AssistantProvider,
    AssistantProviderError,
    AssistantProviderInvalidResponse,
    AssistantProviderResponseTooLarge,
    AssistantProviderTimeout,
)


logger = logging.getLogger(__name__)

DEFAULT_PROVIDER_TIMEOUT_SECONDS = 10.0
MAX_PROVIDER_TIMEOUT_SECONDS = 30.0

PROVIDER_TIMEOUT = "provider_timeout"
PROVIDER_UNAVAILABLE = "provider_unavailable"
PROVIDER_INVALID_RESPONSE = "provider_invalid_response"
PROVIDER_RESPONSE_TOO_LARGE = "provider_response_too_large"
UNSUPPORTED_CONTEXT_VERSION = "unsupported_context_version"
ASSISTANT_INVALID_REQUEST = "assistant_invalid_request"
ASSISTANT_INTERNAL_ERROR = "assistant_internal_error"

ASSISTANT_FAILURE_CATEGORIES = frozenset(
    {
        PROVIDER_TIMEOUT,
        PROVIDER_UNAVAILABLE,
        PROVIDER_INVALID_RESPONSE,
        PROVIDER_RESPONSE_TOO_LARGE,
        UNSUPPORTED_CONTEXT_VERSION,
        ASSISTANT_INVALID_REQUEST,
        ASSISTANT_INTERNAL_ERROR,
    }
)

_SAFE_PROVIDER_ID = re.compile(r"[a-z0-9_-]{1,32}\Z")


class AssistantServiceError(ValueError):
    """Controlled caller/context failure that must not invoke a provider."""

    def __init__(self, code: str, safe_message: str):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


def _validated_timeout(timeout_seconds: Any) -> float:
    if isinstance(timeout_seconds, bool) or not isinstance(
        timeout_seconds, (int, float)
    ):
        raise AssistantServiceError(
            ASSISTANT_INVALID_REQUEST,
            "Assistant timeout configuration is invalid.",
        )
    timeout = float(timeout_seconds)
    if (
        not math.isfinite(timeout)
        or timeout <= 0
        or timeout > MAX_PROVIDER_TIMEOUT_SECONDS
    ):
        raise AssistantServiceError(
            ASSISTANT_INVALID_REQUEST,
            "Assistant timeout configuration is invalid.",
        )
    return timeout


def _validated_context(tool_context: Any) -> ToolContext:
    if not isinstance(tool_context, dict):
        raise AssistantServiceError(
            ASSISTANT_INVALID_REQUEST,
            "Current Tool Context is invalid.",
        )
    if tool_context.get("schema_version") != TOOL_CONTEXT_SCHEMA_VERSION:
        raise AssistantServiceError(
            UNSUPPORTED_CONTEXT_VERSION,
            "Current Tool Context version is not supported.",
        )
    try:
        validated = validate_tool_context(tool_context)
    except ToolContextValidationError as exc:
        raise AssistantServiceError(
            ASSISTANT_INVALID_REQUEST,
            "Current Tool Context is invalid.",
        ) from exc
    return json.loads(canonical_json(validated))


def _provider_identifier(provider: AssistantProvider) -> str:
    candidate = getattr(provider, "provider_id", "")
    if isinstance(candidate, str) and _SAFE_PROVIDER_ID.fullmatch(candidate):
        return candidate
    return "unknown"


def _unavailable(category: str, provider: AssistantProvider) -> AssistantResponse:
    logger.warning(
        "Assistant request failed safely.",
        extra={
            "assistant_failure_category": category,
            "assistant_provider": _provider_identifier(provider),
        },
    )
    return build_unavailable_response()


def _external_unavailable(outcome: str, provider_id: str) -> AssistantResponse:
    logger.warning(
        "External assistant request blocked safely.",
        extra={
            "assistant_gate_outcome": outcome,
            "assistant_provider": (
                provider_id if _SAFE_PROVIDER_ID.fullmatch(provider_id) else "unknown"
            ),
        },
    )
    return build_unavailable_response()


def ask(
    *,
    message: str,
    tool_context: ToolContext,
    capability: str = READ_ONLY_CAPABILITY,
    provider: AssistantProvider | None = None,
    provider_name: str = DEFAULT_ASSISTANT_PROVIDER,
    timeout_seconds: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    knowledge_context: KnowledgeContext | None = None,
) -> AssistantResponse | ProviderProposalCandidate:
    """Return a validated response without calculations, mutation, or persistence."""
    try:
        validated_message = validate_user_message(message)
    except AssistantMessageValidationError as exc:
        raise AssistantServiceError(
            ASSISTANT_INVALID_REQUEST,
            "Assistant message is invalid.",
        ) from exc
    validated_context = _validated_context(tool_context)
    try:
        validated_knowledge = validate_knowledge_context(
            knowledge_context or empty_knowledge_context()
        )
        detached_knowledge = json.loads(canonical_knowledge_json(validated_knowledge))
    except KnowledgeContextValidationError as exc:
        raise AssistantServiceError(
            ASSISTANT_INVALID_REQUEST,
            "KolliPack Knowledge Context is invalid.",
        ) from exc
    timeout = _validated_timeout(timeout_seconds)
    try:
        instructions = get_assistant_instructions(capability)
    except ValueError as exc:
        raise AssistantServiceError(
            ASSISTANT_INVALID_REQUEST,
            "Assistant capability is not supported.",
        ) from exc

    if provider is None:
        try:
            provider = get_assistant_provider(provider_name)
        except ValueError:

            class _UnknownProvider:
                provider_id = "unknown"

            return _unavailable(PROVIDER_UNAVAILABLE, _UnknownProvider())

    try:
        provider_context = json.loads(canonical_json(validated_context))
        candidate = provider.generate(
            message=validated_message,
            tool_context=provider_context,
            instructions=instructions,
            timeout_seconds=timeout,
            knowledge_context=detached_knowledge,
        )
    except AssistantProviderTimeout:
        return _unavailable(PROVIDER_TIMEOUT, provider)
    except AssistantProviderResponseTooLarge:
        return _unavailable(PROVIDER_RESPONSE_TOO_LARGE, provider)
    except AssistantProviderInvalidResponse:
        return _unavailable(PROVIDER_INVALID_RESPONSE, provider)
    except AssistantProviderError:
        return _unavailable(PROVIDER_UNAVAILABLE, provider)
    except Exception:
        return _unavailable(ASSISTANT_INTERNAL_ERROR, provider)

    try:
        return parse_assistant_provider_candidate(
            candidate,
            tool_context=validated_context,
        )
    except AssistantResponseTooLargeError:
        return _unavailable(PROVIDER_RESPONSE_TOO_LARGE, provider)
    except AssistantResponseValidationError:
        return _unavailable(PROVIDER_INVALID_RESPONSE, provider)


def ask_external(
    *,
    user,
    message: str,
    tool_context: ToolContext,
    provider: AssistantProvider | None = None,
    capability: str = READ_ONLY_CAPABILITY,
    config=None,
    throttle=None,
    knowledge_context: KnowledgeContext | None = None,
) -> AssistantResponse | ProviderProposalCandidate:
    """Gate an external call before delegating to the provider service.

    An injected test provider or the server-configured registry provider is
    used only after every application-owned policy, configuration, privacy,
    and throttle condition has passed.
    """
    try:
        external_request = build_external_assistant_request(
            message=message,
            tool_context=tool_context,
            knowledge_context=knowledge_context or empty_knowledge_context(),
            capability=capability,
        )
    except ExternalAssistantRequestError as exc:
        raise AssistantServiceError(exc.code, exc.safe_message) from exc

    decision = evaluate_external_provider_gate(
        user=user,
        request=external_request,
        config=config,
        throttle=throttle,
    )
    if not decision.allowed:
        return _external_unavailable(decision.outcome, decision.provider_id)

    if provider is None:
        try:
            provider = get_assistant_provider(decision.provider_id)
        except ValueError:
            return _external_unavailable(
                PROVIDER_CONFIGURATION_MISMATCH,
                decision.provider_id,
            )
    elif _provider_identifier(provider) != decision.provider_id:
        return _external_unavailable(
            PROVIDER_CONFIGURATION_MISMATCH,
            decision.provider_id,
        )

    return ask(
        message=external_request.message,
        tool_context=external_request.tool_context,
        knowledge_context=external_request.knowledge_context,
        capability=external_request.instructions.capability,
        provider=provider,
        timeout_seconds=decision.timeout_seconds,
    )


__all__ = [
    "ASSISTANT_FAILURE_CATEGORIES",
    "AssistantServiceError",
    "ask",
    "ask_external",
]
