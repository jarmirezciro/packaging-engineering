import json
from itertools import combinations

from django.test import SimpleTestCase

from packagingapp.tools.transport.service import analyze_transport_capacity
from packagingapp.utils.container_tool.engine import (
    TOLERANCE,
    _evaluate_next_product_frontier_orientations,
    allowed_orientations,
    build_product_block_candidates,
    choose_product_block,
    normalize_products,
    pack_container,
    sort_products,
)


MODE = "maximum_utilization_floor_first"


def container(length, width, height, max_weight=None):
    return {
        "L": float(length),
        "W": float(width),
        "H": float(height),
        "max_weight": max_weight,
        "packing_mode": MODE,
    }


def product(name, length, width, height, qty, *, weight=0.0, stackable=True, sequence=1):
    return {
        "name": name,
        "length": float(length),
        "width": float(width),
        "height": float(height),
        "qty": int(qty),
        "weight": float(weight),
        "stackable": bool(stackable),
        "sequence": int(sequence),
        "r1": True,
        "r2": False,
        "r3": False,
    }


def primary_case_products():
    return [
        product("SKU302473", 457.2, 279.4, 317.5, 375, weight=0.2427),
        product("SKU503739", 431.8, 318.77, 317.5, 405, weight=0.907),
        product("Case Pack 12", 558.8, 377.444, 317.5, 288, weight=0.907),
        product("Case Pack", 558.8, 355.6, 381.0, 160, weight=2.268),
    ]


class FrontToBackInvariantMixin:
    def assert_geometry(self, result, selected_container, source_products):
        placements = result["placements"]
        for placement in placements:
            self.assertGreaterEqual(placement.x, -TOLERANCE)
            self.assertGreaterEqual(placement.y, -TOLERANCE)
            self.assertGreaterEqual(placement.z, -TOLERANCE)
            self.assertLessEqual(
                placement.x + placement.l,
                selected_container["L"] + TOLERANCE,
            )
            self.assertLessEqual(
                placement.y + placement.w,
                selected_container["W"] + TOLERANCE,
            )
            self.assertLessEqual(
                placement.z + placement.h,
                selected_container["H"] + TOLERANCE,
            )
            source = source_products[placement.row_index]
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

        for first, second in combinations(placements, 2):
            self.assertFalse(
                min(first.x + first.l, second.x + second.l)
                > max(first.x, second.x) + TOLERANCE
                and min(first.y + first.w, second.y + second.w)
                > max(first.y, second.y) + TOLERANCE
                and min(first.z + first.h, second.z + second.h)
                > max(first.z, second.z) + TOLERANCE,
                (first, second),
            )

        for placement in placements:
            if placement.z <= TOLERANCE:
                continue
            unsupported = [(placement.x, placement.y, placement.l, placement.w)]
            for support in placements:
                if not support.stackable:
                    continue
                if abs(support.z + support.h - placement.z) > TOLERANCE:
                    continue
                updated = []
                sx0, sy0 = support.x, support.y
                sx1, sy1 = support.x + support.l, support.y + support.w
                for x0, y0, length, width in unsupported:
                    x1, y1 = x0 + length, y0 + width
                    ix0, iy0 = max(x0, sx0), max(y0, sy0)
                    ix1, iy1 = min(x1, sx1), min(y1, sy1)
                    if ix1 <= ix0 + TOLERANCE or iy1 <= iy0 + TOLERANCE:
                        updated.append((x0, y0, length, width))
                        continue
                    if ix0 > x0 + TOLERANCE:
                        updated.append((x0, y0, ix0 - x0, width))
                    if x1 > ix1 + TOLERANCE:
                        updated.append((ix1, y0, x1 - ix1, width))
                    middle_length = ix1 - ix0
                    if iy0 > y0 + TOLERANCE:
                        updated.append((ix0, y0, middle_length, iy0 - y0))
                    if y1 > iy1 + TOLERANCE:
                        updated.append((ix0, iy1, middle_length, y1 - iy1))
                unsupported = [
                    rectangle
                    for rectangle in updated
                    if rectangle[2] > TOLERANCE and rectangle[3] > TOLERANCE
                ]
                if not unsupported:
                    break
            self.assertFalse(unsupported, placement)

        loaded = {row_index: 0 for row_index in range(len(source_products))}
        for placement in placements:
            loaded[placement.row_index] += 1
        for item in result["unplaced"]:
            loaded[item["row_index"]] += 1
        self.assertEqual(
            loaded,
            {row_index: source["qty"] for row_index, source in enumerate(source_products)},
        )
        self.assertLessEqual(
            result["loaded_weight"],
            float(selected_container["max_weight"] or float("inf")) + TOLERANCE,
        )


class LoadFrontToBackV1Tests(FrontToBackInvariantMixin, SimpleTestCase):
    def test_shared_sort_prioritizes_largest_valid_footprint(self):
        selected_container = container(12039, 2362, 2692)
        ordered = sort_products(
            normalize_products(primary_case_products()),
            selected_container,
        )
        self.assertEqual(
            [item.name for item in ordered],
            ["Case Pack 12", "Case Pack", "SKU503739", "SKU302473"],
        )

    def test_space_evenly_diagnostics_use_shared_footprint_first_order(self):
        result = pack_container(
            {**container(12039, 2362, 2692), "packing_mode": "space_evenly"},
            primary_case_products(),
        )
        self.assertEqual(
            [item["product_name"] for item in result["space_evenly_product_order"]],
            ["Case Pack 12", "Case Pack", "SKU503739", "SKU302473"],
        )

    def test_front_to_back_diagnostics_use_shared_footprint_first_order(self):
        result = pack_container(
            container(12039, 2362, 2692),
            primary_case_products(),
        )
        self.assertEqual(
            [item["product_name"] for item in result["front_to_back_product_order"]],
            ["Case Pack 12", "Case Pack", "SKU503739", "SKU302473"],
        )

    def test_same_footprint_prefers_larger_unit_volume(self):
        source = [
            product("smaller-volume", 4, 2, 1, 1),
            product("larger-volume", 2, 4, 2, 1),
        ]
        ordered = sort_products(normalize_products(source), container(10, 10, 10))
        self.assertEqual([item.row_index for item in ordered], [1, 0])

    def test_larger_footprint_beats_larger_unit_volume(self):
        source = [
            product("larger-footprint", 5, 2, 1, 1),
            product("larger-volume", 3, 3, 2, 1),
        ]
        ordered = sort_products(normalize_products(source), container(10, 10, 10))
        self.assertEqual([item.row_index for item in ordered], [0, 1])

    def test_same_sequence_order_matches_space_evenly_sorting(self):
        source = [
            product("small", 1, 2, 2, 1, sequence=9),
            product("large", 2, 2, 2, 1, sequence=1),
            product("middle", 2, 1, 2, 1, sequence=2),
        ]
        selected_container = container(20, 10, 10)
        expected = sort_products(
            normalize_products(
                [{**item, "sequence": 1} for item in source]
            ),
            selected_container,
        )
        result = pack_container(selected_container, source)
        self.assertEqual(
            [item["row_index"] for item in result["front_to_back_product_order"]],
            [item.row_index for item in expected],
        )
        self.assertTrue(
            all(item["sequence"] == 1 for item in result["front_to_back_product_order"])
        )

    def test_both_existing_maximum_utilization_identifiers_route_to_v1(self):
        source = [product("A", 1, 1, 1, 3)]
        floor_first = pack_container(container(3, 2, 1), source)
        maximum = pack_container(
            {**container(3, 2, 1), "packing_mode": "maximum_utilization"},
            source,
        )
        self.assertEqual(floor_first["strategy"], "front_to_back_blocks")
        self.assertEqual(maximum["strategy"], "front_to_back_blocks")
        self.assertEqual(maximum["packing_mode"], "maximum_utilization")
        self.assertEqual(
            [
                (item.row_index, item.x, item.y, item.z)
                for item in floor_first["placements"]
            ],
            [
                (item.row_index, item.x, item.y, item.z)
                for item in maximum["placements"]
            ],
        )

    def test_clean_block_uses_the_same_shared_candidate_selector(self):
        selected_container = container(10, 4, 4)
        source = [product("Block", 2, 1, 1, 40)]
        normalized = normalize_products([{**source[0], "sequence": 1}])[0]
        candidates, _ = build_product_block_candidates(
            normalized,
            selected_container,
            selected_container["L"],
        )
        expected = choose_product_block(candidates, normalized.qty, selected_container["L"])
        result = pack_container(selected_container, source)
        actual = result["front_to_back_product_blocks"][0]["block"]
        self.assertIsNotNone(expected)
        self.assertEqual(actual["pattern"], expected.pattern)
        self.assertEqual(actual["capacity"], expected.module_capacity)
        self.assertEqual(actual["depth"], expected.depth)
        self.assertEqual(actual["transverse_capacity"], expected.transverse_capacity)

    def test_residual_is_immediate_and_next_product_is_carried_forward(self):
        selected_container = container(4, 2, 1)
        source = [
            product("A", 1, 1, 1, 3),
            product("B", 1, 1, 1, 3),
        ]
        result = pack_container(selected_container, source)
        self.assert_geometry(result, selected_container, source)
        summary_a, summary_b = result["front_to_back_product_blocks"]
        self.assertEqual(summary_a["regular_block_qty"], 2)
        self.assertEqual(summary_a["residual_qty"], 1)
        self.assertEqual(summary_a["qty_loaded_in_own_frontier"], 1)
        self.assertEqual(summary_a["qty_of_next_product_loaded_in_frontier"], 1)
        self.assertEqual(summary_b["qty_already_loaded_in_previous_frontier"], 1)
        self.assertEqual(summary_b["qty_entering_product_phase"], 2)
        self.assertEqual(summary_b["regular_block_qty"], 2)
        phases = [item["phase"] for item in result["front_to_back_phase_order"]]
        self.assertLess(
            phases.index("current_product_residual"),
            phases.index("next_product_frontier_fill"),
        )
        self.assertLess(
            phases.index("next_product_frontier_fill"),
            max(
                index
                for index, item in enumerate(result["front_to_back_phase_order"])
                if item["phase"] == "complete_block"
                and item["row_index"] == 1
            ),
        )
        frontier_b = [
            placement
            for placement in result["placements"]
            if placement.row_index == 1
        ][0]
        self.assertEqual((frontier_b.x, frontier_b.y, frontier_b.z), (1.0, 1.0, 0.0))

    def test_closed_frontier_is_not_reopened_by_a_later_product(self):
        selected_container = container(5, 2, 1)
        source = [
            product("A", 1, 1, 1, 3),
            product("B", 1, 1, 1, 3),
            product("C", 1, 1, 1, 1),
        ]
        result = pack_container(selected_container, source)
        self.assert_geometry(result, selected_container, source)
        c_placements = [
            placement for placement in result["placements"] if placement.row_index == 2
        ]
        self.assertTrue(c_placements)
        self.assertGreaterEqual(min(placement.x for placement in c_placements), 3.0)
        self.assertTrue(all(frontier["closed"] for frontier in result["front_to_back_frontiers"]))

    def test_non_stackable_and_payload_rules_are_preserved(self):
        non_stackable_container = container(2, 1, 2)
        non_stackable_source = [
            product("Base", 1, 1, 1, 2, stackable=False),
            product("Later", 1, 1, 1, 1),
        ]
        non_stackable_result = pack_container(
            non_stackable_container,
            non_stackable_source,
        )
        self.assert_geometry(
            non_stackable_result,
            non_stackable_container,
            non_stackable_source,
        )
        self.assertEqual(
            [item["row_index"] for item in non_stackable_result["unplaced"]],
            [1],
        )

        payload_container = container(2, 1, 1, max_weight=15)
        payload_source = [
            product("Heavy", 1, 1, 1, 2, weight=10),
            product("Light", 1, 1, 1, 1, weight=1),
        ]
        payload_result = pack_container(payload_container, payload_source)
        self.assert_geometry(payload_result, payload_container, payload_source)
        self.assertEqual(len(payload_result["placements"]), 1)
        self.assertEqual(len(payload_result["unplaced"]), 2)
        self.assertEqual(payload_result["loaded_weight"], 10.0)

    def test_primary_case_is_deterministic_and_diagnostics_are_json_safe(self):
        selected_container = container(12039, 2362, 2692)
        source = [
            product("SKU302473", 457.2, 279.4, 317.5, 375, weight=0.2427),
            product("SKU503739", 431.8, 318.77, 317.5, 405, weight=0.907),
            product("Case Pack 12", 558.8, 377.444, 317.5, 288, weight=0.907),
            product("Case Pack", 558.8, 355.6, 381.0, 160, weight=2.268),
        ]
        first = pack_container(selected_container, source)
        second = pack_container(selected_container, source)
        self.assert_geometry(first, selected_container, source)
        self.assertEqual(
            [
                (
                    item.row_index,
                    item.item_index,
                    item.x,
                    item.y,
                    item.z,
                    item.l,
                    item.w,
                    item.h,
                )
                for item in first["placements"]
            ],
            [
                (
                    item.row_index,
                    item.item_index,
                    item.x,
                    item.y,
                    item.z,
                    item.l,
                    item.w,
                    item.h,
                )
                for item in second["placements"]
            ],
        )
        self.assertEqual(
            first["front_to_back_phase_order"],
            second["front_to_back_phase_order"],
        )
        json.dumps(
            {
                key: value
                for key, value in first.items()
                if key.startswith("front_to_back_")
            }
        )
        self.assertEqual(len(first["placements"]), 1228)
        self.assertEqual(first["unplaced"], [])
        self.assertEqual(
            sum(item["requested_qty"] for item in first["front_to_back_product_blocks"]),
            1228,
        )
        self.assertTrue(first["front_to_back_frontiers"])
        self.assertTrue(
            all(
                first["front_to_back_phase_order"].index(frontier_phase)
                < first["front_to_back_phase_order"].index(block_phase)
                for frontier_phase in first["front_to_back_phase_order"]
                if frontier_phase["phase"] == "next_product_frontier_fill"
                for block_phase in first["front_to_back_phase_order"]
                if block_phase["phase"] == "complete_block"
                and block_phase["row_index"] == frontier_phase["row_index"]
            )
        )

    def test_service_exposes_front_to_back_diagnostics(self):
        analysis = analyze_transport_capacity(
            {
                "container_source": "manual",
                "packing_mode": MODE,
                "container_l": 4,
                "container_w": 2,
                "container_h": 1,
                "max_weight": None,
                "tare_weight": None,
            },
            [
                {
                    **product("A", 1, 1, 1, 3),
                    "max_qty": False,
                },
                {
                    **product("B", 1, 1, 1, 3),
                    "max_qty": False,
                },
            ],
        )
        self.assertTrue(analysis["ok"])
        self.assertIn("front_to_back_product_blocks", analysis["result"])
        self.assertIn("front_to_back_phase_order", analysis["result"])
        self.assertEqual(
            analysis["result"]["packing_mode"],
            MODE,
        )

    def test_next_product_tries_all_orientations_inside_exact_frontier(self):
        result = pack_container(
            container(12039, 2362, 2692),
            primary_case_products(),
            mode=MODE,
        )

        frontier = next(
            item
            for item in result["front_to_back_frontiers"]
            if item["current_product"] == "Case Pack"
            and item["next_product"] == "SKU503739"
        )
        self.assertEqual(frontier["current_product_residual_requested"], 20)
        self.assertEqual(frontier["current_product_residual_packed"], 20)
        self.assertEqual(frontier["next_product_qty_packed"], 10)
        self.assertEqual(
            frontier["next_product_selected_orientation"],
            [318.77, 431.8, 317.5],
        )
        self.assertEqual(frontier["next_product_valid_orientation_count"], 1)
        self.assertEqual(
            [candidate["fits_frontier"] for candidate in frontier["next_product_orientation_candidates"]],
            [False, True],
        )

        p2_summary = next(
            item
            for item in result["front_to_back_product_blocks"]
            if item["product_name"] == "SKU503739"
        )
        self.assertEqual(p2_summary["requested_qty"], 405)
        self.assertEqual(p2_summary["qty_already_loaded_in_previous_frontier"], 10)
        self.assertEqual(p2_summary["qty_entering_product_phase"], 395)

    def test_next_product_without_a_frontier_fit_is_left_for_product_phase(self):
        normalized = normalize_products([product("Next", 4, 3, 1, 1)])[0]
        selected, candidates, _ = _evaluate_next_product_frontier_orientations(
            normalized,
            1,
            0.0,
            2.5,
            container(10, 10, 2),
            [],
            0,
            0.0,
        )
        self.assertIsNone(selected)
        self.assertEqual([item["quantity_packed"] for item in candidates], [0, 0])
