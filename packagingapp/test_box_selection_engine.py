import itertools
import os
import tempfile
from collections import Counter

from django.test import SimpleTestCase

from .utils.box_selection.engine import (
    calculate_placements,
    compute_max_quantity_only,
    run_mode1_and_render,
)


class BoxSelectionPilotParityTests(SimpleTestCase):
    product = (500.0, 200.0, 300.0)
    container = (800.0, 800.0, 900.0)
    tolerance = 1e-9

    def assert_valid_geometry(self, placements, product, container):
        allowed_orientations = set(itertools.permutations(product))
        origins = set()

        for placement in placements:
            self.assertIn(placement.dimensions, allowed_orientations)
            self.assertIn(placement.level, (0, 1))
            self.assertIn(placement.region_type, ("main", "residual"))
            self.assertTrue(all(value > 0 for value in placement.dimensions))
            self.assertNotIn(placement.origin, origins)
            origins.add(placement.origin)

            for axis in range(3):
                self.assertGreaterEqual(placement.origin[axis], -self.tolerance)
                self.assertLessEqual(
                    placement.origin[axis] + placement.dimensions[axis],
                    container[axis] + self.tolerance,
                )

        for first, second in itertools.combinations(placements, 2):
            positive_intersection = all(
                min(
                    first.origin[axis] + first.dimensions[axis],
                    second.origin[axis] + second.dimensions[axis],
                )
                - max(first.origin[axis], second.origin[axis])
                > self.tolerance
                for axis in range(3)
            )
            self.assertFalse(positive_intersection, (first, second))

    def test_regression_uses_root_main_grid_and_complete_child_solution(self):
        placements = calculate_placements(self.product, self.container, 1, 1, 1)

        self.assertEqual(compute_max_quantity_only(self.product, self.container, 1, 1, 1), 18)
        self.assertEqual(len(placements), 18)
        self.assertEqual(
            Counter((placement.level, placement.region_type) for placement in placements),
            Counter({(0, "main"): 12, (1, "main"): 4, (1, "residual"): 2}),
        )
        self.assert_valid_geometry(placements, self.product, self.container)

    def test_renderers_use_the_authoritative_placements_and_draw_limit_only_limits_display(self):
        with tempfile.TemporaryDirectory(prefix="kollipack-box-engine-test-") as media_root:
            full = run_mode1_and_render(
                self.product,
                self.container,
                1,
                1,
                1,
                media_root,
                render_style="clean",
            )
            limited = run_mode1_and_render(
                self.product,
                self.container,
                1,
                1,
                1,
                media_root,
                draw_limit=5,
                render_style="clean",
            )

            self.assertEqual(full.max_quantity, 18)
            self.assertEqual(len(full.placements), 18)
            self.assertEqual(len(full.threejs_scene["products"]), 18)
            self.assertTrue(os.path.exists(os.path.join(media_root, full.image_rel_path)))

            scene_geometry = [
                (
                    item["x"],
                    item["y"],
                    item["z"],
                    item["dx"],
                    item["dy"],
                    item["dz"],
                    item["level"],
                    item["region_type"],
                )
                for item in full.threejs_scene["products"]
            ]
            placement_geometry = [
                (*placement.origin, *placement.dimensions, placement.level, placement.region_type)
                for placement in full.placements
            ]
            self.assertEqual(scene_geometry, placement_geometry)

            self.assertEqual(limited.max_quantity, 18)
            self.assertEqual(len(limited.placements), 18)
            self.assertEqual(len(limited.threejs_scene["products"]), 5)

    def test_no_fit_exact_fit_and_zero_volume_residuals(self):
        self.assertEqual(
            calculate_placements(self.product, (100.0, 100.0, 100.0), 1, 1, 1),
            [],
        )
        self.assertEqual(
            compute_max_quantity_only(self.product, (100.0, 100.0, 100.0), 1, 1, 1),
            0,
        )

        exact = calculate_placements(self.product, self.product, 1, 1, 1)
        self.assertEqual(len(exact), 1)
        self.assertEqual(exact[0].level, 0)
        self.assertEqual(exact[0].region_type, "main")
        self.assert_valid_geometry(exact, self.product, self.product)

        self.assertEqual(
            calculate_placements((0.0, 200.0, 300.0), self.container, 1, 1, 1),
            [],
        )

    def test_single_rotation_flag_applies_to_every_level(self):
        product = (2.0, 3.0, 5.0)
        container = (12.0, 12.0, 12.0)
        allowed_by_flags = {
            (1, 0, 0): {(3.0, 5.0, 2.0), (5.0, 3.0, 2.0)},
            (0, 1, 0): {(2.0, 5.0, 3.0), (5.0, 2.0, 3.0)},
            (0, 0, 1): {(2.0, 3.0, 5.0), (3.0, 2.0, 5.0)},
        }

        for flags, allowed_orientations in allowed_by_flags.items():
            with self.subTest(flags=flags):
                placements = calculate_placements(product, container, *flags)
                self.assertTrue(placements)
                self.assertTrue(
                    all(placement.dimensions in allowed_orientations for placement in placements)
                )
                self.assert_valid_geometry(placements, product, container)

