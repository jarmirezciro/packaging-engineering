import hashlib
import inspect
import json
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from packagingapp.admin import AIKnowledgeGapAdmin
from packagingapp.assistant.contracts import (
    ASSISTANT_KNOWLEDGE_GAP_MESSAGE,
    ASSISTANT_RESPONSE_SCHEMA_VERSION,
    ASSISTANT_UNAVAILABLE_MESSAGE,
)
from packagingapp.assistant.knowledge import empty_knowledge_context
from packagingapp.assistant.knowledge_gaps import (
    build_ai_knowledge_gap_hash,
    normalize_ai_knowledge_gap_question,
    register_ai_knowledge_gap,
)
from packagingapp.assistant.public_contracts import (
    PUBLIC_KNOWLEDGE_FALLBACK_MESSAGE,
    empty_public_knowledge_context,
)
from packagingapp.models import AIKnowledgeGap, UserSubscription


def ready_state():
    return {
        "mode": "single",
        "action": "refresh",
        "product_source": "manual",
        "product_l": "10",
        "product_w": "8",
        "product_h": "6",
        "product_weight": "25",
        "desired_qty": "4",
        "product_shape": "cuboid",
        "r1": True,
        "r2": True,
        "r3": True,
        "container_source": "manual",
        "box_l": "40",
        "box_w": "30",
        "box_h": "20",
        "box_thickness_mm": "",
        "box_weight": "100",
        "box_max_payload": "1000",
    }


class AIKnowledgeGapServiceTests(TestCase):
    def register(self, question="Why P2 make better result?", **overrides):
        values = {
            "question": question,
            "source": AIKnowledgeGap.Source.AUTHENTICATED,
            "surface": AIKnowledgeGap.Surface.STANDALONE,
            "knowledge_scope": AIKnowledgeGap.KnowledgeScope.CONTAINER_SELECTION,
            "reason": AIKnowledgeGap.Reason.DOCUMENTATION_GAP,
        }
        values.update(overrides)
        return register_ai_knowledge_gap(**values)

    def test_valid_gap_creation_defaults_timestamps_and_exact_hash(self):
        before = self.register()

        self.assertIsNotNone(before)
        gap = AIKnowledgeGap.objects.get()
        self.assertEqual(gap.question_text, "Why P2 make better result?")
        self.assertEqual(gap.status, AIKnowledgeGap.Status.NEW)
        self.assertEqual(gap.occurrence_count, 1)
        self.assertIsNotNone(gap.first_seen_at)
        self.assertIsNotNone(gap.last_seen_at)
        self.assertLessEqual(gap.first_seen_at, gap.last_seen_at)
        identity = "\x1f".join(
            (
                "authenticated",
                "container_selection",
                "documentation_gap",
                "why p2 make better result?",
            )
        )
        self.assertEqual(
            gap.question_hash,
            hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        )

    def test_normalized_repeat_increments_and_preserves_original_wording(self):
        original = "Why   P2 make\nbetter result?"
        first = self.register(original)
        first_seen = first.first_seen_at
        second = self.register("  WHY P2 MAKE BETTER RESULT?  ")

        self.assertEqual(AIKnowledgeGap.objects.count(), 1)
        first.refresh_from_db()
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(first.question_text, original)
        self.assertEqual(first.occurrence_count, 2)
        self.assertEqual(first.first_seen_at, first_seen)
        self.assertGreaterEqual(first.last_seen_at, first_seen)
        self.assertEqual(
            normalize_ai_knowledge_gap_question("  Straße\tFRAGE  "),
            "strasse frage",
        )

    def test_identity_separates_question_scope_reason_and_source_not_surface(self):
        self.register("Question one")
        self.register("Question two")
        self.register(
            "Question one",
            knowledge_scope=AIKnowledgeGap.KnowledgeScope.BAG_SELECTION,
        )
        self.register(
            "Question one",
            reason=AIKnowledgeGap.Reason.CLARIFICATION_EXHAUSTED,
        )
        self.register(
            "Question one",
            source=AIKnowledgeGap.Source.PUBLIC,
            surface=AIKnowledgeGap.Surface.PUBLIC_SITE,
        )
        self.register(
            "Question one",
            source=AIKnowledgeGap.Source.PUBLIC,
            surface=AIKnowledgeGap.Surface.PUBLIC_TOOL,
        )

        self.assertEqual(AIKnowledgeGap.objects.count(), 5)
        public_gap = AIKnowledgeGap.objects.get(source=AIKnowledgeGap.Source.PUBLIC)
        self.assertEqual(public_gap.occurrence_count, 2)
        self.assertEqual(public_gap.surface, AIKnowledgeGap.Surface.PUBLIC_SITE)

    def test_unique_constraint_is_database_authority(self):
        values = {
            "question_text": "First",
            "question_hash": "a" * 64,
            "source": AIKnowledgeGap.Source.AUTHENTICATED,
            "surface": AIKnowledgeGap.Surface.STANDALONE,
            "knowledge_scope": AIKnowledgeGap.KnowledgeScope.CONTAINER_SELECTION,
            "reason": AIKnowledgeGap.Reason.DOCUMENTATION_GAP,
        }
        AIKnowledgeGap.objects.create(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AIKnowledgeGap.objects.create(**values)

    def test_concurrent_insert_collision_uses_atomic_increment_path(self):
        raced = AIKnowledgeGap.objects.create(
            question_text="Raced",
            question_hash="b" * 64,
            source=AIKnowledgeGap.Source.AUTHENTICATED,
            surface=AIKnowledgeGap.Surface.STANDALONE,
            knowledge_scope=AIKnowledgeGap.KnowledgeScope.CONTAINER_SELECTION,
            reason=AIKnowledgeGap.Reason.DOCUMENTATION_GAP,
        )
        with patch(
            "packagingapp.assistant.knowledge_gaps._increment_existing_gap",
            side_effect=(None, raced),
        ) as increment, patch.object(
            AIKnowledgeGap.objects,
            "create",
            side_effect=IntegrityError("simulated unique race"),
        ):
            result = self.register("Concurrent question")

        self.assertEqual(result, raced)
        self.assertEqual(increment.call_count, 2)

    def test_service_and_model_have_no_identity_or_engineering_fields(self):
        allowed_parameters = {
            "question",
            "source",
            "surface",
            "knowledge_scope",
            "reason",
        }
        self.assertEqual(
            set(inspect.signature(register_ai_knowledge_gap).parameters),
            allowed_parameters,
        )
        forbidden = {
            "user",
            "user_id",
            "username",
            "email",
            "ip_address",
            "session_id",
            "session_key",
            "tool_context",
            "knowledge_context",
            "result",
            "proposal",
            "token",
            "provider_metadata",
        }
        model_fields = {field.name for field in AIKnowledgeGap._meta.fields}
        self.assertTrue(forbidden.isdisjoint(model_fields))
        for field in forbidden:
            with self.subTest(field=field), self.assertRaises(TypeError):
                self.register(**{field: object()})

    def test_invalid_reviewed_classification_fails_closed_without_a_row(self):
        with self.assertLogs(
            "packagingapp.assistant.knowledge_gaps", level="WARNING"
        ) as logs:
            result = self.register(source="unknown")
        self.assertIsNone(result)
        self.assertFalse(AIKnowledgeGap.objects.exists())
        self.assertIn("knowledge_gap_persistence_failed", repr(logs.records[0].__dict__))
        self.assertNotIn("Why P2", logs.output[0])

    def test_admin_is_review_only_except_for_status(self):
        model_admin = AIKnowledgeGapAdmin(AIKnowledgeGap, admin.site)
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertNotIn("status", model_admin.readonly_fields)
        self.assertIn("question_text", model_admin.readonly_fields)
        self.assertEqual(model_admin.search_fields, ("question_text",))

    def test_hash_helper_uses_only_reviewed_identity_fields(self):
        first = build_ai_knowledge_gap_hash(
            question=" A  QUESTION ",
            source="public",
            knowledge_scope="global",
            reason="documentation_gap",
        )
        second = build_ai_knowledge_gap_hash(
            question="a question",
            source="public",
            knowledge_scope="global",
            reason="documentation_gap",
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)


@override_settings(AI_PUBLIC_EXPERT_ENABLED=True)
class PublicKnowledgeGapEndpointTests(TestCase):
    def setUp(self):
        self.url = reverse("public_expert_ask")

    def post(self, message, scope="global"):
        return self.client.post(
            self.url,
            data=json.dumps({"message": message, "knowledge_scope": scope}),
            content_type="application/json",
        )

    def test_genuine_no_match_registers_once_and_returns_existing_fallback(self):
        question = "How does humidity affect corrugated compression strength?"
        with patch(
            "packagingapp.assistant.public_views.retrieve_public_knowledge_context",
            return_value=empty_public_knowledge_context(),
        ), patch(
            "packagingapp.assistant.public_views.ask_public_external",
            return_value={
                "schema_version": "1.0",
                "type": "answer",
                "message": PUBLIC_KNOWLEDGE_FALLBACK_MESSAGE,
            },
        ) as service:
            response = self.post(question)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["response"]["message"], PUBLIC_KNOWLEDGE_FALLBACK_MESSAGE)
        service.assert_called_once()
        gap = AIKnowledgeGap.objects.get()
        self.assertEqual(gap.question_text, question)
        self.assertEqual(gap.source, AIKnowledgeGap.Source.PUBLIC)
        self.assertEqual(gap.surface, AIKnowledgeGap.Surface.PUBLIC_SITE)
        self.assertEqual(gap.reason, AIKnowledgeGap.Reason.DOCUMENTATION_GAP)

    def test_public_boundaries_normal_answer_and_unavailable_create_no_gap(self):
        cases = (
            ("Why did the calculator give me 45?", "Boundary answer."),
            ("How many products fit?", "Boundary answer."),
            ("Change the box width.", "Boundary answer."),
            ("What is cubicity?", "Documented answer."),
            ("Provider failed.", "The Public Expert is temporarily unavailable."),
        )
        for question, message in cases:
            response_type = "unavailable" if question == "Provider failed." else "answer"
            with self.subTest(question=question), patch(
                "packagingapp.assistant.public_views.ask_public_external",
                return_value={
                    "schema_version": "1.0",
                    "type": response_type,
                    "message": message,
                },
            ):
                response = self.post(question, "container_selection")
                self.assertEqual(response.status_code, 200)
                self.assertFalse(AIKnowledgeGap.objects.exists())

    def test_persistence_failure_does_not_break_fallback_or_log_question(self):
        question = "Private-looking unanswered wording must not enter logs."
        with patch(
            "packagingapp.assistant.public_views.retrieve_public_knowledge_context",
            return_value=empty_public_knowledge_context(),
        ), patch(
            "packagingapp.assistant.public_views.ask_public_external",
            return_value={
                "schema_version": "1.0",
                "type": "answer",
                "message": PUBLIC_KNOWLEDGE_FALLBACK_MESSAGE,
            },
        ), patch(
            "packagingapp.assistant.knowledge_gaps._upsert_ai_knowledge_gap",
            side_effect=DatabaseError("database unavailable"),
        ), self.assertLogs(
            "packagingapp.assistant.knowledge_gaps", level="WARNING"
        ) as logs:
            response = self.post(question)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["response"]["message"], PUBLIC_KNOWLEDGE_FALLBACK_MESSAGE)
        self.assertNotIn(question, "\n".join(logs.output))


class AuthenticatedKnowledgeGapEndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="gap-user", password="test-password")
        UserSubscription.objects.create(user=self.user, plan=UserSubscription.Plan.PLUS)
        self.client.force_login(self.user)
        self.url = reverse("assistant_ask")

    def post(self, message, **extra):
        payload = {
            "tool": "container_selection",
            "surface": "standalone",
            "state": ready_state(),
            "message": message,
        }
        payload.update(extra)
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_validated_knowledge_gap_outcome_registers_and_returns_fixed_limitation(self):
        question = "How does humidity affect corrugated compression strength?"
        candidate = {
            "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
            "type": "knowledge_gap",
            "message": ASSISTANT_KNOWLEDGE_GAP_MESSAGE,
        }
        with patch(
            "packagingapp.assistant.views.ask_external", return_value=candidate
        ):
            response = self.post(question)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["response"]["type"], "answer")
        self.assertEqual(response.json()["response"]["message"], ASSISTANT_KNOWLEDGE_GAP_MESSAGE)
        gap = AIKnowledgeGap.objects.get()
        self.assertEqual(gap.question_text, question)
        self.assertEqual(gap.source, AIKnowledgeGap.Source.AUTHENTICATED)
        self.assertEqual(gap.knowledge_scope, "container_selection")

    def test_knowledge_no_match_with_tool_context_answer_creates_no_gap(self):
        with patch(
            "packagingapp.assistant.views.retrieve_knowledge_context",
            return_value=empty_knowledge_context(),
        ), patch(
            "packagingapp.assistant.views.ask_external",
            return_value={
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "answer",
                "message": "The current Tool Context provides the requested value.",
                "fact_refs": [],
            },
        ) as service:
            response = self.post("What is my maximum quantity?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.call_args.kwargs["knowledge_context"]["status"], "no_match")
        self.assertEqual(response.json()["response"]["type"], "answer")
        self.assertFalse(AIKnowledgeGap.objects.exists())

    def test_documented_answer_proposal_clarification_and_unavailable_create_no_gap(self):
        outcomes = (
            {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "answer",
                "message": "A documented answer.",
                "fact_refs": [],
            },
            {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "clarifying_question",
                "message": "Which documented concept do you mean?",
            },
            {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "unavailable",
                "message": ASSISTANT_UNAVAILABLE_MESSAGE,
            },
        )
        for outcome in outcomes:
            with self.subTest(response_type=outcome["type"]), patch(
                "packagingapp.assistant.views.ask_external", return_value=outcome
            ):
                response = self.post("Question")
                self.assertEqual(response.status_code, 200)
                self.assertFalse(AIKnowledgeGap.objects.exists())

        def proposal(**kwargs):
            return {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "propose_input_changes",
                "state_fingerprint": kwargs["tool_context"]["tool"]["state_fingerprint"],
                "changes": [
                    {
                        "field": "product.dimensions.length",
                        "value": 320,
                        "unit": "mm",
                    }
                ],
                "summary": "Set the requested product length.",
            }

        with patch("packagingapp.assistant.views.ask_external", side_effect=proposal):
            response = self.post("Set product length to 320 mm.")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["response"]["type"], "proposal_preview")
        self.assertFalse(AIKnowledgeGap.objects.exists())

    def test_persistence_failure_does_not_break_authenticated_limitation(self):
        question = "Unanswered authenticated question that must not be logged."
        with patch(
            "packagingapp.assistant.views.ask_external",
            return_value={
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": "knowledge_gap",
                "message": ASSISTANT_KNOWLEDGE_GAP_MESSAGE,
            },
        ), patch(
            "packagingapp.assistant.knowledge_gaps._upsert_ai_knowledge_gap",
            side_effect=DatabaseError("database unavailable"),
        ), self.assertLogs(
            "packagingapp.assistant.knowledge_gaps", level="WARNING"
        ) as logs:
            response = self.post(question)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["response"]["message"], ASSISTANT_KNOWLEDGE_GAP_MESSAGE)
        self.assertNotIn(question, "\n".join(logs.output))

