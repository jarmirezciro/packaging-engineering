from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from packagingapp.forms import ContainerSelectionMode1Form
from packagingapp.tools.bag.service import build_bag_analysis_report
from packagingapp.tools.bag.export import build_bag_selection_single_pdf
from packagingapp.tools.container.service import build_container_analysis_report
from packagingapp.tools.container.service import analyze_container_capacity
from packagingapp.tools.container.export import build_container_selection_single_pdf
from packagingapp.tools.corrugated_material_strength.export import build_corrugated_material_strength_pdf
from packagingapp.tools.corrugated_material_strength.presenter import present_corrugated_result
from packagingapp.tools.corrugated_material_strength.serializers import serialize_corrugated_inputs
from packagingapp.tools.corrugated_material_strength.service import calculate_corrugated_material_strength
from packagingapp.tools.full_packaging.export import build_workflow_report_payload
from packagingapp.tools.full_packaging.flow_summary import build_packaging_flow_summary
from packagingapp.tools.palletization.service import (
    analyze_palletization_capacity,
    analyze_palletization_config,
)
from packagingapp.tools.palletization.export import build_palletization_pdf
from packagingapp.tools.transport.presenter import attach_transport_result_presentation
from packagingapp.tools.transport.export import build_transport_container_pdf
from packagingapp.tools.transport.service import (
    analyze_transport_capacity,
    transport_rows_for_display,
)
from packagingapp.units import convert_length, convert_mass
from packagingapp.views.full_packaging import (
    _apply_payload_to_config,
    _build_container_non_design_workflow_payload,
    _build_pallet_workflow_payload,
    _build_transport_workflow_payload,
    _transport_rows_from_selected,
)


class CorrugatedUnitPresentationTests(TestCase):
    @staticmethod
    def _metric_inputs():
        return {
            "box_dimension_unit": "mm",
            "product_mass_unit": "g",
            "pallet_dimension_unit": "mm",
            "pallet_mass_unit": "kg",
            "material_dimension_unit": "mm",
            "box_length_mm": Decimal("400"),
            "box_width_mm": Decimal("300"),
            "box_height_mm": Decimal("200"),
            "product_weight_g": Decimal("200"),
            "quantity": 1000,
            "fefco_code": "0201",
            "joint_width_mm": Decimal("40"),
            "sheet_margin_per_edge_mm": Decimal("20"),
            "pallet_source": "manual",
            "pallet_length_mm": Decimal("1200"),
            "pallet_width_mm": Decimal("800"),
            "pallet_height_mm": Decimal("144"),
            "pallet_weight_kg": Decimal("25"),
            "max_palletized_height_mm": Decimal("1200"),
            "pattern": "COLUMN_ALIGNED",
            "stacked_pallets": 1,
            "board_mode": "manual",
            "manual_wall_type": "SINGLE_WALL",
            "manual_flute_1": "C",
            "manual_combined_grammage_g_m2": Decimal("560"),
            "ect_override_kn_m": Decimal("4"),
            "caliper_override_mm": Decimal("3.6"),
            "distribution_profile": "NORMAL",
            "distribution_factor": Decimal("3"),
            "co2_mode": "CONSTRUCTION",
        }

    def test_equivalent_units_preserve_corrugated_engine_results(self):
        metric_data = self._metric_inputs()
        imperial_data = dict(metric_data)
        imperial_data.update({
            "box_dimension_unit": "in",
            "product_mass_unit": "lb",
            "pallet_dimension_unit": "ft",
            "pallet_mass_unit": "lb",
            "material_dimension_unit": "in",
        })
        for key in (
            "box_length_mm", "box_width_mm", "box_height_mm",
            "joint_width_mm", "sheet_margin_per_edge_mm",
        ):
            imperial_data[key] = convert_length(metric_data[key], "mm", "in")
        for key in (
            "pallet_length_mm", "pallet_width_mm", "pallet_height_mm",
            "max_palletized_height_mm",
        ):
            imperial_data[key] = convert_length(metric_data[key], "mm", "ft")
        imperial_data["product_weight_g"] = convert_mass(
            metric_data["product_weight_g"], "g", "lb"
        )
        imperial_data["pallet_weight_kg"] = convert_mass(
            metric_data["pallet_weight_kg"], "kg", "lb"
        )
        imperial_data["caliper_override_mm"] = convert_length(
            metric_data["caliper_override_mm"], "mm", "in"
        )

        metric_inputs = serialize_corrugated_inputs(metric_data)
        imperial_inputs = serialize_corrugated_inputs(imperial_data)
        for key in (
            "box_length_mm", "box_width_mm", "box_height_mm",
            "product_weight_g", "joint_width_mm", "sheet_margin_per_edge_mm",
            "pallet_length_mm", "pallet_width_mm", "pallet_height_mm",
            "pallet_weight_kg", "max_palletized_height_mm", "caliper_override_mm",
        ):
            self.assertAlmostEqual(metric_inputs[key], imperial_inputs[key], places=9)

        metric_result = calculate_corrugated_material_strength(metric_inputs)
        imperial_result = calculate_corrugated_material_strength(imperial_inputs)
        for key in (
            "blank_length_mm", "blank_width_mm", "finished_box_weight_g",
            "external_length_mm", "external_width_mm", "external_height_mm",
            "boxes_per_pallet", "palletized_height_mm", "required_bct_n",
        ):
            self.assertAlmostEqual(metric_result[key], imperial_result[key], places=8)

        presented = present_corrugated_result(imperial_result, imperial_inputs)
        self.assertTrue(presented["display"]["internal_dimensions"].endswith(" in"))
        self.assertTrue(presented["display"]["gross_packed_box_weight"].endswith(" lb"))
        self.assertTrue(presented["display"]["palletized_height"].endswith(" ft"))
        self.assertEqual(presented["external_length_mm"], imperial_result["external_length_mm"])

    def test_corrugated_page_exposes_all_shared_unit_groups(self):
        response = self.client.get(reverse("corrugated_material_strength"))
        self.assertEqual(response.status_code, 200)
        for name, group in (
            ("box_dimension_unit", "corrugated-box-dimensions"),
            ("product_mass_unit", "corrugated-product-mass"),
            ("pallet_dimension_unit", "corrugated-pallet-dimensions"),
            ("pallet_mass_unit", "corrugated-pallet-mass"),
            ("material_dimension_unit", "corrugated-material-dimensions"),
        ):
            self.assertContains(response, f'name="{name}"')
            self.assertContains(response, f'data-unit-group="{group}"')
        self.assertContains(response, "js/unit_selector.js")


class MajorToolResultPresentationTests(SimpleTestCase):
    def test_repeated_unit_switch_cycles_return_to_the_same_physical_value(self):
        length = Decimal("1234.56789")
        current_length_unit = "mm"
        for target in ("in", "ft", "cm", "mm"):
            length = convert_length(length, current_length_unit, target)
            current_length_unit = target
        self.assertEqual(length, Decimal("1234.56789"))

        mass = Decimal("9876.54321")
        current_mass_unit = "g"
        for target in ("lb", "oz", "kg", "g"):
            mass = convert_mass(mass, current_mass_unit, target)
            current_mass_unit = target
        self.assertEqual(mass, Decimal("9876.54321"))

    def test_container_and_bag_reports_keep_canonical_values_and_add_local_strings(self):
        form = ContainerSelectionMode1Form(data={
            "mode": "single",
            "product_source": "manual",
            "product_l": "3.937007874",
            "product_w": "3.149606299",
            "product_h": "2.362204724",
            "product_dimension_unit": "in",
            "product_weight": "1",
            "product_mass_unit": "lb",
            "desired_qty": "2",
            "r1": "on", "r2": "on", "r3": "on",
            "container_source": "manual",
            "box_l": "1.312335958",
            "box_w": "0.984251969",
            "box_h": "0.820209974",
            "box_thickness_mm": "0.01312336",
            "container_dimension_unit": "ft",
            "box_weight": "1",
            "box_max_payload": "20",
            "container_mass_unit": "lb",
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        container = build_container_analysis_report(
            form=form,
            result=SimpleNamespace(max_quantity=8),
            product=(100, 80, 60),
            container=(400, 300, 250),
            desired_qty=2,
            product_source="manual",
        )
        self.assertEqual(
            (container["internal_length"], container["internal_width"], container["internal_height"]),
            (400.0, 300.0, 250.0),
        )
        self.assertTrue(container["internal_dimensions_display"].endswith(" ft"))
        self.assertTrue(container["total_weight_current_display"].endswith(" lb"))

        bag = build_bag_analysis_report(
            config={
                "product_source": "manual",
                "product_weight": 1,
                "product_mass_unit": "lb",
                "product_dimension_unit": "in",
                "bag_source": "manual",
                "bag_weight": 1,
                "bag_max_payload": 20,
                "bag_dimension_unit": "ft",
                "bag_mass_unit": "lb",
            },
            result={
                "desired_qty": 2,
                "max_quantity": 4,
                "fits": True,
                "bag_len": 450,
                "bag_w": 330,
                "best_required": (400, 300),
                "usage": 0.8,
            },
            product=(100, 80, 60),
            quantity=2,
        )
        self.assertEqual(bag["current_quantity"], 2)
        self.assertTrue(bag["bag_dimensions_display"].endswith(" ft"))
        self.assertTrue(bag["total_weight_display"].endswith(" lb"))

    def test_pallet_and_transport_presenters_do_not_change_canonical_geometry(self):
        pallet = analyze_palletization_config({
            "box_source": "manual",
            "box_l": convert_length(Decimal("400"), "mm", "in"),
            "box_w": convert_length(Decimal("300"), "mm", "in"),
            "box_h": convert_length(Decimal("250"), "mm", "in"),
            "box_dimension_unit": "in",
            "box_weight": convert_mass(Decimal("450"), "g", "lb"),
            "max_weight_on_bottom_box": convert_mass(Decimal("5000"), "g", "lb"),
            "mass_unit": "lb",
            "pallet_source": "manual",
            "pallet_l": convert_length(Decimal("1200"), "mm", "ft"),
            "pallet_w": convert_length(Decimal("800"), "mm", "ft"),
            "pallet_height": convert_length(Decimal("144"), "mm", "ft"),
            "pallet_dimension_unit": "ft",
            "max_stack_height": convert_length(Decimal("1200"), "mm", "ft"),
            "max_width_stickout": 0,
            "max_length_stickout": 0,
        })
        self.assertTrue(pallet["ok"], pallet["messages"])
        selected = pallet["serialized_result"]["selected_result"]
        self.assertGreater(selected["total_height_mm"], 0)
        self.assertTrue(selected["total_height_display"].endswith(" ft"))
        self.assertTrue(selected["max_bottom_load_display"].endswith(" lb"))

        serialized = {
            "summary": {
                "loaded_weight": 200,
                "tare_weight": 100,
                "gross_weight": 300,
                "container_max_weight": 1000,
                "occupied_length": 2400,
                "occupied_width": 1200,
                "occupied_height": 1000,
                "residual_length": 100,
                "residual_width": 50,
                "residual_height": 200,
                "product_rows": [{
                    "length": 1200, "width": 800, "height": 1000,
                    "weight_each": 100,
                }],
            },
            "threejs_scene": {"products": [{"length": 1200}]},
        }
        canonical = deepcopy(serialized)
        presented = attach_transport_result_presentation(serialized, {
            "load_unit_dimension_unit": "in",
            "load_unit_mass_unit": "lb",
            "transport_dimension_unit": "ft",
            "transport_mass_unit": "lb",
        })
        self.assertEqual(presented["summary"]["gross_weight"], canonical["summary"]["gross_weight"])
        self.assertEqual(presented["threejs_scene"]["products"][0]["length"], 1200)
        self.assertTrue(presented["display"]["occupied_dimensions"].endswith(" ft"))
        self.assertTrue(presented["summary"]["product_rows"][0]["weight_each_display"].endswith(" lb"))


class FullPackagingUnitPresentationTests(SimpleTestCase):
    @staticmethod
    def _workflow():
        return {
            "steps": [{
                "type": "container",
                "config": {
                    "product_dimension_unit": "cm",
                    "product_mass_unit": "g",
                    "container_dimension_unit": "in",
                    "container_mass_unit": "lb",
                },
                "selected": {
                    "label": "Case",
                    "length": 508,
                    "width": 254,
                    "height": 127,
                    "weight_kg": 4.5359237,
                    "units_per_parent": 10,
                    "total_base_units": 10,
                },
            }, {
                "type": "transport",
                "config": {
                    "load_unit_dimension_unit": "in",
                    "load_unit_mass_unit": "lb",
                    "transport_dimension_unit": "ft",
                    "transport_mass_unit": "lb",
                },
                "selected": {
                    "label": "Transport container",
                    "length": 6096,
                    "width": 2438.4,
                    "height": 2590.8,
                    "weight_kg": 1000,
                    "units_per_parent": 2,
                    "total_base_units": 20,
                },
                "result": {
                    "summary": {
                        "placed_units": 2,
                        "unplaced_units": 0,
                        "utilization_volume_pct": 50,
                        "utilization_weight_pct": 10,
                        "gross_weight": 1000,
                        "product_rows": [{
                            "name": "Case", "length": 508, "width": 254,
                            "height": 127, "weight_each": 4.5359237,
                            "qty_requested": 2, "qty_packed": 2,
                        }],
                    },
                },
            }],
        }

    def test_flow_summary_and_pdf_payload_use_each_step_unit_context(self):
        workflow = self._workflow()
        canonical = deepcopy(workflow)
        summary = build_packaging_flow_summary(workflow["steps"])
        self.assertIn("in", summary["stages"][0]["physical"])
        self.assertIn("lb", summary["stages"][0]["physical"])
        self.assertIn("ft", summary["stages"][1]["physical"])

        report = build_workflow_report_payload(workflow)
        self.assertEqual(report["steps"][0]["output"]["dimensions_display"], "20 × 10 × 5 in")
        self.assertEqual(report["steps"][0]["output"]["weight_display"], "10 lb")
        self.assertEqual(report["steps"][1]["input"]["dimensions_display"], "20 × 10 × 5 in")
        self.assertTrue(report["steps"][1]["output"]["dimensions_display"].endswith(" ft"))
        self.assertEqual(report["steps"][1]["transport_rows"][0]["dimensions_display"], "20 × 10 × 5 in")
        self.assertEqual(report["steps"][1]["transport_rows"][0]["weight_each_display"], "10 lb")
        self.assertEqual(workflow, canonical)


class FullPackagingEndToEndUnitEquivalenceTests(SimpleTestCase):
    @staticmethod
    def _container_run(*, alternative):
        if alternative:
            config = {
                "mode": "single", "product_source": "manual",
                "product_l": convert_length(Decimal("100"), "mm", "in"),
                "product_w": convert_length(Decimal("80"), "mm", "in"),
                "product_h": convert_length(Decimal("60"), "mm", "in"),
                "product_dimension_unit": "in",
                "product_weight": convert_mass(Decimal("453.59237"), "g", "lb"),
                "product_mass_unit": "lb", "desired_qty": 1,
                "r1": True, "r2": True, "r3": True,
                "container_source": "manual",
                "box_l": Decimal("40"), "box_w": Decimal("30"), "box_h": Decimal("25"),
                "box_thickness_mm": "", "container_dimension_unit": "cm",
                "box_weight": Decimal("450"), "box_max_payload": Decimal("10000"),
                "container_mass_unit": "g",
            }
        else:
            config = {
                "mode": "single", "product_source": "manual",
                "product_l": Decimal("100"), "product_w": Decimal("80"),
                "product_h": Decimal("60"), "product_dimension_unit": "mm",
                "product_weight": Decimal("453.59237"), "product_mass_unit": "g",
                "desired_qty": 1, "r1": True, "r2": True, "r3": True,
                "container_source": "manual",
                "box_l": Decimal("400"), "box_w": Decimal("300"),
                "box_h": Decimal("250"), "box_thickness_mm": "",
                "container_dimension_unit": "mm", "box_weight": Decimal("450"),
                "box_max_payload": Decimal("10000"), "container_mass_unit": "g",
            }
        form = ContainerSelectionMode1Form(data=config)
        if not form.is_valid():
            raise AssertionError(form.errors.as_json())
        analysis = analyze_container_capacity(form, config)
        if not analysis["ok"]:
            raise AssertionError(analysis["messages"])
        payload = _build_container_non_design_workflow_payload(
            config,
            analysis["result"]["max_quantity"],
            None,
            None,
            None,
        )
        return payload

    @staticmethod
    def _pallet_run(container_payload, *, alternative):
        if alternative:
            config = {
                "box_dimension_unit": "in", "mass_unit": "kg",
                "pallet_dimension_unit": "mm", "pallet_source": "manual",
                "pallet_l": 1200, "pallet_w": 800, "pallet_height": 144,
                "max_stack_height": 1200, "max_width_stickout": 0,
                "max_length_stickout": 0,
                "max_weight_on_bottom_box": 100,
            }
        else:
            config = {
                "box_dimension_unit": "mm", "mass_unit": "g",
                "pallet_dimension_unit": "mm", "pallet_source": "manual",
                "pallet_l": 1200, "pallet_w": 800, "pallet_height": 144,
                "max_stack_height": 1200, "max_width_stickout": 0,
                "max_length_stickout": 0,
                "max_weight_on_bottom_box": 100000,
            }
        config = _apply_payload_to_config(config, "pallet", container_payload)
        analysis = analyze_palletization_capacity(config)
        if not analysis["ok"]:
            raise AssertionError(analysis["messages"])
        effective = analysis["effective_config"]
        payload = _build_pallet_workflow_payload(
            effective,
            analysis["selected_row"],
            None,
            container_payload,
        )
        return payload, analysis

    @staticmethod
    def _transport_run(pallet_payload, *, alternative):
        canonical_rows = _transport_rows_from_selected(pallet_payload)
        if alternative:
            config = {
                "container_source": "manual", "packing_mode": "space_evenly",
                "container_l": convert_length(Decimal("6000"), "mm", "ft"),
                "container_w": convert_length(Decimal("2500"), "mm", "ft"),
                "container_h": convert_length(Decimal("2600"), "mm", "ft"),
                "max_weight": convert_mass(Decimal("20000"), "kg", "lb"),
                "tare_weight": convert_mass(Decimal("1000"), "kg", "lb"),
                "load_unit_dimension_unit": "ft", "load_unit_mass_unit": "lb",
                "transport_dimension_unit": "ft", "transport_mass_unit": "lb",
            }
            rows = transport_rows_for_display(canonical_rows, "ft", "lb")
        else:
            config = {
                "container_source": "manual", "packing_mode": "space_evenly",
                "container_l": 6000, "container_w": 2500, "container_h": 2600,
                "max_weight": 20000, "tare_weight": 1000,
                "load_unit_dimension_unit": "mm", "load_unit_mass_unit": "kg",
                "transport_dimension_unit": "mm", "transport_mass_unit": "kg",
            }
            rows = transport_rows_for_display(canonical_rows, "mm", "kg")
        analysis = analyze_transport_capacity(config, rows)
        if not analysis["ok"]:
            raise AssertionError(analysis["messages"])
        final_payload = _build_transport_workflow_payload(
            analysis["container"],
            analysis["result"],
            analysis["summary"],
            None,
            pallet_payload,
        )
        return final_payload, analysis

    def test_metric_and_mixed_unit_complete_workflows_have_the_same_physics(self):
        metric_container = self._container_run(alternative=False)
        mixed_container = self._container_run(alternative=True)
        self.assertEqual(metric_container, mixed_container)

        metric_pallet, metric_pallet_analysis = self._pallet_run(
            metric_container, alternative=False
        )
        mixed_pallet, mixed_pallet_analysis = self._pallet_run(
            mixed_container, alternative=True
        )
        self.assertEqual(metric_pallet, mixed_pallet)
        metric_row = metric_pallet_analysis["selected_row"]
        mixed_row = mixed_pallet_analysis["selected_row"]
        for key in (
            "pattern", "stacking", "boxes_layer_A", "boxes_layer_B", "layers",
            "total_boxes", "feasible_weight",
        ):
            self.assertEqual(metric_row[key], mixed_row[key])
        for key in ("used_height_mm", "max_bottom_load_g", "weight_limit_g"):
            self.assertAlmostEqual(metric_row[key], mixed_row[key], places=8)

        metric_final, metric_transport = self._transport_run(
            metric_pallet, alternative=False
        )
        mixed_final, mixed_transport = self._transport_run(
            mixed_pallet, alternative=True
        )
        self.assertEqual(metric_final, mixed_final)
        self.assertEqual(
            metric_transport["summary"]["placed_units"],
            mixed_transport["summary"]["placed_units"],
        )
        self.assertEqual(
            metric_transport["summary"]["utilization_volume_pct"],
            mixed_transport["summary"]["utilization_volume_pct"],
        )
        metric_geometry = [
            (p.row_index, p.x, p.y, p.z, p.l, p.w, p.h)
            for p in metric_transport["result"]["placements"]
        ]
        mixed_geometry = [
            (p.row_index, p.x, p.y, p.z, p.l, p.w, p.h)
            for p in mixed_transport["result"]["placements"]
        ]
        self.assertEqual(len(metric_geometry), len(mixed_geometry))
        for metric_placement, mixed_placement in zip(metric_geometry, mixed_geometry):
            for metric_value, mixed_value in zip(metric_placement, mixed_placement):
                if isinstance(metric_value, (int, float)):
                    self.assertAlmostEqual(metric_value, mixed_value, places=8)
                else:
                    self.assertEqual(metric_value, mixed_value)


class LegacyMetricReportCompatibilityTests(SimpleTestCase):
    def test_legacy_payloads_without_display_metadata_still_build_metric_pdfs(self):
        container_pdf = build_container_selection_single_pdf({
            "product": {"source": "Manual", "id": "P1", "name": "Product", "dimensions": "100 × 80 × 60 mm", "weight": "200 g"},
            "container": {"source": "Manual", "part_number": "BOX", "description": "Box", "type": "BOX", "dimensions": "400 × 300 × 250 mm", "external_dimensions": "408 × 308 × 258 mm", "box_thickness_mm": 4},
            "analysis_report": {"max_quantity": 8, "requested_qty": 1},
        })
        bag_pdf = build_bag_selection_single_pdf({
            "product": {"source": "Manual", "id": "P1", "name": "Product", "dimensions": "100 × 80 × 60 mm", "weight": "200 g"},
            "bag": {"source": "Manual", "part_number": "BAG", "description": "Bag", "dimensions": "450 × 330 mm", "weight": "18 g"},
            "analysis_report": {"max_quantity": 4, "current_quantity": 1},
        })
        pallet_pdf = build_palletization_pdf({
            "box": {"source": "Manual", "part_number": "BOX", "description": "Box", "dimensions": "400 × 300 × 250 mm", "weight": "450 g"},
            "pallet": {"source": "Manual", "part_number": "PALLET", "description": "Pallet", "dimensions": "1200 × 800 × 144 mm", "max_stack_height": "1200 mm", "overhang": "0 mm"},
            "analysis_report": {
                "boxes_layer_A": 8, "layers": 4, "total_boxes": 32,
                "total_height_mm": 1144, "used_height_mm": 1000,
                "layer_footprint_util_pct": 100, "volumetric_util_pct": 83,
                "feasible_weight": True, "max_bottom_load_kg": 10800,
                "weight_limit_kg": 100000,
            },
        })
        transport_pdf = build_transport_container_pdf({
            "transport_unit": {"source": "Manual", "part_number": "TRAILER", "dimensions": "6000 × 2500 × 2600 mm"},
            "summary": {
                "placed_units": 1, "unplaced_units": 0,
                "utilization_volume_pct": 10, "utilization_weight_pct": 5,
                "packed_volume_m3": 1, "container_volume_m3": 39,
                "loaded_weight": 500, "gross_weight": 1500,
                "occupied_length": 1200, "occupied_width": 800, "occupied_height": 1000,
                "residual_length": 4800, "residual_width": 1700, "residual_height": 1600,
                "product_rows": [{
                    "name": "Pallet", "length": 1200, "width": 800, "height": 1000,
                    "weight_each": 500, "qty_requested": 1, "qty_packed": 1,
                }],
            },
        })
        corrugated_inputs = serialize_corrugated_inputs(
            CorrugatedUnitPresentationTests._metric_inputs()
        )
        for unit_key in (
            "box_dimension_unit", "product_mass_unit", "pallet_dimension_unit",
            "pallet_mass_unit", "material_dimension_unit",
        ):
            corrugated_inputs.pop(unit_key, None)
        corrugated_pdf = build_corrugated_material_strength_pdf({
            "inputs": corrugated_inputs,
            "result": calculate_corrugated_material_strength(corrugated_inputs),
        })
        for pdf in (
            container_pdf, bag_pdf, pallet_pdf, transport_pdf, corrugated_pdf
        ):
            self.assertTrue(pdf.getvalue().startswith(b"%PDF"))
