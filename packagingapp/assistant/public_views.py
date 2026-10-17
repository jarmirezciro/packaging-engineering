"""Same-origin anonymous HTTP boundary for the Public Expert."""

from __future__ import annotations

import json

from django.conf import settings
from django.http import JsonResponse

from .public_contracts import (
    MAX_PUBLIC_USER_MESSAGE_LENGTH,
    PUBLIC_KNOWLEDGE_SCOPES,
    PublicExpertValidationError,
    build_public_expert_context,
    build_public_unavailable_response,
    validate_public_user_message,
)
from .public_knowledge import public_knowledge_trace, retrieve_public_knowledge_context
from .public_policy import load_public_expert_configuration
from .public_service import ask_public_external


MAX_PUBLIC_EXPERT_REQUEST_BYTES = 8 * 1024


def _error(code: str, message: str, *, status: int) -> JsonResponse:
    return JsonResponse(
        {"ok": False, "error": {"code": code, "message": message}},
        status=status,
    )


def _parse_payload(request) -> dict:
    content_length = request.META.get("CONTENT_LENGTH")
    if content_length:
        try:
            declared_size = int(content_length)
        except (TypeError, ValueError) as exc:
            raise PublicExpertValidationError("invalid_request_size") from exc
        if declared_size > MAX_PUBLIC_EXPERT_REQUEST_BYTES:
            raise PublicExpertValidationError("request_too_large")
    raw_body = request.body
    if len(raw_body) > MAX_PUBLIC_EXPERT_REQUEST_BYTES:
        raise PublicExpertValidationError("request_too_large")
    try:
        payload = json.loads(
            raw_body.decode("utf-8"),
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise PublicExpertValidationError("malformed_json") from exc
    if not isinstance(payload, dict) or set(payload) != {"message", "knowledge_scope"}:
        raise PublicExpertValidationError("invalid_request_schema")
    return payload


def _trace_enabled() -> bool:
    value = getattr(settings, "AI_PUBLIC_EXPERT_KNOWLEDGE_TRACE_ENABLED", False)
    if isinstance(value, str):
        value = value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(settings.DEBUG and value is True)


def public_expert_ask(request):
    """Answer one stateless public question without reading browser/tool state."""
    if request.method != "POST":
        response = _error(
            "method_not_allowed",
            "Use POST for Public Expert requests.",
            status=405,
        )
        response["Allow"] = "POST"
        return response
    if request.content_type != "application/json":
        return _error(
            "unsupported_content_type",
            "Public Expert requests require application/json.",
            status=415,
        )

    try:
        payload = _parse_payload(request)
        message = validate_public_user_message(payload.get("message"))
        knowledge_scope = payload.get("knowledge_scope")
        if knowledge_scope not in PUBLIC_KNOWLEDGE_SCOPES:
            raise PublicExpertValidationError("unsupported_knowledge_scope")
    except PublicExpertValidationError as exc:
        code = str(exc)
        if code == "request_too_large":
            return _error(
                "public_expert_request_too_large",
                "Public Expert request exceeds the application size limit.",
                status=413,
            )
        if code == "malformed_json":
            return _error(
                "malformed_json",
                "Request body must contain valid UTF-8 JSON.",
                status=400,
            )
        if code == "unsupported_knowledge_scope":
            return _error(
                "unsupported_knowledge_scope",
                "The requested public knowledge scope is not supported.",
                status=400,
            )
        return _error(
            "invalid_request_schema",
            f"Request must contain only message (maximum {MAX_PUBLIC_USER_MESSAGE_LENGTH} characters) and knowledge_scope.",
            status=400,
        )

    config = load_public_expert_configuration()
    if not config.enabled:
        return JsonResponse({"ok": True, "response": build_public_unavailable_response()})

    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    expert_context = build_public_expert_context(knowledge_scope)
    knowledge_context = retrieve_public_knowledge_context(
        message,
        knowledge_scope=knowledge_scope,
    )
    try:
        response = ask_public_external(
            session_key=session_key,
            message=message,
            expert_context=expert_context,
            knowledge_context=knowledge_context,
            config=config,
        )
    except PublicExpertValidationError:
        return _error(
            "public_expert_request_failed",
            "The Public Expert request could not be processed safely.",
            status=422,
        )

    envelope = {"ok": True, "response": response}
    if _trace_enabled():
        envelope["knowledge_trace"] = public_knowledge_trace(knowledge_context)
    return JsonResponse(envelope)


__all__ = ["MAX_PUBLIC_EXPERT_REQUEST_BYTES", "public_expert_ask"]
