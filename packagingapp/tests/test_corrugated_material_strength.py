import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from packagingapp.forms import CorrugatedMaterialStrengthForm
from packagingapp.models import CorrugatedBoardConstruction
from packagingapp.tools.corrugated_material_strength.contracts import build_shared_corrugated_material_ui_contract
from packagingapp.tools.corrugated_material_strength.geometry import BoxGeometryInput, Fefco0201GeometryProvider
from packagingapp.tools.corrugated_material_strength.service import calculate_corrugated_material_strength
from packagingapp.tools.corrugated_material_strength.strength import predict_bct_mckee_metric


class CorrugatedModelTests(TestCase):
    def test_all_seed_codes_and_grammage(self):
        expected = {
            "GEN_E_125_90_125": Decimal("377.25"),
            "GEN_E_150_100_150": Decimal("440.00"),
            "GEN_B_125_100_125": Decimal("394.00"),
            "GEN_B_150_120_150": Decimal("470.50"),
            "GEN_C_150_120_150": Decimal("481.60"),
            "FEFCO_C_175_140_175": Decimal("560.20"),
            "GEN_A_175_140_175": Decimal("573.00"),
            "GEN_EB_150_100_125_120_150": Decimal("735.50"),
            "GEN_BC_175_120_150_140_175": Decimal("880.70"),
        }
        self.assertEqual(CorrugatedBoardConstruction.objects.count(), 9)
        for code, grammage in expected.items():
            construction = CorrugatedBoardConstruction.objects.get(code=code)
            self.assertEqual(construction.combined_grammage_g_m2, grammage)
            self.assertIsNone(construction.ect_kn_m)
            self.assertIsNone(construction.caliper_mm)
            self.assertIsNone(construction.measured_bct_n)

    def test_single_and_double_wall_validation(self):
        single = CorrugatedBoardConstruction(
            code="TEST_SINGLE", name="Test", source_type="ADMIN_ENTERED", source_label="Test",
            wall_type="SINGLE_WALL", flute_1="B", outer_liner_gsm=125,
            medium_1_gsm=100, inner_liner_gsm=125, take_up_factor_1=Decimal("1.325"),
            glue_per_layer_1_gsm=Decimal("5.75"),
        )
        single.full_clean()
        self.assertEqual(single.combined_grammage_g_m2, Decimal("394.00"))
        double = CorrugatedBoardConstruction(
            code="TEST_DOUBLE", name="Test", source_type="ADMIN_ENTERED", source_label="Test",
            wall_type="DOUBLE_WALL", flute_1="E", flute_2="B", outer_liner_gsm=150,
            medium_1_gsm=100, middle_liner_gsm=125, medium_2_gsm=120, inner_liner_gsm=150,
            take_up_factor_1=Decimal("1.275"), take_up_factor_2=Decimal("1.325"),
            glue_per_layer_1_gsm=Decimal("6.25"), glue_per_layer_2_gsm=Decimal("5.75"),
        )
        double.full_clean()
        self.assertEqual(double.flute_display, "EB")
        self.assertEqual(double.combined_grammage_g_m2, Decimal("735.50"))

    def test_invalid_single_wall_second_medium_is_rejected(self):
        construction = CorrugatedBoardConstruction(
            code="TEST_INVALID", name="Test", source_type="ADMIN_ENTERED", source_label="Test",
            wall_type="SINGLE_WALL", flute_1="B", flute_2="C", outer_liner_gsm=125,
            medium_1_gsm=100, inner_liner_gsm=125, take_up_factor_1=Decimal("1.325"),
            glue_per_layer_1_gsm=Decimal("5.75"),
        )
        with self.assertRaises(Exception):
            construction.full_clean()

    def test_co2_metadata_is_required_when_factor_exists(self):
        construction = CorrugatedBoardConstruction(
            code="TEST_CO2", name="Test", source_type="ADMIN_ENTERED", source_label="Test",
            wall_type="SINGLE_WALL", flute_1="B", outer_liner_gsm=125,
            medium_1_gsm=100, inner_liner_gsm=125, take_up_factor_1=Decimal("1.325"),
            glue_per_layer_1_gsm=Decimal("5.75"), co2_factor_kg_co2e_per_kg=Decimal("0.491"),
        )
        with self.assertRaises(Exception):
            construction.full_clean()


class CorrugatedCalculationTests(TestCase):
    def test_benchmark_geometry_material_pallet_and_strength(self):
        geometry = Fefco0201GeometryProvider().calculate(BoxGeometryInput(
            Decimal("400"), Decimal("300"), Decimal("200"), Decimal("40"), Decimal("20")
        ))
        self.assertEqual(geometry.blank_length_mm, Decimal("1440"))
        self.assertEqual(geometry.blank_width_mm, Decimal("500"))
        self.assertEqual(geometry.effective_box_area_m2, Decimal("0.708"))
        self.assertEqual(geometry.production_sheet_area_m2, Decimal("0.7992"))
        self.assertAlmostEqual(float(geometry.material_utilization_percent), 88.5886, places=3)
        construction = CorrugatedBoardConstruction.objects.get(code="FEFCO_C_175_140_175")
        result = calculate_corrugated_material_strength({
            "box_length_mm": 400, "box_width_mm": 300, "box_height_mm": 200,
            "product_weight_g": 200, "quantity": 1000, "joint_width_mm": 40,
            "sheet_margin_per_edge_mm": 20, "pallet_length_mm": 1200,
            "pallet_width_mm": 800, "pallet_height_mm": 144, "pallet_weight_kg": 0,
            "max_palletized_height_mm": 1200, "stacked_pallets": 1,
            "pattern": "COLUMN_ALIGNED", "distribution_profile": "NORMAL",
            "board_mode": "catalogue", "co2_mode": "CONSTRUCTION",
            "ect_override_kn_m": 4.0, "caliper_override_mm": 3.6,
        }, construction=construction)
        self.assertAlmostEqual(result["finished_box_weight_g"], 0.708 * 560.2, places=4)
        self.assertEqual(result["boxes_per_layer"], 8)
        self.assertEqual(result["layers"], 5)
        self.assertEqual(result["boxes_per_pallet"], 40)
        self.assertAlmostEqual(result["supported_mass_kg"], 2.3864864, places=5)
        self.assertAlmostEqual(result["required_bct_n"], 70.209, places=2)
        self.assertAlmostEqual(result["available_bct_n"], 1586.695, places=2)
        self.assertGreater(result["strength_margin"], 22)
        self.assertAlmostEqual(result["finished_box_co2_kg"] + result["cutting_scrap_co2_kg"], result["required_sheet_co2_kg"], places=8)
        json.dumps(result)

    def test_missing_strength_does_not_use_nominal_flute_height(self):
        construction = CorrugatedBoardConstruction.objects.get(code="GEN_E_150_100_150")
        result = calculate_corrugated_material_strength({
            "box_length_mm": 400, "box_width_mm": 300, "box_height_mm": 200,
            "product_weight_g": 200, "quantity": 1, "joint_width_mm": 40,
            "sheet_margin_per_edge_mm": 20, "pallet_length_mm": 1200,
            "pallet_width_mm": 800, "pallet_height_mm": 144,
            "max_palletized_height_mm": 1200, "distribution_profile": "NORMAL",
            "co2_mode": "CONSTRUCTION",
        }, construction=construction)
        self.assertEqual(result["strength_status"], "Strength unavailable")
        self.assertIsNone(result["available_bct_n"])
        self.assertIn("finished-board caliper", result["strength"]["data_note"])

    def test_mckee_units_and_override_priority(self):
        value = predict_bct_mckee_metric(Decimal("4.0"), Decimal("3.6"), Decimal("140"))
        self.assertAlmostEqual(float(value), 1586.695, places=2)


class CorrugatedContractAndViewTests(TestCase):
    def test_prefix_contract_is_unique_and_json_safe(self):
        contract = build_shared_corrugated_material_ui_contract(mode="workflow", prefix="3")
        self.assertEqual(contract["field_ids"]["box_length_mm"], "3_box_length_mm")
        self.assertEqual(len(contract["field_ids"].values()), len(set(contract["field_ids"].values())))
        json.dumps(contract)

    def test_get_renders_defaults_and_catalogue(self):
        response = self.client.get(reverse("corrugated_material_strength"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Corrugated Material &amp; Strength")
        self.assertContains(response, "GEN_E_125_90_125")
        self.assertContains(response, "Preliminary engineering estimate")

    def test_valid_post_renders_result_and_strength_unavailable_state(self):
        construction = CorrugatedBoardConstruction.objects.get(code="GEN_E_125_90_125")
        response = self.client.post(reverse("corrugated_material_strength"), {
            "action": "run_analysis", "box_length_mm": "400", "box_width_mm": "300", "box_height_mm": "200",
            "product_weight_g": "200", "quantity": "1000", "fefco_code": "0201", "joint_width_mm": "40",
            "sheet_margin_per_edge_mm": "20", "pallet_source": "manual", "pallet_length_mm": "1200",
            "pallet_width_mm": "800", "pallet_height_mm": "144", "pallet_weight_kg": "0",
            "max_palletized_height_mm": "1200", "pattern": "COLUMN_ALIGNED", "stacked_pallets": "1",
            "board_mode": "catalogue", "board_construction_id": str(construction.pk), "manual_wall_type": "SINGLE_WALL",
            "distribution_profile": "NORMAL", "distribution_factor": "3", "co2_mode": "CONSTRUCTION",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Strength unavailable")
        self.assertContains(response, "Required sheet material")
        self.assertIn("corrugated_material_strength_last_analysis", self.client.session)

    def test_manual_board_entry_and_pdf_export(self):
        response = self.client.post(reverse("corrugated_material_strength"), {
            "action": "run_analysis", "box_length_mm": "400", "box_width_mm": "300", "box_height_mm": "200",
            "product_weight_g": "200", "quantity": "1000", "fefco_code": "0201", "joint_width_mm": "40",
            "sheet_margin_per_edge_mm": "20", "pallet_source": "manual", "pallet_length_mm": "1200",
            "pallet_width_mm": "800", "pallet_height_mm": "144", "pallet_weight_kg": "0",
            "max_palletized_height_mm": "1200", "pattern": "COLUMN_ALIGNED", "stacked_pallets": "1",
            "board_mode": "manual", "manual_wall_type": "SINGLE_WALL", "manual_flute_1": "C",
            "manual_combined_grammage_g_m2": "560", "ect_override_kn_m": "4", "caliper_override_mm": "3.6",
            "distribution_profile": "NORMAL", "distribution_factor": "3", "co2_mode": "CUSTOM",
            "custom_co2_factor_kg_per_kg": "0.491", "custom_co2_source": "Test screening", "custom_co2_boundary": "Screening",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Predicted / measured BCT")
        pdf = self.client.get(reverse("corrugated_material_strength_export_pdf"))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
