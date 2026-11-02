from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from django.urls import reverse

from packagingapp.forms import ContainerSelectionMode1Form
from packagingapp.models import CorrugatedBoardConstruction, CorrugatedECTReferenceGrade
from packagingapp.tools.container.corrugated_material import (
    LB_MSF_TO_GSM,
    build_corrugated_material_options,
    gsm_to_lb_msf,
    resolve_corrugated_caliper,
)
from packagingapp.tools.container.service import (
    apply_manual_rsc_design_defaults,
    apply_catalogue_choices,
    build_container_analysis_report,
    get_corrugated_material_options,
)


class CorrugatedMaterialSelectionTests(TestCase):
    def _analysis_form(self, thickness=""):
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
            "box_thickness_mm": thickness,
            "container_dimension_unit": "mm",
            "container_mass_unit": "g",
            "corrugated_material_id": "FEFCO_C_175_140_175",
        }
        form = ContainerSelectionMode1Form(data)
        form.fields["corrugated_material_id"].choices = [
            ("", "No carton tare calculation"),
            ("FEFCO_C_175_140_175", "C flute"),
        ]
        return form

    def test_areal_density_conversion_is_not_mass_conversion(self):
        self.assertEqual(gsm_to_lb_msf(Decimal("560.2")), Decimal("560.2") / LB_MSF_TO_GSM)
        self.assertAlmostEqual(float(gsm_to_lb_msf("560.2")), 114.7, places=1)

    def test_reference_caliper_uses_lowest_ect_category(self):
        construction = SimpleNamespace(
            caliper_mm=None,
            flute_1="C",
            flute_2="",
            flute_display="C",
        )
        grades = [
            SimpleNamespace(
                is_active=True,
                flute_family="C",
                ect_lb_in=Decimal("55"),
                reference_caliper_mm=Decimal("4.64"),
                code="REF_C_55",
            ),
            SimpleNamespace(
                is_active=True,
                flute_family="C",
                ect_lb_in=Decimal("32"),
                reference_caliper_mm=Decimal("4.08"),
                code="REF_C_32",
            ),
        ]
        resolved = resolve_corrugated_caliper(construction, grades)
        self.assertEqual(resolved.source, "reference")
        self.assertEqual(resolved.value_mm, Decimal("4.08"))
        self.assertEqual(resolved.reference_grade_code, "REF_C_32")

    def test_actual_caliper_has_priority_over_reference(self):
        construction = SimpleNamespace(
            caliper_mm=Decimal("3.95"),
            flute_1="C",
            flute_2="",
            flute_display="C",
        )
        resolved = resolve_corrugated_caliper(
            construction,
            [SimpleNamespace(
                is_active=True,
                flute_family="C",
                ect_lb_in=Decimal("32"),
                reference_caliper_mm=Decimal("4.08"),
                code="REF_C_32",
            )],
        )
        self.assertEqual(resolved.source, "actual")
        self.assertEqual(resolved.value_mm, Decimal("3.95"))

    def test_reference_families_and_labels_use_catalogue_values(self):
        codes = {
            "A": "REF_A_32",
            "B": "REF_B_32",
            "C": "REF_C_32",
            "E": "REF_E_32",
            "F": "REF_F_32",
            "N": "REF_N_32",
            "EB": "REF_EB_42",
            "BC": "REF_BC_42",
        }
        grades = CorrugatedECTReferenceGrade.objects.filter(code__in=codes.values())
        for family, code in codes.items():
            construction = SimpleNamespace(
                caliper_mm=None,
                flute_1=family[0],
                flute_2=family[1] if len(family) == 2 else "",
                flute_display=family,
            )
            resolved = resolve_corrugated_caliper(construction, grades)
            self.assertEqual(resolved.source, "reference")
            self.assertEqual(resolved.reference_grade_code, code)

    def test_catalogue_option_has_metric_and_imperial_labels(self):
        construction = CorrugatedBoardConstruction.objects.get(
            code="FEFCO_C_175_140_175"
        )
        metric = get_corrugated_material_options(
            [construction], dimension_unit="mm"
        )[0]
        imperial = get_corrugated_material_options(
            [construction], dimension_unit="in"
        )[0]
        self.assertIn("560.2 g/m²", metric["label"])
        self.assertIn("4.08 mm", metric["label"])
        self.assertIn("114.7 lb/MSF", imperial["label"])
        self.assertIn("0.1606 in", imperial["label"])

    def test_new_choices_use_codes_and_hide_legacy_custom_choice(self):
        construction = CorrugatedBoardConstruction.objects.get(
            code="FEFCO_C_175_140_175"
        )
        form = ContainerSelectionMode1Form(initial={"corrugated_material_id": ""})
        apply_catalogue_choices(
            form,
            [],
            [],
            corrugated_materials=[construction],
            container_dimension_unit="mm",
        )
        choices = list(form.fields["corrugated_material_id"].choices)
        self.assertNotIn("custom", [value for value, _ in choices])
        self.assertIn((construction.code, choices[-1][1]), choices)

        legacy = ContainerSelectionMode1Form(
            initial={"corrugated_material_id": "custom"}
        )
        apply_catalogue_choices(
            legacy,
            [],
            [],
            corrugated_materials=[construction],
        )
        self.assertIn(
            "custom",
            [value for value, _ in legacy.fields["corrugated_material_id"].choices],
        )

    def test_container_page_renders_caliper_and_metric_grammage(self):
        response = self.client.get(reverse("container_selection_mode1"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "560.2 g/m²")
        self.assertContains(response, "4.08 mm (reference)")
        self.assertNotContains(response, "Custom grammage")

    def test_new_manual_design_defaults_use_stable_code_and_display_unit(self):
        config = apply_manual_rsc_design_defaults(
            {
                "mode": "design",
                "container_source": "manual",
                "container_dimension_unit": "in",
                "corrugated_material_id": "",
                "box_thickness_mm": "",
            },
            enabled=True,
        )
        self.assertEqual(config["corrugated_material_id"], "FEFCO_C_175_140_175")
        self.assertAlmostEqual(float(config["box_thickness_mm"]), 4.08 / 25.4, places=7)

    def test_caliper_prefills_effective_thickness_but_manual_override_wins(self):
        board = CorrugatedBoardConstruction.objects.get(
            code="FEFCO_C_175_140_175"
        )
        automatic = self._analysis_form()
        self.assertTrue(automatic.is_valid(), automatic.errors)
        automatic_report = build_container_analysis_report(
            form=automatic,
            result=SimpleNamespace(max_quantity=12),
            product=(100, 80, 50),
            container=(600, 400, 300),
            desired_qty=5,
            product_source="manual",
            selected_board_construction=board,
        )
        override = self._analysis_form("4.5")
        self.assertTrue(override.is_valid(), override.errors)
        override_report = build_container_analysis_report(
            form=override,
            result=SimpleNamespace(max_quantity=12),
            product=(100, 80, 50),
            container=(600, 400, 300),
            desired_qty=5,
            product_source="manual",
            selected_board_construction=board,
        )
        self.assertEqual(automatic_report["box_thickness_mm"], 4.08)
        self.assertEqual(automatic_report["corrugated_caliper_source"], "reference")
        self.assertEqual(override_report["box_thickness_mm"], 4.5)
        self.assertEqual(
            automatic_report["carton_tare_g"], override_report["carton_tare_g"]
        )
        self.assertNotEqual(
            automatic_report["external_length"], override_report["external_length"]
        )

    def test_unavailable_caliper_is_explicit(self):
        construction = SimpleNamespace(
            caliper_mm=None,
            flute_1="",
            flute_2="",
            flute_display="",
        )
        option = build_corrugated_material_options(
            [SimpleNamespace(
                pk=1,
                code="UNKNOWN",
                name="Unknown",
                wall_type="SINGLE_WALL",
                flute_display="",
                combined_grammage_g_m2=Decimal("300"),
                caliper_mm=None,
            )],
            [],
        )[0]
        self.assertEqual(resolve_corrugated_caliper(construction, []).source, "unavailable")
        self.assertEqual(option["caliper_source"], "unavailable")
        self.assertIn("Caliper", option["label"])
