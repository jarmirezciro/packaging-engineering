"""Bounded, application-owned clarification continuity.

Clarification Context carries only the unresolved dialogue needed to interpret
the current message. It is deliberately separate from Tool Context and
Knowledge Context and never grants engineering or action authority.
"""

from __future__ import annotations

import hmac
import json
import re
import secrets
from typing import Any, Literal, TypedDict

from django.core import signing

from .contracts import (
    MAX_CLARIFYING_QUESTION_LENGTH,
    MAX_USER_MESSAGE_LENGTH,
    AssistantResponseValidationError,
    validate_assistant_plain_text,
)
from .public_contracts import PUBLIC_EXPERT_CAPABILITY
from .public_throttle import derive_opaque_public_session_key
from .prompts import READ_ONLY_CAPABILITY
from .throttle import derive_opaque_user_key
from .workflow import is_valid_assistant_step_ref


CLARIFICATION_CONTEXT_SCHEMA_VERSION = "1.0"
CONTINUATION_TOKEN_SCHEMA_VERSION = "1.0"
CONTINUATION_TOKEN_MAX_AGE_SECONDS = 10 * 60
CONTINUATION_TOKEN_SALT = "packagingapp.assistant.clarification.v1"

MAX_CLARIFICATION_ROUNDS = 2
MAX_CLARIFICATION_TURNS = MAX_CLARIFICATION_ROUNDS * 2
MAX_CLARIFICATION_USER_MESSAGE_LENGTH = MAX_USER_MESSAGE_LENGTH
MAX_CLARIFICATION_ASSISTANT_MESSAGE_LENGTH = MAX_CLARIFYING_QUESTION_LENGTH
MAX_CLARIFICATION_TEXT_CHARS = 5_000
MAX_CLARIFICATION_CONTEXT_BYTES = 8 * 1024
MAX_CONTINUATION_TOKEN_LENGTH = 12 * 1024
MAX_CLARIFICATION_RETRIEVAL_QUERY_CHARS = 6_000

CLARIFICATION_DEPTH_MESSAGE = (
    "I still need more information to understand the request reliably. "
    "Please restate the request with the missing details included."
)
STALE_CONTINUATION_MESSAGE = (
    "The tool inputs changed since I asked that clarification. "
    "Please repeat the request for the current inputs."
)
EXPIRED_CONTINUATION_MESSAGE = (
    "That clarification has expired. Please repeat the original request."
)
INVALID_CONTINUATION_MESSAGE = (
    "That clarification can no longer be continued safely. "
    "Please repeat the original request."
)

_FINGERPRINT_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IDENTIFIER_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_NONCE_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,64}\Z")
_BINDING_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_AUTHENTICATED_SURFACES = frozenset({"standalone", "workflow"})
_PUBLIC_SURFACES = frozenset({"public_site", "public_tool"})


class ClarificationTurn(TypedDict):
    role: Literal["user", "assistant"]
    message: str


class ClarificationContext(TypedDict):
    schema_version: str
    turns: list[ClarificationTurn]


class ClarificationContextError(ValueError):
    """Raised when bounded clarification data violates its strict contract."""


class ClarificationDepthExceeded(ClarificationContextError):
    """Raised when a third assistant clarification would be required."""


class ContinuationTokenError(ValueError):
    """Raised when a continuation token is malformed or unauthenticated."""


class ContinuationTokenExpired(ContinuationTokenError):
    """Raised when a correctly signed continuation token exceeded its lifetime."""


class ContinuationTokenBindingMismatch(ContinuationTokenError):
    """Raised when a token is valid but belongs to a different authority scope."""


class ContinuationTokenStale(ContinuationTokenError):
    """Raised when authenticated engineering state changed during clarification."""


def _has_unsupported_control_characters(value: str) -> bool:
    return any(ord(character) < 32 and character not in "\n\r\t" for character in value)


def _validate_user_turn_message(message: Any) -> str:
    if not isinstance(message, str):
        raise ClarificationContextError("Clarification user messages must be text.")
    normalized = message.strip()
    if not normalized or len(normalized) > MAX_CLARIFICATION_USER_MESSAGE_LENGTH:
        raise ClarificationContextError("Clarification user message length is invalid.")
    if _has_unsupported_control_characters(normalized):
        raise ClarificationContextError(
            "Clarification user message contains unsupported control characters."
        )
    return normalized


def _validate_assistant_turn_message(message: Any) -> str:
    try:
        return validate_assistant_plain_text(
            message,
            field_name="Clarification assistant message",
            max_length=MAX_CLARIFICATION_ASSISTANT_MESSAGE_LENGTH,
        )
    except AssistantResponseValidationError as exc:
        raise ClarificationContextError(
            "Clarification assistant message violates the plain-text policy."
        ) from exc


def validate_clarification_context(context: Any) -> ClarificationContext:
    """Validate an exact one- or two-round unresolved clarification chain."""
    if not isinstance(context, dict) or set(context) != {"schema_version", "turns"}:
        raise ClarificationContextError("Clarification Context fields do not match schema.")
    if context.get("schema_version") != CLARIFICATION_CONTEXT_SCHEMA_VERSION:
        raise ClarificationContextError("Unsupported Clarification Context version.")
    turns = context.get("turns")
    if not isinstance(turns, list) or len(turns) not in {2, 4}:
        raise ClarificationContextError("Clarification Context turn count is invalid.")

    normalized: list[ClarificationTurn] = []
    total_chars = 0
    for index, turn in enumerate(turns):
        if not isinstance(turn, dict) or set(turn) != {"role", "message"}:
            raise ClarificationContextError("Clarification turn fields are invalid.")
        expected_role = "user" if index % 2 == 0 else "assistant"
        if turn.get("role") != expected_role:
            raise ClarificationContextError("Clarification roles must alternate.")
        message = (
            _validate_user_turn_message(turn.get("message"))
            if expected_role == "user"
            else _validate_assistant_turn_message(turn.get("message"))
        )
        total_chars += len(message)
        normalized.append({"role": expected_role, "message": message})

    if total_chars > MAX_CLARIFICATION_TEXT_CHARS:
        raise ClarificationContextError("Clarification text exceeds the total limit.")
    normalized_context: ClarificationContext = {
        "schema_version": CLARIFICATION_CONTEXT_SCHEMA_VERSION,
        "turns": normalized,
    }
    encoded = json.dumps(
        normalized_context,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_CLARIFICATION_CONTEXT_BYTES:
        raise ClarificationContextError("Clarification Context exceeds the byte limit.")
    return normalized_context


def canonical_clarification_json(context: ClarificationContext) -> str:
    validated = validate_clarification_context(context)
    return json.dumps(
        validated,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def clarification_depth(context: ClarificationContext) -> int:
    return len(validate_clarification_context(context)["turns"]) // 2


def build_next_clarification_context(
    *,
    previous_context: ClarificationContext | None,
    current_user_message: str,
    assistant_question: str,
) -> ClarificationContext:
    """Append one validated user/assistant pair without summarizing or trimming."""
    turns: list[ClarificationTurn] = []
    if previous_context is not None:
        validated_previous = validate_clarification_context(previous_context)
        if clarification_depth(validated_previous) >= MAX_CLARIFICATION_ROUNDS:
            raise ClarificationDepthExceeded("Maximum clarification depth reached.")
        turns.extend(validated_previous["turns"])
    turns.extend(
        [
            {"role": "user", "message": current_user_message},
            {"role": "assistant", "message": assistant_question},
        ]
    )
    return validate_clarification_context(
        {
            "schema_version": CLARIFICATION_CONTEXT_SCHEMA_VERSION,
            "turns": turns,
        }
    )


def build_clarification_retrieval_query(
    current_user_message: str,
    clarification_context: ClarificationContext | None,
) -> str:
    """Build one bounded deterministic retrieval query; never a knowledge source."""
    current = _validate_user_turn_message(current_user_message)
    if clarification_context is None:
        return current
    validated = validate_clarification_context(clarification_context)
    turns = validated["turns"]
    query = (
        f"Current user message: {current}\n"
        f"Initial unresolved request: {turns[0]['message']}\n"
        f"Most recent assistant clarification: {turns[-1]['message']}"
    )
    return query[:MAX_CLARIFICATION_RETRIEVAL_QUERY_CHARS]


def is_probable_short_clarification_reply(message: str) -> bool:
    """Identify only compact replies for preserving deterministic public boundaries."""
    normalized = " ".join(_validate_user_turn_message(message).lower().split())
    if len(normalized) > 120 or "?" in normalized:
        return False
    new_topic_prefixes = (
        "actually",
        "forget that",
        "new question",
        "what ",
        "why ",
        "how ",
        "which ",
        "explain ",
        "tell me ",
    )
    return not normalized.startswith(new_topic_prefixes)


def _validate_common_payload(payload: Any) -> tuple[ClarificationContext, int]:
    context = payload.get("clarification_context")
    try:
        validated_context = validate_clarification_context(context)
    except ClarificationContextError as exc:
        raise ContinuationTokenError(
            "Continuation Clarification Context is invalid."
        ) from exc
    depth = payload.get("clarification_depth")
    if isinstance(depth, bool) or not isinstance(depth, int):
        raise ContinuationTokenError("Continuation depth is invalid.")
    if depth not in {1, 2} or depth != clarification_depth(validated_context):
        raise ContinuationTokenError("Continuation depth does not match its context.")
    nonce = payload.get("nonce")
    if not isinstance(nonce, str) or not _NONCE_PATTERN.fullmatch(nonce):
        raise ContinuationTokenError("Continuation token identity is invalid.")
    return validated_context, depth


def _loads(token: Any, *, max_age: int) -> dict[str, Any]:
    if not isinstance(token, str) or not token or len(token) > MAX_CONTINUATION_TOKEN_LENGTH:
        raise ContinuationTokenError("Continuation token is invalid.")
    try:
        payload = signing.loads(
            token,
            salt=CONTINUATION_TOKEN_SALT,
            max_age=max_age,
        )
    except signing.SignatureExpired as exc:
        raise ContinuationTokenExpired("Continuation token expired.") from exc
    except signing.BadSignature as exc:
        raise ContinuationTokenError("Continuation token signature is invalid.") from exc
    if not isinstance(payload, dict):
        raise ContinuationTokenError("Continuation token payload is invalid.")
    return payload


def _dumps(payload: dict[str, Any]) -> str:
    token = signing.dumps(payload, salt=CONTINUATION_TOKEN_SALT, compress=True)
    if len(token) > MAX_CONTINUATION_TOKEN_LENGTH:
        raise ContinuationTokenError("Continuation token exceeds the size limit.")
    return token


def issue_authenticated_continuation_token(
    *,
    clarification_context: ClarificationContext,
    user_identifier: object,
    tool: str,
    surface: str,
    state_fingerprint: str,
    step_ref: str | None = None,
) -> str:
    if not isinstance(tool, str) or not _IDENTIFIER_PATTERN.fullmatch(tool):
        raise ContinuationTokenError("Continuation tool binding is invalid.")
    if surface not in _AUTHENTICATED_SURFACES:
        raise ContinuationTokenError("Continuation surface binding is invalid.")
    if not isinstance(state_fingerprint, str) or not _FINGERPRINT_PATTERN.fullmatch(
        state_fingerprint
    ):
        raise ContinuationTokenError("Continuation state binding is invalid.")
    if surface == "workflow" and not is_valid_assistant_step_ref(step_ref):
        raise ContinuationTokenError("Continuation workflow binding is invalid.")
    context = validate_clarification_context(clarification_context)
    payload: dict[str, Any] = {
        "schema_version": CONTINUATION_TOKEN_SCHEMA_VERSION,
        "capability": READ_ONLY_CAPABILITY,
        "tool": tool,
        "surface": surface,
        "state_fingerprint": state_fingerprint,
        "clarification_context": context,
        "clarification_depth": clarification_depth(context),
        "user_binding": derive_opaque_user_key(user_identifier),
        "nonce": secrets.token_urlsafe(18),
    }
    if surface == "workflow":
        payload["step_ref"] = step_ref
    return _dumps(payload)


def load_authenticated_continuation_token(
    token: Any,
    *,
    user_identifier: object,
    tool: str,
    surface: str,
    state_fingerprint: str,
    step_ref: str | None = None,
    max_age: int = CONTINUATION_TOKEN_MAX_AGE_SECONDS,
) -> ClarificationContext:
    payload = _loads(token, max_age=max_age)
    expected_keys = {
        "schema_version",
        "capability",
        "tool",
        "surface",
        "state_fingerprint",
        "clarification_context",
        "clarification_depth",
        "user_binding",
        "nonce",
    }
    if payload.get("surface") == "workflow":
        expected_keys.add("step_ref")
    if set(payload) != expected_keys:
        raise ContinuationTokenError("Continuation token fields are invalid.")
    if payload.get("schema_version") != CONTINUATION_TOKEN_SCHEMA_VERSION:
        raise ContinuationTokenError("Continuation token version is unsupported.")
    context, _depth = _validate_common_payload(payload)
    binding = payload.get("user_binding")
    if not isinstance(binding, str) or not _BINDING_PATTERN.fullmatch(binding):
        raise ContinuationTokenError("Continuation user binding is invalid.")
    expected_binding = derive_opaque_user_key(user_identifier)
    if not hmac.compare_digest(binding, expected_binding):
        raise ContinuationTokenBindingMismatch("Continuation token belongs to another user.")
    if (
        payload.get("capability") != READ_ONLY_CAPABILITY
        or payload.get("tool") != tool
        or payload.get("surface") != surface
    ):
        raise ContinuationTokenBindingMismatch("Continuation token scope does not match.")
    if surface == "workflow":
        if not is_valid_assistant_step_ref(step_ref) or payload.get("step_ref") != step_ref:
            raise ContinuationTokenBindingMismatch("Continuation workflow step does not match.")
    elif "step_ref" in payload:
        raise ContinuationTokenError("Standalone continuation cannot contain a step binding.")
    if payload.get("state_fingerprint") != state_fingerprint:
        raise ContinuationTokenStale("Continuation state fingerprint is stale.")
    return context


def issue_public_continuation_token(
    *,
    clarification_context: ClarificationContext,
    session_key: str,
    surface: str,
    knowledge_scope: str,
) -> str:
    if surface not in _PUBLIC_SURFACES:
        raise ContinuationTokenError("Public continuation surface is invalid.")
    if not isinstance(knowledge_scope, str) or not _IDENTIFIER_PATTERN.fullmatch(
        knowledge_scope
    ):
        raise ContinuationTokenError("Public continuation scope is invalid.")
    context = validate_clarification_context(clarification_context)
    payload = {
        "schema_version": CONTINUATION_TOKEN_SCHEMA_VERSION,
        "capability": PUBLIC_EXPERT_CAPABILITY,
        "surface": surface,
        "knowledge_scope": knowledge_scope,
        "clarification_context": context,
        "clarification_depth": clarification_depth(context),
        "session_binding": derive_opaque_public_session_key(session_key),
        "nonce": secrets.token_urlsafe(18),
    }
    return _dumps(payload)


def load_public_continuation_token(
    token: Any,
    *,
    session_key: str,
    surface: str,
    knowledge_scope: str,
    max_age: int = CONTINUATION_TOKEN_MAX_AGE_SECONDS,
) -> ClarificationContext:
    payload = _loads(token, max_age=max_age)
    expected_keys = {
        "schema_version",
        "capability",
        "surface",
        "knowledge_scope",
        "clarification_context",
        "clarification_depth",
        "session_binding",
        "nonce",
    }
    if set(payload) != expected_keys:
        raise ContinuationTokenError("Public continuation token fields are invalid.")
    if payload.get("schema_version") != CONTINUATION_TOKEN_SCHEMA_VERSION:
        raise ContinuationTokenError("Public continuation token version is unsupported.")
    context, _depth = _validate_common_payload(payload)
    binding = payload.get("session_binding")
    if not isinstance(binding, str) or not _BINDING_PATTERN.fullmatch(binding):
        raise ContinuationTokenError("Public continuation session binding is invalid.")
    expected_binding = derive_opaque_public_session_key(session_key)
    if not hmac.compare_digest(binding, expected_binding):
        raise ContinuationTokenBindingMismatch(
            "Public continuation token belongs to another session."
        )
    if (
        payload.get("capability") != PUBLIC_EXPERT_CAPABILITY
        or payload.get("surface") != surface
        or payload.get("knowledge_scope") != knowledge_scope
    ):
        raise ContinuationTokenBindingMismatch("Public continuation scope does not match.")
    return context


__all__ = [
    "CLARIFICATION_CONTEXT_SCHEMA_VERSION",
    "CLARIFICATION_DEPTH_MESSAGE",
    "CONTINUATION_TOKEN_MAX_AGE_SECONDS",
    "CONTINUATION_TOKEN_SALT",
    "CONTINUATION_TOKEN_SCHEMA_VERSION",
    "EXPIRED_CONTINUATION_MESSAGE",
    "INVALID_CONTINUATION_MESSAGE",
    "MAX_CLARIFICATION_ASSISTANT_MESSAGE_LENGTH",
    "MAX_CLARIFICATION_CONTEXT_BYTES",
    "MAX_CLARIFICATION_ROUNDS",
    "MAX_CLARIFICATION_TEXT_CHARS",
    "MAX_CLARIFICATION_TURNS",
    "MAX_CONTINUATION_TOKEN_LENGTH",
    "STALE_CONTINUATION_MESSAGE",
    "ClarificationContext",
    "ClarificationContextError",
    "ClarificationDepthExceeded",
    "ContinuationTokenBindingMismatch",
    "ContinuationTokenError",
    "ContinuationTokenExpired",
    "ContinuationTokenStale",
    "build_clarification_retrieval_query",
    "build_next_clarification_context",
    "canonical_clarification_json",
    "clarification_depth",
    "is_probable_short_clarification_reply",
    "issue_authenticated_continuation_token",
    "issue_public_continuation_token",
    "load_authenticated_continuation_token",
    "load_public_continuation_token",
    "validate_clarification_context",
]
