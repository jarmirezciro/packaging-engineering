"""Application-owned persistence for genuine unanswered knowledge questions."""

from __future__ import annotations

import hashlib
import logging

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from ..models import AIKnowledgeGap
from .contracts import AssistantMessageValidationError, validate_user_message
from .public_contracts import PublicExpertValidationError, validate_public_user_message


logger = logging.getLogger(__name__)

KNOWLEDGE_GAP_PERSISTENCE_FAILED = "knowledge_gap_persistence_failed"
_IDENTITY_SEPARATOR = "\x1f"


class KnowledgeGapValidationError(ValueError):
    """Raised internally when reviewed primitive classifications are invalid."""


def normalize_ai_knowledge_gap_question(question: str) -> str:
    """Normalize only whitespace and case for exact-repeat identity."""
    if not isinstance(question, str):
        raise KnowledgeGapValidationError("Knowledge-gap question must be text.")
    return " ".join(question.split()).casefold()


def build_ai_knowledge_gap_hash(
    *,
    question: str,
    source: str,
    knowledge_scope: str,
    reason: str,
) -> str:
    normalized = normalize_ai_knowledge_gap_question(question)
    identity = _IDENTITY_SEPARATOR.join(
        (source, knowledge_scope, reason, normalized)
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _validate_classification(
    *,
    source: str,
    surface: str,
    knowledge_scope: str,
    reason: str,
) -> None:
    if source not in AIKnowledgeGap.Source.values:
        raise KnowledgeGapValidationError("Knowledge-gap source is invalid.")
    if surface not in AIKnowledgeGap.Surface.values:
        raise KnowledgeGapValidationError("Knowledge-gap surface is invalid.")
    if knowledge_scope not in AIKnowledgeGap.KnowledgeScope.values:
        raise KnowledgeGapValidationError("Knowledge-gap scope is invalid.")
    if reason not in AIKnowledgeGap.Reason.values:
        raise KnowledgeGapValidationError("Knowledge-gap reason is invalid.")
    authenticated_surfaces = {
        AIKnowledgeGap.Surface.STANDALONE,
        AIKnowledgeGap.Surface.WORKFLOW,
    }
    public_surfaces = {
        AIKnowledgeGap.Surface.PUBLIC_SITE,
        AIKnowledgeGap.Surface.PUBLIC_TOOL,
    }
    if source == AIKnowledgeGap.Source.AUTHENTICATED and surface not in authenticated_surfaces:
        raise KnowledgeGapValidationError("Authenticated source and surface disagree.")
    if source == AIKnowledgeGap.Source.PUBLIC and surface not in public_surfaces:
        raise KnowledgeGapValidationError("Public source and surface disagree.")


def _validate_question(*, question: str, source: str) -> str:
    try:
        if source == AIKnowledgeGap.Source.PUBLIC:
            return validate_public_user_message(question)
        return validate_user_message(question)
    except (AssistantMessageValidationError, PublicExpertValidationError) as exc:
        raise KnowledgeGapValidationError("Knowledge-gap question is invalid.") from exc


def _increment_existing_gap(*, question_hash: str, seen_at):
    updated = AIKnowledgeGap.objects.filter(question_hash=question_hash).update(
        occurrence_count=F("occurrence_count") + 1,
        last_seen_at=seen_at,
    )
    if not updated:
        return None
    return AIKnowledgeGap.objects.get(question_hash=question_hash)


def _upsert_ai_knowledge_gap(
    *,
    question: str,
    question_hash: str,
    source: str,
    surface: str,
    knowledge_scope: str,
    reason: str,
) -> AIKnowledgeGap:
    seen_at = timezone.now()
    existing = _increment_existing_gap(
        question_hash=question_hash,
        seen_at=seen_at,
    )
    if existing is not None:
        return existing

    try:
        with transaction.atomic():
            return AIKnowledgeGap.objects.create(
                question_text=question,
                question_hash=question_hash,
                source=source,
                surface=surface,
                knowledge_scope=knowledge_scope,
                reason=reason,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
            )
    except IntegrityError:
        # A concurrent request inserted the same unique identity after our first
        # UPDATE. The savepoint above keeps the connection usable for one atomic
        # increment against the database-authoritative row.
        raced = _increment_existing_gap(
            question_hash=question_hash,
            seen_at=seen_at,
        )
        if raced is None:
            raise
        return raced


def register_ai_knowledge_gap(
    *,
    question: str,
    source: str,
    surface: str,
    knowledge_scope: str,
    reason: str,
) -> AIKnowledgeGap | None:
    """Best-effort exact-normalized upsert from reviewed primitive fields only."""
    try:
        _validate_classification(
            source=source,
            surface=surface,
            knowledge_scope=knowledge_scope,
            reason=reason,
        )
        validated_question = _validate_question(question=question, source=source)
        question_hash = build_ai_knowledge_gap_hash(
            question=validated_question,
            source=source,
            knowledge_scope=knowledge_scope,
            reason=reason,
        )
        return _upsert_ai_knowledge_gap(
            question=validated_question,
            question_hash=question_hash,
            source=source,
            surface=surface,
            knowledge_scope=knowledge_scope,
            reason=reason,
        )
    except Exception:
        logger.warning(
            "Knowledge-gap persistence failed safely.",
            extra={"knowledge_gap_failure_category": KNOWLEDGE_GAP_PERSISTENCE_FAILED},
        )
        return None


__all__ = [
    "KNOWLEDGE_GAP_PERSISTENCE_FAILED",
    "KnowledgeGapValidationError",
    "build_ai_knowledge_gap_hash",
    "normalize_ai_knowledge_gap_question",
    "register_ai_knowledge_gap",
]
