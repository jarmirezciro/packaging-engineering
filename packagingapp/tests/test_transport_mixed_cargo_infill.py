import hashlib
import json
from collections import Counter
from itertools import combinations

from django.test import SimpleTestCase

from packagingapp.tools.transport.modes import (
    FRONT_TO_BACK_INFILL_MODE,
    FRONT_TO_BACK_MODE,
    SPACE_EVENLY_INFILL_MODE,
    SPACE_EVENLY_MODE,
)
from packagingapp.utils.container_tool.engine import (
    TOLERANCE,
    Placement,
    Space,
    build_product_block_candidates,
    choose_product_block,
    derive_local_side_residuals,
    derive_local_top_residuals,
    fill_top_residual_deterministically,
    merge_local_side_residuals,
    merge_local_top_residuals,
    normalize_products,
    pack_container,
)


INFILL_MODES = (SPACE_EVENLY_INFILL_MODE, FRONT_TO_BACK_INFILL_MODE)


def container(mode, *, length=12, width=10, height=5, max_weight=None):
    return {
        "L": float(length),
        "W": float(width),
        "H": float(height),
        "max_weight": max_weight,
        "packing_mode": mode,
    }


def product(
    name,
    length,
    width,
    height,
    qty,
    *,
    weight=0,
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


def geometry_signature(result):
    return tuple(
        (
            placement.product_name,
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


def golden_digest(result):
    payload = {
        "placements": geometry_signature(result),
        "packed": dict(
            sorted(Counter(item.row_index for item in result["placements"]).items())
        ),
        "unplaced": dict(
            sorted(Counter(item["row_index"] for item in result["unplaced"]).items())
        ),
        "loaded_weight": result["loaded_weight"],
        "occupied_x": max(
            (item.x + item.l for item in result["placements"]),
            default=0,
        ),
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def primary_products():
    return [
        product("SKU302473", 457.2, 279.4, 317.5, 375, weight=0.2427),
        product("SKU503739", 431.8, 318.77, 317.5, 405, weight=0.907),
        product("Case Pack 12", 558.8, 377.444, 317.5, 288, weight=0.907),
        product("Case Pack", 558.8, 355.6, 381.0, 160, weight=2.268),
    ]


def simple_side_products(*, filler_qty=6, filler_weight=0, filler_stackable=True):
    return [
        product("Bulky", 4, 6, 5, 4, weight=1),
        product(
            "Small",
            2,
            2,
            5,
            filler_qty,
            weight=filler_weight,
            stackable=filler_stackable,
        ),
    ]


def full_top_support(product_name="P", row_index=0):
    return [
        Placement(
            product_name,
            item_index,
            row_index,
            1,
            0.0,
            True,
            x,
            y,
            z,
            50.0,
            50.0,
            50.0,
        )
        for item_index, (x, y, z) in enumerate(
            (
                (x, y, z)
                for z in (0.0, 50.0, 100.0, 150.0)
                for y in (0.0, 50.0)
                for x in (0.0, 50.0)
            )
        )
    ]


class MixedCargoInfillTests(SimpleTestCase):
    def assert_physical(self, result, selected_container):
        for placement in result["placements"]:
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
        for first, second in combinations(result["placements"], 2):
            overlap = (
                min(first.x + first.l, second.x + second.l)
                > max(first.x, second.x) + TOLERANCE
                and min(first.y + first.w, second.y + second.w)
                > max(first.y, second.y) + TOLERANCE
                and min(first.z + first.h, second.z + second.h)
                > max(first.z, second.z) + TOLERANCE
            )
            self.assertFalse(overlap, (first, second))

    def test_approved_modes_keep_captured_golden_geometry(self):
        selected_container = {
            "L": 12039.0,
            "W": 2362.0,
            "H": 2692.0,
            "max_weight": None,
        }
        expected = {
            SPACE_EVENLY_MODE: (
                "0fe3904ce174d598cd4d7462ed4610328b16198bf5de82bf8b22c2a216a66041"
            ),
            FRONT_TO_BACK_MODE: (
                "8416bd1c04162d9a052d8c53560c30290ae72ffc4a3a4ba12f8cb8b80db5c679"
            ),
        }
        for mode, digest in expected.items():
            with self.subTest(mode=mode):
                result = pack_container(
                    {**selected_container, "packing_mode": mode},
                    primary_products(),
                )
                self.assertEqual(golden_digest(result), digest)
                self.assertEqual(len(result["placements"]), 1228)
                self.assertEqual(result["unplaced"], [])

    def test_historical_front_to_back_identifiers_are_geometry_aliases(self):
        source = simple_side_products()
        canonical = pack_container(container(FRONT_TO_BACK_MODE), source)
        canonical_signature = geometry_signature(canonical)
        for alias in (
            "maximum_utilization",
            "maximum_utilization_floor_first",
            "front_to_back_blocks",
            "load_front_to_back",
        ):
            with self.subTest(alias=alias):
                result = pack_container(container(alias), source)
                self.assertEqual(result["packing_mode"], FRONT_TO_BACK_MODE)
                self.assertEqual(geometry_signature(result), canonical_signature)

    def test_simple_side_infill_preserves_anchor_and_carries_filler_quantity(self):
        source = simple_side_products()
        parent_by_infill = {
            SPACE_EVENLY_INFILL_MODE: SPACE_EVENLY_MODE,
            FRONT_TO_BACK_INFILL_MODE: FRONT_TO_BACK_MODE,
        }
        for mode in INFILL_MODES:
            with self.subTest(mode=mode):
                baseline = pack_container(container(parent_by_infill[mode]), source)
                result = pack_container(container(mode), source)
                baseline_anchor = [
                    item for item in geometry_signature(baseline) if item[1] == 0
                ]
                infill_anchor = [
                    item for item in geometry_signature(result) if item[1] == 0
                ]
                counts = Counter(item.row_index for item in result["placements"])

                self.assertEqual(infill_anchor, baseline_anchor)
                self.assertEqual(counts, {0: 4, 1: 6})
                self.assertEqual(result["unplaced"], [])
                self.assertEqual(result[f"{mode}_infill_units_total"], 6)
                self.assertEqual(result[f"{mode}_side_residuals_filled"], 1)
                self.assertTrue(
                    all(
                        item.y >= 8 - TOLERANCE
                        for item in result["placements"]
                        if item.row_index == 1
                    )
                )
                self.assert_physical(result, container(mode))

    def test_multiple_fillers_use_stable_residual_local_ranking(self):
        source = [
            product("Bulky", 4, 6, 5, 2),
            product("Medium", 3, 1.2, 5, 2),
            product("Small", 2, 0.8, 5, 3),
        ]
        for mode in INFILL_MODES:
            with self.subTest(mode=mode):
                selected_container = container(mode, length=6)
                first = pack_container(selected_container, source)
                second = pack_container(selected_container, source)
                actions = first[f"{mode}_actions"]

                self.assertEqual(geometry_signature(first), geometry_signature(second))
                self.assertEqual(
                    [action["filler_product"] for action in actions],
                    ["Medium", "Small"],
                )
                self.assertEqual(
                    Counter(item.row_index for item in first["placements"]),
                    {0: 2, 1: 2, 2: 3},
                )
                self.assert_physical(first, selected_container)

    def test_residual_quantities_are_generic_and_high_quantity_work_is_bounded(self):
        for mode in INFILL_MODES:
            high_candidate_count = None
            for quantity in (1, 2, 3, 7, 17, 500):
                with self.subTest(mode=mode, quantity=quantity):
                    result = pack_container(
                        container(mode),
                        simple_side_products(filler_qty=quantity),
                    )
                    self.assertEqual(
                        result[f"{mode}_infill_units_total"],
                        min(quantity, 6),
                    )
                    self.assertEqual(result[f"{mode}_historical_gap_searches"], 0)
                    self.assertEqual(result[f"{mode}_backtracking_count"], 0)
                    self.assertEqual(result[f"{mode}_beam_states_evaluated"], 0)
                    if quantity in (17, 500):
                        candidate_count = result[
                            f"{mode}_infill_block_candidates_evaluated"
                        ]
                        if high_candidate_count is None:
                            high_candidate_count = candidate_count
                        else:
                            self.assertEqual(candidate_count, high_candidate_count)

    def test_real_sequence_groups_cooperate_only_within_their_group(self):
        source = [
            product("P1", 4, 6, 5, 2, sequence=1),
            product("P2", 2, 2, 5, 3, sequence=1),
            product("P3", 4, 6, 5, 2, sequence=2),
            product("P4", 2, 2, 5, 3, sequence=2),
            product("P5", 1, 1, 5, 20, sequence=3),
        ]
        for mode in INFILL_MODES:
            with self.subTest(mode=mode):
                result = pack_container(container(mode), source)
                actions = result[f"{mode}_actions"]
                pairs = [
                    (action["anchor_product"], action["filler_product"])
                    for action in actions
                ]

                self.assertEqual(pairs, [("P1", "P2"), ("P3", "P4")])
                self.assertEqual(result[f"{mode}_sequence_group_count"], 3)
                self.assertTrue(result[f"{mode}_sequence_restricted"])
                self.assertNotIn(4, Counter(
                    item.row_index for item in result["placements"]
                ))
                self.assert_physical(result, container(mode))

    def test_stackability_rotation_and_payload_remain_authoritative(self):
        for mode in INFILL_MODES:
            with self.subTest(mode=mode, contract="stackability"):
                selected_container = container(mode, height=10)
                non_stackable = pack_container(
                    selected_container,
                    simple_side_products(
                        filler_qty=12,
                        filler_stackable=False,
                    ),
                )
                filler = [
                    item for item in non_stackable["placements"] if item.row_index == 1
                ]
                self.assertTrue(filler)
                self.assertTrue(all(item.z == 0 for item in filler))
                self.assert_physical(non_stackable, selected_container)

            with self.subTest(mode=mode, contract="payload"):
                payload_result = pack_container(
                    container(mode, max_weight=6),
                    simple_side_products(filler_qty=6, filler_weight=1),
                )
                self.assertEqual(
                    Counter(item.row_index for item in payload_result["placements"]),
                    {0: 4, 1: 2},
                )
                self.assertEqual(payload_result["loaded_weight"], 6)
                self.assertEqual(len(payload_result["unplaced"]), 4)
                self.assert_physical(payload_result, container(mode, max_weight=6))

            with self.subTest(mode=mode, contract="residual_local_rotation"):
                selected_container = container(mode, length=6, width=11)
                source = [
                    product("Bulky", 4, 6, 5, 2),
                    product("Rotated filler", 2, 3, 5, 5),
                ]
                normalized_filler = normalize_products(source)[1]
                whole_candidates, _ = build_product_block_candidates(
                    normalized_filler,
                    selected_container,
                    selected_container["L"],
                )
                whole = choose_product_block(
                    whole_candidates,
                    normalized_filler.qty,
                    selected_container["L"],
                )
                result = pack_container(selected_container, source)
                action = result[f"{mode}_actions"][0]

                self.assertEqual(list(whole.orientations[0]), [3.0, 2.0, 5.0])
                self.assertEqual(action["selected_orientations"][0], [2.0, 3.0, 5.0])
                self.assert_physical(result, selected_container)
                json.dumps(
                    {
                        key: value
                        for key, value in result.items()
                        if key.startswith(f"{mode}_")
                    }
                )

    def test_local_side_residuals_merge_complete_x_faces(self):
        merged = merge_local_side_residuals(
            [
                # These are two computational slices of one physical side
                # space; their full Y/Z faces are identical.
                Space(0.0, 1600.0, 0.0, 500.0, 700.0, 2400.0),
                Space(500.0, 1600.0, 0.0, 500.0, 700.0, 2400.0),
            ]
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(
            (merged[0].x, merged[0].L, merged[0].y, merged[0].W),
            (0.0, 1000.0, 1600.0, 700.0),
        )

    def test_local_side_residuals_use_xy_geometry_and_preserve_x_tail(self):
        selected_container = {"L": 1000.0, "W": 2300.0, "H": 2400.0}
        anchor = type(
            "SyntheticPlacement",
            (),
            {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "l": 1000.0,
                "w": 1600.0,
                "h": 1200.0,
            },
        )()
        residuals = derive_local_side_residuals(
            [anchor], selected_container, 0.0, 1000.0
        )
        self.assertEqual(
            [(space.x, space.L, space.y, space.W) for space in residuals],
            [(0.0, 1000.0, 1600.0, 700.0)],
        )

        partial_filler = type(
            "SyntheticPlacement",
            (),
            {
                "x": 0.0,
                "y": 1600.0,
                "z": 0.0,
                "l": 500.0,
                "w": 400.0,
                "h": 1200.0,
            },
        )()
        residuals = derive_local_side_residuals(
            [anchor, partial_filler], selected_container, 0.0, 1000.0
        )
        self.assertEqual(
            [(space.x, space.L, space.y, space.W) for space in residuals],
            [
                (0.0, 500.0, 2000.0, 300.0),
                (500.0, 500.0, 1600.0, 700.0),
            ],
        )

    def test_reported_mixed_bulky_case_closes_merged_and_frontier_side_spaces(self):
        source = [
            product(
                "EUR palletized load",
                1200,
                800,
                1100,
                20,
                weight=900,
            ),
            product("P2", 500, 400, 700, 100),
            product("P3", 500, 200, 700, 130),
        ]
        selected_container = {
            "L": 12032.0,
            "W": 2352.0,
            "H": 2395.0,
            "max_weight": 26500.0,
        }
        for mode in INFILL_MODES:
            with self.subTest(mode=mode):
                parent_mode = (
                    SPACE_EVENLY_MODE
                    if mode == SPACE_EVENLY_INFILL_MODE
                    else FRONT_TO_BACK_MODE
                )
                baseline = pack_container(
                    {**selected_container, "packing_mode": parent_mode}, source
                )
                result = pack_container(
                    {**selected_container, "packing_mode": mode}, source
                )
                self.assertEqual(
                    [
                        item
                        for item in geometry_signature(result)
                        if item[1] == 0
                    ],
                    [
                        item
                        for item in geometry_signature(baseline)
                        if item[1] == 0
                    ],
                )
                self.assertEqual(
                    Counter(item.row_index for item in result["placements"]),
                    {0: 20, 1: 100, 2: 130},
                )
                self.assertEqual(result["unplaced"], [])
                self.assert_physical(result, selected_container)
                envelopes = result[f"{mode}_side_residual_envelopes"]
                first_envelope = envelopes[0]
                self.assertIn(
                    {"x": 0.0, "y": 2000.0, "z": 0.0, "L": 4800.0, "W": 352.0, "H": 2395.0},
                    first_envelope,
                )
                first_action = result[f"{mode}_actions"][0]
                self.assertEqual(first_action["filler_product"], "P3")
                self.assertEqual(first_action["quantity"], 27)
                self.assertEqual(
                    first_action["selected_block"]["actual_depth_committed"],
                    4500.0,
                )
                self.assertLess(
                    first_action["selected_block"]["actual_depth_committed"],
                    first_action["residual_x_end"]
                    - first_action["residual_x_start"],
                )
                self.assertIn(
                    {
                        "x": 4500.0,
                        "y": 2000.0,
                        "z": 0.0,
                        "L": 300.0,
                        "W": 352.0,
                        "H": 2395.0,
                    },
                    [
                        space
                        for envelope in envelopes
                        for space in envelope
                    ],
                )
                if mode == FRONT_TO_BACK_INFILL_MODE:
                    self.assertIn(
                        {
                            "x": 6800.0,
                            "y": 2000.0,
                            "z": 0.0,
                            "L": 1200.0,
                            "W": 352.0,
                            "H": 2395.0,
                        },
                        [
                            space
                            for envelope in envelopes
                            for space in envelope
                        ],
                    )

    def test_space_evenly_closes_each_residual_frontier_with_shared_quantity_state(self):
        source = [
            product("P1", 1200, 800, 1100, 20),
            product("P2", 500, 400, 700, 100),
            product("P3", 500, 200, 700, 130),
        ]
        selected_container = {
            "L": 12032.0,
            "W": 2352.0,
            "H": 2395.0,
            "max_weight": 26500.0,
            "packing_mode": SPACE_EVENLY_INFILL_MODE,
        }
        result = pack_container(selected_container, source)

        frontiers = result["space_evenly_residual_frontiers"]
        self.assertEqual(len(frontiers), 2)
        self.assertEqual(
            result["space_evenly_infill_residual_frontiers_closed"],
            len(frontiers),
        )
        self.assertEqual(
            result["space_evenly_infill_post_frontier_units"],
            6,
        )
        self.assertEqual(
            result["space_evenly_infill_post_frontier_side_residuals_filled"],
            1,
        )
        self.assertEqual(frontiers[0]["units_added_by_product"], {"2": 6})
        self.assertEqual(frontiers[1]["units_added_by_product"], {})
        self.assertEqual(
            [
                (action["anchor_product"], action["filler_product"], action["quantity"])
                for action in result["space_evenly_infill_actions"]
            ],
            [
                ("P1", "P3", 27),
                ("P2", "P3", 6),
            ],
        )
        self.assertEqual(
            Counter(item.row_index for item in result["placements"]),
            {0: 20, 1: 100, 2: 130},
        )
        self.assertEqual(result["unplaced"], [])
        self.assert_physical(result, selected_container)
        for row_index in range(3):
            item_indices = [
                placement.item_index
                for placement in result["placements"]
                if placement.row_index == row_index
            ]
            self.assertEqual(len(item_indices), len(set(item_indices)))
        self.assertEqual(
            result["space_evenly_infill_historical_gap_searches"],
            0,
        )
        self.assertEqual(result["space_evenly_infill_backtracking_count"], 0)
        self.assertEqual(result["space_evenly_infill_beam_states_evaluated"], 0)

    def test_space_evenly_exact_qty_400_keeps_protected_modes_and_reports_no_fit(self):
        source = [
            product("EUR palletized load", 1200, 800, 1100, 20, weight=900),
            product("P2", 500, 400, 700, 100),
            product("P3", 500, 200, 700, 400),
        ]
        selected_container = {
            "L": 12032.0,
            "W": 2352.0,
            "H": 2395.0,
            "max_weight": 26500.0,
        }
        expected_protected = {
            SPACE_EVENLY_MODE: (
                "b98a1a656cafc6b013e2fde92534be99c54bda9bcec22481d3e5e59ce344b5cc"
            ),
            FRONT_TO_BACK_MODE: (
                "e7ba733515c909717e63efefe607a3ed54b3376514553a0af49012de4bd3d204"
            ),
            FRONT_TO_BACK_INFILL_MODE: (
                "a1163b061f9e1bc8649e0315749ed83d2b687406a9a0699378117f866fb93eca"
            ),
        }
        for mode, expected_digest in expected_protected.items():
            with self.subTest(mode=mode):
                result = pack_container(
                    {**selected_container, "packing_mode": mode}, source
                )
                signature = geometry_signature(result)
                digest = hashlib.sha256(
                    json.dumps(signature, separators=(",", ":")).encode()
                ).hexdigest()
                self.assertEqual(digest, expected_digest)

        result = pack_container(
            {**selected_container, "packing_mode": SPACE_EVENLY_INFILL_MODE},
            source,
        )
        closures = result["space_evenly_infill_post_frontier_closures"]
        self.assertEqual(
            result["space_evenly_infill_residual_frontiers_closed"],
            len(result["space_evenly_residual_frontiers"]),
        )
        self.assertGreaterEqual(
            result["space_evenly_infill_post_frontier_side_residuals_derived"],
            len(closures),
        )
        self.assertTrue(
            any(
                closure["residual_evaluation_reasons"]
                for closure in closures
            )
        )
        self.assertTrue(
            all(
                reason["reason"]
                in {
                    "no_enabled_orientation_fits",
                    "insufficient_width",
                    "insufficient_x_depth",
                    "no_remaining_quantity",
                    "payload_exhausted",
                    "sequence_restriction",
                }
                for closure in closures
                for reason in closure["residual_evaluation_reasons"]
            )
        )
        self.assert_physical(result, selected_container)
        for mode in INFILL_MODES:
            with self.subTest(top_mode=mode):
                mixed = pack_container(
                    {**selected_container, "packing_mode": mode}, source
                )
                self.assertGreater(
                    mixed[f"{mode}_top_support_planes_evaluated"], 0
                )
                self.assertGreaterEqual(
                    mixed[f"{mode}_top_residual_count"], 2
                )
                self.assertTrue(
                    mixed[f"{mode}_top_residual_evaluation_reasons"]
                )

    def test_case_study_current_product_is_eligible_for_supported_top_infill(self):
        source = [
            product(
                "P1",
                1200,
                800,
                1100,
                20,
                weight=900,
                r2=True,
                r3=True,
            ),
            product("P2", 500, 400, 700, 100, r2=True, r3=True),
            product("P3", 500, 200, 700, 400, r2=True, r3=True),
        ]
        selected_container = {
            "L": 12032.0,
            "W": 2352.0,
            "H": 2395.0,
            "max_weight": 26500.0,
        }
        parent_modes = {
            SPACE_EVENLY_INFILL_MODE: SPACE_EVENLY_MODE,
            FRONT_TO_BACK_INFILL_MODE: FRONT_TO_BACK_MODE,
        }
        for mode in INFILL_MODES:
            with self.subTest(mode=mode):
                baseline = pack_container(
                    {**selected_container, "packing_mode": parent_modes[mode]},
                    source,
                )
                result = pack_container(
                    {**selected_container, "packing_mode": mode},
                    source,
                )
                baseline_count = Counter(
                    placement.row_index for placement in baseline["placements"]
                )[2]
                result_count = Counter(
                    placement.row_index for placement in result["placements"]
                )[2]
                top_units = result[f"{mode}_top_infill_units_by_product"].get("2", 0)

                self.assertGreater(result_count, baseline_count)
                self.assertGreater(top_units, 0)
                self.assertTrue(
                    any(
                        action["anchor_product"] == "P3"
                        and action["filler_product"] == "P3"
                        and action["anchor_eligible"]
                        for action in result[f"{mode}_top_actions"]
                    )
                )
                self.assertGreater(
                    result[f"{mode}_top_anchor_candidate_evaluations"],
                    0,
                )
                self.assertTrue(
                    any(
                        residual["anchor_product"] == "P3"
                        and residual["anchor_remaining_quantity"] > 0
                        and residual["anchor_eligible"]
                        for window in result[f"{mode}_top_residual_windows"]
                        for residual in window["residuals"]
                    )
                )
                if mode == SPACE_EVENLY_INFILL_MODE:
                    self.assertTrue(
                        any(
                            frontier["anchor_product"] == "P3"
                            and any(
                                action["anchor_product"] == "P3"
                                and action["anchor_eligible"]
                                and action["anchor_remaining_quantity"] > 0
                                for action in frontier.get(
                                    "top_infill_actions", []
                                )
                            )
                            for frontier in result[
                                "space_evenly_residual_frontiers"
                            ]
                        )
                    )
                self.assert_physical(result, selected_container)

    def test_supported_top_residuals_are_local_roof_clear_and_height_specific(self):
        selected_container = {"L": 100.0, "W": 100.0, "H": 300.0}
        lower = Placement(
            "Lower", 0, 0, 1, 0.0, True, 0.0, 0.0, 0.0, 100.0, 100.0, 100.0
        )
        upper = Placement(
            "Upper", 0, 0, 1, 0.0, True, 0.0, 0.0, 100.0, 50.0, 100.0, 50.0
        )
        self.assertEqual(
            derive_local_top_residuals(
                [lower], selected_container, 0.0, 100.0
            ),
            [Space(0.0, 0.0, 100.0, 100.0, 100.0, 200.0)],
        )
        residuals = derive_local_top_residuals(
            [lower, upper], selected_container, 0.0, 100.0
        )
        self.assertEqual(
            [(space.x, space.y, space.z, space.L, space.W, space.H) for space in residuals],
            [
                (50.0, 0.0, 100.0, 50.0, 100.0, 200.0),
                (0.0, 0.0, 150.0, 50.0, 100.0, 150.0),
            ],
        )

    def test_supported_top_union_merges_touching_supporters_but_not_gaps_or_heights(self):
        touching = [
            Placement("Lower", 0, 0, 1, 0.0, True, 0.0, 0.0, 0.0, 50.0, 50.0, 100.0),
            Placement("Lower", 1, 0, 1, 0.0, True, 50.0, 0.0, 0.0, 50.0, 50.0, 100.0),
        ]
        selected_container = {"L": 100.0, "W": 50.0, "H": 300.0}
        self.assertEqual(
            merge_local_top_residuals(
                [
                    Space(0.0, 0.0, 100.0, 50.0, 50.0, 200.0),
                    Space(50.0, 0.0, 100.0, 50.0, 50.0, 200.0),
                ]
            ),
            [Space(0.0, 0.0, 100.0, 100.0, 50.0, 200.0)],
        )
        self.assertEqual(
            derive_local_top_residuals(touching, selected_container, 0.0, 100.0),
            [Space(0.0, 0.0, 100.0, 100.0, 50.0, 200.0)],
        )
        gap = [
            touching[0],
            Placement("Lower", 1, 0, 1, 0.0, True, 60.0, 0.0, 0.0, 40.0, 50.0, 100.0),
        ]
        self.assertEqual(
            [(space.x, space.L) for space in derive_local_top_residuals(gap, selected_container, 0.0, 100.0)],
            [(0.0, 50.0), (60.0, 40.0)],
        )
        different_height = touching + [
            Placement("Higher", 0, 0, 1, 0.0, True, 0.0, 0.0, 100.0, 50.0, 50.0, 50.0)
        ]
        self.assertEqual(
            sorted({space.z for space in derive_local_top_residuals(different_height, selected_container, 0.0, 100.0)}),
            [100.0, 150.0],
        )

    def test_supported_top_fill_rederives_and_synchronizes_quantity_state(self):
        products = normalize_products(
            [
                product("Anchor", 100, 100, 100, 1),
                product("Filler", 50, 50, 50, 10),
            ]
        )
        selected_container = {
            "L": 100.0,
            "W": 100.0,
            "H": 300.0,
            "max_weight": None,
        }
        committed = [
            Placement("Anchor", 0, 0, 1, 0.0, True, 0.0, 0.0, 0.0, 100.0, 100.0, 100.0)
        ]
        remaining = {0: 0, 1: 10}
        next_item_index = {0: 1, 1: 0}
        placements, loaded_weight, stats = fill_top_residual_deterministically(
            Space(0.0, 0.0, 0.0, 100.0, 100.0, 300.0),
            products[0],
            products,
            remaining,
            next_item_index,
            selected_container,
            0.0,
            False,
            eligible_row_indices={1},
            committed_placements=committed,
            window_x_start=0.0,
            window_x_end=100.0,
        )
        self.assertEqual(len(placements), 10)
        self.assertEqual(remaining, {0: 0, 1: 0})
        self.assertEqual(next_item_index, {0: 1, 1: 10})
        self.assertEqual(loaded_weight, 0.0)
        self.assertEqual(stats["top_infill_units_total"], 10)
        self.assertEqual(stats["top_residuals_filled"], 1)
        self.assertEqual(stats["top_actions"][0]["support_validation"], "full_union_supported")
        self.assertTrue(all(item.z >= 100.0 for item in placements))
        self.assert_physical({"placements": committed + placements}, selected_container)

    def test_top_infill_allows_same_product_continuation_without_duplicate_indices(self):
        products = normalize_products(
            [product("P", 50, 50, 50, 22)]
        )
        selected_container = {
            "L": 100.0,
            "W": 100.0,
            "H": 250.0,
            "max_weight": None,
        }
        committed = full_top_support()
        remaining = {0: 6}
        next_item_index = {0: 16}
        placements, loaded_weight, stats = fill_top_residual_deterministically(
            Space(0.0, 0.0, 0.0, 100.0, 100.0, 250.0),
            products[0],
            products,
            remaining,
            next_item_index,
            selected_container,
            0.0,
            False,
            eligible_row_indices={0},
            committed_placements=committed,
            window_x_start=0.0,
            window_x_end=100.0,
        )

        self.assertEqual(len(placements), 4)
        self.assertEqual(remaining, {0: 2})
        self.assertEqual(next_item_index, {0: 20})
        self.assertEqual(loaded_weight, 0.0)
        self.assertEqual(
            [placement.item_index for placement in placements],
            [16, 17, 18, 19],
        )
        self.assertTrue(all(placement.product_name == "P" for placement in placements))
        self.assertTrue(all(placement.z == 200.0 for placement in placements))
        self.assertEqual(stats["top_infill_units_by_product"], {"0": 4})
        self.assertEqual(stats["top_actions"][0]["filler_product"], "P")
        self.assertTrue(stats["top_actions"][0]["anchor_eligible"])
        self.assertEqual(stats["top_actions"][0]["anchor_remaining_quantity"], 6)
        self.assert_physical({"placements": committed + placements}, selected_container)

    def test_top_infill_final_product_can_fill_its_own_supported_residual(self):
        products = normalize_products(
            [
                product("Consumed", 50, 50, 50, 0),
                product("Final", 50, 50, 50, 6),
            ]
        )
        selected_container = {
            "L": 100.0,
            "W": 100.0,
            "H": 250.0,
            "max_weight": None,
        }
        committed = full_top_support("Final", row_index=1)
        remaining = {0: 0, 1: 6}
        next_item_index = {0: 0, 1: 16}
        placements, _, stats = fill_top_residual_deterministically(
            Space(0.0, 0.0, 0.0, 100.0, 100.0, 250.0),
            products[1],
            products,
            remaining,
            next_item_index,
            selected_container,
            0.0,
            False,
            eligible_row_indices={1},
            committed_placements=committed,
            window_x_start=0.0,
            window_x_end=100.0,
        )

        self.assertEqual(len(placements), 4)
        self.assertEqual(remaining, {0: 0, 1: 2})
        self.assertEqual(next_item_index, {0: 0, 1: 20})
        self.assertTrue(all(placement.row_index == 1 for placement in placements))
        self.assertEqual(stats["top_infill_units_by_product"], {"1": 4})

    def test_top_infill_does_not_evaluate_anchor_with_zero_remaining_quantity(self):
        products = normalize_products(
            [product("Anchor", 50, 50, 50, 1)]
        )
        selected_container = {
            "L": 100.0,
            "W": 100.0,
            "H": 250.0,
            "max_weight": None,
        }
        committed = full_top_support("Anchor")
        remaining = {0: 0}
        next_item_index = {0: 16}
        placements, _, stats = fill_top_residual_deterministically(
            Space(0.0, 0.0, 0.0, 100.0, 100.0, 250.0),
            products[0],
            products,
            remaining,
            next_item_index,
            selected_container,
            0.0,
            False,
            eligible_row_indices={0},
            committed_placements=committed,
            window_x_start=0.0,
            window_x_end=100.0,
        )

        self.assertEqual(placements, [])
        self.assertEqual(remaining, {0: 0})
        self.assertEqual(stats["top_actions"], [])
        self.assertTrue(stats["top_residual_evaluation_reasons"])
        self.assertTrue(
            all(
                reason["anchor_eligible"] is False
                and reason["anchor_eligibility_reason"] == "no_remaining_quantity"
                and reason["anchor_candidate_evaluated"] is False
                for reason in stats["top_residual_evaluation_reasons"]
            )
        )

    def test_top_infill_evaluates_rejected_anchor_and_keeps_other_filler_available(self):
        products = normalize_products(
            [
                product("TooBig", 200, 200, 200, 6),
                product("Filler", 50, 50, 50, 1),
            ]
        )
        selected_container = {
            "L": 100.0,
            "W": 100.0,
            "H": 300.0,
            "max_weight": None,
        }
        committed = [
            Placement(
                "Base",
                0,
                9,
                1,
                0.0,
                True,
                0.0,
                0.0,
                0.0,
                100.0,
                100.0,
                200.0,
            )
        ]
        remaining = {0: 6, 1: 1}
        next_item_index = {0: 0, 1: 0}
        placements, _, stats = fill_top_residual_deterministically(
            Space(0.0, 0.0, 0.0, 100.0, 100.0, 300.0),
            products[0],
            products,
            remaining,
            next_item_index,
            selected_container,
            0.0,
            False,
            eligible_row_indices={0, 1},
            committed_placements=committed,
            window_x_start=0.0,
            window_x_end=100.0,
        )

        self.assertEqual(
            [(placement.product_name, placement.row_index) for placement in placements],
            [("Filler", 1)],
        )
        self.assertEqual(remaining, {0: 6, 1: 0})
        self.assertTrue(
            any(
                reason["anchor_candidate_evaluated"]
                and "TooBig" in reason["eligible_products"]
                and reason["reason"] in {
                    "insufficient_width",
                    "insufficient_x_depth",
                    "insufficient_residual_height",
                    "no_enabled_orientation_fits",
                }
                for reason in stats["top_residual_evaluation_reasons"]
            )
        )

    def test_top_infill_never_stacks_on_non_stackable_support(self):
        products = normalize_products(
            [product("Filler", 50, 50, 50, 4)]
        )
        selected_container = {
            "L": 100.0,
            "W": 100.0,
            "H": 200.0,
            "max_weight": None,
        }
        committed = [
            Placement(
                "Base",
                0,
                9,
                1,
                0.0,
                False,
                0.0,
                0.0,
                0.0,
                100.0,
                100.0,
                100.0,
            )
        ]
        remaining = {0: 4}
        placements, _, stats = fill_top_residual_deterministically(
            Space(0.0, 0.0, 0.0, 100.0, 100.0, 200.0),
            products[0],
            products,
            remaining,
            {0: 0},
            selected_container,
            0.0,
            False,
            eligible_row_indices={0},
            committed_placements=committed,
            window_x_start=0.0,
            window_x_end=100.0,
        )

        self.assertEqual(placements, [])
        self.assertEqual(remaining, {0: 4})
        self.assertEqual(stats["top_support_planes_evaluated"], 0)

    def test_both_mixed_modes_apply_top_closure_after_side_without_baseline_change(self):
        source = [
            product("Anchor", 100, 100, 200, 1),
            product("Filler", 50, 50, 50, 10),
        ]
        selected_container = {
            "L": 150.0,
            "W": 100.0,
            "H": 300.0,
            "max_weight": None,
        }
        for mode in INFILL_MODES:
            with self.subTest(mode=mode):
                result = pack_container(
                    {**selected_container, "packing_mode": mode}, source
                )
                repeat = pack_container(
                    {**selected_container, "packing_mode": mode}, source
                )
                self.assertEqual(geometry_signature(result), geometry_signature(repeat))
                counts = Counter(item.row_index for item in result["placements"])
                self.assertEqual(counts, {0: 1, 1: 10})
                self.assertEqual(result["unplaced"], [])
                self.assertEqual(result[f"{mode}_infill_units_total"], 0)
                self.assertEqual(result[f"{mode}_top_infill_units_total"], 8)
                self.assertEqual(len(result[f"{mode}_top_actions"]), 1)
                self.assertEqual(
                    result[f"{mode}_top_actions"][0]["support_z"],
                    200.0,
                )
                self.assertEqual(
                    result[f"{mode}_top_actions"][0]["filler_product"],
                    "Filler",
                )
                self.assert_physical(result, selected_container)
