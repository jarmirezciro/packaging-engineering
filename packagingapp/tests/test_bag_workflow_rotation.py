import json
from copy import deepcopy
from itertools import product
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from packagingapp.tools.bag.service import analyze_bag_capacity, analyze_bag_config
from packagingapp.tools.bag.workflow import build_bag_design_pending_result
from packagingapp.tools.bag.workflow_rotation import bag_design_rotation_metadata, derive_bag_load_unit_rotations, rotation_tuple
from packagingapp.tools.full_packaging.chain_optimizer import build_design_candidate_payload, optimize_design_chain
from packagingapp.views.full_packaging import _apply_chained_defaults, _evaluate_design_chain_step, _new_step


TOP = "bag-design-90e1dd5f89f589e5"
SIDE = "bag-design-138ba262b3550a49"
REFERENCE_CONFIG = {
    "mode": "design", "product_l": 90, "product_w": 60, "product_h": 25,
    "product_weight": 50, "desired_qty": 12, "r1": True, "r2": False, "r3": True,
}


class BagRotationMappingTests(SimpleTestCase):
    def test_every_orientation_maps_all_valid_permission_combinations(self):
        axes_by_orientation = ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 1, 0), (2, 0, 1))
        for flags in product((False, True), repeat=3):
            for index, axes in enumerate(axes_by_orientation):
                with self.subTest(flags=flags, index=index):
                    expected = tuple(flags[axis] for axis in axes) if any(flags) else None
                    self.assertEqual(derive_bag_load_unit_rotations(flags, index), expected)
        for invalid in (None, "3", -1, 6, 1.5, True):
            self.assertIsNone(derive_bag_load_unit_rotations((True, True, True), invalid))
        self.assertIsNone(derive_bag_load_unit_rotations({"r1": True, "r2": False}, 0))

    def test_payloads_agree_and_require_axis_preserving_outer_dimensions(self):
        config = {**REFERENCE_CONFIG, "selected_design_candidate_id": TOP}
        interactive = analyze_bag_config(config, "select_design_candidate")
        capacity = analyze_bag_capacity(config)
        candidate = interactive["result"]
        flags = interactive["pending_result"]["original_product_rotations"]
        trial = build_design_candidate_payload("bag", candidate, original_rotations=flags)
        for payload in (interactive["pending_result"], capacity["pending_result"], trial):
            self.assertEqual(payload["orientation_index"], 3)
            self.assertEqual(payload["original_product_rotations"], {"r1": True, "r2": False, "r3": True})
            self.assertEqual(rotation_tuple(payload["load_unit_rotation_defaults"]), (False, True, True))
            json.dumps(payload, allow_nan=False)

        legacy = build_bag_design_pending_result({**candidate, "film_caliper_mm": None}, original_rotations=flags)
        self.assertEqual(legacy["outer_dimension_source"], "legacy_bag_dimensions")
        self.assertIsNone(legacy["load_unit_rotation_defaults"])
        self.assertIsNone(bag_design_rotation_metadata(candidate, {**trial, "length": trial["height"]}, flags)["load_unit_rotation_defaults"])
        self.assertIsNone(build_bag_design_pending_result({**candidate, "orientation_index": None}, original_rotations=flags)["load_unit_rotation_defaults"])

    def test_catalogue_permissions_are_the_payload_source(self):
        product = SimpleNamespace(
            product_length=90, product_width=60, product_height=25, weight=0.05,
            rotation_1=False, rotation_2=False, rotation_3=True,
        )
        config = {**REFERENCE_CONFIG, "product_source": "catalogue", "selected_design_candidate_id": SIDE}
        for result in (analyze_bag_config(config, "run_design", selected_product=product),
                       analyze_bag_capacity(config, selected_product=product)):
            metadata = result["pending_result"]
            self.assertEqual(metadata["orientation_index"], 0)
            self.assertEqual(rotation_tuple(metadata["original_product_rotations"]), (False, False, True))
            self.assertEqual(rotation_tuple(metadata["load_unit_rotation_defaults"]), (False, False, True))

    def test_equal_physical_inputs_with_different_orientation_provenance_have_separate_trials(self):
        config = {**REFERENCE_CONFIG, "product_l": 25, "product_w": 25, "desired_qty": 1}
        analysis = analyze_bag_config(config, "run_design")
        first = analysis["result"]
        second = {**first, "candidate_id": "same-dimensions-orientation-3", "orientation_index": 3}
        payload = analysis["pending_result"]
        source = {"type": "bag", "config": config, "design_candidates": [first, second], "pending_result": payload}
        for consumer in ("container", "transport"):
            with self.subTest(consumer=consumer):
                workflow = {"steps": [source, _new_step(consumer)]}
                original = deepcopy(workflow)
                observed = []

                def evaluate(steps, idx):
                    step = steps[idx]
                    _apply_chained_defaults(step, steps, idx)
                    cfg = step["config"]
                    flags = rotation_tuple(cfg if consumer == "container" else cfg["product_rows"][0])
                    upstream = steps[idx - 1]["pending_result"]
                    observed.append(((upstream["length"], upstream["width"], upstream["height"]), flags))
                    return {"total_base_units": 1 if flags[0] else 2}

                result = optimize_design_chain(workflow, 0, evaluate)
                self.assertEqual([flags for _, flags in observed], [(True, False, True), (False, True, True)])
                self.assertEqual(observed[0][0], observed[1][0])
                self.assertEqual(result["sorted_candidate_ids"][0], second["candidate_id"])
                self.assertEqual(workflow, original)


class BagRotationWorkflowTests(TestCase):
    def setUp(self):
        self.enterContext(self.settings(MEDIA_ROOT=self.enterContext(TemporaryDirectory())))

    def open_case(self, slug):
        self.slug = slug
        self.url = reverse("full_packaging_case", args=[slug])
        return self.client.get(self.url, {"reset": 1}, follow=True)

    def saved_steps(self):
        return self.client.session[f"full_packaging_mode_session_case_{self.slug}"]["steps"]

    def post_step(self, index, action="run_step", **fields):
        response = self.client.post(self.url, {"action": action, "index": index, **fields})
        self.assertRedirects(response, self.url, fetch_redirect_response=False)

    def choose_bag(self, candidate_id, **fields):
        self.post_step(0, action_0="select_design_candidate", selected_design_candidate_id_0=candidate_id, **fields)

    def assert_capacity_trial_matches_current_result(self, steps):
        capacity = _evaluate_design_chain_step(deepcopy(steps), 1)
        expected = steps[1]["pending_result"]["total_base_units"]
        self.assertEqual(capacity["total_base_units"], expected)
        workflow = {"steps": deepcopy(steps)}
        bag = workflow["steps"][0]
        bag["design_candidates"] = [row for row in bag["design_candidates"] if row["candidate_id"] in (TOP, SIDE)]
        result = optimize_design_chain(workflow, 0, _evaluate_design_chain_step)
        self.assertEqual(result["candidate_results"][bag["selected_design_candidate_id"]]["final_base_units"], expected)
        self.assertEqual(len(result["candidate_results"]), 2)

    def test_container_mapped_length_and_height_only_calibrations(self):
        for axis, orientation in (("r3", 0), ("r1", 3)):
            with self.subTest(axis=axis):
                page = self.open_case(f"calibration-bag-to-container-{axis}")
                bag, carton = page.context["steps"]
                self.assertEqual(bag["pending_result"]["orientation_index"], orientation)
                self.assertEqual(rotation_tuple(carton["config"]), (False, False, True))
                self.assertContains(page, 'name="bag_rotations_displayed" value="001"')
                self.assertContains(page, "Rotation defaults inherited from the selected bag arrangement")
                self.assertEqual(float(carton["config"]["product_h"]), bag["pending_result"]["height"])

    def test_container_inheritance_changes_preserves_override_and_can_be_restored(self):
        page = self.open_case("calibration-bag-same-size-different-rotations")
        bag, carton = page.context["steps"]
        self.assertEqual(rotation_tuple(carton["config"]), (False, True, True))
        original_dimensions = (carton["config"]["product_l"], carton["config"]["product_w"], carton["config"]["product_h"])
        self.assertEqual(len(bag["design_candidates_for_display"]), len(bag["design_candidates"]))
        self.choose_bag(SIDE)
        bag, carton = self.client.get(self.url).context["steps"]
        self.assertEqual(rotation_tuple(carton["config"]), (True, False, True))
        self.assertNotEqual(tuple(carton["config"][key] for key in ("product_l", "product_w", "product_h")), original_dimensions)

        # Submitting an unchanged form from before the candidate change is not an edit.
        self.post_step(1, action_1="run_single", bag_rotations_displayed="011", r2_1="on", r3_1="on")
        self.assertIsNone(self.saved_steps()[1]["bag_rotation_inheritance"]["override"])
        self.post_step(1, action_1="run_single", bag_rotations_displayed="101", r1_1="on")
        self.assertEqual(rotation_tuple(self.saved_steps()[1]["config"]), (True, False, False))
        self.choose_bag(TOP)
        page = self.client.get(self.url)
        self.assertContains(page, "Rotation permissions customized for this step")
        carton = page.context["steps"][1]
        self.assertEqual(rotation_tuple(carton["config"]), (True, False, False))
        self.assertEqual(carton["bag_rotation_inheritance"]["defaults"], [False, True, True])

        self.post_step(1, action_1="run_single", bag_rotations_displayed="100", r1_1="on")
        self.assert_capacity_trial_matches_current_result(self.saved_steps())
        self.post_step(1, action_1="run_single", bag_rotations_displayed="100", r1_1="on", restore_bag_rotations="1")
        self.assertEqual(rotation_tuple(self.saved_steps()[1]["config"]), (False, True, True))

        # An explicit all-off edit is retained for downstream validation.
        self.post_step(1, action_1="run_single", bag_rotations_displayed="011")
        carton = self.saved_steps()[1]
        self.assertEqual(rotation_tuple(carton["config"]), (False, False, False))
        self.assertIsNone(carton["pending_result"])

    def test_transport_preserves_rotations_and_row_controls_across_mode_and_source_changes(self):
        page = self.open_case("calibration-bag-to-transport-rotations")
        self.assertContains(page, 'name="bag_rotations_displayed" value="011"')
        self.choose_bag(SIDE)
        self.assertEqual(rotation_tuple(self.client.get(self.url).context["steps"][1]["product_rows"][0]), (True, False, True))
        self.post_step(1, step_action_1="run_analysis", bag_rotations_displayed="101", **{
            "item_r1[]": "1", "item_r2[]": "0", "item_r3[]": "0",
            "item_max_qty[]": "1", "item_stackable[]": "0", "item_sequence[]": "3",
        })
        self.post_step(1, step_action_1="refresh", packing_mode_1="front_to_back_infill")
        self.choose_bag(TOP)
        page = self.client.get(self.url)
        self.assertContains(page, "Rotation permissions customized for this step")
        row = page.context["steps"][1]["product_rows"][0]
        self.assertEqual(rotation_tuple(row), (True, False, False))
        self.assertTrue(row["max_qty"])
        self.assertFalse(row["stackable"])
        self.assertEqual(int(row["sequence"]), 3)

        self.post_step(1, step_action_1="run_analysis", bag_rotations_displayed="100")
        steps = self.saved_steps()
        json.dumps(steps, allow_nan=False)
        self.assert_capacity_trial_matches_current_result(steps)
        self.post_step(1, step_action_1="run_analysis", bag_rotations_displayed="100", restore_bag_rotations="1")
        row = self.saved_steps()[1]["config"]["product_rows"][0]
        self.assertEqual(rotation_tuple(row), (False, True, True))
        self.assertTrue(row["max_qty"])
        self.assertEqual(int(row["sequence"]), 3)

    def test_legacy_dimensions_and_later_steps_use_existing_defaults(self):
        self.open_case("calibration-bag-same-size-different-rotations")
        self.choose_bag(TOP, film_preset_0="legacy")
        page = self.client.get(self.url)
        self.assertContains(page, "Rotation defaults could not be derived from the selected bag")
        bag, carton = page.context["steps"]
        self.assertEqual(bag["pending_result"]["outer_dimension_source"], "legacy_bag_dimensions")
        self.assertEqual(rotation_tuple(carton["config"]), (True, True, True))
        self.choose_bag(TOP, film_preset_0="ldpe_1_2")
        self.post_step(1, action_1="run_single")
        for step_type in ("transport", "pallet"):
            self.post_step(1, action="add_step", step_type=step_type)
            later = self.client.get(self.url).context["steps"][-1]
            self.assertNotIn("bag_rotation_inheritance", later)
            if step_type == "transport":
                self.assertEqual(rotation_tuple(later["product_rows"][0]), (True, True, True))
            self.post_step(2, action="remove_step")

    def test_customizations_are_isolated_between_workflows(self):
        first = self.open_case("calibration-bag-candidate-rotation-override")
        self.assertContains(first, "Rotation permissions customized for this step")
        self.choose_bag(SIDE)
        self.assertEqual(self.client.get(self.url).context["steps"][1]["bag_rotation_inheritance"]["override"], [True, False, True])
        second = self.open_case("calibration-bag-same-size-different-rotations")
        self.assertIsNone(second.context["steps"][1]["bag_rotation_inheritance"]["override"])
        self.post_step(1, action_1="run_single", bag_rotations_displayed="011", r1_1="on")
        self.assertEqual(self.saved_steps()[1]["bag_rotation_inheritance"]["override"], [True, False, False])
        separate = Client().get(self.url)
        self.assertIsNone(separate.context["steps"][1]["bag_rotation_inheritance"]["override"])
