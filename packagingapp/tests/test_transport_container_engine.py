from collections import Counter
from itertools import combinations
import json

from django.test import SimpleTestCase

from packagingapp.utils.container_tool.engine import (
    allowed_orientations,
    pack_container,
)


TOLERANCE = 1e-9


def transport_container(mode):
    return {
        "L": 12032.0,
        "W": 2352.0,
        "H": 2395.0,
        "max_weight": 26500.0,
        "packing_mode": mode,
    }


def product(
    name,
    length,
    width,
    height,
    qty,
    *,
    weight=0.0,
    sequence=1,
    stackable=True,
):
    return {
        "name": name,
        "length": float(length),
        "width": float(width),
        "height": float(height),
        "qty": int(qty),
        "weight": float(weight),
        "sequence": int(sequence),
        "stackable": bool(stackable),
        # R1 is the repository default and permits the two floor rotations.
        "r1": True,
        "r2": False,
        "r3": False,
    }


def eur_palletized_load(qty=20):
    return product(
        "EUR palletized load",
        1200,
        800,
        1100,
        qty,
        weight=900,
    )


def maximum_regression_products():
    return [
        eur_palletized_load(),
        product("Product 2", 500, 400, 700, 100),
    ]


def frontier_regression_products():
    return [
        eur_palletized_load(),
        product("Product 2", 500, 200, 700, 100),
    ]


class TransportEngineInvariantMixin:
    def geometry_signature(self, result):
        return tuple(
            (
                placement.row_index,
                placement.item_index,
                placement.x,
                placement.y,
                placement.z,
                placement.l,
                placement.w,
                placement.h,
            )
            for placement in result["placements"]
        )

    def _subtract_rectangle(self, rectangle, blocker):
        x0, y0, length, width = rectangle
        bx0, by0, blocker_length, blocker_width = blocker
        x1, y1 = x0 + length, y0 + width
        bx1, by1 = bx0 + blocker_length, by0 + blocker_width

        ix0, iy0 = max(x0, bx0), max(y0, by0)
        ix1, iy1 = min(x1, bx1), min(y1, by1)
        if ix1 <= ix0 + TOLERANCE or iy1 <= iy0 + TOLERANCE:
            return [rectangle]

        pieces = []
        if ix0 > x0 + TOLERANCE:
            pieces.append((x0, y0, ix0 - x0, width))
        if x1 > ix1 + TOLERANCE:
            pieces.append((ix1, y0, x1 - ix1, width))

        middle_length = ix1 - ix0
        if iy0 > y0 + TOLERANCE:
            pieces.append((ix0, y0, middle_length, iy0 - y0))
        if y1 > iy1 + TOLERANCE:
            pieces.append((ix0, iy1, middle_length, y1 - iy1))
        return pieces

    def assert_full_base_support(self, placement, placements):
        if placement.z <= TOLERANCE:
            return

        unsupported = [
            (placement.x, placement.y, placement.l, placement.w)
        ]
        for support in placements:
            if not support.stackable:
                continue
            if abs(support.z + support.h - placement.z) > TOLERANCE:
                continue

            updated = []
            blocker = (support.x, support.y, support.l, support.w)
            for rectangle in unsupported:
                updated.extend(self._subtract_rectangle(rectangle, blocker))
            unsupported = [
                rectangle
                for rectangle in updated
                if rectangle[2] > TOLERANCE
                and rectangle[3] > TOLERANCE
            ]
            if not unsupported:
                return

        self.fail(f"Placement has unsupported base area: {placement!r}")

    def assert_transport_invariants(self, result, container, products):
        placements = result["placements"]

        for placement in placements:
            self.assertGreaterEqual(placement.row_index, 0)
            self.assertLess(placement.row_index, len(products))
            self.assertGreaterEqual(placement.x, -TOLERANCE)
            self.assertGreaterEqual(placement.y, -TOLERANCE)
            self.assertGreaterEqual(placement.z, -TOLERANCE)
            self.assertLessEqual(
                placement.x + placement.l,
                container["L"] + TOLERANCE,
            )
            self.assertLessEqual(
                placement.y + placement.w,
                container["W"] + TOLERANCE,
            )
            self.assertLessEqual(
                placement.z + placement.h,
                container["H"] + TOLERANCE,
            )

            source = products[placement.row_index]
            permitted = {
                tuple(round(value, 9) for value in orientation)
                for orientation in allowed_orientations(
                    (
                        source["length"],
                        source["width"],
                        source["height"],
                    ),
                    source["r1"],
                    source["r2"],
                    source["r3"],
                )
            }
            self.assertIn(
                tuple(
                    round(value, 9)
                    for value in (placement.l, placement.w, placement.h)
                ),
                permitted,
            )
            self.assert_full_base_support(placement, placements)

        for first, second in combinations(placements, 2):
            overlap_x = min(first.x + first.l, second.x + second.l) - max(
                first.x, second.x
            )
            overlap_y = min(first.y + first.w, second.y + second.w) - max(
                first.y, second.y
            )
            overlap_z = min(first.z + first.h, second.z + second.h) - max(
                first.z, second.z
            )
            self.assertFalse(
                overlap_x > TOLERANCE
                and overlap_y > TOLERANCE
                and overlap_z > TOLERANCE,
                (first, second),
            )

            if not first.stackable:
                first_supports_second = (
                    abs(first.z + first.h - second.z) <= TOLERANCE
                    and overlap_x > TOLERANCE
                    and overlap_y > TOLERANCE
                )
                self.assertFalse(first_supports_second, (first, second))
            if not second.stackable:
                second_supports_first = (
                    abs(second.z + second.h - first.z) <= TOLERANCE
                    and overlap_x > TOLERANCE
                    and overlap_y > TOLERANCE
                )
                self.assertFalse(second_supports_first, (second, first))

        packed_by_row = Counter(
            placement.row_index for placement in placements
        )
        unplaced_by_row = Counter(
            item["row_index"] for item in result["unplaced"]
        )
        for row_index, source in enumerate(products):
            self.assertEqual(
                packed_by_row[row_index] + unplaced_by_row[row_index],
                source["qty"],
            )

        expected_weight = sum(
            placement.weight for placement in placements
        )
        self.assertAlmostEqual(result["loaded_weight"], expected_weight)
        if container.get("max_weight"):
            self.assertLessEqual(
                expected_weight,
                float(container["max_weight"]) + TOLERANCE,
            )

    def assert_intervals_are_contiguous(self, intervals):
        ordered = sorted(intervals)
        self.assertTrue(ordered)
        current_end = ordered[0][1]
        for start, end in ordered[1:]:
            self.assertLessEqual(start, current_end + TOLERANCE)
            current_end = max(current_end, end)
        return ordered[0][0], current_end


class MaximumUtilizationRegressionTests(
    TransportEngineInvariantMixin,
    SimpleTestCase,
):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.container = transport_container("maximum_utilization")
        cls.products = maximum_regression_products()
        cls.result = pack_container(cls.container, cls.products)

    def test_established_residual_continuity_case(self):
        self.assert_transport_invariants(
            self.result,
            self.container,
            self.products,
        )
        self.assertEqual(
            Counter(
                placement.row_index
                for placement in self.result["placements"]
            ),
            {0: 20, 1: 100},
        )
        self.assertEqual(self.result["packing_mode"], "maximum_utilization")
        self.assertFalse(self.result["maximum_uses_sequence_frontier"])
        self.assertEqual(self.result["sequence_zones"], [])

        # Probe the first Product 2 floor lane. A computational split aligned
        # with the earlier 1200 mm modules must not create periodic voids in
        # this physically continuous run of cargo.
        second_row = [
            placement
            for placement in self.result["placements"]
            if placement.row_index == 1
        ]
        seed = min(second_row, key=lambda item: (item.z, item.y, item.x))
        probe_y = seed.y + seed.w / 2.0
        probe_z = seed.z + seed.h / 2.0
        intervals = [
            (placement.x, placement.x + placement.l)
            for placement in second_row
            if placement.y <= probe_y < placement.y + placement.w
            and placement.z <= probe_z < placement.z + placement.h
        ]
        start, end = self.assert_intervals_are_contiguous(intervals)
        self.assertGreater(end - start, 1200.0)

    def test_same_input_has_the_same_geometry_signature(self):
        repeated = pack_container(self.container, self.products)
        self.assertEqual(
            self.geometry_signature(repeated),
            self.geometry_signature(self.result),
        )


class MaximumUtilizationFloorFirstTests(
    TransportEngineInvariantMixin,
    SimpleTestCase,
):
    def test_floor_first_is_isolated_and_preserves_existing_quantities(self):
        container = transport_container("maximum_utilization_floor_first")
        products = maximum_regression_products()
        result = pack_container(container, products)
        existing = pack_container(
            transport_container("maximum_utilization"),
            products,
        )

        self.assert_transport_invariants(result, container, products)
        self.assertEqual(result["packing_mode"], "maximum_utilization_floor_first")
        self.assertEqual(result["strategy"], "floor_first_blocks_adjacent")
        self.assertEqual(
            Counter(placement.row_index for placement in result["placements"]),
            {0: 20, 1: 100},
        )
        self.assertLessEqual(
            max(placement.z for placement in result["placements"]),
            max(placement.z for placement in existing["placements"]),
        )
        repeated = pack_container(container, products)
        self.assertEqual(
            self.geometry_signature(result),
            self.geometry_signature(repeated),
        )

    def test_floor_first_fills_width_rows_then_vertical_layers(self):
        container = {
            "L": 3.0,
            "W": 2.0,
            "H": 3.0,
            "max_weight": None,
            "packing_mode": "maximum_utilization_floor_first",
        }
        products = [product("Cube", 1, 1, 1, 18)]

        result = pack_container(container, products)
        self.assert_transport_invariants(result, container, products)
        self.assertEqual(result["strategy"], "floor_first_blocks_adjacent")
        self.assertEqual(result["floor_first_candidate_source"], "floor_first")
        self.assertTrue(result["floor_first_candidate_selected"])
        self.assertEqual(
            [
                (placement.x, placement.y, placement.z)
                for placement in result["placements"]
            ],
            [
                (x, y, z)
                for x in range(3)
                for z in range(3)
                for y in range(2)
            ],
        )
        self.assertEqual(result["unplaced"], [])

    def test_floor_first_reported_case_is_distinct_and_complete(self):
        container = {
            "L": 12039.0,
            "W": 2362.0,
            "H": 2692.0,
            "max_weight": 26000.0,
            "packing_mode": "maximum_utilization_floor_first",
        }
        products = [
            product("SKU302473", 457.2, 279.4, 317.5, 375, weight=0.227, sequence=4),
            product("SKU503739", 431.8, 318.77, 317.5, 405, weight=0.907, sequence=3),
            product("Case Pack 12", 558.8, 377.444, 317.5, 288, weight=0.907, sequence=2),
            product("Case Pack", 558.8, 355.6, 381.0, 160, weight=2.268, sequence=1),
        ]

        result = pack_container(container, products)
        maximum = pack_container(
            {**container, "packing_mode": "maximum_utilization"},
            products,
        )
        self.assert_transport_invariants(result, container, products)
        self.assertEqual(
            Counter(placement.row_index for placement in result["placements"]),
            {0: 375, 1: 405, 2: 288, 3: 160},
        )
        self.assertEqual(result["unplaced"], [])
        self.assertEqual(result["strategy"], "floor_first_blocks_adjacent")
        self.assertEqual(
            result["floor_first_residual_packed_units"],
            result["floor_first_residual_units"],
        )
        self.assertEqual(result["floor_first_residual_unplaced_units"], 0)
        case_pack_block = next(
            block
            for block in result["floor_first_main_blocks"]
            if block["row_index"] == 3
        )
        case_pack_residual = [
            placement
            for placement in result["placements"]
            if placement.row_index == 3
            and placement.x >= case_pack_block["x_end"] - TOLERANCE
        ]
        self.assertEqual(
            len(case_pack_residual),
            products[3]["qty"] - case_pack_block["qty"],
        )
        self.assertNotEqual(
            self.geometry_signature(result),
            self.geometry_signature(maximum),
        )


class StrictSequenceRegressionTests(
    TransportEngineInvariantMixin,
    SimpleTestCase,
):
    def test_frontier_is_full_width_and_per_product_row(self):
        container = transport_container("sequence_loading")
        products = frontier_regression_products()
        result = pack_container(container, products)
        self.assert_transport_invariants(result, container, products)

        zones = result["sequence_zones"]
        self.assertEqual(len(zones), 2)
        self.assertEqual([zone["row_index"] for zone in zones], [0, 1])
        self.assertTrue(all(zone["strict_full_width_frontier"] for zone in zones))
        self.assertEqual({product_["sequence"] for product_ in products}, {1})

        frontier = zones[0]["x_end"]
        later = [
            placement
            for placement in result["placements"]
            if placement.row_index == 1
        ]
        self.assertTrue(later)
        self.assertEqual(min(placement.x for placement in later), frontier)
        self.assertTrue(
            all(placement.x >= frontier - TOLERANCE for placement in later)
        )


class AccessibleSequenceRegressionTests(
    TransportEngineInvariantMixin,
    SimpleTestCase,
):
    def test_established_eur_pallet_quantity_family_uses_only_transition_band(self):
        compaction_moves = 0
        for pallet_qty in (21, 23, 25, 27, 29):
            with self.subTest(pallet_qty=pallet_qty):
                container = transport_container("accessible_sequence_loading")
                products = [
                    eur_palletized_load(pallet_qty),
                    product("Product 2", 500, 400, 700, 100),
                ]
                result = pack_container(container, products)
                self.assert_transport_invariants(result, container, products)
                self.assertEqual(
                    result["strategy"],
                    "accessible_sequence_loading",
                )

                zones = result["sequence_zones"]
                transition_start = zones[0]["final_band_start"]
                strict_frontier = zones[0]["x_end"]
                later = [
                    placement
                    for placement in result["placements"]
                    if placement.row_index == 1
                ]
                later_min_x = min(placement.x for placement in later)

                self.assertEqual(len(later), 100)
                self.assertGreater(zones[1]["side_gap_qty"], 0)
                self.assertGreaterEqual(
                    later_min_x,
                    transition_start - TOLERANCE,
                )
                self.assertLess(later_min_x, strict_frontier - TOLERANCE)
                compaction_moves += (
                    zones[1]["compaction_component_moves"]
                    + zones[1]["compaction_stack_moves"]
                    + zones[1]["compaction_individual_moves"]
                )

        self.assertGreater(compaction_moves, 0)

    def test_backward_and_forward_compaction_remain_accessible_only(self):
        container = transport_container("accessible_sequence_loading")
        products = frontier_regression_products()
        result = pack_container(container, products)
        self.assert_transport_invariants(result, container, products)

        later_zone = result["sequence_zones"][1]
        self.assertEqual(result["strategy"], "accessible_sequence_loading")
        self.assertGreater(later_zone["side_gap_qty"], 0)
        self.assertGreater(later_zone["compaction_component_moves"], 0)
        self.assertGreater(later_zone["forward_compacted_components"], 0)
        self.assertGreater(later_zone["forward_compacted_placements"], 0)


class PackingModeIsolationTests(
    TransportEngineInvariantMixin,
    SimpleTestCase,
):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.products = frontier_regression_products()
        cls.results = {}
        for mode in (
            "maximum_utilization",
            "accessible_sequence_loading",
            "sequence_loading",
        ):
            container = transport_container(mode)
            cls.results[mode] = (container, pack_container(container, cls.products))

    def test_modes_keep_distinct_observable_geometry(self):
        minimum_x = {}
        for mode, (container, result) in self.results.items():
            self.assert_transport_invariants(result, container, self.products)
            minimum_x[mode] = min(
                placement.x
                for placement in result["placements"]
                if placement.row_index == 1
            )

        maximum = self.results["maximum_utilization"][1]
        accessible = self.results["accessible_sequence_loading"][1]
        strict = self.results["sequence_loading"][1]
        maximum_row_zero_end = max(
            placement.x + placement.l
            for placement in maximum["placements"]
            if placement.row_index == 0
        )
        strict_frontier = strict["sequence_zones"][0]["x_end"]

        self.assertLess(
            minimum_x["maximum_utilization"],
            maximum_row_zero_end - TOLERANCE,
        )
        self.assertFalse(maximum["maximum_uses_sequence_frontier"])
        self.assertEqual(maximum["sequence_zones"], [])

        self.assertLess(
            minimum_x["accessible_sequence_loading"],
            strict_frontier - TOLERANCE,
        )
        self.assertEqual(
            accessible["strategy"],
            "accessible_sequence_loading",
        )

        self.assertEqual(minimum_x["sequence_loading"], strict_frontier)
        self.assertNotEqual(
            self.geometry_signature(accessible),
            self.geometry_signature(strict),
        )


class SpaceEvenlyTests(
    TransportEngineInvariantMixin,
    SimpleTestCase,
):
    def test_preserves_quantity_with_complete_blocks_and_door_leftovers(self):
        products = [product("Cube", 1000, 1000, 1000, 8)]
        maximum_container = {
            "L": 4000.0,
            "W": 2000.0,
            "H": 2000.0,
            "max_weight": None,
            "packing_mode": "maximum_utilization",
        }
        evenly_container = {
            **maximum_container,
            "packing_mode": "space_evenly",
        }

        maximum = pack_container(maximum_container, products)
        result = pack_container(evenly_container, products)
        self.assert_transport_invariants(result, evenly_container, products)

        self.assertEqual(result["strategy"], "space_evenly_blocks")
        self.assertEqual(len(maximum["placements"]), 8)
        self.assertEqual(len(result["placements"]), 8)
        self.assertEqual(result["space_evenly_target_counts"], {"0": 8})
        self.assertEqual(result["space_evenly_effective_height"], 2000.0)
        self.assertEqual(result["space_evenly_height_reduction"], 0.0)
        self.assertEqual(result["space_evenly_main_block_count"], 1)
        self.assertEqual(result["space_evenly_block_packed_units"], 8)
        self.assertEqual(result["space_evenly_residual_packed_units"], 0)

    def test_main_block_is_a_complete_homogeneous_lattice(self):
        container = {
            "L": 6000.0,
            "W": 2000.0,
            "H": 2000.0,
            "max_weight": None,
            "packing_mode": "space_evenly",
        }
        products = [product("Remainder", 400, 500, 500, 103)]
        result = pack_container(container, products)
        self.assert_transport_invariants(result, container, products)

        block = result["space_evenly_main_blocks"][0]
        orientation = tuple(block["orientation"])
        self.assertEqual(block["qty"], block["nx"] * block["ny"] * block["nz"])
        main = [
            placement
            for placement in result["placements"]
            if placement.x < result["space_evenly_main_blocks_end_x"] - TOLERANCE
        ]
        self.assertEqual(len(main), block["qty"])
        self.assertEqual(
            {
                (placement.l, placement.w, placement.h)
                for placement in main
            },
            {orientation},
        )
        expected = {
            (
                block["x_start"] + ix * orientation[0],
                block["y_start"] + iy * orientation[1],
                iz * orientation[2],
            )
            for iz in range(block["nz"])
            for iy in range(block["ny"])
            for ix in range(block["nx"])
        }
        actual = {
            (placement.x, placement.y, placement.z)
            for placement in main
        }
        self.assertEqual(actual, expected)

    def test_full_height_is_kept_when_lower_ceiling_loses_target_quantity(self):
        container = {
            "L": 2000.0,
            "W": 2000.0,
            "H": 2000.0,
            "max_weight": None,
            "packing_mode": "space_evenly",
        }
        products = [product("Cube", 1000, 1000, 1000, 8)]
        result = pack_container(container, products)

        self.assert_transport_invariants(result, container, products)
        self.assertEqual(result["space_evenly_effective_height"], container["H"])
        self.assertEqual(result["space_evenly_target_total_units"], 8)
        self.assertTrue(
            all(
                placement.z + placement.h
                <= result["space_evenly_effective_height"] + TOLERANCE
                for placement in result["placements"]
            )
        )

    def test_structured_blocks_hand_a_true_remainder_to_physical_residual_fill(self):
        container = {
            "L": 2000.0,
            "W": 2000.0,
            "H": 2000.0,
            "max_weight": None,
            "packing_mode": "space_evenly",
        }
        products = [product("Odd cube quantity", 1000, 1000, 1000, 5)]
        result = pack_container(container, products)

        self.assert_transport_invariants(result, container, products)
        self.assertEqual(result["space_evenly_target_total_units"], 5)
        self.assertEqual(result["space_evenly_block_packed_units"], 4)
        self.assertEqual(result["space_evenly_residual_packed_units"], 1)
        self.assertGreater(
            result["space_evenly_total_residual_candidates_evaluated"],
            0,
        )

    def test_two_and_three_product_targets_preserve_physical_invariants(self):
        fixtures = (
            [
                product("A", 1000, 1000, 500, 4, sequence=1),
                product("B", 500, 1000, 500, 4, sequence=2),
            ],
            [
                product("A", 1000, 1000, 500, 4, sequence=1),
                product("B", 500, 1000, 500, 4, sequence=2),
                product("C", 500, 500, 500, 4, sequence=3),
            ],
        )
        for products in fixtures:
            with self.subTest(product_rows=len(products)):
                container = {
                    "L": 4000.0,
                    "W": 2000.0,
                    "H": 2000.0,
                    "max_weight": 1000.0,
                    "packing_mode": "space_evenly",
                }
                result = pack_container(container, products)
                self.assert_transport_invariants(result, container, products)
                self.assertEqual(
                    Counter(
                        placement.row_index
                        for placement in result["placements"]
                    ),
                    {row_index: 4 for row_index in range(len(products))},
                )
                self.assertLessEqual(
                    result["space_evenly_effective_height"],
                    container["H"],
                )

    def test_four_product_main_blocks_are_contiguous_and_residuals_are_door_side(self):
        container = {
            "L": 7000.0,
            "W": 2000.0,
            "H": 2000.0,
            "max_weight": None,
            "packing_mode": "space_evenly",
        }
        products = [
            product("A", 1000, 1000, 500, 5, sequence=1),
            product("B", 800, 1000, 500, 5, sequence=2),
            product("C", 600, 1000, 500, 5, sequence=3),
            product("D", 400, 1000, 500, 5, sequence=4),
        ]
        result = pack_container(container, products)
        self.assert_transport_invariants(result, container, products)

        blocks = result["space_evenly_main_blocks"]
        self.assertEqual(result["strategy"], "space_evenly_blocks")
        self.assertEqual(len(blocks), 4)
        self.assertEqual(
            len({block["row_index"] for block in blocks}),
            len(blocks),
        )
        self.assertEqual(blocks[0]["x_start"], 0.0)
        for previous, current in zip(blocks, blocks[1:]):
            self.assertEqual(previous["x_end"], current["x_start"])

        frontier = result["space_evenly_residual_zone_start"]
        self.assertEqual(frontier, blocks[-1]["x_end"])
        main_placements = [
            placement
            for placement in result["placements"]
            if placement.x < frontier - TOLERANCE
        ]
        residual_placements = [
            placement
            for placement in result["placements"]
            if placement.x >= frontier - TOLERANCE
        ]
        self.assertTrue(residual_placements)
        self.assertGreater(
            len({placement.row_index for placement in residual_placements}),
            1,
        )
        self.assertTrue(
            all(
                placement.x >= frontier - TOLERANCE
                for placement in residual_placements
            )
        )

        matched_main = 0
        for block in blocks:
            zone = [
                placement
                for placement in main_placements
                if placement.x >= block["x_start"] - TOLERANCE
                and placement.x + placement.l <= block["x_end"] + TOLERANCE
            ]
            self.assertEqual(len(zone), block["qty"])
            self.assertEqual(
                {placement.row_index for placement in zone},
                {block["row_index"]},
            )
            matched_main += len(zone)
        self.assertEqual(matched_main, len(main_placements))

        self.assertLessEqual(
            result["space_evenly_block_candidates_generated"],
            12 * len(products),
        )
        self.assertLessEqual(
            result["space_evenly_beam_states_evaluated"],
            len(products) * (12 + 1) * 10,
        )
        self.assertLessEqual(
            result["space_evenly_residual_states_evaluated"],
            6,
        )

    def test_reported_1228_unit_case_is_complete_bounded_and_deterministic(self):
        container = {
            "L": 12039.0,
            "W": 2362.0,
            "H": 2692.0,
            "max_weight": 26000.0,
            "packing_mode": "space_evenly",
        }
        products = [
            product("SKU302473", 457.2, 279.4, 317.5, 375, weight=0.227, sequence=1),
            product("SKU503739", 431.8, 318.77, 317.5, 405, weight=0.907, sequence=2),
            product("Case Pack 12", 558.8, 377.444, 317.5, 288, weight=0.907, sequence=3),
            product("Case Pack", 558.8, 355.6, 381.0, 160, weight=2.268, sequence=4),
        ]

        first = pack_container(container, products)
        second = pack_container(container, products)
        self.assert_transport_invariants(first, container, products)
        self.assertEqual(
            Counter(placement.row_index for placement in first["placements"]),
            {0: 375, 1: 405, 2: 288, 3: 160},
        )
        self.assertEqual(first["unplaced"], [])
        self.assertEqual(first["space_evenly_main_block_count"], 4)
        self.assertEqual(
            [
                (block["row_index"], block["qty"])
                for block in first["space_evenly_main_blocks"]
            ],
            [(0, 360), (1, 392), (2, 288), (3, 140)],
        )
        self.assertEqual(first["space_evenly_main_block_units"], 1180)
        self.assertEqual(first["space_evenly_residual_units"], 48)
        self.assertLessEqual(first["space_evenly_block_candidates_generated"], 48)
        self.assertEqual(first["space_evenly_beam_states_evaluated"], 0)
        self.assertEqual(first["space_evenly_residual_states_evaluated"], 1)
        frontier = first["space_evenly_residual_zone_start"]
        main_placements = [
            placement
            for placement in first["placements"]
            if placement.x < frontier - TOLERANCE
        ]
        self.assertEqual(
            len(main_placements),
            first["space_evenly_main_block_units"],
        )
        for block in first["space_evenly_main_blocks"]:
            block_placements = [
                placement
                for placement in main_placements
                if placement.x >= block["x_start"] - TOLERANCE
                and placement.x + placement.l <= block["x_end"] + TOLERANCE
            ]
            self.assertEqual(len(block_placements), block["qty"])
            self.assertEqual(
                {placement.row_index for placement in block_placements},
                {block["row_index"]},
            )
        self.assertEqual(
            self.geometry_signature(first),
            self.geometry_signature(second),
        )

    def test_non_stackable_rotation_payload_and_zero_weight_contracts(self):
        non_stackable_container = {
            "L": 500.0,
            "W": 500.0,
            "H": 1000.0,
            "max_weight": None,
            "packing_mode": "space_evenly",
        }
        non_stackable = [
            product("Non-stackable", 500, 500, 500, 2, stackable=False),
        ]
        result = pack_container(non_stackable_container, non_stackable)
        self.assert_transport_invariants(
            result,
            non_stackable_container,
            non_stackable,
        )
        self.assertEqual(len(result["placements"]), 1)
        self.assertEqual(result["space_evenly_target_counts"], {"0": 1})

        rotation_container = {
            "L": 100.0,
            "W": 200.0,
            "H": 300.0,
            "max_weight": None,
            "packing_mode": "space_evenly",
        }
        rotation_products = [product("R3 only", 300, 100, 200, 1)]
        rotation_products[0].update({"r1": False, "r2": False, "r3": True})
        rotated = pack_container(rotation_container, rotation_products)
        self.assert_transport_invariants(
            rotated,
            rotation_container,
            rotation_products,
        )
        self.assertEqual(len(rotated["placements"]), 1)
        self.assertEqual(
            (rotated["placements"][0].l, rotated["placements"][0].w, rotated["placements"][0].h),
            (100.0, 200.0, 300.0),
        )

        payload_container = {
            "L": 100.0,
            "W": 100.0,
            "H": 400.0,
            "max_weight": 15.0,
            "packing_mode": "space_evenly",
        }
        payload_products = [
            product("Payload limited", 100, 100, 100, 3, weight=10),
            product("Zero weight", 100, 100, 100, 3, weight=0, sequence=2),
        ]
        payload_result = pack_container(payload_container, payload_products)
        self.assert_transport_invariants(
            payload_result,
            payload_container,
            payload_products,
        )
        self.assertEqual(
            Counter(
                placement.row_index
                for placement in payload_result["placements"]
            ),
            {1: 3},
        )
        self.assertEqual(len(payload_result["unplaced"]), 3)

    def test_result_is_deterministic_and_metadata_is_json_safe(self):
        container = {
            "L": 3000.0,
            "W": 2000.0,
            "H": 1500.0,
            "max_weight": None,
            "packing_mode": "space_evenly",
        }
        products = [
            product("A", 1000, 1000, 500, 5),
            product("B", 500, 500, 500, 3, sequence=2),
        ]
        first = pack_container(container, products)
        second = pack_container(container, products)
        self.assertEqual(
            self.geometry_signature(first),
            self.geometry_signature(second),
        )
        metadata = {
            key: value
            for key, value in first.items()
            if key.startswith("space_evenly_")
        }
        self.assertGreaterEqual(
            metadata["space_evenly_total_block_candidates_evaluated"],
            metadata["space_evenly_block_candidates_evaluated"],
        )
        json.dumps(metadata)


class TransportPhysicalContractTests(
    TransportEngineInvariantMixin,
    SimpleTestCase,
):
    def test_payload_and_quantity_accounting_in_every_mode(self):
        products = [
            product("Payload limited", 100, 100, 100, 3, weight=10),
        ]
        for mode in (
            "maximum_utilization",
            "accessible_sequence_loading",
            "sequence_loading",
        ):
            with self.subTest(mode=mode):
                container = {
                    "L": 100.0,
                    "W": 100.0,
                    "H": 300.0,
                    "max_weight": 15.0,
                    "packing_mode": mode,
                }
                result = pack_container(container, products)
                self.assert_transport_invariants(result, container, products)
                self.assertEqual(len(result["placements"]), 1)
                self.assertEqual(len(result["unplaced"]), 2)
                self.assertEqual(result["loaded_weight"], 10.0)
                self.assertTrue(
                    all(
                        item["reason"] == "Container max payload exceeded"
                        for item in result["unplaced"]
                    )
                )

    def test_non_stackable_product_cannot_support_later_cargo(self):
        products = [
            product(
                "Non-stackable base",
                500,
                500,
                500,
                1,
                stackable=False,
            ),
            product("Later cargo", 500, 500, 500, 1),
        ]
        for mode in (
            "maximum_utilization",
            "accessible_sequence_loading",
            "sequence_loading",
        ):
            with self.subTest(mode=mode):
                container = {
                    "L": 500.0,
                    "W": 500.0,
                    "H": 1000.0,
                    "max_weight": None,
                    "packing_mode": mode,
                }
                result = pack_container(container, products)
                self.assert_transport_invariants(result, container, products)
                self.assertEqual(
                    Counter(
                        placement.row_index
                        for placement in result["placements"]
                    ),
                    {0: 1},
                )
                self.assertEqual(
                    Counter(item["row_index"] for item in result["unplaced"]),
                    {1: 1},
                )
