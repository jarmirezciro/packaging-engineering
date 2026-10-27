import hashlib

from django.test import SimpleTestCase

from packagingapp.tests.transport_physical_validator import (
    assert_transport_result_physical,
)
from packagingapp.tools.transport.modes import TRANSPORT_PACKING_MODE_OPTIONS
from packagingapp.utils.container_tool.engine import (
    MonoFloorLane,
    TOLERANCE,
    _mono_transition_candidate,
    _validate_frontier_geometry,
    normalize_products,
    pack_container,
)


ACTIVE_MODES = tuple(option["value"] for option in TRANSPORT_PACKING_MODE_OPTIONS)
PALLET_CONTAINER = {
    "L": 12032.0,
    "W": 2352.0,
    "H": 2698.0,
    "max_weight": None,
}


def product(
    *,
    name="Rectangle",
    length=1200.0,
    width=800.0,
    height=144.0,
    qty=30,
    weight=1.0,
    stackable=False,
    sequence=1,
    r1=True,
    r2=False,
    r3=False,
):
    return {
        "name": name,
        "length": length,
        "width": width,
        "height": height,
        "qty": qty,
        "weight": weight,
        "stackable": stackable,
        "sequence": sequence,
        "r1": r1,
        "r2": r2,
        "r3": r3,
    }


def packed_signature(result, scale=1.0):
    coordinates = [
        (
            placement.row_index,
            round(placement.x / scale, 7),
            round(placement.y / scale, 7),
            round(placement.z / scale, 7),
            round(placement.l / scale, 7),
            round(placement.w / scale, 7),
            round(placement.h / scale, 7),
        )
        for placement in result["placements"]
    ]
    return hashlib.sha256(repr(coordinates).encode()).hexdigest()


def rectangles_overlap(first, second):
    return (
        min(first[0] + first[2], second[0] + second[2])
        > max(first[0], second[0]) + TOLERANCE
        and min(first[1] + first[3], second[1] + second[3])
        > max(first[1], second[1]) + TOLERANCE
    )


class MonoLaneTransitionOracleTests(SimpleTestCase):
    def test_independent_twenty_four_rectangle_witness_and_upper_bound(self):
        container_length = PALLET_CONTAINER["L"]
        container_width = PALLET_CONTAINER["W"]

        for increase in (5, 10, 15, 20, 25, 30):
            with self.subTest(increase=increase):
                long_side = 1200 + increase
                short_side = 800 + increase
                rectangles = []
                for index in range(7):
                    rectangles.append(
                        (index * short_side, 0, short_side, long_side)
                    )
                for index in range(5):
                    rectangles.append(
                        (index * long_side, long_side, long_side, short_side)
                    )
                for index in range(5):
                    rectangles.append(
                        (
                            container_length - 5 * long_side + index * long_side,
                            0,
                            long_side,
                            short_side,
                        )
                    )
                for index in range(7):
                    rectangles.append(
                        (
                            5 * long_side + index * short_side,
                            short_side,
                            short_side,
                            long_side,
                        )
                    )

                self.assertEqual(len(rectangles), 24)
                for rectangle in rectangles:
                    x, y, length, width = rectangle
                    self.assertGreaterEqual(x, 0)
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(x + length, container_length + TOLERANCE)
                    self.assertLessEqual(y + width, container_width + TOLERANCE)
                for index, first in enumerate(rectangles):
                    self.assertFalse(
                        any(
                            rectangles_overlap(first, second)
                            for second in rectangles[index + 1 :]
                        )
                    )

                self.assertLessEqual(long_side + short_side, container_width)
                self.assertGreater(2 * long_side, container_width)
                maximum_short_x = int(container_length // short_side)
                self.assertLessEqual(maximum_short_x, 14)
                self.assertGreater(
                    maximum_short_x * short_side
                    + (25 - maximum_short_x) * long_side,
                    2 * container_length,
                )

    def test_independent_twenty_four_impossibility_for_larger_increases(self):
        container_length = PALLET_CONTAINER["L"]
        container_width = PALLET_CONTAINER["W"]
        for increase in (40, 50, 60):
            with self.subTest(increase=increase):
                long_side = 1200 + increase
                short_side = 800 + increase
                self.assertGreater(2 * long_side, container_width)
                maximum_short_x = int(container_length // short_side)
                self.assertGreater(
                    maximum_short_x * short_side
                    + (24 - maximum_short_x) * long_side,
                    2 * container_length,
                )


class MonoLaneTransitionEngineTests(SimpleTestCase):
    def run_case(
        self,
        container,
        rows,
        mode,
        *,
        max_lane_transitions=1,
        candidate_budget=4096,
    ):
        configured = {**container, "packing_mode": mode}
        result = pack_container(
            configured,
            rows,
            max_lane_transitions=max_lane_transitions,
            mono_transition_candidate_budget=candidate_budget,
        )
        assert_transport_result_physical(self, result, configured, rows)
        return result

    def test_overhang_total_dimension_increase_matrix_in_every_mode(self):
        expected_by_increase = {0: 25, 5: 24, 10: 24, 15: 24, 20: 24, 25: 24, 30: 24}
        for increase, expected in expected_by_increase.items():
            row = product(length=1200 + increase, width=800 + increase)
            for mode in ACTIVE_MODES:
                with self.subTest(increase=increase, mode=mode):
                    result = self.run_case(PALLET_CONTAINER, [row], mode)
                    self.assertEqual(len(result["placements"]), expected)
                    if increase:
                        self.assertTrue(result["mono_lane_transition"]["selected"])
                        self.assertEqual(
                            result["mono_lane_transition"]["realized_transitions"],
                            1,
                        )

    def test_per_side_overhang_equivalents_reach_twenty_three(self):
        for total_increase in (40, 50, 60):
            row = product(
                length=1200 + total_increase,
                width=800 + total_increase,
            )
            for mode in ACTIVE_MODES:
                with self.subTest(total_increase=total_increase, mode=mode):
                    result = self.run_case(PALLET_CONTAINER, [row], mode)
                    self.assertEqual(len(result["placements"]), 23)

    def test_transition_budget_zero_preserves_baseline_and_one_is_monotonic(self):
        row = product(length=1210, width=810)
        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                baseline = self.run_case(
                    PALLET_CONTAINER,
                    [row],
                    mode,
                    max_lane_transitions=0,
                )
                enhanced = self.run_case(PALLET_CONTAINER, [row], mode)
                self.assertEqual(len(baseline["placements"]), 23)
                self.assertEqual(len(enhanced["placements"]), 24)
                self.assertGreaterEqual(
                    len(enhanced["placements"]),
                    len(baseline["placements"]),
                )

    def test_quantity_sweeps_never_overpack_or_skip_available_units(self):
        for increase, capacity in ((0, 25), (10, 24)):
            for quantity in (1, 2, 3, 4, 5, 6, 7, 17, 23, 24, 25, 26, 30):
                row = product(
                    length=1200 + increase,
                    width=800 + increase,
                    qty=quantity,
                )
                for mode in ACTIVE_MODES:
                    with self.subTest(
                        increase=increase,
                        quantity=quantity,
                        mode=mode,
                    ):
                        result = self.run_case(PALLET_CONTAINER, [row], mode)
                        self.assertEqual(
                            len(result["placements"]),
                            min(quantity, capacity),
                        )
                        if increase == 0 and quantity == 3:
                            self.assertLessEqual(
                                max(
                                    placement.x + placement.l
                                    for placement in result["placements"]
                                ),
                                1600 + TOLERANCE,
                            )

    def test_existing_801_and_802_adaptive_results_remain_twenty_five(self):
        for width in (801, 802):
            row = product(length=1200, width=width)
            for mode in ACTIVE_MODES:
                with self.subTest(width=width, mode=mode):
                    result = self.run_case(PALLET_CONTAINER, [row], mode)
                    self.assertEqual(len(result["placements"]), 25)

    def test_effective_one_layer_stackable_matches_nonstackable(self):
        for stackable in (False, True):
            row = product(
                length=1210,
                width=810,
                height=1500,
                stackable=stackable,
            )
            for mode in ACTIVE_MODES:
                with self.subTest(stackable=stackable, mode=mode):
                    result = self.run_case(PALLET_CONTAINER, [row], mode)
                    self.assertEqual(len(result["placements"]), 24)

    def test_supported_two_layer_transition_reaches_forty_eight(self):
        row = product(
            name="Tall stackable rectangle",
            length=1205,
            width=805,
            height=1341,
            qty=60,
            stackable=True,
        )
        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                baseline = self.run_case(
                    PALLET_CONTAINER,
                    [row],
                    mode,
                    max_lane_transitions=0,
                )
                enhanced = self.run_case(PALLET_CONTAINER, [row], mode)
                self.assertEqual(len(baseline["placements"]), 38)
                self.assertEqual(len(enhanced["placements"]), 48)
                self.assertTrue(enhanced["mono_lane_transition"]["selected"])
                self.assertEqual(
                    enhanced["mono_lane_transition"]["floor_quantity"],
                    24,
                )
                self.assertTrue(
                    any(placement.z > TOLERANCE for placement in enhanced["placements"])
                )

    def test_per_lane_blockers_compact_the_four_lane_coordinate_witness(self):
        row = product(
            name="Witness rectangle",
            length=1205,
            width=805,
            height=1341,
            qty=48,
            stackable=True,
        )
        normalized = normalize_products([row])[0]
        left = (
            MonoFloorLane(1, normalized.orientations[1], 0.0),
            MonoFloorLane(0, normalized.orientations[0], 1205.0),
        )
        right = (
            MonoFloorLane(0, normalized.orientations[0], 0.0),
            MonoFloorLane(1, normalized.orientations[1], 805.0),
        )
        candidate = _mono_transition_candidate(
            normalized,
            PALLET_CONTAINER,
            left,
            right,
            10845.0,
            48,
        )
        self.assertIsNotNone(candidate)
        self.assertTrue(
            _validate_frontier_geometry(
                list(candidate.placements),
                PALLET_CONTAINER,
            )[0]
        )
        right_lanes = [
            lane for lane in candidate.lane_metadata if lane["side"] == "right"
        ]
        self.assertEqual(
            [lane["x_start"] for lane in right_lanes],
            [10465.0, 10845.0],
        )
        self.assertEqual(candidate.floor_quantity, 24)
        self.assertLessEqual(candidate.occupied_length, 11670.0 + TOLERANCE)

    def test_true_multi_layer_baseline_remains_stronger(self):
        container = {"L": 2400, "W": 1200, "H": 1000, "max_weight": None}
        row = product(
            name="Stackable carton",
            length=600,
            width=400,
            height=300,
            qty=50,
            stackable=True,
        )
        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                baseline = self.run_case(
                    container,
                    [row],
                    mode,
                    max_lane_transitions=0,
                )
                enhanced = self.run_case(container, [row], mode)
                self.assertEqual(len(enhanced["placements"]), 36)
                self.assertEqual(
                    packed_signature(enhanced),
                    packed_signature(baseline),
                )

    def test_general_rectangular_families_are_valid_and_non_degrading(self):
        families = (
            ("Small cartons", 2400, 1200, 600, 400, 12),
            ("Reusable crates", 3500, 1500, 700, 500, 15),
            ("Asymmetric transport cases", 4100, 1730, 730, 470, 18),
            ("Machinery bases", 6000, 1250, 1450, 260, 16),
            ("Nearly square cartons", 3010, 2010, 505, 495, 23),
            ("Fractional trays", 3100.5, 1610.25, 617.5, 383.25, 20),
        )
        for name, length, width, item_l, item_w, baseline_count in families:
            container = {
                "L": length,
                "W": width,
                "H": 200,
                "max_weight": None,
            }
            row = product(
                name=name,
                length=item_l,
                width=item_w,
                height=200,
                qty=100,
            )
            for mode in ACTIVE_MODES:
                with self.subTest(name=name, mode=mode):
                    baseline = self.run_case(
                        container,
                        [row],
                        mode,
                        max_lane_transitions=0,
                    )
                    enhanced = self.run_case(container, [row], mode)
                    self.assertEqual(len(baseline["placements"]), baseline_count)
                    self.assertGreaterEqual(
                        len(enhanced["placements"]),
                        baseline_count,
                    )
                    if name in {"Small cartons", "Reusable crates"}:
                        area_upper_bound = int(
                            (length * width) // (item_l * item_w)
                        )
                        self.assertEqual(area_upper_bound, baseline_count)
                        self.assertEqual(
                            len(enhanced["placements"]),
                            area_upper_bound,
                        )

    def test_non_pallet_quantity_sweeps_respect_requested_quantity(self):
        fixtures = (
            (
                {"L": 2400, "W": 1200, "H": 400, "max_weight": None},
                product(length=600, width=400, height=400, qty=1),
                12,
            ),
            (
                {"L": 4100, "W": 1730, "H": 350, "max_weight": None},
                product(length=730, width=470, height=350, qty=1),
                19,
            ),
        )
        for container, row, known_capacity in fixtures:
            for quantity in (1, 2, 3, 4, 5, 7, 11, 17, 50):
                configured_row = {**row, "qty": quantity}
                with self.subTest(
                    footprint=(row["length"], row["width"]),
                    quantity=quantity,
                ):
                    result = self.run_case(
                        container,
                        [configured_row],
                        "front_to_back",
                    )
                    self.assertEqual(
                        len(result["placements"]),
                        min(quantity, known_capacity),
                    )

    def test_rotation_groups_never_create_unpermitted_orientations(self):
        container = {"L": 2100, "W": 1200, "H": 800, "max_weight": None}
        for flags in (
            {"r1": True, "r2": False, "r3": False},
            {"r1": False, "r2": True, "r3": False},
            {"r1": False, "r2": False, "r3": True},
            {"r1": True, "r2": True, "r3": True},
        ):
            row = product(
                length=700,
                width=400,
                height=300,
                qty=30,
                **flags,
            )
            with self.subTest(flags=flags):
                result = self.run_case(container, [row], "front_to_back")
                self.assertTrue(result["placements"])

    def test_zero_quantity_rows_are_ignored_but_positive_rows_are_not_merged(self):
        positive = product(name="Positive", length=1210, width=810, qty=30)
        zero = product(name="Zero", length=333, width=222, qty=0)
        identical = product(name="Distinct row", length=1210, width=810, qty=1)
        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode, case="zero-row"):
                mono = self.run_case(PALLET_CONTAINER, [zero, positive], mode)
                self.assertEqual(len(mono["placements"]), 24)
                self.assertTrue(mono["mono_lane_transition"]["selected"])
            with self.subTest(mode=mode, case="two-positive-rows"):
                disabled = self.run_case(
                    PALLET_CONTAINER,
                    [positive, identical],
                    mode,
                    max_lane_transitions=0,
                )
                enabled = self.run_case(
                    PALLET_CONTAINER,
                    [positive, identical],
                    mode,
                )
                self.assertNotIn("mono_lane_transition", enabled)
                self.assertEqual(
                    packed_signature(enabled),
                    packed_signature(disabled),
                )

    def test_narrow_short_inputs_are_deterministic_and_transition_limit_is_explicit(self):
        container = {"L": 900, "W": 600, "H": 500, "max_weight": None}
        row = product(length=400, width=350, height=500, qty=20)
        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                first = self.run_case(container, [row], mode)
                second = self.run_case(container, [row], mode)
                self.assertEqual(packed_signature(first), packed_signature(second))
        with self.assertRaisesRegex(ValueError, "only 0 or 1"):
            pack_container(
                {**container, "packing_mode": "front_to_back"},
                [row],
                max_lane_transitions=2,
            )

    def test_scaling_and_input_axis_metamorphics(self):
        normalized_signatures = []
        for scale in (0.5, 1.0, 2.0):
            container = {
                key: value * scale if key in {"L", "W", "H"} else value
                for key, value in PALLET_CONTAINER.items()
            }
            row = product(
                length=1210 * scale,
                width=810 * scale,
                height=144 * scale,
            )
            result = self.run_case(container, [row], "front_to_back")
            self.assertEqual(len(result["placements"]), 24)
            normalized_signatures.append(packed_signature(result, scale=scale))
        self.assertEqual(len(set(normalized_signatures)), 1)

        original = self.run_case(
            PALLET_CONTAINER,
            [product(length=1210, width=810)],
            "front_to_back",
        )
        swapped = self.run_case(
            PALLET_CONTAINER,
            [product(length=810, width=1210)],
            "front_to_back",
        )
        self.assertEqual(len(original["placements"]), len(swapped["placements"]))

        rotated_container = {
            **PALLET_CONTAINER,
            "L": PALLET_CONTAINER["W"],
            "W": PALLET_CONTAINER["L"],
        }
        rotated = self.run_case(
            rotated_container,
            [product(length=810, width=1210)],
            "front_to_back",
        )
        self.assertEqual(len(original["placements"]), len(rotated["placements"]))

    def test_single_row_regression_improves_and_mixed_rows_are_unchanged(self):
        container = {"L": 1800, "W": 2352, "H": 2698, "max_weight": None}
        row = product(length=260, width=1200, qty=26)
        baseline = self.run_case(
            container,
            [row],
            "space_evenly",
            max_lane_transitions=0,
        )
        enhanced = self.run_case(container, [row], "space_evenly")
        self.assertEqual(len(baseline["placements"]), 10)
        self.assertGreaterEqual(len(enhanced["placements"]), 11)

        mixed_rows = [
            product(name="First", length=400, width=801, height=250, qty=17),
            product(name="Second", length=260, width=600, height=500, qty=17),
        ]
        mixed_container = {
            "L": 4800,
            "W": 1800,
            "H": 2698,
            "max_weight": None,
        }
        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                disabled = self.run_case(
                    mixed_container,
                    mixed_rows,
                    mode,
                    max_lane_transitions=0,
                )
                enabled = self.run_case(mixed_container, mixed_rows, mode)
                self.assertEqual(
                    packed_signature(enabled),
                    packed_signature(disabled),
                )

    def test_payload_rotation_controls_and_search_cap_fallback(self):
        payload_container = {**PALLET_CONTAINER, "max_weight": 10}
        payload_row = product(length=1210, width=810, qty=30, weight=2)
        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                result = self.run_case(payload_container, [payload_row], mode)
                self.assertEqual(len(result["placements"]), 5)

        no_rotation = product(r1=False, r2=False, r3=False)
        result = self.run_case(
            PALLET_CONTAINER,
            [no_rotation],
            "front_to_back",
        )
        self.assertEqual(result["placements"], [])

        small_container = {"L": 10000, "W": 1000, "H": 100, "max_weight": None}
        small_row = product(
            name="Tiny units",
            length=10,
            width=5,
            height=100,
            qty=5000,
        )
        baseline = self.run_case(
            small_container,
            [small_row],
            "front_to_back",
            max_lane_transitions=0,
        )
        enhanced = self.run_case(
            small_container,
            [small_row],
            "front_to_back",
            candidate_budget=8,
        )
        self.assertEqual(len(enhanced["placements"]), len(baseline["placements"]))
        self.assertEqual(packed_signature(enhanced), packed_signature(baseline))
        diagnostics = enhanced["mono_lane_transition"]
        self.assertLessEqual(diagnostics["configuration_count"], 128)
        self.assertEqual(diagnostics["candidate_count"], 0)
        self.assertEqual(diagnostics["placement_cap"], 512)
