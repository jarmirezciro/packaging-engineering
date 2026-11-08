import json
import tempfile
from html.parser import HTMLParser
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

from packagingapp.models import UserPreferences
from packagingapp.tools.transport.case_presets import (
    TRANSPORT_CONTAINER_CASE_PRESETS,
    get_transport_container_case_preset,
)
from packagingapp.tools.transport.service import _prepare_transport_analysis


NEW_REGRESSION_CASE_SLUGS = (
    "p1-p2-imperial-supported-roof",
    "40hc-euro-pallet-unequal-lane-tails",
    "tops-dgfe-shared-loading-group",
    "easycargo-40hc-r3-only-dgfe",
    "48ft-semitrailer-expv2-2-support-beds",
)


class CaseLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href", "")
        if tag == "a" and href.startswith(f"{reverse('container_tool')}?case="):
            self.links.append(href)


class RegressionCompendiumTests(TestCase):
    def setUp(self):
        media_root = tempfile.TemporaryDirectory(prefix="kollipack-cases-")
        self.addCleanup(media_root.cleanup)
        settings = self.settings(MEDIA_ROOT=media_root.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def case_links(self, response):
        parser = CaseLinkParser()
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
                    self.assertAlmostEqual(actual[key], value, msg=key)
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
        self.assertRedirects(
            self.client.get("/regressions/", HTTP_HOST="localhost"),
            "/regressions",
            301,
            fetch_redirect_response=False,
        )

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


class RegressionPresetSourceTests(SimpleTestCase):
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
