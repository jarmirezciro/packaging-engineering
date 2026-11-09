import json
import tempfile
from collections import defaultdict
from html.parser import HTMLParser
from itertools import combinations
from math import prod
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

from packagingapp.models import UserPreferences
from packagingapp.tests.benchmark_shared_mosaic_patterns import BENCHMARK_CASES
from packagingapp.tests.test_container_bag_unit_rollout import _bag_config as metric_bag_fixture
from packagingapp.tools.bag.case_presets import BAG_SELECTION_CASE_PRESETS
from packagingapp.tools.bag.service import analyze_bag_config
from packagingapp.tools.container.case_presets import CONTAINER_SELECTION_CASE_PRESETS
from packagingapp.tools.full_packaging.case_presets import get_case_titles
from packagingapp.tools.palletization.case_presets import PALLETIZATION_CASE_PRESETS
from packagingapp.tools.palletization.state import default_palletization_config
from packagingapp.tools.transport.case_presets import (
    TRANSPORT_CONTAINER_CASE_PRESETS,
    get_transport_container_case_preset,
)
from packagingapp.tools.transport.service import _prepare_transport_analysis
from packagingapp.units import convert_length, convert_mass
from packagingapp.utils.package_design_arrangements import build_canonical_design_arrangements


NEW_REGRESSION_CASE_SLUGS = (
    "p1-p2-imperial-supported-roof",
    "40hc-euro-pallet-unequal-lane-tails",
    "tops-dgfe-shared-loading-group",
    "easycargo-40hc-r3-only-dgfe",
    "48ft-semitrailer-expv2-2-support-beds",
)


class CaseLinkParser(HTMLParser):
    def __init__(self, tool_name):
        super().__init__()
        self.case_prefix = f"{reverse(tool_name)}?case="
        self.links = []

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href", "")
        if tag == "a" and href.startswith(self.case_prefix):
            self.links.append(href)


class RegressionCompendiumTests(TestCase):
    def setUp(self):
        media_root = tempfile.TemporaryDirectory(prefix="kollipack-cases-")
        self.addCleanup(media_root.cleanup)
        settings = self.settings(MEDIA_ROOT=media_root.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def case_links(self, response, tool_name="container_tool"):
        parser = CaseLinkParser(tool_name)
        parser.feed(response.content.decode())
        return parser.links

    def assert_preset_inputs(self, response, preset):
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "container_tool/container_tool.html")
        self.assertEqual(response.context["mode"], "standalone")
        for key, expected in preset["config"].items():
            self.assertEqual(response.context["form"][key].value(), expected, key)
        for key, fallback in (
            ("load_unit_dimension_unit", "mm"),
            ("load_unit_mass_unit", "kg"),
            ("transport_dimension_unit", "mm"),
            ("transport_mass_unit", "kg"),
        ):
            self.assertEqual(
                response.context["transport_values"][key],
                preset["config"].get(key, fallback),
            )
        rows = response.context["product_rows"]
        self.assertEqual(len(rows), len(preset["rows"]))
        for actual, expected in zip(rows, preset["rows"]):
            for key, value in expected.items():
                if key in {"length", "width", "height", "weight"}:
                    if key == "weight":
                        canonical = convert_mass(value, preset["config"].get("load_unit_mass_unit", "kg"), "kg")
                    else:
                        canonical = convert_length(value, preset["config"].get("load_unit_dimension_unit", "mm"), "mm")
                    self.assertAlmostEqual(actual[f"canonical_{key}"], canonical, msg=key)
                    self.assertAlmostEqual(float(actual[key]), value, delta=0.005001, msg=key)
                else:
                    self.assertEqual(actual[key], value, key)

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["localhost", "kollipack.example"])
    def test_compendium_lists_registry_cases_with_host_independent_links(self):
        for host in ("localhost", "kollipack.example"):
            with self.subTest(host=host):
                response = self.client.get("/regressions", HTTP_HOST=host)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "base.html")
                self.assertContains(response, "Regression &amp; Case Compendium")
                self.assertContains(response, "Transport Container Cases")
                expected_links = []
                for index, (slug, preset) in enumerate(
                    TRANSPORT_CONTAINER_CASE_PRESETS.items(), start=1
                ):
                    self.assertContains(response, f"Case {index:02d}")
                    self.assertContains(response, escape(preset["label"]))
                    expected_links.append(
                        f"{reverse('container_tool')}?{urlencode({'case': slug})}"
                    )
                self.assertEqual(self.case_links(response), expected_links)
                self.assertContains(response, "Container Selection Cases")
                self.assertEqual(
                    self.case_links(response, "container_selection_mode1"),
                    [
                        f"{reverse('container_selection_mode1')}?{urlencode({'case': slug})}"
                        for slug in CONTAINER_SELECTION_CASE_PRESETS
                    ],
                )
                for heading, route, presets in (
                    ("Palletization Cases", "palletization_mode1", PALLETIZATION_CASE_PRESETS),
                    ("Bag Selection Cases", "bag_selection_mode1", BAG_SELECTION_CASE_PRESETS),
                ):
                    self.assertContains(response, heading)
                    self.assertEqual(self.case_links(response, route), [
                        f"{reverse(route)}?{urlencode({'case': slug})}" for slug in presets
                    ])
                self.assertContains(response, "Packaging Flow Cases")
                for slug, title in get_case_titles():
                    url = reverse("full_packaging_case", args=[slug])
                    self.assertContains(response, f'href="{url}?reset=1">{escape(title)}</a>', count=1)
        self.assertRedirects(
            self.client.get("/regressions/", HTTP_HOST="localhost"),
            "/regressions",
            301,
            fetch_redirect_response=False,
        )

    def assert_pallet_case_geometry(self, response):
        result = response.context["selected_result"]
        self.assertIsNotNone(result, response.context["form"].errors)
        scene = response.context["threejs_scene"]
        self.assertEqual(scene["units"], "mm")
        self.assertEqual(len(scene["placements"]), result["total_boxes"])
        self.assertEqual(scene["total_cases"], result["total_boxes"])
        self.assertEqual(scene["layers"], result["layers"])

        config = response.context["pallet_config"]
        box_unit = config["box_dimension_unit"]
        pallet_unit = config["pallet_dimension_unit"]
        for axis, suffix in (("length", "l"), ("width", "w"), ("height", "h")):
            self.assertAlmostEqual(
                scene["case"][axis], convert_length(float(config[f"box_{suffix}"]), box_unit, "mm")
            )
            pallet_field = f"pallet_{axis if axis == 'height' else suffix}"
            self.assertAlmostEqual(
                scene["pallet"][axis], convert_length(float(config[pallet_field]), pallet_unit, "mm")
            )

        limits = {}
        for axis, length in (("x", "length"), ("y", "width")):
            allowance = convert_length(float(config[f"max_{length}_stickout"] or 0), pallet_unit, "mm")
            limits[axis] = (-allowance / 2, scene["pallet"][length] + allowance / 2)
        deck = scene["pallet"]["height"]
        limits["z"] = (deck, convert_length(float(config["max_stack_height"]), pallet_unit, "mm"))

        epsilon = 1e-6
        length, width = scene["case"]["length"], scene["case"]["width"]
        footprints = {"LxW": (length, width), "WxL": (width, length)}
        layers = defaultdict(list)
        for carton in scene["placements"]:
            layers[carton["layer"]].append(carton)
            self.assertIn(carton["orientation"], footprints)
            length, width = footprints[carton["orientation"]]
            self.assertAlmostEqual(carton["dx"], length)
            self.assertAlmostEqual(carton["dy"], width)
            self.assertAlmostEqual(carton["dz"], scene["case"]["height"])
            self.assertAlmostEqual(carton["z"], deck + (carton["layer"] - 1) * carton["dz"])
            for axis, (lower, upper) in limits.items():
                self.assertGreater(carton[f"d{axis}"], 0)
                self.assertGreaterEqual(carton[axis], lower - epsilon)
                self.assertLessEqual(carton[axis] + carton[f"d{axis}"], upper + epsilon)

        self.assertEqual(set(layers), set(range(1, result["layers"] + 1)))
        for layer in layers.values():
            for first, second in combinations(layer, 2):
                self.assertTrue(any(
                    first[axis] + first[f"d{axis}"] <= second[axis] + epsilon
                    or second[axis] + second[f"d{axis}"] <= first[axis] + epsilon
                    for axis in ("x", "y")
                ), f"Overlapping cartons: {first} and {second}")

    def test_palletization_links_load_calculate_select_and_recalculate(self):
        user = get_user_model().objects.create_user(username="pallet-case-units")
        UserPreferences.objects.create(user=user, default_length_unit="ft", default_small_mass_unit="oz")
        self.client.force_login(user)

        # Current default results. The benchmark notes record historical results
        # separately, including the compact Think Beyond the Box alternative.
        capacities = {
            "tops-pro-48x40-benchmark": (10, 5, 50),
            "tops-case-pack-8": (24, 6, 144),
            "tops-case-pack-16": (11, 7, 77),
            "capepack-original-216": (9, 2, 18),
            "capepack-original-240": (4, 5, 20),
            "capepack-72in-12-pack": (10, 3, 30),
            "capepack-72in-16-pack": (8, 3, 24),
            "north-american-splitrow": (24, 6, 144),
            "pinwheel-mosaic": (24, 8, 192),
            "brick-centre-filled": (18, 5, 90),
            "maximum-pallet-load": (6, 4, 22),
            "bottom-carton-load": (24, 8, 192),
            "overhang-feasibility": (1, 2, 2),
            "fractional-dimensions": (34, 6, 204),
            "exact-stack-height": (8, 1, 8),
            "think-beyond-the-box-compact": (5, 4, 20),
            "think-beyond-the-box-alternative-7": (6, 4, 24),
        }
        page = self.client.get(reverse("regressions"))
        route = reverse("palletization_mode1")
        links = self.case_links(page, "palletization_mode1")
        self.assertEqual(len(links), len(PALLETIZATION_CASE_PRESETS))
        self.assertEqual(set(capacities), set(PALLETIZATION_CASE_PRESETS))

        for link, (slug, preset) in zip(links, PALLETIZATION_CASE_PRESETS.items()):
            with self.subTest(case=slug):
                self.assertEqual(link, f"{route}?{urlencode({'case': slug})}")
                self.assertContains(page, escape(preset["label"]))
                response = self.client.get(link)
                self.assertTemplateUsed(response, "palletization/palletization_mode1.html")
                self.assertEqual(response.context["mode"], "standalone")
                config = {**default_palletization_config(), **preset["config"]}
                self.assertEqual(response.context["pallet_config"], config)
                form = response.context["form"]
                for key in form.fields.keys() & config.keys():
                    self.assertEqual(form[key].value(), config[key], key)
                advanced = int(config["show_advanced"])
                self.assertContains(response, f'name="show_advanced" id="show_advanced" value="{advanced}"')
                self.assert_pallet_case_geometry(response)
                selected = response.context["selected_result"]
                self.assertEqual(
                    (selected["boxes_layer_A"], selected["layers"], selected["total_boxes"]),
                    capacities[slug],
                )
                rows = response.context["results_table"]
                self.assertIn(selected["result_key"], [row["result_key"] for row in rows])
                export = self.client.session["palletization_last_export"]
                self.assertEqual(export["analysis_report"], selected)
                json.dumps(export, allow_nan=False)

                if len(rows) > 1:
                    alternative = rows[1]["result_key"]
                    switched = self.client.post(link, {
                        **config, "action": "select_result", "selected_result_key": alternative,
                    })
                    self.assertEqual(switched.context["selected_result"]["result_key"], alternative)
                    self.assert_pallet_case_geometry(switched)

                # The standalone form posts back to the case URL. Allow room
                # for exactly one layer of the edited carton height.
                box_height = config["box_h"] + 1
                carton_height = convert_length(
                    box_height, config["box_dimension_unit"], config["pallet_dimension_unit"]
                )
                stack_height = config["pallet_height"] + carton_height * 1.01
                edited = self.client.post(link, {
                    **config, "action": "run_analysis", "box_h": box_height,
                    "max_stack_height": stack_height,
                })
                self.assertEqual(edited.context["form"]["box_h"].value(), str(box_height))
                self.assertEqual(edited.context["form"]["max_stack_height"].value(), str(stack_height))
                self.assert_pallet_case_geometry(edited)
                self.assertEqual(edited.context["selected_result"]["layers"], 1)

    def test_palletization_cases_leave_standalone_and_seo_defaults_available(self):
        route = reverse("palletization_mode1")
        seo_route = reverse("palletization_calculator")
        self.client.get(route, {"case": "capepack-72in-16-pack"})

        standalone = self.client.get(route)
        self.assertTemplateUsed(standalone, "palletization/palletization_mode1.html")
        self.assertEqual(standalone.context["pallet_config"], default_palletization_config())
        self.assertIsNone(standalone.context["selected_result"])
        self.assertEqual(self.client.get(route, {"case": "unknown-pallet-case"}).status_code, 404)

        article_case = self.client.get(seo_route, {"case": "tops-pro-48x40-benchmark"})
        self.assertTemplateUsed(article_case, "marketing/palletization_calculator.html")
        self.assertFalse(article_case.context["is_initial_example"])
        self.assertEqual(article_case.context["selected_result"]["total_boxes"], 50)

        example = self.client.get(seo_route)
        self.assertTrue(example.context["is_initial_example"])
        self.assertEqual(example.context["form"]["box_l"].value(), 400)
        self.assertEqual(example.context["form"]["pallet_dimension_unit"].value(), "mm")
        self.assertEqual(example.context["selected_result"]["total_boxes"], 40)

        user = get_user_model().objects.create_user(username="pallet-default-units")
        UserPreferences.objects.create(user=user, default_length_unit="ft", default_small_mass_unit="oz")
        self.client.force_login(user)
        standalone = self.client.get(route)
        self.assertEqual(standalone.context["pallet_config"], {
            **default_palletization_config(),
            "box_dimension_unit": "ft",
            "pallet_dimension_unit": "ft",
            "mass_unit": "oz",
        })
        self.assertIsNone(standalone.context["selected_result"])

    def test_case_links_preserve_inputs_results_and_exports_across_session(self):
        page = self.client.get(reverse("regressions"))
        links = self.case_links(page)
        self.assertEqual(len(links), len(TRANSPORT_CONTAINER_CASE_PRESETS))
        # Revisit the metric/payload case after the imperial/blank-payload case.
        for link, slug in list(zip(links, TRANSPORT_CONTAINER_CASE_PRESETS)) + [
            (links[0], next(iter(TRANSPORT_CONTAINER_CASE_PRESETS)))
        ]:
            with self.subTest(case=slug):
                preset = get_transport_container_case_preset(slug)
                response = self.client.get(link)
                self.assert_preset_inputs(response, preset)
                self.assertEqual(response.context["row_errors"], [])
                result = response.context["result"]
                self.assertIsNotNone(result)
                self.assertEqual(result["packing_mode"], preset["config"]["packing_mode"])
                self.assertEqual(
                    result["summary"]["placed_units"] + result["summary"]["unplaced_units"],
                    sum(row["qty"] for row in preset["rows"]),
                )
                self.assertEqual(
                    len(response.context["threejs_scene"]["items"]),
                    result["summary"]["placed_units"],
                )
                export = self.client.session["transport_container_last_export"]
                self.assertEqual(export["summary"], result["summary"])
                json.dumps(dict(self.client.session))
                self.assertEqual(get_transport_container_case_preset(slug), preset)

    def test_container_case_links_load_inputs_and_calculate_in_standalone_tool(self):
        user = get_user_model().objects.create_user(username="container-case-units")
        UserPreferences.objects.create(user=user, default_length_unit="ft")
        self.client.force_login(user)
        page = self.client.get(reverse("regressions"))
        links = self.case_links(page, "container_selection_mode1")
        self.assertEqual(len(links), len(CONTAINER_SELECTION_CASE_PRESETS))
        single_capacities = {
            "mosaic-packing-benchmark": 106,
            "product-orientation-capacity": 18,
            "pinwheel-packing-benchmark": 16,
        }
        design_results = {
            "bottle-packaging-24": (24, (6, 2, 2), "15.66 × 5.22 × 20 in"),
            "bottle-packaging-15": (15, (5, 3, 1), "13.2 × 7.92 × 9.75 in"),
            "design-mode-quantity-optimization": (8, (2, 1, 4), "240 × 180 × 320 mm"),
        }
        for link, (slug, preset) in zip(links, CONTAINER_SELECTION_CASE_PRESETS.items()):
            with self.subTest(case=slug):
                self.assertContains(page, escape(preset["label"]))
                response = self.client.get(link)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "container_selection/container_selection_mode1.html")
                self.assertEqual(response.context["mode"], "standalone")
                form = response.context["form"]
                self.assertFalse(form.errors)
                for key, expected in preset["config"].items():
                    self.assertEqual(form[key].value(), expected if isinstance(expected, bool) else str(expected), key)
                unit = preset["config"].get("product_dimension_unit", "mm")
                self.assertEqual(form["product_dimension_unit"].value(), unit)
                self.assertEqual(form["container_dimension_unit"].value(), unit)
                result = response.context["result"]
                scene = response.context["threejs_scene"]
                if slug in single_capacities:
                    quantity = single_capacities[slug]
                    self.assertEqual(result.max_quantity, quantity)
                    self.assertIn("container_selection_single_export", self.client.session)
                else:
                    quantity, arrangement, dimensions = design_results[slug]
                    self.assertEqual(result["design_quantity"], quantity)
                    self.assertEqual((result["rows"], result["columns"], result["layers"]), arrangement)
                    self.assertEqual(result["container_dimensions_display"], dimensions)
                    self.assertIn("container_selection_design_export", self.client.session)
                    if unit == "in":
                        self.assertEqual(scene["productShape"], "bottle")
                        self.assertAlmostEqual(result["corrugated_caliper_mm"], 4.064)
                    else:
                        candidates = response.context["design_candidates"]
                        self.assertEqual(result["additional_capacity"], 1)
                        self.assertEqual(len(candidates), 30)
                        self.assertEqual(len({row["container_dimensions_display"] for row in candidates}), 30)
                self.assertEqual(len(scene["products"]), quantity)
                json.dumps(dict(self.client.session), allow_nan=False)

    def test_container_orientation_case_accepts_edits_and_keeps_the_public_example(self):
        slug = "product-orientation-capacity"
        preset = CONTAINER_SELECTION_CASE_PRESETS[slug]
        query = urlencode({"case": slug})
        url = f"{reverse('container_selection_mode1')}?{query}"
        response = self.client.post(url, {**preset["config"], "r1": "", "r2": ""})
        self.assertEqual(response.context["result"].max_quantity, 15)
        self.assertEqual(self.client.get(url).context["result"].max_quantity, 18)

        public = self.client.get(reverse("container_selection_calculator"), {"case": slug})
        self.assertEqual(public.context["active_case_slug"], slug)
        self.assertEqual(public.context["result"].max_quantity, 18)

    def test_unknown_container_case_returns_404_and_plain_tool_keeps_defaults(self):
        url = reverse("container_selection_mode1")
        self.assertEqual(self.client.get(url, {"case": "unknown-case"}).status_code, 404)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["result"])
        self.assertEqual(response.context["form"]["product_l"].value(), "")

    def test_post_to_case_url_calculates_edited_inputs(self):
        slug = "easycargo-40hc-mixed-cargo-benchmark"
        preset = get_transport_container_case_preset(slug)
        row = preset["rows"][0]
        data = {**preset["config"], "action": "run_analysis", "container_l": "12000"}
        for key, value in row.items():
            data[f"item_{key}[]"] = [str(int(value)) if isinstance(value, bool) else str(value)]
        data["item_qty[]"] = ["2"]
        data["item_sequence[]"] = ["5"]
        url = f"{reverse('container_tool')}?{urlencode({'case': slug})}"
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"]["container_l"].value(), 12000)
        self.assertEqual(response.context["row_errors"], [])
        self.assertEqual(len(response.context["product_rows"]), 1)
        self.assertEqual(response.context["product_rows"][0]["qty"], 2)
        self.assertEqual(response.context["product_rows"][0]["sequence"], 5)
        self.assertEqual(response.context["result"]["summary"]["placed_units"], 2)
        self.assert_preset_inputs(self.client.get(url), preset)

    def test_case_units_override_account_defaults(self):
        user = get_user_model().objects.create_user(username="case-units")
        UserPreferences.objects.create(
            user=user, default_length_unit="ft", default_large_mass_unit="t"
        )
        self.client.force_login(user)
        slug = "mix_load_case_hight_cube"
        response = self.client.get(reverse("container_tool"), {"case": slug})
        self.assert_preset_inputs(response, get_transport_container_case_preset(slug))

    def test_new_cases_calculate_after_switching_strategy(self):
        for slug in NEW_REGRESSION_CASE_SLUGS:
            with self.subTest(case=slug):
                preset = get_transport_container_case_preset(slug)
                mode = {
                    "front_to_back": "space_evenly",
                    "front_to_back_infill": "space_evenly_infill",
                }[preset["config"]["packing_mode"]]
                data = {**preset["config"], "action": "run_analysis", "packing_mode": mode}
                for key in preset["rows"][0]:
                    data[f"item_{key}[]"] = [
                        str(int(row[key])) if isinstance(row[key], bool) else str(row[key])
                        for row in preset["rows"]
                    ]
                url = f"{reverse('container_tool')}?{urlencode({'case': slug})}"
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["row_errors"], [])
                self.assertEqual(response.context["form"]["packing_mode"].value(), mode)
                result = response.context["result"]
                self.assertIsNotNone(result)
                self.assertEqual(result["packing_mode"], mode)
                self.assertEqual(
                    result["summary"]["placed_units"] + result["summary"]["unplaced_units"],
                    sum(row["qty"] for row in preset["rows"]),
                )
                for key, value in response.context["transport_values"].items():
                    self.assertEqual(value, preset["config"].get(key, "kg" if "mass" in key else "mm"))
                for actual, expected in zip(response.context["product_rows"], preset["rows"]):
                    self.assertEqual(actual["sequence"], 1)
                    for key in ("qty", "stackable", "r1", "r2", "r3"):
                        self.assertEqual(actual[key], expected[key], key)
                json.dumps(dict(self.client.session))

    def test_unknown_cases_return_404_and_plain_tool_keeps_defaults(self):
        for slug in ("unknown-case", "../../manage.py", "os.system('echo test')"):
            with self.subTest(case=slug):
                response = self.client.get(reverse("container_tool"), {"case": slug})
                self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("container_tool"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["result"])
        self.assertEqual(response.context["form"]["container_l"].value(), "")


class BagCompendiumTests(TestCase):
    def test_bag_links_load_standalone_results_with_case_units_and_scenes(self):
        user = get_user_model().objects.create_user(username="bag-case-units")
        UserPreferences.objects.create(user=user, default_length_unit="ft", default_small_mass_unit="oz")
        self.client.force_login(user)
        page = self.client.get(reverse("regressions"))
        parser = CaseLinkParser("bag_selection_mode1")
        parser.feed(page.content.decode())
        self.assertEqual(len(parser.links), len(BAG_SELECTION_CASE_PRESETS))

        single_capacities = {
            "maximum-bag-capacity": 2,
            "sealing-and-bag-orientation": 1,
            "bottle-dimensional-allowances": 30,
            "imperial-metric-units": 12,
            "pillow-bag-visualization": 6,
        }
        design_quantities = {"three-dimensional-bag-design": 12, "non-smooth-quantity-design": 8}
        cases = list(zip(parser.links, BAG_SELECTION_CASE_PRESETS.items()))
        for link, (slug, preset) in cases + cases[:1]:
            with self.subTest(case=slug):
                self.assertContains(page, escape(preset["label"]))
                response = self.client.get(link)
                self.assertTemplateUsed(response, "bag_selection/bag_selection_mode1.html")
                self.assertContains(response, 'data-scene-script="bagThreeJsScene"')
                self.assertEqual(response.context["mode"], "standalone")
                config = response.context["bag_config"]
                expected = preset["config"]
                for key, value in expected.items():
                    self.assertEqual(config[key], str(value), key)
                for key, fallback in (
                    ("product_dimension_unit", "mm"), ("bag_dimension_unit", "mm"),
                    ("product_mass_unit", "g"), ("bag_mass_unit", "g"),
                    ("product_allowance_l", "0"), ("product_allowance_w", "0"), ("product_allowance_h", "0"),
                    ("product_source", "manual"), ("bag_source", "manual"), ("product_shape", "cuboid"),
                ):
                    self.assertEqual(response.context["form"][key].value(), str(expected.get(key, fallback)), key)

                scene = response.context["threejs_scene"]
                self.assertEqual(scene["productShape"], config["product_shape"])
                self.assertEqual(response.context["product_unit_scene"]["displayUnit"], config["product_dimension_unit"])
                self.assertEqual((scene["packageType"], scene["mode"], scene["units"]), ("bag", config["mode"], "mm"))
                bag = scene["bag"]
                self.assertEqual((bag["openingSide"], bag["openingAt"]), ("width", "length-end"))
                self.assertEqual((bag["sealingAllowance"], bag["fitTolerance"]), (10, 2))
                self.assertAlmostEqual(scene["container"]["length"] - bag["usableBodyLength"], 10)
                for item in scene["products"]:
                    self.assertLessEqual(item["x"] + item["dx"], bag["usableBodyLength"] + 0.000001)

                result = response.context["result"]
                if slug in single_capacities:
                    quantity = single_capacities[slug]
                    self.assertEqual(result["max_quantity"], quantity)
                    self.assertEqual(prod(scene["usedLayout"]), quantity)
                    self.assertAlmostEqual(scene["selectedRequiredBag"]["length"], result["best_required"][0])
                    self.assertAlmostEqual(scene["selectedRequiredBag"]["width"], result["best_required"][1])
                    self.assertAlmostEqual(bag["flatLength"], result["bag_len"], places=6)
                    self.assertAlmostEqual(bag["flatWidth"], result["bag_w"], places=6)
                    report = response.context["analysis_report"]
                    self.assertEqual(self.client.session["bag_selection_single_export"]["analysis_report"], report)
                    if slug == "bottle-dimensional-allowances":
                        self.assertEqual(report["effective_product_dimensions_display"], "66.294 × 66.294 × 257.048 mm")
                        self.assertEqual(scene["productDefinition"], {"length": 63.246, "width": 63.246, "height": 254})
                    if slug == "pillow-bag-visualization":
                        self.assertEqual(report["total_weight_display"], "1518 g")
                        self.assertEqual(report["payload_usage_display"], "30%")
                else:
                    quantity = design_quantities[slug]
                    self.assertEqual(result["design_quantity"], quantity)
                    self.assertEqual(result["additional_capacity"], quantity - expected["desired_qty"])
                    self.assertEqual(scene, result["render_data"])
                    self.assertEqual({item["orientationIndex"] for item in scene["products"]}, {result["orientation_index"]})
                    self.assertEqual(bag["flatLength"], result["bag_length"])
                    self.assertEqual(bag["flatWidth"], result["bag_width"])
                    canonical = build_canonical_design_arrangements(
                        tuple(expected[f"product_{axis}"] for axis in "lwh"), expected["desired_qty"], 1, 1, 1
                    )
                    candidates = response.context["design_candidates"]
                    self.assertEqual([row["arrangement_id"] for row in candidates], [
                        row["arrangement_id"] for row in canonical["arrangements"]
                    ])
                    self.assertEqual(len({row["candidate_id"] for row in candidates}), len(candidates))
                    self.assertEqual(self.client.session["bag_selection_design_export"]["selected_candidate"]["candidate_id"], result["candidate_id"])
                self.assertEqual(len(scene["products"]), quantity)
                json.dumps(dict(self.client.session), allow_nan=False)

        plain = self.client.get(reverse("bag_selection_mode1"))
        self.assertIsNone(plain.context["result"])
        self.assertEqual(plain.context["form"]["product_l"].value(), "")
        self.assertEqual(plain.context["form"]["product_dimension_unit"].value(), "ft")
        self.assertEqual(plain.context["form"]["bag_mass_unit"].value(), "oz")

    def test_sealing_case_accepts_swapped_bag_and_reports_no_fit(self):
        url = f"{reverse('bag_selection_mode1')}?case=sealing-and-bag-orientation"
        initial = self.client.get(url)
        self.assertEqual(initial.context["result"]["best_required"], (122, 62))
        data = {**initial.context["bag_config"], "bag_length": 65, "bag_width": 130}
        edited = self.client.post(url, data)
        self.assertFalse(edited.context["form"].errors)
        self.assertEqual(edited.context["result"]["max_quantity"], 0)
        self.assertIsNone(edited.context["threejs_scene"])
        self.assertEqual(self.client.get(url).context["result"]["max_quantity"], 1)

    def test_design_case_keeps_candidate_ids_and_accepts_selection_and_quantity_edits(self):
        url = f"{reverse('bag_selection_mode1')}?case=non-smooth-quantity-design"
        initial = self.client.get(url)
        data = initial.context["bag_config"]
        ids = [row["candidate_id"] for row in initial.context["design_candidates"]]
        selected = self.client.post(url, {
            **data, "action": "select_design_candidate", "selected_design_candidate_id": ids[-1],
        })
        self.assertEqual([row["candidate_id"] for row in selected.context["design_candidates"]], ids)
        self.assertEqual(selected.context["result"]["candidate_id"], ids[-1])
        self.assertEqual(selected.context["threejs_scene"], selected.context["result"]["render_data"])
        edited = self.client.post(url, {**data, "desired_qty": 9})
        self.assertEqual(edited.context["result"]["design_quantity"], 9)
        self.assertEqual(len(edited.context["threejs_scene"]["products"]), 9)

    def test_mixed_unit_case_matches_metric_fixture(self):
        response = self.client.get(reverse("bag_selection_mode1"), {"case": "imperial-metric-units"})
        metric = analyze_bag_config(metric_bag_fixture(), "run_single")
        self.assertEqual(response.context["result"]["max_quantity"], metric["result"]["max_quantity"])
        self.assertEqual(response.context["threejs_scene"], metric["threejs_scene"])
        report = response.context["analysis_report"]
        for key in ("product_weight", "bag_weight", "payload_capacity"):
            self.assertAlmostEqual(report[key], metric["analysis_report"][key], places=6)
        for key, unit in (("product_dimensions", "cm"), ("bag_dimensions", "in"), ("payload_capacity", "lb")):
            self.assertTrue(report[f"{key}_display"].endswith(f" {unit}"), key)

    def test_unknown_bag_cases_return_404(self):
        for slug in ("unknown-case", "../../manage.py"):
            self.assertEqual(self.client.get(reverse("bag_selection_mode1"), {"case": slug}).status_code, 404)


class RegressionPresetSourceTests(SimpleTestCase):
    def test_pinwheel_preset_matches_existing_mosaic_benchmark(self):
        _, product, container, rotations = next(
            case for case in BENCHMARK_CASES if case[0] == "reference_imperial_equivalent"
        )
        config = CONTAINER_SELECTION_CASE_PRESETS["pinwheel-packing-benchmark"]["config"]
        self.assertEqual(tuple(config[f"product_{axis}"] for axis in "lwh"), product)
        self.assertEqual(tuple(config[f"box_{axis}"] for axis in "lwh"), container)
        self.assertEqual(tuple(config[f"r{index}"] for index in range(1, 4)), rotations)

    def assert_matches_source(self, slug, source_container, source_rows):
        preset = get_transport_container_case_preset(slug)
        prepared = _prepare_transport_analysis(preset["config"], preset["rows"])
        self.assertTrue(prepared["ok"], prepared["messages"])
        for key, value in source_container.items():
            self.assertEqual(prepared["container"][key], value, key)
        self.assertEqual(len(prepared["products"]), len(source_rows))
        for actual, expected in zip(prepared["products"], source_rows):
            for key, value in expected.items():
                if key in {"length", "width", "height", "weight"}:
                    self.assertAlmostEqual(actual[key], value, msg=key)
                else:
                    self.assertEqual(actual[key], value, key)
        self.assertTrue(all(not row["max_qty"] for row in preset["rows"]))
        self.assertEqual(preset["config"]["max_weight"], "")
        self.assertEqual(preset["config"]["tare_weight"], "")
        json.dumps(preset, allow_nan=False)

    def test_variants_match_documented_engine_fixture_inputs(self):
        from packagingapp.tests.test_transport_adaptive_mixed_lane import (
            container as pallet_container,
            product as pallet_product,
        )
        from packagingapp.tests.test_transport_easycargo_preset import EasyCargoEngineTests
        from packagingapp.tests.test_transport_front_to_back import (
            container as tops_container,
            primary_case_products,
        )
        from packagingapp.tests.test_transport_mixed_cargo_infill import stackability_expv2_2

        sources = (
            ("40hc-euro-pallet-unequal-lane-tails", pallet_container(), [pallet_product(1200, 801, 30)]),
            ("tops-dgfe-shared-loading-group", tops_container(12039, 2362, 2692), primary_case_products()),
            ("easycargo-40hc-r3-only-dgfe", *EasyCargoEngineTests().benchmark_inputs(all_rotations=False)),
            ("48ft-semitrailer-expv2-2-support-beds", *stackability_expv2_2()),
        )
        for slug, source_container, source_rows in sources:
            with self.subTest(case=slug):
                self.assert_matches_source(slug, source_container, source_rows)

    def test_roof_preserves_documented_inches_and_kg_service_inputs(self):
        # evidence.json -> equivalent_unit_checks[0].imperial_input; no
        # dependency on that local investigation artifact at application runtime.
        preset = get_transport_container_case_preset("p1-p2-imperial-supported-roof")
        self.assertEqual(preset["config"]["load_unit_dimension_unit"], "in")
        self.assertEqual(preset["config"]["transport_dimension_unit"], "in")
        self.assertEqual(preset["config"]["load_unit_mass_unit"], "kg")
        self.assertEqual(preset["config"]["transport_mass_unit"], "kg")
        self.assertEqual(
            [(row["length"], row["width"], row["height"]) for row in preset["rows"]],
            [(275.5, 94.2, 63), (63, 23.6, 39.44)],
        )
        self.assertEqual([row["qty"] for row in preset["rows"]], [1, 17])
        self.assertEqual([row["weight"] for row in preset["rows"]], [0, 2])
        prepared = _prepare_transport_analysis(preset["config"], preset["rows"])
        self.assertTrue(prepared["ok"], prepared["messages"])
        for key, value in (("L", 6997.7), ("W", 2392.68), ("H", 2743.454)):
            self.assertAlmostEqual(prepared["container"][key], value, msg=key)
        support, cargo = prepared["products"]
        self.assertAlmostEqual(prepared["container"]["H"] - support["height"], 45.01 * 25.4)
        self.assertAlmostEqual(cargo["height"], 1001.776)
        self.assertEqual(cargo["weight"], 2)
        for row in (support, cargo):
            self.assertTrue(row["stackable"])
            self.assertTrue(row["r3"])
            self.assertFalse(row["r1"] or row["r2"])
            self.assertEqual(row["sequence"], 1)

    def test_constraint_variants_do_not_mutate_their_base_presets(self):
        for slug, base_slug in (
            ("tops-dgfe-shared-loading-group", "tops-max-load-high-cube-benchmark"),
            ("easycargo-40hc-r3-only-dgfe", "easycargo-40hc-mixed-cargo-benchmark"),
            ("48ft-semitrailer-expv2-2-support-beds", "48ft-semitrailer-3stop-benchmark"),
        ):
            with self.subTest(case=slug):
                base = get_transport_container_case_preset(base_slug)
                original_variant = get_transport_container_case_preset(slug)
                edited = get_transport_container_case_preset(slug)
                edited["rows"][0]["length"] = -1
                edited["config"]["container_l"] = -1
                self.assertEqual(get_transport_container_case_preset(base_slug), base)
                self.assertEqual(get_transport_container_case_preset(slug), original_variant)
