from collections import Counter
from dataclasses import replace
from itertools import combinations
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from packagingapp.forms import ContainerToolForm
from packagingapp.tools.transport.service import _prepare_transport_analysis
from packagingapp.utils.container_tool import engine


TOLERANCE = 1e-7


def product(
    name,
    length,
    width,
    height,
    qty,
    *,
    weight=0.0,
    sequence=1,
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
        "sequence": sequence,
        "stackable": bool(stackable),
        "r1": bool(r1),
        "r2": bool(r2),
        "r3": bool(r3),
    }


def accepted_container():
    return {
        "L": 12039.0,
        "W": 2362.0,
        "H": 2692.0,
        "max_weight": None,
        "packing_mode": "space_evenly",
    }


def accepted_products():
    return [
        product("SKU302473", 457.2, 279.4, 317.5, 375, weight=0.2427),
        product("SKU503739", 431.8, 318.77, 317.5, 405, weight=0.907),
        product("Case Pack 12", 558.8, 377.444, 317.5, 288, weight=0.907),
        product("Case Pack", 558.8, 355.6, 381.0, 160, weight=2.268),
    ]


def geometry_signature(result):
    return tuple(
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
        for placement in result["placements"]
    )


class SpaceEvenlyStabilizationTests(SimpleTestCase):
    def assert_physical_invariants(self, result, container, products):
        counts = Counter(placement.row_index for placement in result["placements"])
        for row_index, row in enumerate(products):
            self.assertLessEqual(counts[row_index], row["qty"])

        for placement in result["placements"]:
            self.assertGreaterEqual(placement.x, -TOLERANCE)
            self.assertGreaterEqual(placement.y, -TOLERANCE)
            self.assertGreaterEqual(placement.z, -TOLERANCE)
            self.assertLessEqual(placement.x + placement.l, container["L"] + TOLERANCE)
            self.assertLessEqual(placement.y + placement.w, container["W"] + TOLERANCE)
            self.assertLessEqual(placement.z + placement.h, container["H"] + TOLERANCE)

        for first, second in combinations(result["placements"], 2):
            separated = (
                first.x + first.l <= second.x + TOLERANCE
                or second.x + second.l <= first.x + TOLERANCE
                or first.y + first.w <= second.y + TOLERANCE
                or second.y + second.w <= first.y + TOLERANCE
                or first.z + first.h <= second.z + TOLERANCE
                or second.z + second.h <= first.z + TOLERANCE
            )
            self.assertTrue(separated)

    def choose_terminal_support_plan(
        self,
        *,
        current_quantity,
        next_orientation,
        max_weight=None,
    ):
        base, current, next_product = engine.normalize_products(
            [
                product("Base", 500, 500, 100, 1),
                product("Current", 460, 280, 100, current_quantity, weight=1),
                product("Next", 320, 200, 100, 1),
            ]
        )
        # Model the acceptance fixture's explicitly orientation-restricted next SKU.
        next_product = replace(
            next_product,
            orientations=(tuple(float(value) for value in next_orientation),),
        )
        parent = engine.SupportSurface(0, 0, 0, 100, 500, 500, base, 0, 1)
        stats = {
            "candidate_evaluations": 0,
            "support_checks": 0,
            "support_relationships": 0,
        }
        plan = engine._choose_upper_run(
            parent,
            0,
            500,
            [current, next_product],
            {current.row_index: current_quantity, next_product.row_index: 1},
            {current.row_index: 0, next_product.row_index: 1},
            0,
            current,
            {"L": 1000, "W": 500, "H": 1000, "max_weight": max_weight},
            stats,
        )
        self.assertIsNotNone(plan)
        return plan

    def choose_upper_plan(
        self,
        parent,
        products,
        remaining,
        current_product,
        *,
        container=None,
        allow_none=False,
    ):
        stats = {
            "candidate_evaluations": 0,
            "support_checks": 0,
            "support_relationships": 0,
        }
        plan = engine._choose_upper_run(
            parent,
            parent.y,
            parent.width,
            products,
            remaining,
            {product.row_index: index for index, product in enumerate(products)},
            0,
            current_product,
            container
            or {
                "L": 1200,
                "W": max(parent.y + parent.width, 1200),
                "H": 1200,
                "max_weight": None,
            },
            stats,
        )
        if not allow_none:
            self.assertIsNotNone(plan)
        return plan

    def test_stale_sequences_are_forced_to_one_without_changing_geometry(self):
        container = accepted_container()
        baseline_products = accepted_products()
        stale_products = [
            {**row, "sequence": sequence}
            for row, sequence in zip(baseline_products, (4, 2, 99, 7))
        ]

        baseline = engine.pack_container(container, baseline_products)
        stale = engine.pack_container(container, stale_products)
        repeated = engine.pack_container(container, stale_products)

        self.assertEqual(geometry_signature(stale), geometry_signature(baseline))
        self.assertEqual(geometry_signature(repeated), geometry_signature(stale))
        self.assertTrue(
            all(item["sequence"] == 1 for item in stale["space_evenly_product_order"])
        )
        self.assertTrue(all(placement.sequence == 1 for placement in stale["placements"]))

    def test_phase_one_signature_remains_frozen(self):
        result = engine.pack_container(accepted_container(), accepted_products())

        self.assertEqual(
            [item["row_index"] for item in result["space_evenly_product_order"]],
            [2, 3, 1, 0],
        )
        self.assertEqual(result["space_evenly_main_block_count"], 27)
        self.assertEqual(result["space_evenly_main_block_units"], 1180)
        self.assertEqual(result["space_evenly_main_blocks_end_x"], 10668.0)
        self.assertEqual(
            [
                (
                    block["row_index"],
                    block["regular_qty"],
                    block["residual_qty"],
                    block["complete_blocks"],
                    block["block"]["orientation"],
                )
                for block in result["space_evenly_product_blocks"]
            ],
            [
                (2, 288, 0, 6, [558.8, 377.444, 317.5]),
                (3, 140, 20, 5, [355.6, 558.8, 381.0]),
                (1, 392, 13, 7, [431.8, 318.77, 317.5]),
                (0, 360, 15, 9, [279.4, 457.2, 317.5]),
            ],
        )

    def test_foundation_preserves_product_choice_and_improves_width(self):
        result = engine.pack_container(accepted_container(), accepted_products())
        foundation = result["space_evenly_residual_bands"][0]

        self.assertEqual(foundation["foundation_product"], "Case Pack")
        self.assertEqual(
            foundation["foundation_orientation"],
            [355.6, 558.8, 381.0],
        )
        self.assertAlmostEqual(foundation["foundation_occupied_width"], 2235.2)
        self.assertAlmostEqual(
            foundation["foundation_width_utilization"],
            2235.2 / 2362.0,
        )
        self.assertEqual(foundation["foundation_orientation_count"], 1)

    def test_selected_upper_sku_uses_best_single_orientation(self):
        normalized = engine.normalize_products(
            [
                product("Base", 900, 900, 100, 1),
                product("Upper", 800, 400, 300, 1, r1=True, r2=True),
            ]
        )
        base, upper = normalized
        parent = engine.SupportSurface(0, 0, 0, 100, 900, 1000, base, 0, 2)
        stats = {
            "candidate_evaluations": 0,
            "support_checks": 0,
            "support_relationships": 0,
        }

        plan = engine._choose_upper_run(
            parent,
            0,
            1000,
            [upper],
            {upper.row_index: 1},
            {upper.row_index: 0},
            0,
            upper,
            {"L": 1000, "W": 1000, "H": 1000, "max_weight": None},
            stats,
        )

        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.runs), 1)
        self.assertEqual(plan.runs[0].orientation, (300.0, 800.0, 400.0))
        self.assertEqual(plan.occupied_width, 800.0)
        self.assertEqual(plan.width_utilization, 0.8)

    def test_same_product_repeats_parent_orientation_across_z_passes(self):
        current = engine.normalize_products(
            [product("Current", 450, 280, 300, 12)]
        )[0]
        parent = engine.SupportSurface(
            0, 0, 0, 300, 450, 1120, current, 0, 4
        )

        second_row = self.choose_upper_plan(
            parent,
            [current],
            {current.row_index: 8},
            current,
        )
        second_surface = engine._upper_child_surface(
            parent,
            parent.y,
            current,
            second_row.runs[0].orientation_index,
            second_row.runs[0].orientation,
            second_row.runs[0].quantity,
        )
        third_row = self.choose_upper_plan(
            second_surface,
            [current],
            {current.row_index: 4},
            current,
        )

        self.assertEqual(
            [
                parent.orientation_index,
                second_row.runs[0].orientation_index,
                third_row.runs[0].orientation_index,
            ],
            [0, 0, 0],
        )
        self.assertEqual(
            [second_row.runs[0].quantity, third_row.runs[0].quantity],
            [4, 4],
        )

    def test_partial_final_row_keeps_parent_orientation(self):
        current = engine.normalize_products(
            [product("Current", 450, 280, 300, 2)]
        )[0]
        parent = engine.SupportSurface(
            0, 0, 0, 300, 450, 1120, current, 0, 4
        )

        plan = self.choose_upper_plan(
            parent,
            [current],
            {current.row_index: 2},
            current,
        )

        self.assertEqual(plan.runs[0].orientation, (450.0, 280.0, 300.0))
        self.assertEqual(plan.runs[0].quantity, 2)
        self.assertEqual(plan.occupied_width, 560.0)

    def test_pattern_continuation_respects_payload_limit(self):
        current = engine.normalize_products(
            [product("Current", 450, 280, 300, 4, weight=1)]
        )[0]
        parent = engine.SupportSurface(
            0, 0, 0, 300, 450, 1120, current, 0, 4
        )

        plan = self.choose_upper_plan(
            parent,
            [current],
            {current.row_index: 4},
            current,
            container={"L": 1200, "W": 1200, "H": 1200, "max_weight": 2},
        )

        self.assertEqual(plan.runs[0].orientation_index, 0)
        self.assertEqual(plan.runs[0].quantity, 2)

    def test_new_product_on_surface_still_uses_width_optimizer(self):
        base, upper = engine.normalize_products(
            [
                product("Base", 900, 900, 100, 1),
                product("Upper", 800, 400, 300, 1, r1=True, r2=True),
            ]
        )
        parent = engine.SupportSurface(0, 0, 0, 100, 900, 1000, base, 0, 2)

        plan = self.choose_upper_plan(
            parent,
            [upper],
            {upper.row_index: 1},
            upper,
        )

        self.assertEqual(plan.runs[0].orientation, (300.0, 800.0, 400.0))
        self.assertEqual(plan.occupied_width, 800.0)

    def test_height_failure_falls_back_to_existing_orientation_optimizer(self):
        current = engine.normalize_products(
            [product("Current", 450, 280, 300, 1, r1=True, r2=True)]
        )[0]
        parent = engine.SupportSurface(
            0, 0, 0, 720, 450, 1120, current, 0, 4
        )

        plan = self.choose_upper_plan(
            parent,
            [current],
            {current.row_index: 1},
            current,
            container={"L": 1200, "W": 1200, "H": 1000, "max_weight": None},
            allow_none=True,
        )

        self.assertIsNone(plan)

    def test_exhausted_parent_product_allows_normal_product_switch(self):
        parent_product, next_product = engine.normalize_products(
            [
                product("Parent", 900, 900, 100, 1),
                product("Next", 800, 400, 300, 1, r1=True, r2=True),
            ]
        )
        parent = engine.SupportSurface(
            0, 0, 0, 100, 900, 1000, parent_product, 0, 2
        )

        plan = self.choose_upper_plan(
            parent,
            [parent_product, next_product],
            {parent_product.row_index: 0, next_product.row_index: 1},
            None,
        )

        self.assertEqual(plan.product.row_index, next_product.row_index)
        self.assertEqual(plan.runs[0].orientation, (300.0, 800.0, 400.0))

    def test_parent_pattern_precedes_terminal_support_heuristic(self):
        current, next_product = engine.normalize_products(
            [
                product("Current", 460, 280, 100, 1),
                product("Next", 200, 320, 100, 1),
            ]
        )
        next_product = replace(
            next_product,
            orientations=((200.0, 320.0, 100.0),),
        )
        parent = engine.SupportSurface(
            0, 0, 0, 100, 460, 560, current, 0, 2
        )
        remaining = {current.row_index: 1, next_product.row_index: 1}

        generic = engine._choose_width_optimized_upper_plan(
            parent,
            0,
            560,
            current,
            list(enumerate(current.orientations)),
            1,
            [current, next_product],
            remaining,
            {"L": 1000, "W": 560, "H": 1000, "max_weight": None},
            {
                "candidate_evaluations": 0,
                "support_checks": 0,
                "support_relationships": 0,
            },
        )
        continued = self.choose_upper_plan(
            parent,
            [current, next_product],
            remaining,
            current,
            container={"L": 1000, "W": 560, "H": 1000, "max_weight": None},
        )

        self.assertEqual(generic.runs[0].orientation_index, 1)
        self.assertEqual(generic.support_potential, 1)
        self.assertEqual(continued.runs[0].orientation_index, 0)
        self.assertEqual(continued.support_potential, 0)

    def test_terminal_row_preserves_support_for_another_remaining_sku(self):
        plan = self.choose_terminal_support_plan(
            current_quantity=1,
            next_orientation=(320, 200, 100),
        )
        repeated = self.choose_terminal_support_plan(
            current_quantity=1,
            next_orientation=(320, 200, 100),
        )

        self.assertEqual(plan.runs[0].orientation, (460.0, 280.0, 100.0))
        self.assertEqual(plan.occupied_width, 280.0)
        self.assertEqual(plan.support_potential, 1)
        self.assertEqual(plan, repeated)

    def test_non_terminal_row_keeps_width_optimized_orientation(self):
        plan = self.choose_terminal_support_plan(
            current_quantity=2,
            next_orientation=(320, 200, 100),
        )

        self.assertEqual(plan.runs[0].orientation, (280.0, 460.0, 100.0))
        self.assertEqual(plan.occupied_width, 460.0)

    def test_payload_limited_row_is_not_treated_as_terminal(self):
        plan = self.choose_terminal_support_plan(
            current_quantity=2,
            next_orientation=(320, 200, 100),
            max_weight=1,
        )

        self.assertEqual(plan.runs[0].orientation, (280.0, 460.0, 100.0))
        self.assertEqual(plan.occupied_width, 460.0)

    def test_terminal_row_without_support_benefit_keeps_width_optimum(self):
        plan = self.choose_terminal_support_plan(
            current_quantity=1,
            next_orientation=(480, 200, 100),
        )

        self.assertEqual(plan.runs[0].orientation, (280.0, 460.0, 100.0))
        self.assertEqual(plan.occupied_width, 460.0)
        self.assertEqual(plan.support_potential, 0)

    def test_terminal_support_gate_keeps_width_priority_among_valid_plans(self):
        plan = self.choose_terminal_support_plan(
            current_quantity=1,
            next_orientation=(250, 200, 100),
        )

        self.assertEqual(plan.runs[0].orientation, (280.0, 460.0, 100.0))
        self.assertEqual(plan.occupied_width, 460.0)
        self.assertEqual(plan.support_potential, 1)

    def test_upper_row_finds_bounded_two_orientation_solution(self):
        normalized = engine.normalize_products(
            [
                product("Base", 600, 600, 100, 1),
                product("P4", 558.8, 355.6, 381.0, 6),
            ]
        )
        base, p4 = normalized
        parent = engine.SupportSurface(0, 0, 0, 100, 600, 2362, base, 0, 4)
        stats = {
            "candidate_evaluations": 0,
            "support_checks": 0,
            "support_relationships": 0,
        }

        plan = engine._choose_upper_run(
            parent,
            0,
            2362,
            [p4],
            {p4.row_index: 6},
            {p4.row_index: 0},
            0,
            p4,
            {"L": 1000, "W": 2362, "H": 1000, "max_weight": None},
            stats,
        )

        self.assertIsNotNone(plan)
        self.assertEqual(
            [(run.orientation_index, run.quantity) for run in plan.runs],
            [(1, 4)],
        )
        self.assertAlmostEqual(plan.occupied_width, 2235.2)
        self.assertAlmostEqual(plan.width_utilization, 2235.2 / 2362.0)

        first_surface = engine._upper_child_surface(
            parent,
            0,
            p4,
            plan.runs[0].orientation_index,
            plan.runs[0].orientation,
            plan.runs[0].quantity,
        )
        second_surface = engine._upper_child_surface(
            parent,
            first_surface.width,
            p4,
            plan.runs[0].orientation_index,
            plan.runs[0].orientation,
            plan.runs[0].quantity,
        )
        first_continuation = self.choose_upper_plan(
            first_surface,
            [p4],
            {p4.row_index: 6},
            p4,
        )
        second_continuation = self.choose_upper_plan(
            second_surface,
            [p4],
            {p4.row_index: 1},
            p4,
        )
        self.assertEqual(first_continuation.runs[0].orientation_index, 1)
        self.assertEqual(first_continuation.runs[0].quantity, 4)
        self.assertEqual(second_continuation.runs[0].orientation_index, 1)
        self.assertEqual(second_continuation.runs[0].quantity, 1)

    def test_accepted_case_remains_complete_supported_and_physical(self):
        container = accepted_container()
        products = accepted_products()
        result = engine.pack_container(container, products)

        self.assertEqual(len(result["placements"]), 1228)
        self.assertEqual(result["unplaced"], [])
        self.assertEqual(result["space_evenly_residual_packed_units"], 48)
        frontiers = result["space_evenly_residual_frontiers"]
        self.assertEqual(result["space_evenly_residual_bands"], frontiers)
        self.assertEqual(len(frontiers), 2)
        self.assertEqual(
            [frontier["anchor_row_index"] for frontier in frontiers],
            [3, 1],
        )
        self.assertTrue(
            all(
                frontier["physical_validation"]["valid"]
                for frontier in frontiers
            )
        )
        self.assertTrue(frontiers[0]["extension_evaluated"])
        self.assertFalse(frontiers[0]["extension_justified"])
        self.assertGreater(
            frontiers[0]["next_clean_frontier_efficiency"],
            frontiers[0]["extension_marginal_efficiency"],
        )
        self.assertLessEqual(
            max(placement.x + placement.l for placement in result["placements"]),
            11621.77 + TOLERANCE,
        )
        p2_residual = [
            placement
            for placement in result["placements"]
            if placement.row_index == 1 and placement.item_index >= 392
        ]
        self.assertEqual(len(p2_residual), 13)
        self.assertEqual(
            sum(placement.z > TOLERANCE for placement in p2_residual),
            10,
        )
        self.assertEqual(
            sum(placement.z <= TOLERANCE for placement in p2_residual),
            3,
        )
        self.assertEqual(result["space_evenly_support_surface_count"], 13)
        self.assert_physical_invariants(result, container, products)

    def test_service_ignores_invalid_stale_sequence_for_space_evenly(self):
        prepared = _prepare_transport_analysis(
            {
                "packing_mode": "space_evenly",
                "container_source": "manual",
                "container_l": 1000,
                "container_w": 1000,
                "container_h": 1000,
                "max_weight": None,
                "tare_weight": None,
            },
            [
                product(
                    "A",
                    100,
                    100,
                    100,
                    2,
                    sequence="stale-invalid",
                )
            ],
        )

        self.assertTrue(prepared["ok"], prepared["messages"])
        self.assertEqual(prepared["products"][0]["sequence"], 1)
        self.assertEqual(prepared["safe_rows"][0]["sequence"], 1)

    def test_shared_ui_freezes_initial_and_dynamic_sequence_fields(self):
        base_dir = Path(settings.BASE_DIR)
        product_template = (
            base_dir
            / "packagingapp/templates/container_tool/partials/_transport_product_section.html"
        ).read_text(encoding="utf-8")
        scripts = (
            base_dir
            / "packagingapp/templates/container_tool/partials/_transport_scripts.html"
        ).read_text(encoding="utf-8")

        self.assertEqual(product_template.count("data-transport-sequence-input"), 4)
        self.assertIn("field.value = '1'", scripts)
        self.assertIn("field.readOnly = sequenceLocked", scripts)
        self.assertIn("mode === 'front_to_back'", scripts)
        self.assertGreaterEqual(
            scripts.count(
                "transportSyncSequenceInputs(newRow.closest('[data-transport-tool-root]'))"
            ),
            2,
        )
        self.assertIn("transportBindPackingMode(root)", scripts)

        rendered = render_to_string(
            "container_tool/partials/_transport_product_section.html",
            {
                "is_workflow": False,
                "is_first_step": True,
                "form": ContainerToolForm(initial={"packing_mode": "space_evenly"}),
                "transport_sequence_locked": True,
                "product_rows": [product("A", 100, 100, 100, 1, sequence=99)],
                "result": None,
                "product_catalogues": [],
                "product_items": [],
            },
        )
        self.assertIn(
            'value="1" data-transport-sequence-input readonly aria-readonly="true"',
            rendered,
        )
        self.assertNotIn('value="99" data-transport-sequence-input', rendered)
