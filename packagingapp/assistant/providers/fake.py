"""Deterministic offline provider used by assistant-service tests."""

from __future__ import annotations

import json

from ..contracts import (
    ASSISTANT_KNOWLEDGE_GAP_MESSAGE,
    ASSISTANT_RESPONSE_SCHEMA_VERSION,
    MAX_PROVIDER_RESPONSE_BYTES,
    ToolContext,
)
from ..clarification import ClarificationContext
from ..actions import MAX_PROPOSAL_CHANGES, PROPOSE_INPUT_CHANGES
from ..prompts import AssistantInstructions
from ..knowledge import KnowledgeContext
from ..public_contracts import (
    PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION,
    PublicExpertContext,
    PublicKnowledgeContext,
)
from .base import AssistantProviderTimeout, AssistantProviderUnavailable


FAKE_PROVIDER_MODES = frozenset(
    {
        "success_answer",
        "success_clarification",
        "success_knowledge_gap",
        "malformed_response",
        "unknown_response_type",
        "missing_required_field",
        "oversized_response",
        "timeout",
        "provider_error",
        "invalid_fact_reference",
        "valid_single_proposal",
        "valid_multi_proposal",
        "unknown_proposal_field",
        "invalid_proposal_unit",
        "invalid_proposal_value_type",
        "stale_proposal_fingerprint",
        "too_many_proposal_changes",
        "extra_proposal_property",
        "malformed_proposal",
    }
)


def _json_response(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class FakeAssistantProvider:
    provider_id = "fake"

    def __init__(self, mode: str = "success_answer"):
        if mode not in FAKE_PROVIDER_MODES:
            raise ValueError("Unsupported fake assistant provider mode.")
        self.mode = mode
        self.call_count = 0
        self.last_timeout_seconds = None

    def generate(
        self,
        *,
        message: str,
        tool_context: ToolContext,
        instructions: AssistantInstructions,
        timeout_seconds: float,
        knowledge_context: KnowledgeContext | None = None,
        clarification_context: ClarificationContext | None = None,
    ):
        self.call_count += 1
        self.last_timeout_seconds = timeout_seconds

        if self.mode == "timeout":
            raise AssistantProviderTimeout("deterministic fake timeout detail")
        if self.mode == "provider_error":
            raise AssistantProviderUnavailable("deterministic fake provider detail")
        if self.mode == "malformed_response":
            return "{not-json"
        if self.mode == "unknown_response_type":
            return _json_response(
                {
                    "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                    "type": "apply_changes",
                    "message": "This response type is intentionally unsupported.",
                }
            )
        if self.mode == "missing_required_field":
            return _json_response(
                {
                    "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                    "type": "answer",
                    "fact_refs": [],
                }
            )
        if self.mode == "oversized_response":
            return _json_response(
                {
                    "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                    "type": "answer",
                    "message": "x" * (MAX_PROVIDER_RESPONSE_BYTES + 1),
                    "fact_refs": [],
                }
            )
        if self.mode == "invalid_fact_reference":
            return _json_response(
                {
                    "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                    "type": "answer",
                    "message": "This answer intentionally cites a nonexistent fact.",
                    "fact_refs": ["nonexistent_context_fact"],
                }
            )
        if self.mode == "success_clarification":
            return _json_response(
                {
                    "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                    "type": "clarifying_question",
                    "message": "Which part of the current KolliPack state should I explain?",
                }
            )
        if self.mode == "success_knowledge_gap":
            return _json_response(
                {
                    "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                    "type": "knowledge_gap",
                    "message": ASSISTANT_KNOWLEDGE_GAP_MESSAGE,
                }
            )

        if self.mode.endswith("proposal") or self.mode in {
            "unknown_proposal_field",
            "invalid_proposal_unit",
            "invalid_proposal_value_type",
            "stale_proposal_fingerprint",
            "too_many_proposal_changes",
            "extra_proposal_property",
        }:
            return _json_response(_proposal_for_mode(self.mode, tool_context))

        return _json_response(_answer_for_context(tool_context))

    def generate_public(
        self,
        *,
        message: str,
        expert_context: PublicExpertContext,
        instructions: AssistantInstructions,
        timeout_seconds: float,
        max_output_tokens: int,
        knowledge_context: PublicKnowledgeContext,
        clarification_context: ClarificationContext | None = None,
    ):
        self.call_count += 1
        self.last_timeout_seconds = timeout_seconds
        if self.mode == "timeout":
            raise AssistantProviderTimeout("deterministic fake timeout detail")
        if self.mode == "provider_error":
            raise AssistantProviderUnavailable("deterministic fake provider detail")
        if self.mode == "malformed_response":
            return "{not-json"
        if self.mode == "oversized_response":
            return _json_response(
                {
                    "schema_version": PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION,
                    "type": "answer",
                    "message": "x" * (MAX_PROVIDER_RESPONSE_BYTES + 1),
                }
            )
        if self.mode == "success_clarification":
            return _json_response(
                {
                    "schema_version": PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION,
                    "type": "clarifying_question",
                    "message": "Which KolliPack concept would you like me to explain?",
                }
            )
        return _json_response(
            {
                "schema_version": PUBLIC_EXPERT_RESPONSE_SCHEMA_VERSION,
                "type": "answer",
                "message": "KolliPack provides deterministic packaging-engineering tools.",
            }
        )


def _proposal_for_mode(mode: str, tool_context: ToolContext):
    fingerprint = tool_context["tool"]["state_fingerprint"]
    changes = [
        {
            "field": "product.dimensions.length",
            "value": 320,
            "unit": "mm",
        }
    ]
    if mode == "valid_multi_proposal":
        changes.extend(
            [
                {
                    "field": "product.dimensions.width",
                    "value": 180,
                    "unit": "mm",
                },
                {
                    "field": "request.desired_quantity",
                    "value": 24,
                    "unit": "pcs",
                },
            ]
        )
    elif mode == "unknown_proposal_field":
        changes[0]["field"] = "engine.global_optimization"
    elif mode == "invalid_proposal_unit":
        changes[0]["unit"] = "inch"
    elif mode == "invalid_proposal_value_type":
        changes[0]["value"] = {"hidden": "object"}
    elif mode == "stale_proposal_fingerprint":
        fingerprint = "sha256:" + ("0" * 64)
    elif mode == "too_many_proposal_changes":
        changes = [
            {"field": f"unknown.field.{index}", "value": index + 1, "unit": "mm"}
            for index in range(MAX_PROPOSAL_CHANGES + 1)
        ]

    candidate = {
        "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
        "type": PROPOSE_INPUT_CHANGES,
        "state_fingerprint": fingerprint,
        "changes": changes,
        "summary": "Set the requested Container inputs.",
    }
    if mode == "extra_proposal_property":
        candidate["apply"] = True
    elif mode == "malformed_proposal":
        candidate.pop("changes")
    return candidate


def _answer_for_context(tool_context: ToolContext):
    status = tool_context["tool"]["calculation_status"]
    facts = {
        fact.get("code"): fact
        for fact in tool_context.get("explanation_facts", [])
        if isinstance(fact, dict) and isinstance(fact.get("code"), str)
    }
    maximum = facts.get("maximum_geometric_quantity")
    if status == "complete" and maximum is not None:
        return {
            "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
            "type": "answer",
            "message": (
                "The current result reports a maximum geometric quantity of "
                f"{maximum.get('value')} units."
            ),
            "fact_refs": ["maximum_geometric_quantity"],
        }

    messages = {
        "empty": "The current tool context is empty. Add the required product and container information before calculating.",
        "partial": "The current inputs are incomplete. Complete the missing information identified by KolliPack.",
        "invalid": "KolliPack has reported validation errors in the current inputs.",
        "ready": "The current inputs are ready for calculation, but no current result is available.",
        "complete": "A current validated KolliPack result is available for explanation.",
        "stale": "The retained result is stale because inputs changed, so it is not available as the current result.",
    }
    return {
        "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
        "type": "answer",
        "message": messages[status],
        "fact_refs": [],
    }
