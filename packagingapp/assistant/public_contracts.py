"""Strict contracts for the anonymous, knowledge-only Public Expert."""

from __future__ import annotations

import json
from typing import Any, TypedDict

from .contracts import (
    AssistantResponseTooLargeError,
    AssistantResponseValidationError,
    validate_assistant_plain_text,
)


PUBLIC_EXPERT_CAPABILITY = "public_knowledge"
PUBLIC_EXPERT_CONTEXT_SCHEMA_VERSION = "1.0"
PUBLIC_KNOWLEDGE_CONTEXT_SCHEMA_VERSION = "1.0"
PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION = "1.0"
PUBLIC_EXPERT_UNAVAILABLE_MESSAGE = "The Public Expert is temporarily unavailable."
PUBLIC_KNOWLEDGE_FALLBACK_MESSAGE = (
    "I don't have enough approved KolliPack information to answer that reliably."
)

PUBLIC_EXPERT_RESPONSE_TYPES = frozenset(
    {"answer", "clarifying_question", "unavailable"}
)
PUBLIC_KNOWLEDGE_SCOPES = frozenset(
    {"global", "container_selection", "bag_selection", "palletization", "transport"}
)
PUBLIC_EXPERT_SURFACES = frozenset({"public_site", "public_tool"})

MAX_PUBLIC_USER_MESSAGE_LENGTH = 1_200
MAX_PUBLIC_ASSISTANT_MESSAGE_LENGTH = 3_000
MAX_PUBLIC_PROVIDER_RESPONSE_BYTES = 8 * 1024
MAX_PUBLIC_KNOWLEDGE_SECTIONS = 5
MAX_PUBLIC_KNOWLEDGE_SECTION_CHARS = 2_200
MAX_PUBLIC_KNOWLEDGE_TEXT_CHARS = 9_000
MAX_PUBLIC_KNOWLEDGE_CONTEXT_BYTES = 16 * 1024
MAX_PUBLIC_KNOWLEDGE_REF_LENGTH = 200
MAX_PUBLIC_KNOWLEDGE_TITLE_LENGTH = 180
MAX_PUBLIC_HEADING_PATH_ITEMS = 8


class PublicExpertContext(TypedDict):
    schema_version: str
    surface: str
    knowledge_scope: str


class PublicKnowledgeSection(TypedDict):
    ref: str
    title: str
    heading_path: list[str]
    text: str


class PublicKnowledgeContext(TypedDict):
    schema_version: str
    status: str
    sections: list[PublicKnowledgeSection]


class PublicExpertResponse(TypedDict):
    schema_version: str
    type: str
    message: str


class PublicExpertValidationError(ValueError):
    """Raised when public request, context, or provider data is invalid."""


def _has_unsupported_control_characters(value: str) -> bool:
    return any(ord(character) < 32 and character not in "\n\r\t" for character in value)


def validate_public_user_message(message: Any) -> str:
    if not isinstance(message, str):
        raise PublicExpertValidationError("Public Expert message must be plain text.")
    normalized = message.strip()
    if not normalized:
        raise PublicExpertValidationError("Public Expert message cannot be empty.")
    if len(normalized) > MAX_PUBLIC_USER_MESSAGE_LENGTH:
        raise PublicExpertValidationError(
            f"Public Expert message exceeds {MAX_PUBLIC_USER_MESSAGE_LENGTH} characters."
        )
    if _has_unsupported_control_characters(normalized):
        raise PublicExpertValidationError(
            "Public Expert message contains unsupported control characters."
        )
    return normalized


def build_public_expert_context(knowledge_scope: str) -> PublicExpertContext:
    if knowledge_scope not in PUBLIC_KNOWLEDGE_SCOPES:
        raise PublicExpertValidationError("Unsupported public knowledge scope.")
    context: PublicExpertContext = {
        "schema_version": PUBLIC_EXPERT_CONTEXT_SCHEMA_VERSION,
        "surface": "public_site" if knowledge_scope == "global" else "public_tool",
        "knowledge_scope": knowledge_scope,
    }
    return validate_public_expert_context(context)


def validate_public_expert_context(context: Any) -> PublicExpertContext:
    if not isinstance(context, dict) or set(context) != {
        "schema_version",
        "surface",
        "knowledge_scope",
    }:
        raise PublicExpertValidationError("Public Expert Context fields do not match schema.")
    if context.get("schema_version") != PUBLIC_EXPERT_CONTEXT_SCHEMA_VERSION:
        raise PublicExpertValidationError("Unsupported Public Expert Context version.")
    scope = context.get("knowledge_scope")
    surface = context.get("surface")
    if scope not in PUBLIC_KNOWLEDGE_SCOPES or surface not in PUBLIC_EXPERT_SURFACES:
        raise PublicExpertValidationError("Public Expert Context values are invalid.")
    expected_surface = "public_site" if scope == "global" else "public_tool"
    if surface != expected_surface:
        raise PublicExpertValidationError("Public Expert surface and scope do not agree.")
    return context


def empty_public_knowledge_context(*, unavailable: bool = False) -> PublicKnowledgeContext:
    context: PublicKnowledgeContext = {
        "schema_version": PUBLIC_KNOWLEDGE_CONTEXT_SCHEMA_VERSION,
        "status": "unavailable" if unavailable else "no_match",
        "sections": [],
    }
    return validate_public_knowledge_context(context)


def validate_public_knowledge_context(context: Any) -> PublicKnowledgeContext:
    if not isinstance(context, dict) or set(context) != {
        "schema_version",
        "status",
        "sections",
    }:
        raise PublicExpertValidationError("Public Knowledge Context fields do not match schema.")
    if context.get("schema_version") != PUBLIC_KNOWLEDGE_CONTEXT_SCHEMA_VERSION:
        raise PublicExpertValidationError("Unsupported Public Knowledge Context version.")
    status = context.get("status")
    if status not in {"available", "no_match", "unavailable"}:
        raise PublicExpertValidationError("Unsupported Public Knowledge Context status.")
    sections = context.get("sections")
    if not isinstance(sections, list) or len(sections) > MAX_PUBLIC_KNOWLEDGE_SECTIONS:
        raise PublicExpertValidationError("Public knowledge sections exceed the limit.")
    if status == "available" and not sections:
        raise PublicExpertValidationError("Available public knowledge requires sections.")
    if status != "available" and sections:
        raise PublicExpertValidationError("Unavailable public knowledge cannot contain sections.")

    total_chars = 0
    for section in sections:
        if not isinstance(section, dict) or set(section) != {
            "ref",
            "title",
            "heading_path",
            "text",
        }:
            raise PublicExpertValidationError("Public knowledge section fields are invalid.")
        ref = section.get("ref")
        title = section.get("title")
        heading_path = section.get("heading_path")
        text = section.get("text")
        if (
            not isinstance(ref, str)
            or not ref
            or len(ref) > MAX_PUBLIC_KNOWLEDGE_REF_LENGTH
            or "\\" in ref
            or ref.startswith("/")
            or ".." in ref.split("/")
        ):
            raise PublicExpertValidationError("Public knowledge ref is invalid.")
        if not isinstance(title, str) or not title or len(title) > MAX_PUBLIC_KNOWLEDGE_TITLE_LENGTH:
            raise PublicExpertValidationError("Public knowledge title is invalid.")
        if (
            not isinstance(heading_path, list)
            or not heading_path
            or len(heading_path) > MAX_PUBLIC_HEADING_PATH_ITEMS
            or not all(
                isinstance(item, str)
                and item
                and len(item) <= MAX_PUBLIC_KNOWLEDGE_TITLE_LENGTH
                for item in heading_path
            )
        ):
            raise PublicExpertValidationError("Public knowledge heading path is invalid.")
        if (
            not isinstance(text, str)
            or not text
            or len(text) > MAX_PUBLIC_KNOWLEDGE_SECTION_CHARS
            or _has_unsupported_control_characters(text)
        ):
            raise PublicExpertValidationError("Public knowledge text is invalid.")
        total_chars += len(text)

    if total_chars > MAX_PUBLIC_KNOWLEDGE_TEXT_CHARS:
        raise PublicExpertValidationError("Public knowledge text exceeds the total limit.")
    encoded = json.dumps(
        context,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_PUBLIC_KNOWLEDGE_CONTEXT_BYTES:
        raise PublicExpertValidationError("Public Knowledge Context is too large.")
    return context


def canonical_public_json(value: Any) -> str:
    if isinstance(value, dict) and set(value) == {
        "schema_version",
        "surface",
        "knowledge_scope",
    }:
        validated = validate_public_expert_context(value)
    else:
        validated = validate_public_knowledge_context(value)
    return json.dumps(
        validated,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def build_public_unavailable_response() -> PublicExpertResponse:
    return {
        "schema_version": PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION,
        "type": "unavailable",
        "message": PUBLIC_EXPERT_UNAVAILABLE_MESSAGE,
    }


def build_public_answer(message: str) -> PublicExpertResponse:
    return validate_public_expert_response(
        {
            "schema_version": PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION,
            "type": "answer",
            "message": message,
        }
    )


def validate_public_expert_response(response: Any) -> PublicExpertResponse:
    if not isinstance(response, dict) or set(response) != {
        "schema_version",
        "type",
        "message",
    }:
        raise PublicExpertValidationError("Public Expert response fields do not match schema.")
    if response.get("schema_version") != PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION:
        raise PublicExpertValidationError("Unsupported Public Expert response version.")
    response_type = response.get("type")
    if response_type not in PUBLIC_EXPERT_RESPONSE_TYPES:
        raise PublicExpertValidationError("Unsupported Public Expert response type.")
    try:
        message = validate_assistant_plain_text(
            response.get("message"),
            field_name="Public Expert response message",
            max_length=MAX_PUBLIC_ASSISTANT_MESSAGE_LENGTH,
        )
    except (AssistantResponseValidationError, AssistantResponseTooLargeError) as exc:
        raise PublicExpertValidationError(str(exc)) from exc
    if response_type == "unavailable" and message != PUBLIC_EXPERT_UNAVAILABLE_MESSAGE:
        raise PublicExpertValidationError(
            "Unavailable Public Expert responses must use the safe message."
        )
    encoded = json.dumps(
        response,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_PUBLIC_PROVIDER_RESPONSE_BYTES:
        raise PublicExpertValidationError("Public Expert response is too large.")
    return {
        "schema_version": PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION,
        "type": response_type,
        "message": message,
    }


def parse_public_expert_response(candidate: Any) -> PublicExpertResponse:
    if isinstance(candidate, bytes):
        if len(candidate) > MAX_PUBLIC_PROVIDER_RESPONSE_BYTES:
            raise PublicExpertValidationError("Public Expert response is too large.")
        try:
            candidate = candidate.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PublicExpertValidationError("Public Expert response must be UTF-8 JSON.") from exc
    if isinstance(candidate, str):
        if len(candidate.encode("utf-8")) > MAX_PUBLIC_PROVIDER_RESPONSE_BYTES:
            raise PublicExpertValidationError("Public Expert response is too large.")
        try:
            candidate = json.loads(candidate, parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()))
        except (json.JSONDecodeError, ValueError) as exc:
            raise PublicExpertValidationError("Public Expert response must be valid JSON.") from exc
    return validate_public_expert_response(candidate)


def build_public_expert_response_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION],
            },
            "type": {
                "type": "string",
                "enum": sorted(PUBLIC_EXPERT_RESPONSE_TYPES),
            },
            "message": {
                "type": "string",
                "description": "A concise plain-text public knowledge response.",
            },
        },
        "required": ["schema_version", "type", "message"],
        "additionalProperties": False,
    }


__all__ = [
    "MAX_PUBLIC_USER_MESSAGE_LENGTH",
    "PUBLIC_EXPERT_CAPABILITY",
    "PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION",
    "PUBLIC_EXPERT_UNAVAILABLE_MESSAGE",
    "PUBLIC_KNOWLEDGE_FALLBACK_MESSAGE",
    "PUBLIC_KNOWLEDGE_SCOPES",
    "PublicExpertContext",
    "PublicExpertResponse",
    "PublicExpertValidationError",
    "PublicKnowledgeContext",
    "build_public_answer",
    "build_public_expert_context",
    "build_public_expert_response_json_schema",
    "build_public_unavailable_response",
    "canonical_public_json",
    "empty_public_knowledge_context",
    "parse_public_expert_response",
    "validate_public_expert_context",
    "validate_public_expert_response",
    "validate_public_knowledge_context",
    "validate_public_user_message",
]
