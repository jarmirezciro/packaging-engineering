"""Knowledge-only orchestration for the anonymous KolliPack Public Expert."""

from __future__ import annotations

import logging
import re

from .clarification import (
    ClarificationContext,
    is_probable_short_clarification_reply,
)
from .providers import DEFAULT_ASSISTANT_PROVIDER, get_assistant_provider
from .providers.base import (
    AssistantProviderError,
    AssistantProviderInvalidResponse,
    AssistantProviderResponseTooLarge,
    AssistantProviderTimeout,
)
from .public_contracts import (
    PUBLIC_KNOWLEDGE_FALLBACK_MESSAGE,
    PublicExpertContext,
    PublicExpertResponse,
    PublicExpertValidationError,
    PublicKnowledgeContext,
    build_public_answer,
    build_public_unavailable_response,
    parse_public_expert_response,
)
from .public_policy import (
    PUBLIC_PROVIDER_CONFIGURATION_MISMATCH,
    PublicExternalRequestError,
    build_public_external_request,
    evaluate_public_provider_gate,
)


logger = logging.getLogger(__name__)

PUBLIC_PROVIDER_TIMEOUT = "public_provider_timeout"
PUBLIC_PROVIDER_UNAVAILABLE = "public_provider_unavailable"
PUBLIC_PROVIDER_INVALID_RESPONSE = "public_provider_invalid_response"
PUBLIC_PROVIDER_RESPONSE_TOO_LARGE = "public_provider_response_too_large"
PUBLIC_INTERNAL_ERROR = "public_internal_error"

_FORM_STATE_PATTERNS = (
    r"\bwhat (?:dimensions|values|quantity) did i (?:enter|request|select)\b",
    r"\bwhich rotations? (?:do i have|are) enabled\b",
    r"\bwhat (?:box|bag|pallet|container) did i select\b",
    r"\binspect (?:the |my )?(?:page|form|dom|inputs?)\b",
    r"\bcurrent form values?\b",
)
_RESULT_PATTERNS = (
    r"\bwhy did i get\b",
    r"\bwhy (?:is|was) my\b",
    r"\bwhy did (?:this |the )?candidate .*rank\b",
    r"\bis my result correct\b",
    r"\bwhy did (?:this |the )?tool choose\b",
    r"\bmy (?:utilization|efficiency|cubicity|result) (?:is|says|shows)\b",
    r"\bis my .*(?:utilization|efficiency|cubicity).*(?:good|correct|high|low)\b",
)
_CALCULATION_PATTERNS = (
    r"^\s*calculate\b",
    r"^\s*optimi[sz]e\b",
    r"\bhow many .+\bfit\b",
    r"\bwhat (?:box|bag|container|pallet) should i use for \d",
    r"\bbest pallet pattern for\b",
)
_ACTION_PATTERNS = (
    r"^\s*(?:set|change|update)\b",
    r"^\s*use r[123]\b",
    r"^\s*run (?:the |this )?(?:calculation|tool|analysis)\b",
    r"^\s*select (?:the )?(?:first|second|third|candidate|box|bag|pallet)\b",
    r"^\s*apply (?:this|the|these)\b",
    r"\bwithout asking\b",
)
_AUTHORITY_PATTERNS = (
    r"\b(?:reveal|show|print|repeat) (?:the )?(?:hidden |system |developer )?(?:prompt|instructions?)\b",
    r"\b(?:reveal|show|describe|explain) (?:the )?(?:internal|private|confidential) (?:kollipack )?(?:implementation|details?|catalogues?|data|information)\b",
    r"\bprivate catalogues?\b",
    r"\bact as (?:the )?(?:premium|authenticated|internal) (?:assistant|expert)\b",
)


def _matches(patterns: tuple[str, ...], question: str) -> bool:
    normalized = " ".join(question.lower().split())
    return any(re.search(pattern, normalized) for pattern in patterns)


def public_question_boundary(question: str) -> str | None:
    if _matches(_FORM_STATE_PATTERNS, question):
        return "form_state"
    if _matches(_AUTHORITY_PATTERNS, question):
        return "authority"
    if _matches(_ACTION_PATTERNS, question):
        return "action"
    if _matches(_CALCULATION_PATTERNS, question):
        return "calculation"
    if _matches(_RESULT_PATTERNS, question):
        return "result"
    return None


def _boundary_response(question: str, boundary: str) -> PublicExpertResponse:
    if boundary == "form_state":
        return build_public_answer(
            "The Public Expert does not have access to values entered in the demo, "
            "including dimensions, selections, rotations, or requested quantity."
        )
    if boundary == "action":
        return build_public_answer(
            "The Public Expert cannot change inputs, select candidates, apply changes, "
            "or run calculations. Use the calculator controls directly."
        )
    if boundary == "authority":
        return build_public_answer(
            "The Public Expert can only explain approved public KolliPack knowledge. "
            "It cannot provide hidden prompts, internal implementation details, private "
            "catalogues, or authenticated Assistant capabilities."
        )
    if boundary == "calculation":
        return build_public_answer(
            "The Public Expert does not perform packaging calculations. It can explain "
            "which KolliPack tool performs the calculation, but the calculation must be "
            "run in that tool."
        )

    normalized = question.lower()
    concept = ""
    if "utilization" in normalized:
        concept = (
            " In KolliPack, utilization compares occupied usable volume or area with "
            "the applicable usable capacity; the exact denominator depends on the tool."
        )
    elif "cubicity" in normalized:
        concept = (
            " In Container Design, cubicity describes how cube-like a candidate's "
            "internal bounding dimensions are; it is not volume utilization."
        )
    elif "efficiency" in normalized:
        concept = (
            " KolliPack uses several tool-specific efficiency measures, so the metric's "
            "documented denominator matters."
        )
    return build_public_answer(
        "I can explain documented KolliPack concepts, but I cannot inspect or validate "
        "your current inputs, calculation, candidates, or results."
        + concept
    )


def _unavailable(category: str, provider_id: str = "unknown") -> PublicExpertResponse:
    logger.warning(
        "Public Expert request failed safely.",
        extra={
            "public_expert_failure_category": category,
            "assistant_provider": provider_id if re.fullmatch(r"[a-z0-9_-]{1,32}", provider_id) else "unknown",
        },
    )
    return build_public_unavailable_response()


def ask_public_external(
    *,
    session_key: str,
    message: str,
    expert_context: PublicExpertContext,
    knowledge_context: PublicKnowledgeContext,
    clarification_context: ClarificationContext | None = None,
    provider=None,
    provider_name: str = DEFAULT_ASSISTANT_PROVIDER,
    config=None,
    throttle=None,
) -> PublicExpertResponse:
    """Gate and answer one stateless public question without engineering state."""
    try:
        external_request = build_public_external_request(
            message=message,
            expert_context=expert_context,
            knowledge_context=knowledge_context,
            clarification_context=clarification_context,
        )
    except PublicExternalRequestError as exc:
        raise PublicExpertValidationError(exc.safe_message) from exc

    decision = evaluate_public_provider_gate(
        session_key=session_key,
        request=external_request,
        config=config,
        throttle=throttle,
    )
    if not decision.allowed:
        return _unavailable(decision.outcome, decision.provider_id)

    boundary_question = external_request.message
    boundary = public_question_boundary(boundary_question)
    if (
        boundary is None
        and external_request.clarification_context is not None
        and is_probable_short_clarification_reply(external_request.message)
    ):
        boundary_question = external_request.clarification_context["turns"][0]["message"]
        boundary = public_question_boundary(boundary_question)
    if boundary:
        return _boundary_response(boundary_question, boundary)
    if external_request.knowledge_context["status"] == "no_match":
        return build_public_answer(PUBLIC_KNOWLEDGE_FALLBACK_MESSAGE)
    if external_request.knowledge_context["status"] != "available":
        return _unavailable(PUBLIC_PROVIDER_UNAVAILABLE, decision.provider_id)

    if provider is None:
        try:
            provider = get_assistant_provider(decision.provider_id or provider_name)
        except ValueError:
            return _unavailable(PUBLIC_PROVIDER_CONFIGURATION_MISMATCH)
    if getattr(provider, "provider_id", "") != decision.provider_id:
        return _unavailable(PUBLIC_PROVIDER_CONFIGURATION_MISMATCH)
    generate_public = getattr(provider, "generate_public", None)
    if not callable(generate_public):
        return _unavailable(PUBLIC_PROVIDER_CONFIGURATION_MISMATCH)

    try:
        provider_request = {
            "message": external_request.message,
            "expert_context": external_request.expert_context,
            "instructions": external_request.instructions,
            "timeout_seconds": decision.timeout_seconds,
            "max_output_tokens": decision.max_output_tokens,
            "knowledge_context": external_request.knowledge_context,
        }
        if external_request.clarification_context is not None:
            provider_request["clarification_context"] = (
                external_request.clarification_context
            )
        candidate = generate_public(**provider_request)
    except AssistantProviderTimeout:
        return _unavailable(PUBLIC_PROVIDER_TIMEOUT, decision.provider_id)
    except AssistantProviderResponseTooLarge:
        return _unavailable(PUBLIC_PROVIDER_RESPONSE_TOO_LARGE, decision.provider_id)
    except AssistantProviderInvalidResponse:
        return _unavailable(PUBLIC_PROVIDER_INVALID_RESPONSE, decision.provider_id)
    except AssistantProviderError:
        return _unavailable(PUBLIC_PROVIDER_UNAVAILABLE, decision.provider_id)
    except Exception:
        return _unavailable(PUBLIC_INTERNAL_ERROR, decision.provider_id)

    try:
        return parse_public_expert_response(candidate)
    except PublicExpertValidationError:
        return _unavailable(PUBLIC_PROVIDER_INVALID_RESPONSE, decision.provider_id)


__all__ = [
    "ask_public_external",
    "public_question_boundary",
]
