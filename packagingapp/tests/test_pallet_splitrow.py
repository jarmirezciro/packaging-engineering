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
            Placement2D(x=5, y=0, l=230, w=170, orientation="LxW"),
            Placement2D(x=235, y=0, l=230, w=170, orientation="LxW"),
            Placement2D(x=465, y=0, l=230, w=170, orientation="LxW"),
            Placement2D(x=695, y=0, l=230, w=170, orientation="LxW"),
            Placement2D(x=925, y=0, l=230, w=170, orientation="LxW"),
            Placement2D(x=5, y=340, l=170, w=230, orientation="WxL"),
            Placement2D(x=175, y=340, l=170, w=230, orientation="WxL"),
            Placement2D(x=345, y=340, l=170, w=230, orientation="WxL"),
        ]

        from packagingapp.utils.palletization.engine import balance_splitrow_sparse_rows

        balanced = balance_splitrow_sparse_rows(placements, 1200, 800)
        self.assertEqual(
            [round(p.x, 6) for p in balanced[:5]],
            [0, 230, 510, 740, 970],
        )
        self._assert_layer_invariants(balanced, 1200, 800)

    def test_non_integer_dimensions_do_not_require_a_dimension_gcd(self):
        base, interlock = get_base_and_interlock_layers(
            "Splitrow", 1234.5, 987.25, 137.3, 83.7
        )
        self.assertEqual(len(base), 98)
        self.assertEqual(len(interlock), 98)
        self._assert_layer_invariants(base, 1234.5, 987.25)
        self._assert_layer_invariants(interlock, 1234.5, 987.25)

    def test_splitrow_tie_keeps_block_capacity_and_first_winner_behavior(self):
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
