import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.test import TestCase, SimpleTestCase
from django.urls import reverse

from packagingapp.tools.transport.serializers import serialize_transport_threejs_scene
from packagingapp.tools.transport.service import analyze_transport_capacity
from packagingapp.forms import ContainerToolForm


class TransportVisualizationContractTests(SimpleTestCase):
    def test_space_evenly_is_the_fourth_form_choice(self):
        self.assertEqual(
            ContainerToolForm.PACKING_MODE_CHOICES,
            [
                ("maximum_utilization", "Maximum utilization"),
                ("space_evenly", "Space evenly"),
                ("accessible_sequence_loading", "Sequence loading"),
                ("sequence_loading", "Strict sequence loading"),
            ],
        )

    def test_space_evenly_capacity_service_keeps_mode_and_auto_quantity(self):
        analysis = analyze_transport_capacity(
            {
                "container_source": "manual",
                "packing_mode": "space_evenly",
                "container_l": 400,
                "container_w": 200,
                "container_h": 100,
                "max_weight": None,
                "tare_weight": None,
            },
            [{
                "name": "Auto cube",
                "length": 100,
                "width": 100,
                "height": 100,
                "qty": 1,
                "max_qty": True,
                "stackable": True,
                "weight": 0,
                "sequence": 1,
                "r1": True,
                "r2": False,
                "r3": False,
            }],
        )
        self.assertTrue(analysis["ok"])
        self.assertEqual(analysis["safe_rows"][0]["qty"], 8)
        self.assertEqual(analysis["result"]["packing_mode"], "space_evenly")
        self.assertEqual(analysis["result"]["space_evenly_target_total_units"], 8)

    def test_three_approved_camera_presets_and_loading_default(self):
        root = Path(settings.BASE_DIR)
        partial = (
            root
            / "packagingapp/templates/container_tool/partials/"
            "_transport_result_section.html"
        ).read_text(encoding="utf-8")
        viewer = (
            root / "static/js/transport_container_threejs_viewer.js"
        ).read_text(encoding="utf-8")

        self.assertEqual(partial.count('data-transport-threejs-view="'), 3)
        self.assertIn('data-transport-threejs-view="loading"', partial)
        self.assertIn('data-transport-threejs-view="opposite"', partial)
        self.assertIn('data-transport-threejs-view="top"', partial)
        self.assertNotIn('data-transport-threejs-view="reset"', partial)
        self.assertNotIn('data-transport-threejs-view="front"', partial)
        self.assertNotIn('data-transport-threejs-view="side"', partial)
        self.assertIn(
            'class="btn btn-app-outline btn-sm active" '
            'data-transport-threejs-view="loading"',
            partial,
        )
        self.assertIn(
            'const TRANSPORT_REPORT_VIEWS = Object.freeze(["loading", "opposite", "top"]);',
            viewer,
        )
        self.assertIn('currentViewName: "loading"', viewer)
        self.assertIn("function applyTransportView(instance, viewName", viewer)
        self.assertIn("function fitTransportView(instance, preset, width, height)", viewer)
        self.assertIn("camera.up.set(...preset.up)", viewer)

    def test_product_identity_color_and_legend_metadata_follow_row_index(self):
        summary = {
            "placed_units": 3,
            "product_rows": [
                {"name": "Main pallet load", "length": 1200, "width": 800, "height": 1225, "qty_requested": 1},
                {"name": "Secondary carton", "length": 500, "width": 700, "height": 300, "qty_requested": 1},
                {"name": "Small carton", "length": 400, "width": 350, "height": 300, "qty_requested": 1},
            ],
        }
        placements = [
            SimpleNamespace(product_name="Small carton", row_index=2, x=1700, y=0, z=0, l=400, w=350, h=300),
            SimpleNamespace(product_name="Main pallet load", row_index=0, x=0, y=0, z=0, l=1200, w=800, h=1225),
            SimpleNamespace(product_name="Secondary carton", row_index=1, x=1200, y=0, z=0, l=500, w=700, h=300),
        ]
        container = {"L": 5900, "W": 2352, "H": 2395}

        first = serialize_transport_threejs_scene(container, placements, summary)
        second = serialize_transport_threejs_scene(container, list(reversed(placements)), summary)
        first_colors = {
            item["product_id"]: item["color"] for item in first["items"]
        }
        second_colors = {
            item["product_id"]: item["color"] for item in second["items"]
        }

        self.assertEqual(
            [product["product_id"] for product in first["products"]],
            ["P1", "P2", "P3"],
        )
        self.assertEqual(first_colors, second_colors)
        self.assertEqual(
            {
                product["product_id"]: product["color"]
                for product in first["products"]
            },
            first_colors,
        )
        self.assertEqual(
            [
                (item["x"], item["y"], item["z"], item["dx"], item["dy"], item["dz"])
                for item in first["items"]
            ],
            [
                (placement.x, placement.y, placement.z, placement.l, placement.w, placement.h)
                for placement in placements
            ],
        )
        json.dumps(first)


class TransportVisualizationSurfaceTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="kollipack-transport-view-test-")
        self.analysis_data = {
            "action": "run_analysis",
            "container_source": "manual",
            "packing_mode": "maximum_utilization",
            "container_l": "2400",
            "container_w": "1200",
            "container_h": "1200",
            "max_weight": "1000",
            "tare_weight": "200",
            "item_name[]": ["Pallet A"],
            "item_length[]": ["1200"],
            "item_width[]": ["800"],
            "item_height[]": ["1000"],
            "item_qty[]": ["2"],
            "item_max_qty[]": ["0"],
            "item_weight[]": ["100"],
            "item_sequence[]": ["1"],
            "item_r1[]": ["1"],
            "item_r2[]": ["0"],
            "item_r3[]": ["0"],
        }

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_standalone_legend_matches_scene_and_pdf_requires_three_views(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.post(reverse("container_tool"), self.analysis_data)
        self.assertEqual(response.status_code, 200)
        scene = response.context["threejs_scene"]
        self.assertEqual(response.content.count(b"data-transport-threejs-view="), 3)
        self.assertContains(response, "data-transport-product-legend")
        self.assertEqual(
            self.client.session["transport_container_last_export"]["product_legend"],
            scene["products"],
        )

        with self.settings(MEDIA_ROOT=self.media_root):
            missing = self.client.post(reverse("container_tool_export_pdf"), {})
        self.assertEqual(missing.status_code, 400)
        self.assertIn(b"Loading, Opposite Side and Top", missing.content)

    def test_public_calculator_inherits_space_evenly_from_shared_form(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(reverse("transport_container_calculator"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="space_evenly"', count=1)
        self.assertContains(response, "Space evenly")

    def test_standalone_space_evenly_serializes_diagnostics(self):
        data = dict(self.analysis_data)
        data["packing_mode"] = "space_evenly"
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.post(reverse("container_tool"), data)

        self.assertEqual(response.status_code, 200)
        result = response.context["result"]
        self.assertEqual(result["packing_mode"], "space_evenly")
        self.assertEqual(result["strategy"], "space_evenly")
        self.assertIn("space_evenly_effective_height", result)
        self.assertContains(response, "Packing mode: Space evenly")
        json.dumps(result)

    def test_workflow_viewer_ids_are_prefixed_and_unique(self):
        self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "transport"},
        )
        workflow_data = dict(self.analysis_data)
        workflow_data.update({
            "action": "run_step",
            "index": "0",
            "step_action_0": "run_analysis",
            "container_source_0": "manual",
            "container_l_0": "2400",
            "container_w_0": "1200",
            "container_h_0": "1200",
            "max_weight_0": "1000",
            "tare_weight_0": "200",
            "packing_mode_0": "space_evenly",
        })
        with self.settings(MEDIA_ROOT=self.media_root):
            run_response = self.client.post(reverse("full_packaging_mode"), workflow_data)
            page = self.client.get(reverse("full_packaging_mode"))

        self.assertEqual(run_response.status_code, 302)
        self.assertContains(page, 'id="transportThreeJsViewer_0"', count=1)
        self.assertContains(page, 'id="transportThreeJsScene_0"', count=1)
        self.assertEqual(page.content.count(b"data-transport-threejs-view="), 3)
        self.assertContains(page, "data-transport-product-legend")
        workflow = self.client.session["full_packaging_mode_session"]
        self.assertEqual(
            workflow["steps"][0]["config"]["packing_mode"],
            "space_evenly",
        )
        self.assertEqual(
            workflow["steps"][0]["result"]["packing_mode"],
            "space_evenly",
        )
        self.assertContains(page, "Packing mode: Space evenly")
        json.dumps(workflow)
