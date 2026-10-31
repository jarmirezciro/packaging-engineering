from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from packagingapp.models import PackagingCatalogue, PackagingMaterial, UserPreferences


class PalletizationUnitSelectorTemplateTests(TestCase):
    def test_public_palletization_renders_the_shared_selector(self):
        response = self.client.get(reverse("palletization_calculator"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/unit_selector.js")
        self.assertContains(response, 'data-unit-group="pallet-box-dimensions"')
        self.assertContains(response, "Millimetres (mm)")
        self.assertContains(response, "Pounds (lb)")

    def test_workflow_selector_uses_prefixed_json_safe_state(self):
        self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "pallet"},
        )
        response = self.client.get(reverse("full_packaging_mode"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="box_dimension_unit_0"')
        self.assertContains(response, 'data-unit-group="pallet-box-dimensions_0"')
        self.assertContains(response, 'aria-controls="boxDimensionUnitMenu_0-length"')
        self.assertEqual(
            response.context["steps"][0]["config"]["box_dimension_unit"],
            "mm",
        )

    def test_packaging_flow_renders_selected_pallet_summary_in_local_units(self):
        user = get_user_model().objects.create_user(
            username="pallet-flow-user",
            password="pass-123",
        )
        UserPreferences.objects.create(
            user=user,
            default_length_unit="in",
            default_small_mass_unit="lb",
            default_large_mass_unit="kg",
        )
        catalogue = PackagingCatalogue.objects.create(
            name="Flow Pallets",
            is_public=True,
        )
        pallet = PackagingMaterial.objects.create(
            catalogue=catalogue,
            part_number="FLOW-PALLET-1",
            part_description="Euro Pallet",
            packaging_type="PALLET",
            branding="Brand1",
            packaging_materials="Wood",
            part_length=Decimal("1200"),
            part_width=Decimal("800"),
            part_height=Decimal("144"),
            part_weight=Decimal("25"),
        )
        self.client.force_login(user)

        self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "pallet"},
        )
        response = self.client.post(
            reverse("full_packaging_mode"),
            {
                "action": "run_step",
                "index": "0",
                "action_0": "select_pallet",
                "pallet_source_0": "catalogue",
                "pallet_catalogue_id_0": str(catalogue.pk),
                "pallet_id_0": str(pallet.pk),
                "max_stack_height_0": "50",
                "max_width_stickout_0": "",
                "max_length_stickout_0": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["steps"][0]["config"]["pallet_dimension_unit"],
            "in",
        )
        self.assertEqual(response.context["steps"][0]["config"]["max_stack_height"], "50")
        self.assertContains(response, 'name="max_stack_height_0"')
        self.assertContains(response, 'value="50"')
        self.assertContains(response, "FLOW-PALLET-1")
        self.assertContains(response, "Euro Pallet")
        self.assertContains(response, "47.244")
        self.assertContains(response, "in")
        self.assertContains(response, "55.116")
        self.assertContains(response, "lb")
