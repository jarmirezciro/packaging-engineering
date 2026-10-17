"""Versioned, strict Tool Context contract validation.

Tool Context is an outbound allow-list.  This module intentionally rejects
unknown Python objects instead of coercing or stringifying them.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import is_dataclass
from decimal import Decimal
from pathlib import Path, PurePath
from typing import Any, TypedDict

from django.db.models import Model, QuerySet

try:
    import numpy as np
except ImportError:  # pragma: no cover - numpy is a declared project dependency.
    np = None


TOOL_CONTEXT_SCHEMA_VERSION = "1.0"
ASSISTANT_RESPONSE_SCHEMA_VERSION = "1.1"
ASSISTANT_UNAVAILABLE_MESSAGE = "The assistant is temporarily unavailable."

ASSISTANT_RESPONSE_TYPES = frozenset(
    {"answer", "clarifying_question", "unavailable"}
)
MAX_USER_MESSAGE_LENGTH = 2_000
MAX_ASSISTANT_MESSAGE_LENGTH = 4_000
MAX_ASSISTANT_FACT_REFS = 16
MAX_PROVIDER_RESPONSE_BYTES = 16 * 1024

_HTML_TAG_PATTERN = re.compile(r"<\s*(?:!|/?\s*[A-Za-z])[^>]*>")
_URL_PATTERN = re.compile(
    r"(?:https?://|ftp://|mailto:|javascript:|data:|www\.)",
    re.IGNORECASE,
)

CALCULATION_STATUSES = frozenset(
    {"empty", "partial", "invalid", "ready", "complete", "stale"}
)
TOOL_CONTEXT_SURFACES = frozenset({"standalone", "public", "workflow"})

MAX_ALTERNATIVES = 5
MAX_VALIDATION_ERRORS = 20
MAX_WARNINGS = 20
MAX_EXPLANATION_FACTS = 32
MAX_ALLOWED_PROPOSALS = 24
MAX_STRING_LENGTH = 512
MAX_MAPPING_ITEMS = 64
MAX_LIST_ITEMS = 50
MAX_NESTING_DEPTH = 12
MAX_CONTEXT_BYTES = 64 * 1024

TOOL_CONTEXT_KEYS = frozenset(
    {
        "schema_version",
        "tool",
        "inputs",
        "input_definitions",
        "validation",
        "assumptions",
        "restrictions",
        "result",
        "alternatives",
        "workflow",
        "warnings",
        "explanation_facts",
        "allowed_proposals",
    }
)

TOOL_KEYS = frozenset(
    {"id", "surface", "mode", "state_fingerprint", "calculation_status"}
)

# These keys identify structures that must never cross this boundary.  The
# adapter may inspect them in application-owned source objects, but a completed
# Tool Context containing one is invalid.
FORBIDDEN_OUTBOUND_KEYS = frozenset(
    {
        "api_key",
        "catalogue_id",
        "container_id",
        "cookie",
        "csrf_token",
        "database_id",
        "drawing",
        "email",
        "environment",
        "image",
        "image_path",
        "image_url",
        "material_id",
        "media_path",
        "owner_id",
        "password",
        "path",
        "picture",
        "placement",
        "placements",
        "product_catalogue_id",
        "render_data",
        "scene",
        "secret",
        "selected_product_id",
        "session",
        "session_id",
        "session_key",
        "snapshot",
        "stack_trace",
        "threejs_scene",
        "token",
        "user_id",
        "username",
    }
)


class ToolContext(TypedDict):
    schema_version: str
    tool: dict[str, Any]
    inputs: dict[str, Any]
    input_definitions: dict[str, Any]
    validation: dict[str, Any]
    assumptions: list[dict[str, Any]]
    restrictions: list[dict[str, Any]]
    result: dict[str, Any] | None
    alternatives: list[dict[str, Any]]
    workflow: dict[str, Any] | None
    warnings: list[dict[str, Any]]
    explanation_facts: list[dict[str, Any]]
    allowed_proposals: list[str]


class AssistantResponse(TypedDict, total=False):
    schema_version: str
    type: str
    message: str
    fact_refs: list[str]


class ToolContextValidationError(ValueError):
    """Raised when a Tool Context is unsafe, malformed, or unexpectedly large."""


class AssistantResponseValidationError(ValueError):
    """Raised when an untrusted provider response violates the response contract."""


class AssistantResponseTooLargeError(AssistantResponseValidationError):
    """Raised when provider output exceeds the application-owned byte limit."""


class AssistantMessageValidationError(ValueError):
    """Raised when a caller message violates the assistant request contract."""


def _reject_known_unsafe_type(value: Any, path: str) -> None:
    if isinstance(value, (Model, QuerySet)):
        raise ToolContextValidationError(f"{path} contains a Django model/query object.")
    if isinstance(value, Decimal):
        raise ToolContextValidationError(f"{path} contains Decimal; convert it explicitly.")
    if isinstance(value, (Path, PurePath)):
        raise ToolContextValidationError(f"{path} contains a filesystem path.")
    if is_dataclass(value):
        raise ToolContextValidationError(f"{path} contains a dataclass instance.")
    if np is not None and isinstance(value, (np.ndarray, np.generic)):
        raise ToolContextValidationError(f"{path} contains a NumPy value.")


def _validate_value(value: Any, *, path: str, depth: int) -> None:
    if depth > MAX_NESTING_DEPTH:
        raise ToolContextValidationError(
            f"{path} exceeds the maximum nesting depth of {MAX_NESTING_DEPTH}."
        )

    _reject_known_unsafe_type(value, path)

    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ToolContextValidationError(f"{path} contains a non-finite number.")
        return
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise ToolContextValidationError(
                f"{path} exceeds the maximum string length of {MAX_STRING_LENGTH}."
            )
        return
    if isinstance(value, dict):
        if len(value) > MAX_MAPPING_ITEMS:
            raise ToolContextValidationError(
                f"{path} exceeds the maximum mapping size of {MAX_MAPPING_ITEMS}."
            )
        for key, child in value.items():
            if not isinstance(key, str):
                raise ToolContextValidationError(f"{path} contains a non-string key.")
            if len(key) > 128:
                raise ToolContextValidationError(f"{path} contains an overlong key.")
            if key.lower() in FORBIDDEN_OUTBOUND_KEYS:
                raise ToolContextValidationError(
                    f"{path}.{key} is forbidden in outbound Tool Context."
                )
            _validate_value(child, path=f"{path}.{key}", depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > MAX_LIST_ITEMS:
            raise ToolContextValidationError(
                f"{path} exceeds the maximum list size of {MAX_LIST_ITEMS}."
            )
        for index, child in enumerate(value):
            _validate_value(child, path=f"{path}[{index}]", depth=depth + 1)
        return

    raise ToolContextValidationError(
        f"{path} contains unsupported type {type(value).__name__}; "
        "unknown objects are never stringified."
    )


def canonical_json(value: Any) -> str:
    """Serialize an already-explicit primitive structure deterministically."""
    _validate_value(value, path="value", depth=0)
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:  # Defensive parity with json.dumps.
        raise ToolContextValidationError("Value is not strict JSON.") from exc


def state_fingerprint(state: dict[str, Any]) -> str:
    """Hash canonical semantic engineering state without identity or UI state."""
    encoded = canonical_json(state).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def validate_tool_context(context: ToolContext) -> ToolContext:
    """Validate shape, privacy-denied keys, JSON safety, and deterministic limits."""
    if not isinstance(context, dict):
        raise ToolContextValidationError("Tool Context must be a dictionary.")
    if frozenset(context) != TOOL_CONTEXT_KEYS:
        missing = sorted(TOOL_CONTEXT_KEYS - frozenset(context))
        extra = sorted(frozenset(context) - TOOL_CONTEXT_KEYS)
        raise ToolContextValidationError(
            f"Tool Context keys do not match schema; missing={missing}, extra={extra}."
        )
    if context.get("schema_version") != TOOL_CONTEXT_SCHEMA_VERSION:
        raise ToolContextValidationError("Unsupported Tool Context schema version.")

    tool = context.get("tool")
    if not isinstance(tool, dict) or frozenset(tool) != TOOL_KEYS:
        raise ToolContextValidationError("Tool metadata does not match schema.")
    if tool.get("surface") not in TOOL_CONTEXT_SURFACES:
        raise ToolContextValidationError("Unsupported Tool Context surface.")
    calculation_status = tool.get("calculation_status")
    if calculation_status not in CALCULATION_STATUSES:
        raise ToolContextValidationError("Unsupported calculation status.")
    fingerprint = tool.get("state_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint.startswith("sha256:"):
        raise ToolContextValidationError("State fingerprint must be SHA-256 tagged.")

    validation = context.get("validation")
    if not isinstance(validation, dict) or set(validation) != {"status", "errors"}:
        raise ToolContextValidationError("Validation section does not match schema.")
    if validation.get("status") not in {"valid", "incomplete", "invalid"}:
        raise ToolContextValidationError("Unsupported validation status.")

    if not isinstance(context.get("inputs"), dict) or not isinstance(
        context.get("input_definitions"), dict
    ):
        raise ToolContextValidationError("Inputs and input definitions must be dictionaries.")
    for section in ("assumptions", "restrictions"):
        if not isinstance(context.get(section), list):
            raise ToolContextValidationError(f"{section} must be a list.")

    result = context.get("result")
    alternatives = context.get("alternatives")
    if calculation_status == "complete":
        if not isinstance(result, dict):
            raise ToolContextValidationError("A complete context requires a result object.")
    elif result is not None or alternatives:
        raise ToolContextValidationError(
            "Only a complete context may expose a result or alternatives."
        )

    workflow = context.get("workflow")
    if tool.get("surface") == "workflow":
        if not isinstance(workflow, dict):
            raise ToolContextValidationError("Workflow surface requires workflow metadata.")
    elif workflow is not None:
        raise ToolContextValidationError(
            "Non-workflow surfaces cannot expose workflow metadata."
        )

    bounded_sections = (
        ("alternatives", MAX_ALTERNATIVES),
        ("warnings", MAX_WARNINGS),
        ("explanation_facts", MAX_EXPLANATION_FACTS),
        ("allowed_proposals", MAX_ALLOWED_PROPOSALS),
    )
    for section, limit in bounded_sections:
        value = context.get(section)
        if not isinstance(value, list) or len(value) > limit:
            raise ToolContextValidationError(
                f"{section} must be a list with at most {limit} items."
            )
    if not all(isinstance(path, str) for path in context["allowed_proposals"]):
        raise ToolContextValidationError("Allowed proposals must be semantic field strings.")
    errors = validation.get("errors")
    if not isinstance(errors, list) or len(errors) > MAX_VALIDATION_ERRORS:
        raise ToolContextValidationError(
            f"validation.errors must contain at most {MAX_VALIDATION_ERRORS} items."
        )

    encoded = canonical_json(context).encode("utf-8")
    if len(encoded) > MAX_CONTEXT_BYTES:
        raise ToolContextValidationError(
            f"Tool Context exceeds the {MAX_CONTEXT_BYTES}-byte limit."
        )
    return context


def _has_unsupported_control_characters(value: str) -> bool:
    return any(ord(character) < 32 and character not in "\n\r\t" for character in value)


def validate_user_message(message: Any) -> str:
    """Validate and normalize the only free-text assistant request field."""
    if not isinstance(message, str):
        raise AssistantMessageValidationError("Assistant message must be plain text.")
    normalized = message.strip()
    if not normalized:
        raise AssistantMessageValidationError("Assistant message cannot be empty.")
    if len(normalized) > MAX_USER_MESSAGE_LENGTH:
        raise AssistantMessageValidationError(
            f"Assistant message exceeds {MAX_USER_MESSAGE_LENGTH} characters."
        )
    if _has_unsupported_control_characters(normalized):
        raise AssistantMessageValidationError(
            "Assistant message contains unsupported control characters."
        )
    return normalized


def validate_assistant_plain_text(
    message: Any,
    *,
    field_name: str = "Assistant response message",
    max_length: int = MAX_ASSISTANT_MESSAGE_LENGTH,
) -> str:
    """Validate bounded provider text that may be displayed as escaped text."""
    if not isinstance(message, str):
        raise AssistantResponseValidationError(
            f"{field_name} must be a string."
        )
    if not message.strip():
        raise AssistantResponseValidationError(
            f"{field_name} cannot be empty."
        )
    if len(message) > max_length:
        raise AssistantResponseTooLargeError(
            f"{field_name} exceeds {max_length} characters."
        )
    if _has_unsupported_control_characters(message):
        raise AssistantResponseValidationError(
            f"{field_name} contains unsupported control characters."
        )
    if _HTML_TAG_PATTERN.search(message):
        raise AssistantResponseValidationError(
            f"{field_name} HTML is not supported."
        )
    if _URL_PATTERN.search(message):
        raise AssistantResponseValidationError(
            f"{field_name} URLs are not supported."
        )
    return message


def _validate_assistant_message(message: Any) -> str:
    return validate_assistant_plain_text(message)


def _assistant_response_bytes(response: dict[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            response,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AssistantResponseValidationError(
            "Assistant response is not strict JSON."
        ) from exc
    if len(encoded) > MAX_PROVIDER_RESPONSE_BYTES:
        raise AssistantResponseTooLargeError(
            f"Assistant response exceeds {MAX_PROVIDER_RESPONSE_BYTES} bytes."
        )
    return encoded


def _reject_json_constant(_value):
    raise ValueError("Non-finite JSON numbers are not supported.")


def validate_assistant_response(
    response: Any,
    *,
    tool_context: ToolContext,
) -> AssistantResponse:
    """Validate one provider candidate against the application-owned contract."""
    validate_tool_context(tool_context)
    if not isinstance(response, dict):
        raise AssistantResponseValidationError(
            "Assistant response must be a JSON object."
        )

    response_type = response.get("type")
    if response_type not in ASSISTANT_RESPONSE_TYPES:
        raise AssistantResponseValidationError("Unsupported assistant response type.")
    expected_keys = {"schema_version", "type", "message"}
    if response_type == "answer":
        expected_keys.add("fact_refs")
    if set(response) != expected_keys:
        raise AssistantResponseValidationError(
            "Assistant response fields do not match the response schema."
        )
    if response.get("schema_version") != ASSISTANT_RESPONSE_SCHEMA_VERSION:
        raise AssistantResponseValidationError(
            "Unsupported assistant response schema version."
        )

    message = _validate_assistant_message(response.get("message"))
    if response_type == "unavailable" and message != ASSISTANT_UNAVAILABLE_MESSAGE:
        raise AssistantResponseValidationError(
            "Unavailable responses must use the application-owned safe message."
        )
    validated: AssistantResponse = {
        "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
        "type": response_type,
        "message": message,
    }

    if response_type == "answer":
        fact_refs = response.get("fact_refs")
        if not isinstance(fact_refs, list) or len(fact_refs) > MAX_ASSISTANT_FACT_REFS:
            raise AssistantResponseValidationError(
                f"Answer fact_refs must contain at most {MAX_ASSISTANT_FACT_REFS} items."
            )
        if not all(isinstance(reference, str) and reference for reference in fact_refs):
            raise AssistantResponseValidationError(
                "Answer fact_refs must be non-empty strings."
            )
        if len(set(fact_refs)) != len(fact_refs):
            raise AssistantResponseValidationError(
                "Answer fact_refs cannot contain duplicates."
            )
        available_fact_refs = {
            fact.get("code")
            for fact in tool_context.get("explanation_facts", [])
            if isinstance(fact, dict) and isinstance(fact.get("code"), str)
        }
        unknown = sorted(set(fact_refs) - available_fact_refs)
        if unknown:
            raise AssistantResponseValidationError(
                "Answer contains a fact reference not present in Tool Context."
            )
        validated["fact_refs"] = list(fact_refs)

    _assistant_response_bytes(dict(validated))
    return validated


def parse_assistant_response(
    candidate: Any,
    *,
    tool_context: ToolContext,
) -> AssistantResponse:
    """Parse bounded provider output, then apply strict response validation."""
    if isinstance(candidate, bytes):
        raw_bytes = candidate
        if len(raw_bytes) > MAX_PROVIDER_RESPONSE_BYTES:
            raise AssistantResponseTooLargeError(
                f"Assistant response exceeds {MAX_PROVIDER_RESPONSE_BYTES} bytes."
            )
        try:
            raw_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AssistantResponseValidationError(
                "Assistant response must be UTF-8 JSON."
            ) from exc
        candidate = raw_text

    if isinstance(candidate, str):
        if len(candidate.encode("utf-8")) > MAX_PROVIDER_RESPONSE_BYTES:
            raise AssistantResponseTooLargeError(
                f"Assistant response exceeds {MAX_PROVIDER_RESPONSE_BYTES} bytes."
            )
        try:
            candidate = json.loads(
                candidate,
                parse_constant=_reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise AssistantResponseValidationError(
                "Assistant response must contain valid JSON."
            ) from exc

    return validate_assistant_response(candidate, tool_context=tool_context)


def build_unavailable_response() -> AssistantResponse:
    """Create the sole user-facing response for normalized assistant failures."""
    return {
        "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
        "type": "unavailable",
        "message": ASSISTANT_UNAVAILABLE_MESSAGE,
    }


def build_assistant_response_json_schema() -> dict[str, Any]:
    """Build the strict provider wire schema from Assistant Response constants.

    OpenAI Structured Outputs requires every object property to be required and
    does not permit a root-level ``anyOf``.  The wire representation therefore
    always carries ``fact_refs``.  Provider adapters must remove an empty
    ``fact_refs`` from non-answer candidates before the unchanged application
    validator runs.  KolliPack remains the final response authority.
    """
    return {
        "type": "object",
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [ASSISTANT_RESPONSE_SCHEMA_VERSION],
            },
            "type": {
                "type": "string",
                "enum": sorted(ASSISTANT_RESPONSE_TYPES),
            },
            "message": {
                "type": "string",
                "description": (
                    "Plain-text answer, clarifying question, or the exact "
                    "application-owned unavailable message."
                ),
            },
            "fact_refs": {
                "type": "array",
                "description": (
                    "For answers, zero or more unique codes present in Tool "
                    "Context explanation_facts. For every other type, an empty list."
                ),
                "items": {"type": "string"},
                "maxItems": MAX_ASSISTANT_FACT_REFS,
            },
        },
        "required": ["schema_version", "type", "message", "fact_refs"],
        "additionalProperties": False,
    }
