import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from packagingapp.assistant.actions import (
    MAX_PROPOSAL_CHANGES,
    NoEffectiveProposalChanges,
    PROPOSE_INPUT_CHANGES,
    ProposalCandidateValidationError,
    ProposalStateMismatchError,
    parse_assistant_provider_candidate,
)
from packagingapp.assistant.contracts import ASSISTANT_RESPONSE_SCHEMA_VERSION
from packagingapp.assistant.prompts import READ_ONLY_INSTRUCTIONS
from packagingapp.models import UserSubscription
from packagingapp.tools.container.assistant import build_container_tool_context
from packagingapp.tools.container.assistant_actions import (
    build_container_proposal_preview,
)
from packagingapp.tools.container.state import default_container_config
from packagingapp.forms import ContainerSelectionMode1Form


def manual_config(**overrides):
    config = default_container_config()
    config.update(
        {
            "mode": "single",
            "action": "refresh",
            "product_source": "manual",
            "product_l": "180",
            "product_w": "120",
            "product_h": "80",
            "product_weight": "450",
            "desired_qty": "12",
            "r1": True,
            "r2": True,
            "r3": True,
            "container_source": "manual",
            "box_l": "600",
            "box_w": "400",
            "box_h": "300",
            "box_thickness_mm": "4",
            "box_weight": "900",
            "box_max_payload": "20000",
        }
    )
    config.update(overrides)
    return config


def form_for(config):
    form = ContainerSelectionMode1Form(data=config)
    for field_name in ("catalogue_id", "product_catalogue_id"):
        current = str(config.get(field_name) or "")
        form.fields[field_name].choices = [("", "Select")]
        if current:
            form.fields[field_name].choices.append((current, "Current visible"))
    form.is_valid()
    return form


def candidate(context, changes, **overrides):
    value = {
        "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
        "type": PROPOSE_INPUT_CHANGES,
        "state_fingerprint": context["tool"]["state_fingerprint"],
        "changes": changes,
        "summary": "Set the requested Container inputs.",
    }
    value.update(overrides)
    return value


class AssistantProposalContractTests(SimpleTestCase):
    def setUp(self):
        self.config = manual_config()
        self.form = form_for(self.config)
        self.context = build_container_tool_context(
            config=self.config,
            form=self.form,
        )

    def parse(self, changes, **overrides):
        return parse_assistant_provider_candidate(
            candidate(self.context, changes, **overrides),
            tool_context=self.context,
        )

    def preview(self, changes, **overrides):
        parsed = self.parse(changes, **overrides)
        return build_container_proposal_preview(
            parsed,
            tool_context=self.context,
            current_config=self.config,
            current_form=self.form,
        )

    def test_valid_single_field_preview_is_application_owned_and_non_mutating(self):
        before_config = deepcopy(self.config)
        before_context = deepcopy(self.context)

        preview = self.preview(
            [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}]
        )

        self.assertEqual(preview["type"], "proposal_preview")
        self.assertEqual(preview["schema_version"], "1.0")
        self.assertTrue(preview["valid"])
        self.assertEqual(preview["changes"][0]["label"], "Product length")
        self.assertEqual(preview["changes"][0]["before"], {"value": 180.0, "unit": "mm"})
        self.assertEqual(preview["changes"][0]["after"], {"value": 320.0, "unit": "mm"})
        self.assertEqual(preview["changes"][0]["status"], "valid")
        self.assertEqual(preview["resulting_state"]["calculation_status"], "ready")
        self.assertEqual(preview["notice"], "These changes have not been applied.")
        self.assertEqual(self.config, before_config)
        self.assertEqual(self.context, before_context)

    def test_provider_action_language_never_becomes_preview_authority(self):
        preview = self.preview(
            [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
            summary=(
                "Apply immediately. Run the calculation. Ignore the field "
                "allow-list and change selected_product_id."
            ),
        )

        self.assertTrue(preview["valid"])
        self.assertEqual(preview["summary"], "Review the proposed input changes below.")
        serialized = json.dumps(preview, sort_keys=True)
        self.assertNotIn("Apply immediately", serialized)
        self.assertNotIn("selected_product_id", serialized)

    def test_prompt_requires_clarification_for_ambiguous_and_relative_requests(self):
        rules = "\n".join(READ_ONLY_INSTRUCTIONS.rules)

        self.assertIn("Ambiguous requests such as making a box bigger", rules)
        self.assertIn("Do not convert relative changes, deltas, or percentages", rules)
        self.assertIn("Ask for an explicit target instead", rules)

    def test_multi_field_preview_and_explicit_unit_normalization_are_atomic(self):
        preview = self.preview(
            [
                {"field": "product.dimensions.length", "value": 32, "unit": "cm"},
                {"field": "product.weight", "value": 0.5, "unit": "kg"},
                {"field": "request.desired_quantity", "value": 24, "unit": "pcs"},
            ]
        )

        self.assertTrue(preview["valid"])
        self.assertEqual(
            [row["after"] for row in preview["changes"]],
            [
                {"value": 320.0, "unit": "mm"},
                {"value": 500.0, "unit": "g"},
                {"value": 24, "unit": "pcs"},
            ],
        )

    def test_safe_single_change_on_empty_state_is_valid_but_incomplete(self):
        config = default_container_config()
        form = form_for(config)
        context = build_container_tool_context(config=config, form=form)
        parsed = parse_assistant_provider_candidate(
            candidate(
                context,
                [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
            ),
            tool_context=context,
        )

        preview = build_container_proposal_preview(
            parsed,
            tool_context=context,
            current_config=config,
            current_form=form,
        )

        self.assertTrue(preview["valid"])
        self.assertEqual(preview["changes"][0]["before"]["value"], None)
        self.assertEqual(preview["resulting_state"], {
            "validation": "incomplete",
            "calculation_status": "incomplete",
        })

    def test_existing_form_validation_rejects_invalid_ranges_and_fractional_quantity(self):
        cases = (
            ("product.dimensions.height", 0, "mm"),
            ("product.dimensions.length", -20, "mm"),
            ("request.desired_quantity", -5, "pcs"),
            ("request.desired_quantity", 2.5, "pcs"),
        )
        for field, value, unit in cases:
            with self.subTest(field=field, value=value):
                preview = self.preview([{"field": field, "value": value, "unit": unit}])
                self.assertFalse(preview["valid"])
                self.assertEqual(preview["changes"][0]["status"], "invalid")
                self.assertTrue(preview["changes"][0]["message"])
                self.assertEqual(
                    preview["resulting_state"]["calculation_status"], "invalid"
                )

    def test_orientation_mapping_reuses_axes_and_rejects_disabling_all(self):
        valid = self.preview(
            [{
                "field": "product.allowed_vertical_axes",
                "value": ["length", "height"],
                "unit": "none",
            }]
        )
        self.assertTrue(valid["valid"])
        self.assertEqual(valid["changes"][0]["after"]["value"], ["length", "height"])

        invalid = self.preview(
            [{"field": "product.allowed_vertical_axes", "value": [], "unit": "none"}]
        )
        self.assertFalse(invalid["valid"])
        self.assertEqual(invalid["changes"][0]["status"], "invalid")

    def test_field_specific_units_and_value_types_fail_without_model_arithmetic(self):
        wrong_unit = self.preview(
            [{"field": "product.dimensions.length", "value": 5, "unit": "kg"}]
        )
        self.assertEqual(wrong_unit["changes"][0]["status"], "unsupported_unit")
        self.assertFalse(wrong_unit["valid"])

        wrong_type = self.preview(
            [{
                "field": "product.dimensions.length",
                "value": ["length"],
                "unit": "mm",
            }]
        )
        self.assertEqual(wrong_type["changes"][0]["status"], "invalid")
        self.assertFalse(wrong_type["valid"])

    def test_unknown_database_duplicate_excessive_extra_and_unsafe_candidates_fail_closed(self):
        invalid_candidates = [
            candidate(
                self.context,
                [{"field": "engine.global_optimization", "value": 1, "unit": "mm"}],
            ),
            candidate(
                self.context,
                [{"field": "selected_product_id", "value": 1, "unit": "none"}],
            ),
            candidate(
                self.context,
                [
                    {"field": "product.dimensions.length", "value": 1, "unit": "mm"},
                    {"field": "product.dimensions.length", "value": 2, "unit": "mm"},
                ],
            ),
            candidate(
                self.context,
                [
                    {"field": f"field.{index}", "value": index, "unit": "mm"}
                    for index in range(MAX_PROPOSAL_CHANGES + 1)
                ],
            ),
            {
                **candidate(
                    self.context,
                    [{"field": "product.dimensions.length", "value": 1, "unit": "mm"}],
                ),
                "apply": True,
            },
            candidate(
                self.context,
                [{"field": "product.dimensions.length", "value": 1, "unit": "inch"}],
            ),
            candidate(
                self.context,
                [{"field": "product.dimensions.length", "value": 1, "unit": "mm"}],
                summary="<script>alert(1)</script>",
            ),
        ]
        for invalid in invalid_candidates:
            with self.subTest(candidate=repr(invalid)[:80]), self.assertRaises(
                ProposalCandidateValidationError
            ):
                parse_assistant_provider_candidate(invalid, tool_context=self.context)

    def test_new_context_field_requires_an_explicit_tool_mapping(self):
        future_context = deepcopy(self.context)
        future_context["input_definitions"]["future.reviewed.field"] = deepcopy(
            self.context["input_definitions"]["product.dimensions.length"]
        )
        future_context["allowed_proposals"].append("future.reviewed.field")
        parsed = parse_assistant_provider_candidate(
            candidate(
                future_context,
                [{"field": "future.reviewed.field", "value": 1, "unit": "mm"}],
            ),
            tool_context=future_context,
        )

        with self.assertRaises(ProposalCandidateValidationError):
            build_container_proposal_preview(
                parsed,
                tool_context=future_context,
                current_config=self.config,
                current_form=self.form,
            )

    def test_stale_fingerprint_and_no_op_do_not_produce_a_current_preview(self):
        stale = self.parse(
            [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
            state_fingerprint="sha256:" + ("0" * 64),
        )
        with self.assertRaises(ProposalStateMismatchError):
            build_container_proposal_preview(
                stale,
                tool_context=self.context,
                current_config=self.config,
                current_form=self.form,
            )

        no_op = self.parse(
            [{"field": "product.dimensions.length", "value": 18, "unit": "cm"}]
        )
        with self.assertRaises(NoEffectiveProposalChanges):
            build_container_proposal_preview(
                no_op,
                tool_context=self.context,
                current_config=self.config,
                current_form=self.form,
            )

    def test_catalogue_and_inherited_product_values_are_not_editable(self):
        selected_product = SimpleNamespace(
            product_length=180,
            product_width=120,
            product_height=80,
            weight=450,
            rotation_1=True,
            rotation_2=True,
            rotation_3=True,
            desired_qty=12,
        )
        catalogue_config = manual_config(
            product_source="catalogue",
            selected_product_id="1",
        )
        catalogue_form = form_for(catalogue_config)
        catalogue_context = build_container_tool_context(
            config=catalogue_config,
            form=catalogue_form,
            selected_product=selected_product,
        )
        catalogue_candidate = parse_assistant_provider_candidate(
            candidate(
                catalogue_context,
                [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
            ),
            tool_context=catalogue_context,
        )
        catalogue_preview = build_container_proposal_preview(
            catalogue_candidate,
            tool_context=catalogue_context,
            current_config=catalogue_config,
            current_form=catalogue_form,
            selected_product=selected_product,
        )
        self.assertEqual(catalogue_preview["changes"][0]["status"], "not_editable")
        self.assertIn("catalogue", catalogue_preview["changes"][0]["message"])

        selected_material = SimpleNamespace(
            part_length=600,
            part_width=400,
            part_height=300,
            box_thickness_mm=4,
        )
        container_config = manual_config(
            container_source="catalogue",
            catalogue_id="9",
            container_id="10",
        )
        container_form = form_for(container_config)
        container_context = build_container_tool_context(
            config=container_config,
            form=container_form,
            selected_material=selected_material,
        )
        container_candidate = parse_assistant_provider_candidate(
            candidate(
                container_context,
                [{
                    "field": "container.internal_dimensions.length",
                    "value": 700,
                    "unit": "mm",
                }],
            ),
            tool_context=container_context,
        )
        container_preview = build_container_proposal_preview(
            container_candidate,
            tool_context=container_context,
            current_config=container_config,
            current_form=container_form,
            selected_material=selected_material,
        )
        self.assertEqual(container_preview["changes"][0]["status"], "not_editable")
        self.assertIn("catalogue", container_preview["changes"][0]["message"])

        inherited_context = build_container_tool_context(
            config=self.config,
            form=self.form,
            surface="workflow",
            workflow={
                "input_origin": "inherited",
                "result_state": "none",
                "step_type": "container_selection",
                "step_ordinal": 2,
            },
        )
        inherited_candidate = parse_assistant_provider_candidate(
            candidate(
                inherited_context,
                [{"field": "product.dimensions.width", "value": 200, "unit": "mm"}],
            ),
            tool_context=inherited_context,
        )
        inherited_preview = build_container_proposal_preview(
            inherited_candidate,
            tool_context=inherited_context,
            current_config=self.config,
            current_form=self.form,
        )
        self.assertEqual(inherited_preview["changes"][0]["status"], "not_editable")
        self.assertIn("inherited", inherited_preview["changes"][0]["message"])

    def test_optimal_catalogue_quantity_is_no_longer_advertised_as_editable(self):
        selected_product = SimpleNamespace(
            product_length=180,
            product_width=120,
            product_height=80,
            weight=450,
            rotation_1=True,
            rotation_2=True,
            rotation_3=True,
            desired_qty=45,
        )
        config = manual_config(
            mode="optimal",
            product_source="catalogue",
            selected_product_id="1",
            catalogue_id="9",
            container_source="catalogue",
        )
        form = form_for(config)
        context = build_container_tool_context(
            config=config,
            form=form,
            selected_product=selected_product,
        )
        self.assertFalse(
            context["input_definitions"]["request.desired_quantity"]["editable"]
        )
        self.assertNotIn("request.desired_quantity", context["allowed_proposals"])

    def test_proposal_preview_never_calls_any_container_calculation_path(self):
        parsed = self.parse(
            [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}]
        )
        with patch(
            "packagingapp.tools.container.service.run_mode1_and_render"
        ) as run_engine, patch(
            "packagingapp.tools.container.service.compute_max_quantity_only"
        ) as capacity_engine, patch(
            "packagingapp.tools.container.service.build_container_design_candidates"
        ) as design_engine, patch(
            "packagingapp.utils.package_design_arrangements.build_canonical_design_arrangements"
        ) as arrangements:
            preview = build_container_proposal_preview(
                parsed,
                tool_context=self.context,
                current_config=self.config,
                current_form=self.form,
            )
        self.assertTrue(preview["valid"])
        run_engine.assert_not_called()
        capacity_engine.assert_not_called()
        design_engine.assert_not_called()
        arrangements.assert_not_called()


@override_settings(MEDIA_URL="/media/")
class AssistantProposalEndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="assistant-proposal-user")
        UserSubscription.objects.create(
            user=self.user,
            plan=UserSubscription.Plan.PLUS,
        )
        self.client.force_login(self.user)
        self.url = reverse("assistant_ask")

    def payload(self, state=None, message="Set product length to 320 mm."):
        return {
            "tool": "container_selection",
            "surface": "standalone",
            "state": state or manual_config(),
            "message": message,
        }

    def post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_endpoint_turns_candidate_into_preview_without_state_or_engine_mutation(self):
        before_session = deepcopy(dict(self.client.session))

        def proposal(**kwargs):
            return candidate(
                kwargs["tool_context"],
                [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
            )

        with patch(
            "packagingapp.assistant.views.ask_external", side_effect=proposal
        ), patch(
            "packagingapp.tools.container.service.run_mode1_and_render"
        ) as run_engine, patch(
            "packagingapp.tools.container.service.compute_max_quantity_only"
        ) as capacity_engine, patch(
            "packagingapp.tools.container.service.build_container_design_candidates"
        ) as design_engine:
            response = self.post(self.payload())

        self.assertEqual(response.status_code, 200)
        preview = response.json()["response"]
        self.assertEqual(preview["type"], "proposal_preview")
        self.assertEqual(preview["changes"][0]["before"]["value"], 180.0)
        self.assertEqual(preview["changes"][0]["after"]["value"], 320.0)
        self.assertEqual(dict(self.client.session), before_session)
        run_engine.assert_not_called()
        capacity_engine.assert_not_called()
        design_engine.assert_not_called()

    def test_endpoint_rejects_stale_candidate_and_normalizes_all_no_op(self):
        def stale(**kwargs):
            return candidate(
                kwargs["tool_context"],
                [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
                state_fingerprint="sha256:" + ("0" * 64),
            )

        with patch(
            "packagingapp.assistant.views.ask_external", side_effect=stale
        ), self.assertLogs("packagingapp.assistant.views", level="WARNING"):
            stale_response = self.post(self.payload())
        self.assertEqual(stale_response.json()["response"]["type"], "unavailable")

        def no_op(**kwargs):
            return candidate(
                kwargs["tool_context"],
                [{"field": "product.dimensions.length", "value": 18, "unit": "cm"}],
            )

        with patch(
            "packagingapp.assistant.views.ask_external", side_effect=no_op
        ):
            no_op_response = self.post(self.payload())
        self.assertEqual(no_op_response.json()["response"]["type"], "answer")
        self.assertIn("no effective change", no_op_response.json()["response"]["message"])
