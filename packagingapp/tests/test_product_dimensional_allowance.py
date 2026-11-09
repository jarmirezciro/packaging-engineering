from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from tempfile import TemporaryDirectory

from packagingapp.forms import BagSelectionForm, ContainerSelectionMode1Form
from packagingapp.tools.bag.service import analyze_bag_capacity, analyze_bag_config
from packagingapp.tools.container.service import analyze_container_capacity, analyze_container_form
from packagingapp.tools.container.dimensions import resolve_external_carton_dimensions
from packagingapp.tools.container.state import default_container_config
from packagingapp.tools.product_dimensions import (
    apply_product_allowances,
    normalize_product_allowances,
)
from packagingapp.utils.box_selection.box_selection_tool_arrays_2_origin_coordinates import (
    allowed_product_orientations,
)
from packagingapp.utils.box_selection.engine import build_container_design_candidates
from packagingapp.views.full_packaging import _apply_payload_to_config


def _container_data(**overrides):
    data = {
        "mode": "single",
        "action": "run_single",
        "product_source": "manual",
        "product_l": "2.49",
        "product_w": "2.49",
        "product_h": "10",
        "product_allowance_l": "0",
        "product_allowance_w": "0",
        "product_allowance_h": "0",
        "product_dimension_unit": "in",
        "product_mass_unit": "g",
        "desired_qty": "24",
        "r1": "",
        "r2": "",
        "r3": "on",
        "container_source": "manual",
        "box_l": "16",
        "box_w": "6",
        "box_h": "21",
        "box_thickness_mm": "0.16",
        "container_dimension_unit": "in",
        "container_mass_unit": "g",
    }
    data.update(overrides)
    return data


def _bag_config(**overrides):
    config = {
        "mode": "single",
        "action": "run_single",
        "product_source": "manual",
        "product_l": 63.246,
        "product_w": 63.246,
        "product_h": 254,
        "product_allowance_l": 0,
        "product_allowance_w": 0,
        "product_allowance_h": 0,
        "product_dimension_unit": "mm",
        "product_mass_unit": "g",
        "bag_source": "manual",
        "bag_length": 600,
        "bag_width": 300,
        "bag_dimension_unit": "mm",
        "bag_mass_unit": "g",
    }
    config.update(overrides)
    return config


class ProductDimensionalAllowanceContractTests(SimpleTestCase):
    def test_allowances_are_added_once_and_keep_original_axis_relationship(self):
        nominal = (63.246, 63.246, 254.0)
        allowances = normalize_product_allowances((0.12, 0.12, 0.12), "in")
        self.assertEqual(
            tuple(round(value, 6) for value in allowances),
            (3.048, 3.048, 3.048),
        )
        self.assertEqual(
            tuple(round(value, 6) for value in apply_product_allowances(nominal, allowances)),
            (66.294, 66.294, 257.048),
        )

        rotated = allowed_product_orientations(
            apply_product_allowances((10, 20, 30), (1, 2, 3)),
            1,
            1,
            1,
        )
        self.assertIn((11.0, 22.0, 33.0), [row["dimensions"] for row in rotated])
        self.assertIn((33.0, 22.0, 11.0), [row["dimensions"] for row in rotated])

    def test_zero_allowance_preserves_container_capacity(self):
        metric = ContainerSelectionMode1Form(data=_container_data(
            product_dimension_unit="mm",
            product_l="63.246",
            product_w="63.246",
            product_h="254",
            container_dimension_unit="mm",
            box_l="406.4",
            box_w="152.4",
            box_h="533.4",
            box_thickness_mm="4.064",
        ))
        legacy = ContainerSelectionMode1Form(data={
            key: value
            for key, value in _container_data(
                product_dimension_unit="mm",
                product_l="63.246",
                product_w="63.246",
                product_h="254",
                container_dimension_unit="mm",
                box_l="406.4",
                box_w="152.4",
                box_h="533.4",
                box_thickness_mm="4.064",
            ).items()
            if not key.startswith("product_allowance_")
        })
        self.assertTrue(metric.is_valid(), metric.errors.as_json())
        self.assertTrue(legacy.is_valid(), legacy.errors.as_json())
        current = analyze_container_capacity(metric, metric.data)
        previous = analyze_container_capacity(legacy, legacy.data)
        self.assertTrue(current["ok"], current["messages"])
        self.assertTrue(previous["ok"], previous["messages"])
        self.assertEqual(current["result"], previous["result"])

    def test_nonzero_container_allowance_changes_capacity_input(self):
        form = ContainerSelectionMode1Form(data=_container_data(
            product_allowance_l="0.12",
            product_allowance_w="0.12",
            product_allowance_h="0.12",
            box_l="15",
            box_w="5",
            box_h="20.2",
        ))
        self.assertTrue(form.is_valid(), form.errors.as_json())
        result = analyze_container_capacity(form, form.data)
        self.assertTrue(result["ok"], result["messages"])
        # 2.49 + 0.12 inches, with allowance applied once per product.
        expected = (2.61 * 25.4, 2.61 * 25.4, 10.12 * 25.4)
        self.assertLess(result["result"]["max_quantity"], 24)
        # The selected internal carton is intentionally tight: nominal product
        # dimensions fit 24, while the effective envelope does not.
        self.assertGreater(expected[0], 2.49 * 25.4)

    def test_capepack_arrangement_uses_effective_envelope_and_separate_thickness(self):
        nominal = (2.49 * 25.4, 2.49 * 25.4, 10 * 25.4)
        allowances = normalize_product_allowances((0.12, 0.12, 0.12), "in")
        effective = apply_product_allowances(nominal, allowances)
        design = build_container_design_candidates(effective, 24, 0, 0, 1)
        candidate = next(
            row
            for row in design["candidates"]
            if (row["rows"], row["columns"], row["layers"]) == (6, 2, 2)
        )

        self.assertEqual(candidate["orientation_index"], 0)  # height vertical
        self.assertAlmostEqual(candidate["container_length"], effective[0] * 6, places=1)
        self.assertAlmostEqual(candidate["container_width"], effective[1] * 2, places=1)
        self.assertAlmostEqual(candidate["container_height"], effective[2] * 2, places=1)

        external = resolve_external_carton_dimensions(
            candidate["container_length"],
            candidate["container_width"],
            candidate["container_height"],
            thickness_mm=0.16 * 25.4,
        )
        self.assertAlmostEqual(external["external_length"] / 25.4, 15.98, places=2)
        self.assertAlmostEqual(external["external_width"] / 25.4, 5.54, places=2)
        self.assertAlmostEqual(external["external_height"] / 25.4, 20.88, places=2)
        self.assertAlmostEqual(external["box_thickness_mm"], 0.16 * 25.4, places=6)

    def test_bag_design_uses_effective_product_dimensions(self):
        result = analyze_bag_config(
            _bag_config(
                mode="design",
                action="run_design",
                desired_qty=6,
                product_allowance_l=3.048,
                product_allowance_w=3.048,
                product_allowance_h=3.048,
            ),
            "run_design",
        )
        self.assertEqual(result["messages"], [])
        self.assertEqual(
            result["analysis_report"]["effective_product_dimensions_display"],
            "66.294 × 66.294 × 257.048 mm",
        )

    def test_bag_uses_effective_dimensions_but_product_scene_stays_nominal(self):
        with TemporaryDirectory() as media_root:
            result = analyze_bag_config(
                _bag_config(
                    product_allowance_l=3.048,
                    product_allowance_w=3.048,
                    product_allowance_h=3.048,
                    bag_length=900,
                    bag_width=500,
                ),
                "run_single",
                media_root=media_root,
            )
        self.assertEqual(result["messages"], [])
        self.assertIsNotNone(result["analysis_report"])
        self.assertEqual(
            result["analysis_report"]["effective_product_dimensions_display"],
            "66.294 × 66.294 × 257.048 mm",
        )
        self.assertEqual(
            result["product_unit_scene"]["productDefinition"],
            {"length": 63.246, "width": 63.246, "height": 254.0},
        )

    def test_container_report_exposes_nominal_and_effective_dimensions(self):
        form = ContainerSelectionMode1Form(data=_container_data(
            product_allowance_l="0.12",
            product_allowance_w="0.12",
            product_allowance_h="0.12",
        ))
        self.assertTrue(form.is_valid(), form.errors.as_json())
        with TemporaryDirectory() as media_root:
            result = analyze_container_form(
                form,
                form.data,
                media_root=media_root,
            )
        self.assertEqual(result["messages"], [])
        self.assertEqual(
            result["analysis_report"]["effective_product_dimensions_display"],
            "2.61 × 2.61 × 10.12 in",
        )
        self.assertEqual(
            result["product_unit_scene"]["productDefinition"],
            {"length": 63.246, "width": 63.246, "height": 254.0},
        )

    def test_units_convert_allowances_without_changing_physical_value(self):
        inches = normalize_product_allowances((0.12, 0.12, 0.12), "in")
        millimetres = normalize_product_allowances((3.048, 3.048, 3.048), "mm")
        centimetres = normalize_product_allowances((0.3048, 0.3048, 0.3048), "cm")
        for left, right in zip(inches, millimetres):
            self.assertAlmostEqual(left, right, places=8)
        for left, right in zip(inches, centimetres):
            self.assertAlmostEqual(left, right, places=8)

    def test_catalogue_product_keeps_nominal_dimensions_and_applies_allowance(self):
        product = SimpleNamespace(
            product_length=63.246,
            product_width=63.246,
            product_height=254,
            rotation_1=False,
            rotation_2=False,
            rotation_3=True,
            desired_qty=24,
            weight=None,
        )
        data = _container_data(
            product_source="catalogue",
            product_l="",
            product_w="",
            product_h="",
            product_allowance_l="-0.12",
            product_allowance_w="0",
            product_allowance_h="0.12",
            # Catalogue dimensions are canonical mm, but the shared picker
            # keeps the active imperial display unit for the allowance fields.
            product_dimension_unit="in",
        )
        form = ContainerSelectionMode1Form(data=data)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        with TemporaryDirectory() as media_root:
            result = analyze_container_form(
                form,
                data,
                selected_product=product,
                media_root=media_root,
            )
        self.assertTrue(result["ok"], result["messages"])
        self.assertEqual(
            result["analysis_report"]["effective_product_dimensions_display"],
            "2.37 × 2.49 × 10.12 in",
        )
        self.assertEqual(result["product_unit_scene"]["productDefinition"],
                         {"length": 63.246, "width": 63.246, "height": 254.0})

    def test_workflow_inherited_dimensions_reset_allowance_to_prevent_double_counting(self):
        config = default_container_config()
        config.update({
            "product_l": "100",
            "product_w": "80",
            "product_h": "60",
            "product_allowance_l": "5",
            "product_allowance_w": "4",
            "product_allowance_h": "3",
        })
        updated = _apply_payload_to_config(
            config,
            "container",
            {"length": 420, "width": 320, "height": 250, "weight_g": 1000},
        )
        self.assertEqual(
            (updated["product_l"], updated["product_w"], updated["product_h"]),
            (420.0, 320.0, 250.0),
        )
        self.assertEqual(
            (updated["product_allowance_l"], updated["product_allowance_w"], updated["product_allowance_h"]),
            ("0", "0", "0"),
        )

    def test_invalid_allowance_values_are_rejected(self):
        for value in ("invalid", "NaN", "Infinity", "-Infinity"):
            form = ContainerSelectionMode1Form(data=_container_data(product_allowance_l=value))
            self.assertFalse(form.is_valid(), value)
            self.assertIn("product_allowance_l", form.errors)

        result = analyze_bag_config(
            _bag_config(product_allowance_l="-1"),
            "run_single",
        )
        self.assertIsNone(result["result"])
        self.assertTrue(any("allowances" in message for message in result["messages"]))

    def test_non_positive_or_non_finite_effective_dimensions_stop_all_entry_points(self):
        for mode, action in (("single", "run_single"), ("design", "run_design"), ("optimal", "find_top5")):
            for unit, nominal, allowance in (("in", "2.49", "-2.49"), ("in", "2.49", "-3"),
                                             ("in", "1e307", "1e307"), ("mm", "1e308", "1e308")):
                with self.subTest(mode=mode, nominal=nominal, allowance=allowance):
                    data = _container_data(mode=mode, action=action, product_dimension_unit=unit,
                                           product_l=nominal, product_allowance_l=allowance)
                    form = ContainerSelectionMode1Form(data)
                    self.assertTrue(form.is_valid(), form.errors)
                    for analyze in (analyze_container_form, analyze_container_capacity):
                        result = analyze(form, data)
                        self.assertFalse(result["ok"])
                        self.assertIsNone(result["result"])
                        self.assertTrue(any("dimensions" in message or "allowances" in message for message in result["messages"]))

    def test_signed_imperial_and_metric_allowances_preserve_geometry_and_rotation(self):
        configs = (
            _container_data(product_l="6", product_w="5", product_h="7",
                            product_allowance_l="-0.5", product_allowance_w="-0.5", product_allowance_h="-1"),
            _container_data(product_dimension_unit="mm", product_l="152.4", product_w="127", product_h="177.8",
                            product_allowance_l="-12.7", product_allowance_w="-12.7", product_allowance_h="-25.4"),
            _container_data(product_l="5.5", product_w="4.5", product_h="6"),
        )
        for data in configs:
            with self.subTest(data=data):
                form = ContainerSelectionMode1Form(data)
                self.assertTrue(form.is_valid(), form.errors)
                result = analyze_container_capacity(form, data)
                self.assertTrue(result["ok"], result["messages"])
                self.assertEqual(result["result"]["max_quantity"], 9)


class ProductDimensionalAllowanceUiTests(TestCase):
    def test_standalone_and_workflow_render_allowance_fields(self):
        for url in (
            reverse("container_selection_calculator"),
            reverse("bag_selection_calculator"),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Additional parameters")
            self.assertContains(response, "Show Advanced")
            self.assertContains(response, "Effective dimensions used for packing")
            self.assertContains(response, "product_allowance_l")

        self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "container"},
        )
        response = self.client.get(reverse("full_packaging_mode"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="product_allowance_l_0"')
        self.assertContains(response, 'id="productAdditionalParameters_0"')

    def test_signed_allowances_reach_design_in_standalone_and_workflow(self):
        data = _container_data(mode="design", action="run_design", desired_qty="16",
                               product_l="6", product_w="5", product_h="7",
                               product_allowance_l="-0.5", product_allowance_w="-0.5", product_allowance_h="-1",
                               product_shape="cylinder")
        data.pop("r1")
        data.pop("r2")
        standalone = self.client.post(reverse("container_selection_mode1"), data)
        flow_url = reverse("full_packaging_mode")
        self.client.post(flow_url, {"action": "add_step", "step_type": "container"})
        flow = self.client.post(flow_url, {**{f"{key}_0": value for key, value in data.items()},
                                          "action": "run_step", "index": "0"}, follow=True)
        for response, context, suffix in ((standalone, standalone.context, ""), (flow, flow.context["steps"][0], "_0")):
            with self.subTest(suffix=suffix):
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Positive allowances increase packing dimensions; negative allowances reduce them.")
                for axis in "lwh":
                    self.assertRegex(response.content.decode(), rf'<input\b(?=[^>]*name="product_allowance_{axis}{suffix}")(?![^>]*\bmin=)[^>]*>')
                report = context["analysis_report"]
                self.assertEqual(report["effective_product_dimensions_display"], "5.5 × 4.5 × 6 in")
                self.assertEqual(report["nominal_product_dimensions_display"], "6 × 5 × 7 in")
                self.assertAlmostEqual(context["product_unit_scene"]["productDefinition"]["length"], 152.4)
        self.assertEqual(
            [row["candidate_id"] for row in standalone.context["design_candidates"]],
            [row["candidate_id"] for row in flow.context["steps"][0]["design_candidates"]],
        )
