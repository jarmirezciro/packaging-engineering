import tempfile

from django.test import SimpleTestCase

from packagingapp.assistant.evaluation import (
    build_container_evaluation_cases,
    build_input_action_evaluation_cases,
    build_knowledge_evaluation_cases,
    build_proposal_evaluation_cases,
)


class AssistantEvaluationFixtureTests(SimpleTestCase):
    def test_first_evaluation_set_has_expected_states_and_authoritative_result(self):
        with tempfile.TemporaryDirectory() as media_root:
            cases = build_container_evaluation_cases(media_root=media_root)

        self.assertEqual(
            [case.name for case in cases],
            [
                "empty",
                "partial",
                "invalid",
                "ready",
                "complete_single",
                "capacity",
                "utilization",
                "assumption",
                "payload",
                "stale",
                "unsupported",
            ],
        )
        by_name = {case.name: case for case in cases}
        for name in ("complete_single", "capacity", "utilization", "assumption", "payload", "unsupported"):
            self.assertEqual(
                by_name[name].tool_context["tool"]["calculation_status"],
                "complete",
            )
            self.assertIsNotNone(by_name[name].tool_context["result"])
        self.assertEqual(
            by_name["stale"].tool_context["tool"]["calculation_status"],
            "stale",
        )
        self.assertIsNone(by_name["stale"].tool_context["result"])

    def test_knowledge_evaluation_set_covers_requested_questions_and_states(self):
        with tempfile.TemporaryDirectory() as media_root:
            cases = build_knowledge_evaluation_cases(media_root=media_root)

        self.assertEqual(len(cases), 40)
        by_name = {case.name: case for case in cases}
        self.assertEqual(
            by_name["design_mode"].tool_context["tool"]["mode"],
            "design",
        )
        self.assertIn(
            by_name["design_mode"].tool_context["tool"]["calculation_status"],
            {"ready", "partial", "empty"},
        )
        self.assertIsNone(by_name["design_mode"].tool_context["result"])
        self.assertEqual(
            by_name["current_result_regression"].tool_context["tool"][
                "calculation_status"
            ],
            "complete",
        )
        self.assertEqual(
            {case.category for case in cases},
            {
                "bag_selection",
                "container_selection",
                "cross_tool",
                "current_result",
                "expected_state_boundary",
                "packaging_flow",
                "palletization",
                "transport_container",
                "unsupported",
            },
        )

    def test_proposal_evaluation_set_is_the_bounded_session_9_suite(self):
        cases = build_proposal_evaluation_cases()

        self.assertEqual(
            [case.name for case in cases],
            [
                "proposal_product_length",
                "proposal_quantity_and_height",
                "proposal_unit_normalization",
                "proposal_ambiguous",
                "proposal_read_only_regression",
            ],
        )
        self.assertTrue(all(case.proposal_config is not None for case in cases))
        self.assertTrue(
            all(case.tool_context["tool"]["calculation_status"] == "ready" for case in cases)
        )

    def test_input_action_evaluation_set_covers_session_10_5_boundaries(self):
        with tempfile.TemporaryDirectory() as media_root:
            cases = build_input_action_evaluation_cases(media_root=media_root)

        self.assertEqual(len(cases), 20)
        by_name = {case.name: case for case in cases}
        self.assertEqual(
            by_name["action_current_maximum"].tool_context["tool"]["calculation_status"],
            "complete",
        )
        self.assertIsNotNone(by_name["action_current_maximum"].tool_context["result"])
        self.assertFalse(
            by_name["action_catalogue_product"].tool_context["input_definitions"]
            ["product.dimensions.length"]["editable"]
        )
        self.assertFalse(
            by_name["action_catalogue_container"].tool_context["input_definitions"]
            ["container.internal_dimensions.width"]["editable"]
        )
        self.assertEqual(
            by_name["action_inherited_product"].tool_context["workflow"]["input_origin"],
            "inherited",
        )
        self.assertEqual(
            {case.category for case in cases},
            {
                "clarification",
                "current_result",
                "design",
                "explanation",
                "invalid_value",
                "multi_field",
                "prompt_injection",
                "relative_request",
                "rotations",
                "simple",
                "source_authority",
                "unit_conversion",
                "unsupported_action",
                "unsupported_unit",
            },
        )
