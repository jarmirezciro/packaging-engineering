import json
import tempfile
from math import prod

from django.test import TestCase
from django.urls import reverse

from packagingapp.models import PackagingCatalogue, PackagingMaterial
from packagingapp.tests.transport_physical_validator import assert_transport_result_physical
from packagingapp.tools.full_packaging.case_presets import get_case_preset, get_case_titles
from packagingapp.tools.full_packaging.export import build_workflow_report_payload
from packagingapp.tools.transport.service import _prepare_transport_analysis
from packagingapp.units import convert_length, convert_mass
from packagingapp.utils.container_tool.engine import pack_container
from packagingapp.views.full_packaging import (
    _decorate_transport_scene_with_pallet_visualization,
)


class FullPackagingCaseTests(TestCase):
    def setUp(self):
        media = self.enterContext(tempfile.TemporaryDirectory(prefix="kollipack-flow-cases-"))
        self.enterContext(self.settings(MEDIA_ROOT=media))

    def case_url(self, slug):
        return reverse("full_packaging_case", args=[slug])

    def case_steps(self, slug):
        return self.client.session[f"full_packaging_mode_session_case_{slug}"]["steps"]

    def open_case(self, slug):
        response = self.client.get(self.case_url(slug) + "?reset=1", follow=True)
        self.assertEqual(response.status_code, 200)
        return response

    def post_case(self, slug, action, index, **fields):
        response = self.client.post(self.case_url(slug), {
            "action": action, "index": index, **fields,
        })
        self.assertRedirects(response, self.case_url(slug), fetch_redirect_response=False)

    def assert_cleared(self, steps):
        for step in steps:
            for key in ("selected", "pending_result", "result", "threejs_scene", "analysis_report", "selected_result"):
                self.assertIsNone(step[key], (step["type"], key))
            self.assertFalse(step["summary"])

    def test_all_compendium_cases_open_with_complete_json_safe_chains(self):
        expected = {
            "think-beyond-the-box": (("container", "pallet", "transport"), (12, 24, 48)),
            "tops-product-pallet-optimization": (("container", "pallet"), (8, 144)),
            "cape-pack-12-carton-two-layouts": (("container", "pallet"), (12, 20)),
            "capepack-parameter-fine-tuning": (("container", "pallet"), (12, 30)),
            "full-chain-with-bag": (("bag", "container", "pallet", "transport"), (6, 4, 12, 30)),
            "bag-design-final-capacity": (("bag", "container", "pallet"), (4, 24, 8)),
            "mixed-units-across-the-chain": (("container", "pallet", "transport"), (60, 18, 30)),
            "nested-packaging-chain": (("container", "container", "pallet", "transport"), (55, 2, 6, 30)),
            "capepack-bottle-24": (("container", "pallet"), (24, 42)),
            "capepack-bottle-15": (("container", "pallet"), (15, 72)),
            "capepack-bottle-20": (("container", "pallet"), (20, 48)),
        }
        self.assertEqual([slug for slug, _ in get_case_titles()], list(expected))
        compendium = self.client.get(reverse("regressions"))
        for slug, (types, quantities) in expected.items():
            with self.subTest(case=slug):
                self.assertContains(compendium, f'href="{self.case_url(slug)}?reset=1"')
                response = self.open_case(slug)
                steps = self.case_steps(slug)
                self.assertEqual(tuple(step["type"] for step in steps), types)
                for index, (step, quantity) in enumerate(zip(steps, quantities)):
                    payload = step["selected"]
                    self.assertEqual(payload, step["pending_result"])
                    self.assertEqual(payload["units_per_parent"], quantity)
                    self.assertEqual(payload["total_base_units"], prod(quantities[:index + 1]))
                    if index:
                        self.assert_inherited_output(steps[index - 1]["selected"], step)
                summary = response.context["packaging_flow_summary"]
                self.assertTrue(summary["is_complete"])
                self.assertEqual(summary["final"]["value"], f"{prod(quantities):,}")
                json.dumps(steps, allow_nan=False)

    def assert_inherited_output(self, upstream, step):
        config = step["config"]
        step_type = step["type"]
        if step_type == "transport":
            row = config["product_rows"][0]
            for axis in ("length", "width", "height"):
                self.assertAlmostEqual(row[f"canonical_{axis}"], upstream[axis])
            if upstream.get("weight_kg") is None:
                self.assertNotIn("weight_kg", step["selected"])
                self.assertEqual(step["selected"]["weight_status"], "unknown")
                self.assertIsNone(step["result"]["summary"]["gross_weight"])
            else:
                self.assertAlmostEqual(row["canonical_weight"], upstream["weight_kg"], places=10)
            return
        if step_type == "pallet":
            prefix, dimension_unit, mass_unit = "box", "box_dimension_unit", "mass_unit"
        else:
            prefix, dimension_unit, mass_unit = "product", "product_dimension_unit", "product_mass_unit"
        for suffix, axis in zip("lwh", ("length", "width", "height")):
            self.assertAlmostEqual(
                convert_length(float(config[f"{prefix}_{suffix}"]), config[dimension_unit], "mm"),
                upstream[axis],
            )
        weight = config[f"{prefix}_weight"]
        if upstream.get("weight_kg") is None:
            self.assertEqual(weight, "")
        else:
            self.assertAlmostEqual(
                convert_mass(float(weight), config[mass_unit], "kg"), upstream["weight_kg"],
            )

    def test_capepack_bottles_preserve_captured_geometry_and_pallet_controls(self):
        cases = (
            (24, (2.49, 2.49, 10), 3.19, (6, 2, 2), (405.888, 140.718, 524.256),
             1219, (0, 0), (21, 2), (6, 4, 1)),
            (15, (2.52, 2.52, 9.75), 1.19, (5, 3, 1), (343.408, 209.298, 263.906),
             1219.2, (1.45, 1), (18, 4), (15, 1, 1)),
            (20, (2.46, 2.46, 10.25), 1.19, (5, 4, 1), (335.788, 270.258, 276.606),
             1219, (0, 0), (12, 4), (5, 2, 2)),
        )
        for quantity, nominal, weight, arrangement, outer, deck_length_mm, overhang, layers, alternate in cases:
            with self.subTest(bottles_per_carton=quantity):
                slug = f"capepack-bottle-{quantity}"
                self.open_case(slug)
                carton, pallet = self.case_steps(slug)
                config, design, selected = carton["config"], carton["result"], carton["selected"]
                self.assertEqual(config["product_shape"], "bottle")
                self.assertEqual((config["product_dimension_unit"], config["container_dimension_unit"]), ("in", "in"))
                self.assertEqual(config["product_mass_unit"], "lb")
                self.assertEqual(float(config["product_weight"]), weight)
                self.assertEqual((config["r1"], config["r2"], config["r3"]), (False, False, True))
                self.assertEqual(tuple(design[key] for key in ("rows", "columns", "layers")), arrangement)
                self.assertEqual(design["orientation_index"], 0)
                self.assertEqual(selected["box_thickness_mm"], 4.064)
                self.assertEqual(selected["weight_status"], "gross_estimated")
                self.assertEqual(carton["threejs_scene"]["productShape"], "bottle")
                self.assertEqual(len(carton["threejs_scene"]["products"]), quantity)
                for index, (short, axis) in enumerate(zip("lwh", ("length", "width", "height"))):
                    allowance = 0.12 if short in "lw" else 0
                    self.assertEqual(float(config[f"product_{short}"]), nominal[index])
                    self.assertEqual(float(config[f"product_allowance_{short}"]), allowance)
                    self.assertAlmostEqual(
                        carton["product_unit_scene"]["productDefinition"][axis],
                        convert_length(nominal[index], "in", "mm"),
                    )
                    self.assertAlmostEqual(
                        selected[f"internal_{axis}"],
                        convert_length((nominal[index] + allowance) * arrangement[index], "in", "mm"),
                        delta=0.00501,
                    )
                    self.assertAlmostEqual(selected[axis], outer[index])
                    self.assertAlmostEqual(pallet["threejs_scene"]["case"][axis], outer[index])

                cfg, result, scene = pallet["config"], pallet["selected_result"], pallet["threejs_scene"]
                self.assertEqual((cfg["box_dimension_unit"], cfg["pallet_dimension_unit"], cfg["mass_unit"]), ("in", "in", "lb"))
                self.assertEqual((cfg["pallet_w"], cfg["max_stack_height"]), (40, 50))
                self.assertEqual((cfg["max_length_stickout"], cfg["max_width_stickout"]), overhang)
                self.assertAlmostEqual(scene["pallet"]["length"], deck_length_mm)
                self.assertAlmostEqual(scene["pallet"]["height"], 141)
                self.assertEqual((result["boxes_layer_A"], result["layers"]), layers)
                self.assertEqual(len(scene["placements"]), prod(layers))
                self.assertEqual(pallet["selected"]["total_base_units"], quantity * prod(layers))

                alternate_candidate = next(
                    row for row in carton["design_candidates"]
                    if tuple(row[key] for key in ("rows", "columns", "layers")) == alternate
                )
                self.post_case(
                    slug, "run_step", 0, step_action_0="select_design_candidate",
                    selected_design_candidate_id_0=alternate_candidate["candidate_id"],
                )
                self.post_case(slug, "use_step_result", 0)
                self.assert_cleared(self.case_steps(slug)[1:])
                self.post_case(slug, "run_step", 1, step_action_1="run_analysis", max_stack_height_1="35")
                edited_carton, edited_pallet = self.case_steps(slug)
                self.assertEqual(edited_carton["selected"]["selected_candidate_id"], alternate_candidate["candidate_id"])
                self.assertEqual(float(edited_pallet["config"]["max_stack_height"]), 35)
                self.assert_inherited_output(edited_carton["selected"], edited_pallet)
                self.assertEqual(
                    edited_pallet["pending_result"]["total_base_units"],
                    quantity * edited_pallet["selected_result"]["total_boxes"],
                )
                self.open_case(slug)
                reset_carton, reset_pallet = self.case_steps(slug)
                self.assertEqual(reset_carton["selected"], selected)
                self.assertEqual(reset_pallet["config"], cfg)
                self.assertEqual(reset_pallet["selected"]["total_base_units"], quantity * prod(layers))

    def test_think_beyond_the_box_compact_alternative_recalculates_the_chain(self):
        slug = "think-beyond-the-box"
        self.open_case(slug)
        compact = self.design_candidate(slug, (500, 300, 300))
        self.post_case(
            slug, "run_step", 0, step_action_0="select_design_candidate",
            selected_design_candidate_id_0=compact["candidate_id"],
        )
        self.post_case(slug, "use_step_result", 0)
        self.assert_cleared(self.case_steps(slug)[1:])
        self.post_case(slug, "run_step", 1, step_action_1="run_analysis")
        self.post_case(slug, "run_step", 2, step_action_2="run_analysis")
        _, pallet, transport = self.case_steps(slug)
        self.assertEqual(pallet["pending_result"]["units_per_parent"], 20)
        self.assertEqual(transport["pending_result"]["units_per_parent"], 48)
        self.assertEqual(transport["pending_result"]["total_base_units"], 11520)

    def design_candidate(self, slug, dimensions):
        return next(
            row for row in self.case_steps(slug)[0]["design_candidates"]
            if tuple(row[f"container_{axis}"] for axis in ("length", "width", "height")) == dimensions
        )

    def test_tops_sixteen_pack_recalculates_with_the_article_carton_geometry(self):
        slug = "tops-product-pallet-optimization"
        self.open_case(slug)
        self.post_case(slug, "run_step", 0, step_action_0="run_design", desired_qty_0="16")
        candidate = self.design_candidate(slug, (356, 280, 153))
        self.post_case(
            slug, "run_step", 0, step_action_0="select_design_candidate",
            selected_design_candidate_id_0=candidate["candidate_id"],
        )
        self.post_case(slug, "use_step_result", 0)
        self.assert_cleared(self.case_steps(slug)[1:])
        self.post_case(slug, "run_step", 1, step_action_1="run_analysis")
        carton, pallet = self.case_steps(slug)
        self.assertEqual(tuple(carton["selected"][axis] for axis in ("length", "width", "height")), (364, 288, 169))
        self.assert_inherited_output(carton["selected"], pallet)
        self.assertEqual(pallet["pending_result"]["units_per_parent"], 77)
        self.assertEqual(pallet["pending_result"]["total_base_units"], 1232)

    def test_bag_case_uses_the_bundle_envelope_and_propagates_tare_once(self):
        slug = "full-chain-with-bag"
        self.open_case(slug)
        bag, carton, pallet, transport = self.case_steps(slug)
        self.assertEqual((bag["result"]["bag_len"], bag["result"]["bag_w"]), (450, 330))
        self.assertEqual(tuple(bag["selected"][axis] for axis in ("length", "width", "height")), (318, 208, 120))
        self.assertEqual(bag["selected"]["weight_g"], 1518)
        self.assertEqual(carton["selected"]["net_content_weight_g"], 6072)
        self.assertEqual(carton["selected"]["carton_tare_g"], 450)
        self.assertAlmostEqual(pallet["selected"]["weight_kg"], 78.264)
        self.assertAlmostEqual(transport["selected"]["weight_kg"], 1000 + 30 * 78.264)

        self.post_case(slug, "run_step", 0, action_0="run_single", bag_weight_0="20")
        self.post_case(slug, "use_step_result", 0)
        self.assert_cleared(self.case_steps(slug)[1:])
        self.post_case(slug, "run_step", 1, action_1="run_single")
        catalogue = PackagingCatalogue.objects.create(name="Flow case test pallets")
        test_pallet = PackagingMaterial.objects.create(
            catalogue=catalogue, packaging_type="PALLET", part_number="Flow test pallet",
            part_length=1200, part_width=800, part_height=144, part_weight=25,
        )
        self.post_case(
            slug, "run_step", 2, step_action_2="run_analysis", pallet_source_2="catalogue",
            pallet_catalogue_id_2=catalogue.pk, pallet_id_2=test_pallet.pk, max_pallet_load_2="80000",
        )
        self.post_case(slug, "run_step", 3, step_action_3="run_analysis")
        pallet, transport = self.case_steps(slug)[2:]
        cargo_g = pallet["selected_result"]["actual_pallet_load_g"]
        self.assertAlmostEqual(cargo_g, 12 * 6530)
        self.assertLess(cargo_g, 80000)
        self.assertAlmostEqual(pallet["pending_result"]["weight_kg"], 103.36)
        self.assertAlmostEqual(transport["pending_result"]["weight_kg"], 1000 + 30 * 103.36)
        self.assertEqual(transport["pending_result"]["total_base_units"], 8640)

    def test_bag_design_ranks_and_recalculates_a_real_alternative(self):
        slug = "bag-design-final-capacity"
        self.open_case(slug)
        self.post_case(slug, "optimize_design_final_capacity", 0)
        bag, carton, pallet = self.case_steps(slug)
        ranking = bag["design_chain_optimization"]
        best = ranking["sorted_candidate_ids"][0]
        self.assertEqual(ranking["candidate_results"][best]["final_base_units"], 4032)
        self.assertNotEqual(bag["selected_design_candidate_id"], best)
        original_order = [row["candidate_id"] for row in bag["design_candidates"]]
        self.assertEqual(pallet["selected"]["total_base_units"], 768)

        self.post_case(
            slug, "run_step", 0, action_0="select_design_candidate",
            selected_design_candidate_id_0=best,
        )
        self.post_case(slug, "use_step_result", 0)
        bag, carton, pallet = self.case_steps(slug)
        self.assertEqual(bag["selected"]["selected_candidate_id"], best)
        self.assertEqual([row["candidate_id"] for row in bag["design_candidates"]], original_order)
        self.assertEqual(bag["design_chain_optimization"], ranking)
        self.assert_cleared((carton, pallet))
        self.post_case(slug, "run_step", 1, action_1="run_single")
        self.post_case(slug, "run_step", 2, step_action_2="run_analysis")
        bag, carton, pallet = self.case_steps(slug)
        self.assert_inherited_output(bag["selected"], carton)
        self.assertLess(
            carton["pending_result"]["net_content_weight_g"],
            float(carton["config"]["box_max_payload"]),
        )
        self.assertEqual(pallet["pending_result"]["total_base_units"], 4032)

    def test_mixed_units_survive_transport_rerun_and_match_the_report(self):
        slug = "mixed-units-across-the-chain"
        response = self.open_case(slug)
        steps = self.case_steps(slug)
        carton, pallet, transport = steps
        self.assertEqual(carton["config"]["product_dimension_unit"], "in")
        self.assertEqual(carton["config"]["product_mass_unit"], "lb")
        self.assertEqual(pallet["config"]["box_dimension_unit"], "in")
        self.assertEqual(pallet["config"]["pallet_dimension_unit"], "mm")
        self.assertEqual(pallet["config"]["mass_unit"], "kg")
        row = response.context["steps"][2]["product_rows"][0]
        self.assertNotEqual(
            convert_mass(float(row["weight"]), "lb", "kg"), pallet["selected"]["weight_kg"],
        )
        self.post_case(slug, "run_step", 2, step_action_2="run_analysis", **{
            f"item_{key}[]": [row[key]] for key in ("length", "width", "height", "weight", "name")
        }, **{"item_max_qty[]": ["1"], "item_r3[]": ["1"], "item_stackable[]": ["1"]})
        updated = self.case_steps(slug)[2]
        self.assertEqual(updated["pending_result"], transport["selected"])
        self.assertEqual(updated["threejs_scene"]["items"], transport["threejs_scene"]["items"])
        report = build_workflow_report_payload({"steps": steps})["steps"]
        self.assertTrue(report[0]["output"]["dimensions_display"].endswith(" cm"))
        self.assertTrue(report[1]["input"]["dimensions_display"].endswith(" in"))
        self.assertTrue(report[1]["input"]["weight_display"].endswith(" kg"))
        self.assertTrue(report[2]["input"]["dimensions_display"].endswith(" ft"))
        self.assertTrue(report[2]["input"]["weight_display"].endswith(" lb"))
        self.assertEqual(report[2]["output"]["total_base_units"], 32400)
        self.post_case(slug, "run_step", 0, action_0="run_single", box_weight_0="500")
        self.post_case(slug, "use_step_result", 0)
        self.assert_cleared(self.case_steps(slug)[1:])
        self.post_case(slug, "run_step", 1, step_action_1="run_analysis")
        self.post_case(slug, "run_step", 2, step_action_2="run_analysis")
        carton, pallet, transport = self.case_steps(slug)
        self.assert_inherited_output(carton["selected"], pallet)
        self.assert_inherited_output(pallet["pending_result"], transport)
        self.assertEqual(transport["pending_result"]["total_base_units"], 32400)

    def test_nested_case_invalidation_reset_and_session_independence(self):
        slug = "nested-packaging-chain"
        response = self.open_case(slug)
        self.assertContains(response, 'name="box_l_0"')
        self.assertContains(response, 'name="box_l_1"')
        first_ui, second_ui = (step["container_ui"] for step in response.context["steps"][:2])
        for key in ("product_unit_viewer", "product_unit_scene"):
            self.assertNotEqual(first_ui["ids"][key], second_ui["ids"][key])
            for ui in (first_ui, second_ui):
                self.assertContains(response, f'id="{ui["ids"][key]}"', count=1)
        preset = get_case_preset(slug)
        inner, outer, pallet, transport = self.case_steps(slug)
        self.assertEqual(float(inner["config"]["product_allowance_l"]), 5)
        self.assertEqual(float(outer["config"]["product_allowance_l"]), 0)
        self.assertAlmostEqual(outer["selected"]["weight_kg"], 2 * inner["selected"]["weight_kg"] + 0.65)
        self.post_case(slug, "toggle_step", 1)
        response = self.client.get(self.case_url(slug))
        self.assertFalse(response.context["steps"][1]["expanded"])
        self.assertEqual(response.context["packaging_flow_summary"]["final"]["value"], "19,800")

        self.post_case(slug, "run_step", 0, action_0="run_single")
        self.assertEqual(self.case_steps(slug)[3]["selected"], transport["selected"])
        self.post_case(slug, "run_step", 0, action_0="run_single", box_weight_0="500")
        self.post_case(slug, "use_step_result", 0)
        cleared_steps = self.case_steps(slug)
        self.assert_cleared(cleared_steps[1:])
        self.assertEqual(cleared_steps[1]["config"]["box_l"], outer["config"]["box_l"])
        report = build_workflow_report_payload({"steps": cleared_steps})
        self.assertEqual(dict(report["steps"][2]["metrics"])["Total cartons"], "-")
        response = self.client.get(self.case_url(slug))
        self.assertEqual(response.context["packaging_flow_summary"]["completed_count"], 1)
        self.post_case(slug, "run_step", 1, action_1="run_single")
        self.assertAlmostEqual(self.case_steps(slug)[1]["pending_result"]["weight_kg"], 51.54516)

        self.open_case("full-chain-with-bag")
        self.assertEqual(self.case_steps(slug)[0]["selected"]["carton_tare_g"], 500)
        self.assertEqual(self.client.get(reverse("full_packaging_mode")).context["steps"], [])
        self.assertEqual(self.client.get(self.case_url("missing-case")).status_code, 404)
        self.assertEqual(self.client.get(self.case_url("missing-case") + "?reset=1").status_code, 404)
        self.assertEqual(get_case_preset(slug), preset)
        self.open_case(slug)
        self.assertEqual(self.case_steps(slug)[3]["selected"], transport["selected"])
        self.assertEqual(self.case_steps(slug)[0]["selected"]["carton_tare_g"], 450)

    def test_capepack_parameter_fine_tuning_case_reproduces_twelve_and_sixteen_unit_results(self):
        case_url = reverse(
            "full_packaging_case",
            args=["capepack-parameter-fine-tuning"],
        )
        response = self.client.get(case_url + "?reset=1", follow=True)

        self.assertEqual(response.status_code, 200)
        session_key = (
            "full_packaging_mode_session_case_capepack-parameter-fine-tuning"
        )
        workflow = self.client.session[session_key]
        self.assertEqual(
            [step["type"] for step in workflow["steps"]],
            ["container", "pallet"],
        )

        container = workflow["steps"][0]
        self.assertEqual(container["config"]["product_dimension_unit"], "in")
        self.assertEqual(container["config"]["product_mass_unit"], "lb")
        self.assertTrue(container["config"]["r1"])
        self.assertTrue(container["config"]["r2"])
        self.assertTrue(container["config"]["r3"])
        self.assertEqual(container["config"]["box_thickness_mm"], "0.16")
        designs = {
            tuple(row["container_dimensions_display"].split(" × ")): row
            for row in container["design_candidates"]
        }
        self.assertIn(("18", "8", "20 in"), designs)

        pallet = workflow["steps"][1]
        self.assertEqual(pallet["config"]["box_dimension_unit"], "in")
        self.assertEqual(pallet["config"]["pallet_dimension_unit"], "in")
        self.assertEqual(pallet["config"]["mass_unit"], "lb")
        self.assertEqual(pallet["config"]["pallet_l"], 48)
        self.assertEqual(pallet["config"]["pallet_w"], 40)
        self.assertEqual(pallet["config"]["pallet_height"], 5.5)
        self.assertEqual(pallet["config"]["max_stack_height"], 72)
        self.assertEqual(pallet["config"]["max_pallet_load"], 2000)
        self.assertEqual(pallet["config"]["max_width_stickout"], 0)
        self.assertEqual(pallet["config"]["max_length_stickout"], 0)
        self.assertEqual(pallet["selected_result"]["total_boxes"], 30)
        self.assertEqual(pallet["pending_result"]["total_base_units"], 360)
        json.dumps(workflow)

        response = self.client.post(
            case_url,
            {
                "action": "run_step",
                "index": "0",
                "mode_0": "design",
                "product_source_0": "manual",
                "container_source_0": "manual",
                "product_l_0": "6",
                "product_w_0": "5",
                "product_h_0": "8",
                "product_weight_0": "2.25",
                "product_dimension_unit_0": "in",
                "product_mass_unit_0": "lb",
                "desired_qty_0": "16",
                "box_thickness_mm_0": "0.16",
                "container_dimension_unit_0": "in",
                "container_mass_unit_0": "lb",
                "r1_0": "on",
                "r2_0": "on",
                "r3_0": "on",
                "step_action_0": "run_design",
            },
        )
        self.assertEqual(response.status_code, 302)

        workflow = self.client.session[session_key]
        container = workflow["steps"][0]
        designs = {
            tuple(row["container_dimensions_display"].split(" × ")): row
            for row in container["design_candidates"]
        }
        self.assertIn(("16", "12", "20 in"), designs)

        response = self.client.post(
            case_url,
            {
                "action": "run_step",
                "index": "0",
                "step_action_0": "select_design_candidate",
                "selected_design_candidate_id_0": designs[("16", "12", "20 in")][
                    "candidate_id"
                ],
            },
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            case_url,
            {"action": "use_step_result", "index": "0"},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            case_url,
            {
                "action": "run_step",
                "index": "1",
                "step_action_1": "run_analysis",
            },
        )
        self.assertEqual(response.status_code, 302)

        workflow = self.client.session[session_key]
        self.assertEqual(
            workflow["steps"][0]["selected"]["internal_length"],
            406.4,
        )
        self.assertEqual(workflow["steps"][1]["selected_result"]["total_boxes"], 24)
        self.assertEqual(
            workflow["steps"][1]["pending_result"]["total_base_units"],
            384,
        )
        json.dumps(workflow)

    def test_cape_pack_benchmark_case_exposes_both_designs_and_prefills_pallet(self):
        case_url = reverse(
            "full_packaging_case",
            args=["cape-pack-12-carton-two-layouts"],
        )
        response = self.client.get(case_url + "?reset=1", follow=True)

        self.assertEqual(response.status_code, 200)
        workflow = self.client.session[
            "full_packaging_mode_session_case_cape-pack-12-carton-two-layouts"
        ]
        self.assertEqual(
            [step["type"] for step in workflow["steps"]],
            ["container", "pallet"],
        )

        container = workflow["steps"][0]
        self.assertEqual(container["config"]["product_dimension_unit"], "in")
        self.assertFalse(container["config"]["r1"])
        self.assertFalse(container["config"]["r2"])
        self.assertTrue(container["config"]["r3"])
        designs = {
            tuple(row["container_dimensions_display"].split(" × ")): row
            for row in container["design_candidates"]
        }
        self.assertIn(("15", "12", "16 in"), designs)
        self.assertIn(("20", "18", "8 in"), designs)

        pallet = workflow["steps"][1]
        self.assertEqual(pallet["config"]["box_dimension_unit"], "in")
        self.assertEqual(pallet["config"]["pallet_dimension_unit"], "in")
        self.assertEqual(pallet["config"]["mass_unit"], "lb")
        self.assertEqual(pallet["config"]["pallet_l"], 48)
        self.assertEqual(pallet["config"]["pallet_w"], 40)
        self.assertEqual(pallet["config"]["pallet_height"], 5.5)
        self.assertEqual(pallet["config"]["max_stack_height"], 50)
        self.assertEqual(pallet["config"]["max_pallet_load"], 2000)
        self.assertEqual(pallet["selected_result"]["total_boxes"], 20)
        self.assertEqual(pallet["pending_result"]["total_base_units"], 240)
        json.dumps(workflow)

        response = self.client.post(
            case_url,
            {
                "action": "run_step",
                "index": "0",
                "step_action_0": "select_design_candidate",
                "selected_design_candidate_id_0": designs[("15", "12", "16 in")][
                    "candidate_id"
                ],
            },
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            case_url,
            {"action": "use_step_result", "index": "0"},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            case_url,
            {
                "action": "run_step",
                "index": "1",
                "step_action_1": "run_analysis",
            },
        )
        self.assertEqual(response.status_code, 302)
        workflow = self.client.session[
            "full_packaging_mode_session_case_cape-pack-12-carton-two-layouts"
        ]
        self.assertEqual(workflow["steps"][1]["selected_result"]["total_boxes"], 18)
        self.assertEqual(workflow["steps"][1]["pending_result"]["total_base_units"], 216)
        json.dumps(workflow)

    def test_think_beyond_the_box_case_loads_and_remains_json_safe(self):
        case_url = reverse("full_packaging_case", args=["think-beyond-the-box"])
        for query in ("", "?reset=1"):
            with self.subTest(query=query):
                response = self.client.get(case_url + query, follow=True)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.context["case_preset"]["slug"],
                    "think-beyond-the-box",
                )
                self.assertEqual(
                    [step["type"] for step in response.context["steps"]],
                    ["container", "pallet", "transport"],
                )

        session = self.client.session
        workflow = session["full_packaging_mode_session_case_think-beyond-the-box"]
        self.assertEqual(
            [step["type"] for step in workflow["steps"]],
            ["container", "pallet", "transport"],
        )
        pallet_step = workflow["steps"][1]
        transport_scene = workflow["steps"][2]["threejs_scene"]
        self.assertEqual(
            pallet_step["config"]["max_width_stickout"],
            25.4,
        )
        self.assertEqual(
            pallet_step["config"]["max_length_stickout"],
            25.4,
        )
        self.assertEqual(pallet_step["pending_result"]["length"], 1225.4)
        self.assertEqual(pallet_step["pending_result"]["width"], 825.4)
        self.assertEqual(pallet_step["config"]["pallet_height"], 80.0)
        self.assertEqual(pallet_step["config"]["max_stack_height"], 1350)
        transport_row = workflow["steps"][2]["config"]["product_rows"][0]
        self.assertFalse(transport_row["r1"])
        self.assertFalse(transport_row["r2"])
        self.assertTrue(transport_row["r3"])
        self.assertTrue(transport_row["stackable"])
        self.assertEqual(
            workflow["steps"][2]["result"]["summary"]["placed_units"],
            48,
        )
        self.assertEqual(
            workflow["steps"][2]["result"]["summary"]["occupied_height"],
            2688.0,
        )
        self.assertEqual(
            transport_scene["metadata"]["detailed_pallet_items"],
            len(transport_scene["items"]),
        )
        self.assertContains(response, "palletization_result")
        self.assertTrue(transport_scene["items"])
        self.assertTrue(
            all(
                item["source_type"] == "palletization_result"
                and item["visualization_ref"] == "palletized_load"
                and item["pallet_orientation"]
                for item in transport_scene["items"]
            )
        )
        self.assertTrue(
            all(item["pallet_orientation"] in ("lwh", "wlh") for item in transport_scene["items"])
        )
        self.assertNotIn(
            'onchange="fpTransportSyncCheckboxHidden(this)" disabled',
            response.content.decode(),
        )
        self.assertEqual(
            transport_scene["workflow_visualizations"]["palletized_load"]["bounds"][
                "center_x"
            ],
            600.0,
        )
        transport = workflow["steps"][2]
        prepared = _prepare_transport_analysis(transport["config"], [transport_row])
        self.assertTrue(prepared["ok"], prepared["messages"])
        container, products = prepared["container"], prepared["products"]
        engine = pack_container(container, products)
        assert_transport_result_physical(self, engine, container, products)
        self.assertEqual(
            [tuple(item[k] for k in ("x", "y", "z", "dx", "dy", "dz")) for item in transport_scene["items"]],
            [(p.x, p.y, p.z, p.l, p.w, p.h) for p in engine["placements"]],
        )
        assembly = transport_scene["workflow_visualizations"]["palletized_load"]["scene"]
        self.assertEqual(assembly["pallet"]["height"], 80)
        self.assertEqual({carton["z"] for carton in assembly["placements"]}, {80, 396, 712, 1028})
        self.assertEqual(
            max(carton["z"] + carton["dz"] for carton in assembly["placements"]), 1344,
        )
        json.dumps(workflow)

    def test_direct_pallet_visualization_normalizes_base_height_with_overhang(self):
        transport_scene = {
            "items": [{
                "x": 0,
                "y": 0,
                "z": 0,
                "dx": 1225.4,
                "dy": 825.4,
                "dz": 600,
            }],
            "metadata": {"total_items": 1},
        }
        upstream = {
            "source_type": "palletization_result",
            "length": 1225.4,
            "width": 825.4,
            "height": 600,
            "pallet_visualization": {
                "pallet": {
                    "length": 1200,
                    "width": 800,
                    "height": 108,
                    "deck_thickness": 20,
                },
                "allowed_footprint": {
                    "x": -12.7,
                    "y": -12.7,
                    "length": 1225.4,
                    "width": 825.4,
                },
                "placements": [{
                    "x": 4,
                    "y": 6,
                    "z": 108,
                    "dx": 400,
                    "dy": 400,
                    "dz": 500,
                }],
            },
        }

        decorated = _decorate_transport_scene_with_pallet_visualization(
            transport_scene,
            upstream,
        )
        visualization = decorated["workflow_visualizations"]["palletized_load"]

        self.assertEqual(
            visualization["scene"]["pallet"]["height"],
            100.0,
        )
        self.assertEqual(
            visualization["scene"]["placements"][0]["z"],
            100.0,
        )
        self.assertEqual(visualization["bounds"]["center_x"], 600.0)
        self.assertEqual(
            decorated["items"][0]["source_type"],
            "palletization_result",
        )

    def test_inherited_transport_orientation_and_stackability_choices_are_editable(self):
        case_url = reverse("full_packaging_case", args=["think-beyond-the-box"])
        self.client.get(case_url + "?reset=1")

        session = self.client.session
        key = "full_packaging_mode_session_case_think-beyond-the-box"
        row = session[key]["steps"][2]["config"]["product_rows"][0]
        response = self.client.post(
            case_url,
            {
                "action": "run_step",
                "index": "2",
                "step_action_2": "run_analysis",
                "container_source_2": "manual",
                "packing_mode_2": "front_to_back",
                "container_l_2": "12032",
                "container_w_2": "2352",
                "container_h_2": "2698",
                "max_weight_2": "26000",
                "tare_weight_2": "",
                "item_name[]": [row["name"]],
                "item_length[]": [str(row["length"])],
                "item_width[]": [str(row["width"])],
                "item_height[]": [str(row["height"])],
                "item_qty[]": ["1"],
                "item_max_qty[]": ["1"],
                "item_stackable[]": ["1"],
                "item_weight[]": ["0"],
                "item_sequence[]": ["1"],
                "item_r1[]": ["1"],
                "item_r2[]": ["1"],
                "item_r3[]": ["0"],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.client.get(case_url)
        updated_row = self.client.session[key]["steps"][2]["config"]["product_rows"][0]
        self.assertTrue(updated_row["r1"])
        self.assertTrue(updated_row["r2"])
        self.assertFalse(updated_row["r3"])
        self.assertTrue(updated_row["stackable"])
