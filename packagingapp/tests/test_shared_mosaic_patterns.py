import itertools
import os
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase

from packagingapp.tests.benchmark_shared_mosaic_patterns import BENCHMARK_CASES
from packagingapp.utils.box_selection.engine import (
    calculate_legacy_placements,
    calculate_placements,
    compare_packing_candidates,
    compute_max_quantity_only,
    run_mode1_and_render,
)
from packagingapp.utils.box_selection.mosaic import (
    MOSAIC_CANDIDATE_BUDGET,
    MosaicSearchResult,
    search_mosaic_placements,
    validate_mosaic_placements,
)
from packagingapp.utils.packing_patterns import (
    PATTERN_FAMILIES,
    enumerate_pattern_candidates,
)
from packagingapp.utils.packing_patterns import patterns as shared_patterns
from packagingapp.utils.packing_patterns.validation import validate_placements
from packagingapp.utils.palletization import engine as pallet_engine


def _signature(placements):
    return tuple(
        sorted(
            (
                round(item.x, 6),
                round(item.y, 6),
                round(item.l, 6),
                round(item.w, 6),
                item.orientation,
            )
            for item in placements
        )
    )


class SharedPatternParityTests(SimpleTestCase):
    def test_requested_pattern_families_are_exposed(self):
        self.assertEqual(
            PATTERN_FAMILIES,
            (
                "block",
                "row",
                "splitrow",
                "brick",
                "pinwheel",
                "hybrid_pinwheel",
                "nested_pinwheel",
                "centre_filled_pinwheel",
                "regional_mosaic",
            ),
        )

    def test_representative_geometry_matches_unchanged_palletization_generators(self):
        fixtures = (
            (1200.0, 800.0, 230.0, 170.0),
            (1000.0, 800.0, 300.0, 200.0),
            (1200.0, 1200.0, 400.0, 200.0),
            (384.81, 368.3, 152.4, 101.6),
        )
        functions = (
            (pallet_engine.pattern_block, shared_patterns.pattern_block, {}),
            (pallet_engine.pattern_row, shared_patterns.pattern_row, {}),
            (pallet_engine.pattern_splitrow, shared_patterns.pattern_splitrow, {}),
            (pallet_engine.pattern_brick_best, shared_patterns.pattern_brick_best, {}),
            (pallet_engine.pattern_pinwheel, shared_patterns.pattern_pinwheel, {}),
            (pallet_engine.pattern_pinwheel, shared_patterns.pattern_pinwheel, {"rotated": True}),
            (pallet_engine.pattern_hybrid_pinwheel, shared_patterns.pattern_hybrid_pinwheel, {}),
            (pallet_engine.pattern_hybrid_pinwheel, shared_patterns.pattern_hybrid_pinwheel, {"rotated": True}),
            (pallet_engine.pattern_nested_pinwheel, shared_patterns.pattern_nested_pinwheel, {}),
            (pallet_engine.pattern_nested_pinwheel, shared_patterns.pattern_nested_pinwheel, {"rotated": True}),
            (pallet_engine.pattern_center_filled_pinwheel, shared_patterns.pattern_center_filled_pinwheel, {}),
        )
        for fixture in fixtures:
            for original, shared, kwargs in functions:
                with self.subTest(fixture=fixture, function=original.__name__, kwargs=kwargs):
                    self.assertEqual(
                        _signature(original(*fixture, **kwargs)),
                        _signature(shared(*fixture, **kwargs)),
                    )

    def test_enumeration_is_deterministic_valid_and_bounded(self):
        args = (1200.0, 800.0, 230.0, 170.0)
        first = enumerate_pattern_candidates(*args)
        second = enumerate_pattern_candidates(*args)
        self.assertIs(first, second)
        self.assertLessEqual(len(first), 96)
        self.assertTrue(first)
        for candidate in first:
            self.assertTrue(
                validate_placements(
                    candidate.placements,
                    args[0],
                    args[1],
                    expected_footprint=(args[2], args[3]),
                ).valid
            )


class ContainerMosaicIntegrationTests(SimpleTestCase):
    tolerance = 1e-9

    def assert_valid_selected_geometry(self, placements, product, container):
        allowed = set(itertools.permutations(product))
        seen = set()
        for placement in placements:
            self.assertIn(placement.dimensions, allowed)
            self.assertNotIn((*placement.origin, *placement.dimensions), seen)
            seen.add((*placement.origin, *placement.dimensions))
            for axis in range(3):
                self.assertGreaterEqual(placement.origin[axis], -self.tolerance)
                self.assertLessEqual(
                    placement.origin[axis] + placement.dimensions[axis],
                    container[axis] + self.tolerance,
                )
        for first, second in itertools.combinations(placements, 2):
            overlap = all(
                min(
                    first.origin[axis] + first.dimensions[axis],
                    second.origin[axis] + second.dimensions[axis],
                )
                - max(first.origin[axis], second.origin[axis])
                > self.tolerance
                for axis in range(3)
            )
            self.assertFalse(overlap)

    def test_reference_preserves_twelve_unit_legacy_and_selects_valid_sixteen(self):
        product = (152.4, 101.6, 152.4)
        container = (384.81, 368.3, 342.9)
        legacy = calculate_legacy_placements(product, container, 0, 0, 1)
        mosaic = search_mosaic_placements(product, container, 0, 0, 1, legacy_quantity=len(legacy))
        selected = calculate_placements(product, container, 0, 0, 1)
        self.assertEqual(len(legacy), 12)
        self.assertEqual(mosaic.quantity, 16)
        self.assertEqual(len(selected), 16)
        self.assertEqual(mosaic.family, "pinwheel")
        self.assertTrue(
            validate_mosaic_placements(mosaic.placements, product, container, 0, 0, 1)[0]
        )
        self.assert_valid_selected_geometry(selected, product, container)

    def test_winning_mosaic_is_the_single_render_and_scene_source(self):
        product = (152.4, 101.6, 152.4)
        container = (384.81, 368.3, 342.9)
        with tempfile.TemporaryDirectory(prefix="kollipack-mosaic-render-") as media_root:
            result = run_mode1_and_render(
                product,
                container,
                0,
                0,
                1,
                media_root,
                render_style="clean",
            )
            self.assertEqual(result.max_quantity, 16)
            self.assertEqual(len(result.placements), 16)
            self.assertEqual(len(result.threejs_scene["products"]), 16)
            self.assertEqual(result.candidate_family, "pinwheel")
            self.assertEqual(result.threejs_scene["candidateFamily"], "pinwheel")
            self.assertEqual(result.threejs_scene["legacyQuantity"], 12)
            self.assertEqual(result.threejs_scene["mosaicQuantity"], 16)
            self.assertEqual(
                {
                    (item["dx"], item["dy"], item["dz"])
                    for item in result.threejs_scene["products"]
                },
                {
                    (101.6, 152.4, 152.4),
                    (152.4, 101.6, 152.4),
                },
            )
            self.assertTrue(
                os.path.exists(os.path.join(media_root, result.image_rel_path))
            )

    def test_legacy_wins_ties_and_when_legacy_residuals_are_better(self):
        product = (500.0, 200.0, 300.0)
        container = (800.0, 800.0, 900.0)
        comparison = compare_packing_candidates(product, container, 1, 1, 1)
        self.assertEqual(comparison.legacy_quantity, 18)
        self.assertLess(comparison.mosaic_quantity, comparison.legacy_quantity)
        self.assertEqual(comparison.selected_quantity, comparison.legacy_quantity)
        self.assertEqual(comparison.winning_family, "legacy")

    def test_mosaic_failure_and_invalid_result_fail_closed_to_legacy(self):
        product = (500.0, 200.0, 300.0)
        container = (800.0, 800.0, 900.0)
        legacy = calculate_legacy_placements(product, container, 1, 1, 1)
        with patch(
            "packagingapp.utils.box_selection.engine.search_mosaic_placements",
            side_effect=RuntimeError("candidate failure"),
        ):
            self.assertEqual(
                calculate_placements(product, container, 1, 1, 1),
                legacy,
            )
        invalid = MosaicSearchResult(
            placements=tuple(),
            reported_quantity=len(legacy) + 10,
            family="invalid",
            validation_error="invalid geometry",
        )
        with patch(
            "packagingapp.utils.box_selection.engine.search_mosaic_placements",
            return_value=invalid,
        ):
            self.assertEqual(
                calculate_placements(product, container, 1, 1, 1),
                legacy,
            )

    def test_rotation_flags_control_every_mosaic_vertical_family(self):
        product = (120.0, 80.0, 40.0)
        container = (500.0, 360.0, 250.0)
        for flags, vertical in (
            ((1, 0, 0), 120.0),
            ((0, 1, 0), 80.0),
            ((0, 0, 1), 40.0),
        ):
            with self.subTest(flags=flags):
                result = search_mosaic_placements(product, container, *flags)
                self.assertTrue(result.placements)
                self.assertTrue(
                    all(placement.dimensions[2] == vertical for placement in result.placements)
                )

    def test_reference_is_consistent_for_scaled_metric_and_imperial_values(self):
        product = (152.4, 101.6, 152.4)
        container = (384.81, 368.3, 342.9)
        for divisor in (1.0, 10.0, 25.4, 304.8):
            scaled_product = tuple(value / divisor for value in product)
            scaled_container = tuple(value / divisor for value in container)
            self.assertEqual(
                compute_max_quantity_only(
                    scaled_product, scaled_container, 0, 0, 1
                ),
                16,
            )

    def test_benchmark_matrix_never_regresses_and_stays_within_budget(self):
        for name, product, container, flags in BENCHMARK_CASES:
            with self.subTest(name=name):
                comparison = compare_packing_candidates(product, container, *flags)
                self.assertGreaterEqual(
                    comparison.selected_quantity,
                    comparison.legacy_quantity,
                )
                self.assertTrue(comparison.geometry_valid)
                self.assertLessEqual(
                    comparison.mosaic_candidate_count,
                    MOSAIC_CANDIDATE_BUDGET,
                )
