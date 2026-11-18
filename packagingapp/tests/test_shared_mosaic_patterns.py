import itertools
import os
import tempfile
from dataclasses import replace
from unittest.mock import patch

from django.test import SimpleTestCase

from packagingapp.tests.benchmark_shared_mosaic_patterns import BENCHMARK_CASES
from packagingapp.tools.palletization.case_presets import PALLETIZATION_CASE_PRESETS
from packagingapp.tools.palletization.service import analyze_palletization_capacity
from packagingapp.tools.palletization.state import default_palletization_config
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
from packagingapp.utils.packing_patterns import core as shared_core
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
                "perimeter_core_mosaic",
                "regional_mosaic",
                "nested_simple_lattice_1d",
                "nested_simple_lattice_2d",
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
            (pallet_engine.pattern_center_filled_pinwheel, shared_patterns.pattern_center_filled_pinwheel, {}),
            (pallet_engine.pattern_perimeter_core_mosaic, shared_patterns.pattern_perimeter_core_mosaic, {}),
        )
        for fixture in fixtures:
            for original, shared, kwargs in functions:
                with self.subTest(fixture=fixture, function=original.__name__, kwargs=kwargs):
                    shared_kwargs = dict(kwargs)
                    if original is pallet_engine.pattern_hybrid_pinwheel:
                        # Hybrid eligibility is deliberately consumer-specific;
                        # compare constructors under the same policy. Container
                        # defaults have their independent frozen Stage 1 test.
                        shared_kwargs["policy"] = shared_patterns.PALLETIZATION_SEARCH_POLICY
                    self.assertEqual(
                        _signature(original(*fixture, **kwargs)),
                        _signature(shared(*fixture, **shared_kwargs)),
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


class PalletSharedPatternDelegationTests(SimpleTestCase):
    def test_every_pallet_pattern_wrapper_delegates_to_the_shared_api(self):
        functions = (
            ("pattern_block", {}),
            ("pattern_row", {}),
            ("pattern_splitrow", {}),
            ("pattern_brick_best", {}),
            ("pattern_pinwheel", {}),
            ("pattern_hybrid_pinwheel", {}),
            ("pattern_nested_pinwheel", {}),
            ("pattern_center_filled_pinwheel", {}),
            ("pattern_perimeter_core_mosaic", {}),
        )
        fixture = (1200.0, 1200.0, 400.0, 200.0)

        for function_name, kwargs in functions:
            shared_function = getattr(shared_patterns, function_name)
            pallet_function = getattr(pallet_engine, function_name)
            with self.subTest(function=function_name), patch.object(
                shared_patterns,
                function_name,
                wraps=shared_function,
            ) as delegated:
                layer = pallet_function(*fixture, **kwargs)

                delegated.assert_called_once()
                self.assertIs(
                    delegated.call_args.kwargs["policy"],
                    shared_patterns.PALLETIZATION_SEARCH_POLICY,
                )
                self.assertTrue(layer)
                self.assertTrue(
                    all(type(item) is pallet_engine.Placement2D for item in layer)
                )

    def test_pallet_policy_does_not_leak_into_container_defaults(self):
        fixture = (1200.0, 800.0, 70.0, 40.0)
        container_before = shared_patterns.pattern_pinwheel(*fixture)
        pallet_layer = pallet_engine.pattern_pinwheel(*fixture)
        container_after = shared_patterns.pattern_pinwheel(*fixture)

        self.assertEqual(_signature(container_before), _signature(container_after))
        self.assertEqual(len(container_before), 280)
        self.assertEqual(len(pallet_layer), 320)


class NestedPinwheelEligibilityTests(SimpleTestCase):
    def assert_single_center_void(self, layer, contour_l, contour_w, long_side, short_side):
        self.assertTrue(validate_placements(layer, contour_l, contour_w).valid)
        void_side = long_side - short_side
        self.assertAlmostEqual(
            contour_l * contour_w - sum(item.l * item.w for item in layer),
            void_side ** 2,
            delta=1e-6,
        )
        left, right = (contour_l - void_side) / 2, (contour_l + void_side) / 2
        bottom, top = (contour_w - void_side) / 2, (contour_w + void_side) / 2
        for item in layer:
            self.assertTrue(
                item.x + item.l <= left + 1e-9 or item.x >= right - 1e-9
                or item.y + item.w <= bottom + 1e-9 or item.y >= top - 1e-9
            )

    def test_positive_cases_keep_ordered_geometry_and_one_center_void(self):
        historical_policy = replace(
            shared_patterns.PALLETIZATION_SEARCH_POLICY, require_compact_nested_pinwheel=False
        )
        for case, count, contour_mm in ((4, 12, (1016, 1016)), (8, 64, (1200, 700))):
            with self.subTest(case=case):
                preset = PALLETIZATION_CASE_PRESETS[f"calibration-case-{case}"]
                config = {**default_palletization_config(), **preset["config"]}
                result = analyze_palletization_capacity(config)
                effective = result["effective_config"]
                args = tuple(effective[name] for name in ("pallet_l", "pallet_w", "box_l", "box_w"))
                layer = pallet_engine.pattern_nested_pinwheel(*args)
                historical_layer = shared_patterns.pattern_nested_pinwheel(*args, policy=historical_policy)
                self.assertEqual(len(layer), count)
                self.assertEqual(
                    [(item.x, item.y, item.l, item.w, item.orientation) for item in layer],
                    [(item.x, item.y, item.l, item.w, item.orientation) for item in historical_layer],
                )
                self.assert_single_center_void(layer, *contour_mm, *args[2:])

    def test_generated_contact_fits_at_the_carton_width_boundary(self):
        # Exact openings for (n, q) = (3, 2), (2, 2), and (2, 4), respectively.
        for ratio, contour, count in ((1.5, 6.5, 28), (3, 8, 20), (5, 14, 36)):
            for short in (11.0, 25.4):
                box = (ratio * short, short)
                for slack, expected_count in (((1, 1), count), ((1.01, 1.01), 0), ((1.01, 0), count)):
                    with self.subTest(ratio=ratio, short=short, slack=slack):
                        area = tuple((contour + margin) * short for margin in slack)
                        layer = pallet_engine.pattern_nested_pinwheel(*area, *box)
                        self.assertEqual(len(layer), expected_count)
                        if layer:
                            self.assert_single_center_void(layer, contour * short, contour * short, *box)

    def test_lower_count_valid_rotation_replaces_ineligible_candidates(self):
        args = (800.0, 800.0, 200.0, 100.0)
        self.assertEqual(pallet_engine.pattern_nested_pinwheel(*args), [])
        layer = pallet_engine.pattern_nested_pinwheel(*args, rotated=True)
        self.assertEqual(len(layer), 24)
        self.assert_single_center_void(layer, 700.0, 700.0, *args[2:])

        base, interlock = pallet_engine.get_base_and_interlock_layers("Nested pinwheel", *args)
        self.assertEqual(base, pallet_engine.center_placements_on_area(layer, *args[:2]))
        self.assertEqual(interlock, [])

    def test_pallet_eligibility_preserves_container_nested_geometry(self):
        args = (2000.0, 2000.0, 292.0, 316.0)
        container = shared_patterns.pattern_nested_pinwheel(*args)
        self.assertEqual(len(container), 24)
        for rotated in (False, True):
            self.assertEqual(pallet_engine.pattern_nested_pinwheel(*args, rotated=rotated), [])
        self.assertEqual(container, shared_patterns.pattern_nested_pinwheel(*args))


class HybridPinwheelEligibilityTests(SimpleTestCase):
    def test_positive_calibrations_preserve_ordered_core_and_rectangular_band(self):
        historical_policy = replace(
            shared_patterns.PALLETIZATION_SEARCH_POLICY, require_coherent_hybrid_pinwheel=False,
        )
        for args, count, core_count, band_y in (
            ((48 * 25.4, 40 * 25.4, 16 * 25.4, 8 * 25.4), 15, 12, 812.8),
            ((2000.0, 2000.0, 300.0, 400.0), 33, 28, 1700.0),
        ):
            for rotated in (False, True):
                with self.subTest(args=args, rotated=rotated):
                    layer = pallet_engine.pattern_hybrid_pinwheel(*args, rotated=rotated)
                    historical = shared_patterns.pattern_hybrid_pinwheel(
                        *args, rotated=rotated, policy=historical_policy,
                    )
                    self.assertEqual(
                        [(p.x, p.y, p.l, p.w, p.orientation) for p in layer],
                        [(p.x, p.y, p.l, p.w, p.orientation) for p in historical],
                    )
                    self.assertTrue(validate_placements(layer, *args[:2]).valid)
                    if rotated:
                        continue
                    self.assertEqual(len(layer), count)
                    fillers = layer[core_count:]
                    self.assertTrue(all(abs(p.y - band_y) < 1e-9 for p in fillers))
                    self.assertAlmostEqual(fillers[0].x, 0)
                    for left, right in zip(fillers, fillers[1:]):
                        self.assertAlmostEqual(left.x + left.l, right.x)
                    self.assertAlmostEqual(fillers[-1].x + fillers[-1].l, args[0])

    def test_case_five_is_rejected_by_coherence_before_secondary_relevance(self):
        args = (1200.0, 800.0, 292.0, 312.0)
        historical_policy = replace(
            shared_core.PALLETIZATION_SEARCH_POLICY, require_coherent_hybrid_pinwheel=False,
        )
        historical = shared_core.pattern_hybrid_pinwheel(*args, policy=historical_policy)
        self.assertEqual(len(historical), 7)
        self.assertGreater(len(historical) * args[2] * args[3] / (args[0] * args[1]), 0.60)
        self.assertEqual(
            [(p.x, p.y, p.l, p.w) for p in historical[4:]],
            [(610.0, 88.0, 292.0, 312.0), (902.0, 88.0, 292.0, 312.0),
             (756.0, 400.0, 292.0, 312.0)],
        )
        # Removing only the relevance filter still cannot admit the detached
        # seven-carton arrangement. Only the four-carton primary core or the
        # six-carton alternate core remains, both below the relevance floor.
        with patch.object(shared_core, "_hybrid_floor_is_relevant", return_value=True):
            self.assertEqual(len(pallet_engine.pattern_hybrid_pinwheel(*args)), 4)
            self.assertEqual(len(pallet_engine.pattern_hybrid_pinwheel(*args, rotated=True)), 6)
        for rotated in (False, True):
            self.assertEqual(pallet_engine.pattern_hybrid_pinwheel(*args, rotated=rotated), [])

    def test_fragmented_margins_are_rejected_before_filler_construction(self):
        cases = (
            # Detached, staggered right-margin brick (Case 5).
            ((1200, 800, 292, 312), (292, 312)),
            # A sparse top grid would split its two cartons to opposite ends.
            ((500, 800, 300, 200), (300, 200)),
        )
        for args, box in cases:
            base, _, _ = shared_core.pinwheel_motif(0, 0, *box, *box)
            with self.subTest(args=args), patch.object(shared_core, "pattern_brick") as brick, patch.object(
                shared_core, "try_two_orientations_grid",
            ) as grid:
                layer = shared_core.call_with_policy(
                    shared_core._add_rectangular_margin_fill, base, *args, *box,
                    policy=shared_core.PALLETIZATION_SEARCH_POLICY,
                )
                self.assertEqual(layer, [])
                brick.assert_not_called()
                grid.assert_not_called()

    def test_margin_arithmetic_preserves_attached_rectangles_and_rejects_split_rows(self):
        for balance, span, expected in (
            (True, 1200.0, 3), (True, 1210.0, None), (False, 1210.0, 3),
            (True, 500.0, 1),
        ):
            self.assertEqual(
                shared_core.call_with_policy(
                    shared_core._coherent_hybrid_margin_count,
                    span, 1000.0, span, 800.0, 400.0, 200.0, balance,
                    policy=shared_core.PALLETIZATION_SEARCH_POLICY,
                ), expected,
            )

    def test_relevance_boundary_and_unit_scaling(self):
        for scale in (1.0, 25.4, 1 / 25.4):
            self.assertTrue(shared_core._hybrid_floor_is_relevant(
                6, 10 * scale, 10 * scale, 5 * scale, 2 * scale,
            ))
            self.assertFalse(shared_core._hybrid_floor_is_relevant(
                6, 10.001 * scale, 10 * scale, 5 * scale, 2 * scale,
            ))
            self.assertEqual(pallet_engine.pattern_hybrid_pinwheel(
                *(value * scale for value in (1200, 800, 292, 312)),
            ), [])

    def test_pallet_policy_preserves_container_hybrid_and_search_limits(self):
        args = (1200.0, 800.0, 292.0, 312.0)
        container_before = shared_patterns.pattern_hybrid_pinwheel(*args)
        self.assertEqual(len(container_before), 7)
        self.assertEqual(pallet_engine.pattern_hybrid_pinwheel(*args), [])
        self.assertEqual(shared_patterns.pattern_hybrid_pinwheel(*args), container_before)
        self.assertEqual(
            (shared_core.PALLETIZATION_SEARCH_POLICY.max_pinwheel_parameter,
             shared_core.PALLETIZATION_SEARCH_POLICY.max_pinwheel_candidates), (30, 80),
        )
        self.assertEqual(
            (shared_core.CONTAINER_SEARCH_POLICY.max_pinwheel_parameter,
             shared_core.CONTAINER_SEARCH_POLICY.max_pinwheel_candidates), (12, 8),
        )


class PerimeterCoreMosaicTests(SimpleTestCase):
    def test_cape_pack_topology_is_exactly_ten_mixed_orientation_cartons(self):
        length, width = 18.32, 8.64
        layer = shared_patterns.pattern_perimeter_core_mosaic(48.0, 40.0, length, width)

        self.assertEqual(len(layer), 10)
        self.assertEqual(sum(placement.l == length and placement.w == width for placement in layer), 6)
        self.assertEqual(sum(placement.l == width and placement.w == length for placement in layer), 4)
        self.assertTrue(
            validate_placements(
                layer,
                48.0,
                40.0,
                expected_footprint=(length, width),
            ).valid
        )
        self.assertAlmostEqual(
            max(item.x + item.l for item in layer) - min(item.x for item in layer),
            2 * length + width,
        )
        self.assertAlmostEqual(
            max(item.y + item.w for item in layer) - min(item.y for item in layer),
            2 * length,
        )
        self.assertAlmostEqual(10 * length * width / (48.0 * 40.0) * 100, 82.44)

    def test_ratio_boundary_rotation_units_and_reversal_are_supported(self):
        for ratio in (2.0, 2.125, 2.2, 2.25, 10.0):
            with self.subTest(ratio=ratio):
                short = 8.0
                long = ratio * short
                footprint = (2 * long + short, 2 * long)
                layer = shared_patterns.pattern_perimeter_core_mosaic(
                    footprint[0] + 3.0,
                    footprint[1] + 5.0,
                    long,
                    short,
                )
                self.assertEqual(len(layer), 10)
                self.assertTrue(validate_placements(layer, footprint[0] + 3.0, footprint[1] + 5.0).valid)

        metric = shared_patterns.pattern_perimeter_core_mosaic(
            48.0 * 25.4,
            40.0 * 25.4,
            18.32 * 25.4,
            8.64 * 25.4,
        )
        imperial = shared_patterns.pattern_perimeter_core_mosaic(48.0, 40.0, 18.32, 8.64)
        self.assertEqual(len(metric), len(imperial))
        self.assertEqual(
            {
                (round(item.x / 25.4, 6), round(item.y / 25.4, 6),
                 round(item.l / 25.4, 6), round(item.w / 25.4, 6))
                for item in metric
            },
            {
                (round(item.x, 6), round(item.y, 6), round(item.l, 6), round(item.w, 6))
                for item in imperial
            },
        )
        reversed_layer = shared_patterns.pattern_perimeter_core_mosaic(48.0, 40.0, 8.64, 18.32)
        self.assertEqual(
            {
                (round(item.x, 6), round(item.y, 6), round(item.l, 6), round(item.w, 6))
                for item in reversed_layer
            },
            {
                (round(item.x, 6), round(item.y, 6), round(item.l, 6), round(item.w, 6))
                for item in imperial
            },
        )

        rotated_area = shared_patterns.pattern_perimeter_core_mosaic(
            2 * 18.32,
            2 * 18.32 + 8.64,
            18.32,
            8.64,
        )
        self.assertEqual(len(rotated_area), 10)
        self.assertAlmostEqual(
            max(item.x + item.l for item in rotated_area) - min(item.x for item in rotated_area),
            2 * 18.32,
        )

    def test_invalid_ratio_and_insufficient_area_are_rejected(self):
        self.assertEqual(
            shared_patterns.pattern_perimeter_core_mosaic(1000.0, 1000.0, 19.9, 10.0),
            [],
        )
        self.assertEqual(
            shared_patterns.pattern_perimeter_core_mosaic(45.27, 36.63, 18.32, 8.64),
            [],
        )

    def test_container_tie_keeps_legacy_but_exposes_shared_candidate(self):
        candidates = enumerate_pattern_candidates(48.0, 40.0, 18.32, 8.64)
        perimeter = [item for item in candidates if item.family == "perimeter_core_mosaic"]
        self.assertEqual(len(perimeter), 1)
        self.assertEqual(perimeter[0].quantity, 10)

        comparison = compare_packing_candidates(
            (18.32, 8.64, 20.32),
            (48.0, 40.0, 20.32),
            0,
            0,
            1,
        )
        self.assertEqual(comparison.legacy_quantity, 10)
        self.assertEqual(comparison.selected_quantity, 10)
        self.assertEqual(comparison.winning_family, "legacy")

    def test_palletization_catalogue_retains_distinct_geometry_and_stack_counts(self):
        unit = 25.4
        rows = pallet_engine.run_palletization_analysis(
            18.32 * unit,
            8.64 * unit,
            20.32 * unit,
            48.0 * unit,
            40.0 * unit,
            50.0 * unit,
            pallet_height=5.50 * unit,
        )
        block = next(row for row in rows if row["pattern"] == "Block")
        perimeter = next(row for row in rows if row["pattern"] == "Perimeter-Core Mosaic")
        block_geometry = {
            (item.x, item.y, item.l, item.w) for item in block["layer_A_2d"]
        }
        perimeter_geometry = {
            (item.x, item.y, item.l, item.w) for item in perimeter["layer_A_2d"]
        }
        self.assertNotEqual(block_geometry, perimeter_geometry)
        self.assertEqual(
            (perimeter["boxes_layer_A"], perimeter["layers"], perimeter["total_boxes"]),
            (10, 2, 20),
        )
        self.assertAlmostEqual(perimeter["used_height_mm"] / unit + 5.50, 46.14)
        self.assertAlmostEqual(perimeter["layer_footprint_util_pct"], 82.44)
        self.assertEqual(
            {item.orientation for item in perimeter["layer_A_2d"]},
            {"LxW", "WxL"},
        )

        three_layers = pallet_engine.run_palletization_analysis(
            18.32 * unit,
            8.64 * unit,
            20.32 * unit,
            48.0 * unit,
            40.0 * unit,
            66.46 * unit,
            pallet_height=5.50 * unit,
        )
        three_layer_perimeter = next(
            row for row in three_layers if row["pattern"] == "Perimeter-Core Mosaic"
        )
        self.assertEqual((three_layer_perimeter["layers"], three_layer_perimeter["total_boxes"]), (3, 30))

        brick_rows = pallet_engine.run_palletization_analysis(
            400.0, 200.0, 200.0, 1200.0, 800.0, 1150.0, pallet_height=150.0
        )
        brick = next(row for row in brick_rows if row["pattern"] == "Brick")
        self.assertEqual(brick["boxes_layer_A"], 12)


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
