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
from packagingapp.tools.bag.service import analyze_bag_capacity
from packagingapp.utils.bag_selection.engine import (
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
