"""Short-lived signed references for reviewed Assistant proposals."""

from __future__ import annotations

import hmac
import math
import re
import secrets
from typing import Any

from django.core import signing

from .actions import MAX_PROPOSAL_CHANGES, PROPOSAL_UNITS
from .throttle import derive_opaque_user_key
from .workflow import is_valid_assistant_step_ref


PROPOSAL_TOKEN_SCHEMA_VERSION = "1.0"
PROPOSAL_TOKEN_MAX_AGE_SECONDS = 10 * 60
MAX_PROPOSAL_TOKEN_LENGTH = 8 * 1024
PROPOSAL_TOKEN_SALT = "packagingapp.assistant.reviewed-proposal.v1"

_FINGERPRINT_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
_NONCE_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,64}\Z")
_USER_BINDING_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class ProposalTokenError(ValueError):
    """Raised when a proposal token is malformed or fails authentication."""


class ProposalTokenExpired(ProposalTokenError):
    """Raised when a correctly signed proposal token exceeded its lifetime."""


class ProposalTokenUserMismatch(ProposalTokenError):
    """Raised when a token is presented by a different authenticated user."""


def _validate_change_value(value: Any) -> float | int | list[str]:
    if isinstance(value, bool):
        raise ProposalTokenError("Proposal token contains an invalid value type.")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ProposalTokenError("Proposal token contains a non-finite value.")
        return value
    if isinstance(value, list):
        if (
            len(value) > 3
            or any(item not in {"length", "width", "height"} for item in value)
            or len(set(value)) != len(value)
        ):
            raise ProposalTokenError("Proposal token contains invalid orientation values.")
        return list(value)
    raise ProposalTokenError("Proposal token contains an invalid value type.")


def _validate_changes(changes: Any, *, allowed_fields: set[str]) -> list[dict[str, Any]]:
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_PROPOSAL_CHANGES:
        raise ProposalTokenError("Proposal token contains an invalid change set.")
    normalized = []
    seen = set()
    for change in changes:
        if not isinstance(change, dict) or set(change) != {"field", "value", "unit"}:
            raise ProposalTokenError("Proposal token change fields are invalid.")
        field = change.get("field")
        unit = change.get("unit")
        if not isinstance(field, str) or field not in allowed_fields or field in seen:
            raise ProposalTokenError("Proposal token contains an unsupported field.")
        if unit not in PROPOSAL_UNITS:
            raise ProposalTokenError("Proposal token contains an unsupported unit.")
        seen.add(field)
        normalized.append(
            {
                "field": field,
                "value": _validate_change_value(change.get("value")),
                "unit": unit,
            }
        )
    return normalized


def _validate_payload(
    payload: Any,
    *,
    user_identifier: object,
    allowed_fields: set[str],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProposalTokenError("Proposal token payload must be an object.")
    surface = payload.get("surface")
    expected_keys = {
        "schema_version",
        "proposal_schema_version",
        "tool",
        "surface",
        "state_fingerprint",
        "changes",
        "user_binding",
        "nonce",
    }
    if surface == "workflow":
        expected_keys.add("step_ref")
    if set(payload) != expected_keys:
        raise ProposalTokenError("Proposal token payload fields are invalid.")
    if payload.get("schema_version") != PROPOSAL_TOKEN_SCHEMA_VERSION:
        raise ProposalTokenError("Proposal token version is not supported.")
    if payload.get("proposal_schema_version") != "1.1":
        raise ProposalTokenError("Proposal schema version is not supported.")
    if payload.get("tool") != "container_selection":
        raise ProposalTokenError("Proposal token tool is not supported.")
    if surface not in {"standalone", "workflow"}:
        raise ProposalTokenError("Proposal token surface is not supported.")
    fingerprint = payload.get("state_fingerprint")
    if not isinstance(fingerprint, str) or not _FINGERPRINT_PATTERN.fullmatch(fingerprint):
        raise ProposalTokenError("Proposal token fingerprint is invalid.")
    nonce = payload.get("nonce")
    if not isinstance(nonce, str) or not _NONCE_PATTERN.fullmatch(nonce):
        raise ProposalTokenError("Proposal token identity is invalid.")
    binding = payload.get("user_binding")
    if not isinstance(binding, str) or not _USER_BINDING_PATTERN.fullmatch(binding):
        raise ProposalTokenError("Proposal token user binding is invalid.")
    expected_binding = derive_opaque_user_key(user_identifier)
    if not hmac.compare_digest(binding, expected_binding):
        raise ProposalTokenUserMismatch("Proposal token belongs to another user.")
    if surface == "workflow" and not is_valid_assistant_step_ref(payload.get("step_ref")):
        raise ProposalTokenError("Proposal token workflow binding is invalid.")

    return {
        **payload,
        "changes": _validate_changes(
            payload.get("changes"),
            allowed_fields=allowed_fields,
        ),
    }


def issue_reviewed_proposal_token(
    *,
    user_identifier: object,
    tool: str,
    surface: str,
    state_fingerprint: str,
    changes: list[dict[str, Any]],
    allowed_fields: set[str],
    step_ref: str | None = None,
) -> str:
    """Issue one authenticated, timestamped proposal reference."""
    payload = {
        "schema_version": PROPOSAL_TOKEN_SCHEMA_VERSION,
        "proposal_schema_version": "1.1",
        "tool": tool,
        "surface": surface,
        "state_fingerprint": state_fingerprint,
        "changes": changes,
        "user_binding": derive_opaque_user_key(user_identifier),
        "nonce": secrets.token_urlsafe(18),
    }
    if surface == "workflow":
        payload["step_ref"] = step_ref
    validated = _validate_payload(
        payload,
        user_identifier=user_identifier,
        allowed_fields=allowed_fields,
    )
    token = signing.dumps(validated, salt=PROPOSAL_TOKEN_SALT, compress=True)
    if len(token) > MAX_PROPOSAL_TOKEN_LENGTH:
        raise ProposalTokenError("Proposal token exceeds the application size limit.")
    return token


def load_reviewed_proposal_token(
    token: Any,
    *,
    user_identifier: object,
    allowed_fields: set[str],
    max_age: int = PROPOSAL_TOKEN_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Authenticate, expire, and strictly validate a reviewed proposal token."""
    if not isinstance(token, str) or not token or len(token) > MAX_PROPOSAL_TOKEN_LENGTH:
        raise ProposalTokenError("Proposal token is invalid.")
    try:
        payload = signing.loads(
            token,
            salt=PROPOSAL_TOKEN_SALT,
            max_age=max_age,
        )
    except signing.SignatureExpired as exc:
        raise ProposalTokenExpired("Proposal token has expired.") from exc
    except signing.BadSignature as exc:
        raise ProposalTokenError("Proposal token signature is invalid.") from exc
    return _validate_payload(
        payload,
        user_identifier=user_identifier,
        allowed_fields=allowed_fields,
    )


__all__ = [
    "MAX_PROPOSAL_TOKEN_LENGTH",
    "PROPOSAL_TOKEN_MAX_AGE_SECONDS",
    "PROPOSAL_TOKEN_SCHEMA_VERSION",
    "ProposalTokenError",
    "ProposalTokenExpired",
    "ProposalTokenUserMismatch",
    "issue_reviewed_proposal_token",
    "load_reviewed_proposal_token",
]
