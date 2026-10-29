import json
import math
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from packagingapp.assistant.contracts import (
    MAX_ALTERNATIVES,
    ToolContextValidationError,
    validate_tool_context,
)
from packagingapp.forms import ContainerSelectionMode1Form
from packagingapp.models import (
    PackagingCatalogue,
    PackagingMaterial,
    Product,
    ProductCatalogue,
)
from packagingapp.tools.container.assistant import (
    build_container_tool_context,
    build_container_tool_context_from_page_context,
    build_container_tool_context_from_workflow_step,
)
from packagingapp.tools.container.service import (
    analyze_container_form,
    get_selected_material,
    get_selected_product,
)
from packagingapp.tools.container.state import default_container_config
from packagingapp.utils.box_selection.box_selection_tool_arrays_2_origin_coordinates import (
    allowed_product_orientations,
)
from packagingapp.utils.box_selection.engine import Mode1Result, Placement


def manual_config(**overrides):
    config = default_container_config()
    config.update(
        {
            "mode": "single",
            "action": "",
            "product_source": "manual",
            "product_l": "10",
            "product_w": "12",
            "product_h": "8",
            "product_weight": "100",
            "desired_qty": "4",
            "product_shape": "cuboid",
            "r1": True,
            "r2": True,
            "r3": True,
            "container_source": "manual",
            "box_l": "20",
            "box_w": "24",
            "box_h": "16",
            "box_thickness_mm": "",
            "box_weight": "50",
            "box_max_payload": "1000",
        }
    )
    config.update(overrides)
    return config


def form_for(config):
    form = ContainerSelectionMode1Form(data=config)
    for field_name in ("catalogue_id", "product_catalogue_id"):
        value = str(config.get(field_name) or "")
        form.fields[field_name].choices = [("", "Select")]
        if value:
            form.fields[field_name].choices.append((value, "Visible"))
    form.is_valid()
    return form


def selection_report(**overrides):
    report = {
        "requested_qty": 4,
        "max_quantity": 8,
        "remaining_capacity": 4,
        "volumetric_efficiency_current_pct": 50,
        "internal_length": 20.0,
        "internal_width": 24.0,
        "internal_height": 16.0,
        "external_length": 28.0,
        "external_width": 32.0,
        "external_height": 32.0,
        "box_thickness_mm": 4.0,
        "box_thickness_assumed": True,
        "external_dimension_source": "default_thickness",
        "product_weight": 100.0,
        "container_tare": 50.0,
        "payload_capacity": 1000.0,
        "net_weight": 400.0,
        "total_weight_current": 450.0,
        "payload_usage_pct": 40,
    }
    report.update(overrides)
    return report


def selection_analysis(**overrides):
    analysis = {
        "ok": True,
        "messages": [],
        "result": Mode1Result(
            max_quantity=8,
            image_rel_path="private/results/result.png",
            threejs_scene={"scene": "must-not-leak"},
            placements=(Placement((0, 0, 0), (10, 12, 8), 0, "main"),),
        ),
        "analysis_report": selection_report(),
        "top5": [],
        "design_candidates": [],
        "selected_design_candidate_id": "",
    }
    analysis.update(overrides)
    return analysis


class ContainerAssistantStateTests(SimpleTestCase):
    def test_empty_state_distinguishes_defaults_from_result(self):
        context = build_container_tool_context(config=default_container_config())

        self.assertEqual(context["tool"]["calculation_status"], "empty")
        self.assertIsNone(context["result"])
        self.assertEqual(context["validation"]["status"], "incomplete")
        self.assertIsNone(
            context["inputs"]["product"]["dimensions"]["length"]["value"]
        )

    def test_partial_state_preserves_entered_values(self):
        config = default_container_config()
        config["product_l"] = "10"
        context = build_container_tool_context(config=config)

        self.assertEqual(context["tool"]["calculation_status"], "partial")
        self.assertEqual(
            context["inputs"]["product"]["dimensions"]["length"]["value"],
            10.0,
        )
        self.assertIsNone(context["result"])

    def test_invalid_state_uses_django_form_errors(self):
        config = manual_config(product_l="-1")
        context = build_container_tool_context(config=config, form=form_for(config))

        self.assertEqual(context["tool"]["calculation_status"], "invalid")
        self.assertEqual(context["validation"]["status"], "invalid")
        self.assertTrue(
            any(
                error["field"] == "product.dimensions.length"
                for error in context["validation"]["errors"]
            )
        )

    def test_attempted_incomplete_calculation_is_invalid(self):
        config = default_container_config()
        config["action"] = "run_single"
        context = build_container_tool_context(config=config)

        self.assertEqual(context["tool"]["calculation_status"], "invalid")
        self.assertTrue(context["validation"]["errors"])

    def test_ready_state_has_valid_inputs_without_result(self):
        config = manual_config()
        context = build_container_tool_context(config=config, form=form_for(config))

        self.assertEqual(context["tool"]["calculation_status"], "ready")
        self.assertEqual(context["validation"]["status"], "valid")
        self.assertIsNone(context["result"])

    def test_complete_single_context_matches_service_result(self):
        config = manual_config(
            action="run_single",
            product_l="10",
            product_w="10",
            product_h="10",
            box_l="20",
            box_w="20",
            box_h="20",
        )
        form = form_for(config)
        self.assertTrue(form.is_valid(), form.errors)
        with tempfile.TemporaryDirectory() as media_root:
            analysis = analyze_container_form(form, config, media_root=media_root)

        context = build_container_tool_context(
            config=config,
            form=form,
            analysis=analysis,
        )

        self.assertEqual(context["tool"]["calculation_status"], "complete")
        self.assertEqual(
            context["result"]["max_quantity"]["value"],
            analysis["result"].max_quantity,
        )
        self.assertEqual(context["result"]["max_quantity"]["value"], 8)
        self.assertEqual(context["result"]["thickness"]["status"], "assumed")
        self.assertIn(
            "external_dimensions_default_thickness",
            {item["code"] for item in context["assumptions"]},
        )

    def test_stale_result_is_suppressed_after_relevant_input_change(self):
        config_a = manual_config()
        context_a = build_container_tool_context(
            config=config_a,
            form=form_for(config_a),
            analysis=selection_analysis(),
        )
        config_b = manual_config(product_l="11")
        context_b = build_container_tool_context(
            config=config_b,
            form=form_for(config_b),
            analysis=selection_analysis(),
            result_state_fingerprint=context_a["tool"]["state_fingerprint"],
        )

        self.assertEqual(context_b["tool"]["calculation_status"], "stale")
        self.assertIsNone(context_b["result"])
        self.assertEqual(context_b["alternatives"], [])
        self.assertIn(
            "previous_result_is_stale",
            {warning["code"] for warning in context_b["warnings"]},
        )

    def test_manual_inputs_units_sources_definitions_and_proposals(self):
        config = manual_config()
        context = build_container_tool_context(config=config, form=form_for(config))

        self.assertEqual(context["inputs"]["product"]["source"], "manual")
        self.assertEqual(
            context["inputs"]["container"]["internal_dimensions"]["width"],
            {"value": 24.0, "unit": "mm", "status": "valid"},
        )
        self.assertEqual(
            context["inputs"]["product"]["weight"],
            {"value": 100.0, "unit": "g", "status": "valid"},
        )
        self.assertEqual(
            context["input_definitions"]["product.dimensions.length"]["minimum_exclusive"],
            0.0,
        )
        self.assertIn("product.dimensions.length", context["allowed_proposals"])

    def test_orientation_semantics_follow_authoritative_mapping(self):
        config = manual_config(r1=True, r2=False, r3=True)
        context = build_container_tool_context(config=config, form=form_for(config))
        expected_vertical_symbols = {
            row["label"].split("×")[-1].strip()
            for row in allowed_product_orientations((10, 12, 8), 1, 0, 1)
        }
        expected_axes = [
            axis
            for symbol, axis in (("L", "length"), ("W", "width"), ("H", "height"))
            if symbol in expected_vertical_symbols
        ]

        self.assertEqual(
            context["inputs"]["product"]["allowed_vertical_axes"],
            expected_axes,
        )

    def test_single_result_exposes_only_informational_payload_semantics(self):
        config = manual_config(action="run_single")
        context = build_container_tool_context(
            config=config,
            form=form_for(config),
            analysis=selection_analysis(),
        )

        self.assertEqual(context["result"]["payload_usage"]["status"], "informational")
        serialized = json.dumps(context)
        self.assertNotIn("payload_limited", serialized)
        self.assertIn("payload_not_capacity_constraint", serialized)

    def test_optimal_alternatives_keep_order_and_are_capped(self):
        config = manual_config(
            mode="optimal",
            action="find_top5",
            container_source="catalogue",
            catalogue_id="visible-catalogue",
            box_l="",
            box_w="",
            box_h="",
        )
        rows = [
            {
                "material": SimpleNamespace(
                    id=index,
                    owner_id="private-owner",
                    part_number=f"SECRET-{index}",
                ),
                "max_qty": 20 - index,
                "usage": 0.9 - (index / 100),
                "container_vol": 1000 + index,
            }
            for index in range(1, 8)
        ]
        context = build_container_tool_context(
            config=config,
            form=form_for(config),
            analysis={"ok": True, "messages": [], "result": None, "top5": rows},
            selected_material=SimpleNamespace(id=rows[2]["material"].id),
        )

        self.assertEqual(context["tool"]["calculation_status"], "complete")
        self.assertEqual(len(context["alternatives"]), MAX_ALTERNATIVES)
        self.assertEqual(
            [row["geometric_capacity"]["value"] for row in context["alternatives"]],
            [19, 18, 17, 16, 15],
        )
        self.assertEqual(context["alternatives"][0]["label"], "Candidate 1")
        self.assertTrue(context["alternatives"][2]["selected"])
        serialized = json.dumps(context)
        self.assertNotIn("SECRET-", serialized)
        self.assertNotIn("private-owner", serialized)

    def test_optimal_fingerprint_tracks_candidate_engineering_state(self):
        config = manual_config(
            mode="optimal",
            container_source="catalogue",
            catalogue_id="visible-catalogue",
            box_l="",
            box_w="",
            box_h="",
        )
        material_a = SimpleNamespace(
            part_length=20,
            part_width=24,
            part_height=16,
            external_length=None,
            external_width=None,
            external_height=None,
            box_thickness_mm=None,
            part_volume=7680,
            part_weight=999,
            owner_id="excluded",
        )
        material_b = SimpleNamespace(**vars(material_a))
        material_b.part_length = 21
        material_c = SimpleNamespace(**vars(material_a))
        material_c.part_weight = 123456
        material_c.owner_id = "different-excluded-owner"
        first = build_container_tool_context(
            config=config,
            form=form_for(config),
            available_materials=[material_a],
        )
        second = build_container_tool_context(
            config=config,
            form=form_for(config),
            available_materials=[material_b],
        )
        third = build_container_tool_context(
            config=config,
            form=form_for(config),
            available_materials=[material_c],
        )

        self.assertNotEqual(
            first["tool"]["state_fingerprint"], second["tool"]["state_fingerprint"]
        )
        self.assertEqual(
            first["inputs"]["container"]["catalogue_scope"]["candidate_count"], 1
        )
        self.assertEqual(
            first["tool"]["state_fingerprint"], third["tool"]["state_fingerprint"]
        )
        serialized = json.dumps(first)
        self.assertNotIn("excluded", serialized)

    def test_design_context_preserves_candidate_contract_without_render_payload(self):
        config = manual_config(
            mode="design",
            action="run_design",
            desired_qty="5",
            box_l="",
            box_w="",
            box_h="",
        )
        form = form_for(config)
        self.assertTrue(form.is_valid(), form.errors)
        analysis = analyze_container_form(form, config)
        context = build_container_tool_context(
            config=config,
            form=form,
            analysis=analysis,
        )

        self.assertEqual(context["tool"]["calculation_status"], "complete")
        self.assertEqual(context["result"]["kind"], "design")
        self.assertEqual(
            context["result"]["candidate_id"],
            analysis["result"]["candidate_id"],
        )
        for field in (
            "rank",
            "desired_quantity",
            "design_quantity",
            "additional_capacity",
            "arrangement",
            "orientation",
            "rows",
            "columns",
            "layers",
            "internal_dimensions",
            "external_dimensions",
            "cubicity",
            "volume",
        ):
            self.assertIn(field, context["result"])
        serialized = json.dumps(context)
        self.assertNotIn("render_data", serialized)
        self.assertNotIn("products", serialized)

    def test_fingerprint_is_stable_across_surface_identity_and_ui_action(self):
        config = manual_config(action="refresh")
        first = build_container_tool_context(
            config=config,
            form=form_for(config),
            surface="standalone",
        )
        changed_ui = manual_config(action="select_product")
        changed_ui["username"] = "identity-must-not-matter"
        changed_ui["session_key"] = "session-must-not-matter"
        second = build_container_tool_context(
            config=changed_ui,
            form=form_for(changed_ui),
            surface="public",
        )
        changed_engineering = manual_config(product_h="9")
        third = build_container_tool_context(
            config=changed_engineering,
            form=form_for(changed_engineering),
        )

        self.assertEqual(
            first["tool"]["state_fingerprint"], second["tool"]["state_fingerprint"]
        )
        self.assertNotEqual(
            first["tool"]["state_fingerprint"], third["tool"]["state_fingerprint"]
        )
        self.assertEqual(second["tool"]["surface"], "public")

    def test_page_context_adapter_does_not_use_export_session_payloads(self):
        config = manual_config(action="run_single")
        form = form_for(config)
        page_context = {
            "container_form": form,
            "container_config": config,
            "result": selection_analysis()["result"],
            "analysis_report": selection_report(),
            "top5": [],
            "design_candidates": [],
            "selected_design_candidate_id": "",
            "selected_product": None,
            "selected_material": None,
            "container_selection_last_export": {"secret": "must-not-be-read"},
        }
        context = build_container_tool_context_from_page_context(
            page_context, surface="seo"
        )

        self.assertEqual(context["tool"]["surface"], "public")
        self.assertEqual(context["tool"]["calculation_status"], "complete")
        self.assertNotIn("must-not-be-read", json.dumps(context))


class ContainerAssistantWorkflowTests(SimpleTestCase):
    def _step(self, *, pending=True, selected=False):
        config = manual_config(action="run_single")
        payload = {
            "internal_length": 20.0,
            "internal_width": 24.0,
            "internal_height": 16.0,
            "external_length": 28.0,
            "external_width": 32.0,
            "external_height": 32.0,
            "units_per_parent": 8,
            "total_base_units": 8,
            "label": "Sensitive workflow label",
            "source_step_type": "container",
        }
        return {
            "type": "container",
            "config": config,
            "result": {
                "kind": "container",
                "max_quantity": 8,
                "analysis_report": selection_report(),
                "threejs_scene": {"must": "not leak"},
            },
            "analysis_report": selection_report(),
            "top5": [],
            "design_candidates": [],
            "selected_design_candidate_id": "",
            "pending_result": payload if pending else None,
            "selected": payload if selected else None,
            "messages": [],
            "unrelated_steps": [{"secret": "not-current-step"}],
        }

    def test_standalone_and_workflow_semantics_match(self):
        step = self._step(pending=True)
        standalone = build_container_tool_context(
            config=step["config"],
            form=form_for(step["config"]),
            analysis=selection_analysis(),
        )
        workflow = build_container_tool_context_from_workflow_step(
            step,
            form=form_for(step["config"]),
            step_ordinal=2,
        )

        for section in ("inputs", "result", "assumptions", "restrictions"):
            self.assertEqual(standalone[section], workflow[section])
        standalone_facts = standalone["explanation_facts"]
        workflow_common_facts = [
            fact
            for fact in workflow["explanation_facts"]
            if fact["code"] != "result_state_is_pending"
        ]
        self.assertEqual(standalone_facts, workflow_common_facts)
        self.assertEqual(workflow["workflow"]["input_origin"], "inherited")
        self.assertEqual(workflow["workflow"]["result_state"], "pending")
        self.assertNotIn("not-current-step", json.dumps(workflow))

    def test_pending_and_selected_workflow_results_remain_distinct(self):
        pending = build_container_tool_context_from_workflow_step(
            self._step(pending=True, selected=False),
            step_ordinal=2,
        )
        selected = build_container_tool_context_from_workflow_step(
            self._step(pending=True, selected=True),
            step_ordinal=2,
        )

        self.assertEqual(pending["workflow"]["result_state"], "pending")
        self.assertEqual(selected["workflow"]["result_state"], "selected")

    def test_inherited_effective_product_fields_are_not_editable(self):
        context = build_container_tool_context_from_workflow_step(
            self._step(), step_ordinal=2
        )

        self.assertFalse(
            context["input_definitions"]["product.dimensions.length"]["editable"]
        )
        self.assertNotIn("product.dimensions.length", context["allowed_proposals"])


class ToolContextContractTests(SimpleTestCase):
    def setUp(self):
        self.context = build_container_tool_context(config=default_container_config())

    def assert_rejected(self, value):
        context = deepcopy(self.context)
        context["inputs"]["unsafe"] = value
        with self.assertRaises(ToolContextValidationError):
            validate_tool_context(context)

    def test_context_is_strict_json_safe(self):
        json.dumps(self.context, allow_nan=False)

    def test_decimal_path_numpy_dataclass_and_arbitrary_objects_fail(self):
        @dataclass
        class UnsafeDataclass:
            value: int

        for value in (
            Decimal("1.2"),
            Path("private/file.txt"),
            np.float64(1.2),
            np.array([1, 2]),
            UnsafeDataclass(1),
            SimpleNamespace(value=1),
        ):
            with self.subTest(value=type(value).__name__):
                self.assert_rejected(value)

    def test_non_finite_numbers_fail(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                self.assert_rejected(value)

    def test_forbidden_keys_fail(self):
        for key in ("user_id", "session_key", "threejs_scene", "placements", "image_url"):
            context = deepcopy(self.context)
            context["inputs"][key] = "sensitive"
            with self.subTest(key=key), self.assertRaises(ToolContextValidationError):
                validate_tool_context(context)

    def test_size_limits_fail_loudly(self):
        context = deepcopy(self.context)
        context["warnings"] = [
            {"code": "oversized", "message": "x" * 513}
        ]
        with self.assertRaises(ToolContextValidationError):
            validate_tool_context(context)

    def test_result_and_workflow_sections_follow_status_and_surface(self):
        context = deepcopy(self.context)
        context["result"] = {"kind": "fabricated"}
        with self.assertRaises(ToolContextValidationError):
            validate_tool_context(context)

        context = deepcopy(self.context)
        context["tool"]["calculation_status"] = "complete"
        with self.assertRaises(ToolContextValidationError):
            validate_tool_context(context)

        context = deepcopy(self.context)
        context["tool"]["surface"] = "workflow"
        with self.assertRaises(ToolContextValidationError):
            validate_tool_context(context)

        context = deepcopy(self.context)
        context["alternatives"] = [
            {"rank": rank} for rank in range(MAX_ALTERNATIVES + 1)
        ]
        with self.assertRaises(ToolContextValidationError):
            validate_tool_context(context)


class ContainerAssistantCataloguePrivacyTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="private-user",
            email="private@example.com",
            password="not-a-real-secret",
        )
        self.public_products = ProductCatalogue.objects.create(
            name="Public product catalogue", is_public=True
        )
        self.private_products = ProductCatalogue.objects.create(
            name="Secret product catalogue", owner=self.owner, is_public=False
        )
        self.public_product = Product.objects.create(
            catalogue=self.public_products,
            product_id="PUBLIC-PRODUCT",
            product_name="Public product",
            product_length=10,
            product_width=12,
            product_height=8,
            weight=Decimal("0.100"),
            desired_qty=4,
            rotation_1=True,
            rotation_2=False,
            rotation_3=True,
        )
        self.private_product = Product.objects.create(
            catalogue=self.private_products,
            product_id="SECRET-PRODUCT",
            product_name="Secret product",
            product_length=99,
            product_width=98,
            product_height=97,
        )
        self.public_packaging = PackagingCatalogue.objects.create(
            name="Public packaging catalogue", is_public=True
        )
        self.private_packaging = PackagingCatalogue.objects.create(
            name="Secret packaging catalogue", owner=self.owner, is_public=False
        )
        self.public_material = PackagingMaterial.objects.create(
            catalogue=self.public_packaging,
            part_number="PUBLIC-BOX",
            part_description="Public box",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Board",
            part_length=20,
            part_width=24,
            part_height=16,
            part_weight=Decimal("0.050"),
        )
        self.private_material = PackagingMaterial.objects.create(
            catalogue=self.private_packaging,
            part_number="SECRET-BOX",
            part_description="Secret box",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Secret board",
            part_length=200,
            part_width=240,
            part_height=160,
        )

    def test_public_resolution_cannot_rehydrate_private_records(self):
        private_config = {
            "selected_product_id": str(self.private_product.pk),
            "container_id": str(self.private_material.pk),
        }
        self.assertIsNone(get_selected_product(private_config, user=None))
        self.assertIsNone(get_selected_material(private_config, user=None))

        public_config = {
            "selected_product_id": str(self.public_product.pk),
            "container_id": str(self.public_material.pk),
        }
        self.assertEqual(
            get_selected_product(public_config, user=None), self.public_product
        )
        self.assertEqual(
            get_selected_material(public_config, user=None), self.public_material
        )

    def test_catalogue_values_are_authoritative_and_sensitive_metadata_is_absent(self):
        config = manual_config(
            action="run_single",
            product_source="catalogue",
            product_catalogue_id=str(self.public_products.pk),
            selected_product_id=str(self.public_product.pk),
            product_l="999",
            product_w="999",
            product_h="999",
            product_weight="999",
            r1=False,
            r2=True,
            r3=False,
            container_source="catalogue",
            catalogue_id=str(self.public_packaging.pk),
            container_id=str(self.public_material.pk),
            box_l="999",
            box_w="999",
            box_h="999",
            box_weight="999",
        )
        form = form_for(config)
        context = build_container_tool_context(
            config=config,
            form=form,
            analysis=selection_analysis(
                analysis_report=selection_report(container_tare=50.0)
            ),
            selected_product=self.public_product,
            selected_material=self.public_material,
            surface="public",
        )

        self.assertEqual(
            context["inputs"]["product"]["dimensions"]["length"]["value"],
            10.0,
        )
        self.assertEqual(
            context["inputs"]["container"]["internal_dimensions"]["length"]["value"],
            20.0,
        )
        self.assertEqual(
            context["inputs"]["product"]["allowed_vertical_axes"],
            ["length", "height"],
        )
        self.assertNotIn("tare_weight", context["inputs"]["container"])
        self.assertNotIn("container.tare_weight", context["input_definitions"])
        self.assertEqual(
            context["inputs"]["product"]["weight"],
            {"value": 100.0, "unit": "g", "status": "valid"},
        )
        self.assertEqual(
            context["result"]["container_tare"],
            {"value": 50.0, "unit": "g", "status": "informational"},
        )
        self.assertNotIn(
            "catalogue_container_weight_unit_ambiguous",
            {warning["code"] for warning in context["warnings"]},
        )
        serialized = json.dumps(context, sort_keys=True)
        for sensitive in (
            self.owner.username,
            self.owner.email,
            "PUBLIC-PRODUCT",
            "Public product",
            "PUBLIC-BOX",
            "Public box",
            "Secret board",
            "private/results/result.png",
            "must-not-leak",
        ):
            self.assertNotIn(sensitive, serialized)
        for forbidden_key in (
            '"owner_id"',
            '"user_id"',
            '"catalogue_id"',
            '"material_id"',
            '"selected_product_id"',
        ):
            self.assertNotIn(forbidden_key, serialized)

    def test_model_and_queryset_are_rejected_by_shared_validator(self):
        context = build_container_tool_context(config=default_container_config())
        for unsafe in (
            self.public_product,
            Product.objects.filter(pk=self.public_product.pk),
        ):
            candidate = deepcopy(context)
            candidate["inputs"]["unsafe"] = unsafe
            with self.subTest(value=type(unsafe).__name__), self.assertRaises(
                ToolContextValidationError
            ):
                validate_tool_context(candidate)
