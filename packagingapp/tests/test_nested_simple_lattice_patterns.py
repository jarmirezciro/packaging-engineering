from django.test import SimpleTestCase

from packagingapp.utils.box_selection.engine import compare_packing_candidates
from packagingapp.utils.box_selection.mosaic import search_mosaic_placements
from packagingapp.utils.packing_patterns import enumerate_pattern_candidates
from packagingapp.utils.packing_patterns import patterns as shared_patterns
from packagingapp.utils.packing_patterns.validation import validate_placements
from packagingapp.utils.palletization import engine as pallet_engine


class NestedSimpleLatticeGeometryTests(SimpleTestCase):
    box_l = 82.0
    box_w = 70.0

    def assert_lattice(self, family, i, j, area_l=None, area_w=None, **kwargs):
        area_l = area_l or i * self.box_l + j * self.box_w
        area_w = area_w or i * self.box_w + j * self.box_l
        constructor = getattr(shared_patterns, family)
        first = constructor(
            area_l,
            area_w,
            self.box_l,
            self.box_w,
            i=i,
            j=j,
            **kwargs,
        )
        second = constructor(
            area_l,
            area_w,
            self.box_l,
            self.box_w,
            i=i,
            j=j,
            **kwargs,
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first), (i + j) ** 2)
        self.assertTrue(
            validate_placements(
                first,
                area_l,
                area_w,
                expected_footprint=(self.box_l, self.box_w),
            ).valid
        )
        min_x = min(item.x for item in first)
        min_y = min(item.y for item in first)
        max_x = max(item.x + item.l for item in first)
        max_y = max(item.y + item.w for item in first)
        expected_l = i * self.box_l + j * self.box_w
        expected_w = i * self.box_w + j * self.box_l
        if kwargs.get("rotated"):
            expected_l, expected_w = expected_w, expected_l
        self.assertAlmostEqual(max_x - min_x, expected_l)
        self.assertAlmostEqual(max_y - min_y, expected_w)
        self.assertAlmostEqual(
            area_l * area_w - sum(item.l * item.w for item in first),
            i * j * (self.box_l - self.box_w) ** 2,
        )
        self.assertEqual(
            {item.orientation for item in first},
            {"LxW", "WxL"},
        )
        return first

    def test_1d_representative_lattice_sizes(self):
        for j in range(2, 7):
            with self.subTest(j=j):
                self.assert_lattice("pattern_nested_simple_lattice_1d", 1, j)

    def test_2d_representative_and_published_asymmetric_lattices(self):
        for i, j in ((2, 2), (2, 3), (3, 3), (3, 4), (5, 3)):
            with self.subTest(i=i, j=j):
                self.assert_lattice("pattern_nested_simple_lattice_2d", i, j)

    def test_representative_placement_signatures_are_stable(self):
        def signature(layer):
            return tuple(
                (
                    round(item.x, 6),
                    round(item.y, 6),
                    round(item.l, 6),
                    round(item.w, 6),
                    item.orientation,
                )
                for item in sorted(layer, key=lambda value: (value.x, value.y, value.l, value.w))
            )

        self.assertEqual(
            signature(
                shared_patterns.pattern_nested_simple_lattice_1d(
                    222.0, 234.0, 82.0, 70.0, i=1, j=2
                )
            ),
            (
                (0.0, 0.0, 82.0, 70.0, "LxW"),
                (0.0, 70.0, 70.0, 82.0, "WxL"),
                (0.0, 152.0, 70.0, 82.0, "WxL"),
                (70.0, 82.0, 82.0, 70.0, "LxW"),
                (70.0, 152.0, 70.0, 82.0, "WxL"),
                (82.0, 0.0, 70.0, 82.0, "WxL"),
                (140.0, 164.0, 82.0, 70.0, "LxW"),
                (152.0, 0.0, 70.0, 82.0, "WxL"),
                (152.0, 82.0, 70.0, 82.0, "WxL"),
            ),
        )
        self.assertEqual(
            signature(
                shared_patterns.pattern_nested_simple_lattice_2d(
                    304.0, 304.0, 82.0, 70.0, i=2, j=2
                )
            ),
            (
                (0.0, 0.0, 82.0, 70.0, "LxW"),
                (0.0, 70.0, 82.0, 70.0, "LxW"),
                (0.0, 140.0, 70.0, 82.0, "WxL"),
                (0.0, 222.0, 70.0, 82.0, "WxL"),
                (70.0, 152.0, 82.0, 70.0, "LxW"),
                (70.0, 222.0, 70.0, 82.0, "WxL"),
                (82.0, 0.0, 82.0, 70.0, "LxW"),
                (82.0, 70.0, 70.0, 82.0, "WxL"),
                (140.0, 234.0, 82.0, 70.0, "LxW"),
                (152.0, 82.0, 82.0, 70.0, "LxW"),
                (152.0, 152.0, 70.0, 82.0, "WxL"),
                (164.0, 0.0, 70.0, 82.0, "WxL"),
                (222.0, 164.0, 82.0, 70.0, "LxW"),
                (222.0, 234.0, 82.0, 70.0, "LxW"),
                (234.0, 0.0, 70.0, 82.0, "WxL"),
                (234.0, 82.0, 70.0, 82.0, "WxL"),
            ),
        )

    def test_rotation_reversal_units_and_limits(self):
        metric = self.assert_lattice(
            "pattern_nested_simple_lattice_2d",
            2,
            3,
            area_l=374.0,
            area_w=386.0,
        )
        imperial = shared_patterns.pattern_nested_simple_lattice_2d(
            374.0 / 25.4,
            386.0 / 25.4,
            82.0 / 25.4,
            70.0 / 25.4,
            i=2,
            j=3,
        )
        self.assertEqual(
            {
                tuple(round(value / 25.4, 8) for value in (p.x, p.y, p.l, p.w))
                for p in metric
            },
            {
                tuple(round(value, 8) for value in (p.x, p.y, p.l, p.w))
                for p in imperial
            },
        )

        reversed_layer = shared_patterns.pattern_nested_simple_lattice_2d(
            386.0,
            374.0,
            70.0,
            82.0,
            i=2,
            j=3,
        )
        self.assertEqual(len(reversed_layer), len(metric))
        self.assertTrue(
            validate_placements(
                reversed_layer,
                386.0,
                374.0,
                expected_footprint=(70.0, 82.0),
            ).valid
        )
        self.assertEqual(
            shared_patterns.pattern_nested_simple_lattice_1d(
                221.9, 234.0, 82.0, 70.0, i=1, j=2
            ),
            [],
        )
        self.assertEqual(
            shared_patterns.pattern_nested_simple_lattice_2d(
                304.0, 303.9, 82.0, 70.0, i=2, j=2
            ),
            [],
        )

    def test_enumeration_exposes_multiple_lattice_variants_without_reordering_history(self):
        candidates = enumerate_pattern_candidates(304.0, 304.0, 82.0, 70.0)
        lattice = [item for item in candidates if "nested_simple_lattice" in item.family]
        self.assertTrue(lattice)
        self.assertTrue(any(item.family == "nested_simple_lattice_1d" for item in lattice))
        self.assertTrue(any(item.family == "nested_simple_lattice_2d" for item in lattice))
        self.assertGreaterEqual(len({item.variant for item in lattice}), 2)
        self.assertTrue(
            all(
                validate_placements(
                    item.placements,
                    304.0,
                    304.0,
                    expected_footprint=(82.0, 70.0),
                ).valid
                for item in lattice
            )
        )


class NestedSimpleLatticeConsumerTests(SimpleTestCase):
    def test_lattice_cannot_spend_the_budget_of_later_vertical_axes(self):
        product = (83, 91, 99)
        container = (1302, 1297, 347)
        historical = search_mosaic_placements(
            product, container, 1, 1, 1, include_lattice=False
        )
        selected = compare_packing_candidates(product, container, 1, 1, 1)
        self.assertEqual(historical.quantity, 740)
        self.assertGreaterEqual(selected.selected_quantity, historical.quantity)
        self.assertTrue(selected.geometry_valid)

    def test_pallet_search_shortlists_distinct_lattice_variants(self):
        for family in ("Nested Simple Lattice — 1D", "Nested Simple Lattice — 2D"):
            with self.subTest(family=family):
                entries = list(pallet_engine._nested_simple_lattice_entries(family, 800, 800, 82, 70))
                counts = [len(entry[1]) for entry in entries]
                self.assertEqual(len(entries), pallet_engine.PALLET_LATTICE_VARIANTS_PER_FAMILY)
                self.assertEqual(counts, sorted(counts, reverse=True))
                self.assertEqual(
                    len({pallet_engine.layer_geometry_signature(entry[1]) for entry in entries}),
                    len(entries),
                )

    def test_palletization_delegates_and_exposes_parameters(self):
        layer = pallet_engine.pattern_nested_simple_lattice_2d(
            304.0, 304.0, 82.0, 70.0, i=2, j=2
        )
        self.assertEqual(len(layer), 16)
        self.assertEqual({item.orientation for item in layer}, {"LxW", "WxL"})
        rows = pallet_engine.run_palletization_analysis(
            82.0,
            70.0,
            50.0,
            304.0,
            304.0,
            115.0,
            pallet_height=15.0,
        )
        lattice = next(
            row
            for row in rows
            if row["pattern"] == "Nested Simple Lattice — 2D"
            and row.get("lattice_parameters", {}).get("i") == 2
            and row.get("lattice_parameters", {}).get("j") == 2
        )
        self.assertEqual(
            (lattice["boxes_layer_A"], lattice["layers"], lattice["total_boxes"]),
            (16, 2, 32),
        )

    def test_container_selection_finds_1d_and_exposes_2d_candidate_on_tie(self):
        one_d = search_mosaic_placements(
            (82.0, 70.0, 50.0),
            (292.0, 316.0, 50.0),
            0,
            0,
            1,
        )
        self.assertEqual(one_d.quantity, 16)
        self.assertEqual(one_d.family, "nested_simple_lattice_1d")

        candidates = enumerate_pattern_candidates(304.0, 304.0, 82.0, 70.0)
        two_d = [item for item in candidates if item.family == "nested_simple_lattice_2d"]
        self.assertTrue(any(item.quantity == 16 for item in two_d))
