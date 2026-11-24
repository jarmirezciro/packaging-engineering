import json
import tempfile
from copy import deepcopy
from math import prod
from unittest.mock import patch

from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from packagingapp.models import PackagingCatalogue, PackagingMaterial
from packagingapp.tests.transport_physical_validator import assert_transport_result_physical
from packagingapp.tools.full_packaging.case_presets import get_case_preset, get_case_titles
from packagingapp.tools.full_packaging.chain_optimizer import optimize_design_chain
from packagingapp.tools.full_packaging.export import build_workflow_report_payload
from packagingapp.tools.bag.service import analyze_bag_capacity, analyze_bag_config
from packagingapp.tools.transport.service import _prepare_transport_analysis
from packagingapp.units import convert_length, convert_mass
from packagingapp.utils.container_tool.engine import pack_container
from packagingapp.utils.bag_selection.engine import BAG_DESIGN_ROTATION_ERROR
from packagingapp.views import full_packaging as flow
from packagingapp.views.full_packaging import (
    _decorate_transport_scene_with_pallet_visualization,
    _evaluate_design_chain_step,
)
from packagingapp.utils.palletization.geometry import palletized_load_footprint


BAG_PALLET_CASE = "calibration-bag-terminal-and-downstream"
BAG_PALLET_A = "bag-design-000b08eec76829dc"
BAG_PALLET_B = "bag-design-87f77f08f2620cb4"


class PalletizedLoadFootprintTests(SimpleTestCase):
    def test_footprint_includes_pallet_all_layers_and_asymmetric_bounds(self):
        footprint = palletized_load_footprint(
            1219.2,
            1016.0,
            [
                {"x": -6.35, "y": 4.0, "dx": 300.0, "dy": 400.0},
                {"x": 900.0, "y": -12.7, "dx": 400.0, "dy": 100.0},
                {"x": 400.0, "y": 900.0, "dx": 250.0, "dy": 200.0},
            ],
        )

        self.assertEqual(
            {
                key: footprint[key]
                for key in ("min_x", "max_x", "min_y", "max_y")
            },
            {"min_x": -6.35, "max_x": 1300.0, "min_y": -12.7, "max_y": 1100.0},
        )
        self.assertEqual(footprint["length"], 1306.35)
        self.assertEqual(footprint["width"], 1112.7)
        self.assertEqual(footprint["center_x"], (1300.0 - 6.35) / 2.0)
        self.assertEqual(footprint["center_y"], (1100.0 - 12.7) / 2.0)
        self.assertEqual(footprint["placement_count"], 3)

    def test_empty_or_invalid_placements_fall_back_to_physical_pallet(self):
        footprint = palletized_load_footprint(
            1219.2,
            1016.0,
            [None, {"x": "invalid", "y": 0, "dx": 10, "dy": 10}],
        )

        self.assertEqual(footprint["length"], 1219.2)
        self.assertEqual(footprint["width"], 1016.0)
        self.assertEqual(footprint["center_x"], 609.6)
        self.assertEqual(footprint["center_y"], 508.0)
        self.assertEqual(footprint["placement_count"], 0)


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

    def select_bag_for_pallet(self, candidate_id, **fields):
        self.post_case(BAG_PALLET_CASE, "run_step", 0, action_0="select_design_candidate",
                       selected_design_candidate_id_0=candidate_id, **fields)
        self.post_case(BAG_PALLET_CASE, "use_step_result", 0)

    def run_bag_pallet(self, **fields):
        self.post_case(BAG_PALLET_CASE, "run_step", 1, step_action_1="run_analysis", **fields)

    def start_bag_pallet(self, length=200, width=200, candidate_id=BAG_PALLET_A):
        self.open_case(BAG_PALLET_CASE)
        self.post_case(BAG_PALLET_CASE, "add_step", 0, step_type="pallet")
        self.select_bag_for_pallet(candidate_id)
        self.run_bag_pallet(pallet_l_1=length, pallet_w_1=width, pallet_height_1=100, max_stack_height_1=410)

    def test_same_flat_bag_uses_selected_outer_axes_mass_and_pattern_in_both_pallet_paths(self):
        self.start_bag_pallet()
        catalogue = PackagingCatalogue.objects.create(name="Calibration pallets", is_public=True)
        material = PackagingMaterial.objects.create(
            catalogue=catalogue, packaging_type="PALLET", part_number="Bag calibration pallet",
            part_length=200, part_width=200, part_height=100, part_weight=1.5,
        )
        self.assertEqual(self.case_steps(BAG_PALLET_CASE)[1]["pending_result"]["units_per_parent"], 4)
        self.run_bag_pallet(
            pallet_source_1="catalogue", pallet_catalogue_id_1=catalogue.pk, pallet_id_1=material.pk,
            box_dimension_unit_1="in", pallet_dimension_unit_1="in", mass_unit_1="lb",
            max_stack_height_1=convert_length(410, "mm", "in"),
            max_pallet_load_1=convert_mass(10000, "g", "lb"),
            max_weight_on_bottom_box_1=convert_mass(2000, "g", "lb"),
        )
        controls = None
        for candidate_id, external, count, insertion in (
            (BAG_PALLET_A, (120.06096, 90.06096, 150.06096), 4, "height"),
            (BAG_PALLET_B, (180.06096, 60.06096, 150.06096), 6, "length"),
        ):
            with self.subTest(candidate=candidate_id):
                if candidate_id == BAG_PALLET_B:
                    self.select_bag_for_pallet(candidate_id)
                    self.assert_cleared(self.case_steps(BAG_PALLET_CASE)[1:])
                    self.run_bag_pallet()
                steps = self.case_steps(BAG_PALLET_CASE)
                bag, pallet = steps
                filled_bag = bag["selected"]
                self.assertEqual(filled_bag["selected_candidate_id"], candidate_id)
                self.assertEqual(filled_bag["insertion"]["axis"], insertion)
                self.assertEqual(bag["threejs_scene"]["bag"]["film"]["depthAxis"], insertion)
                self.assertEqual((filled_bag["flat_bag_length_mm"], filled_bag["flat_bag_width_mm"]), (252, 212))
                self.assertEqual(tuple(filled_bag[axis] for axis in ("length", "width", "height")), external)
                self.assertEqual(filled_bag["net_content_weight_g"], 1200)
                self.assertAlmostEqual(filled_bag["bag_tare_g"], 2.9961888768)
                self.assertAlmostEqual(filled_bag["weight_g"], 1200 + filled_bag["bag_tare_g"])
                self.assert_inherited_output(filled_bag, pallet)
                self.assertNotIn("bag_rotation_inheritance", pallet)
                cfg = pallet["config"]
                independent = {key: value for key, value in cfg.items() if key not in {"box_l", "box_w", "box_h", "box_weight"}}
                if controls is None:
                    controls = independent
                self.assertEqual(independent, controls)
                self.assertEqual(cfg["pallet_id"], str(material.pk))
                row = pallet["selected_result"]
                self.assertEqual(row["pattern"], "Block")
                self.assertEqual(row["total_boxes"], count)
                self.assertAlmostEqual(row["actual_pallet_load_g"], count * filled_bag["weight_g"])
                self.assertAlmostEqual(pallet["pending_result"]["weight_g"], count * filled_bag["weight_g"] + 1500)
                self.assertEqual(pallet["pending_result"]["total_base_units"], count * 12)
                self.assertEqual(pallet["pending_result"]["weight_status"], "gross_estimated")
                self.assertEqual(_evaluate_design_chain_step(deepcopy(steps), 1), pallet["pending_result"])
                for placement in pallet["threejs_scene"]["placements"]:
                    self.assertAlmostEqual(placement["dz"], external[2])
                    for actual, expected in zip(sorted((placement["dx"], placement["dy"])), sorted(external[:2])):
                        self.assertAlmostEqual(actual, expected)
                report = build_workflow_report_payload({"steps": steps})["steps"][1]
                self.assertEqual(dict(report["metrics"])["Total cartons"], str(count))
                self.assertIn("Actual pallet load", dict(report["metrics"]))
                json.dumps(steps, allow_nan=False)

    def test_bag_pallet_optimizer_keeps_all_candidates_for_different_and_equal_capacities(self):
        self.start_bag_pallet()
        for length, width, expected in ((200, 200, (48, 72)), (250, 190, (96, 96))):
            with self.subTest(pallet=(length, width)):
                self.run_bag_pallet(pallet_l_1=length, pallet_w_1=width)
                before = self.case_steps(BAG_PALLET_CASE)
                self.post_case(BAG_PALLET_CASE, "optimize_design_final_capacity", 0)
                bag, pallet = self.case_steps(BAG_PALLET_CASE)
                self.assertEqual(pallet, before[1])
                self.assertEqual(bag["design_candidates"], before[0]["design_candidates"])
                self.assertEqual(bag["selected"], before[0]["selected"])
                candidates = bag["design_candidates"]
                optimization = bag["design_chain_optimization"]
                trials = optimization["candidate_results"]
                self.assertEqual(len(candidates), 148)
                self.assertEqual(set(trials), {candidate["candidate_id"] for candidate in candidates})
                self.assertEqual(tuple(trials[candidate]["final_base_units"] for candidate in (BAG_PALLET_A, BAG_PALLET_B)), expected)
                order = optimization["sorted_candidate_ids"]
                first, second = (BAG_PALLET_B, BAG_PALLET_A) if expected[0] != expected[1] else (BAG_PALLET_A, BAG_PALLET_B)
                self.assertLess(order.index(first), order.index(second))
                successful = [candidate_id for candidate_id in order if trials[candidate_id]["status"] == "ok"]
                area_ranks = {candidate["candidate_id"]: candidate["rank"] for candidate in candidates}
                scores = [(-trials[candidate_id]["final_base_units"], area_ranks[candidate_id]) for candidate_id in successful]
                self.assertEqual(scores, sorted(scores))

    def test_bag_switch_clears_old_pallet_geometry_and_revalidates_selected_pattern(self):
        self.start_bag_pallet(400, 240, BAG_PALLET_B)
        self.post_case(BAG_PALLET_CASE, "run_step", 1, step_action_1="select_result", selected_result_key_1="Block__column")
        self.post_case(BAG_PALLET_CASE, "optimize_design_final_capacity", 0)
        trials = self.case_steps(BAG_PALLET_CASE)[0]["design_chain_optimization"]["candidate_results"]
        self.assertEqual(trials[BAG_PALLET_A]["final_base_units"], 144)
        self.select_bag_for_pallet(BAG_PALLET_A)
        self.assert_cleared(self.case_steps(BAG_PALLET_CASE)[1:])
        self.run_bag_pallet()
        pallet = self.case_steps(BAG_PALLET_CASE)[1]
        self.assertEqual(pallet["selected_result_key"], "Block__column")
        self.assertEqual(pallet["pending_result"]["total_base_units"], 144)

        self.post_case(BAG_PALLET_CASE, "run_step", 1, step_action_1="select_result", selected_result_key_1="Pinwheel__column")
        self.assertEqual(self.case_steps(BAG_PALLET_CASE)[1]["selected_result_key"], "Pinwheel__column")
        self.select_bag_for_pallet(BAG_PALLET_B)
        self.assert_cleared(self.case_steps(BAG_PALLET_CASE)[1:])
        self.run_bag_pallet()
        pallet = self.case_steps(BAG_PALLET_CASE)[1]
        self.assertEqual(pallet["selected_result_key"], "Block__column")
        self.assertEqual(pallet["pending_result"]["total_base_units"], 144)

    def test_legacy_bag_missing_an_axis_cannot_reuse_saved_pallet_footprint(self):
        self.start_bag_pallet(500, 500)
        self.post_case(BAG_PALLET_CASE, "use_step_result", 1)
        session_key = f"full_packaging_mode_session_case_{BAG_PALLET_CASE}"
        session = self.client.session
        steps = session[session_key]["steps"]
        legacy = {
            **steps[0]["selected"], "length": 252, "width": 212, "height": 150,
            "outer_dimension_source": "legacy_bag_dimensions",
        }
        weight_g = legacy.pop("weight_g")
        steps[0].update(selected=legacy, pending_result=legacy)
        session.save()
        self.run_bag_pallet()
        self.assertAlmostEqual(self.case_steps(BAG_PALLET_CASE)[1]["config"]["box_weight"], weight_g)

        session = self.client.session
        steps = session[session_key]["steps"]
        legacy = {**legacy, "height": None}
        steps[0].update(selected=legacy, pending_result=legacy)
        session.save()
        self.assertIsNone(_evaluate_design_chain_step(deepcopy(steps), 1))
        response = self.client.get(self.case_url(BAG_PALLET_CASE))
        pallet = response.context["steps"][1]
        self.assertIsNone(pallet["pending_result"])
        self.assertIsNone(pallet["selected"])
        self.assertIsNone(pallet["threejs_scene"])
        self.assertContains(response, "Inherited Bag Design dimensions are incomplete")

    def test_incomplete_weight_uses_geometric_pallet_capacity_with_explicit_legacy_fallback(self):
        self.start_bag_pallet(500, 500)
        for fields, status in (({"film_preset_0": "legacy", "product_weight_0": "100"}, "net_only"),
                               ({"film_preset_0": "ldpe_1_2", "product_weight_0": ""}, "unknown")):
            with self.subTest(status=status):
                self.select_bag_for_pallet(BAG_PALLET_A, **fields)
                self.run_bag_pallet(max_pallet_load_1=1, max_weight_on_bottom_box_1=1)
                steps = self.case_steps(BAG_PALLET_CASE)
                bag, pallet = steps
                self.assertEqual(bag["selected"]["weight_status"], status)
                cfg = pallet["config"]
                self.assertEqual(tuple(cfg[f"box_{key}"] for key in "lwh"),
                                 tuple(bag["selected"][key] for key in ("length", "width", "height")))
                self.assertEqual(cfg["box_weight"], "")
                self.assertGreater(pallet["pending_result"]["units_per_parent"], 0)
                self.assertEqual(pallet["pending_result"]["weight_status"], "unknown")
                self.assertNotIn("weight_g", pallet["pending_result"])
                self.assertIsNone(pallet["selected_result"]["actual_pallet_load_g"])
                self.assertIsNone(pallet["selected_result"]["avg_bottom_load_g"])
                self.assertEqual(_evaluate_design_chain_step(deepcopy(steps), 1), pallet["pending_result"])
                metrics = dict(build_workflow_report_payload({"steps": steps})["steps"][1]["metrics"])
                self.assertNotIn("Load utilization", metrics)
                self.assertEqual(metrics["Bottom-carton load check"], "Unavailable")
                if status == "net_only":
                    self.assertEqual((pallet["config"]["box_l"], pallet["config"]["box_w"], pallet["config"]["box_h"]), (252, 212, 150))
                    self.assertContains(self.client.get(self.case_url(BAG_PALLET_CASE)), "using the legacy Bag dimensions")

    def test_saved_bag_pallet_trials_distinguish_incomplete_and_complete_mass(self):
        self.start_bag_pallet()
        steps = self.case_steps(BAG_PALLET_CASE)
        bag, pallet = steps
        base = next(row for row in bag["design_candidates"] if row["candidate_id"] == BAG_PALLET_A)
        known, net_only = "saved-known-weight", "saved-net-only-weight"
        bag["design_candidates"] = [
            {**base, "candidate_id": known, "bag_tare_g": 0},
            {**base, "candidate_id": net_only, "bag_tare_g": None},
        ]
        pallet["config"]["max_pallet_load"] = 2500
        trials = optimize_design_chain({"steps": steps}, 0, _evaluate_design_chain_step)["candidate_results"]
        self.assertEqual(trials[known]["final_base_units"], 24)
        self.assertEqual(trials[net_only]["final_base_units"], 48)

    def test_bag_orientation_calibration_keeps_selected_height_and_all_rotations(self):
        slug = "calibration-bag-to-pallet-orientation"
        page = self.open_case(slug)
        bag, pallet = page.context["steps"]
        orientations = [row for row in bag["design_candidates_for_display"] if (row["bag_length"], row["bag_width"]) == (267, 197)]
        self.assertEqual(len(orientations), 3)
        self.assertAlmostEqual(pallet["threejs_scene"]["case"]["height"], 180.06096)
        self.assertEqual(pallet["pending_result"]["units_per_parent"], 4)
        candidate = next(row for row in orientations if row["bundle_height"] == 75)
        self.post_case(slug, "run_step", 0, action_0="select_design_candidate", selected_design_candidate_id_0=candidate["candidate_id"])
        self.post_case(slug, "use_step_result", 0)
        self.post_case(slug, "run_step", 1, step_action_1="run_analysis")
        bag, pallet = self.case_steps(slug)
        self.assertEqual(bag["selected"]["selected_candidate_id"], candidate["candidate_id"])
        self.assertAlmostEqual(pallet["config"]["box_h"], 75.06096)
        self.assertTrue(all(abs(item["dz"] - 75.06096) < 1e-8 for item in pallet["threejs_scene"]["placements"]))
        self.assertEqual(pallet["pending_result"]["units_per_parent"], 8)

    def test_bag_container_pallet_calibration_keeps_container_output_and_rotation_override(self):
        slug = "calibration-bag-to-container-to-pallet"
        page = self.open_case(slug)
        bag, carton, pallet = page.context["steps"]
        self.assertEqual(len(bag["design_candidates_for_display"]), len(bag["design_candidates"]))
        self.assertEqual(carton["bag_rotation_inheritance"]["defaults"], [False, True, True])
        self.assert_inherited_output(carton["selected"], pallet)
        self.assertNotEqual(pallet["config"]["box_l"], bag["selected"]["length"])
        self.post_case(slug, "run_step", 1, action_1="run_single", bag_rotations_displayed="011", r3_1="on")
        self.post_case(slug, "run_step", 0, action_0="select_design_candidate", selected_design_candidate_id_0="bag-design-138ba262b3550a49")
        self.post_case(slug, "use_step_result", 0)
        self.assert_cleared(self.case_steps(slug)[1:])
        self.post_case(slug, "run_step", 1, action_1="run_single")
        self.post_case(slug, "use_step_result", 1)
        self.post_case(slug, "run_step", 2, step_action_2="run_analysis")
        steps = self.case_steps(slug)
        bag, carton, pallet = steps
        self.assertEqual(carton["bag_rotation_inheritance"]["defaults"], [True, False, True])
        self.assertEqual(carton["bag_rotation_inheritance"]["override"], [False, False, True])
        self.assert_inherited_output(carton["selected"], pallet)
        self.assertNotIn("bag_rotation_inheritance", pallet)
        self.assertEqual(_evaluate_design_chain_step(deepcopy(steps), 2), pallet["pending_result"])

    def test_bag_design_display_tracks_downstream_steps_and_keeps_the_existing_selection(self):
        slug = "calibration-bag-terminal-and-downstream"
        url = self.case_url(slug)
        page = self.open_case(slug)
        stored = self.case_steps(slug)[0]
        full_ids = [row["candidate_id"] for row in stored["design_candidates"]]
        reference = [row for row in stored["design_candidates"] if (row["bag_length"], row["bag_width"]) == (267, 197)]
        reference_ids = [row["candidate_id"] for row in reference]
        self.assertEqual(len(full_ids), 148)
        self.assertEqual(len(reference_ids), 3)
        self.assertContains(self.client.get(reverse("regressions")), f'href="{url}?reset=1">Open in Packaging Flow</a>')

        def assert_display(response, *, downstream, selected_id):
            step = response.context["steps"][0]
            displayed = step["design_candidates_for_display"]
            ids = [row["candidate_id"] for row in displayed]
            self.assertEqual(step["selected_design_candidate_id"], selected_id)
            self.assertEqual(step["result"]["candidate_id"], selected_id)
            self.assertEqual(step["pending_result"]["selected_candidate_id"], selected_id)
            self.assertEqual(step["threejs_scene"], step["result"]["render_data"])
            self.assertEqual(step["design_chain_ui"]["has_downstream"], downstream)
            self.assertEqual([row["candidate_id"] for row in step["design_candidates"]], full_ids)
            self.assertContains(response, f'tool-row-selected" onclick="bagSelectionSelectDesignCandidate(\'0\', \'{selected_id}\')"')
            if downstream:
                self.assertEqual(ids, full_ids)
                self.assertTrue(all("display_rank" not in row for row in displayed))
                self.assertContains(response, "Orientation-specific arrangements are retained")
            else:
                self.assertEqual(len(ids), 53)
                self.assertEqual([row["display_rank"] for row in displayed], list(range(1, 54)))
                self.assertEqual([candidate_id for candidate_id in ids if candidate_id in reference_ids], [selected_id])
                self.assertContains(response, "Unique bag designs by physical bundle arrangement")
            return step["threejs_scene"]

        default_id = reference_ids[0]
        scene = assert_display(page, downstream=False, selected_id=default_id)
        self.assertEqual(scene["bag"]["film"]["depthAxis"], "height")
        for step_type in ("pallet", "transport", "bag", "container"):
            self.post_case(slug, "add_step", 0, step_type=step_type)
            self.assertEqual(assert_display(self.client.get(url), downstream=True, selected_id=default_id), scene)
            if step_type != "container":
                self.post_case(slug, "remove_step", 1)
        self.post_case(slug, "add_step", 1, step_type="pallet", after_index="1")
        self.assertEqual(assert_display(self.client.get(url), downstream=True, selected_id=default_id), scene)

        explicit_id = reference_ids[2]
        self.post_case(slug, "run_step", 0, action_0="select_design_candidate", selected_design_candidate_id_0=explicit_id)
        explicit_scene = assert_display(self.client.get(url), downstream=True, selected_id=explicit_id)
        self.assertEqual(explicit_scene["bag"]["film"]["depthAxis"], "length")
        self.post_case(slug, "remove_step", 2)
        self.post_case(slug, "remove_step", 1)
        self.assertEqual(assert_display(self.client.get(url), downstream=False, selected_id=explicit_id), explicit_scene)

        session = self.client.session
        old_step = session[f"full_packaging_mode_session_case_{slug}"]["steps"][0]
        old_step.pop("selected_design_candidate_id")
        for row in old_step["design_candidates"]:
            row.pop("flat_bag_length_mm")
            row.pop("flat_bag_width_mm")
            row["render_data"]["bag"].pop("film")
        session.save()
        self.assertEqual(assert_display(self.client.get(url), downstream=False, selected_id=explicit_id), explicit_scene)
        self.assertTrue(all("display_rank" not in row for row in self.case_steps(slug)[0]["design_candidates"]))

    def test_bag_design_rotation_permissions_are_independent_and_reach_capacity_optimizer(self):
        url = reverse("full_packaging_mode")
        session_key = "full_packaging_mode_session"
        for _ in range(2):
            self.assertRedirects(
                self.client.post(url, {"action": "add_step", "step_type": "bag"}), url, fetch_redirect_response=False,
            )
        self.client.post(url, {
            "action": "run_step", "index": 0, "action_0": "run_design", "mode_0": "design",
            "product_l_0": 90, "product_w_0": 60, "product_h_0": 25, "desired_qty_0": 12,
            "rotation_fields_present_0": "1", "r1_0": "1", "product_advanced_open_0": "1",
        })
        self.client.post(url, {"action": "use_step_result", "index": 0})
        self.client.post(url, {
            "action": "run_step", "index": 1, "action_1": "run_design", "mode_1": "design",
            "desired_qty_1": 2, "rotation_fields_present_1": "1", "r3_1": "1", "product_advanced_open_1": "1",
        })
        first, second = self.client.session[session_key]["steps"]
        accepted_id = first["selected"]["selected_candidate_id"]
        self.assertEqual(accepted_id, first["design_candidates"][0]["candidate_id"])
        html = self.client.get(url)
        for index, step, flags in ((0, first, (True, False, False)), (1, second, (False, False, True))):
            cfg = step["config"]
            self.assertEqual(tuple(cfg[key] for key in ("r1", "r2", "r3")), flags)
            self.assertTrue(cfg["product_advanced_open"])
            self.assertContains(html, f'name="rotation_fields_present_{index}"', count=1)
            for key, checked in zip(("r1", "r2", "r3"), flags):
                checked_attr = " checked" if checked else ""
                self.assertContains(html, f'<input type="checkbox" name="{key}_{index}" value="1"{checked_attr}>', html=True)
            ids = [row["candidate_id"] for row in step["design_candidates"]]
            self.assertTrue(ids)
            for analysis in (analyze_bag_config(cfg, "run_design"), analyze_bag_capacity(cfg)):
                self.assertEqual([row["candidate_id"] for row in analysis["design_candidates"]], ids)

        self.client.post(url, {
            "action": "optimize_design_final_capacity", "index": 0, "rotation_fields_present_0": "1", "r3_0": "1",
            "selected_design_candidate_id_0": accepted_id,
        })
        first, second = self.client.session[session_key]["steps"]
        expected = analyze_bag_capacity(first["config"])
        capacity_trials = first["design_chain_optimization"]["candidate_results"]
        self.assertEqual(len(capacity_trials), 50)
        self.assertEqual(list(capacity_trials), [row["candidate_id"] for row in expected["design_candidates"]])
        self.assertTrue(all(trial["status"] == "ok" for trial in capacity_trials.values()))
        self.assertNotIn(accepted_id, capacity_trials)
        self.assertEqual(first["pending_result"]["selected_candidate_id"], next(iter(capacity_trials)))
        self.assertIsNone(first["selected"])
        self.assertIsNone(second["pending_result"])

        self.client.post(url, {"action": "use_step_result", "index": 0})
        self.client.post(url, {"action": "use_step_result", "index": 0, "rotation_fields_present_0": "1"})
        first, second = self.client.session[session_key]["steps"]
        self.assertEqual(first["messages"], [BAG_DESIGN_ROTATION_ERROR])
        self.assertEqual(first["config"]["selected_design_candidate_id"], "")
        self.assertEqual(first["design_candidates"], [])
        for step in (first, second):
            for key in ("selected", "pending_result", "result", "threejs_scene", "analysis_report"):
                self.assertIsNone(step[key], key)
            self.assertFalse(step["summary"])
        self.assertTrue(second["config"]["r3"])
        json.dumps([first, second], allow_nan=False)

    def test_bag_steps_keep_independent_allowances_and_supply_calculated_payloads(self):
        url = reverse("full_packaging_mode")
        key = "full_packaging_mode_session"
        for step_type in ("bag", "bag", "container"):
            response = self.client.post(url, {"action": "add_step", "step_type": step_type})
            self.assertRedirects(response, url, fetch_redirect_response=False)
        response = self.client.get(url)
        for index in (0, 1):
            for field in ("sealing_allowance", "fit_tolerance"):
                self.assertContains(response, f'name="{field}_{index}"', count=1)
        self.client.post(url, {
            "action": "run_step", "index": 0, "action_0": "run_single",
            "product_l_0": 90, "product_w_0": 60, "product_h_0": 25,
            "bag_length_0": 154, "bag_width_0": 114,
            "fit_tolerance_0": 2, "sealing_allowance_0": 10,
            "film_preset_0": "legacy",
        })
        self.client.post(url, {"action": "use_step_result", "index": 0})
        self.client.post(url, {
            "action": "run_step", "index": 1, "action_1": "run_single",
            "bag_length_1": 18.5, "bag_width_1": 16, "bag_dimension_unit_1": "cm",
            "fit_tolerance_1": 0.5, "sealing_allowance_1": 2,
            "film_preset_1": "legacy",
        })
        self.client.post(url, {"action": "use_step_result", "index": 1})
        inner, outer, _ = self.client.session[key]["steps"]
        self.assertEqual((inner["config"]["fit_tolerance"], inner["config"]["sealing_allowance"]), ("2", "10"))
        self.assertEqual((outer["config"]["fit_tolerance"], outer["config"]["sealing_allowance"]), ("0.5", "2"))
        for step, (fit, seal, quantity, body) in zip(
            (inner, outer),
            ((2, 10, 2, (92, 62, 50)), (5, 20, 1, (98, 93, 62))),
        ):
            pending = analyze_bag_capacity(step["config"])["pending_result"]
            scene = step["threejs_scene"]["bag"]
            output = step["selected"]
            self.assertEqual((scene["fitTolerance"], scene["sealingAllowance"]), (fit, seal))
            self.assertEqual(output["bag_assumptions"], pending["bag_assumptions"])
            self.assertEqual(output["units_per_parent"], quantity)
            self.assertEqual(tuple(output[k] for k in ("length", "width", "height")), body)
            self.assertEqual(tuple(pending[k] for k in ("length", "width", "height")), body)
            self.assertEqual(output["total_base_units"], 2)
        response = self.client.get(url)
        carton = response.context["steps"][2]
        self.assert_inherited_output(outer["selected"], carton)
        report = build_workflow_report_payload({"steps": [inner, outer]})
        self.assertEqual(dict(report["steps"][0]["metrics"])["Sealing allowance"], "10 mm")
        self.assertEqual(dict(report["steps"][1]["metrics"])["Fit tolerance"], "0.5 cm")
        json.dumps(self.client.session[key], allow_nan=False)

    def test_all_compendium_cases_open_with_complete_json_safe_chains(self):
        expected = {
            "calibration-bag-to-container-r3": (("bag", "container"), (12, 15)),
            "calibration-bag-to-container-r1": (("bag", "container"), (12, 14)),
            "calibration-bag-to-transport-rotations": (("bag", "transport"), (12, 1)),
            "calibration-bag-candidate-rotation-override": (("bag", "container"), (12, 14)),
            "calibration-bag-same-size-different-rotations": (("bag", "container"), (12, 16)),
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
            "calibration-bag-to-pallet-footprints": (("bag", "pallet"), (12, 4)),
            "calibration-same-bag-size-different-bundles": (("bag", "pallet"), (12, 8)),
            "calibration-bag-to-pallet-orientation": (("bag", "pallet"), (12, 4)),
            "calibration-bag-to-container-to-pallet": (("bag", "container", "pallet"), (12, 16, 8)),
            "calibration-incomplete-bag-weight-pallet": (("bag", "pallet"), (12, 4)),
            "calibration-equivalent-bags-to-container": (("bag", "container"), (12, 15)),
            "calibration-equivalent-loads-different-rotations": (("bag", "container"), (12, 16)),
            "calibration-equivalent-bags-to-transport": (("bag", "transport"), (12, 1)),
            "calibration-mixed-cargo-equivalence": (("transport",), (6,)),
            "calibration-equivalent-bags-to-container-to-pallet": (("bag", "container", "pallet"), (12, 15, 8)),
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

    def test_equivalent_bag_case_reuses_carton_work_without_changing_candidate_selection(self):
        slug = "calibration-equivalent-bags-to-container"
        self.open_case(slug)
        before = self.case_steps(slug)[0]
        other_session = Client()
        other_session.get(self.case_url(slug), {"reset": 1}, follow=True)

        with patch.object(flow, "analyze_container_capacity", wraps=flow.analyze_container_capacity) as solve:
            self.post_case(slug, "optimize_design_final_capacity", 0)
        self.assertEqual(solve.call_count, 50)

        after = self.case_steps(slug)[0]
        self.assertEqual(after["design_candidates"], before["design_candidates"])
        self.assertEqual(after["selected_design_candidate_id"], before["selected_design_candidate_id"])
        self.assertEqual(after["pending_result"], before["pending_result"])
        ids = {row["candidate_id"] for row in before["design_candidates"]}
        results = after["design_chain_optimization"]["candidate_results"]
        self.assertEqual(len(ids), 148)
        self.assertEqual(set(results), ids)
        self.assertEqual(results["bag-design-90e1dd5f89f589e5"], results["bag-design-249267a731a0f206"])
        other_bag = other_session.session[f"full_packaging_mode_session_case_{slug}"]["steps"][0]
        self.assertFalse(other_bag.get("design_chain_optimization"))

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
        response = self.open_case(slug)
        self.assertContains(response, "Bag area (cm²)")
        self.assertContains(response, '<td class="text-end">231.04</td>', html=True)
        steps = self.case_steps(slug)
        initial_bag, initial_carton, _initial_pallet = steps
        selected = initial_bag["selected"]
        # 80 × 60 × 90 mm bundle inserted along 80 mm.
        self.assertEqual((selected["length"], selected["width"], selected["height"]), (152, 152, 90))
        self.assertEqual(selected["metrics"]["bag_area"], 23104)
        self.assert_inherited_output(selected, initial_carton)
        report = build_workflow_report_payload({"steps": steps})
        bag_report, carton_report = report["steps"][:2]
        self.assertEqual(bag_report["output"]["dimensions_display"], "152 × 152 × 90 mm")
        self.assertEqual(carton_report["input"]["dimensions_display"], "152 × 152 × 90 mm")
        self.assertEqual(dict(bag_report["metrics"])["Bag usage"], "100%")
        self.assertEqual(dict(bag_report["metrics"])["Max quantity"], "4")
        json.dumps(steps, allow_nan=False)

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

    def test_bag_optimal_area_renders_for_saved_rows_and_keeps_candidate_selection(self):
        catalogue = PackagingCatalogue.objects.create(name="Area display test bags")
        bag = PackagingMaterial.objects.create(
            catalogue=catalogue, packaging_type="BAG", part_number="97x117",
            part_length=97, part_width=117, part_height=0, bag_actual_weight_g="0.729",
        )
        url = reverse("full_packaging_mode")
        self.assertRedirects(
            self.client.post(url, {"action": "add_step", "step_type": "bag"}),
            url, fetch_redirect_response=False,
        )
        config = {
            "action": "run_step", "index": 0, "mode_0": "optimal",
            "product_l_0": 90, "product_w_0": 60, "product_h_0": 25,
            "bag_source_0": "catalogue", "catalogue_id_0": catalogue.pk,
            "bag_dimension_unit_0": "in",
            "bag_mass_unit_0": "lb",
        }
        response = self.client.post(url, {**config, "action_0": "find_top5"}, follow=True)
        self.assertContains(response, "Bag area (in²)")
        self.assertContains(response, '<td class="text-end">17.59</td>', html=True)
        self.assertContains(response, "Bag weight (oz)")
        self.assertContains(response, '<td class="text-end">0.0257</td>', html=True)
        self.assertContains(response, f"bagSelectionSelectCandidate('0', '{bag.pk}')")

        session = self.client.session
        step = session["full_packaging_mode_session"]["steps"][0]
        row, = step["top5"]
        self.assertEqual(row["bag_area"], 11349)
        row.pop("bag_area_display")
        row.pop("bag_area_unit")
        row.pop("bag_weight_display")
        row.pop("bag_weight_unit")
        session.save()
        restored = self.client.get(url)
        self.assertContains(restored, "Bag area (in²)")
        self.assertContains(restored, '<td class="text-end">17.59</td>', html=True)
        self.assertContains(restored, '<td class="text-end">0.0257</td>', html=True)

        session = self.client.session
        row, = session["full_packaging_mode_session"]["steps"][0]["top5"]
        row.pop("bag_tare_g")
        session.save()
        missing = self.client.get(url)
        self.assertContains(missing, '<td class="text-end">17.59</td><td class="text-end">—</td>', html=True)

        selected = self.client.post(
            url, {**config, "action_0": "select_candidate", "bag_id_0": bag.pk}, follow=True,
        )
        self.assertContains(selected, "Bag area (in²)")
        self.assertContains(
            selected, '<th scope="row" class="fw-normal text-muted">Flat bag dimensions</th>'
            '<td class="text-end">3.819 × 4.606 in</td>', html=True,
        )
        step = self.client.session["full_packaging_mode_session"]["steps"][0]
        self.assertEqual(step["result"]["usage"], 1.0)
        self.assertEqual(step["pending_result"]["units_per_parent"], 1)
        self.assertEqual(step["pending_result"]["bag_tare_g"], 0.729)
        metrics = build_workflow_report_payload({"steps": [step]})["steps"][0]["metrics"]
        self.assertEqual(dict(metrics)["Flat bag dimensions"], "3.819 × 4.606 in")

    def test_bag_design_height_insertion_recalculates_carton_and_pallet(self):
        slug = "bag-design-final-capacity"
        self.open_case(slug)
        self.post_case(slug, "optimize_design_final_capacity", 0)
        bag = self.case_steps(slug)[0]
        candidate = next(
            row for row in bag["design_candidates"]
            if (row["bundle_length"], row["bundle_width"], row["bundle_height"]) == (240, 90, 20)
            and row["insertion"]["axis"] == "height"
        )
        candidate_id = candidate["candidate_id"]
        self.assertEqual((candidate["bag_length"], candidate["bag_width"], candidate["bag_area"]), (122, 332, 40504))
        self.assertEqual(bag["design_chain_optimization"]["candidate_results"][candidate_id]["final_base_units"], 2880)

        self.post_case(
            slug, "run_step", 0, action_0="select_design_candidate",
            selected_design_candidate_id_0=candidate_id,
        )
        self.post_case(slug, "use_step_result", 0)
        self.post_case(slug, "run_step", 1, action_1="run_single")
        self.post_case(slug, "run_step", 2, step_action_2="run_analysis")
        steps = self.case_steps(slug)
        bag, carton, pallet = steps
        selected = bag["selected"]
        self.assertEqual(selected["selected_candidate_id"], candidate_id)
        self.assertEqual(selected["insertion"], {
            "axis": "height", "depth": 20, "opening_axes": ["length", "width"], "opening_dimensions": [240, 90],
        })
        self.assertEqual((selected["length"], selected["width"], selected["height"]), (122, 332, 20))
        self.assert_inherited_output(selected, carton)
        self.assert_inherited_output(carton["pending_result"], pallet)
        self.assertEqual(carton["pending_result"]["units_per_parent"], 90)
        self.assertEqual(pallet["pending_result"]["total_base_units"], 2880)
        report = build_workflow_report_payload({"steps": steps})
        self.assertEqual(report["steps"][1]["input"]["dimensions_display"], "122 × 332 × 20 mm")
        json.dumps(steps, allow_nan=False)

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
        selected_scene = pallet_step["threejs_scene"]
        actual_footprint = palletized_load_footprint(
            selected_scene["pallet"]["length"],
            selected_scene["pallet"]["width"],
            selected_scene["placements"],
        )
        self.assertEqual(
            pallet_step["pending_result"]["length"], actual_footprint["length"]
        )
        self.assertEqual(
            pallet_step["pending_result"]["width"], actual_footprint["width"]
        )
        self.assertLess(pallet_step["pending_result"]["length"], 1225.4)
        self.assertLess(pallet_step["pending_result"]["width"], 825.4)
        self.assertEqual(
            pallet_step["selected_result"]["actual_footprint"], actual_footprint
        )
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

    def test_direct_pallet_visualization_uses_actual_asymmetric_center(self):
        transport_scene = {
            "items": [{
                "x": 0,
                "y": 0,
                "z": 0,
                "dx": 1210,
                "dy": 805,
                "dz": 600,
            }],
            "metadata": {"total_items": 1},
        }
        upstream = {
            "source_type": "palletization_result",
            "length": 1210,
            "width": 805,
            "height": 600,
            "pallet_visualization": {
                "pallet": {
                    "length": 1200,
                    "width": 800,
                    "height": 108,
                    "deck_thickness": 20,
                },
                "allowed_footprint": {
                    "x": -5,
                    "y": -2.5,
                    "length": 1210,
                    "width": 805,
                },
                "placements": [{
                    "x": 0,
                    "y": 0,
                    "z": 108,
                    "dx": 1210,
                    "dy": 805,
                    "dz": 492,
                }],
            },
        }

        decorated = _decorate_transport_scene_with_pallet_visualization(
            transport_scene,
            upstream,
        )

        bounds = decorated["workflow_visualizations"]["palletized_load"]["bounds"]
        self.assertEqual(bounds["center_x"], 605.0)
        self.assertEqual(bounds["center_y"], 402.5)

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
