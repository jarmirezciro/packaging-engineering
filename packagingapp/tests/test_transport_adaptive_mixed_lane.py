from collections import Counter
import json

from django.test import SimpleTestCase

from packagingapp.tools.transport.modes import (
    FRONT_TO_BACK_INFILL_MODE,
    FRONT_TO_BACK_MODE,
    SPACE_EVENLY_INFILL_MODE,
    SPACE_EVENLY_MODE,
)
from packagingapp.utils.container_tool.engine import (
    TOLERANCE,
    build_product_block_candidates,
    choose_product_block,
    normalize_products,
    pack_container,
)
from packagingapp.tests.transport_physical_validator import (
    assert_transport_result_physical,
)


ACTIVE_MODES = (
    FRONT_TO_BACK_MODE,
    FRONT_TO_BACK_INFILL_MODE,
    SPACE_EVENLY_MODE,
    SPACE_EVENLY_INFILL_MODE,
)


def container(mode=FRONT_TO_BACK_MODE, *, length=12032, width=2352, height=2698):
    return {
        "L": float(length),
        "W": float(width),
        "H": float(height),
        "max_weight": None,
        "packing_mode": mode,
    }


def product(length, width, qty, *, height=144, stackable=False):
    return {
        "name": "Test load",
        "length": float(length),
        "width": float(width),
        "height": float(height),
        "qty": int(qty),
        "weight": 1.0,
        "stackable": bool(stackable),
        "sequence": 1,
        "r1": True,
        "r2": False,
        "r3": False,
    }


def geometry_signature(result):
    return tuple(
        (
            placement.row_index,
            placement.item_index,
            round(placement.x, 9),
            round(placement.y, 9),
            round(placement.z, 9),
            round(placement.l, 9),
            round(placement.w, 9),
            round(placement.h, 9),
        )
        for placement in result["placements"]
    )


class AdaptiveMixedLaneRegressionTests(SimpleTestCase):
    def assert_basic_geometry(self, result, selected_container, source):
        return assert_transport_result_physical(
            self,
            result,
            selected_container,
            [source],
        )

    def selected_candidate(self, source):
        selected_container = container()
        normalized = normalize_products([source])[0]
        candidates, _ = build_product_block_candidates(
            normalized,
            selected_container,
            selected_container["L"],
        )
        return choose_product_block(
            candidates,
            normalized.qty,
            selected_container["L"],
        )

    def test_three_euro_pallets_use_compact_partial_mixed_lanes(self):
        source = product(1200, 800, 3)
        selected = self.selected_candidate(source)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.pattern, "adaptive_mixed_lane")
        self.assertEqual(selected.module_capacity, 3)
        self.assertLessEqual(selected.depth, 1600 + TOLERANCE)
        self.assertEqual(set(selected.orientation_indices), {0, 1})

        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                selected_container = container(mode)
                result = pack_container(selected_container, [source])
                self.assert_basic_geometry(result, selected_container, source)
                self.assertEqual(len(result["placements"]), 3)
                self.assertLessEqual(
                    max(item.x + item.l for item in result["placements"]),
                    1600 + TOLERANCE,
                )

    def test_perturbed_pallet_builds_unequal_lane_tails_and_loads_25(self):
        source = product(1200, 801, 30)
        selected = self.selected_candidate(source)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.pattern, "adaptive_mixed_lane")
        self.assertGreaterEqual(selected.module_capacity, 25)
        self.assertLessEqual(selected.depth, 12015 + TOLERANCE)
        self.assertEqual(set(selected.orientation_indices), {0, 1})

        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                selected_container = container(mode)
                result = pack_container(selected_container, [source])
                self.assert_basic_geometry(result, selected_container, source)
                self.assertGreaterEqual(len(result["placements"]), 25)
                self.assertLessEqual(
                    max(item.x + item.l for item in result["placements"]),
                    12015 + TOLERANCE,
                )

    def test_exact_synchronized_euro_pattern_remains_the_true_tie_winner(self):
        source = product(1200, 800, 25)
        selected = self.selected_candidate(source)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.pattern, "synchronized_mixed_orientation")
        self.assertEqual(selected.module_capacity, 5)
        self.assertEqual(selected.depth, 2400.0)
        self.assertEqual(selected.lane_counts, (1, 1))
        self.assertEqual(selected.x_repetitions, (2, 3))

        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                selected_container = container(mode)
                first = pack_container(selected_container, [source])
                second = pack_container(selected_container, [source])
                self.assert_basic_geometry(first, selected_container, source)
                self.assertEqual(len(first["placements"]), 25)
                self.assertEqual(geometry_signature(first), geometry_signature(second))
                self.assertEqual(
                    max(item.x + item.l for item in first["placements"]),
                    12000.0,
                )
                prefix = (
                    "front_to_back"
                    if mode.startswith("front_to_back")
                    else "space_evenly"
                )
                blocks = first[f"{prefix}_main_blocks"]
                self.assertTrue(blocks)
                self.assertTrue(
                    all(
                        block["pattern"] == "synchronized_mixed_orientation"
                        for block in blocks
                    )
                )
                json.dumps(blocks)

    def test_euro_quantity_matrix_has_no_five_unit_assumption(self):
        quantities = (1, 2, 3, 4, 5, 6, 7, 17, 24, 25, 26, 30)
        for mode in ACTIVE_MODES:
            previous_count = 0
            for quantity in quantities:
                with self.subTest(mode=mode, quantity=quantity):
                    source = product(1200, 800, quantity)
                    selected_container = container(mode)
                    first = pack_container(selected_container, [source])
                    second = pack_container(selected_container, [source])
                    self.assert_basic_geometry(first, selected_container, source)
                    packed = len(first["placements"])
                    self.assertEqual(packed, min(quantity, 25))
                    self.assertGreaterEqual(packed, previous_count)
                    previous_count = packed
                    self.assertEqual(
                        geometry_signature(first),
                        geometry_signature(second),
                    )

    def test_stackable_partial_candidate_has_supported_vertical_layers(self):
        source = product(1200, 800, 3, stackable=True)
        normalized = normalize_products([source])[0]
        candidates, _ = build_product_block_candidates(
            normalized,
            container(),
            12032,
            3,
        )
        adaptive = [
            candidate
            for candidate in candidates
            if candidate.pattern == "adaptive_mixed_lane"
        ]
        self.assertTrue(adaptive)
        compact = min(adaptive, key=lambda candidate: candidate.depth)
        self.assertEqual(compact.module_capacity, 3)
        self.assertEqual(compact.depth, 1200.0)
        self.assertGreater(compact.nz, 1)
        self.assertEqual(sum(map(sum, compact.lane_stack_heights)), 3)

        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                selected_container = container(mode)
                result = pack_container(selected_container, [source])
                self.assert_basic_geometry(result, selected_container, source)
                self.assertEqual(len(result["placements"]), 3)
                elevated = [item for item in result["placements"] if item.z > 0]
                self.assertTrue(elevated)

    def test_boundaries_payload_fractional_dimensions_and_rotation_groups(self):
        cases = (
            (
                container(length=1600, width=2000),
                product(1200, 800, 3),
                3,
            ),
            (
                container(length=1599.999, width=2000),
                product(1200, 800, 3),
                2,
            ),
            (
                container(length=12032, width=1999),
                product(1200, 800, 3),
                3,
            ),
            (
                container(length=1600.25, width=2000.375),
                product(1200.25, 800.125, 3),
                3,
            ),
        )
        for selected_container, source, expected in cases:
            with self.subTest(container=selected_container, source=source):
                result = pack_container(selected_container, [source])
                self.assert_basic_geometry(result, selected_container, source)
                self.assertEqual(len(result["placements"]), expected)

        payload_container = {
            **container(length=1600, width=2000),
            "max_weight": 2.5,
        }
        payload_source = product(1200, 800, 3)
        payload_result = pack_container(payload_container, [payload_source])
        self.assert_basic_geometry(
            payload_result,
            payload_container,
            payload_source,
        )
        self.assertEqual(len(payload_result["placements"]), 2)

        for rotation_group, dimensions in (
            ("r2", (1200, 144, 800)),
            ("r3", (144, 1200, 800)),
        ):
            with self.subTest(rotation_group=rotation_group):
                source = product(*dimensions[:2], 3, height=dimensions[2])
                source.update({"r1": False, "r2": False, "r3": False})
                source[rotation_group] = True
                selected_container = container(length=1600, width=2000)
                result = pack_container(selected_container, [source])
                self.assert_basic_geometry(result, selected_container, source)
                self.assertEqual(len(result["placements"]), 3)

    def test_compatible_height_pairs_only_and_disabled_groups_never_appear(self):
        source = product(1200, 800, 6)
        source.update({"r1": True, "r2": True, "r3": True})
        normalized = normalize_products([source])[0]
        candidates, _ = build_product_block_candidates(
            normalized,
            container(),
            12032,
            6,
        )
        adaptive = [
            candidate
            for candidate in candidates
            if candidate.pattern == "adaptive_mixed_lane"
        ]
        self.assertTrue(adaptive)
        self.assertTrue(
            all(
                len({round(item[2], 9) for item in candidate.orientations}) == 1
                for candidate in adaptive
            )
        )

        r1_only = product(1200, 800, 6)
        result = pack_container(container(), [r1_only])
        r1_orientations = {
            (1200.0, 800.0, 144.0),
            (800.0, 1200.0, 144.0),
        }
        self.assertTrue(
            all(
                (item.l, item.w, item.h) in r1_orientations
                for item in result["placements"]
            )
        )

    def test_other_rectangles_and_multiple_skus_remain_physical(self):
        for length, width, quantity in (
            (1200, 790, 30),
            (1200, 825, 30),
            (1000, 700, 50),
            (997.25, 611.125, 37),
        ):
            with self.subTest(length=length, width=width):
                source = product(length, width, quantity)
                selected_container = container()
                result = pack_container(selected_container, [source])
                self.assert_basic_geometry(result, selected_container, source)
                single_orientation_witness = min(
                    quantity,
                    max(
                        int(selected_container["W"] // width)
                        * int(selected_container["L"] // length),
                        int(selected_container["W"] // length)
                        * int(selected_container["L"] // width),
                    ),
                )
                self.assertGreaterEqual(
                    len(result["placements"]),
                    single_orientation_witness,
                )

        products = [
            product(1200, 801, 30),
            {
                **product(500, 400, 12, height=300),
                "name": "Second SKU",
                "sequence": 2,
            },
        ]
        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                selected_container = container(mode)
                result = pack_container(selected_container, products)
                assert_transport_result_physical(
                    self,
                    result,
                    selected_container,
                    products,
                )
                packed = Counter(item.row_index for item in result["placements"])
                self.assertGreaterEqual(packed[0], 25)
                self.assertEqual(
                    packed[0]
                    + Counter(item["row_index"] for item in result["unplaced"])[0],
                    30,
                )

    def test_high_quantity_candidate_work_is_geometry_bounded(self):
        source = product(50, 40, 5000, height=30)
        normalized = normalize_products([source])[0]
        first, first_evaluated = build_product_block_candidates(
            normalized,
            container(),
            12032,
            5000,
        )
        second, second_evaluated = build_product_block_candidates(
            normalized,
            container(),
            12032,
            5000,
        )
        self.assertEqual(first, second)
        self.assertEqual(first_evaluated, second_evaluated)
        self.assertLess(first_evaluated, 10_000)
        self.assertTrue(
            all(
                sum(len(heights) for heights in candidate.lane_stack_heights)
                <= 4096
                for candidate in first
                if candidate.pattern == "adaptive_mixed_lane"
            )
        )
