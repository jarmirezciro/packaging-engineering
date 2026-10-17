"""Strict shared protocol for non-mutating assistant input proposals."""

from __future__ import annotations

import json
import math
import re
from typing import Any, TypedDict

from .contracts import (
    ASSISTANT_RESPONSE_SCHEMA_VERSION,
    ASSISTANT_RESPONSE_TYPES,
    MAX_ASSISTANT_FACT_REFS,
    MAX_PROVIDER_RESPONSE_BYTES,
    AssistantResponse,
    AssistantResponseTooLargeError,
    AssistantResponseValidationError,
    ToolContext,
    validate_assistant_plain_text,
    validate_assistant_response,
    validate_tool_context,
)


PROPOSE_INPUT_CHANGES = "propose_input_changes"
PROPOSAL_PREVIEW_TYPE = "proposal_preview"
PROPOSAL_PREVIEW_SCHEMA_VERSION = "1.0"
APPLY_RESPONSE_SCHEMA_VERSION = "1.0"
APPLY_RESPONSE_TYPE = "applied"
APPLY_SUCCESS_MESSAGE = (
    "Changes applied to inputs. Run the tool when you are ready to calculate."
)
MAX_PROPOSAL_CHANGES = 8
MAX_PROPOSAL_SUMMARY_LENGTH = 512
PROPOSAL_NOT_APPLIED_NOTICE = "These changes have not been applied."

PROPOSAL_CHANGE_STATUSES = frozenset(
    {"valid", "invalid", "not_editable", "unsupported_unit", "no_change"}
)
PROPOSAL_RESULTING_STATUSES = frozenset({"ready", "incomplete", "invalid"})
PROPOSAL_UNITS = frozenset({"mm", "cm", "m", "g", "kg", "pcs", "none"})
PROVIDER_CANDIDATE_TYPES = ASSISTANT_RESPONSE_TYPES | {PROPOSE_INPUT_CHANGES}

_FINGERPRINT_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
_WIRE_KEYS = frozenset(
    {
        "schema_version",
        "type",
        "message",
        "fact_refs",
        "state_fingerprint",
        "changes",
        "summary",
    }
)


class ProposalChangeCandidate(TypedDict):
    field: str
    value: float | int | list[str]
    unit: str


class ProviderProposalCandidate(TypedDict):
    schema_version: str
    type: str
    state_fingerprint: str
    changes: list[ProposalChangeCandidate]
    summary: str


class ProposalCandidateValidationError(AssistantResponseValidationError):
    """Raised when untrusted proposal output violates the shared protocol."""


class ProposalStateMismatchError(ProposalCandidateValidationError):
    """Raised when a candidate does not match freshly reconstructed state."""


class NoEffectiveProposalChanges(ValueError):
    """Raised when every otherwise-valid proposed change is already current."""


class ApplyResponseValidationError(ValueError):
    """Raised when application-owned Apply output violates its contract."""


def _reject_json_constant(_value):
    raise ValueError("Non-finite JSON numbers are not supported.")


def _decode_provider_candidate(candidate: Any) -> dict[str, Any]:
    if isinstance(candidate, bytes):
        if len(candidate) > MAX_PROVIDER_RESPONSE_BYTES:
            raise AssistantResponseTooLargeError(
                f"Assistant response exceeds {MAX_PROVIDER_RESPONSE_BYTES} bytes."
            )
        try:
            candidate = candidate.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProposalCandidateValidationError(
                "Assistant response must be UTF-8 JSON."
            ) from exc
    if isinstance(candidate, str):
        if len(candidate.encode("utf-8")) > MAX_PROVIDER_RESPONSE_BYTES:
            raise AssistantResponseTooLargeError(
                f"Assistant response exceeds {MAX_PROVIDER_RESPONSE_BYTES} bytes."
            )
        try:
            candidate = json.loads(candidate, parse_constant=_reject_json_constant)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProposalCandidateValidationError(
                "Assistant response must contain valid JSON."
            ) from exc
    if not isinstance(candidate, dict):
        raise ProposalCandidateValidationError(
            "Assistant response must be a JSON object."
        )
    try:
        encoded = json.dumps(
            candidate,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProposalCandidateValidationError(
            "Assistant response is not strict JSON."
        ) from exc
    if len(encoded) > MAX_PROVIDER_RESPONSE_BYTES:
        raise AssistantResponseTooLargeError(
            f"Assistant response exceeds {MAX_PROVIDER_RESPONSE_BYTES} bytes."
        )
    return candidate


def _validate_candidate_value(value: Any, *, path: str):
    if isinstance(value, bool):
        raise ProposalCandidateValidationError(f"{path} has an invalid value type.")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ProposalCandidateValidationError(f"{path} must be finite.")
        return value
    if isinstance(value, list):
        if len(value) > 3:
            raise ProposalCandidateValidationError(
                f"{path} must contain at most three values."
            )
        if not all(
            isinstance(item, str) and item and len(item) <= 32 for item in value
        ):
            raise ProposalCandidateValidationError(
                f"{path} must contain bounded non-empty strings."
            )
        if len(set(value)) != len(value):
            raise ProposalCandidateValidationError(
                f"{path} cannot contain duplicate values."
            )
        return list(value)
    raise ProposalCandidateValidationError(f"{path} has an invalid value type.")


def validate_provider_proposal_candidate(
    candidate: Any,
    *,
    tool_context: ToolContext,
) -> ProviderProposalCandidate:
    """Validate a proposal structurally without granting edit authority."""
    validate_tool_context(tool_context)
    if not isinstance(candidate, dict):
        raise ProposalCandidateValidationError("Proposal candidate must be an object.")
    if set(candidate) != {
        "schema_version",
        "type",
        "state_fingerprint",
        "changes",
        "summary",
    }:
        raise ProposalCandidateValidationError(
            "Proposal candidate fields do not match the schema."
        )
    if candidate.get("schema_version") != ASSISTANT_RESPONSE_SCHEMA_VERSION:
        raise ProposalCandidateValidationError(
            "Unsupported proposal candidate schema version."
        )
    if candidate.get("type") != PROPOSE_INPUT_CHANGES:
        raise ProposalCandidateValidationError("Unsupported proposal candidate type.")
    fingerprint = candidate.get("state_fingerprint")
    if not isinstance(fingerprint, str) or not _FINGERPRINT_PATTERN.fullmatch(
        fingerprint
    ):
        raise ProposalCandidateValidationError(
            "Proposal state fingerprint is invalid."
        )
    try:
        summary = validate_assistant_plain_text(
            candidate.get("summary"),
            field_name="Proposal summary",
            max_length=MAX_PROPOSAL_SUMMARY_LENGTH,
        )
    except AssistantResponseValidationError as exc:
        raise ProposalCandidateValidationError(
            "Proposal summary violates the plain-text policy."
        ) from exc
    changes = candidate.get("changes")
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_PROPOSAL_CHANGES:
        raise ProposalCandidateValidationError(
            f"Proposal must contain between one and {MAX_PROPOSAL_CHANGES} changes."
        )

    known_fields = set(tool_context.get("input_definitions") or {})
    normalized_changes: list[ProposalChangeCandidate] = []
    seen_fields = set()
    for index, change in enumerate(changes):
        if not isinstance(change, dict) or set(change) != {"field", "value", "unit"}:
            raise ProposalCandidateValidationError(
                "Proposal change fields do not match the schema."
            )
        field = change.get("field")
        if (
            not isinstance(field, str)
            or not field
            or len(field) > 128
            or field not in known_fields
        ):
            raise ProposalCandidateValidationError(
                "Proposal contains an unknown current-tool field."
            )
        if field in seen_fields:
            raise ProposalCandidateValidationError(
                "Proposal cannot contain duplicate fields."
            )
        seen_fields.add(field)
        unit = change.get("unit")
        if unit not in PROPOSAL_UNITS:
            raise ProposalCandidateValidationError(
                "Proposal contains an unsupported unit."
            )
        normalized_changes.append(
            {
                "field": field,
                "value": _validate_candidate_value(
                    change.get("value"), path=f"changes[{index}].value"
                ),
                "unit": unit,
            }
        )

    return {
        "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
        "type": PROPOSE_INPUT_CHANGES,
        "state_fingerprint": fingerprint,
        "changes": normalized_changes,
        "summary": summary,
    }


def validate_proposal_state_fingerprint(
    candidate: ProviderProposalCandidate,
    *,
    tool_context: ToolContext,
) -> ProviderProposalCandidate:
    validated = validate_provider_proposal_candidate(
        candidate, tool_context=tool_context
    )
    if validated["state_fingerprint"] != tool_context["tool"]["state_fingerprint"]:
        raise ProposalStateMismatchError(
            "Proposal does not match the freshly reconstructed tool state."
        )
    return validated


def parse_assistant_provider_candidate(
    candidate: Any,
    *,
    tool_context: ToolContext,
) -> AssistantResponse | ProviderProposalCandidate:
    """Parse one untrusted provider outcome into an internal bounded candidate."""
    decoded = _decode_provider_candidate(candidate)
    if decoded.get("type") == PROPOSE_INPUT_CHANGES:
        return validate_provider_proposal_candidate(decoded, tool_context=tool_context)
    return validate_assistant_response(decoded, tool_context=tool_context)


def normalize_provider_wire_candidate(candidate: Any) -> dict[str, Any]:
    """Remove strict-wire placeholders without accepting their semantics."""
    if not isinstance(candidate, dict) or set(candidate) != _WIRE_KEYS:
        raise ProposalCandidateValidationError(
            "Provider wire candidate fields do not match the schema."
        )
    if candidate.get("schema_version") != ASSISTANT_RESPONSE_SCHEMA_VERSION:
        raise ProposalCandidateValidationError(
            "Unsupported provider wire schema version."
        )
    candidate_type = candidate.get("type")
    if candidate_type not in PROVIDER_CANDIDATE_TYPES:
        raise ProposalCandidateValidationError("Unsupported provider candidate type.")

    if candidate_type == PROPOSE_INPUT_CHANGES:
        if candidate.get("message") != "" or candidate.get("fact_refs") != []:
            raise ProposalCandidateValidationError(
                "Proposal wire output contains response-only values."
            )
        return {
            key: candidate[key]
            for key in (
                "schema_version",
                "type",
                "state_fingerprint",
                "changes",
                "summary",
            )
        }

    if (
        candidate.get("state_fingerprint") != ""
        or candidate.get("changes") != []
        or candidate.get("summary") != ""
    ):
        raise ProposalCandidateValidationError(
            "Non-proposal wire output contains proposal-only values."
        )
    if candidate_type != "answer" and candidate.get("fact_refs") != []:
        raise ProposalCandidateValidationError(
            "Non-answer wire output contained fact references."
        )
    normalized = {
        "schema_version": candidate["schema_version"],
        "type": candidate_type,
        "message": candidate["message"],
    }
    if candidate_type == "answer":
        normalized["fact_refs"] = candidate["fact_refs"]
    return normalized


def build_assistant_provider_json_schema(
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Build strict provider wire schema from current application metadata."""
    validate_tool_context(tool_context)
    semantic_fields = sorted(tool_context["input_definitions"])
    return {
        "type": "object",
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [ASSISTANT_RESPONSE_SCHEMA_VERSION],
            },
            "type": {"type": "string", "enum": sorted(PROVIDER_CANDIDATE_TYPES)},
            "message": {
                "type": "string",
                "description": (
                    "Plain text for answer, clarification, or unavailable; empty "
                    "for propose_input_changes."
                ),
            },
            "fact_refs": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": MAX_ASSISTANT_FACT_REFS,
            },
            "state_fingerprint": {
                "type": "string",
                "description": (
                    "Exact current Tool Context fingerprint for a proposal; empty "
                    "for every other response type."
                ),
            },
            "changes": {
                "type": "array",
                "maxItems": MAX_PROPOSAL_CHANGES,
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "enum": semantic_fields},
                        "value": {
                            "anyOf": [
                                {"type": "number"},
                                {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": ["length", "width", "height"],
                                    },
                                    "maxItems": 3,
                                },
                            ]
                        },
                        "unit": {"type": "string", "enum": sorted(PROPOSAL_UNITS)},
                    },
                    "required": ["field", "value", "unit"],
                    "additionalProperties": False,
                },
            },
            "summary": {
                "type": "string",
                "description": (
                    "Plain-text proposal summary; empty for every other response type."
                ),
            },
        },
        "required": [
            "schema_version",
            "type",
            "message",
            "fact_refs",
            "state_fingerprint",
            "changes",
            "summary",
        ],
        "additionalProperties": False,
    }


def build_no_effective_changes_response() -> AssistantResponse:
    return {
        "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
        "type": "answer",
        "message": "The requested inputs already match the current values, so there is no effective change to preview.",
        "fact_refs": [],
    }


def is_provider_proposal_candidate(value: Any) -> bool:
    return isinstance(value, dict) and value.get("type") == PROPOSE_INPUT_CHANGES


def validate_apply_response(response: Any) -> dict[str, Any]:
    """Validate the minimal application-owned form-update response."""
    if not isinstance(response, dict) or set(response) != {
        "schema_version",
        "type",
        "fields",
        "calculation_status",
        "message",
    }:
        raise ApplyResponseValidationError("Apply response fields are invalid.")
    if response.get("schema_version") != APPLY_RESPONSE_SCHEMA_VERSION:
        raise ApplyResponseValidationError("Apply response version is not supported.")
    if response.get("type") != APPLY_RESPONSE_TYPE:
        raise ApplyResponseValidationError("Apply response type is not supported.")
    if response.get("calculation_status") not in {"ready", "incomplete"}:
        raise ApplyResponseValidationError("Apply calculation status is invalid.")
    if response.get("message") != APPLY_SUCCESS_MESSAGE:
        raise ApplyResponseValidationError("Apply response message is invalid.")
    fields = response.get("fields")
    if not isinstance(fields, list) or not 1 <= len(fields) <= MAX_PROPOSAL_CHANGES + 2:
        raise ApplyResponseValidationError("Apply response field count is invalid.")
    validated_fields = []
    seen_keys = set()
    for field in fields:
        if not isinstance(field, dict) or set(field) != {
            "field",
            "field_key",
            "value",
            "unit",
        }:
            raise ApplyResponseValidationError("Apply response field shape is invalid.")
        semantic_field = field.get("field")
        field_key = field.get("field_key")
        value = field.get("value")
        unit = field.get("unit")
        if (
            not isinstance(semantic_field, str)
            or not semantic_field
            or len(semantic_field) > 128
            or not isinstance(field_key, str)
            or not field_key
            or len(field_key) > 64
            or field_key in seen_keys
        ):
            raise ApplyResponseValidationError("Apply response field identity is invalid.")
        if isinstance(value, bool):
            if unit is not None:
                raise ApplyResponseValidationError("Boolean Apply fields cannot have units.")
        elif isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                raise ApplyResponseValidationError("Apply response values must be finite.")
            if unit not in {"mm", "g", "pcs"}:
                raise ApplyResponseValidationError("Apply response unit is invalid.")
        else:
            raise ApplyResponseValidationError("Apply response value type is invalid.")
        seen_keys.add(field_key)
        validated_fields.append(dict(field))
    normalized = {**response, "fields": validated_fields}
    encoded = json.dumps(
        normalized,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_PROVIDER_RESPONSE_BYTES:
        raise ApplyResponseValidationError("Apply response is too large.")
    return normalized


__all__ = [
    "APPLY_RESPONSE_SCHEMA_VERSION",
    "APPLY_RESPONSE_TYPE",
    "APPLY_SUCCESS_MESSAGE",
    "ApplyResponseValidationError",
    "MAX_PROPOSAL_CHANGES",
    "NoEffectiveProposalChanges",
    "PROPOSAL_CHANGE_STATUSES",
    "PROPOSAL_NOT_APPLIED_NOTICE",
    "PROPOSAL_PREVIEW_SCHEMA_VERSION",
    "PROPOSAL_PREVIEW_TYPE",
    "PROPOSE_INPUT_CHANGES",
    "ProposalCandidateValidationError",
    "ProposalStateMismatchError",
    "ProviderProposalCandidate",
    "build_assistant_provider_json_schema",
    "build_no_effective_changes_response",
    "is_provider_proposal_candidate",
    "normalize_provider_wire_candidate",
    "parse_assistant_provider_candidate",
    "validate_proposal_state_fingerprint",
    "validate_provider_proposal_candidate",
    "validate_apply_response",
]
