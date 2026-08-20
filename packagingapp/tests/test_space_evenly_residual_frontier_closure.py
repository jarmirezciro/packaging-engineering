import json
from collections import Counter

from django.test import SimpleTestCase

from packagingapp.utils.container_tool import engine


TOLERANCE = 1e-7


def residual_product(
    name,
    length,
    width,
    height,
    qty,
    *,
    weight=0.0,
    stackable=True,
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
        "sequence": 1,
        "stackable": bool(stackable),
        "r1": bool(r1),
        "r2": bool(r2),
        "r3": bool(r3),
    }


def normalized_container(**overrides):
    values = {
        "L": 1000.0,
        "W": 300.0,
        "H": 300.0,
        "max_weight": None,
        "tare_weight": None,
    }
    values.update(overrides)
    return engine._normalize_container(values)


def run_residual_frontiers(products, *, container=None):
    container = container or normalized_container()
    normalized = engine.normalize_products(products)
    ordered = engine.sort_products(normalized, container)
    placements = []
    residual_loaded = {product.row_index: 0 for product in ordered}
    residual_quantities = {
        product.row_index: product.qty for product in ordered
    }
    next_item_index = {product.row_index: 0 for product in ordered}
    (
        frontier,
        loaded_weight,
        frontiers,
        candidate_evaluations,
        local_evaluations,
        support_relationships,
    ) = engine.pack_space_evenly_residual_frontiers(
        container,
        ordered,
        residual_quantities,
        placements,
        residual_loaded,
        next_item_index,
        0.0,
        0.0,
        {},
    )
    return {
        "container": container,
        "ordered": ordered,
        "placements": placements,
        "residual_loaded": residual_loaded,
        "frontier": frontier,
        "loaded_weight": loaded_weight,
        "frontiers": frontiers,
        "candidate_evaluations": candidate_evaluations,
        "local_evaluations": local_evaluations,
        "support_relationships": support_relationships,
    }


def placement(
    *,
    row_index,
    x,
    y,
    z,
    length,
    width,
    height,
    stackable=True,
):
    return engine.Placement(
        product_name=f"P{row_index}",
        item_index=0,
        row_index=row_index,
        sequence=1,
        weight=0.0,
        stackable=stackable,
        x=float(x),
        y=float(y),
        z=float(z),
        l=float(length),
        w=float(width),
        h=float(height),
    )


class SpaceEvenlyResidualFrontierClosureTests(SimpleTestCase):
    def test_quantities_one_two_three_and_seventeen_use_same_geometry_rule(self):
        for quantity in (1, 2, 3, 17):
            with self.subTest(quantity=quantity):
                result = run_residual_frontiers(
                    [residual_product("A", 100, 100, 100, quantity)]
                )
                self.assertEqual(len(result["placements"]), quantity)
                self.assertEqual(sum(result["residual_loaded"].values()), quantity)
                self.assertEqual(
                    result["frontier"],
                    ((quantity + 8) // 9) * 100.0,
                )
                self.assertEqual(len(result["frontiers"]), 1)

    def test_first_feasible_ordered_product_is_residual_anchor(self):
        result = run_residual_frontiers(
            [
                residual_product("Higher footprint", 100, 200, 50, 1),
                residual_product("Lower footprint", 100, 100, 50, 1),
            ],
            container=normalized_container(W=200.0, H=100.0),
        )
        expected = result["ordered"][0]
        first_frontier = result["frontiers"][0]
        self.assertEqual(first_frontier["anchor_row_index"], expected.row_index)
        self.assertEqual(first_frontier["anchor_product"], expected.name)

    def test_whole_frontier_allows_combined_homogeneous_union_support(self):
        result = run_residual_frontiers(
            [
                residual_product(
                    "Lower",
                    100,
                    100,
                    300,
                    2,
                    r1=True,
                    r2=True,
                ),
                residual_product("Bridge", 100, 200, 50, 1),
            ],
            container=normalized_container(L=300.0, W=200.0, H=200.0),
        )
        bridge = next(
            item for item in result["placements"] if item.product_name == "Bridge"
        )
        lower = [
            item for item in result["placements"] if item.product_name == "Lower"
        ]
        self.assertEqual(bridge.z, 100.0)
        self.assertEqual({item.y for item in lower}, {0.0, 100.0})
        self.assertTrue(engine._frontier_supports_full_base(bridge, lower))
        self.assertEqual(result["frontiers"][0]["anchor_product"], "Lower")

    def test_union_support_rejects_a_real_gap(self):
        supports = [
            placement(
                row_index=0,
                x=0,
                y=0,
                z=0,
                length=100,
                width=90,
                height=50,
            ),
            placement(
                row_index=0,
                x=0,
                y=110,
                z=0,
                length=100,
                width=90,
                height=50,
            ),
        ]
        bridge = placement(
            row_index=1,
            x=0,
            y=0,
            z=50,
            length=100,
            width=200,
            height=25,
        )
        self.assertFalse(engine._frontier_supports_full_base(bridge, supports))

    def test_nonstackable_foundation_cannot_support_an_upper_product(self):
        lower = placement(
            row_index=0,
            x=0,
            y=0,
            z=0,
            length=100,
            width=100,
            height=50,
            stackable=False,
        )
        upper = placement(
            row_index=1,
            x=0,
            y=0,
            z=50,
            length=100,
            width=100,
            height=25,
        )
        self.assertFalse(engine._frontier_supports_full_base(upper, [lower]))

    def test_nonstackable_residual_anchor_stays_on_floor(self):
        result = run_residual_frontiers(
            [
                residual_product(
                    "Nonstackable",
                    100,
                    100,
                    100,
                    4,
                    stackable=False,
                )
            ],
            container=normalized_container(W=200.0, H=200.0),
        )
        self.assertEqual(len(result["placements"]), 4)
        self.assertEqual({item.z for item in result["placements"]}, {0.0})
        self.assertEqual(result["frontier"], 200.0)

    def test_nonstackable_upper_can_be_supported_but_cannot_support_another(self):
        floor = placement(
            row_index=0,
            x=0,
            y=0,
            z=0,
            length=100,
            width=100,
            height=50,
        )
        middle = placement(
            row_index=1,
            x=0,
            y=0,
            z=50,
            length=100,
            width=100,
            height=50,
            stackable=False,
        )
        top = placement(
            row_index=2,
            x=0,
            y=0,
            z=100,
            length=100,
            width=100,
            height=25,
        )
        self.assertTrue(engine._frontier_supports_full_base(middle, [floor]))
        self.assertFalse(
            engine._frontier_supports_full_base(top, [floor, middle])
        )

    def test_payload_limit_stops_residual_loading(self):
        result = run_residual_frontiers(
            [residual_product("Weighted", 100, 100, 100, 5, weight=1.0)],
            container=normalized_container(max_weight=2.5),
        )
        self.assertEqual(len(result["placements"]), 2)
        self.assertEqual(result["loaded_weight"], 2.0)
        self.assertEqual(sum(result["residual_loaded"].values()), 2)

    def test_restricted_rotations_are_respected_exactly(self):
        product = residual_product(
            "Restricted",
            120,
            80,
            50,
            3,
            r1=False,
            r2=True,
            r3=False,
        )
        result = run_residual_frontiers([product])
        allowed = {(120.0, 50.0, 80.0), (50.0, 120.0, 80.0)}
        self.assertEqual(len(result["placements"]), 3)
        self.assertTrue(
            all((item.l, item.w, item.h) in allowed for item in result["placements"])
        )

    def test_no_residual_is_a_phase_two_no_op(self):
        result = engine.pack_container(
            {
                "L": 100.0,
                "W": 200.0,
                "H": 100.0,
                "max_weight": None,
                "packing_mode": "space_evenly",
            },
            [residual_product("Exact block", 100, 100, 100, 2)],
        )
        self.assertEqual(result["space_evenly_residual_units"], 0)
        self.assertEqual(result["space_evenly_residual_frontiers"], [])
        self.assertEqual(result["space_evenly_residual_frontier_count"], 0)

    def test_x_exhaustion_returns_remaining_residual_unplaced(self):
        result = engine.pack_container(
            {
                "L": 100.0,
                "W": 200.0,
                "H": 100.0,
                "max_weight": None,
                "packing_mode": "space_evenly",
            },
            [residual_product("One too many", 100, 100, 100, 3)],
        )
        self.assertEqual(len(result["placements"]), 2)
        self.assertEqual(len(result["unplaced"]), 1)
        self.assertEqual(result["space_evenly_residual_packed_units"], 0)
        self.assertEqual(result["space_evenly_residual_frontiers"], [])

    def test_bottom_up_and_deferred_gravity_candidates_are_both_evaluated(self):
        result = run_residual_frontiers(
            [
                residual_product("A", 100, 100, 100, 2),
                residual_product("B", 100, 50, 50, 2),
            ]
        )
        candidates = result["frontiers"][0]["residual_frontier_candidates"]
        self.assertEqual(
            {candidate["gravity_mode"] for candidate in candidates},
            {"bottom_up", "deferred_top_down"},
        )
        self.assertTrue(
            all("physical_validation" in candidate for candidate in candidates)
        )

    def test_equal_extension_efficiency_prefers_native(self):
        native = {
            "valid": True,
            "committed_depth": 1.0,
            "frontier_packed_volume": 100.0,
        }
        extended = {
            "valid": True,
            "committed_depth": 2.0,
            "frontier_packed_volume": 200.0,
        }
        engine._apply_space_evenly_extension_value(
            native,
            extended,
            1.0,
            {"W": 10.0, "H": 10.0},
        )
        self.assertFalse(extended["extension_justified"])
        self.assertEqual(
            extended["extension_decision_reason"],
            "native_preferred_equal_extension_value",
        )

    def test_diagnostics_are_json_safe_and_runs_are_deterministic(self):
        products = [
            residual_product("A", 100, 100, 100, 7),
            residual_product("B", 100, 50, 50, 5),
        ]
        first = run_residual_frontiers(products)
        second = run_residual_frontiers(products)
        signature = lambda result: [
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
            for item in result["placements"]
        ]
        self.assertEqual(signature(first), signature(second))
        self.assertEqual(first["frontiers"], second["frontiers"])
        json.dumps(first["frontiers"])
        self.assertGreater(first["candidate_evaluations"], 0)
        self.assertGreater(first["local_evaluations"], 0)
        self.assertEqual(
            Counter(item.row_index for item in first["placements"]),
            Counter({0: 7, 1: 5}),
        )
