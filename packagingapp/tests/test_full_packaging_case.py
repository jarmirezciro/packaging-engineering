import json

from django.test import TestCase
from django.urls import reverse

from packagingapp.views.full_packaging import (
    _decorate_transport_scene_with_pallet_visualization,
)


class FullPackagingCaseTests(TestCase):
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
        self.assertTrue(transport_row["r1"])
        self.assertFalse(transport_row["r2"])
        self.assertFalse(transport_row["r3"])
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
                "item_r1[]": ["0"],
                "item_r2[]": ["1"],
                "item_r3[]": ["1"],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.client.get(case_url)
        updated_row = self.client.session[key]["steps"][2]["config"]["product_rows"][0]
        self.assertFalse(updated_row["r1"])
        self.assertTrue(updated_row["r2"])
        self.assertTrue(updated_row["r3"])
        self.assertTrue(updated_row["stackable"])
