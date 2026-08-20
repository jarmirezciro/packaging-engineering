import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from packagingapp.tools.full_packaging.chain_optimizer import (
    build_design_candidate_payload,
    build_design_chain_ui,
    invalidate_design_chain_optimizations,
    optimize_design_chain,
    terminal_capacity_labels,
)
from packagingapp.views.full_packaging import (
    DESIGN_CHAIN_PALLET_STALE_MESSAGE,
    SESSION_KEY,
    _evaluate_design_chain_step,
    _new_bag_step,
    _new_container_step,
    _new_pallet_step,
    _new_transport_step,
    _save_workflow,
)


def container_candidate(candidate_id, rank, quantity, length=100):
    return {
        "candidate_id": candidate_id,
        "rank": rank,
        "arrangement": f"Arrangement {candidate_id}",
        "product_orientation": "L × W × H",
        "desired_quantity": quantity,
        "design_quantity": quantity,
        "additional_capacity": 0,
        "container_length": length,
        "container_width": 80,
        "container_height": 60,
        "container_cubicity_score": 0.9,
        "volumetric_efficiency": 0.8,
        "required_container_volume": length * 80 * 60,
        "net_content_weight": None,
        "net_content_weight_display": "—",
        "render_data": {"candidate": candidate_id},
    }


def bag_candidate(candidate_id, rank, quantity, length=100):
    return {
        "candidate_id": candidate_id,
        "rank": rank,
        "arrangement_id": f"arr-{candidate_id}",
        "arrangement": f"Arrangement {candidate_id}",
        "product_orientation": "L × W × H",
        "desired_quantity": quantity,
        "design_quantity": quantity,
        "additional_capacity": 0,
        "bundle_length": length,
        "bundle_width": 80,
        "bundle_height": 60,
        "bag_length": length + 25,
        "bag_width": 100,
        "bundle_cubicity_score": 0.9,
        "bag_area": (length + 25) * 100,
        "net_content_weight": None,
        "net_content_weight_display": "—",
        "render_data": {"candidate": candidate_id},
    }


def source_step(step_type="container", candidates=None, selected_id="a"):
    return {
        "type": step_type,
        "config": {"mode": "design", "selected_design_candidate_id": selected_id},
        "design_candidates": candidates or [container_candidate("a", 1, 8)],
        "selected_design_candidate_id": selected_id,
        "selected": None,
        "pending_result": None,
    }


def downstream_step(step_type, multiplier, **config):
    return {
        "type": step_type,
        "config": {"multiplier": multiplier, **config},
        "selected": {"preserved": True},
        "pending_result": None,
    }


class ChainOptimizerTests(SimpleTestCase):
    def evaluator(self, calls, unavailable_lengths=None):
        unavailable_lengths = set(unavailable_lengths or [])

        def evaluate(steps, index):
            incoming = steps[index - 1]["pending_result"] or steps[index - 1]["selected"]
            calls.append((index, steps[index]["type"], incoming["total_base_units"]))
            steps[index]["config"]["temporary_marker"] = True
            if incoming.get("length") in unavailable_lengths:
                return None
            multiplier = int(steps[index]["config"]["multiplier"])
            output = {
                "length": incoming.get("length"),
                "width": incoming.get("width"),
                "height": incoming.get("height"),
                "units_per_parent": multiplier,
                "total_base_units": incoming["total_base_units"] * multiplier,
            }
            steps[index]["pending_result"] = output
            return output

        return evaluate

    def test_generic_ordered_traversal_supports_required_chains_and_repeated_types(self):
        cases = [
            ("container", ["pallet"]),
            ("bag", ["container", "pallet"]),
            ("container", ["container", "pallet", "transport"]),
        ]
        for source_type, downstream_types in cases:
            with self.subTest(source_type=source_type, downstream_types=downstream_types):
                candidate = (
                    bag_candidate("a", 1, 8)
                    if source_type == "bag"
                    else container_candidate("a", 1, 8)
                )
                workflow = {"steps": [source_step(source_type, [candidate])] + [
                    downstream_step(step_type, 2) for step_type in downstream_types
                ]}
                calls = []
                result = optimize_design_chain(workflow, 0, self.evaluator(calls))
                self.assertEqual([step_type for _index, step_type, _units in calls], downstream_types)
                self.assertEqual(result["candidate_results"]["a"]["final_base_units"], 8 * (2 ** len(downstream_types)))

    def test_base_units_multiply_to_terminal_and_source_uses_upstream_total(self):
        workflow = {"steps": [
            {"type": "bag", "selected": {"total_base_units": 3}, "pending_result": None},
            source_step("container", [container_candidate("a", 1, 8)]),
            downstream_step("pallet", 60),
            downstream_step("transport", 24),
        ]}
        calls = []
        result = optimize_design_chain(workflow, 1, self.evaluator(calls))
        self.assertEqual(result["candidate_results"]["a"]["final_base_units"], 3 * 8 * 60 * 24)
        self.assertEqual(calls, [(2, "pallet", 24), (3, "transport", 1440)])

    def test_sorting_uses_capacity_then_original_rank_and_keeps_unavailable_last(self):
        candidates = [
            container_candidate("a", 1, 8, 10),
            container_candidate("b", 2, 10, 20),
            container_candidate("c", 3, 4, 30),
            container_candidate("d", 4, 8, 40),
        ]
        workflow = {"steps": [source_step("container", candidates, selected_id="b"), downstream_step("pallet", 1)]}
        original = deepcopy(workflow)

        def evaluate(steps, index):
            incoming = steps[index - 1]["pending_result"]
            if incoming["length"] == 48:
                return None
            multipliers = {18: 5, 28: 4, 38: 20}
            output = {"total_base_units": incoming["total_base_units"] * multipliers[incoming["length"]]}
            steps[index]["pending_result"] = output
            return output

        result = optimize_design_chain(workflow, 0, evaluate)
        self.assertEqual(result["sorted_candidate_ids"], ["c", "a", "b", "d"])
        self.assertEqual(result["candidate_results"]["d"]["status"], "unavailable")
        self.assertEqual(workflow, original)
        self.assertEqual(workflow["steps"][0]["selected_design_candidate_id"], "b")

    def test_equivalent_source_payloads_are_evaluated_once(self):
        candidates = [
            container_candidate("a", 1, 8, 100),
            container_candidate("b", 2, 8, 100),
        ]
        workflow = {"steps": [source_step("container", candidates), downstream_step("pallet", 10)]}
        calls = []
        result = optimize_design_chain(workflow, 0, self.evaluator(calls))
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["candidate_results"]["a"], result["candidate_results"]["b"])

    def test_failed_terminal_does_not_fall_back_to_stale_selected_output(self):
        terminal = downstream_step("transport", 10)
        terminal["selected"] = {"total_base_units": 999999}
        workflow = {"steps": [source_step(), terminal]}
        result = optimize_design_chain(workflow, 0, lambda _steps, _index: None)
        self.assertEqual(result["candidate_results"]["a"]["status"], "unavailable")
        self.assertEqual(result["sorted_candidate_ids"], ["a"])
        self.assertIn("Transport Container", result["message"])

    def test_dynamic_labels_and_json_safe_state(self):
        expected = {
            "container": "Max base units / box",
            "bag": "Max base units / bag",
            "pallet": "Max base units / pallet",
            "transport": "Max base units / transport container",
        }
        for step_type, heading in expected.items():
            self.assertEqual(terminal_capacity_labels(step_type)[1], heading)

        workflow = {"steps": [source_step(), downstream_step("transport", 12)]}
        state = optimize_design_chain(workflow, 0, self.evaluator([]))
        json.dumps(state)
        self.assertEqual(state["column_label"], expected["transport"])

    def test_candidate_payload_parity_for_container_bag_and_upstream_units(self):
        upstream = {"total_base_units": 5}
        container = build_design_candidate_payload("container", container_candidate("a", 1, 8), upstream)
        bag = build_design_candidate_payload("bag", bag_candidate("b", 1, 6), upstream)
        self.assertEqual(container["total_base_units"], 40)
        self.assertEqual((container["length"], container["width"], container["height"]), (108, 88, 76))
        self.assertEqual((container["internal_length"], container["internal_width"], container["internal_height"]), (100, 80, 60))
        self.assertTrue(container["box_thickness_assumed"])
        self.assertEqual(bag["total_base_units"], 30)
        self.assertEqual((bag["length"], bag["width"], bag["height"]), (125, 100, 60))
        self.assertEqual(bag["selected_arrangement_id"], "arr-b")

    def test_container_candidate_payload_uses_provided_or_default_thickness(self):
        provided_candidate = container_candidate("provided", 1, 8, 600)
        provided_candidate.update({
            "container_width": 400,
            "container_height": 300,
            "box_thickness_mm": 5,
            "box_thickness_assumed": False,
        })
        provided = build_design_candidate_payload("container", provided_candidate)
        self.assertEqual((provided["length"], provided["width"], provided["height"]), (610, 410, 320))
        self.assertFalse(provided["box_thickness_assumed"])

        blank_candidate = dict(provided_candidate)
        blank_candidate.pop("box_thickness_mm")
        blank_candidate.pop("box_thickness_assumed")
        assumed = build_design_candidate_payload("container", blank_candidate)
        self.assertEqual((assumed["length"], assumed["width"], assumed["height"]), (608, 408, 316))
        self.assertTrue(assumed["box_thickness_assumed"])

    def test_invalidation_preserves_only_unchanged_source_row_selection(self):
        state = {
            "active": True,
            "terminal_step_index": 2,
            "terminal_step_type": "pallet",
        }
        steps = [
            {"design_chain_optimization": deepcopy(state)},
            {"design_chain_optimization": deepcopy(state)},
            {},
        ]
        invalidate_design_chain_optimizations(steps, changed_step_index=1, preserve_source=True)
        self.assertNotIn("design_chain_optimization", steps[0])
        self.assertIn("design_chain_optimization", steps[1])
        invalidate_design_chain_optimizations(steps, structural=True)
        self.assertNotIn("design_chain_optimization", steps[1])

        source_changed = [{"design_chain_optimization": deepcopy(state)}, {}]
        invalidate_design_chain_optimizations(source_changed, changed_step_index=0)
        self.assertNotIn("design_chain_optimization", source_changed[0])

    def test_display_order_is_transient_and_downstream_design_uses_one_selected_path(self):
        candidates = [container_candidate("a", 1, 8), container_candidate("b", 2, 6, 110)]
        step = source_step("container", candidates, selected_id="b")
        step["design_chain_optimization"] = {
            "active": True,
            "source_step_index": 0,
            "terminal_step_index": 1,
            "terminal_step_type": "container",
            "column_label": "Max base units / box",
            "candidate_results": {
                "a": {"status": "ok", "final_base_units": 80},
                "b": {"status": "ok", "final_base_units": 120},
            },
            "sorted_candidate_ids": ["b", "a"],
        }
        downstream = downstream_step("container", 2, mode="design", selected_design_candidate_id="only-this-one")
        ui = build_design_chain_ui(step, [step, downstream], 0)
        self.assertEqual([row["candidate_id"] for row in ui["display_candidates"]], ["b", "a"])
        self.assertEqual(ui["display_candidates"][0]["design_chain_final_base_units_display"], "120")
        self.assertEqual([row["candidate_id"] for row in step["design_candidates"]], ["a", "b"])

    def test_downstream_design_adapter_uses_current_candidate_once_without_branching(self):
        source = source_step()
        source["pending_result"] = build_design_candidate_payload(
            "container", source["design_candidates"][0]
        )
        downstream = source_step(
            "container",
            [container_candidate("down-a", 1, 2), container_candidate("down-b", 2, 3)],
            selected_id="down-b",
        )
        steps = [source, downstream]

        def analyze(form, config, **_kwargs):
            self.assertTrue(form.is_valid())
            self.assertEqual(config["selected_design_candidate_id"], "down-b")
            return {
                "ok": True,
                "mode": "design",
                "result": downstream["design_candidates"][1],
            }

        with patch(
            "packagingapp.views.full_packaging.get_container_packaging_catalogues",
            return_value=[],
        ), patch(
            "packagingapp.views.full_packaging.get_container_product_catalogues",
            return_value=[],
        ), patch(
            "packagingapp.views.full_packaging.analyze_container_capacity",
            side_effect=analyze,
        ) as analyze_mock:
            output = _evaluate_design_chain_step(steps, 1)
        self.assertEqual(analyze_mock.call_count, 1)
        self.assertEqual(output["total_base_units"], 24)

    def test_temporary_evaluation_preserves_live_pattern_and_transport_rows(self):
        source = source_step()
        pallet = downstream_step("pallet", 2)
        pallet["selected_result_key"] = "pattern-7"
        transport = downstream_step(
            "transport",
            3,
            product_rows=[{"qty": 4, "max_qty": True, "sequence": 1}],
        )
        workflow = {"steps": [source, pallet, transport]}
        original = deepcopy(workflow)
        optimize_design_chain(workflow, 0, self.evaluator([]))
        self.assertEqual(workflow, original)


class ChainOptimizerTemplateTests(SimpleTestCase):
    def test_container_and_bag_tables_are_workflow_only(self):
        container = container_candidate("a", 1, 8)
        bag = bag_candidate("b", 1, 8)
        ui = {
            "show": True,
            "active": False,
            "column_label": "Max base units / pallet",
            "message": "",
        }
        workflow_container = render_to_string(
            "container_selection_tool/partials/_container_selection_design_table.html",
            {"design_candidates": [container], "selected_design_candidate_id": "a", "container_ui": {"prefix": "0"}, "mode": "workflow", "design_chain_ui": ui},
        )
        workflow_bag = render_to_string(
            "bag_selection/partials/_bag_selection_design_table.html",
            {"design_candidates": [bag], "selected_design_candidate_id": "b", "bag_ui": {"prefix": "0"}, "mode": "workflow", "design_chain_ui": ui},
        )
        standalone_container = render_to_string(
            "container_selection_tool/partials/_container_selection_design_table.html",
            {"design_candidates": [container], "container_ui": {"prefix": ""}, "mode": "standalone", "design_chain_ui": ui},
        )
        standalone_bag = render_to_string(
            "bag_selection/partials/_bag_selection_design_table.html",
            {"design_candidates": [bag], "bag_ui": {"prefix": ""}, "mode": "standalone", "design_chain_ui": ui},
        )
        self.assertIn("Optimize final capacity", workflow_container)
        self.assertIn("Max base units / pallet", workflow_container)
        self.assertIn("Optimize final capacity", workflow_bag)
        self.assertIn("Max base units / pallet", workflow_bag)
        self.assertNotIn("Optimize final capacity", standalone_container)
        self.assertNotIn("Max base units / pallet", standalone_container)
        self.assertNotIn("Optimize final capacity", standalone_bag)
        self.assertNotIn("Max base units / pallet", standalone_bag)

    def test_no_downstream_or_non_design_mode_hides_workflow_controls(self):
        candidate = container_candidate("a", 1, 8)
        final_source = source_step("container", [candidate])
        self.assertFalse(build_design_chain_ui(final_source, [final_source], 0)["show"])
        final_source["config"]["mode"] = "single"
        self.assertFalse(build_design_chain_ui(final_source, [final_source, downstream_step("pallet", 1)], 0)["show"])


class CapacityOnlyEvaluationTests(TestCase):
    def setUp(self):
        self.source = source_step()
        self.source["pending_result"] = build_design_candidate_payload(
            "container", self.source["design_candidates"][0]
        )

    def test_optimizer_adapter_skips_all_presentation_paths(self):
        forbidden = [
            "packagingapp.tools.container.service.run_mode1_and_render",
            "packagingapp.tools.container.service.render_product_base_unit",
            "packagingapp.tools.bag.service.run_bag_mode1_and_render",
            "packagingapp.tools.palletization.service.selected_result_for_render",
            "packagingapp.tools.palletization.service.serialize_pallet_threejs_scene",
            "packagingapp.tools.transport.service.run_transport_analysis",
            "packagingapp.tools.transport.service.run_container_tool",
        ]
        patches = [patch(target, side_effect=AssertionError(target)) for target in forbidden]

        container = _new_container_step()
        container["config"].update({
            "mode": "single",
            "container_source": "manual",
            "box_l": 500,
            "box_w": 400,
            "box_h": 300,
        })
        bag = _new_bag_step()
        bag["config"].update({
            "mode": "single",
            "bag_source": "manual",
            "bag_length": 600,
            "bag_width": 500,
        })
        pallet = _new_pallet_step()
        pallet["config"].update({
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 144,
            "max_stack_height": 1200,
        })
        transport = _new_transport_step()
        transport["config"].update({
            "container_l": 500,
            "container_w": 400,
            "container_h": 300,
            "product_rows": [{
                "qty": 1,
                "max_qty": False,
                "sequence": 1,
                "r1": True,
                "r2": True,
                "r3": True,
            }],
        })
        pallet_row = {
            "pattern": "capacity-test",
            "stacking": "column",
            "total_boxes": 6,
            "used_height_mm": 600,
        }

        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            for active_patch in patches:
                active_patch.start()
            try:
                with patch(
                    "packagingapp.tools.palletization.service.run_palletization_analysis",
                    return_value=[pallet_row],
                ):
                    outputs = [
                        _evaluate_design_chain_step([deepcopy(self.source), container], 1),
                        _evaluate_design_chain_step([deepcopy(self.source), bag], 1),
                        _evaluate_design_chain_step([deepcopy(self.source), pallet], 1),
                        _evaluate_design_chain_step([deepcopy(self.source), transport], 1),
                    ]
            finally:
                for active_patch in reversed(patches):
                    active_patch.stop()

            self.assertEqual(list(Path(media_root).rglob("*")), [])

        self.assertTrue(all(output for output in outputs), outputs)
        self.assertEqual(outputs[2]["total_base_units"], 8 * 6)
        for output in outputs:
            self.assertNotIn("render_data", output)
            self.assertNotIn("pallet_visualization", output)
            json.dumps(output)

    def test_pallet_capacity_and_full_service_select_the_same_numeric_row(self):
        from packagingapp.tools.palletization.service import (
            analyze_palletization_capacity,
            analyze_palletization_config,
        )

        config = {
            "box_l": 400,
            "box_w": 300,
            "box_h": 200,
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 144,
            "max_stack_height": 1200,
            "max_width_stickout": 0,
            "max_length_stickout": 0,
        }
        rows = [{
            "pattern": "shared-core",
            "stacking": "column",
            "total_boxes": 24,
            "used_height_mm": 800,
            "interlock_possible": False,
            "interlock_possible_layer": False,
        }]
        with patch(
            "packagingapp.tools.palletization.service.run_palletization_analysis",
            side_effect=[deepcopy(rows), deepcopy(rows)],
        ), patch(
            "packagingapp.tools.palletization.service.selected_result_for_render",
            return_value={},
        ), patch(
            "packagingapp.tools.palletization.service.serialize_pallet_threejs_scene",
            return_value=None,
        ), patch(
            "packagingapp.tools.palletization.service.serialize_pallet_analysis_result",
            return_value={"selected_result": rows[0]},
        ):
            capacity = analyze_palletization_capacity(config)
            full = analyze_palletization_config(config)

        self.assertEqual(
            capacity["selected_row"]["total_boxes"],
            full["result"]["selected_row"]["total_boxes"],
        )
        self.assertEqual(capacity["effective_config"], full["effective_config"])

    def test_optimizer_and_normal_path_pass_same_external_carton_size_and_rank_on_it(self):
        candidate_a = container_candidate("thin", 2, 1, 390)
        candidate_a.update({
            "container_width": 390,
            "container_height": 300,
            "box_thickness_mm": 4,
            "box_thickness_assumed": False,
        })
        candidate_b = container_candidate("thick", 1, 1, 390)
        candidate_b.update({
            "container_width": 390,
            "container_height": 300,
            "box_thickness_mm": 10,
            "box_thickness_assumed": False,
        })

        pallet = _new_pallet_step()
        pallet["config"].update({
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 144,
            "max_stack_height": 1200,
        })
        received = []

        def controlled_pallet_capacity(*, config, **_kwargs):
            box_l = float(config["box_l"])
            box_w = float(config["box_w"])
            received.append((box_l, box_w, float(config["box_h"])))
            total_boxes = int(1200 // box_l) * int(800 // box_w)
            return {
                "ok": True,
                "effective_config": config,
                "selected_row": {
                    "pattern": "controlled-grid",
                    "stacking": "column",
                    "total_boxes": total_boxes,
                    "used_height_mm": 300,
                },
            }

        normal_source = source_step("container", [candidate_a], selected_id="thin")
        normal_source["pending_result"] = build_design_candidate_payload("container", candidate_a)

        optimizer_source = source_step(
            "container", [candidate_a, candidate_b], selected_id="thin"
        )
        workflow = {"steps": [optimizer_source, pallet]}

        with patch(
            "packagingapp.views.full_packaging.analyze_palletization_capacity",
            side_effect=controlled_pallet_capacity,
        ):
            normal_output = _evaluate_design_chain_step(
                [normal_source, deepcopy(pallet)], 1
            )
            optimized = optimize_design_chain(
                workflow, 0, _evaluate_design_chain_step
            )

        self.assertEqual(received[0], (398.0, 398.0, 316.0))
        self.assertEqual(received[0], received[1])
        self.assertEqual(received[2], (410.0, 410.0, 340.0))
        self.assertEqual(normal_output["total_base_units"], 6)
        self.assertEqual(optimized["candidate_results"]["thin"]["final_base_units"], 6)
        self.assertEqual(optimized["candidate_results"]["thick"]["final_base_units"], 2)
        self.assertEqual(optimized["sorted_candidate_ids"], ["thin", "thick"])


class ChainOptimizerViewTests(TestCase):
    def setUp(self):
        self.url = reverse("full_packaging_mode")

    def workflow(self):
        source = _new_container_step()
        source["config"].update({"mode": "design", "selected_design_candidate_id": "b"})
        source["design_candidates"] = [
            container_candidate("a", 1, 8),
            container_candidate("b", 2, 6, 110),
        ]
        source["selected_design_candidate_id"] = "b"
        source["pending_result"] = build_design_candidate_payload(
            "container", source["design_candidates"][1]
        )
        pallet = _new_pallet_step()
        return {"steps": [source, pallet], "show_add_bar_after": None}

    def save_session_workflow(self, workflow):
        session = self.client.session
        session[SESSION_KEY] = workflow
        session.save()

    def test_post_redirects_once_saves_json_safe_state_and_does_not_auto_select(self):
        workflow = self.workflow()
        self.save_session_workflow(workflow)
        state = {
            "active": True,
            "source_step_index": 0,
            "terminal_step_index": 1,
            "terminal_step_type": "pallet",
            "terminal_label": "pallet",
            "column_label": "Max base units / pallet",
            "candidate_results": {
                "a": {"status": "ok", "final_base_units": 200},
                "b": {"status": "ok", "final_base_units": 100},
            },
            "sorted_candidate_ids": ["a", "b"],
            "message": "",
        }
        with patch("packagingapp.views.full_packaging.optimize_design_chain", return_value=state), patch(
            "packagingapp.views.full_packaging._save_workflow", wraps=_save_workflow
        ) as save_mock:
            response = self.client.post(
                self.url,
                {"action": "optimize_design_final_capacity", "index": "0"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(save_mock.call_count, 1)
        saved = self.client.session[SESSION_KEY]
        self.assertEqual(saved["steps"][0]["selected_design_candidate_id"], "b")
        self.assertEqual(saved["steps"][0]["design_chain_optimization"], state)
        json.dumps(saved)

    def test_row_selection_preserves_optimized_order_and_stable_candidate_id(self):
        workflow = self.workflow()
        workflow["steps"][0]["design_chain_optimization"] = {
            "active": True,
            "source_step_index": 0,
            "terminal_step_index": 1,
            "terminal_step_type": "pallet",
            "column_label": "Max base units / pallet",
            "candidate_results": {
                "a": {"status": "ok", "final_base_units": 100},
                "b": {"status": "ok", "final_base_units": 200},
            },
            "sorted_candidate_ids": ["b", "a"],
            "message": "",
        }
        self.save_session_workflow(workflow)

        def select_candidate(step, _steps, _idx, _post):
            step["selected_design_candidate_id"] = "a"
            step["config"]["selected_design_candidate_id"] = "a"
            step["pending_result"] = build_design_candidate_payload(
                "container", step["design_candidates"][0]
            )

        with patch("packagingapp.views.full_packaging._process_container_step", side_effect=select_candidate):
            response = self.client.post(
                self.url,
                {
                    "action": "run_step",
                    "index": "0",
                    "step_action_0": "select_design_candidate",
                    "selected_design_candidate_id_0": "a",
                },
            )
        self.assertEqual(response.status_code, 302)
        saved = self.client.session[SESSION_KEY]
        self.assertEqual(saved["steps"][0]["selected_design_candidate_id"], "a")
        self.assertEqual(saved["steps"][0]["design_chain_optimization"]["sorted_candidate_ids"], ["b", "a"])

        page = self.client.get(self.url)
        displayed = page.context["steps"][0]["design_candidates_for_display"]
        self.assertEqual([row["candidate_id"] for row in displayed], ["b", "a"])
        self.assertEqual(page.context["steps"][0]["selected_design_candidate_id"], "a")

    def test_pallet_noop_refresh_preserves_optimized_order(self):
        workflow = self.workflow()
        workflow["steps"][0]["design_chain_optimization"] = {
            "active": True,
            "source_step_index": 0,
            "terminal_step_index": 1,
            "terminal_step_type": "pallet",
            "terminal_label": "pallet",
            "column_label": "Max base units / pallet",
            "candidate_results": {
                "a": {"status": "ok", "final_base_units": 200},
                "b": {"status": "ok", "final_base_units": 100},
            },
            "sorted_candidate_ids": ["a", "b"],
            "message": "",
        }
        self.save_session_workflow(workflow)

        response = self.client.post(
            self.url,
            {
                "action": "run_step",
                "index": "1",
                "step_action_1": "refresh",
                "show_advanced_1": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        saved = self.client.session[SESSION_KEY]
        self.assertEqual(
            saved["steps"][0]["design_chain_optimization"]["sorted_candidate_ids"],
            ["a", "b"],
        )

    def test_pallet_capacity_change_clears_ranking_with_rerun_message(self):
        workflow = self.workflow()
        workflow["steps"][0]["design_chain_optimization"] = {
            "active": True,
            "source_step_index": 0,
            "terminal_step_index": 1,
            "terminal_step_type": "pallet",
            "terminal_label": "pallet",
            "column_label": "Max base units / pallet",
            "candidate_results": {
                "a": {"status": "ok", "final_base_units": 200},
                "b": {"status": "ok", "final_base_units": 100},
            },
            "sorted_candidate_ids": ["a", "b"],
            "message": "",
        }
        self.save_session_workflow(workflow)

        response = self.client.post(
            self.url,
            {
                "action": "run_step",
                "index": "1",
                "step_action_1": "refresh",
                "pallet_l_1": "1400",
            },
        )
        self.assertEqual(response.status_code, 302)
        saved = self.client.session[SESSION_KEY]
        self.assertNotIn("design_chain_optimization", saved["steps"][0])
        self.assertEqual(
            saved["steps"][0]["design_chain_optimization_message"],
            DESIGN_CHAIN_PALLET_STALE_MESSAGE,
        )

    def test_pallet_layout_selection_preserves_ranking(self):
        workflow = self.workflow()
        workflow["steps"][0]["design_chain_optimization"] = {
            "active": True,
            "source_step_index": 0,
            "terminal_step_index": 1,
            "terminal_step_type": "pallet",
            "terminal_label": "pallet",
            "column_label": "Max base units / pallet",
            "candidate_results": {
                "a": {"status": "ok", "final_base_units": 200},
                "b": {"status": "ok", "final_base_units": 100},
            },
            "sorted_candidate_ids": ["a", "b"],
            "message": "",
        }
        self.save_session_workflow(workflow)

        response = self.client.post(
            self.url,
            {
                "action": "run_step",
                "index": "1",
                "step_action_1": "select_result",
                "selected_result_key_1": "alternate__column",
            },
        )
        self.assertEqual(response.status_code, 302)
        saved = self.client.session[SESSION_KEY]
        self.assertEqual(
            saved["steps"][0]["design_chain_optimization"]["sorted_candidate_ids"],
            ["a", "b"],
        )

    def test_interlock_preview_selection_preserves_numeric_ranking(self):
        workflow = self.workflow()
        workflow["steps"][1]["selected_result_key"] = "alternate__column"
        workflow["steps"][0]["design_chain_optimization"] = {
            "active": True,
            "source_step_index": 0,
            "terminal_step_index": 1,
            "terminal_step_type": "pallet",
            "terminal_label": "pallet",
            "column_label": "Max base units / pallet",
            "candidate_results": {
                "a": {"status": "ok", "final_base_units": 200},
                "b": {"status": "ok", "final_base_units": 100},
            },
            "sorted_candidate_ids": ["a", "b"],
            "message": "",
        }
        self.save_session_workflow(workflow)

        response = self.client.post(
            self.url,
            {
                "action": "run_step",
                "index": "1",
                "step_action_1": "select_result",
                "selected_result_key_1": "alternate__column__interlock_preview",
            },
        )
        self.assertEqual(response.status_code, 302)
        saved = self.client.session[SESSION_KEY]
        self.assertEqual(
            saved["steps"][0]["design_chain_optimization"]["sorted_candidate_ids"],
            ["a", "b"],
        )
