import base64
import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from PIL import Image

from packagingapp.models import (
    PackagingCatalogue,
    PackagingMaterial,
    Product,
    ProductCatalogue,
    UserSubscription,
)
from packagingapp.tools.bag.export import build_bag_selection_pdf
from packagingapp.tools.bag.service import analyze_bag_capacity, analyze_bag_config, format_bag_area
from packagingapp.utils.bag_selection.engine import (
    BagSizingParameters,
    bag_formula,
    build_bag_design_candidates,
    build_required_bag_options,
    compute_max_quantity_for_bag,
    required_bag_dimensions,
)


PRODUCT = (90, 60, 25)
PRODUCT_INPUTS = {
    "product_source": "manual",
    "bag_source": "manual",
    "product_l": 90,
    "product_w": 60,
    "product_h": 25,
    "desired_qty": 1,
}
# Candidate ID from the previous sizing rule for the (90, 25, 60) bundle.
SAVED_DESIGN_ID = "bag-design-27332e78c4d5db55"
HEIGHT_INSERTION = {
    "axis": "height",
    "depth": 25,
    "opening_axes": ["length", "width"],
    "opening_dimensions": [90, 60],
}
DESIGN_SHORT_INSERTION = {
    "axis": "width",
    "depth": 25,
    "opening_axes": ["length", "height"],
    "opening_dimensions": [60, 90],
}


class BagSizingEngineTests(SimpleTestCase):
    def test_configurable_allowances_preserve_reference_axes_and_design_identities(self):
        expected = [
            (BagSizingParameters(), [(87, 127), (117, 97), (152, 97)]),
            (BagSizingParameters(4, 15), [(89, 134), (119, 104), (154, 104)]),
            (BagSizingParameters(0, 0), [(85, 115), (115, 85), (150, 85)]),
        ]
        baseline = build_bag_design_candidates(*PRODUCT, 1)
        for assumptions, sizes in expected:
            with self.subTest(assumptions=assumptions):
                grid = build_required_bag_options(*PRODUCT, 1, parameters=assumptions)["solutions"][0]
                self.assertEqual([(row["req_w"], row["req_len"]) for row in grid["bag_options"]], sizes)
                self.assertEqual([row["insertion"]["axis"] for row in grid["bag_options"]], ["length", "width", "height"])
                design = build_bag_design_candidates(*PRODUCT, 1, parameters=assumptions)
                self.assertCountEqual([(row["bag_width"], row["bag_length"]) for row in design["candidates"]], sizes)
                self.assertEqual(
                    [row["candidate_id"] for row in design["candidates"]],
                    [row["candidate_id"] for row in baseline["candidates"]],
                )
                self.assertEqual(design["candidate_aliases"], baseline["candidate_aliases"])
                for row in design["candidates"]:
                    bag = row["render_data"]["bag"]
                    self.assertEqual(bag["fitTolerance"], assumptions.fit_tolerance_mm)
                    self.assertEqual(bag["sealingAllowance"], assumptions.sealing_allowance_mm)

    def test_required_dimensions_for_each_opening_plane(self):
        cases = [
            ((90, 60, 25), (127, 87, 11049)),
            ((90, 25, 60), (127, 87, 11049)),
            ((60, 25, 90), (97, 117, 11349)),
            ((25, 90, 60), (97, 152, 14744)),
            ((180, 25, 25), (217, 52, 11284)),
        ]
        for bundle, expected in cases:
            with self.subTest(bundle=bundle):
                length, width = required_bag_dimensions(*bundle)
                self.assertEqual((length, width, length * width), expected)
        expected = {(127, 87), (97, 117), (97, 152)}
        self.assertEqual(bag_formula(90, 25, 60), expected)
        self.assertEqual(bag_formula(*PRODUCT), expected)

    def test_selection_requirements_use_packed_grid_spans_for_all_three_axes(self):
        result = build_required_bag_options(*PRODUCT, 2)
        self.assertEqual(
            result["required"],
            [(152, 112), (122, 142), (157, 117), (122, 152), (127, 147), (217, 87), (97, 207), (97, 242), (127, 212)],
        )
        stacked = next(solution for solution in result["solutions"] if solution["layout"] == (1, 1, 2))
        self.assertEqual(stacked["bag_options"][2]["insertion"], {**HEIGHT_INSERTION, "depth": 50})
        for length, width, expected in [(127, 87, 1), (87, 127, 0), (152, 112, 2), (151, 112, 1), (97, 152, 1)]:
            with self.subTest(length=length, width=width):
                self.assertEqual(
                    compute_max_quantity_for_bag(*PRODUCT, length, width)["max_quantity"], expected
                )

    def test_reference_rotations_consolidate_to_three_sizes_and_keep_opening_planes(self):
        design = build_bag_design_candidates(*PRODUCT, 1)
        candidates = design["candidates"]
        expected = [
            ("length", 60, [25, 90], 117, 97, 11349),
            ("width", 25, [60, 90], 152, 97, 14744),
            ("height", 90, [60, 25], 87, 127, 11049),
        ]
        self.assertEqual(len(candidates), 3)
        self.assertEqual(len(design["candidate_aliases"]), 6)
        self.assertEqual(len({row["candidate_id"] for row in candidates}), 3)
        self.assertEqual(len({row["arrangement_id"] for row in candidates}), 1)
        self.assertEqual([row["rank"] for row in candidates], [1, 2, 3])
        self.assertEqual(build_bag_design_candidates(*PRODUCT, 1), design)
        for row, (axis, depth, opening, width, length, area) in zip(candidates, expected):
            self.assertEqual(row["insertion"]["axis"], axis)
            self.assertEqual(row["insertion"]["depth"], depth)
            self.assertEqual(row["insertion"]["opening_dimensions"], opening)
            self.assertEqual((row["bag_width"], row["bag_length"], row["bag_area"]), (width, length, area))
            scene = row["render_data"]
            self.assertEqual(scene["products"], candidates[0]["render_data"]["products"])
            self.assertEqual(scene["bag"]["insertion"], row["insertion"])
            self.assertEqual(scene["bag"]["film"], {"depthAxis": axis, "bundleDimensions": [60, 25, 90]})

    def test_design_sizes_every_arrangement_in_existing_cubicity_order(self):
        candidates = build_bag_design_candidates(*PRODUCT, 2)["candidates"]
        self.assertEqual(
            [
                (
                    (row["bundle_length"], row["bundle_width"], row["bundle_height"]),
                    (row["bag_length"], row["bag_width"], row["bag_area"]),
                )
                for row in candidates if row["insertion"]["axis"] == "length"
            ],
            [
                ((60, 50, 90), (122, 142, 17324)),
                ((90, 50, 60), (152, 112, 17024)),
                ((90, 60, 50), (152, 112, 17024)),
                ((90, 25, 120), (127, 147, 18669)),
                ((120, 25, 90), (157, 117, 18369)),
                ((120, 90, 25), (157, 117, 18369)),
                ((60, 25, 180), (97, 207, 20079)),
                ((180, 25, 60), (217, 87, 18879)),
                ((180, 60, 25), (217, 87, 18879)),
            ],
        )
        regular_grid = [
            row for row in candidates
            if (row["bundle_length"], row["bundle_width"], row["bundle_height"]) == (90, 60, 50)
        ]
        self.assertEqual(
            [(row["insertion"]["depth"], row["bag_length"], row["bag_width"]) for row in regular_grid],
            [(90, 152, 112), (60, 122, 142), (50, 122, 152)],
        )
        same_size = [row for row in candidates if (row["bag_width"], row["bag_length"]) == (112, 152)]
        self.assertEqual({row["bundle_height"] for row in same_size}, {50, 60, 90})
        self.assertEqual(len({row["arrangement_id"] for row in same_size}), 3)
        for row in same_size:
            self.assertEqual(len(row["render_data"]["products"]), 2)
            self.assertEqual(row["render_data"]["bag"]["film"]["bundleDimensions"], [
                row["bundle_length"], row["bundle_width"], row["bundle_height"],
            ])

    def test_equal_spans_keep_only_the_first_equivalent_insertion_axis(self):
        equal_sides = [
            row for row in build_bag_design_candidates(90, 25, 25, 2)["candidates"]
            if (row["bundle_length"], row["bundle_width"], row["bundle_height"]) == (180, 25, 25)
        ]
        self.assertEqual(
            [(row["insertion"]["axis"], row["bag_length"], row["bag_width"], row["bag_area"]) for row in equal_sides],
            [("length", 217, 52, 11284), ("width", 62, 207, 12834)],
        )
        cube = build_bag_design_candidates(25, 25, 25, 1)["candidates"]
        self.assertEqual([(row["insertion"]["axis"], row["bag_length"], row["bag_width"]) for row in cube], [
            ("length", 62, 52),
        ])
        rectangular = build_bag_design_candidates(90, 25, 25, 1)["candidates"]
        self.assertCountEqual([(row["bag_length"], row["bag_width"]) for row in rectangular], [
            (127, 52), (62, 117),
        ])
        for product, required in [((90, 25, 25), [(127, 52), (62, 117)]), ((25, 25, 25), [(62, 52)])]:
            with self.subTest(product=product):
                selection = build_required_bag_options(*product, 1)
                self.assertCountEqual(selection["required"], required)
                self.assertEqual(len(selection["solutions"][0]["bag_options"]), len(required))


class BagAreaFormattingTests(SimpleTestCase):
    def test_fixed_precision_and_invalid_areas(self):
        self.assertEqual(format_bag_area(10000, "mm"), {
            "bag_area_display": "100.00", "bag_area_unit": "cm²",
        })
        for value in (None, "", "invalid", float("inf"), float("nan"), -1):
            with self.subTest(value=value):
                self.assertEqual(format_bag_area(value, "in"), {
                    "bag_area_display": "—", "bag_area_unit": "in²",
                })


class BagSizingSurfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catalogue = PackagingCatalogue.objects.create(name="Lay-flat bags")
        cls.bags = {}
        sizes = [(127, 87), (97, 117), (97, 152), (128, 87), (98, 117), (99, 117), (130, 87), (87, 127), (154, 114)]
        for length, width in sizes:
            cls.bags[length, width] = PackagingMaterial.objects.create(
                catalogue=cls.catalogue,
                packaging_type="BAG",
                part_number=f"{length}x{width}",
                part_length=length,
                part_width=width,
                part_height=0,
            )
        cls.user = get_user_model().objects.create_user(username="bag-sizing")
        UserSubscription.objects.create(user=cls.user, plan=UserSubscription.Plan.PLUS)

    def post_bag(self, route="bag_selection_mode1", **inputs):
        response = self.client.post(reverse(route), {**PRODUCT_INPUTS, **inputs})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].errors)
        return response

    def test_design_area_uses_bag_dimension_unit_and_preserves_engine_results(self):
        expected_display = {
            "cm²": {11049: "110.49", 11349: "113.49", 14744: "147.44"},
            "in²": {11049: "17.13", 11349: "17.59", 14744: "22.85"},
        }
        engine = build_bag_design_candidates(*PRODUCT, 1)["candidates"]
        for length_unit, area_unit in (
            ("mm", "cm²"), ("cm", "cm²"), ("m", "cm²"), ("in", "in²"), ("ft", "in²"),
        ):
            with self.subTest(length_unit=length_unit):
                response = self.post_bag(mode="design", action="run_design", bag_dimension_unit=length_unit)
                self.assertContains(
                    response, f'<th>Bag W × L</th><th class="text-end text-nowrap">Bag area ({area_unit})</th>',
                )
                rows = response.context["design_candidates"]
                self.assertEqual([row["candidate_id"] for row in rows], [row["candidate_id"] for row in engine])
                self.assertEqual(response.context["result"]["candidate_id"], engine[0]["candidate_id"])
                for row, candidate in zip(rows, engine):
                    for key in ("bag_area", "bag_width", "bag_length", "design_quantity", "bag_usage", "rank"):
                        self.assertEqual(row[key], candidate[key], key)
                    display = expected_display[area_unit][row["bag_area"]]
                    self.assertEqual((row["bag_area_display"], row["bag_area_unit"]), (display, area_unit))
                    self.assertContains(response, f'<td class="text-end">{display}</td>', count=1, html=True)

    def test_custom_single_fit_capacity_utilization_and_report_use_the_same_values(self):
        custom = {"fit_tolerance": 4, "sealing_allowance": 15}
        original = self.post_bag(action="run_single", bag_length=154, bag_width=114)
        self.assertEqual(original.context["result"]["max_quantity"], 2)
        manual = self.post_bag(action="run_single", bag_length=154, bag_width=114, **custom)
        catalogue = self.post_bag(
            action="select_bag", bag_source="catalogue", catalogue_id=self.catalogue.pk,
            bag_id=self.bags[154, 114].pk, **custom,
        )
        for response in (manual, catalogue):
            result, report = response.context["result"], response.context["analysis_report"]
            self.assertTrue(result["fits"])
            self.assertEqual(result["best_required"], (134, 89))
            self.assertEqual((result["max_quantity"], report["max_quantity"]), (1, 1))
            self.assertAlmostEqual(result["usage"], (134 * 89) / (154 * 114))
            self.assertEqual(report["required_area_max"], 134 * 89)
            self.assertEqual(report["bag_assumptions"], result["bag_assumptions"])
            scene = response.context["threejs_scene"]["bag"]
            self.assertEqual((scene["fitTolerance"], scene["sealingAllowance"], scene["insertion"]["axis"]), (4, 15, "length"))
        no_fit = self.post_bag(action="run_single", bag_length=127, bag_width=87, **custom)
        self.assertFalse(no_fit.context["result"]["fits"])
        self.assertEqual(no_fit.context["analysis_report"]["max_quantity"], 0)
        switched = self.post_bag(action="run_single", bag_length=120, bag_width=155, fit_tolerance=0, sealing_allowance=0)
        old = self.post_bag(action="run_single", bag_length=120, bag_width=155)
        self.assertEqual(old.context["threejs_scene"]["bag"]["insertion"]["axis"], "height")
        self.assertEqual(switched.context["threejs_scene"]["bag"]["insertion"]["axis"], "length")

    def test_custom_optimal_top_five_use_current_allowances_and_keep_them_when_selected(self):
        for length, width in [(134, 89), (104, 119), (104, 154), (135, 89), (105, 119)]:
            PackagingMaterial.objects.create(
                catalogue=self.catalogue, packaging_type="BAG", part_number=f"{length}x{width}",
                part_length=length, part_width=width, part_height=0,
            )
        config = {
            "mode": "optimal", "bag_source": "catalogue", "catalogue_id": self.catalogue.pk,
            "fit_tolerance": 4, "sealing_allowance": 15,
        }
        route = "bag_selection_calculator"
        optimal = self.post_bag(route=route, action="find_top5", **config)
        rows = optimal.context["top5"]
        self.assertEqual([row["part_number"] for row in rows], ["134x89", "104x119", "104x154", "135x89", "105x119"])
        self.assertEqual([row["best_required"] for row in rows], [(134, 89), (104, 119), (104, 154), (134, 89), (104, 119)])
        self.assertTrue(all(row["bag_assumptions"]["sealing_allowance_mm"] == 15 for row in rows))
        self.assertContains(optimal, "Sealing allowance: 15 mm")
        selected = self.post_bag(route=route, action="select_candidate", bag_id=rows[2]["id"], **config)
        self.assertEqual(selected.context["threejs_scene"]["bag"]["insertion"], HEIGHT_INSERTION)
        self.assertEqual(selected.context["threejs_scene"]["bag"]["fitTolerance"], 4)
        saved = self.client.session["bag_selection_optimal_export"]
        self.assertEqual(saved["analysis_report"]["bag_assumptions"]["fit_tolerance_display"], "4 mm")

    def test_custom_design_values_survive_product_selection_mode_changes_and_candidate_selection(self):
        products = ProductCatalogue.objects.create(name="Reference products")
        product = Product.objects.create(
            catalogue=products, product_id="reference", product_length=90, product_width=60, product_height=25,
        )
        config = {
            "product_source": "catalogue", "product_catalogue_id": products.pk, "selected_product_id": product.pk,
            "fit_tolerance": 4.125, "sealing_allowance": 15.25,
        }
        for mode in ("single", "optimal", "design"):
            response = self.post_bag(mode=mode, action="select_product", **config)
            self.assertEqual(response.context["form"]["fit_tolerance"].value(), "4.125")
            self.assertEqual(response.context["form"]["sealing_allowance"].value(), "15.25")
            self.assertContains(response, "bagPackagingDimensionUnitMenu-sealing-allowance")
        generated = self.post_bag(mode="design", action="run_design", **config)
        self.assertEqual(len(generated.context["design_candidates"]), 3)
        candidate = next(row for row in generated.context["design_candidates"] if row["insertion"]["depth"] == 90)
        selected = self.post_bag(
            mode="design", action="select_design_candidate", selected_design_candidate_id=candidate["candidate_id"], **config,
        )
        self.assertEqual(selected.context["result"]["candidate_id"], candidate["candidate_id"])
        self.assertEqual(selected.context["threejs_scene"]["bag"]["flatLength"], 134.375)
        self.assertEqual(selected.context["threejs_scene"]["bag"]["flatWidth"], 89.125)
        self.assertEqual(self.client.session["bag_selection_design_export"]["analysis_report"]["bag_assumptions"], {
            "fit_tolerance_mm": 4.125, "fit_tolerance_display": "4.125 mm",
            "sealing_allowance_mm": 15.25, "sealing_allowance_display": "15.25 mm",
        })

    def test_invalid_allowances_are_rejected_before_the_packing_engine(self):
        for field in ("sealing_allowance", "fit_tolerance"):
            for value in ("", "-0.1", "NaN", "Infinity", "bad"):
                with self.subTest(field=field, value=value), patch(
                    "packagingapp.tools.bag.service.build_bag_design_candidates"
                ) as engine:
                    config = {**PRODUCT_INPUTS, "mode": "design", "action": "run_design", field: value}
                    response = self.client.post(reverse("bag_selection_mode1"), config)
                    self.assertIn(field, response.context["form"].errors)
                    self.assertIsNone(response.context["result"])
                    self.assertTrue(analyze_bag_config(config, "run_design")["messages"])
                    self.assertFalse(analyze_bag_capacity(config)["ok"])
                    engine.assert_not_called()

    def test_pdf_exports_include_custom_assumptions_and_the_current_snapshot(self):
        self.client.force_login(self.user)
        png = BytesIO()
        Image.new("RGB", (32, 32)).save(png, format="PNG")
        snapshot = "data:image/png;base64," + base64.b64encode(png.getvalue()).decode("ascii")
        modes = {
            "single": {"action": "run_single", "bag_length": 15.4, "bag_width": 11.4},
            "optimal": {
                "action": "select_candidate", "bag_source": "catalogue",
                "catalogue_id": self.catalogue.pk, "bag_id": self.bags[154, 114].pk,
            },
            "design": {"action": "run_design"},
        }
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root), patch(
            "reportlab.rl_config.pageCompression", 0
        ):
            for mode, inputs in modes.items():
                with self.subTest(mode=mode):
                    self.post_bag(
                        mode=mode, fit_tolerance="0.4", sealing_allowance="1.5",
                        bag_dimension_unit="cm", **inputs,
                    )
                    route = "bag_selection_export_optimal_pdf" if mode == "optimal" else "bag_selection_export_pdf"
                    pdf = self.client.post(reverse(route), {f"{mode}_export": "1", "threejs_snapshot": snapshot})
                    self.assertEqual(pdf.status_code, 200)
                    self.assertEqual(pdf["Content-Type"], "application/pdf")
                    for text in (b"Sealing allowance", b"1.5 cm", b"Fit tolerance", b"0.4 cm", b"/Subtype /Image"):
                        self.assertIn(text, pdf.content)

    def test_single_manual_catalogue_and_capacity_agree_on_required_area(self):
        bag = self.bags[154, 114]
        manual = self.post_bag(mode="single", action="run_single", bag_length=154, bag_width=114)
        catalogue = self.post_bag(
            mode="single", action="select_bag", bag_source="catalogue",
            catalogue_id=self.catalogue.pk, bag_id=bag.pk,
        )
        for response in (manual, catalogue):
            result = response.context["result"]
            report = response.context["analysis_report"]
            self.assertEqual(result["max_quantity"], 2)
            self.assertEqual(result["best_required"], (152, 112))
            self.assertAlmostEqual(result["usage"], 17024 / 17556)
            self.assertEqual((report["required_area_current"], report["required_area_max"]), (17024, 17024))
            self.assertEqual((report["bag_area"], report["bag_usage_current_display"]), (17556, "97%"))
        self.assertEqual(self.client.session["bag_selection_single_export"]["analysis_report"], report)
        capacity = analyze_bag_capacity(manual.context["bag_config"])["pending_result"]
        self.assertEqual(capacity["units_per_parent"], 2)
        self.assertEqual((capacity["length"], capacity["width"], capacity["height"]), (92, 62, 50))

    def test_single_selects_third_insertion_with_manual_catalogue_and_equivalent_units(self):
        bag = self.bags[97, 152]
        variants = [
            {"action": "run_single", "bag_length": 97, "bag_width": 152},
            {
                "action": "select_bag", "bag_source": "catalogue",
                "catalogue_id": self.catalogue.pk, "bag_id": bag.pk,
            },
            {
                "action": "run_single", "product_dimension_unit": "cm", "bag_dimension_unit": "cm",
                "product_l": 9, "product_w": 6, "product_h": 2.5, "bag_length": 9.7, "bag_width": 15.2,
            },
        ]
        for inputs in variants:
            with self.subTest(inputs=inputs):
                response = self.post_bag(mode="single", **inputs)
                result = response.context["result"]
                self.assertEqual((result["max_quantity"], result["best_required"], result["usage"]), (1, (97, 152), 1.0))
                self.assertEqual(response.context["threejs_scene"]["bag"]["insertion"], HEIGHT_INSERTION)
                self.assertEqual(response.context["threejs_scene"]["bag"]["film"], {
                    "depthAxis": "length", "bundleDimensions": [25, 90, 60],
                })
                capacity = analyze_bag_capacity(response.context["bag_config"], selected_material=bag)["pending_result"]
                self.assertEqual(capacity["insertion"], HEIGHT_INSERTION)
                self.assertEqual(tuple(capacity[axis] for axis in ("length", "width", "height")), (25, 90, 60))

    def test_optimal_catalogue_top_five_and_public_selection_respect_bag_axes(self):
        config = {"mode": "optimal", "bag_source": "catalogue", "catalogue_id": self.catalogue.pk}
        optimal = self.post_bag(action="find_top5", **config)
        self.assertEqual(
            [(row["bag_len"], row["bag_w"]) for row in optimal.context["top5"]],
            [(127, 87), (97, 117), (97, 152), (128, 87), (98, 117)],
        )
        for unit, header, displays in (
            ("mm", "cm²", ["110.49", "113.49", "147.44", "111.36", "114.66"]),
            ("in", "in²", ["17.13", "17.59", "22.85", "17.26", "17.77"]),
        ):
            with self.subTest(unit=unit):
                response = optimal if unit == "mm" else self.post_bag(
                    route="bag_selection_calculator", action="find_top5", bag_dimension_unit=unit, **config,
                )
                self.assertRegex(
                    response.content.decode(),
                    rf'<th>Bag dimensions</th>\s*<th class="text-end text-nowrap">Bag area \({header}\)</th>',
                )
                rows = response.context["top5"]
                self.assertEqual([row["bag_area"] for row in rows], [11049, 11349, 14744, 11136, 11466])
                self.assertEqual([row["bag_area_display"] for row in rows], displays)
                for key in ("id", "usage", "best_required"):
                    self.assertEqual([row[key] for row in rows], [row[key] for row in optimal.context["top5"]])
                for display in displays:
                    self.assertContains(response, f'<td class="text-end">{display}</td>', count=1, html=True)
        bag = self.bags[98, 117]
        selected = self.post_bag(
            route="bag_selection_calculator", action="select_candidate", bag_id=bag.pk, **config
        )
        self.assertEqual(selected.context["result"]["best_required"], (97, 117))
        self.assertAlmostEqual(selected.context["result"]["usage"], 11349 / 11466)
        self.assertEqual(selected.context["analysis_report"]["required_area"], 11349)
        self.assertEqual(selected.context["threejs_scene"]["selectedRequiredBag"], {"length": 97, "width": 117})
        export = self.client.session["bag_selection_optimal_export"]
        self.assertEqual(export["selected_candidate"]["part_number"], "98x117")
        self.assertEqual(export["analysis_report"]["required_area"], 11349)
        third = self.post_bag(action="select_candidate", bag_id=self.bags[97, 152].pk, **config)
        self.assertEqual(third.context["result"]["best_required"], (97, 152))
        self.assertEqual(third.context["result"]["usage"], 1.0)
        self.assertEqual(third.context["threejs_scene"]["bag"]["insertion"], HEIGHT_INSERTION)
        self.assertEqual(self.client.session["bag_selection_optimal_export"]["analysis_report"]["required_area"], 14744)

    def test_saved_design_selection_preserves_corrected_dimensions_in_pdf_payload(self):
        self.client.force_login(self.user)
        response = self.post_bag(mode="design", action="select_design_candidate", selected_design_candidate_id=SAVED_DESIGN_ID)
        self.assertContains(response, "117 × 97 mm")
        self.assertContains(response, "87 × 127 mm")
        row = response.context["result"]
        design = build_bag_design_candidates(*PRODUCT, 1)
        self.assertEqual(row["candidate_id"], design["candidate_aliases"][SAVED_DESIGN_ID])
        self.assertEqual((row["bundle_length"], row["bundle_width"], row["bundle_height"]), (60, 25, 90))
        self.assertEqual(row["insertion"]["depth"], 90)
        capacity = analyze_bag_capacity({
            **response.context["bag_config"], "selected_design_candidate_id": SAVED_DESIGN_ID,
        })
        self.assertEqual(capacity["selected_design_candidate_id"], row["candidate_id"])
        self.assertEqual((row["bag_width"], row["bag_length"], row["bag_area"], row["bag_usage"]), (87, 127, 11049, 1))
        scene = response.context["threejs_scene"]["bag"]
        self.assertEqual((scene["flatWidth"], scene["flatLength"]), (87, 127))
        saved = self.client.session["bag_selection_design_export"]
        json.dumps(saved, allow_nan=False)
        self.assertEqual(saved["selected_candidate"]["candidate_id"], row["candidate_id"])
        self.assertEqual(saved["bag"]["dimensions"], "87 × 127 mm")
        self.assertEqual(saved["analysis_report"]["bag_area"], 11049)

        third = next(
            row for row in response.context["design_candidates"]
            if row["insertion"]["depth"] == 25
        )
        selected = self.post_bag(mode="design", action="select_design_candidate", selected_design_candidate_id=third["candidate_id"])
        self.assertEqual(selected.context["result"]["candidate_id"], third["candidate_id"])
        self.assertEqual(selected.context["threejs_scene"]["bag"]["insertion"], DESIGN_SHORT_INSERTION)
        json.dumps(self.client.session["bag_selection_design_export"], allow_nan=False)

        image = BytesIO()
        Image.new("RGB", (32, 32)).save(image, format="PNG")
        snapshot = "data:image/png;base64," + base64.b64encode(image.getvalue()).decode("ascii")
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root), patch(
            "packagingapp.views.bag_selection.build_bag_selection_pdf", wraps=build_bag_selection_pdf,
        ) as build_pdf:
            pdf = self.client.post(reverse("bag_selection_export_pdf"), {
                "design_export": "1", "threejs_snapshot": snapshot,
            })
            self.assertEqual(pdf.status_code, 200)
            self.assertEqual(pdf["Content-Type"], "application/pdf")
            self.assertTrue(pdf.content.startswith(b"%PDF-"))
            payload = build_pdf.call_args.args[0]
            self.assertTrue((Path(media_root) / payload["threejs_snapshot_rel_path"]).is_file())
            self.assertEqual(payload["bag"]["dimensions"], "152 × 97 mm")
            self.assertEqual(payload["analysis_report"]["bag_area"], 14744)
            self.assertEqual(payload["selected_candidate"]["insertion"], DESIGN_SHORT_INSERTION)

    def test_multi_product_catalogue_applies_the_same_fit_to_each_product(self):
        products = ProductCatalogue.objects.create(name="Lay-flat products")
        reference = Product.objects.create(
            catalogue=products, product_id="reference", product_length=90, product_width=60, product_height=25,
        )
        filters = {"product_catalogue_id": products.pk, "packaging_catalogue_id": self.catalogue.pk}
        run_url = reverse("multi_product_bag_run")
        single = self.client.post(run_url, filters).json()["results"]
        self.assertEqual(single[0]["top5"][0]["best_required"], [127, 87])
        doubled = Product.objects.create(
            catalogue=products, product_id="doubled", product_length=90, product_width=60, product_height=25,
            desired_qty=2,
        )
        results = {
            row["product"]["id"]: row["top5"]
            for row in self.client.post(run_url, filters).json()["results"]
        }
        self.assertEqual(results[reference.pk], single[0]["top5"])
        self.assertEqual(results[reference.pk][2]["best_required"], [97, 152])
        draw = self.client.post(reverse("multi_product_bag_draw"), {
            "product_id": reference.pk, "bag_id": self.bags[97, 152].pk,
        }).json()
        self.assertEqual(draw["threejs_scene"]["bag"]["insertion"], HEIGHT_INSERTION)
        self.assertEqual(draw["threejs_scene"]["bag"]["film"], {
            "depthAxis": "length", "bundleDimensions": [25, 90, 60],
        })
        self.assertEqual(len(results[doubled.pk]), 1)
        self.assertEqual(results[doubled.pk][0]["best_required"], [152, 112])
        self.assertAlmostEqual(results[doubled.pk][0]["usage"], 17024 / 17556)
