import json
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from packagingapp.tools.full_packaging.export import _step_metrics
from packagingapp.tools.palletization.export import _analysis_rows, build_palletization_pdf
from packagingapp.tools.palletization.presenter import build_pallet_ui_contract
from packagingapp.tools.palletization.service import (
    analyze_palletization_capacity,
    analyze_palletization_config,
)
from packagingapp.tools.palletization.state import default_palletization_config
from packagingapp.units import convert_mass
from packagingapp.utils.palletization.engine import (
    max_cartons_for_pallet_load,
    run_palletization_analysis,
    selected_result_for_render,
)
from packagingapp.views.full_packaging import _read_prefixed_pallet_post


class PalletMaximumLoadEngineTests(SimpleTestCase):
    def _engine(self, **updates):
        inputs = {
            "box_l": 400,
            "box_w": 400,
            "box_h": 200,
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 150,
            "max_stack_height": 1150,
            "box_weight": 1000,
        }
        inputs.update(updates)
        return run_palletization_analysis(**inputs)

    @staticmethod
    def _placement_signature(rows):
        return [
            (
                row["pattern"],
                row["stacking"],
                row["total_boxes"],
                row["layers"],
                [
                    (
                        placement.x,
                        placement.y,
                        placement.z,
                        placement.l,
                        placement.w,
                        placement.h,
                        placement.layer_index,
                    )
                    for placement in row["placements3d"]
                ],
            )
            for row in rows
        ]

    def test_blank_maximum_load_preserves_baseline_geometry(self):
        baseline = self._engine()
        explicit_blank = self._engine(max_pallet_load=None)

        self.assertEqual(
            self._placement_signature(explicit_blank),
            self._placement_signature(baseline),
        )
        self.assertEqual(baseline[0]["total_boxes"], 30)
        self.assertEqual(baseline[0]["layers"], 5)
        self.assertIsNone(baseline[0]["load_utilization_pct"])
        self.assertEqual(baseline[0]["limiting_constraint"], "Geometry")

    def test_weight_limit_caps_authoritative_geometry_with_partial_final_layer(self):
        rows = self._engine(max_pallet_load=22000)
        selected = rows[0]

        self.assertEqual(selected["total_boxes"], 22)
        self.assertEqual(len(selected["placements3d"]), 22)
        self.assertEqual([len(layer) for layer in selected["layers_2d"]], [6, 6, 6, 4])
        self.assertEqual(selected["layers"], 4)
        self.assertEqual(selected["actual_pallet_load_g"], 22000)
        self.assertEqual(selected["load_utilization_pct"], 100)
        self.assertEqual(selected["limiting_constraint"], "Weight")
        self.assertLessEqual(
            selected["actual_pallet_load_g"],
            selected["max_pallet_load_g"],
        )

    def test_geometry_limit_and_exact_combined_boundary_are_reported(self):
        geometry_limited = self._engine(max_pallet_load=100000)[0]
        exact_both = self._engine(max_pallet_load=30000)[0]

        self.assertEqual(geometry_limited["total_boxes"], 30)
        self.assertEqual(geometry_limited["limiting_constraint"], "Geometry")
        self.assertEqual(geometry_limited["load_utilization_pct"], 30)
        self.assertEqual(exact_both["total_boxes"], 30)
        self.assertEqual(exact_both["limiting_constraint"], "Both")
        self.assertEqual(exact_both["load_utilization_pct"], 100)

    def test_decimal_floor_does_not_add_a_carton_at_float_boundary(self):
        self.assertEqual(max_cartons_for_pallet_load(0.3, 0.1), 3)
        self.assertEqual(max_cartons_for_pallet_load(0.299999999999, 0.1), 2)

    def test_single_carton_over_limit_returns_no_engine_solution(self):
        self.assertEqual(self._engine(max_pallet_load=999), [])

    def test_alternate_layer_preview_keeps_the_same_weight_cap(self):
        selected = next(
            row
            for row in self._engine(box_w=300, max_pallet_load=22000)
            if row.get("interlock_possible") and row.get("interlock_possible_layer")
        )
        preview = selected_result_for_render(
            selected,
            available_carton_height=1000,
            render_interlock=True,
        )

        self.assertEqual(len(preview["placements3d"]), selected["total_boxes"])
        self.assertEqual(len(preview["placements3d"]), 22)


class PalletMaximumLoadServiceTests(SimpleTestCase):
    def _config(self, **updates):
        config = default_palletization_config()
        config.update({
            "box_l": 400,
            "box_w": 400,
            "box_h": 200,
            "box_weight": 1,
            "mass_unit": "kg",
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 150,
            "max_stack_height": 1150,
        })
        config.update(updates)
        return config

    def test_missing_invalid_and_non_positive_inputs_are_rejected(self):
        cases = (
            ({"max_pallet_load": 22, "box_weight": ""}, "Carton gross weight"),
            ({"max_pallet_load": 22, "box_weight": 0}, "Carton gross weight"),
            ({"max_pallet_load": 0}, "Max pallet load must be greater than 0"),
            ({"max_pallet_load": -1}, "Max pallet load must be greater than 0"),
            ({"max_pallet_load": "not-a-number"}, "Max Pallet Load must be a finite number"),
            ({"max_pallet_load": "nan"}, "Max Pallet Load must be a finite number"),
        )
        for updates, expected in cases:
            with self.subTest(updates=updates):
                result = analyze_palletization_capacity(self._config(**updates))
                self.assertFalse(result["ok"])
                self.assertTrue(
                    any(expected in message for message in result["messages"]),
                    result["messages"],
                )

    def test_single_carton_over_limit_has_meaningful_validation(self):
        result = analyze_palletization_capacity(
            self._config(max_pallet_load=0.5)
        )

        self.assertFalse(result["ok"])
        self.assertIn(
            "Max Pallet Load is lower than one carton gross weight; no carton can be placed.",
            result["messages"],
        )

    def test_metric_and_imperial_inputs_produce_the_same_capped_placement(self):
        metric = analyze_palletization_config(self._config(max_pallet_load=22))
        imperial = analyze_palletization_config(self._config(
            mass_unit="lb",
            box_weight=convert_mass(1, "kg", "lb"),
            max_pallet_load=convert_mass(22, "kg", "lb"),
        ))

        self.assertTrue(metric["ok"], metric["messages"])
        self.assertTrue(imperial["ok"], imperial["messages"])
        metric_selected = metric["serialized_result"]["selected_result"]
        imperial_selected = imperial["serialized_result"]["selected_result"]
        self.assertEqual(metric_selected["total_boxes"], 22)
        self.assertEqual(imperial_selected["total_boxes"], 22)
        self.assertEqual(
            len(metric["threejs_scene"]["placements"]),
            len(imperial["threejs_scene"]["placements"]),
        )
        self.assertEqual(imperial_selected["max_pallet_load_display"], "48.502 lb")

    def test_catalogue_carton_weight_uses_the_same_gross_weight_contract(self):
        material = SimpleNamespace(
            external_length=400,
            external_width=400,
            external_height=200,
            part_length=400,
            part_width=400,
            part_height=200,
            part_weight=Decimal("1.000"),
        )
        result = analyze_palletization_config(
            self._config(
                box_source="catalogue",
                box_weight="",
                max_pallet_load=22,
            ),
            selected_box_material=material,
        )

        self.assertTrue(result["ok"], result["messages"])
        self.assertEqual(result["effective_config"]["box_weight"], 1000)
        self.assertEqual(
            result["serialized_result"]["selected_result"]["total_boxes"],
            22,
        )

    def test_recalculation_uses_the_modified_limit(self):
        first = analyze_palletization_config(self._config(max_pallet_load=22))
        second = analyze_palletization_config(self._config(max_pallet_load=11))

        self.assertEqual(first["serialized_result"]["selected_result"]["total_boxes"], 22)
        self.assertEqual(second["serialized_result"]["selected_result"]["total_boxes"], 11)
        self.assertEqual(len(second["threejs_scene"]["placements"]), 11)

    def test_prefixed_workflow_state_persists_json_safe_limit_and_matches_service(self):
        step = {"config": self._config()}
        posted = {
            "max_pallet_load_2": "22",
            "mass_unit_2": "kg",
        }
        flow_config = _read_prefixed_pallet_post(step, 2, posted)
        json.dumps(flow_config)

        standalone = analyze_palletization_config(self._config(max_pallet_load=22))
        workflow = analyze_palletization_config(flow_config)

        self.assertEqual(flow_config["max_pallet_load"], "22")
        self.assertEqual(
            standalone["serialized_result"]["selected_result"]["total_boxes"],
            workflow["serialized_result"]["selected_result"]["total_boxes"],
        )


class PalletMaximumLoadPresentationTests(TestCase):
    def _analysis(self):
        config = default_palletization_config()
        config.update({
            "box_l": 400,
            "box_w": 400,
            "box_h": 200,
            "box_weight": 1,
            "mass_unit": "kg",
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 150,
            "max_stack_height": 1150,
            "max_pallet_load": 22,
        })
        return analyze_palletization_config(config)

    def test_shared_ui_contract_exposes_prefixed_field_on_app_and_public_surfaces(self):
        contract = build_pallet_ui_contract(prefix="2")
        self.assertEqual(contract["names"]["max_pallet_load"], "max_pallet_load_2")

        standalone = self.client.get(reverse("palletization_mode1"))
        public = self.client.get(reverse("palletization_calculator"))
        self.assertContains(standalone, "Max Pallet Load")
        self.assertContains(standalone, 'name="max_pallet_load"')
        self.assertContains(public, 'name="max_pallet_load"')

    def test_standalone_post_renders_the_capped_result_and_load_metrics(self):
        response = self.client.post(reverse("palletization_mode1"), {
            "action": "run_analysis",
            "box_source": "manual",
            "box_l": "400",
            "box_w": "400",
            "box_h": "200",
            "box_dimension_unit": "mm",
            "box_weight": "1",
            "mass_unit": "kg",
            "pallet_source": "manual",
            "pallet_l": "1200",
            "pallet_w": "800",
            "pallet_height": "150",
            "pallet_dimension_unit": "mm",
            "max_stack_height": "1150",
            "max_pallet_load": "22",
            "max_width_stickout": "0",
            "max_length_stickout": "0",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cartons per pallet")
        self.assertContains(response, "22 pcs")
        self.assertContains(response, "Actual pallet load")
        self.assertContains(response, "Maximum pallet load")
        self.assertContains(response, "Load utilization")
        self.assertContains(response, "Weight")

    def test_screen_and_both_pdf_metric_paths_use_serialized_load_values(self):
        analysis = self._analysis()
        selected = analysis["serialized_result"]["selected_result"]

        self.assertEqual(selected["actual_pallet_load_display"], "22 kg")
        self.assertEqual(selected["max_pallet_load_display"], "22 kg")
        self.assertEqual(selected["load_utilization_pct"], 100)

        flow_rows = dict(_step_metrics({
            "type": "pallet",
            "config": {"mass_unit": "kg", "pallet_dimension_unit": "mm"},
            "selected_result": selected,
        }))
        self.assertEqual(flow_rows["Actual pallet load"], "22 kg")
        self.assertEqual(flow_rows["Maximum pallet load"], "22 kg")
        self.assertEqual(flow_rows["Load utilization"], "100.00%")
        self.assertEqual(flow_rows["Limiting constraint"], "Weight")

        standalone_rows = dict(_analysis_rows(selected))
        self.assertEqual(standalone_rows["Actual pallet load"], "22 kg")
        self.assertEqual(standalone_rows["Maximum pallet load"], "22 kg")
        self.assertEqual(standalone_rows["Load utilization"], "100.0%")
        self.assertEqual(standalone_rows["Limiting constraint"], "Weight")

        pdf = build_palletization_pdf({
            "box": {"source": "Manual", "dimensions": "400 × 400 × 200 mm", "weight": "1 kg"},
            "pallet": {
                "source": "Manual",
                "dimensions": "1200 × 800 × 150 mm",
                "max_stack_height": "1150 mm",
                "max_pallet_load": "22 kg",
                "overhang": "0 mm",
            },
            "analysis_report": selected,
        })
        self.assertTrue(pdf.getvalue().startswith(b"%PDF"))

    def test_blank_limit_omits_limit_and_utilization_from_serialized_result(self):
        config = default_palletization_config()
        config.update({
            "box_l": 400,
            "box_w": 400,
            "box_h": 200,
            "box_weight": 1,
            "mass_unit": "kg",
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 150,
            "max_stack_height": 1150,
            "max_pallet_load": "",
        })
        selected = analyze_palletization_config(config)["serialized_result"]["selected_result"]

        self.assertIsNone(selected["max_pallet_load_g"])
        self.assertIsNone(selected["load_utilization_pct"])
        self.assertEqual(selected["actual_pallet_load_display"], "30 kg")
