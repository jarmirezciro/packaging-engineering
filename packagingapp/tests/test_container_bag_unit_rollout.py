from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from packagingapp.forms import BagSelectionForm, ContainerSelectionMode1Form
from packagingapp.tools.bag.service import (
    analyze_bag_capacity,
    analyze_bag_config,
    build_bag_analysis_report,
)
from packagingapp.tools.container.service import (
    analyze_container_capacity,
    build_container_analysis_report,
)


def _container_form(**overrides):
    data = {
        "mode": "single",
        "action": "run_single",
        "product_source": "manual",
        "product_l": "100",
        "product_w": "80",
        "product_h": "60",
        "product_weight": "453.59237",
        "desired_qty": "1",
        "r1": "on",
        "r2": "on",
        "r3": "on",
        "container_source": "manual",
        "box_l": "400",
        "box_w": "300",
        "box_h": "250",
        "box_thickness_mm": "4",
        "box_weight": "450",
        "box_max_payload": "5000",
        "product_dimension_unit": "mm",
        "product_mass_unit": "g",
        "container_dimension_unit": "mm",
        "container_mass_unit": "g",
    }
    data.update(overrides)
    return ContainerSelectionMode1Form(data=data), data


def _bag_config(**overrides):
    config = {
        "mode": "single",
        "action": "run_single",
        "product_source": "manual",
        "product_l": 100,
        "product_w": 80,
        "product_h": 60,
        "product_weight": 453.59237,
        "desired_qty": 1,
        "product_shape": "cuboid",
        "bag_source": "manual",
        "bag_length": 450,
        "bag_width": 330,
        "bag_weight": 450,
        "bag_max_payload": 5000,
        "product_dimension_unit": "mm",
        "product_mass_unit": "g",
        "bag_dimension_unit": "mm",
        "bag_mass_unit": "g",
    }
    config.update(overrides)
    return config


class ContainerManualUnitBoundaryTests(SimpleTestCase):
    def test_equivalent_product_and_container_dimensions_normalize_to_same_capacity(self):
        metric_form, metric_data = _container_form(
            product_l="76.2",
            product_w="50.8",
            product_h="38.1",
        )
        self.assertTrue(metric_form.is_valid(), metric_form.errors.as_json())
        metric = analyze_container_capacity(metric_form, metric_data)
        self.assertTrue(metric["ok"], metric["messages"])

        imperial_form, imperial_data = _container_form(
            product_l="3",
            product_w="2",
            product_h="1.5",
            product_dimension_unit="in",
            box_l="1.312335958005249",
            box_w="0.984251968503937",
            box_h="0.820209973753281",
            box_thickness_mm="0.0131233595800525",
            container_dimension_unit="ft",
        )
        self.assertTrue(imperial_form.is_valid(), imperial_form.errors.as_json())
        imperial = analyze_container_capacity(imperial_form, imperial_data)
        self.assertTrue(imperial["ok"], imperial["messages"])
        self.assertEqual(metric["result"]["max_quantity"], imperial["result"]["max_quantity"])
        for actual, expected in zip(imperial["result"]["container"], metric["result"]["container"]):
            self.assertAlmostEqual(actual, expected, places=7)

    def test_equivalent_manual_mass_values_are_reported_as_same_grams(self):
        metric_form, _ = _container_form()
        self.assertTrue(metric_form.is_valid(), metric_form.errors.as_json())
        imperial_form, _ = _container_form(
            product_weight="1",
            product_mass_unit="lb",
            box_weight="0.992080017",
            box_max_payload="11.023113109",
            container_mass_unit="lb",
        )
        self.assertTrue(imperial_form.is_valid(), imperial_form.errors.as_json())

        kwargs = {
            "result": SimpleNamespace(max_quantity=8),
            "product": (100, 80, 60),
            "container": (400, 300, 250),
            "desired_qty": 1,
            "product_source": "manual",
            "mode": "single",
        }
        metric_report = build_container_analysis_report(form=metric_form, **kwargs)
        imperial_report = build_container_analysis_report(form=imperial_form, **kwargs)
        self.assertAlmostEqual(imperial_report["product_weight"], metric_report["product_weight"], places=6)
        self.assertAlmostEqual(imperial_report["container_tare"], metric_report["container_tare"], places=6)
        self.assertAlmostEqual(imperial_report["payload_capacity"], metric_report["payload_capacity"], places=6)

    def test_invalid_units_are_not_reinterpreted_as_metric(self):
        form, data = _container_form(product_dimension_unit="yard")
        form.is_valid()
        result = analyze_container_capacity(form, data)
        self.assertFalse(result["ok"])
        self.assertTrue(any("Unsupported product dimension unit" in message for message in result["messages"]))

    def test_legacy_metric_request_without_unit_metadata_still_works(self):
        form, data = _container_form()
        for key in (
            "product_dimension_unit",
            "product_mass_unit",
            "container_dimension_unit",
            "container_mass_unit",
        ):
            data.pop(key)
        form = ContainerSelectionMode1Form(data=data)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        result = analyze_container_capacity(form, data)
        self.assertTrue(result["ok"], result["messages"])


class BagManualUnitBoundaryTests(SimpleTestCase):
    def test_capacity_helper_uses_the_same_canonical_bag_dimensions(self):
        metric = analyze_bag_capacity(_bag_config())
        imperial = analyze_bag_capacity(
            _bag_config(
                product_l=10,
                product_w=8,
                product_h=6,
                product_dimension_unit="cm",
                bag_length=17.7165354330709,
                bag_width=12.992125984252,
                bag_dimension_unit="in",
            )
        )
        self.assertTrue(metric["ok"], metric["messages"])
        self.assertTrue(imperial["ok"], imperial["messages"])
        self.assertEqual(metric["pending_result"]["units_per_parent"], imperial["pending_result"]["units_per_parent"])
        for key in ("length", "width", "height"):
            self.assertAlmostEqual(
                metric["pending_result"][key],
                imperial["pending_result"][key],
                places=6,
            )

    def test_equivalent_units_preserve_bag_fit_result(self):
        metric = _bag_config()
        imperial = _bag_config(
            product_l=10,
            product_w=8,
            product_h=6,
            product_dimension_unit="cm",
            product_weight=1,
            product_mass_unit="lb",
            bag_length=17.7165354330709,
            bag_width=12.992125984252,
            bag_dimension_unit="in",
            bag_weight=0.992080017,
            bag_max_payload=11.023113109,
            bag_mass_unit="lb",
        )
        with TemporaryDirectory() as media_root:
            metric_result = analyze_bag_config(metric, "run_single", media_root=media_root)
            imperial_result = analyze_bag_config(imperial, "run_single", media_root=media_root)

        self.assertEqual(metric_result["messages"], [])
        self.assertEqual(imperial_result["messages"], [])
        for key in ("max_quantity", "fits", "bag_len", "bag_w", "best_required"):
            if key in ("bag_len", "bag_w"):
                self.assertAlmostEqual(imperial_result["result"][key], metric_result["result"][key], places=6)
            else:
                self.assertEqual(imperial_result["result"][key], metric_result["result"][key])

    def test_manual_mass_report_normalizes_to_grams(self):
        metric = _bag_config()
        imperial = _bag_config(
            product_weight=1,
            product_mass_unit="lb",
            bag_weight=0.992080017,
            bag_max_payload=11.023113109,
            bag_mass_unit="lb",
        )
        result = {
            "desired_qty": 1,
            "max_quantity": 1,
            "fits": True,
            "bag_len": 450,
            "bag_w": 330,
            "best_required": (400, 300),
            "usage": 0.8,
        }
        metric_report = build_bag_analysis_report(
            config=metric,
            result=result,
            product=(100, 80, 60),
            quantity=1,
        )
        imperial_report = build_bag_analysis_report(
            config=imperial,
            result=result,
            product=(100, 80, 60),
            quantity=1,
        )
        self.assertAlmostEqual(imperial_report["product_weight"], metric_report["product_weight"], places=6)
        self.assertAlmostEqual(imperial_report["bag_weight"], metric_report["bag_weight"], places=6)
        self.assertAlmostEqual(imperial_report["payload_capacity"], metric_report["payload_capacity"], places=6)

    def test_invalid_units_are_not_reinterpreted_as_metric(self):
        result = analyze_bag_config(
            _bag_config(product_dimension_unit="yard"),
            "run_single",
        )
        self.assertTrue(any("Unsupported product dimension unit" in message for message in result["messages"]))
        self.assertIsNone(result["result"])


class ContainerBagUnitSelectorTemplateTests(TestCase):
    def test_standalone_tools_render_the_shared_selector(self):
        container = self.client.get(reverse("container_selection_calculator"))
        bag = self.client.get(reverse("bag_selection_calculator"))
        self.assertEqual(container.status_code, 200)
        self.assertEqual(bag.status_code, 200)
        for response, group in (
            (container, "container-product-dimensions"),
            (container, "container-packaging-mass"),
            (bag, "bag-product-dimensions"),
            (bag, "bag-packaging-mass"),
        ):
            self.assertContains(response, "data-unit-selector")
            self.assertContains(response, f'data-unit-group="{group}"')
            self.assertContains(response, "Millimetres (mm)")
            self.assertContains(response, "Pounds (lb)")
            self.assertContains(response, "js/unit_selector.js")

    def test_full_packaging_carries_prefixed_unit_groups(self):
        self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "container"},
        )
        response = self.client.get(reverse("full_packaging_mode"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="product_dimension_unit_0"')
        self.assertContains(response, 'data-unit-group="container-product-dimensions_0"')

        self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "bag"},
        )
        response = self.client.get(reverse("full_packaging_mode"))
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.content.decode(), r'name="bag_dimension_unit_\d+"')
        self.assertRegex(response.content.decode(), r'data-unit-group="bag-packaging-dimensions_\d+"')
