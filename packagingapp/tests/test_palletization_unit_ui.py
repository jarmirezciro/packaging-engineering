from django.test import TestCase
from django.urls import reverse


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
