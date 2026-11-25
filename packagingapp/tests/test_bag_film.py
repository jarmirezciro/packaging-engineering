from decimal import Decimal
from itertools import product as cartesian_product
import json
import re
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.test.html import parse_html
from django.urls import reverse

from packagingapp.forms import PackagingMaterialForm
from packagingapp.models import PackagingCatalogue, PackagingMaterial
from packagingapp.tools.bag.dimensions import resolve_bag_outer_dimensions
from packagingapp.tools.bag.film import FILM_PRESETS, resolve_bag_film
from packagingapp.tools.bag.service import analyze_bag_capacity, analyze_bag_config, format_bag_weight
from packagingapp.tools.bag.workflow import attach_bag_workflow_weight
from packagingapp.units import convert_film_thickness, format_dimensions
from packagingapp.utils.bag_selection.engine import build_required_bag_options, run_bag_mode1_and_render


class BagFilmTests(SimpleTestCase):
    def test_candidate_weight_formatting_keeps_precision_and_handles_unavailable_tare(self):
        for selected_unit, unit, value in (
            ("g", "g", "0.620"), ("kg", "g", "0.620"), ("t", "g", "0.620"),
            ("oz", "oz", "0.0219"), ("lb", "oz", "0.0219"),
        ):
            with self.subTest(selected_unit=selected_unit):
                self.assertEqual(format_bag_weight(0.6196632768, selected_unit), {
                    "bag_weight_display": value, "bag_weight_unit": unit,
                })
        for weight in (None, "", "NaN", "Infinity", "invalid", -1, 0):
            self.assertEqual(format_bag_weight(weight, "g")["bag_weight_display"], "—")
        self.assertEqual(format_bag_weight(0.000001, "g")["bag_weight_display"], "<0.001")
        self.assertEqual(format_bag_weight(0.000001, "lb")["bag_weight_display"], "<0.0001")

    def test_presets_and_film_units(self):
        expected = {
            "ldpe_1": (25.4, 23.368), "ldpe_1_2": (30.48, 28.0416),
            "ldpe_1_5": (38.1, 35.052), "ldpe_2": (50.8, 46.736),
            "ldpe_3": (76.2, 70.104), "pp_20": (20, 18),
            "pp_25": (25, 22.5), "pp_30": (30, 27),
            "pp_40": (40, 36), "pp_50": (50, 45),
        }
        self.assertEqual(set(FILM_PRESETS), set(expected))
        for preset, (microns, grammage) in expected.items():
            with self.subTest(preset=preset):
                film = resolve_bag_film({"film_preset": preset})
                self.assertAlmostEqual(film["film_caliper_mm"] * 1000, microns)
                self.assertEqual(film["film_grammage_g_m2"], grammage)
        millimetres = convert_film_thickness(Decimal("1.2"), "mil", "mm")
        self.assertEqual(millimetres, Decimal("0.03048"))
        self.assertEqual(convert_film_thickness(millimetres, "mm", "um"), Decimal("30.48"))
        self.assertEqual(convert_film_thickness(Decimal("30.48"), "um", "mil"), Decimal("1.2"))

    def test_reference_tare_and_outer_dimensions(self):
        film = resolve_bag_film({}, (127, 87))
        self.assertEqual(film["film_area_m2"], 0.022098)
        self.assertEqual(film["bag_tare_g"], 0.6196632768)
        self.assertEqual(film["bag_tare_display"], "0.620 g")
        dims = resolve_bag_outer_dimensions((127, 87), (90, 60, 25), film)
        self.assertEqual(tuple(dims[f"external_{axis}_mm"] for axis in ("length", "width", "height")),
                         (90.06096, 60.06096, 25.06096))
        self.assertEqual(dims["outer_dimension_source"], "tight_fit_film_estimate")

    def test_custom_and_invalid_values(self):
        config = {"film_preset": "custom", "film_caliper": "32", "film_caliper_unit": "um",
                  "film_grammage": "40"}
        self.assertEqual(resolve_bag_film(config)["film_grammage_g_m2"], 40)
        for value in ("", "0", "-1", "NaN", "Infinity", "invalid", "1e1000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_bag_film({**config, "film_grammage": value})
        for override in ({"film_caliper_unit": "cm"}, {"film_preset": "unknown"}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                resolve_bag_film({**config, **override})
        film = resolve_bag_film({"film_caliper_override": "1", "film_caliper": "2"})
        self.assertEqual(film["film_grammage_g_m2"], 46.736)

    def test_catalogue_precedence_and_construction(self):
        cfg = {"bag_source": "catalogue", "bag_weight": "0.8"}
        bag = SimpleNamespace(bag_film_family="ldpe", bag_construction="two_wall",
                              bag_film_caliper_mm=Decimal("0.03048"), combined_grammage_g_m2=Decimal("28.0416"),
                              bag_actual_weight_g=Decimal("0.7"), part_weight=Decimal("0.001"))
        self.assertEqual(resolve_bag_film(cfg, (127, 87), bag)["bag_tare_g"], 0.7)
        self.assertEqual(resolve_bag_film({**cfg, "bag_weight_override": "1"}, (127, 87), bag)["bag_tare_g"], 0.8)
        bag.bag_actual_weight_g = None
        self.assertEqual(resolve_bag_film(cfg, (127, 87), bag)["bag_tare_g"], 1)
        bag.part_weight = None
        self.assertEqual(resolve_bag_film(cfg, (127, 87), bag)["bag_tare_g"], 0.6196632768)
        bag.bag_construction = "other"
        self.assertIsNone(resolve_bag_film(cfg, (127, 87), bag)["bag_tare_g"])
        self.assertIsNone(resolve_bag_film(cfg, (127, 87), SimpleNamespace())["film_caliper_mm"])

    def test_weight_status_when_content_or_tare_is_missing(self):
        for net, tare, upstream, expected in (
            (None, 0.62, None, "unknown"),
            (20, None, None, "net_only"),
            (20, 0.62, {"weight_status": "net_only"}, "unknown"),
        ):
            with self.subTest(net=net, tare=tare, upstream=upstream):
                payload = attach_bag_workflow_weight(
                    {}, {"net_content_weight_g": net, "bag_tare_g": tare}, upstream=upstream
                )
                self.assertEqual(payload["weight_status"], expected)
                self.assertEqual(payload.get("weight_g"), net if expected == "net_only" else None)
                self.assertIsNone(payload["gross_bag_weight_g"])

    def test_design_estimates_each_candidate_using_its_own_flat_stock(self):
        config = {"mode": "design", "product_l": 90, "product_w": 60, "product_h": 25, "product_weight": 50}
        analysis = analyze_bag_config(config, "run_design")
        candidates = analysis["design_candidates"]
        self.assertEqual(len({row["bag_tare_g"] for row in candidates}), 3)
        for row in candidates:
            with self.subTest(candidate=row["candidate_id"]):
                self.assertAlmostEqual(row["bag_tare_g"], row["bag_area"] * 2e-6 * 28.0416)
                selected = analyze_bag_capacity({**config, "selected_design_candidate_id": row["candidate_id"]})
                output = selected["pending_result"]
                self.assertEqual(output["bag_tare_g"], row["bag_tare_g"])
                self.assertEqual(output["gross_bag_weight_g"], 50 + row["bag_tare_g"])
                self.assertAlmostEqual(output["external_height_mm"], output["bundle_height_mm"] + 0.06096)

    def test_multi_item_capacity_uses_complete_grid_beyond_render_limit(self):
        config = {
            "mode": "optimal", "catalogue_id": "1", "product_l": "10.12345",
            "product_w": 10, "product_h": 10, "desired_qty": 300,
        }
        material = SimpleNamespace(
            id=1, part_number="300", part_description="", branding="", part_length=300, part_width=300,
            bag_film_family="pp", bag_film_caliper_mm=0.03, bag_construction="two_wall",
        )
        rendered = analyze_bag_config(config, "select_candidate", selected_material=material)
        capacity = analyze_bag_capacity(config, selected_material=material)
        self.assertEqual(len(rendered["threejs_scene"]["products"]), 250)
        self.assertEqual(rendered["pending_result"]["units_per_parent"], 300)
        for axis in ("length", "width", "height"):
            self.assertEqual(rendered["pending_result"][axis], capacity["pending_result"][axis])
        bundle = rendered["pending_result"]
        self.assertAlmostEqual(
            bundle["bundle_length_mm"] * bundle["bundle_width_mm"] * bundle["bundle_height_mm"],
            300 * 10.12345 * 10 * 10,
        )


class StockBagEnvelopeTests(SimpleTestCase):
    def stock_material(self, length, width):
        return SimpleNamespace(
            id=1, part_number="Stock", part_description="", branding="", part_length=length, part_width=width,
        )

    def analyze_stock(self, mode, product, stock, quantity, **allowances):
        config = dict(zip(("product_l", "product_w", "product_h"), product), mode=mode, **allowances)
        length, width = stock
        if mode == "single":
            return analyze_bag_config({**config, "bag_length": length, "bag_width": width}, "run_single")
        material = self.stock_material(length, width)
        config.update(catalogue_id="1", bag_source="catalogue", bag_id="1", desired_qty=quantity)
        return analyze_bag_config(config, "select_candidate", selected_material=material, materials=[material])

    def test_demo_stock_bags_keep_capacity_usage_and_authoritative_grid(self):
        # Layout is in original product axes. Placements are in bag L, W, H.
        fixtures = (
            ((45, 35, 190), (350, 200), 6, 82.18, (190, 105, 90), (248, 108, 90), (2, 3, 1), (190, 35, 45), 4),
            ((130, 50, 18), (220, 160), 6, 87.27, (130, 108, 50), (158, 108, 50), (1, 1, 6), (130, 18, 50), 1),
            ((130, 50, 18), (240, 180), 8, 86.19, (130, 100, 72), (156, 106, 72), (1, 2, 4), (130, 50, 18), 0),
            ((130, 50, 18), (260, 200), 10, 85.66, (130, 100, 90), (158, 108, 90), (1, 2, 5), (130, 50, 18), 0),
            ((130, 50, 18), (300, 200), 12, 84.33, (216, 130, 50), (238, 148, 50), (1, 1, 12), (18, 130, 50), 5),
            ((130, 50, 18), (320, 230), 20, 91.09, (200, 130, 90), (218, 138, 90), (1, 4, 5), (50, 130, 18), 2),
        )
        for product, stock, qty, usage, bundle, envelope, layout, unit, orientation in fixtures:
            for mode, quantity_key in (("single", "max_quantity"), ("optimal", "desired_qty")):
                with self.subTest(stock=stock, mode=mode):
                    analysis = self.analyze_stock(mode, product, stock, qty, fit_tolerance=2, sealing_allowance=10)
                    result = analysis["result"]
                    scene = analysis["threejs_scene"]
                    bag = scene["bag"]
                    self.assertEqual(result[quantity_key], qty)
                    self.assertEqual(result["usage_pct"], usage)
                    self.assertEqual((bag["flatLength"], bag["flatWidth"]), stock)
                    self.assertEqual(bag["film"], {
                        "depthAxis": "length", "bundleDimensions": list(bundle), "envelopeDimensions": list(envelope),
                    })
                    self.assertEqual(scene["usedLayout"], list(layout))
                    required = scene["selectedRequiredBag"]
                    self.assertEqual((required["length"], required["width"]), result["best_required"])
                    self.assertEqual(len(scene["products"]), qty)
                    origins = set()
                    for item in scene["products"]:
                        self.assertEqual((item["dx"], item["dy"], item["dz"]), unit)
                        self.assertEqual(item["orientationIndex"], orientation)
                        origin = tuple(item[axis] for axis in "xyz")
                        origins.add(origin)
                        for start, size, limit in zip(origin, unit, envelope):
                            self.assertLessEqual(start + size, limit)
                    self.assertEqual(origins, set(cartesian_product(*(
                        range(0, span, size) for span, size in zip(bundle, unit)
                    ))))
                    json.dumps(scene, allow_nan=False)

    def test_exact_fit_uses_zero_and_fractional_allowances_in_both_modes(self):
        for tolerance, seal in ((0, 0), (0, 15.1), (4.25, 0), (4.25, 13.5)):
            for mode in ("single", "optimal"):
                with self.subTest(mode=mode, tolerance=tolerance, seal=seal):
                    stock = (115 + tolerance + seal, 85 + tolerance)
                    analysis = self.analyze_stock(
                        mode, (90, 60, 25), stock, 1, fit_tolerance=tolerance, sealing_allowance=seal,
                    )
                    bag = analysis["threejs_scene"]["bag"]
                    self.assertEqual((bag["fitTolerance"], bag["sealingAllowance"]), (tolerance, seal))
                    self.assertEqual(bag["film"]["envelopeDimensions"], [90, 60, 25])
                    self.assertEqual(bag["film"]["bundleDimensions"], [90, 60, 25])
                    self.assertEqual(analysis["result"]["usage_pct"], 100)

    def test_larger_catalogue_stock_keeps_the_same_selected_grid(self):
        smaller, larger = (
            self.analyze_stock("optimal", (130, 50, 18), stock, 12)["threejs_scene"]
            for stock in ((300, 200), (307, 205))
        )
        for field in ("products", "selectedRequiredBag", "usedLayout"):
            self.assertEqual(smaller[field], larger[field])
        self.assertEqual(smaller["bag"]["insertion"], larger["bag"]["insertion"])
        self.assertEqual(smaller["bag"]["film"]["envelopeDimensions"], [238, 148, 50])
        self.assertEqual(larger["bag"]["film"]["envelopeDimensions"], [245, 153, 50])

    def test_inconsistent_selected_bundle_is_rejected_without_clamping(self):
        product = (90, 60, 25)
        solutions = build_required_bag_options(*product, 1)["solutions"]
        for solution in solutions:
            for option in solution["bag_options"]:
                length, width, height = option["body_box"]
                option["body_box"] = length + 1, width, height
        with self.assertRaisesRegex(ValueError, "usable envelope does not contain"):
            run_bag_mode1_and_render(product, (127, 87), 1, solutions, "", selected_required_bag=(127, 87))


class BagFilmSurfaceTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user(username="film"))
        self.catalogue = PackagingCatalogue.objects.create(name="Film stock", is_public=True)

    def bag_result_details(self, response):
        html = response.content.decode()
        pattern = r'<details([^>]*)>\s*<summary[^>]*>\s*<strong>Detailed analysis</strong>.*?</details>'
        sections = []
        for match in re.finditer(pattern, html, re.S):
            self.assertNotIn("open", match[1])
            start = html.rindex('<div class="app-section-title">', 0, match.start())
            summary = html[start:match.start()]
            self.assertIn("Interactive 3D result", summary)
            for label in ("Film material", "Estimated film area", "Packaging weight source", "Outer dimensions source"):
                self.assertNotIn(label, summary)
            tbody = re.search(r"<tbody>.*?</tbody>", match[0], re.S)[0]
            rows = parse_html(tbody).children
            self.assertTrue(all(row.name == "tr" for row in rows))
            labels = [row.children[0].children[0] for row in rows]
            self.assertEqual(len(labels), len(set(labels)))
            sections.append((summary, dict(zip(labels, (row.children[1].children[0] for row in rows)))))
        return sections

    def test_single_and_design_disclosures_use_the_selected_results(self):
        product = {
            "product_source": "manual", "bag_source": "manual", "desired_qty": 1,
            "product_l": 90, "product_w": 60, "product_h": 25, "product_weight": 100,
        }
        single = self.client.post(reverse("bag_selection_calculator"), {
            **product, "mode": "single", "action": "run_single", "bag_length": 127, "bag_width": 87,
        })
        self.assertFalse(single.context["form"].errors)
        (summary, rows), = self.bag_result_details(single)
        self.assertIn("Total weight", summary)
        self.assertIn("100.62 g", summary)
        self.assertEqual(rows["Total weight"], "100.62 g")
        self.assertEqual(rows["Packaging weight"], "0.620 g")
        self.assertEqual(rows["Packaging weight source"], "Estimated from film properties")
        self.assertEqual(rows["Sealing allowance"], "10 mm")
        self.assertEqual(rows["Fit tolerance"], "2 mm")
        self.assertEqual(rows["Film material"], "LDPE")
        self.assertEqual(rows["Caliper"], "1.2 mil (30.48 µm)")
        self.assertEqual(rows["Grammage"], "28.04 g/m²")
        self.assertEqual(rows["Estimated film area"], "220.98 cm²")

        url = reverse("bag_selection_mode1")
        design_config = {**product, "mode": "design"}
        initial = self.client.post(url, {**design_config, "action": "run_design"})
        alternatives = initial.context["design_candidates"]
        chosen = alternatives[-1]
        selected = self.client.post(url, {
            **design_config, "action": "select_design_candidate", "selected_design_candidate_id": chosen["candidate_id"],
        })
        (design_summary, design_rows), = self.bag_result_details(selected)
        self.assertIn("Designed bag", design_summary)
        self.assertIn("Bundle:", design_summary)
        self.assertNotIn("Total weight", design_summary)
        self.assertNotIn("Sealing allowance", design_summary)
        self.assertEqual(design_rows["Net contents weight"], "100 g")
        self.assertEqual(design_rows["Total weight"], chosen["total_weight_display"])
        self.assertEqual(design_rows["Packaging weight"], chosen["bag_tare_display"])
        self.assertNotEqual(design_rows["Packaging weight"], self.bag_result_details(initial)[0][1]["Packaging weight"])

    def test_optimal_disclosure_distinguishes_actual_weight_and_unknown_film(self):
        actual = PackagingMaterial.objects.create(
            catalogue=self.catalogue, packaging_type="BAG", part_number="FILM",
            part_length=127, part_width=87, part_height=0, bag_film_family="pp",
            bag_film_caliper_mm=Decimal("0.03"), bag_construction="two_wall",
            bag_actual_weight_g=Decimal("0.729"),
        )
        unknown = PackagingMaterial.objects.create(
            catalogue=self.catalogue, packaging_type="BAG", part_number="UNKNOWN",
            part_length=128, part_width=87, part_height=0,
        )
        estimated = PackagingMaterial.objects.create(
            catalogue=self.catalogue, packaging_type="BAG", part_number="ESTIMATE",
            part_length=97, part_width=117, part_height=0, bag_film_family="ldpe",
            bag_film_caliper_mm=Decimal("0.03048"), bag_construction="two_wall",
        )
        url = reverse("bag_selection_mode1")
        inputs = {
            "mode": "optimal", "action": "select_candidate", "bag_source": "catalogue",
            "catalogue_id": self.catalogue.pk, "desired_qty": 1,
            "product_source": "manual", "product_l": 90, "product_w": 60,
            "product_h": 25, "product_weight": 100,
        }
        selected = self.client.post(url, {**inputs, "bag_id": actual.pk})
        self.assertFalse(selected.context["form"].errors)
        ranking = [str(bag.pk) for bag in (actual, estimated, unknown)]
        self.assertEqual([row["id"] for row in selected.context["top5"]], ranking)
        self.assertEqual([row["bag_weight_display"] for row in selected.context["top5"]], ["0.729", "0.636", "—"])
        self.assertContains(
            selected,
            '<th class="text-end text-nowrap">Bag area (cm²)</th>'
            '<th class="text-end text-nowrap">Bag weight (g)</th><th>Usage</th>',
            html=True,
        )
        (summary, rows), = self.bag_result_details(selected)
        self.assertIn("100.729 g", summary)
        self.assertEqual(rows["Film material"], "PP")
        self.assertEqual(rows["Packaging weight"], "0.729 g")
        self.assertEqual(rows["Packaging weight source"], "Actual catalogue weight")

        missing = self.client.post(url, {**inputs, "bag_id": unknown.pk})
        (_summary, missing_rows), = self.bag_result_details(missing)
        self.assertEqual(missing_rows["Packaging weight"], "Unavailable")
        self.assertEqual(missing_rows["Packaging weight source"], "Unavailable")
        self.assertNotIn("Caliper", missing_rows)
        self.assertNotIn("Grammage", missing_rows)

        overridden = self.client.post(url, {
            **inputs, "action": "find_top5", "bag_mass_unit": "lb",
            "bag_weight_override": "1", "bag_weight": "0.002",
        })
        override_rows = overridden.context["top5"]
        self.assertEqual([row["id"] for row in override_rows], ranking)
        self.assertEqual([row["bag_weight_display"] for row in override_rows], ["0.0320"] * 3)
        self.assertTrue(all(row["bag_tare_source"] == "manual_override" for row in override_rows))
        self.assertContains(overridden, "Bag weight (oz)")

    def test_preview_and_catalogue_high_precision_form(self):
        form = PackagingMaterialForm(data={
            "part_number": "BAG-87", "part_description": "Sample stock",
            "branding": "Brand1", "packaging_materials": "Polyethylene", "packaging_type": "BAG",
            "part_length": "127", "part_width": "87", "part_height": "0",
            "bag_film_family": "ldpe", "bag_construction": "two_wall", "bag_film_caliper_mm": "0.03048",
            "combined_grammage_g_m2": "28.0416", "bag_actual_weight_g": "0.620123",
        })
        self.assertTrue(form.is_valid(), form.errors)
        bag = form.save(commit=False)
        bag.catalogue = self.catalogue
        bag.save()
        bag.refresh_from_db()
        self.assertEqual(bag.bag_film_caliper_mm, Decimal("0.03048"))
        self.assertEqual(bag.bag_actual_weight_g, Decimal("0.620123"))
        catalogue_page = reverse("catalogue_detail", args=[self.catalogue.pk])
        matches = self.client.get(catalogue_page, {"catalogue_mass_unit": "g", "min_weight": "0.6201"})
        self.assertContains(matches, "BAG-87")
        too_light = self.client.get(catalogue_page, {"catalogue_mass_unit": "g", "min_weight": "0.6202"})
        self.assertNotContains(too_light, "BAG-87")
        url = reverse("bag_film_preview")
        preview = self.client.post(url, {"bag_length": 127, "bag_width": 87}).json()
        self.assertEqual(preview["inputs"], {"caliper": "1.2", "grammage": "28.04", "tare": "0.620"})
        catalogue = {"mode": "optimal", "bag_id": bag.pk, "film_caliper_unit": "um"}
        preview = self.client.post(url, catalogue).json()
        self.assertEqual(preview["inputs"]["caliper"], "30.48")
        self.assertEqual(preview["sources"]["tare"], "Actual catalogue weight")
        preview = self.client.post(url, {**catalogue, "bag_weight_override": "1", "bag_weight": "0.725"}).json()
        self.assertEqual(preview["inputs"]["tare"], "0.725")
        self.assertEqual(preview["sources"]["tare"], "Manual override")
        preview = self.client.post(url, {**catalogue, "bag_weight_override": "0", "bag_weight": "0.725"}).json()
        self.assertEqual(preview["sources"]["tare"], "Actual catalogue weight")

    def test_single_design_and_optimal_workflow_inherit_gross_weight_once(self):
        bag = PackagingMaterial.objects.create(
            catalogue=self.catalogue, packaging_type="BAG", part_number="OVERSIZE",
            part_length=500, part_width=500, part_height=0, bag_film_family="pp",
            bag_film_caliper_mm=Decimal("0.03"), bag_construction="two_wall",
            bag_actual_weight_g=Decimal("0.729"),
        )
        url = reverse("full_packaging_mode")
        for index in range(3):
            self.client.post(url, {"action": "add_step", "step_type": "bag"})
        inputs = (
            {"action_0": "run_single", "product_l_0": 90, "product_w_0": 60, "product_h_0": 25,
             "product_weight_0": 50, "bag_length_0": 127, "bag_width_0": 87,
             "bag_advanced_open_0": "1", "bag_weight_override_0": "0", "bag_weight_0": "0.620"},
            {"action_1": "run_design", "mode_1": "design", "desired_qty_1": 2,
             "film_preset_1": "pp_40", "film_caliper_unit_1": "um", "bag_mass_unit_1": "lb"},
            {"action_2": "select_candidate", "mode_2": "optimal", "desired_qty_2": 1,
             "bag_source_2": "catalogue", "catalogue_id_2": self.catalogue.pk, "bag_id_2": bag.pk},
        )
        for index, fields in enumerate(inputs):
            response = self.client.post(url, {"action": "run_step", "index": index, **fields})
            self.assertEqual(response.status_code, 302)
            self.client.post(url, {"action": "use_step_result", "index": index})
        steps = self.client.session["full_packaging_mode_session"]["steps"]
        inner, design, optimal = [step["selected"] for step in steps]
        self.assertEqual(inner["bag_tare_g"], 0.6196632768)
        self.assertEqual(steps[0]["config"]["bag_weight"], "")
        self.assertEqual(inner["outer_dimension_source"], "tight_fit_film_estimate")
        self.assertAlmostEqual(design["net_content_weight_g"], 2 * inner["weight_g"])
        self.assertAlmostEqual(design["weight_g"], 2 * inner["weight_g"] + design["bag_tare_g"])
        self.assertAlmostEqual(optimal["weight_g"], design["weight_g"] + 0.729)
        self.assertAlmostEqual(optimal["weight_kg"] * 1000, optimal["weight_g"])
        self.assertEqual(optimal["total_base_units"], 2)
        self.assertEqual([step["config"]["film_preset"] for step in steps], ["ldpe_1_2", "pp_40", "ldpe_1_2"])

        session = self.client.session
        saved_design = session["full_packaging_mode_session"]["steps"][1]
        self.assertEqual(design["selected_candidate_id"], saved_design["design_candidates"][0]["candidate_id"])
        saved_design["design_candidates"].sort(key=lambda row: row["bag_area"], reverse=True)
        for rank, row in enumerate(saved_design["design_candidates"], start=1):
            row["rank"] = rank
        for row in [saved_design["result"], *saved_design["design_candidates"]]:
            row["bag_dimensions_display"] = format_dimensions(row["bag_width"], row["bag_length"])
        session.save()

        html = self.client.get(url)
        restored = html.context["steps"][1]["result"]
        self.assertContains(html, f'<strong>{format_dimensions(restored["bag_length"], restored["bag_width"])}</strong>', html=True)
        self.assertContains(html, "Bag weight (oz)", count=1)
        self.assertContains(html, "Bag weight (g)", count=1)
        design_rows = html.context["steps"][1]["design_candidates_for_display"]
        self.assertEqual([row["bag_area"] for row in design_rows], sorted(row["bag_area"] for row in design_rows))
        self.assertEqual([row["rank"] for row in design_rows], list(range(1, len(design_rows) + 1)))
        self.assertEqual(restored["candidate_id"], design["selected_candidate_id"])
        self.assertGreater(len({row["bag_weight_display"] for row in design_rows}), 1)
        self.assertTrue(all(row["bag_weight_unit"] == "oz" for row in design_rows))
        for row in design_rows:
            self.assertEqual(row["bag_dimensions_display"], format_dimensions(row["bag_length"], row["bag_width"]))
        for index in range(3):
            self.assertContains(html, f'name="film_caliper_unit_{index}"', count=1)
        sections = self.bag_result_details(html)
        self.assertEqual(len(sections), 3)
        for (_summary, rows), output in zip(sections, (inner, design, optimal)):
            self.assertEqual(
                rows["Flat bag dimensions"],
                format_dimensions(output["flat_bag_length_mm"], output["flat_bag_width_mm"]),
            )
            self.assertIn("Packed bundle dimensions", rows)
            self.assertIn("Outer dimensions", rows)
            self.assertNotIn("Bag dimensions", rows)
            self.assertEqual(rows["Outer dimensions source"], output["outer_dimension_source_display"])
            self.assertEqual(rows["Packaging weight source"], output["bag_tare_source_display"])
        json.dumps(steps, allow_nan=False)


class BagFilmMigrationTests(TransactionTestCase):
    def test_migration_preserves_legacy_bag_and_carton_properties(self):
        before = ("packagingapp", "0018_packagingmaterial_corrugated_properties")
        after = ("packagingapp", "0019_bag_film_properties")
        executor = MigrationExecutor(connection)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate([after]))
        executor.migrate([before])
        apps = executor.loader.project_state([before]).apps
        catalogue = apps.get_model("packagingapp", "PackagingCatalogue").objects.create(name="Legacy")
        material = apps.get_model("packagingapp", "PackagingMaterial")
        carton = material.objects.create(
            catalogue=catalogue, packaging_type="BOX", part_number="BOX", part_length=200, part_width=100,
            part_height=75, box_thickness_mm=Decimal("4.125"), combined_grammage_g_m2=450, part_weight=0.2,
        )
        bag = material.objects.create(
            catalogue=catalogue, packaging_type="BAG", part_number="BAG", part_length=127,
            part_width=87, part_height=0, part_weight=Decimal("0.002"),
        )
        MigrationExecutor(connection).migrate([after])
        carton = PackagingMaterial.objects.get(pk=carton.pk)
        bag = PackagingMaterial.objects.get(pk=bag.pk)
        self.assertEqual(carton.box_thickness_mm, Decimal("4.125"))
        self.assertEqual(carton.combined_grammage_g_m2, 450)
        self.assertIsNone(bag.bag_film_family)
        self.assertIsNone(bag.bag_film_caliper_mm)
        self.assertIsNone(bag.bag_actual_weight_g)
        film = resolve_bag_film({"bag_source": "catalogue"}, (127, 87), bag)
        self.assertEqual(film["bag_tare_g"], 2)
        self.assertIsNone(film["film_caliper_mm"])
