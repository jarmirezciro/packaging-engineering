from unittest.mock import patch

from django.test import SimpleTestCase

from packagingapp.utils.palletization.engine import (
    Placement2D,
    get_base_and_interlock_layers,
    pattern_block,
    pattern_splitrow,
    placements_are_valid,
    rect_overlap_area,
    run_palletization_analysis,
)


class SplitrowEngineTests(SimpleTestCase):
    TOPS_AREA = (1244, 1041)
    TOPS_BOX = (411, 289)

    @staticmethod
    def _signature(layer):
        return [
            (round(p.x, 6), round(p.y, 6), round(p.l, 6), round(p.w, 6), p.orientation)
            for p in layer
        ]

    @staticmethod
    def _assert_layer_invariants(layer, area_l, area_w):
        assert placements_are_valid(layer, area_l, area_w)
        for placement in layer:
            assert placement.x >= -1e-9
            assert placement.y >= -1e-9
            assert placement.x + placement.l <= area_l + 1e-9
            assert placement.y + placement.w <= area_w + 1e-9
        for index, first in enumerate(layer):
            for second in layer[index + 1:]:
                assert rect_overlap_area(first, second) <= 1e-9

    def test_tops_splitrow_keeps_ten_boxes_per_layer_and_interlock(self):
        rows = run_palletization_analysis(
            box_l=411,
            box_w=289,
            box_h=231,
            pallet_l=1219,
            pallet_w=1016,
            pallet_height=101,
            max_stack_height=1346,
            max_width_stickout=25,
            max_length_stickout=25,
        )

        splitrow = next(row for row in rows if row["pattern"] == "Splitrow")
        self.assertEqual(splitrow["stacking"], "column")
        self.assertEqual(splitrow["boxes_layer_A"], 10)
        self.assertEqual(splitrow["total_boxes"], 50)
        self.assertTrue(splitrow["interlock_possible"])

    def test_reference_na4840_case_builds_side_splitrow_alternative(self):
        rows = run_palletization_analysis(
            box_l=308,
            box_w=147,
            box_h=193,
            pallet_l=1219,
            pallet_w=1016,
            pallet_height=141,
            max_stack_height=1346,
        )

        splitrow = next(row for row in rows if row["pattern"] == "Splitrow")
        self.assertEqual(splitrow["total_boxes"], 144)

        layer = pattern_splitrow(1219, 1016, 308, 147)
        orientation_counts = {
            (147, 308): sum(1 for placement in layer if (placement.l, placement.w) == (147, 308)),
            (308, 147): sum(1 for placement in layer if (placement.l, placement.w) == (308, 147)),
        }
        self.assertEqual(orientation_counts, {(147, 308): 18, (308, 147): 6})
        self._assert_layer_invariants(layer, 1219, 1016)

        balanced_base, _ = get_base_and_interlock_layers(
            "Splitrow", 1219, 1016, 308, 147
        )
        filler_y = sorted(
            round(placement.y, 6)
            for placement in balanced_base
            if (placement.l, placement.w) == (308, 147)
        )
        main_max_x = max(
            placement.x + placement.l
            for placement in balanced_base
            if (placement.l, placement.w) == (147, 308)
        )
        filler_x = {
            round(placement.x, 6)
            for placement in balanced_base
            if (placement.l, placement.w) == (308, 147)
        }
        self.assertEqual(filler_x, {round(main_max_x, 6)})
        self.assertEqual(filler_y, [46, 193, 340, 529, 676, 823])

    def test_na4840_splitrow_keeps_filler_row_compact(self):
        base, interlock = get_base_and_interlock_layers(
            "Splitrow", 1219, 1016, 284, 160
        )

        self.assertEqual(len(base), 25)
        self.assertEqual(len(interlock), 25)
        self._assert_layer_invariants(base, 1219, 1016)

        filler = sorted(
            (placement for placement in base if placement.orientation == "LxW"),
            key=lambda placement: placement.x,
        )
        self.assertEqual(len(filler), 4)
        self.assertTrue(
            all(
                abs(next_box.x - (box.x + box.l)) <= 1e-6
                for box, next_box in zip(filler, filler[1:])
            )
        )

        main_rows = {}
        for placement in base:
            if placement.orientation == "WxL":
                main_rows.setdefault(round(placement.y, 6), []).append(placement)
        self.assertEqual(len(main_rows), 3)
        for row in main_rows.values():
            row.sort(key=lambda placement: placement.x)
            self.assertTrue(
                all(
                    abs(next_box.x - (box.x + box.l)) <= 1e-6
                    for box, next_box in zip(row, row[1:])
                )
            )

    def test_swapped_splitrow_is_deterministic_and_valid(self):
        for swapped in (False, True):
            first = pattern_splitrow(1200, 800, 230, 170, swapped=swapped)
            second = pattern_splitrow(1200, 800, 230, 170, swapped=swapped)
            self.assertEqual(self._signature(first), self._signature(second))
            self.assertEqual(len(first), 24)
            self._assert_layer_invariants(first, 1200, 800)

            base, interlock = get_base_and_interlock_layers(
                "Splitrow", 1200, 800, 230, 170
            )
            self._assert_layer_invariants(base, 1200, 800)
            self._assert_layer_invariants(interlock, 1200, 800)

    def test_sparse_rows_use_direct_opposite_edge_positions(self):
        placements = [
            # The minority row is the filler band. It must be split against
            # the edges of the fixed main arrangement, not the pallet edges.
            Placement2D(x=5, y=0, l=170, w=230, orientation="LxW"),
            Placement2D(x=175, y=0, l=170, w=230, orientation="LxW"),
            Placement2D(x=345, y=0, l=170, w=230, orientation="LxW"),
            Placement2D(x=515, y=0, l=170, w=230, orientation="LxW"),
            Placement2D(x=5, y=300, l=230, w=170, orientation="WxL"),
            Placement2D(x=235, y=300, l=230, w=170, orientation="WxL"),
            Placement2D(x=465, y=300, l=230, w=170, orientation="WxL"),
            Placement2D(x=695, y=300, l=230, w=170, orientation="WxL"),
            Placement2D(x=925, y=300, l=230, w=170, orientation="WxL"),
        ]

        from packagingapp.utils.palletization.engine import balance_splitrow_sparse_rows

        balanced = balance_splitrow_sparse_rows(placements, 1200, 800)
        self.assertEqual(
            [round(p.x, 6) for p in balanced[:4]],
            [5, 175, 815, 985],
        )
        self.assertEqual(
            [round(p.x, 6) for p in balanced[4:]],
            [5, 235, 465, 695, 925],
        )
        self._assert_layer_invariants(balanced, 1200, 800)

    def test_non_integer_dimensions_do_not_require_a_dimension_gcd(self):
        base, interlock = get_base_and_interlock_layers(
            "Splitrow", 1234.5, 987.25, 137.3, 83.7
        )
        self.assertEqual(len(base), 102)
        self.assertEqual(len(interlock), 102)
        self._assert_layer_invariants(base, 1234.5, 987.25)
        self._assert_layer_invariants(interlock, 1234.5, 987.25)

    def test_splitrow_tie_keeps_block_capacity_and_deterministic_mixed_choice(self):
        splitrow = pattern_splitrow(500, 400, 120, 80)
        block = pattern_block(500, 400, 120, 80)
        self.assertEqual(len(splitrow), len(block))
        self.assertEqual(self._signature(splitrow), self._signature(pattern_splitrow(500, 400, 120, 80)))

    def test_arithmetic_row_selection_materializes_only_winning_candidates(self):
        original_grid_fill = __import__(
            "packagingapp.utils.palletization.engine",
            fromlist=["grid_fill"],
        ).grid_fill
        with patch(
            "packagingapp.utils.palletization.engine.grid_fill",
            wraps=original_grid_fill,
        ) as grid_fill:
            result = pattern_splitrow(1244, 1041, 411, 289)

        self.assertEqual(len(result), 10)
        # Two calls materialize the selected Splitrow bands and two calls build
        # the unchanged Block fallback comparison.
        self.assertLessEqual(grid_fill.call_count, 4)

    def test_splitrow_does_not_call_generic_filler_position_search(self):
        with patch(
            "packagingapp.utils.palletization.engine._candidate_positions_for_filler",
            side_effect=AssertionError("generic filler search must not run"),
        ), patch(
            "packagingapp.utils.palletization.engine.prefer_edge_balanced_filler_layer",
            side_effect=AssertionError("generic filler balancer must not run"),
        ), patch(
            "packagingapp.utils.palletization.engine.prefer_edge_balanced_sparse_filler_lines",
            side_effect=AssertionError("generic sparse balancer must not run"),
        ):
            base, interlock = get_base_and_interlock_layers(
                "Splitrow", 1244, 1041, 411, 289
            )

        self.assertEqual(len(base), 10)
        self.assertEqual(len(interlock), 10)
