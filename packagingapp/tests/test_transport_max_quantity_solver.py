from unittest.mock import patch

from django.test import SimpleTestCase

from packagingapp.tools.transport.modes import TRANSPORT_PACKING_MODE_OPTIONS
from packagingapp.tools.transport.service import (
    _resolve_auto_max_quantities,
    analyze_transport_capacity,
)


ACTIVE_MODES = tuple(option["value"] for option in TRANSPORT_PACKING_MODE_OPTIONS)


def config(*, mode="front_to_back", length=12000, width=2000, height=2698, max_weight=None):
    return {
        "container_source": "manual",
        "packing_mode": mode,
        "container_l": length,
        "container_w": width,
        "container_h": height,
        "max_weight": max_weight,
        "tare_weight": None,
    }


def product(
    name,
    *,
    length,
    width,
    height,
    qty=1,
    max_qty=False,
    stackable=True,
    weight=0,
    sequence=1,
):
    return {
        "name": name,
        "length": length,
        "width": width,
        "height": height,
        "qty": qty,
        "max_qty": max_qty,
        "stackable": stackable,
        "weight": weight,
        "sequence": sequence,
        "r1": True,
        "r2": False,
        "r3": False,
    }


class TransportMaxQuantitySolverTests(SimpleTestCase):
    def test_solver_uses_the_greatest_feasible_quantity_without_monotonicity(self):
        container = {
            "L": 7,
            "W": 1,
            "H": 1,
            "max_weight": None,
            "packing_mode": "front_to_back",
        }
        row = product(
            "Synthetic discontinuity",
            length=1,
            width=1,
            height=1,
            max_qty=True,
        )
        evaluated = []

        def non_monotonic_feasibility(_container, trial, _required):
            quantity = trial[0]["qty"]
            evaluated.append(quantity)
            return quantity <= 4 or quantity == 6

        with patch(
            "packagingapp.tools.transport.service._can_pack_requested_quantities",
            side_effect=non_monotonic_feasibility,
        ):
            resolved, messages = _resolve_auto_max_quantities(container, [row])

        self.assertEqual(messages, [])
        self.assertEqual(resolved[0]["qty"], 6)
        self.assertEqual(evaluated, [7, 6])

    def test_solver_crosses_non_monotonic_synchronized_block_gap_in_every_mode(self):
        row = product(
            "EUR pallet",
            length=1200,
            width=800,
            height=1200,
            max_qty=True,
        )

        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                analysis = analyze_transport_capacity(config(mode=mode), [row])

                self.assertTrue(analysis["ok"], analysis["messages"])
                self.assertEqual(analysis["safe_rows"][0]["qty"], 50)
                self.assertEqual(len(analysis["result"]["placements"]), 50)
                self.assertEqual(analysis["result"]["unplaced"], [])

    def test_solver_finds_later_capacity_after_a_larger_non_monotonic_gap(self):
        analysis = analyze_transport_capacity(
            config(length=12032, width=2352, height=2698),
            [
                product(
                    "Low EUR pallet",
                    length=1200,
                    width=800,
                    height=144,
                    max_qty=True,
                )
            ],
        )

        self.assertTrue(analysis["ok"], analysis["messages"])
        self.assertEqual(analysis["safe_rows"][0]["qty"], 450)
        self.assertEqual(len(analysis["result"]["placements"]), 450)
        self.assertEqual(analysis["result"]["unplaced"], [])

    def test_solver_uses_supported_lane_transition_for_tall_stackable_row(self):
        row = product(
            "Tall stackable rectangle",
            length=1205,
            width=805,
            height=1341,
            max_qty=True,
        )
        for mode in ACTIVE_MODES:
            with self.subTest(mode=mode):
                analysis = analyze_transport_capacity(
                    config(
                        mode=mode,
                        length=12032,
                        width=2352,
                        height=2698,
                    ),
                    [row],
                )
                self.assertTrue(analysis["ok"], analysis["messages"])
                self.assertEqual(analysis["safe_rows"][0]["qty"], 48)
                self.assertEqual(len(analysis["result"]["placements"]), 48)
                self.assertEqual(analysis["result"]["unplaced"], [])

    def test_solver_reserves_fixed_rows_and_payload(self):
        analysis = analyze_transport_capacity(
            config(length=10, width=1, height=1, max_weight=35),
            [
                product(
                    "Fixed",
                    length=1,
                    width=1,
                    height=1,
                    qty=1,
                    weight=5,
                ),
                product(
                    "Automatic",
                    length=1,
                    width=1,
                    height=1,
                    max_qty=True,
                    weight=10,
                ),
            ],
        )

        self.assertTrue(analysis["ok"], analysis["messages"])
        self.assertEqual([row["qty"] for row in analysis["safe_rows"]], [1, 3])
        self.assertEqual(len(analysis["result"]["placements"]), 4)

    def test_multiple_max_rows_remain_row_ordered(self):
        analysis = analyze_transport_capacity(
            config(length=4, width=2, height=1),
            [
                product("First", length=1, width=1, height=1, max_qty=True),
                product("Second", length=1, width=1, height=1, max_qty=True),
            ],
        )

        self.assertTrue(analysis["ok"], analysis["messages"])
        self.assertEqual([row["qty"] for row in analysis["safe_rows"]], [7, 1])
        self.assertEqual(len(analysis["result"]["placements"]), 8)
        self.assertEqual(analysis["result"]["unplaced"], [])
