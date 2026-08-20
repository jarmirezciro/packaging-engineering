import json

from django.test import SimpleTestCase

from packagingapp.tools.transport.modes import (
    FRONT_TO_BACK_INFILL_MODE,
    FRONT_TO_BACK_MODE,
    SPACE_EVENLY_INFILL_MODE,
    SPACE_EVENLY_MODE,
)
from packagingapp.utils.container_tool.engine import pack_container


def container(mode):
    return {
        "L": 12.0,
        "W": 10.0,
        "H": 5.0,
        "max_weight": None,
        "packing_mode": mode,
    }


def product(name, length, width, height, qty, *, sequence=None):
    row = {
        "name": name,
        "length": float(length),
        "width": float(width),
        "height": float(height),
        "qty": int(qty),
        "weight": 0.0,
        "stackable": True,
        "r1": True,
        "r2": False,
        "r3": False,
    }
    if sequence is not None:
        row["sequence"] = int(sequence)
    return row


def placement_signature(result):
    return tuple(
        (
            placement.product_name,
            placement.row_index,
            placement.item_index,
            placement.sequence,
            placement.x,
            placement.y,
            placement.z,
            placement.l,
            placement.w,
            placement.h,
        )
        for placement in result["placements"]
    )


def sequence_source():
    return [
        product("P1", 4, 6, 5, 2, sequence=1),
        product("P2", 2, 2, 5, 3, sequence=1),
        product("P3", 4, 6, 5, 2, sequence=1),
        product("P4", 2, 2, 5, 3, sequence=1),
    ]


class TransportSequenceSemanticsTests(SimpleTestCase):
    def test_space_evenly_ignores_arbitrary_sequence_values(self):
        baseline_source = sequence_source()
        varied_source = [
            {**row, "sequence": sequence}
            for row, sequence in zip(baseline_source, (8, 2, 4, 9))
        ]

        for mode in (SPACE_EVENLY_MODE, SPACE_EVENLY_INFILL_MODE):
            with self.subTest(mode=mode):
                baseline = pack_container(container(mode), baseline_source)
                varied = pack_container(container(mode), varied_source)

                self.assertEqual(placement_signature(varied), placement_signature(baseline))
                self.assertEqual(varied["unplaced"], baseline["unplaced"])
                self.assertEqual(
                    varied["space_evenly_product_order"],
                    baseline["space_evenly_product_order"],
                )
                self.assertTrue(
                    all(placement.sequence == 1 for placement in varied["placements"])
                )
                self.assertTrue(
                    all(
                        item["sequence"] == 1
                        for item in varied["space_evenly_product_order"]
                    )
                )
                if mode == SPACE_EVENLY_INFILL_MODE:
                    self.assertEqual(varied["space_evenly_infill_sequence_group_count"], 1)
                    self.assertFalse(varied["space_evenly_infill_sequence_restricted"])
                    for key in (
                        "space_evenly_infill_actions",
                        "space_evenly_infill_top_actions",
                        "space_evenly_infill_infill_units_total",
                        "space_evenly_infill_top_infill_units_total",
                        "space_evenly_infill_residual_frontiers_closed",
                    ):
                        self.assertEqual(varied[key], baseline[key], key)

    def test_front_to_back_preserves_explicit_sequence_for_normal_and_infill(self):
        source = [
            product("Large sequence 2", 3, 2, 1, 1, sequence=2),
            product("Small sequence 1", 1, 1, 1, 2, sequence=1),
        ]
        for mode in (FRONT_TO_BACK_MODE, FRONT_TO_BACK_INFILL_MODE):
            with self.subTest(mode=mode):
                result = pack_container(container(mode), source)
                order = result["front_to_back_product_order"]

                self.assertEqual(
                    [(item["row_index"], item["sequence"]) for item in order],
                    [(1, 1), (0, 2)],
                )
                self.assertEqual(
                    [(placement.row_index, placement.sequence) for placement in result["placements"]],
                    [(1, 1), (1, 1), (0, 2)],
                )
                if mode == FRONT_TO_BACK_INFILL_MODE:
                    self.assertEqual(result["front_to_back_infill_sequence_group_count"], 2)
                    self.assertTrue(result["front_to_back_infill_sequence_restricted"])

    def test_front_to_back_missing_sequence_matches_explicit_one(self):
        omitted = [
            product("A", 4, 6, 5, 2),
            product("B", 2, 2, 5, 3),
            product("C", 1, 1, 5, 4),
        ]
        explicit = [{**row, "sequence": 1} for row in omitted]

        for mode in (FRONT_TO_BACK_MODE, FRONT_TO_BACK_INFILL_MODE):
            with self.subTest(mode=mode):
                omitted_result = pack_container(container(mode), omitted)
                explicit_result = pack_container(container(mode), explicit)
                self.assertEqual(
                    placement_signature(omitted_result),
                    placement_signature(explicit_result),
                )
                self.assertEqual(omitted_result["unplaced"], explicit_result["unplaced"])

    def test_front_to_back_non_contiguous_sequences_progress_in_ascending_order(self):
        source = [
            product("Sequence 10", 1, 1, 1, 1, sequence=10),
            product("Sequence 1", 1, 1, 1, 1, sequence=1),
            product("Sequence 5", 1, 1, 1, 1, sequence=5),
        ]
        for mode in (FRONT_TO_BACK_MODE, FRONT_TO_BACK_INFILL_MODE):
            with self.subTest(mode=mode):
                first = pack_container(container(mode), source)
                second = pack_container(container(mode), source)
                self.assertEqual(placement_signature(first), placement_signature(second))
                self.assertEqual(
                    [item["sequence"] for item in first["front_to_back_product_order"]],
                    [1, 5, 10],
                )

    def test_front_to_back_same_sequence_keeps_geometric_priority(self):
        source = [
            product("Sequence 2 small", 1, 3, 1, 1, sequence=2),
            product("Sequence 1", 1, 1, 1, 1, sequence=1),
            product("Sequence 2 large", 2, 2, 1, 1, sequence=2),
        ]
        result = pack_container(container(FRONT_TO_BACK_MODE), source)
        self.assertEqual(
            [item["product_name"] for item in result["front_to_back_product_order"]],
            ["Sequence 1", "Sequence 2 large", "Sequence 2 small"],
        )

    def test_front_to_back_infill_keeps_side_and_top_cooperation_within_sequence(self):
        source = [
            product("P1", 4, 6, 5, 2, sequence=1),
            product("P2", 2, 2, 5, 3, sequence=1),
            product("P3", 4, 6, 5, 2, sequence=2),
            product("P4", 2, 2, 5, 3, sequence=2),
        ]
        result = pack_container(container(FRONT_TO_BACK_INFILL_MODE), source)
        for action in result["front_to_back_infill_actions"]:
            anchor = next(
                row for row in source if row["name"] == action["anchor_product"]
            )
            filler = next(
                row for row in source if row["name"] == action["filler_product"]
            )
            self.assertEqual(anchor["sequence"], filler["sequence"])

        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key.startswith("front_to_back_infill_")
            }
        )
