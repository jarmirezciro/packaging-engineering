from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from packagingapp.forms import ContainerSelectionMode1Form
from packagingapp.tools.container.carton_tare import calculate_rsc_carton_tare
from packagingapp.tools.container.service import (
    analyze_container_capacity,
    build_container_analysis_report,
)
from packagingapp.tools.full_packaging.chain_optimizer import build_design_candidate_payload
from packagingapp.views.full_packaging import _build_container_non_design_workflow_payload


def container_form(**overrides):
    data = {
        "mode": "single",
        "action": "run_single",
        "product_source": "manual",
        "product_l": "100",
        "product_w": "80",
        "product_h": "50",
        "product_weight": "100",
        "product_mass_unit": "g",
        "desired_qty": "5",
        "r1": "on",
        "r2": "on",
        "r3": "on",
        "container_source": "manual",
        "box_l": "600",
        "box_w": "400",
        "box_h": "300",
        "container_dimension_unit": "mm",
        "container_mass_unit": "g",
        "box_weight": "",
        "corrugated_material_id": "",
        "custom_combined_grammage_g_m2": "",
    }
    data.update(overrides)
    form = ContainerSelectionMode1Form(data)
    form.fields["corrugated_material_id"].choices = [
        ("", "No carton tare calculation"),
        ("custom", "Custom grammage"),
        ("board-1", "Reference board"),
    ]
    return form


def board(grammage="560.2"):
    return SimpleNamespace(
        pk=1,
        name="Reference board",
        combined_grammage_g_m2=grammage,
    )


def report_for(form, *, selected_board=None, selected_material=None, config=None):
    assert form.is_valid(), form.errors
    return build_container_analysis_report(
        form=form,
        result=SimpleNamespace(max_quantity=12),
        product=(100, 80, 50),
        container=(600, 400, 300),
        desired_qty=5,
        product_source="manual",
        selected_material=selected_material,
        selected_board_construction=selected_board,
    )


class CartonTareCalculationTests(SimpleTestCase):
    def test_custom_selection_requires_positive_grammage(self):
        form = container_form(corrugated_material_id="custom")
        self.assertFalse(form.is_valid())
        self.assertIn("custom_combined_grammage_g_m2", form.errors)

    def test_invalid_non_finite_tare_inputs_fail_closed(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calculate_rsc_carton_tare(600, 400, 300, value)

    def test_geometry_and_grammage_are_independent_inputs(self):
        small = calculate_rsc_carton_tare(600, 400, 300, "560.2")
        larger = calculate_rsc_carton_tare(800, 500, 350, "560.2")
        heavier_board = calculate_rsc_carton_tare(600, 400, 300, "880.7")

        self.assertGreater(larger.finished_box_weight_g, small.finished_box_weight_g)
        self.assertGreater(heavier_board.finished_box_weight_g, small.finished_box_weight_g)
        self.assertGreater(larger.effective_box_area_m2, small.effective_box_area_m2)

    def test_custom_grammage_produces_tare_and_gross_weight(self):
        form = container_form(
            corrugated_material_id="custom",
            custom_combined_grammage_g_m2="300",
        )
        report = report_for(form)
        expected_tare = calculate_rsc_carton_tare(600, 400, 300, 300).finished_box_weight_g

        self.assertAlmostEqual(report["carton_tare_g"], float(expected_tare), places=3)
        self.assertEqual(report["carton_tare_source"], "estimated_material")
        self.assertEqual(report["fefco_code"], "0201")
        self.assertAlmostEqual(report["gross_carton_weight_g"], 1200 + float(expected_tare), places=3)

    def test_selected_board_estimate_is_available_when_product_weight_is_unknown(self):
        form = container_form(
            product_weight="",
            corrugated_material_id="board-1",
        )
        report = report_for(form, selected_board=board())

        self.assertIsNotNone(report["carton_tare_g"])
        self.assertIsNone(report["gross_carton_weight_g"])
        self.assertEqual(report["carton_tare_source"], "estimated_material")
        self.assertFalse(report["has_gross_carton_weight"])

    def test_precedence_catalogue_then_manual_then_material_then_unavailable(self):
        selected_board = board()

        catalogue_form = container_form(
            container_source="catalogue",
            corrugated_material_id="board-1",
            box_weight="500",
        )
        catalogue_report = report_for(
            catalogue_form,
            selected_board=selected_board,
            selected_material=SimpleNamespace(packaging_type="BOX", part_weight=0.75),
        )
        self.assertEqual(catalogue_report["carton_tare_g"], 750.0)
        self.assertEqual(catalogue_report["carton_tare_source"], "catalogue")

        manual_form = container_form(
            corrugated_material_id="board-1",
            box_weight="500",
        )
        manual_report = report_for(manual_form, selected_board=selected_board)
        self.assertEqual(manual_report["carton_tare_g"], 500.0)
        self.assertEqual(manual_report["carton_tare_source"], "manual")

        estimated_report = report_for(
            container_form(corrugated_material_id="board-1"),
            selected_board=selected_board,
        )
        self.assertEqual(estimated_report["carton_tare_source"], "estimated_material")

        crate_report = report_for(
            container_form(
                container_source="catalogue",
                corrugated_material_id="board-1",
            ),
            selected_board=selected_board,
            selected_material=SimpleNamespace(packaging_type="CRATE", part_weight=None),
        )
        self.assertIsNone(crate_report["carton_tare_g"])
        self.assertEqual(crate_report["carton_tare_source"], "unavailable")

    def test_manual_tare_converts_from_selected_mass_unit_once(self):
        form = container_form(
            box_weight="1",
            container_mass_unit="lb",
        )
        report = report_for(form)

        self.assertAlmostEqual(report["carton_tare_g"], 453.59237, places=3)
        self.assertEqual(report["carton_tare_source"], "manual")

    def test_clearing_selector_does_not_reuse_old_session_board(self):
        form = container_form(corrugated_material_id="")
        self.assertTrue(form.is_valid(), form.errors)
        report = build_container_analysis_report(
            form=form,
            result=SimpleNamespace(max_quantity=12),
            product=(100, 80, 50),
            container=(600, 400, 300),
            desired_qty=5,
            product_source="manual",
            selected_board_construction=None,
        )
        self.assertEqual(report["carton_tare_source"], "unavailable")
        self.assertIsNone(report["carton_tare_g"])

    def test_design_calculates_tare_per_candidate(self):
        form = container_form(
            mode="design",
            action="run_design",
            desired_qty="7",
            corrugated_material_id="board-1",
        )
        config = {"corrugated_material_id": "board-1"}
        self.assertTrue(form.is_valid(), form.errors)
        with patch(
            "packagingapp.tools.container.service.get_selected_corrugated_construction",
            return_value=board(),
        ):
            analysis = analyze_container_capacity(form, config)

        self.assertTrue(analysis["ok"], analysis.get("messages"))
        candidates = analysis["design_candidates"]
        tares = {row["carton_tare_g"] for row in candidates}
        self.assertGreater(len(tares), 1)
        self.assertTrue(all(row["carton_tare_source"] == "estimated_material" for row in candidates))
        self.assertTrue(all(row["gross_carton_weight_g"] is not None for row in candidates))

    def test_workflow_inherits_gross_once_and_design_payload_prefers_gross(self):
        cfg = {
            "mode": "single",
            "product_source": "manual",
            "product_l": "100",
            "product_w": "80",
            "product_h": "50",
            "product_weight": "100",
            "product_mass_unit": "g",
            "container_dimension_unit": "mm",
            "box_l": "600",
            "box_w": "400",
            "box_h": "300",
        }
        payload = _build_container_non_design_workflow_payload(
            cfg,
            12,
            None,
            None,
            None,
            analysis_report={
                "gross_carton_weight_g": 1630,
                "net_weight": 1500,
                "carton_tare_g": 130,
                "carton_tare_source": "estimated_material",
                "carton_tare_source_display": "Estimated from corrugated material",
            },
        )
        self.assertAlmostEqual(payload["weight_g"], 1630.0, places=9)
        self.assertAlmostEqual(payload["weight_kg"], 1.63, places=9)
        self.assertEqual(payload["net_content_weight_g"], 1500.0)
        self.assertEqual(payload["carton_tare_g"], 130.0)

        design_payload = build_design_candidate_payload(
            "container",
            {
                "candidate_id": "candidate-1",
                "design_quantity": 5,
                "net_content_weight": 1500,
                "gross_carton_weight_g": 1630,
                "container_length": 600,
                "container_width": 400,
                "container_height": 300,
            },
        )
        self.assertAlmostEqual(design_payload["weight_g"], 1630.0, places=9)
        self.assertAlmostEqual(design_payload["weight_kg"], 1.63, places=9)
