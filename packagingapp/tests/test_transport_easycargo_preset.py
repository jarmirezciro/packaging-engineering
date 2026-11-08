"""Public EasyCargo reproduction through the shared Transport calculator."""

import json
import shutil
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from packagingapp.tests.transport_physical_validator import (
    assert_transport_result_physical,
)
from packagingapp.tools.transport.case_presets import (
    get_transport_container_case_preset,
)
from packagingapp.utils.container_tool import engine


class EasyCargoEngineTests(SimpleTestCase):
    def benchmark_inputs(self, *, all_rotations):
        preset = get_transport_container_case_preset(
            "easycargo-40hc-mixed-cargo-benchmark"
        )
        config = preset["config"]
        container = {
            "L": config["container_l"],
            "W": config["container_w"],
            "H": config["container_h"],
            "packing_mode": config["packing_mode"],
        }
        rows = [
            {**row, "r1": all_rotations, "r2": all_rotations, "r3": True}
            for row in preset["rows"]
        ]
        return container, rows

    def test_r3_only_closes_gap_before_freezer_clean_row(self):
        container, rows = self.benchmark_inputs(all_rotations=False)
        result = engine.pack_container(container, rows)
        frontier = next(
            item for item in result["front_to_back_frontiers"]
            if (item["current_row_index"], item["next_row_index"]) == (2, 6)
        )
        self.assertEqual(frontier["selected_candidate_family"], "dgfe_extended")
        self.assertEqual(frontier["trial_frontier_end_x"], 9305)
        self.assertEqual(frontier["committed_clean_row_x"], 8785)
        self.assertEqual(frontier["x_end"], 9085)
        self.assertEqual(frontier["reclaimed_x_depth"], 220)
        self.assertEqual(result["front_to_back_x_used"], 11145)
        self.assertEqual(
            sum(item.row_index == 6 and item.x == 8785 for item in result["placements"]),
            42,
        )
        self.assertEqual(result["unplaced"], [])
        assert_transport_result_physical(self, result, container, rows)

    def test_all_rotation_families_pack_the_mixed_cargo_benchmark(self):
        container, rows = self.benchmark_inputs(all_rotations=True)
        collision_checks = 0
        rectangles_overlap = engine._frontier_rectangles_overlap

        def count_collision_check(first, second):
            nonlocal collision_checks
            collision_checks += 1
            return rectangles_overlap(first, second)

        with patch.object(engine, "_frontier_rectangles_overlap", count_collision_check):
            result = engine.pack_container(container, rows)

        physical = assert_transport_result_physical(self, result, container, rows)
        self.assertEqual(
            physical["packed_by_row"],
            {index: row["qty"] for index, row in enumerate(rows)},
        )
        # Bound the redundant work without depending on runner speed. The
        # unoptimized engine passed this count in its first transition alone.
        self.assertLess(collision_checks, 6_000_000)


class EasyCargoPublicPresetTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="kollipack-easycargo-test-")

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_preset_inputs_and_reference_totals(self):
        preset = get_transport_container_case_preset(
            "easycargo-40hc-mixed-cargo-benchmark"
        )
        rows = preset["rows"]
        self.assertEqual(len(rows), 7)
        self.assertEqual(sum(row["qty"] for row in rows), 878)
        self.assertAlmostEqual(
            sum(row["qty"] * row["weight"] for row in rows), 11863.4
        )
        self.assertAlmostEqual(
            sum(
                row["qty"] * row["length"] * row["width"] * row["height"]
                for row in rows
            ) / 1e9,
            60.20,
            delta=0.01,
        )
        self.assertEqual([row["sequence"] for row in rows], [1, 1, 2, 2, 3, 3, 3])
        self.assertEqual(
            [(row["r1"], row["r2"], row["r3"], row["stackable"]) for row in rows],
            [
                (True, True, True, True),
                (False, False, True, True),
                (True, True, True, True),
                (False, False, True, True),
                (True, True, True, False),
                (True, True, True, True),
                (True, True, True, True),
            ],
        )
        self.assertEqual(preset["config"]["packing_mode"], "front_to_back_infill")
        self.assertEqual(
            [
                preset["config"][key]
                for key in ("container_l", "container_w", "container_h")
            ],
            [12117, 2388, 2694],
        )
        self.assertEqual(preset["config"]["max_weight"], "")
        self.assertEqual(preset["config"]["tare_weight"], "")
        self.assertEqual(
            [
                preset["config"][key]
                for key in (
                    "load_unit_dimension_unit", "load_unit_mass_unit",
                    "transport_dimension_unit", "transport_mass_unit",
                )
            ],
            ["mm", "kg", "mm", "kg"],
        )
        json.dumps(preset)

    def test_public_calculator_runs_preset_and_accepts_edits(self):
        url = reverse("transport_container_calculator")
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(
                f"{url}?case=easycargo-40hc-mixed-cargo-benchmark"
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_case_example"])
        self.assertEqual(
            response.context["form"]["packing_mode"].value(),
            "front_to_back_infill",
        )
        self.assertEqual(response.context["form"]["container_l"].value(), 12117)
        self.assertEqual(response.context["form"]["container_w"].value(), 2388)
        self.assertEqual(response.context["form"]["container_h"].value(), 2694)
        rows = response.context["product_rows"]
        preset_rows = get_transport_container_case_preset(
            "easycargo-40hc-mixed-cargo-benchmark"
        )["rows"]
        for row, expected in zip(rows, preset_rows):
            for key in (
                "name", "length", "width", "height", "qty", "weight",
                "sequence", "r1", "r2", "r3", "stackable",
            ):
                if key in {"length", "width", "height", "weight"}:
                    self.assertEqual(row[key], f"{expected[key]:.2f}", (expected["name"], key))
                    self.assertEqual(row[f"canonical_{key}"], expected[key], (expected["name"], key))
                else:
                    self.assertEqual(row[key], expected[key], (expected["name"], key))
        self.assertEqual(len(rows), 7)
        result = response.context["result"]
        self.assertIsNotNone(result)
        self.assertEqual(result["packing_mode"], "front_to_back_infill")
        self.assertEqual(
            [row["sequence"] for row in result["summary"]["product_rows"]],
            [1, 1, 2, 2, 3, 3, 3],
        )
        self.assertEqual(
            result["summary"]["placed_units"]
            + result["summary"]["unplaced_units"],
            878,
        )
        self.assertEqual(
            len(response.context["threejs_scene"]["items"]),
            result["summary"]["placed_units"],
        )
        self.assertContains(
            response,
            "7 load-unit rows, and Progressive Fill – Mixed Cargo Infill",
        )
        json.dumps(result)

        with self.settings(MEDIA_ROOT=self.media_root):
            edited = self.client.post(url, {
                "action": "run_analysis",
                "container_source": "manual",
                "packing_mode": "front_to_back_infill",
                "container_l": "12117",
                "container_w": "2388",
                "container_h": "2694",
                "load_unit_dimension_unit": "mm",
                "load_unit_mass_unit": "kg",
                "transport_dimension_unit": "mm",
                "transport_mass_unit": "kg",
                "item_name[]": ["Microwave WH352"],
                "item_length[]": ["414"],
                "item_width[]": ["503"],
                "item_height[]": ["400"],
                "item_qty[]": ["2"],
                "item_max_qty[]": ["0"],
                "item_stackable[]": ["1"],
                "item_weight[]": ["9.3"],
                "item_sequence[]": ["1"],
                "item_r1[]": ["1"],
                "item_r2[]": ["1"],
                "item_r3[]": ["1"],
            })
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.context["result"]["summary"]["placed_units"], 2)
        self.assertEqual(edited.context["product_rows"][0]["qty"], 2)
