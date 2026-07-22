import json
from pathlib import Path

from django.test import TestCase
from django.urls import reverse

from packagingapp.forms import BagSelectionForm, ContainerSelectionMode1Form
from packagingapp.tools.bag.serializers import sanitize_bag_config_for_session
from packagingapp.tools.bag.service import analyze_bag_config
from packagingapp.tools.bag.state import default_bag_config
from packagingapp.tools.container.service import analyze_container_form
from packagingapp.tools.container.serializers import sanitize_container_config_for_session
from packagingapp.utils.bag_selection.engine import (
    build_bag_design_candidates,
    compute_max_quantity_for_bag,
)
from packagingapp.utils.box_selection.engine import (
    build_container_design_candidates,
    compute_max_quantity_only,
)
from packagingapp.utils.quantity_decomposition import (
    generate_factor_arrangements,
    next_smooth_quantity,
)


class QuantityDecompositionTests(TestCase):
    def test_composite_prime_one_and_larger_quantities(self):
        self.assertEqual(next_smooth_quantity(12), 12)
        self.assertEqual(next_smooth_quantity(17), next_smooth_quantity(17))
        self.assertGreater(next_smooth_quantity(17), 17)
        self.assertEqual(next_smooth_quantity(1), 1)
        arrangements = generate_factor_arrangements(60, 3)
        self.assertGreater(len(arrangements), 6)
        self.assertTrue(all(a * b * c == 60 for a, b, c in arrangements))

    def test_arrangements_are_deterministic_and_unique(self):
        first = generate_factor_arrangements(18, 3)
        second = generate_factor_arrangements(18, 3)
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(set(first)))
        self.assertEqual(first, sorted(first))

    def test_bag_and_container_share_prime_rounding(self):
        bag = build_bag_design_candidates(100, 80, 20, 17)
        container = build_container_design_candidates((100, 80, 20), 17, 1, 1, 1)
        self.assertEqual(bag["design_quantity"], next_smooth_quantity(17))
        self.assertEqual(container["design_quantity"], next_smooth_quantity(17))


class BagDesignEngineTests(TestCase):
    def setUp(self):
        self.design = build_bag_design_candidates(100, 80, 20, 18)

    def test_dimensions_opening_scores_ranking_and_deduplication(self):
        candidates = self.design["candidates"]
        self.assertGreater(len(candidates), 1)
        self.assertTrue(all(row["bag_width"] <= row["bag_length"] for row in candidates))
        self.assertTrue(all(row["opening_dimension"] == "width" for row in candidates))
        self.assertTrue(all(
            row["bag_length"] == row["bundle_length"] + row["bundle_height"] + 12
            and row["bag_width"] == row["bundle_width"] + row["bundle_height"] + 2
            for row in candidates
        ))
        self.assertEqual(candidates[0]["bundle_cubicity_score"], max(row["bundle_cubicity_score"] for row in candidates))
        self.assertTrue(all("bag_squareness_score" not in row for row in candidates))

    def test_net_content_weight_ignores_stale_package_values(self):
        config = default_bag_config()
        config.update({
            "mode": "design", "action": "run_design", "product_l": "100", "product_w": "80",
            "product_h": "20", "product_weight": "50", "desired_qty": "17", "bag_weight": "10",
            "bag_max_payload": "1000",
        })
        analysis = analyze_bag_config(config, "run_design")
        selected = analysis["result"]
        self.assertEqual(selected["additional_capacity"], selected["design_quantity"] - 17)
        self.assertEqual(selected["net_content_weight"], selected["design_quantity"] * 50)
        self.assertFalse({"packaging_weight", "total_weight", "payload_capacity", "payload_usage", "remaining_payload_capacity"} & selected.keys())
        json.dumps(selected["render_data"])

    def test_canonical_dimensions_cover_symmetry_prime_and_permutations(self):
        cases = [(100, 80, 20, 12), (100, 100, 20, 12), (100, 100, 100, 12), (400, 200, 200, 12), (100, 80, 20, 17)]
        for case in cases:
            with self.subTest(case=case):
                first = build_bag_design_candidates(*case)
                second = build_bag_design_candidates(*case)
                keys = [row["arrangement_id"] for row in first["candidates"]]
                self.assertEqual(len(keys), len(set(keys)))
                self.assertTrue(all(row["bag_width"] <= row["bag_length"] for row in first["candidates"]))
                self.assertEqual(
                    [(row["candidate_id"], row["arrangement_id"], row["arrangement"], row["product_orientation"]) for row in first["candidates"]],
                    [(row["candidate_id"], row["arrangement_id"], row["arrangement"], row["product_orientation"]) for row in second["candidates"]],
                )
        duplicate_case = build_bag_design_candidates(400, 200, 200, 12)
        container_case = build_container_design_candidates((400, 200, 200), 12, 1, 1, 1)
        self.assertEqual(duplicate_case["generated_candidate_count"], 54)
        self.assertEqual(len(duplicate_case["candidates"]), 16)
        self.assertEqual(
            [row["arrangement_id"] for row in duplicate_case["candidates"]],
            [row["arrangement_id"] for row in container_case["candidates"]],
        )

    def test_rotation_restrictions_match_container_arrangements(self):
        bag = build_bag_design_candidates(100, 80, 20, 18, 0, 0, 1)
        container = build_container_design_candidates((100, 80, 20), 18, 0, 0, 1)
        self.assertEqual(
            [row["arrangement_id"] for row in bag["candidates"]],
            [row["arrangement_id"] for row in container["candidates"]],
        )
        self.assertTrue(all(row["orientation_index"] in (0, 2) for row in bag["candidates"]))

    def test_selection_mode_calculation_is_unchanged(self):
        info = compute_max_quantity_for_bag(100, 80, 20, 132, 102)
        self.assertEqual(info["max_quantity"], 1)


class ContainerDesignEngineTests(TestCase):
    def setUp(self):
        self.design = build_container_design_candidates((100, 80, 20), 18, 1, 1, 1)

    def test_arrangements_bounding_boxes_scores_and_deduplication(self):
        candidates = self.design["candidates"]
        self.assertGreater(len(candidates), 1)
        for row in candidates:
            self.assertEqual(row["rows"] * row["columns"] * row["layers"], row["design_quantity"])
            dims = (row["container_length"], row["container_width"], row["container_height"])
            self.assertGreaterEqual(row["container_length"], row["container_width"])
            self.assertAlmostEqual(row["container_cubicity_score"], min(dims) / max(dims), places=6)
            self.assertEqual(len(row["render_data"]["products"]), row["design_quantity"])
            self.assertEqual(row["render_data"]["container"]["length"], row["container_length"])
        self.assertEqual(candidates[0]["container_cubicity_score"], max(row["container_cubicity_score"] for row in candidates))
        keys = [(r["container_length"], r["container_width"], r["container_height"]) for r in candidates]
        self.assertEqual(len(keys), len(set(keys)))

    def test_rotation_restrictions_and_selection_mode(self):
        restricted = build_container_design_candidates((100, 80, 20), 18, 0, 0, 1)
        self.assertTrue(all(row["orientation_index"] in (0, 2) for row in restricted["candidates"]))
        self.assertEqual(compute_max_quantity_only((100, 80, 20), (200, 160, 40), 1, 1, 1), 8)

    def test_net_content_weight_ignores_stale_package_values(self):
        form = ContainerSelectionMode1Form({
            "mode": "design", "action": "run_design", "product_source": "manual",
            "product_l": 100, "product_w": 80, "product_h": 20, "product_weight": 50, "desired_qty": 17,
            "r1": "on", "r2": "on", "r3": "on", "container_source": "manual", "box_weight": 100,
            "box_max_payload": 1000,
        })
        self.assertTrue(form.is_valid(), form.errors)
        analysis = analyze_container_form(form, form.cleaned_data)
        selected = analysis["result"]
        self.assertEqual(selected["net_content_weight"], selected["design_quantity"] * 50)
        self.assertFalse({"packaging_weight", "total_weight", "payload_capacity", "payload_usage", "remaining_payload_capacity"} & selected.keys())
        json.dumps(selected["render_data"])

    def test_canonical_rsc_dimensions_cover_required_cases(self):
        cases = [
            ((400, 200, 200), 12, 1, 1, 1),
            ((100, 80, 20), 12, 1, 1, 1),
            ((100, 100, 20), 12, 1, 1, 1),
            ((100, 100, 100), 12, 1, 1, 1),
            ((100, 80, 20), 17, 1, 1, 1),
            ((100, 80, 20), 12, 0, 0, 1),
        ]
        for case in cases:
            with self.subTest(case=case):
                first = build_container_design_candidates(*case)
                second = build_container_design_candidates(*case)
                keys = [(row["container_length"], row["container_width"], row["container_height"]) for row in first["candidates"]]
                self.assertEqual(len(keys), len(set(keys)))
                self.assertTrue(all(length >= width for length, width, _height in keys))
                self.assertEqual(
                    [(row["candidate_id"], row["arrangement"], row["product_orientation"]) for row in first["candidates"]],
                    [(row["candidate_id"], row["arrangement"], row["product_orientation"]) for row in second["candidates"]],
                )
                for row in first["candidates"]:
                    container = row["render_data"]["container"]
                    self.assertEqual((container["length"], container["width"], container["height"]), keys[row["rank"] - 1])
                    self.assertTrue(all(product["x"] + product["dx"] <= container["length"] for product in row["render_data"]["products"]))
                    self.assertTrue(all(product["y"] + product["dy"] <= container["width"] for product in row["render_data"]["products"]))
        duplicate_case = build_container_design_candidates((400, 200, 200), 12, 1, 1, 1)
        self.assertEqual(duplicate_case["generated_candidate_count"], 54)
        self.assertEqual(len(duplicate_case["candidates"]), 16)
        self.assertGreater(len({row["container_height"] for row in duplicate_case["candidates"]}), 1)


class DesignModeSurfaceParityTests(TestCase):
    snapshot = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    bag_data = {
        "mode": "design", "action": "run_design", "product_source": "manual",
        "product_l": "100", "product_w": "80", "product_h": "20", "product_weight": "50",
        "desired_qty": "17", "bag_weight": "10", "bag_max_payload": "1000",
        "rotation_permissions_present": "1", "r1": "on", "r2": "on", "r3": "on",
    }
    container_data = {
        "mode": "design", "action": "run_design", "product_source": "manual",
        "product_l": "100", "product_w": "80", "product_h": "20", "product_weight": "50",
        "desired_qty": "18", "r1": "on", "r2": "on", "r3": "on", "box_weight": "100",
        "box_max_payload": "5000",
    }

    def test_standalone_pages_render_design_tables_and_json_safe_scenes(self):
        bag = self.client.post(reverse("bag_selection_mode1"), self.bag_data)
        self.assertEqual(bag.status_code, 200)
        self.assertContains(bag, "Bag design alternatives")
        self.assertEqual(bag.context["result"]["candidate_id"], bag.context["design_candidates"][0]["candidate_id"])
        json.dumps(bag.context["threejs_scene"])

        container = self.client.post(reverse("container_selection_mode1"), self.container_data)
        self.assertEqual(container.status_code, 200)
        self.assertContains(container, "Container design alternatives")
        self.assertEqual(container.context["result"]["candidate_id"], container.context["design_candidates"][0]["candidate_id"])
        json.dumps(container.context["threejs_scene"])

    def test_workflow_matches_standalone_and_non_default_selection_propagates(self):
        standalone = self.client.post(reverse("container_selection_mode1"), self.container_data)
        standalone_ids = [row["candidate_id"] for row in standalone.context["design_candidates"]]

        self.client.post(reverse("full_packaging_mode"), {"action": "add_step", "step_type": "container", "after_index": "start"})
        workflow_post = {"action": "run_step", "index": "0", **{f"{key}_0": value for key, value in self.container_data.items()}}
        workflow_post["action_0"] = "run_design"
        self.client.post(reverse("full_packaging_mode"), workflow_post)
        workflow = self.client.session["full_packaging_mode_session"]
        step = workflow["steps"][0]
        self.assertEqual([row["candidate_id"] for row in step["design_candidates"]], standalone_ids)
        self.assertEqual(step["result"]["candidate_id"], standalone_ids[0])
        self.assertNotIn("tool_mode", step["config"])
        json.dumps(workflow)

        selected_id = standalone_ids[1]
        workflow_post["action_0"] = "select_design_candidate"
        workflow_post["selected_design_candidate_id_0"] = selected_id
        self.client.post(reverse("full_packaging_mode"), workflow_post)
        selected_step = self.client.session["full_packaging_mode_session"]["steps"][0]
        self.assertEqual(selected_step["pending_result"]["selected_candidate_id"], selected_id)
        self.client.post(reverse("full_packaging_mode"), {"action": "use_step_result", "index": "0"})
        committed = self.client.session["full_packaging_mode_session"]["steps"][0]["selected"]
        self.assertEqual(committed["selected_candidate_id"], selected_id)

    def test_bag_workflow_parity(self):
        standalone = self.client.post(reverse("bag_selection_mode1"), self.bag_data)
        standalone_ids = [row["candidate_id"] for row in standalone.context["design_candidates"]]
        self.client.post(reverse("full_packaging_mode"), {"action": "add_step", "step_type": "bag", "after_index": "start"})
        workflow_post = {"action": "run_step", "index": "0", **{f"{key}_0": value for key, value in self.bag_data.items()}}
        workflow_post["action_0"] = "run_design"
        self.client.post(reverse("full_packaging_mode"), workflow_post)
        step = self.client.session["full_packaging_mode_session"]["steps"][0]
        self.assertEqual([row["candidate_id"] for row in step["design_candidates"]], standalone_ids)
        self.assertEqual(step["result"]["render_data"], standalone.context["result"]["render_data"])
        self.assertEqual(
            [row["arrangement_id"] for row in step["design_candidates"]],
            [row["arrangement_id"] for row in standalone.context["design_candidates"]],
        )
        self.assertNotIn("tool_mode", step["config"])

    def test_stale_package_inputs_do_not_change_candidates_or_serialization(self):
        bag_a = self.client.post(reverse("bag_selection_mode1"), {**self.bag_data, "bag_weight": "10", "bag_max_payload": "1000"})
        bag_b = self.client.post(reverse("bag_selection_mode1"), {**self.bag_data, "bag_weight": "999", "bag_max_payload": "1"})
        self.assertEqual(bag_a.context["design_candidates"], bag_b.context["design_candidates"])
        container_a = self.client.post(reverse("container_selection_mode1"), {**self.container_data, "box_weight": "10", "box_max_payload": "1000"})
        container_b = self.client.post(reverse("container_selection_mode1"), {**self.container_data, "box_weight": "999", "box_max_payload": "1"})
        self.assertEqual(container_a.context["design_candidates"], container_b.context["design_candidates"])
        forbidden = {"packaging_weight", "total_weight", "payload_capacity", "payload_usage", "remaining_payload_capacity"}
        self.assertFalse(forbidden & bag_b.context["result"].keys())
        self.assertFalse(forbidden & container_b.context["result"].keys())

    def test_design_reports_use_selected_dimensions_and_threejs_snapshot(self):
        self.client.post(reverse("bag_selection_mode1"), self.bag_data)
        bag_pdf = self.client.post(reverse("bag_selection_export_pdf"), {"design_export": "1", "threejs_snapshot": self.snapshot})
        self.assertEqual(bag_pdf.status_code, 200)
        self.assertEqual(bag_pdf["Content-Type"], "application/pdf")
        self.assertGreater(len(bag_pdf.content), 1000)

        self.client.post(reverse("container_selection_mode1"), self.container_data)
        container_pdf = self.client.post(reverse("container_selection_export_pdf"), {"design_export": "1", "threejs_snapshot": self.snapshot})
        self.assertEqual(container_pdf.status_code, 200)
        self.assertEqual(container_pdf["Content-Type"], "application/pdf")
        self.assertGreater(len(container_pdf.content), 1000)


class DesignModeValidationTests(TestCase):
    def test_missing_invalid_quantity_and_no_orientation_messages(self):
        missing = self.client.post(reverse("bag_selection_mode1"), {
            "mode": "design", "product_source": "manual", "product_l": 100, "product_w": 80, "product_h": 20,
        })
        self.assertContains(missing, "positive whole number")
        invalid = self.client.post(reverse("container_selection_mode1"), {
            "mode": "design", "product_source": "manual", "product_l": 100, "product_w": 80,
            "product_h": 20, "desired_qty": 3, "container_source": "manual", "action": "run_design",
        })
        self.assertContains(invalid, "permitted product orientation")


class DesignModeContractTests(TestCase):
    def test_forms_expose_one_authoritative_three_option_mode(self):
        expected = ["design", "single", "optimal"]
        self.assertEqual([value for value, _label in BagSelectionForm.base_fields["mode"].choices], expected)
        self.assertEqual([value for value, _label in ContainerSelectionMode1Form.base_fields["mode"].choices], expected)
        self.assertNotIn("tool_mode", BagSelectionForm.base_fields)
        self.assertNotIn("tool_mode", ContainerSelectionMode1Form.base_fields)
        for url in (reverse("bag_selection_mode1"), reverse("container_selection_mode1")):
            response = self.client.get(url)
            self.assertEqual(response.content.count(b'name="mode"'), 1)
            self.assertNotContains(response, 'name="tool_mode"')
            self.assertContains(response, "Design Mode")
            self.assertContains(response, "Single")
            self.assertContains(response, "Optimal")

    def test_legacy_mode_is_read_but_never_written(self):
        for sanitizer in (sanitize_bag_config_for_session, sanitize_container_config_for_session):
            design = sanitizer({"tool_mode": "design", "mode": "single"})
            self.assertEqual(design["mode"], "design")
            self.assertNotIn("tool_mode", design)
            single = sanitizer({"tool_mode": "selection", "mode": "single"})
            optimal = sanitizer({"tool_mode": "selection", "mode": "optimal"})
            self.assertEqual(single["mode"], "single")
            self.assertEqual(optimal["mode"], "optimal")
            self.assertNotIn("tool_mode", single)
            self.assertNotIn("tool_mode", optimal)

        legacy = self.client.post(reverse("bag_selection_mode1"), {
            "tool_mode": "design", "mode": "single", "action": "run_design", "product_source": "manual",
            "product_l": 100, "product_w": 80, "product_h": 20, "desired_qty": 12,
        })
        self.assertEqual(legacy.context["current_mode"], "design")
        self.assertTrue(legacy.context["design_candidates"])

    def test_shared_scroll_contract_is_present(self):
        root = Path(__file__).resolve().parents[1]
        css = (root / "static" / "css" / "app_theme.css").read_text(encoding="utf-8")
        script = (root / "static" / "js" / "tool_scroll_preservation.js").read_text(encoding="utf-8")
        bag_template = (root / "packagingapp" / "templates" / "bag_selection" / "partials" / "_bag_selection_design_table.html").read_text(encoding="utf-8")
        container_template = (root / "packagingapp" / "templates" / "container_selection_tool" / "partials" / "_container_selection_design_table.html").read_text(encoding="utf-8")
        selected_row_restore = (root / "packagingapp" / "templates" / "shared" / "_design_results_scroll_restore.html").read_text(encoding="utf-8")
        self.assertIn("max-height: min(60vh, 700px)", css)
        self.assertIn("position: sticky", css)
        self.assertIn("overflow-y: auto", css)
        self.assertIn("data-preserve-inner-scroll", bag_template)
        self.assertIn("data-preserve-inner-scroll", container_template)
        self.assertIn("shared/_design_results_scroll_restore.html", bag_template)
        self.assertIn("shared/_design_results_scroll_restore.html", container_template)
        self.assertIn("scrollArea.scrollTop", script)
        self.assertIn("restoreInnerScroll", script)
        self.assertIn("revealSelectedRow", selected_row_restore)
        self.assertIn(".tool-row-selected", selected_row_restore)
