import json
from itertools import combinations

from django.test import SimpleTestCase

from packagingapp.tools.transport.service import analyze_transport_capacity
from packagingapp.utils.container_tool.engine import (
    TOLERANCE,
    _evaluate_frontier_transition_candidate,
    _evaluate_frontier_transition_candidate_pair,
    _evaluate_next_product_frontier_orientations,
    _frontier_residual_candidate_placements,
    _select_frontier_transition_candidate,
    _settle_deferred_frontier_residuals,
    allowed_orientations,
    build_product_block_candidates,
    choose_product_block,
    normalize_products,
    pack_container,
    sort_products,
)


MODE = "front_to_back"


def container(length, width, height, max_weight=None):
    return {
        "L": float(length),
        "W": float(width),
        "H": float(height),
        "max_weight": max_weight,
        "packing_mode": MODE,
    }


def product(
    name,
    length,
    width,
    height,
    qty,
    *,
    weight=0.0,
    stackable=True,
    sequence=1,
    r1=True,
    r2=False,
    r3=False,
):
    return {
        "name": name,
        "length": float(length),
        "width": float(width),
        "height": float(height),
        "qty": int(qty),
        "weight": float(weight),
        "stackable": bool(stackable),
        "sequence": int(sequence),
        "r1": bool(r1),
        "r2": bool(r2),
        "r3": bool(r3),
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
    def transition_result(
        self,
        next_dimensions,
        *,
        current_quantity=3,
        current_stackable=True,
        next_r2=False,
        next_r3=False,
    ):
        source = [
            product(
                "Current",
                10,
                1,
                1,
                current_quantity,
                stackable=current_stackable,
            ),
            product(
                "Next",
                *next_dimensions,
                99,
                r2=next_r2,
                r3=next_r3,
            ),
        ]
        return pack_container(container(10, 3, 2), source), source

    def test_dgfe_residual_reservation_is_quantity_agnostic(self):
        selected_container = container(3, 5, 2)

        for quantity in (1, 3, 7):
            with self.subTest(quantity=quantity):
                current = normalize_products(
                    [product("Current", 1, 1, 1, quantity)]
                )[0]
                placements, _, packed = _frontier_residual_candidate_placements(
                    current,
                    quantity,
                    0.0,
                    3.0,
                    (1.0, 1.0, 1.0),
                    selected_container,
                    0,
                    0.0,
                    "top_down_row_first",
                )

                self.assertEqual(packed, quantity)
                self.assertEqual(
                    [(item.x, item.y, item.z) for item in placements],
                    [
                        (0.0, float(index), 1.0)
                        for index in range(min(quantity, 5))
                    ]
                    + [
                        (0.0, float(index), 0.0)
                        for index in range(max(quantity - 5, 0))
                    ],
                )

    def test_dgfe_residual_reservation_spans_x_and_caps_at_capacity(self):
        selected_container = container(2, 2, 2)
        current = normalize_products(
            [product("Current", 1, 1, 1, 10)]
        )[0]

        placements, _, packed = _frontier_residual_candidate_placements(
            current,
            7,
            0.0,
            2.0,
            (1.0, 1.0, 1.0),
            selected_container,
            0,
            0.0,
            "top_down_row_first",
        )
        self.assertEqual(packed, 7)
        self.assertEqual(
            [(item.x, item.y, item.z) for item in placements],
            [
                (0.0, 0.0, 1.0),
                (0.0, 1.0, 1.0),
                (0.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (1.0, 0.0, 1.0),
                (1.0, 1.0, 1.0),
                (1.0, 0.0, 0.0),
            ],
        )

        capped, _, capped_qty = _frontier_residual_candidate_placements(
            current,
            10,
            0.0,
            1.0,
            (1.0, 1.0, 1.0),
            selected_container,
            0,
            0.0,
            "top_down_row_first",
        )
        self.assertEqual(capped_qty, 4)
        self.assertEqual(len(capped), 4)

    def test_dgfe_preserves_both_bottom_up_traversals(self):
        selected_container = container(1, 2, 2)
        current = normalize_products(
            [product("Current", 1, 1, 1, 3)]
        )[0]

        row_first, _, _ = _frontier_residual_candidate_placements(
            current,
            3,
            0.0,
            1.0,
            (1.0, 1.0, 1.0),
            selected_container,
            0,
            0.0,
            "bottom_up_row_first",
        )
        column_first, _, _ = _frontier_residual_candidate_placements(
            current,
            3,
            0.0,
            1.0,
            (1.0, 1.0, 1.0),
            selected_container,
            0,
            0.0,
            "bottom_up_column_first",
        )

        self.assertEqual(
            [(item.y, item.z) for item in row_first],
            [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        )
        self.assertEqual(
            [(item.y, item.z) for item in column_first],
            [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0)],
        )

    def test_top_down_column_first_settles_lower_reserved_units_first(self):
        selected_container = container(1, 1, 3)
        current = normalize_products(
            [product("Current", 1, 1, 1, 2)]
        )[0]
        reserved, _, packed = _frontier_residual_candidate_placements(
            current,
            2,
            0.0,
            1.0,
            (1.0, 1.0, 1.0),
            selected_container,
            0,
            0.0,
            "top_down_column_first",
        )
        settled, drops, invalid_reason = _settle_deferred_frontier_residuals(
            reserved,
            [],
            selected_container,
        )

        self.assertEqual(packed, 2)
        self.assertEqual([item.z for item in reserved], [2.0, 1.0])
        self.assertEqual([item.z for item in settled], [1.0, 0.0])
        self.assertEqual(drops, [1.0, 1.0])
        self.assertIsNone(invalid_reason)

    def test_primary_p2_p1_top_down_row_first_candidate_matches_dgfe_geometry(self):
        current, next_product = normalize_products(
            [
                product("SKU503739", 431.8, 318.77, 317.5, 3, weight=0.907),
                product("SKU302473", 457.2, 279.4, 317.5, 375, weight=0.2427),
            ]
        )
        candidate = _evaluate_frontier_transition_candidate(
            current,
            3,
            next_product,
            375,
            "top_down_row_first",
            0.0,
            12039.0,
            (318.77, 431.8, 317.5),
            container(12039, 2362, 2692),
            [],
            0,
            0,
            0.0,
            current_orientation_index=1,
            remaining_length=12039.0,
        )

        self.assertTrue(candidate["valid"], candidate["invalid_reason"])
        self.assertEqual(candidate["gravity_mode"], "deferred_top_down")
        self.assertEqual(candidate["residual_traversal"], "row_first")
        self.assertEqual(
            candidate["virtual_residual_positions"],
            [
                [0.0, 0.0, 2374.5],
                [0.0, 431.8, 2374.5],
                [0.0, 863.6, 2374.5],
            ],
        )
        self.assertEqual(candidate["next_product_selected_orientation"], (279.4, 457.2, 317.5))
        self.assertEqual(
            [
                item["fits_frontier"]
                for item in candidate["next_product_orientation_candidates"]
            ],
            [False, True],
        )
        self.assertEqual(candidate["next_product_qty_packed"], 114)
        self.assertAlmostEqual(candidate["frontier_depth"], 838.2)
        self.assertEqual(candidate["x_rows_evaluated"], 3)
        self.assertEqual(candidate["first_clean_x_row_index"], 2)
        self.assertEqual(
            [item["quantity"] for item in candidate["next_product_x_rows"]],
            [37, 37, 40],
        )
        self.assertEqual(
            [item.z for item in candidate["current_product_placements"]],
            [2222.5, 2222.5, 2222.5],
        )
        self.assertEqual(
            [(item.x, item.y) for item in candidate["current_product_placements"]],
            [(0.0, 0.0), (0.0, 431.8), (0.0, 863.6)],
        )
        self.assertTrue(candidate["gravity_applied"])
        self.assertTrue(candidate["support_valid"])
        self.assertEqual(
            candidate["phase_diagnostics"],
            [
                "candidate_residual_reserved",
                "next_product_all_orientation_evaluation",
                "next_product_row_first_population",
                "gravity_settlement",
                "physical_validation",
                "candidate_scoring",
            ],
        )

    def test_p4_p2_preserves_native_candidate_and_rejects_weak_extension(self):
        current, next_product = normalize_products(
            [
                product("Case Pack", 558.8, 355.6, 381.0, 20, weight=2.268),
                product("SKU503739", 431.8, 318.77, 317.5, 405, weight=0.907),
            ]
        )
        native, extended = _evaluate_frontier_transition_candidate_pair(
            current,
            20,
            next_product,
            405,
            "bottom_up_row_first",
            0.0,
            12039.0,
            (355.6, 558.8, 381.0),
            container(12039, 2362, 2692),
            [],
            0,
            0,
            0.0,
            current_orientation_index=1,
            remaining_length=12039.0,
        )

        self.assertEqual(native["candidate_family"], "native")
        self.assertTrue(native["valid"])
        self.assertAlmostEqual(native["pi_residual_x_footprint"], 355.6)
        self.assertAlmostEqual(native["frontier_depth"], 355.6)
        self.assertEqual(native["next_product_qty_packed"], 10)
        self.assertEqual(
            native["next_product_selected_orientation"],
            (318.77, 431.8, 317.5),
        )

        self.assertEqual(extended["candidate_family"], "dgfe_extended")
        self.assertEqual(extended["next_product_qty_packed"], 50)
        self.assertAlmostEqual(extended["extended_frontier_depth"], 956.31)
        self.assertGreater(
            extended["next_product_regular_block_efficiency"],
            extended["dgfe_marginal_efficiency"],
        )
        self.assertFalse(extended["extension_justified"])
        self.assertEqual(
            extended["extension_decision_reason"],
            "native_preferred_regular_block_more_efficient",
        )

    def test_p2_p1_native_invalid_dgfe_extended_remains_eligible(self):
        current, next_product = normalize_products(
            [
                product("SKU503739", 431.8, 318.77, 317.5, 3, weight=0.907),
                product("SKU302473", 457.2, 279.4, 317.5, 375, weight=0.2427),
            ]
        )
        native, extended = _evaluate_frontier_transition_candidate_pair(
            current,
            3,
            next_product,
            375,
            "top_down_row_first",
            0.0,
            12039.0,
            (318.77, 431.8, 317.5),
            container(12039, 2362, 2692),
            [],
            0,
            0,
            0.0,
            current_orientation_index=1,
            remaining_length=12039.0,
        )

        self.assertFalse(native["valid"])
        self.assertTrue(extended["valid"])
        self.assertTrue(extended["extension_justified"])
        self.assertEqual(
            extended["extension_decision_reason"],
            "native_invalid",
        )
        self.assertAlmostEqual(extended["pi_residual_x_footprint"], 318.77)
        self.assertEqual(extended["next_product_qty_packed"], 114)
        self.assertEqual(
            [item.z for item in extended["current_product_placements"]],
            [2222.5, 2222.5, 2222.5],
        )

    def test_dgfe_extension_is_eligible_without_regular_block_alternative(self):
        current, next_product = normalize_products(
            [
                product("Current", 1, 1, 2, 1),
                product("Next", 1, 1, 1, 3),
            ]
        )
        native, extended = _evaluate_frontier_transition_candidate_pair(
            current,
            1,
            next_product,
            3,
            "bottom_up_row_first",
            0.0,
            3.0,
            (1.0, 1.0, 2.0),
            container(3, 2, 2),
            [],
            0,
            0,
            0.0,
            current_orientation_index=0,
            remaining_length=3.0,
        )

        self.assertEqual(native["next_product_qty_packed"], 2)
        self.assertEqual(extended["next_product_qty_packed"], 3)
        self.assertIsNone(extended["next_product_regular_block_efficiency"])
        self.assertTrue(extended["extension_justified"])
        self.assertEqual(
            extended["extension_decision_reason"],
            "no_regular_block_alternative",
        )

    def test_candidate_selection_minimizes_pi_x_before_local_efficiency(self):
        winner, reason = _select_frontier_transition_candidate(
            [
                {
                    "valid": True,
                    "candidate_family": "native",
                    "strategy": "bottom_up_row_first",
                    "gravity_mode": "bottom_up",
                    "residual_traversal": "row_first",
                    "current_product_orientation_index": 0,
                    "current_product_qty_packed": 20,
                    "pi_residual_x_footprint": 558.8,
                    "frontier_depth": 558.8,
                    "next_product_qty_packed": 40,
                    "frontier_volume_efficiency": 0.95,
                },
                {
                    "valid": True,
                    "candidate_family": "native",
                    "strategy": "bottom_up_row_first",
                    "gravity_mode": "bottom_up",
                    "residual_traversal": "row_first",
                    "current_product_orientation_index": 1,
                    "current_product_qty_packed": 20,
                    "pi_residual_x_footprint": 355.6,
                    "frontier_depth": 355.6,
                    "next_product_qty_packed": 10,
                    "frontier_volume_efficiency": 0.85,
                },
            ]
        )

        self.assertEqual(winner["current_product_orientation_index"], 1)
        self.assertEqual(reason, "smaller_pi_residual_x_footprint")

    def test_deferred_gravity_rejects_non_stackable_landing_surface(self):
        current, next_product = normalize_products(
            [
                product("Current", 2, 2, 1, 1),
                product("Next", 1, 1, 1, 4, stackable=False),
            ]
        )
        candidate = _evaluate_frontier_transition_candidate(
            current,
            1,
            next_product,
            4,
            "top_down_row_first",
            0.0,
            4.0,
            (2.0, 2.0, 1.0),
            container(4, 2, 3),
            [],
            0,
            0,
            0.0,
            current_orientation_index=0,
            remaining_length=4.0,
        )

        self.assertFalse(candidate["valid"])
        self.assertFalse(candidate["support_valid"])
        self.assertEqual(
            candidate["invalid_reason"],
            "no_vertical_union_supported_settlement",
        )

    def test_row_first_wins_when_it_packs_more_next_product(self):
        result, source = self.transition_result((2, 3, 1))
        frontier = result["front_to_back_frontiers"][0]
        candidates = frontier["residual_strategy_candidates"]

        self.assertEqual(
            frontier["selected_residual_strategy"],
            "bottom_up_row_first",
        )
        self.assertEqual(frontier["selection_reason"], "better_frontier_efficiency")
        self.assertEqual(frontier["next_product_population_strategy"], "row_first")
        dgfe_candidates = [
            item
            for item in candidates
            if item["candidate_family"] == "dgfe_extended"
        ]
        self.assertEqual(
            [
                (
                    item["strategy"],
                    item["current_product_residual_packed"],
                    item["next_product_qty_packed"],
                )
                for item in dgfe_candidates[:4]
            ],
            [
                ("top_down_column_first", 0, 0),
                ("top_down_row_first", 3, 5),
                ("bottom_up_column_first", 3, 0),
                ("bottom_up_row_first", 3, 5),
            ],
        )
        self.assert_geometry(result, container(10, 3, 2), source)

    def test_column_first_wins_when_it_packs_more_next_product(self):
        result, source = self.transition_result((2, 1, 2))
        frontier = result["front_to_back_frontiers"][0]
        candidates = frontier["residual_strategy_candidates"]

        self.assertEqual(
            frontier["selected_residual_strategy"],
            "bottom_up_column_first",
        )
        self.assertEqual(frontier["selection_reason"], "better_frontier_efficiency")
        dgfe_candidates = [
            item
            for item in candidates
            if item["candidate_family"] == "dgfe_extended"
        ]
        self.assertEqual(
            [
                (
                    item["strategy"],
                    item["current_product_residual_packed"],
                    item["next_product_qty_packed"],
                )
                for item in dgfe_candidates[:4]
            ],
            [
                ("top_down_column_first", 3, 5),
                ("top_down_row_first", 3, 0),
                ("bottom_up_column_first", 3, 5),
                ("bottom_up_row_first", 3, 0),
            ],
        )
        self.assert_geometry(result, container(10, 3, 2), source)

    def test_exact_next_product_tie_prefers_row_first(self):
        result, _ = self.transition_result((2, 1, 1))
        frontier = result["front_to_back_frontiers"][0]

        self.assertEqual(
            frontier["selected_residual_strategy"],
            "bottom_up_row_first",
        )
        self.assertEqual(frontier["selection_reason"], "tie_prefer_row_first")
        dgfe_candidates = [
            item
            for item in frontier["residual_strategy_candidates"]
            if item["candidate_family"] == "dgfe_extended"
        ]
        self.assertEqual(
            [
                item["next_product_qty_packed"]
                for item in dgfe_candidates[:4]
            ],
            [15, 15, 15, 15],
        )

    def test_current_product_quantity_is_authoritative(self):
        winner, reason = _select_frontier_transition_candidate(
            [
                {
                    "strategy": "row_first",
                    "current_product_qty_packed": 13,
                    "next_product_qty_packed": 2,
                    "valid": True,
                },
                {
                    "strategy": "column_first",
                    "current_product_qty_packed": 12,
                    "next_product_qty_packed": 99,
                    "valid": False,
                },
            ]
        )

        self.assertEqual(winner["strategy"], "row_first")
        self.assertEqual(reason, "current_product_quantity")

    def test_all_dgfe_candidates_evaluate_all_enabled_next_orientations(self):
        result, _ = self.transition_result((2, 1, 2))
        candidates = result["front_to_back_frontiers"][0][
            "residual_strategy_candidates"
        ]

        self.assertEqual(len(candidates), 16)
        self.assertEqual(
            [candidate["strategy"] for candidate in candidates],
            [
                strategy
                for strategy in (
                    "top_down_column_first",
                    "top_down_row_first",
                    "bottom_up_column_first",
                    "bottom_up_row_first",
                )
                for _ in range(2)
            ]
            * 2,
        )
        self.assertEqual(
            [candidate["candidate_family"] for candidate in candidates],
            ["native", "dgfe_extended"] * 8,
        )
        self.assertTrue(
            all(
                len(candidate["next_product_orientation_candidates"]) == 2
                and candidate["next_product_valid_orientation_count"] == 2
                for candidate in candidates
                if candidate["current_product_residual_packed"] == 3
            )
        )

    def test_winner_quantity_is_carried_into_next_product_phase(self):
        result, _ = self.transition_result((2, 1, 2))
        current_summary, next_summary = result["front_to_back_product_blocks"]

        self.assertEqual(current_summary["qty_of_next_product_loaded_in_frontier"], 5)
        self.assertEqual(next_summary["qty_already_loaded_in_previous_frontier"], 5)
        self.assertEqual(next_summary["qty_entering_product_phase"], 94)

    def test_last_product_uses_row_first_without_two_candidate_evaluation(self):
        source = [product("Final", 10, 1, 1, 3)]
        result = pack_container(container(10, 3, 2), source)
        frontier = result["front_to_back_frontiers"][0]

        self.assertEqual(
            frontier["selected_residual_strategy"],
            "row_first",
        )
        self.assertEqual(frontier["selection_reason"], "no_next_product")
        self.assertEqual(frontier["residual_strategy_candidates"], [])
        self.assertIsNone(frontier["next_product_population_strategy"])

    def test_non_stackable_current_product_cannot_create_vertical_column_layout(self):
        result, source = self.transition_result(
            (2, 1, 2),
            current_quantity=2,
            current_stackable=False,
        )
        frontier = result["front_to_back_frontiers"][0]

        self.assertTrue(
            all(
                placement.row_index != 0 or placement.z == 0.0
                for placement in result["placements"]
            )
        )
        self.assertEqual(
            frontier["selected_residual_strategy"],
            "bottom_up_row_first",
        )
        self.assertEqual(frontier["selection_reason"], "tie_prefer_row_first")
        self.assert_geometry(result, container(10, 3, 2), source)

    def test_transition_diagnostics_and_geometry_are_deterministic(self):
        first, _ = self.transition_result((2, 3, 1))
        second, _ = self.transition_result((2, 3, 1))

        self.assertEqual(
            [
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
                for placement in first["placements"]
            ],
            [
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
                for placement in second["placements"]
            ],
        )
        self.assertEqual(first["front_to_back_frontiers"], second["front_to_back_frontiers"])

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

    def test_explicit_sequence_order_precedes_geometric_priority(self):
        source = [
            product("small", 1, 2, 2, 1, sequence=9),
            product("large", 2, 2, 2, 1, sequence=1),
            product("middle", 2, 1, 2, 1, sequence=2),
        ]
        selected_container = container(20, 10, 10)
        result = pack_container(selected_container, source)
        self.assertEqual(
            [item["row_index"] for item in result["front_to_back_product_order"]],
            [1, 2, 0],
        )
        self.assertEqual(
            [item["sequence"] for item in result["front_to_back_product_order"]],
            [1, 2, 9],
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
        self.assertEqual(maximum["packing_mode"], "front_to_back")
        self.assertEqual(floor_first["packing_mode"], "front_to_back")
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
        self.assertEqual(summary_a["selected_candidate_family"], "native")
        self.assertEqual(
            summary_a["extension_decision_reason"],
            "native_preferred_equal_extension_value",
        )
        self.assertEqual(summary_b["qty_already_loaded_in_previous_frontier"], 1)
        self.assertEqual(summary_b["qty_entering_product_phase"], 2)
        self.assertEqual(summary_b["regular_block_qty"], 2)
        phases = [item["phase"] for item in result["front_to_back_phase_order"]]
        self.assertLess(
            phases.index("current_product_residual"),
            phases.index("next_product_frontier_fill"),
        )
        self.assertIn(
            1,
            [
                item["row_index"]
                for item in result["front_to_back_phase_order"]
                if item["phase"] == "complete_block"
            ],
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
        self.assertEqual(
            first["front_to_back_frontiers"],
            second["front_to_back_frontiers"],
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
        self.assertEqual(frontier["selected_candidate_family"], "native")
        self.assertEqual(
            frontier["selected_residual_orientation"],
            [355.6, 558.8, 381.0],
        )
        self.assertEqual(
            frontier["selected_residual_strategy"],
            "bottom_up_row_first",
        )
        self.assertAlmostEqual(frontier["pi_residual_x_footprint"], 355.6)
        self.assertAlmostEqual(frontier["frontier_depth"], 355.6)
        self.assertEqual(frontier["next_product_qty_packed"], 10)
        self.assertEqual(
            frontier["next_product_selected_orientation"],
            [318.77, 431.8, 317.5],
        )
        protected = next(
            candidate
            for candidate in frontier["residual_strategy_candidates"]
            if candidate["current_product_orientation"]
            == [355.6, 558.8, 381.0]
            and candidate["strategy"] == "bottom_up_row_first"
        )
        protected_orientation = next(
            candidate
            for candidate in protected["next_product_orientation_candidates"]
            if candidate["orientation"] == [318.77, 431.8, 317.5]
        )
        self.assertTrue(protected_orientation["fits_frontier"])
        self.assertEqual(protected_orientation["quantity_packed"], 10)
        self.assertEqual(
            [
                candidate["fits_frontier"]
                for candidate in protected["next_product_orientation_candidates"]
            ],
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
        self.assertEqual(p2_summary["regular_block_qty"], 392)
        self.assertEqual(p2_summary["residual_qty"], 3)

    def test_primary_runtime_evaluates_four_strategies_per_orientation(self):
        result = pack_container(
            container(12039, 2362, 2692),
            primary_case_products(),
            mode=MODE,
        )
        frontier = next(
            item
            for item in result["front_to_back_frontiers"]
            if item["current_product"] == "SKU503739"
            and item["next_product"] == "SKU302473"
        )
        candidates = frontier["residual_strategy_candidates"]

        self.assertEqual(frontier["current_product_residual_requested"], 3)
        self.assertEqual(frontier["candidate_count"], 16)
        self.assertEqual(frontier["base_candidate_count"], 8)
        self.assertEqual(len(candidates), 16)
        self.assertEqual(
            [candidate["candidate_family"] for candidate in candidates],
            ["native", "dgfe_extended"] * 8,
        )
        self.assertEqual(
            frontier["selected_residual_orientation"],
            [318.77, 431.8, 317.5],
        )
        self.assertEqual(
            frontier["selected_residual_strategy"],
            "top_down_row_first",
        )
        self.assertEqual(
            frontier["selected_candidate_family"],
            "dgfe_extended",
        )
        self.assertAlmostEqual(frontier["pi_residual_x_footprint"], 318.77)
        self.assertEqual(frontier["selected_frontier_depth"], 838.1999999999999)
        self.assertAlmostEqual(
            frontier["selected_frontier_volume_efficiency"],
            0.892117,
            places=6,
        )
        self.assertEqual(
            frontier["selection_reason"],
            "smaller_pi_residual_x_footprint",
        )
        self.assertTrue(
            all(
                len(candidate["next_product_orientation_candidates"]) == 2
                and candidate["next_product_valid_orientation_count"] == 1
                for candidate in candidates
            )
        )

        p1_summary = next(
            item
            for item in result["front_to_back_product_blocks"]
            if item["product_name"] == "SKU302473"
        )
        self.assertEqual(p1_summary["qty_already_loaded_in_previous_frontier"], 114)
        self.assertEqual(p1_summary["qty_entering_product_phase"], 261)
        self.assertEqual(len(result["placements"]), 1228)
        self.assertEqual(result["unplaced"], [])

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
