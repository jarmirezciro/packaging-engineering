import hashlib
import gzip
import json
from collections import Counter
from dataclasses import asdict
from itertools import combinations, product as flag_product
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from packagingapp.tests.transport_physical_validator import (
    assert_transport_result_physical,
)
from packagingapp.utils.container_tool import engine
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
    r1=False,
    r2=False,
    r3=True,
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


def semitrailer_roof_experiment(*, perturbed=False, g_sequence=3):
    """Controlled mm reconstruction, not an exact replay of hidden UI state.

    Dimensions/all rotations follow the task. Weights follow the local
    48-ft preset (lb -> kg); A/B share group 1, C uses 2, D/E/F use 3.
    The same numeric inch and mm inputs are different physical experiments.
    """
    dimensions = [
        (15.8, 55.2, 63.2) if perturbed else (15.7, 55.1, 63.2),
        (63, 23.6, 39.4), (23.6, 17.7, 51.2), (31.5, 47.2, 15.7),
        (47.2, 47.2, 21.7), (47.2, 47.2, 21.7), (47.2, 47.2, 21.7),
    ]
    return [
        product(name, *dims, qty, weight=lb * 0.45359237,
                sequence=sequence, r1=True, r2=True, r3=True)
        for name, dims, qty, lb, sequence in zip(
            "ABCDEFG", dimensions, (30, 17, 16, 48, 14, 4, 4),
            (88.11, 191.93, 1198.76, 11.02, 1375.67, 661.38, 165.35),
            (1, 1, 2, 3, 3, 3, g_sequence),
        )
    ]


def stackability_expv2_2(*, easycargo_sequences=False, stackable_overrides=None):
    """Rounded task reconstruction: all rotations, canonical mm/kg, no payload.

    Preserve the public preset separately: it has different A dimensions,
    sequences, rotations and B/E stackability. Unit weights follow that preset.
    """
    dimensions = (
        (15.75, 55.15, 63), (63, 23.6, 39.4), (23.6, 17.7, 51.2),
        (31.5, 47.2, 15.7), (47.2, 47.2, 21.7),
        (47.2, 47.2, 21.7), (47.2, 47.2, 21.7),
    )
    sequences = (1, 2, 2, 3, 3, 3, 3) if easycargo_sequences else (1, 1, 1, 3, 3, 3, 3)
    rows = [
        product(
            name, *(value * 25.4 for value in dims), qty,
            weight=weight * 0.45359237, sequence=sequence,
            stackable=(stackable_overrides or {}).get(index, index not in (1, 4)),
            r1=True, r2=True, r3=True,
        )
        for index, (name, dims, qty, weight, sequence) in enumerate(zip(
            "ABCDEFG", dimensions, (30, 17, 16, 48, 14, 4, 4),
            (88.11, 191.93, 1198.76, 11.02, 1375.67, 661.38, 165.35), sequences,
        ))
    ]
    return {"L": 566.9 * 25.4, "W": 98.5 * 25.4, "H": 108 * 25.4, "max_weight": None}, rows


def mixed_support_orientation_case(flags=("r3",)):
    """TC-REG-019 task inputs; never substitute TC-REG-017 dimensions."""
    from packagingapp.tools.transport.service import (
        build_container_from_config, normalize_transport_rows_for_calculation,
        validate_transport_rows, validate_transport_unit_state,
    )

    path = Path(__file__).resolve().parents[2] / "regressions/TC-REG-019-mixed-cargo-support-bed-orientation/input.json"
    fixture = json.loads(path.read_text())
    units, errors = validate_transport_unit_state(fixture["config"])
    assert not errors, errors
    selected, errors = build_container_from_config(fixture["config"], unit_state=units)
    assert not errors, errors
    rows = [{**row, **{key: key in flags for key in ("r1", "r2", "r3")}}
            for row in fixture["rows"]]
    rows, errors = normalize_transport_rows_for_calculation(rows, units)
    assert not errors, errors
    rows, errors = validate_transport_rows(rows)
    assert not errors, errors
    return selected, rows


class SupportedTopAdaptiveMixedLaneTests(SimpleTestCase):
    """TC-REG-013/014: exact supported geometry, independent of cargo names."""

    def roof_case(
        self, length=275.5, width=94.2, height=45.01,
        dimensions=(63.0, 23.6, 39.44), qty=17, *, elevation=10.0,
        flags=(False, False, True), max_weight=None, stackable=True,
    ):
        # Nonzero XYZ origin also exercises the existing block materializer.
        x, y = 7.0, 3.0
        selected_container = container(
            FRONT_TO_BACK_INFILL_MODE, length=x + length + 11,
            width=y + width + 5, height=elevation + height,
            max_weight=max_weight,
        )
        rows = [
            product("Foundation", length, width, elevation, 1, weight=3,
                    stackable=stackable),
            product("Cargo", *dimensions, qty, weight=2.5,
                    r1=flags[0], r2=flags[1], r3=flags[2]),
        ]
        support = Placement("Foundation", 0, 0, 1, 3.0, stackable,
                            x, y, 0.0, length, width, elevation)
        return selected_container, rows, [support], x, x + length

    def fill_roof(self, case, *, sequence_restricted=False):
        selected_container, rows, supports, x_start, x_end = case
        products = normalize_products(rows)
        remaining = {index: row["qty"] for index, row in enumerate(rows)}
        indices = {index: 0 for index in remaining}
        for support in supports:
            remaining[support.row_index] -= 1
            indices[support.row_index] += 1
        placements, weight, stats = fill_top_residual_deterministically(
            Space(x_start, 0, 0, x_end - x_start,
                  selected_container["W"], selected_container["H"]),
            products[0], products, remaining, indices, selected_container,
            sum(item.weight for item in supports), sequence_restricted,
            eligible_row_indices={1}, committed_placements=supports,
        )
        result = {
            "placements": supports + placements, "loaded_weight": weight,
            "unplaced": [dict(row_index=index) for index, count in remaining.items()
                         for _ in range(count)],
        }
        assert_transport_result_physical(self, result, selected_container, rows)
        self.assertEqual(indices[1], len(placements))
        self.assertEqual(remaining[1] + len(placements), rows[1]["qty"])
        self.assertEqual(stats["top_infill_units_total"], len(placements))
        self.assertAlmostEqual(weight, sum(p.weight for p in supports) + len(placements) * 2.5)
        json.dumps(stats)
        return placements, stats, remaining

    def test_generator_already_represents_the_fifteen_unit_supported_construction(self):
        selected_container, rows, supports, x_start, x_end = self.roof_case()
        cargo = normalize_products(rows)[1]
        cavity = Space(x_start, 3, 10, 275.5, 94.2, 45.01)
        candidates, evaluated = build_product_block_candidates(
            cargo, {"L": cavity.L, "W": cavity.W, "H": cavity.H}, cavity.L, 17,
        )
        adaptive = [c for c in candidates if not c.repeatable]
        self.assertEqual(evaluated, 3)
        self.assertEqual(len(adaptive), 1)
        candidate = adaptive[0]
        self.assertEqual(candidate.planned_quantity, 15)
        self.assertEqual(candidate.x_repetitions, (4, 11))
        self.assertAlmostEqual(candidate.depth, 259.6)
        self.assertAlmostEqual(candidate.occupied_width, 86.6)
        placements = engine._materialize_product_block_in_space(cargo, candidate, cavity, 0, 15)
        self.assertEqual(len(placements), 15)
        self.assertEqual(len({id(item) for item in placements}), 15)
        self.assertIsNone(engine._top_candidate_validation_reason(
            placements, supports, cavity, selected_container,
        ))
        # Even in a larger envelope, an unequal-tail construction commits once.
        expanded = Space(cavity.x, cavity.y, cavity.z, 600, cavity.W, cavity.H)
        once = engine._materialize_product_block_in_space(cargo, candidate, expanded, 5, 100)
        self.assertEqual([p.item_index for p in once], list(range(5, 20)))
        self.assertEqual(engine._fill_candidate_plan(
            candidate, 14, 600, allow_stackable_adaptive=True,
        ), (0, 0, 0.0))

    def test_supported_top_selects_fifteen_instead_of_twelve_and_is_deterministic(self):
        first, stats, remaining = self.fill_roof(self.roof_case())
        second, repeated_stats, _ = self.fill_roof(self.roof_case())
        self.assertEqual(len(first), 15)
        self.assertEqual(remaining[1], 2)
        self.assertEqual(geometry_signature({"placements": first}),
                         geometry_signature({"placements": second}))
        self.assertEqual(stats, repeated_stats)
        action = stats["top_actions"][0]
        self.assertEqual(action["selected_block"]["pattern"], "adaptive_mixed_lane")
        self.assertFalse(action["selected_block"]["repeatable"])
        self.assertEqual(action["quantity"], 15)
        self.assertAlmostEqual(action["actual_x_depth_used"], 259.6)
        self.assertEqual(Counter((p.l, p.w, p.h) for p in first),
                         {(63.0, 23.6, 39.44): 4, (23.6, 63.0, 39.44): 11})
        self.assertTrue(all(p.row_index == 1 and p.product_name == "Cargo" for p in first))

    def test_larger_roof_preserves_the_existing_seventeen_unit_geometry(self):
        placements, stats, _ = self.fill_roof(self.roof_case(length=275.8, width=94.5))
        self.assertEqual(len(placements), 17)
        # Captured before the eligibility change: 4 x 4 then one rotated unit.
        expected = sorted(
            [(7 + x * 63, 3 + y * 23.6, 10, 63, 23.6, 39.44)
             for x in range(4) for y in range(4)]
            + [(259, 3, 10, 23.6, 63, 39.44)]
        )
        self.assertEqual(sorted((p.x, p.y, p.z, p.l, p.w, p.h) for p in placements), expected)
        self.assertEqual([action["quantity"] for action in stats["top_actions"]], [16, 1])

    def test_regular_and_side_planning_keep_stackable_adaptive_disabled(self):
        _, rows, _, _, _ = self.roof_case()
        candidates, _ = build_product_block_candidates(
            normalize_products(rows)[1], {"L": 275.5, "W": 94.2, "H": 45.01}, 275.5, 17,
        )
        for candidate in candidates:
            if not candidate.repeatable:
                self.assertEqual(engine._fill_candidate_plan(candidate, 17, 275.5), (0, 0, 0.0))
        self.assertTrue(choose_product_block(candidates, 17, 275.5).repeatable)

    def test_exact_supported_outcome_tie_preserves_synchronized_block(self):
        placements, stats, _ = self.fill_roof(self.roof_case(
            length=2400, width=2000, height=144,
            dimensions=(1200, 800, 144), qty=5,
        ))
        self.assertEqual(len(placements), 5)
        self.assertEqual(stats["top_actions"][0]["selected_block"]["pattern"],
                         "synchronized_mixed_orientation")

    def test_real_dimensional_shortages_never_become_seventeen_unit_fits(self):
        for length, width, expected in [(275.6, 94.4, 17),
                                         (275.599, 94.5, 16),
                                         (275.8, 94.399, 15)]:
            with self.subTest(length=length, width=width):
                placements, _, _ = self.fill_roof(self.roof_case(length=length, width=width))
                self.assertEqual(len(placements), expected)

    def test_supported_adaptive_partial_vertical_stacks_are_materialized_once(self):
        placements, stats, _ = self.fill_roof(self.roof_case(height=84, qty=27))
        self.assertEqual(len(placements), 27)
        self.assertEqual(stats["top_actions"][0]["selected_block"]["pattern"], "adaptive_mixed_lane")
        self.assertEqual({p.z for p in placements}, {10, 49.44})

    def test_unrelated_rectangles_partial_quantities_elevations_and_scale(self):
        families = [
            (29, 13, 4.1, (7, 4, 3), 100),  # short/wide, unequal tails
            (95.5, 12.5, 4, (13.5, 5.25, 3.5), 100),  # narrow/fractional
            (31, 21, 3, (5.5, 4.5, 2), 100),  # nearly square
            (18, 25, 4, (7, 4, 3), 17),
        ]
        for length, width, height, dims, quantity in families:
            base_count = None
            for scale in (0.5, 1, 25.4):
                with self.subTest(family=dims, scale=scale):
                    case = self.roof_case(length=length * scale, width=width * scale,
                        height=height * scale, dimensions=tuple(d * scale for d in dims),
                        qty=quantity, elevation=17 * scale)
                    placements, stats, _ = self.fill_roof(case)
                    self.assertGreater(len(placements), 0)
                    if base_count is None:
                        base_count = len(placements)
                    self.assertEqual(len(placements), base_count)
                    again, _, _ = self.fill_roof(case)
                    self.assertEqual(geometry_signature({"placements": placements}),
                                     geometry_signature({"placements": again}))
                    self.assertLess(stats["top_infill_block_candidates_evaluated"], 1000)
        for qty in (1, 2, 3, 7, 14, 15, 16, 17, 5000):
            with self.subTest(quantity=qty):
                placements, stats, _ = self.fill_roof(self.roof_case(qty=qty))
                self.assertEqual(len(placements), min(qty, 15))
                self.assertLess(stats["top_infill_block_candidates_evaluated"], 100)

    def test_rotation_families_and_disabled_rotations_are_enforced_on_roof(self):
        for flags, dims in [((True, False, False), (39.44, 63, 23.6)),
                            ((False, True, False), (63, 39.44, 23.6)),
                            ((False, False, True), (63, 23.6, 39.44)),
                            ((False, False, False), (63, 23.6, 39.44))]:
            with self.subTest(flags=flags):
                placements, _, _ = self.fill_roof(self.roof_case(dimensions=dims, flags=flags))
                self.assertEqual(len(placements), 15 if any(flags) else 0)

    def test_payload_sequence_and_nonstackable_foundations_remain_authoritative(self):
        placements, _, _ = self.fill_roof(self.roof_case(max_weight=3 + 7 * 2.5))
        self.assertEqual(len(placements), 7)
        placements, _, _ = self.fill_roof(self.roof_case(stackable=False))
        self.assertEqual(placements, [])
        case = self.roof_case()
        case[1][1]["sequence"] = 2
        placements, stats, _ = self.fill_roof(case, sequence_restricted=True)
        self.assertEqual(placements, [])
        self.assertTrue(all(reason["reason"] == "sequence_restriction"
                            for reason in stats["top_residual_evaluation_reasons"]))

    def test_mixed_support_union_and_real_gap_never_allow_overhang(self):
        selected_container, rows, _, x_start, x_end = self.roof_case()
        for gap in (0.0, 0.2):
            with self.subTest(gap=gap):
                supports = [
                    Placement("Foundation", 0, 0, 1, 3., True, 7., 3., 0., 137.75, 94.2, 10.),
                    Placement("Other foundation", 0, 2, 1, 0., True,
                              144.75 + gap, 3., 0., 137.75 - gap, 94.2, 10.),
                ]
                mixed_rows = rows + [product("Other foundation", 137.75 - gap, 94.2, 10, 1)]
                mixed_rows[0] = product("Foundation", 137.75, 94.2, 10, 1, weight=3)
                placements, _, _ = self.fill_roof((selected_container, mixed_rows, supports, x_start, x_end))
                self.assertEqual(len(placements), 15 if gap == 0 else 14)

    def test_complete_reconstructed_semitrailer_experiments_keep_physics_and_sequence(self):
        approved_changes = {
            (False, 3, FRONT_TO_BACK_INFILL_MODE): ([30, 17, 16, 48, 14, 4, 4], 15),
            (False, 4, FRONT_TO_BACK_INFILL_MODE): ([30, 17, 16, 48, 14, 4, 2], 1),
            (True, 3, SPACE_EVENLY_INFILL_MODE): ([30, 17, 16, 48, 14, 4, 4], 17),
            (True, 4, SPACE_EVENLY_INFILL_MODE): ([30, 17, 16, 48, 14, 4, 4], 17),
            (True, 4, FRONT_TO_BACK_INFILL_MODE): ([30, 17, 16, 48, 14, 4, 4], 17),
        }

        def count_b_on_a(outcome):
            foundations = [p for p in outcome["placements"] if p.row_index == 0]
            return sum(
                engine._frontier_supports_full_base(p, foundations)
                for p in outcome["placements"] if p.row_index == 1 and p.z > TOLERANCE
            )

        for perturbed in (False, True):
            for g_sequence in (3, 4):
                rows = semitrailer_roof_experiment(perturbed=perturbed, g_sequence=g_sequence)
                for mode in INFILL_MODES:
                    with self.subTest(perturbed=perturbed, g_sequence=g_sequence, mode=mode):
                        selected_container = container(mode, length=567, width=98.5, height=107)
                        result = engine._pack_container_compatible(selected_container, rows)
                        physical = assert_transport_result_physical(self, result, selected_container, rows)
                        if mode == SPACE_EVENLY_INFILL_MODE:
                            expected = [30, 17, 16, 44, 14, 4, 4] if perturbed else [30, 17, 13, 45, 14, 4, 4]
                        elif perturbed:
                            expected = [30, 17, 16, 48, 14, 4, 4 if g_sequence == 3 else 0]
                        else:
                            expected = [30, 17, 16, 36 if g_sequence == 3 else 44, 14, 4, 4 if g_sequence == 3 else 0]
                        self.assertEqual([physical["packed_by_row"].get(i, 0) for i in range(7)], expected)
                        self.assertEqual(count_b_on_a(result), 17 if perturbed else 15)
                        repeated = engine._pack_container_compatible(selected_container, rows)
                        self.assertEqual(geometry_signature(result), geometry_signature(repeated))
                        json.dumps({key: value for key, value in result.items()
                                    if "infill" in key})

                        public = pack_container(selected_container, rows)
                        public_physical = assert_transport_result_physical(self, public, selected_container, rows)
                        approved = approved_changes.get((perturbed, g_sequence, mode))
                        if approved is None:
                            self.assertEqual(geometry_signature(public), geometry_signature(result))
                        else:
                            public_counts, public_on_a = approved
                            self.assertEqual([public_physical["packed_by_row"].get(i, 0) for i in range(7)],
                                             public_counts)
                            self.assertEqual(count_b_on_a(public), public_on_a)
                            self.assertTrue(public[f"{mode}_supported_constructions"]["selected_policy"])


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
        mode = FRONT_TO_BACK_INFILL_MODE
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
                self.assertEqual(
                    {item.h for item in result["placements"] if item.row_index == 1},
                    {5.0},
                )
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
                r1=True,
            ),
            product("P2", 500, 400, 700, 100, r2=True, r1=True),
            product("P3", 500, 200, 700, 400, r2=True, r1=True),
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
                result = engine._pack_container_compatible(
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
                public = pack_container(selected_container, source, mode)
                physical = assert_transport_result_physical(self, public, selected_container, source)
                if mode == SPACE_EVENLY_INFILL_MODE:
                    self.assertEqual(result_count, 339)
                    self.assertEqual(physical["packed_by_row"], {0: 20, 1: 100, 2: 340})
                    self.assertEqual(public[f"{mode}_top_infill_units_by_product"].get("2"), 3)
                    self.assertFalse(any(
                        action["anchor_product"] == "P3" and action["filler_product"] == "P3"
                        and action["anchor_eligible"] for action in public[f"{mode}_top_actions"]
                    ))
                    self.assertTrue(public[f"{mode}_supported_constructions"]["selected_policy"])
                else:
                    self.assertEqual(geometry_signature(public), geometry_signature(result))

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


class SupportBedConstructionTests(SimpleTestCase):
    """TC-REG-017: construct useful beds before committing a cap to the floor."""

    def small_case(self, *, scale=1, quantity=10, upper_sequence=3, lower_sequence=3):
        selected = {"L": 63 * scale, "W": 47.2 * scale, "H": 108 * scale,
                    "max_weight": None}
        rows = [
            product("Foundation", 31.5 * scale, 47.2 * scale, 15.7 * scale,
                    quantity, sequence=lower_sequence, weight=2),
            product("Cap", 47.2 * scale, 47.2 * scale, 21.7 * scale, 1,
                    sequence=upper_sequence, weight=20, stackable=False),
        ]
        return selected, rows

    def checked(self, selected, rows, mode):
        result = pack_container(selected, rows, mode)
        physical = assert_transport_result_physical(self, result, selected, rows)
        json.dumps({k: v for k, v in result.items() if "infill" in k}, allow_nan=False)
        return result, physical["packed_by_row"]

    def test_expv2_2_loads_all_133_in_both_mixed_modes(self):
        selected, rows = stackability_expv2_2()
        expected_before = {
            FRONT_TO_BACK_INFILL_MODE: [30, 17, 16, 18, 14, 4, 4],
            SPACE_EVENLY_INFILL_MODE: [30, 17, 0, 36, 14, 4, 4],
        }
        for mode in INFILL_MODES:
            with self.subTest(mode=mode):
                ordinary = engine._pack_container_blocks(selected, rows, mode)
                before = Counter(p.row_index for p in ordinary["placements"])
                self.assertEqual([before[i] for i in range(7)], expected_before[mode])
                result, counts = self.checked(selected, rows, mode)
                self.assertEqual([counts[i] for i in range(7)], [30, 17, 16, 48, 14, 4, 4])
                self.assertEqual(result["unplaced"], [])
                self.assertTrue(result[f"{mode}_support_beds"]["selected"])
                self.assertTrue(all(p.z > 0 for p in result["placements"] if p.row_index == 4))
                self.assertEqual(geometry_signature(result), geometry_signature(pack_container(selected, rows, mode)))

    def test_full_supported_module_and_scaled_fractional_geometry(self):
        for scale in (1, 25.4, 3.7):
            selected, rows = self.small_case(scale=scale)
            for mode in INFILL_MODES:
                with self.subTest(scale=scale, mode=mode):
                    result, counts = self.checked(selected, rows, mode)
                    self.assertEqual(counts, {0: 10, 1: 1})
                    cap = next(p for p in result["placements"] if p.row_index == 1)
                    self.assertAlmostEqual(cap.z / scale, 78.5)
                    self.assertAlmostEqual(cap.z / scale + cap.h / scale, 100.2)
                    self.assertTrue(engine._frontier_supports_full_base(cap, result["placements"]))

    def test_unrelated_dimensions_find_an_independent_support_bed(self):
        selected = {"L": 60, "W": 40, "H": 50}
        rows = [product("Small", 30, 40, 10, 4),
                product("Upper", 50, 40, 15, 1, stackable=False)]
        for mode in INFILL_MODES:
            result, counts = self.checked(selected, rows, mode)
            self.assertEqual(counts, {0: 4, 1: 1})
            self.assertTrue(result[f"{mode}_support_beds"]["selected"])

    def test_compound_window_runs_existing_top_closure_before_advancing(self):
        selected, rows = self.small_case()
        rows.append(product("Tail filler", 15.7, 47.2, 10, 1, sequence=3))
        for mode in INFILL_MODES:
            with self.subTest(mode=mode):
                result, counts = self.checked(selected, rows, mode)
                self.assertEqual(counts, {0: 10, 1: 1, 2: 1})
                self.assertEqual(result[f"{mode}_top_infill_units_by_product"], {"2": 1})

    def test_real_height_and_quantity_shortages_do_not_float_or_invent_units(self):
        for quantity, height in ((1, 108), (10, 30), (10, 100.19)):
            selected, rows = self.small_case(quantity=quantity)
            selected["H"] = height
            for mode in INFILL_MODES:
                with self.subTest(quantity=quantity, height=height, mode=mode):
                    result, _ = self.checked(selected, rows, mode)
                    self.assertTrue(result["unplaced"])

    def test_nonstackable_foundations_and_disabled_orientations_are_rejected(self):
        selected, rows = self.small_case()
        for changes in ({"stackable": False}, {"r1": False, "r2": False, "r3": False}):
            source = [{**rows[0], **changes}, dict(rows[1])]
            for mode in INFILL_MODES:
                _, counts = self.checked(selected, source, mode)
                self.assertEqual(counts.get(0, 0), 0)
                self.assertEqual(counts.get(1, 0), 1)

    def test_progressive_does_not_synthesize_cross_sequence_beds(self):
        selected, rows = self.small_case(lower_sequence=4, upper_sequence=3)
        _, counts = self.checked(selected, rows, FRONT_TO_BACK_INFILL_MODE)
        self.assertEqual(counts, {1: 1})
        _, counts = self.checked(selected, rows, SPACE_EVENLY_INFILL_MODE)
        self.assertEqual(counts, {0: 10, 1: 1})

    def test_stackability_and_easycargo_sequence_variations_preserve_each_row(self):
        overrides = ({}, {1: True}, {4: True}, {3: False}, {5: False, 6: False})
        for easycargo in (False, True):
            for flags in overrides:
                selected, rows = stackability_expv2_2(
                    easycargo_sequences=easycargo, stackable_overrides=flags)
                for mode in INFILL_MODES:
                    with self.subTest(easycargo=easycargo, flags=flags, mode=mode):
                        ordinary = engine._pack_container_blocks(selected, rows, mode)
                        before = Counter(p.row_index for p in ordinary["placements"])
                        result, after = self.checked(selected, rows, mode)
                        self.assertTrue(all(after.get(i, 0) >= before[i] for i in range(7)))
                        if mode == FRONT_TO_BACK_INFILL_MODE:
                            sequences = {i: row["sequence"] for i, row in enumerate(rows)}
                            for action in result.get(f"{mode}_support_beds", {}).get("actions", []):
                                self.assertEqual(sequences[action["foundation_row_index"]],
                                                 sequences[action["upper_row_index"]])

    def test_old_residual_fixture_stackability_variations_never_lose_a_row(self):
        for disabled in ((0,), (1,), (2,), (0, 2)):
            rows = [product("P1", 1200, 800, 1100, 20),
                    product("P2", 500, 400, 700, 100),
                    product("P3", 500, 200, 700, 130)]
            for index in disabled:
                rows[index]["stackable"] = False
            selected = {"L": 12032, "W": 2352, "H": 2395, "max_weight": None}
            for mode in INFILL_MODES:
                ordinary = engine._pack_container_blocks(selected, rows, mode)
                before = Counter(p.row_index for p in ordinary["placements"])
                _, after = self.checked(selected, rows, mode)
                self.assertTrue(all(after.get(row, 0) >= qty for row, qty in before.items()))

    def test_configured_payload_still_limits_actual_committed_cargo(self):
        selected, rows = self.small_case()
        selected["max_weight"] = 39
        for mode in INFILL_MODES:
            result, counts = self.checked(selected, rows, mode)
            self.assertLessEqual(result["loaded_weight"], 39 + TOLERANCE)
            self.assertLess(counts.get(0, 0), 10)

    def test_candidate_budget_and_large_requests_have_safe_fallbacks(self):
        for quantity in (10, 5000):
            selected, rows = self.small_case(quantity=quantity)
            for mode in INFILL_MODES:
                result, _ = self.checked(selected, rows, mode)
                diagnostic = result[f"{mode}_support_beds"]
                self.assertLessEqual(diagnostic["candidates_evaluated"], engine.SUPPORT_BED_CANDIDATE_CAP)
                for action in diagnostic["actions"]:
                    self.assertLessEqual(sum(action["units_by_product"].values()), engine.SUPPORT_BED_PLACEMENT_CAP)
        selected, rows = self.small_case()
        with patch.object(engine, "SUPPORT_BED_CANDIDATE_CAP", 0):
            for mode in INFILL_MODES:
                result, counts = self.checked(selected, rows, mode)
                self.assertEqual(counts, {1: 1})
                self.assertFalse(result[f"{mode}_support_beds"]["selected"])

    def test_row_loss_rejects_even_a_larger_trial_and_equal_counts_keep_geometry(self):
        selected, rows = self.small_case()
        baseline = engine._pack_container_blocks(selected, rows, FRONT_TO_BACK_INFILL_MODE)
        trial = {**baseline, "placements": [Placement("Foundation", i, 0, 3, 2, True,
                  0, 0, i * 15.7, 31.5, 47.2, 15.7) for i in range(2)],
                 f"{FRONT_TO_BACK_INFILL_MODE}_support_beds": engine._new_support_bed_stats()}
        with patch.object(engine, "_pack_container_blocks", side_effect=[baseline, trial, trial, trial]):
            result = engine._pack_container_compatible(selected, rows, FRONT_TO_BACK_INFILL_MODE)
        self.assertEqual(geometry_signature(result), geometry_signature(baseline))
        self.assertFalse(result[f"{FRONT_TO_BACK_INFILL_MODE}_support_beds"]["selected"])
        equal = {**baseline, f"{FRONT_TO_BACK_INFILL_MODE}_support_beds": engine._new_support_bed_stats()}
        with patch.object(engine, "_pack_container_blocks", side_effect=[baseline, equal, equal, equal]):
            result = engine._pack_container_compatible(selected, rows, FRONT_TO_BACK_INFILL_MODE)
        self.assertEqual(geometry_signature(result), geometry_signature(baseline))

    def test_complete_loads_and_baseline_modes_do_not_run_support_trials(self):
        selected, rows = self.small_case()
        for mode in (FRONT_TO_BACK_MODE, SPACE_EVENLY_MODE):
            ordinary = engine._pack_container_blocks(selected, rows, mode)
            result = pack_container(selected, rows, mode)
            self.assertEqual(geometry_signature(result), geometry_signature(ordinary))
            self.assertFalse(any("support_beds" in key for key in result))
        rows[1]["qty"] = 0
        for mode in INFILL_MODES:
            with patch.object(engine, "_choose_support_bed", side_effect=AssertionError("unexpected search")):
                self.checked(selected, rows, mode)


class PartialSupportBedConstructionTests(SimpleTestCase):
    """TC-REG-019: bounded partial caps; the separate 123 target stays explicit."""

    def small_case(self, family="r3", *, height=40, payload=None, quantity=5):
        lower, upper = {
            "r3": ((20, 30, 20), (35, 30, 10)),
            "r1": ((20, 20, 30), (10, 35, 30)),
            "r2": ((20, 20, 30), (35, 10, 30)),
        }[family]
        flags = {key: key == family for key in ("r1", "r2", "r3")}
        return {"L": 100, "W": 40, "H": height, "max_weight": payload}, [
            product("Lower", *lower, 8, weight=1, **flags),
            product("Upper", *upper, quantity, weight=1, stackable=False, **flags),
        ]

    def checked(self, selected, rows, mode):
        incumbent = engine._pack_container_approved(selected, rows, mode)
        result = pack_container(selected, rows, mode)
        physical = assert_transport_result_physical(self, result, selected, rows)
        before = Counter(p.row_index for p in incumbent["placements"])
        self.assertTrue(all(physical["packed_by_row"].get(i, 0) >= before[i] for i in range(len(rows))))
        json.dumps({k: v for k, v in result.items() if "infill" in k}, allow_nan=False)
        return result, physical["packed_by_row"]

    def test_r3_reference_adds_supported_b_without_losing_any_row(self):
        selected, rows = mixed_support_orientation_case()
        self.assertAlmostEqual(rows[0]["length"], 15.7 * 25.4)
        self.assertAlmostEqual(rows[0]["width"], 55.1 * 25.4)
        self.assertFalse(rows[1]["stackable"])
        for mode in (FRONT_TO_BACK_INFILL_MODE,):
            with self.subTest(mode=mode):
                result, counts = self.checked(selected, rows, mode)
                self.assertGreater(len(result["placements"]), 53)
                self.assertTrue(result[f"{mode}_partial_support_beds"]["selected"])
                a = [p for p in result["placements"] if p.row_index == 0]
                b = [p for p in result["placements"] if p.row_index == 1 and p.z > 0]
                self.assertGreater(len(b), 0)
                self.assertTrue(all(not p.stackable for p in b))
                self.assertTrue(all(engine._frontier_supports_full_base(p, a) for p in b))
                self.assertEqual(counts[1], 17)
                self.assertEqual(geometry_signature(result), geometry_signature(pack_container(selected, rows, mode)))

    def test_all_rotations_preserve_saved_baseline_modes_and_each_mixed_row(self):
        path = Path(__file__).resolve().parents[2] / "regressions/TC-REG-019-mixed-cargo-support-bed-orientation/implementation/reference-before.json.gz"
        for before in json.loads(gzip.decompress(path.read_bytes())):
            with self.subTest(flags=before["flags"], mode=before["mode"]):
                result, counts = self.checked(before["container"], before["products"], before["mode"])
                self.assertTrue(all(counts.get(i, 0) >= qty for i, qty in enumerate(before["counts"])))
                if before["mode"] in (SPACE_EVENLY_MODE, FRONT_TO_BACK_MODE):
                    # Compare all placement fields, including names, flags, weight and indices.
                    from dataclasses import asdict
                    encoded = json.dumps([asdict(p) for p in result["placements"]], sort_keys=True,
                                         separators=(",", ":"), allow_nan=False).encode()
                    self.assertEqual(hashlib.sha256(encoded).hexdigest(), before["signature_sha256"])

    def test_partial_caps_work_in_each_vertical_family_and_at_other_scales(self):
        for family in ("r1", "r2", "r3"):
            for scale in (1, 3.7, 25.4):
                selected, rows = self.small_case(family)
                selected = {**selected, **{key: selected[key] * scale for key in ("L", "W", "H")}}
                rows = [{**row, **{key: row[key] * scale for key in ("length", "width", "height")}} for row in rows]
                for mode in INFILL_MODES:
                    with self.subTest(family=family, scale=scale, mode=mode):
                        result, counts = self.checked(selected, rows, mode)
                        self.assertGreaterEqual(counts.get(0, 0), 2)
                        self.assertEqual(counts[1], 3)
                        self.assertTrue(any(p.row_index == 1 and p.z > 0 for p in result["placements"]))

    def test_projection_is_a_ranking_estimate_and_both_policies_remain_available(self):
        selected, rows = self.small_case()
        normalized = engine.normalize_products(rows)
        products = engine.sort_products(normalized, selected)
        self.assertEqual(engine._support_bed_tail_depth(products, {0: 8, 1: 5}, selected), 210)
        self.assertEqual(40 + engine._support_bed_tail_depth(products, {0: 6, 1: 4}, selected), 220)
        for policy in ("projected", "compact"):
            plan, attempted = engine._choose_partial_support_bed(
                normalized[1], products, {0: 8, 1: 5}, {0: 0, 1: 0}, selected,
                0, 0, False, [], policy=policy,
            )
            self.assertIsNotNone(plan)
            self.assertGreater(plan["usage"][1], 0)
            self.assertLess(plan["usage"][1], 5)
            self.assertLessEqual(attempted, engine.SUPPORT_BED_CANDIDATE_CAP)
        result, _ = self.checked(selected, rows, FRONT_TO_BACK_INFILL_MODE)
        self.assertEqual([t["policy"] for t in result[f"{FRONT_TO_BACK_INFILL_MODE}_partial_support_beds"]["trials"]],
                         ["projected", "compact"])

    def test_unrelated_aspect_ratio_and_multiple_eligible_supporters(self):
        selected = {"L": 72, "W": 27, "H": 34}
        rows = [product("Lower", 14, 22, 15, 7, weight=1),
                product("Upper", 25, 22, 9, 5, weight=1, stackable=False)]
        for mode in INFILL_MODES:
            _, counts = self.checked(selected, rows, mode)
            self.assertGreaterEqual(counts.get(0, 0), 2)
            self.assertEqual(counts[1], 3)
        selected, rows = self.small_case()
        rows.append(product("Other lower", 18, 32, 12, 4, weight=1))
        for mode in INFILL_MODES:
            result, counts = self.checked(selected, rows, mode)
            self.assertEqual(counts[1], 3)
            self.assertGreaterEqual(counts.get(0, 0) + counts.get(2, 0), 2)
            assert_transport_result_physical(self, result, selected, rows)

    def test_height_payload_sequence_and_foundation_shortages_stay_authoritative(self):
        for mode in INFILL_MODES:
            for height, payload, lower_qty, sequence, expected in (
                (29, None, 8, 1, {1: 3}), (30, None, 8, 1, None),
                (40, 3, 8, 1, {1: 3}), (40, 5, 8, 1, {0: 2, 1: 3}),
                (40, None, 1, 1, {1: 3}), (40, None, 8, 2, None),
            ):
                with self.subTest(mode=mode, height=height, payload=payload, quantity=lower_qty, sequence=sequence):
                    selected, rows = self.small_case(height=height, payload=payload)
                    rows[0].update(qty=lower_qty, sequence=sequence)
                    _, counts = self.checked(selected, rows, mode)
                    if expected is not None:
                        self.assertEqual(counts, expected)
                    elif sequence == 2 and mode == FRONT_TO_BACK_INFILL_MODE:
                        self.assertEqual(counts, {1: 3})
                    else:
                        self.assertGreaterEqual(counts.get(0, 0), 2)
                        self.assertEqual(counts[1], 3)

    def test_complete_requests_and_zero_budget_keep_the_approved_geometry(self):
        for quantity in (1, 2, 3, 7, 5000):
            selected, rows = self.small_case(quantity=quantity)
            for mode in INFILL_MODES:
                result, _ = self.checked(selected, rows, mode)
                for trial in result.get(f"{mode}_partial_support_beds", {}).get("trials", []):
                    self.assertLessEqual(trial["support_beds"]["candidates_evaluated"], engine.SUPPORT_BED_CANDIDATE_CAP)
                    for action in trial["support_beds"]["actions"]:
                        self.assertLessEqual(sum(action["units_by_product"].values()), engine.SUPPORT_BED_PLACEMENT_CAP)
        selected, rows = self.small_case(quantity=1)
        with patch.object(engine, "_choose_partial_support_bed", side_effect=AssertionError("complete outcome searched")):
            for mode in INFILL_MODES:
                self.checked(selected, rows, mode)
        selected, rows = self.small_case()
        with patch.object(engine, "SUPPORT_BED_CANDIDATE_CAP", 0):
            for mode in INFILL_MODES:
                result = pack_container(selected, rows, mode)
                self.assertEqual(geometry_signature(result), geometry_signature(engine._pack_container_approved(selected, rows, mode)))

    def test_whole_outcome_validation_rejects_gaps_flags_rotations_and_payload(self):
        selected, rows = self.small_case()
        def outcome(placements):
            counts = Counter(p.row_index for p in placements)
            return {"packing_mode": FRONT_TO_BACK_INFILL_MODE, "placements": placements,
                    "loaded_weight": sum(p.weight for p in placements),
                    "unplaced": [{"row_index": i} for i, row in enumerate(rows) for _ in range(row["qty"] - counts[i])]}
        adjacent = [Placement("Lower", i, 0, 1, 1, True, i * 20, 0, 0, 20, 30, 20) for i in range(2)]
        upper = Placement("Upper", 0, 1, 1, 1, False, 0, 0, 20, 35, 30, 10)
        normalized = engine.normalize_products(rows)
        self.assertIsNone(engine._partial_support_bed_outcome_reason(outcome(adjacent + [upper]), selected, normalized))
        from dataclasses import replace
        gap = [adjacent[0], replace(adjacent[1], x=30), upper]
        self.assertEqual(engine._partial_support_bed_outcome_reason(outcome(gap), selected, normalized), "unsupported_elevated_placement")
        self.assertEqual(engine._partial_support_bed_outcome_reason(outcome(adjacent + [replace(upper, stackable=True)]), selected, normalized),
                         "product_identity_or_sequence_mismatch")
        self.assertEqual(engine._partial_support_bed_outcome_reason(outcome(adjacent + [replace(upper, h=11)]), selected, normalized),
                         "forbidden_orientation")
        self.assertEqual(engine._partial_support_bed_outcome_reason(outcome(adjacent + [upper]), {**selected, "max_weight": 2}, normalized),
                         "payload_exceeded")

    def test_valid_larger_row_losing_trial_and_equal_total_keep_exact_incumbent(self):
        from dataclasses import replace
        selected, rows = self.small_case()
        mode = FRONT_TO_BACK_INFILL_MODE
        incumbent = engine._pack_container_approved(selected, rows, mode)
        lower = [Placement("Lower", i, 0, 1, 1, True, i * 20, 0, 0, 20, 30, 20) for i in range(4)]
        lower += [Placement("Lower", i + 4, 0, 1, 1, True, 80, 0, i * 20, 20, 30, 20) for i in range(2)]
        upper = [Placement("Upper", i, 1, 1, 1, False, i * 35, 0, 20, 35, 30, 10) for i in range(2)]
        losing = {**incumbent, "placements": lower + upper, "loaded_weight": 8,
                  "unplaced": [{"row_index": i} for i, qty in ((0, 2), (1, 3)) for _ in range(qty)],
                  f"{mode}_support_beds": engine._new_support_bed_stats()}
        self.assertIsNone(engine._partial_support_bed_outcome_reason(losing, selected, engine.normalize_products(rows)))
        equal = {**incumbent, "placements": [replace(p, x=p.x + 1) for p in incumbent["placements"]]}
        self.assertIsNone(engine._partial_support_bed_outcome_reason(equal, selected, engine.normalize_products(rows)))
        for trial, reason in ((losing, "row_quantity_reduced"), (equal, "no_total_quantity_improvement")):
            with patch.object(engine, "_pack_container_approved", return_value=incumbent), \
                    patch.object(engine, "_pack_container_blocks", side_effect=[trial, trial]):
                result = engine._pack_container_compatible(selected, rows, mode)
            self.assertEqual(geometry_signature(result), geometry_signature(incumbent))
            self.assertTrue(all(t["rejection_reason"] == reason for t in result[f"{mode}_partial_support_beds"]["trials"]))


class SupportedConstructionTests(SimpleTestCase):
    """TC-REG-019 follow-up: unchanged inputs, local role choice and staged support."""

    def test_reference_matrix_preserves_rows_and_falls_back_to_exact_geometry(self):
        baseline = Path(__file__).resolve().parents[2] / (
            "regressions/TC-REG-019-mixed-cargo-support-bed-orientation/generalized/before.json.gz"
        )
        records = json.loads(gzip.decompress(baseline.read_bytes()))["cases"]
        for b, e in flag_product((False, True), repeat=2):
            for size in (1, 2, 3):
                for flags in combinations(("r1", "r2", "r3"), size):
                    selected, rows = mixed_support_orientation_case(flags)
                    rows[1]["stackable"], rows[4]["stackable"] = b, e
                    for mode in (FRONT_TO_BACK_MODE, SPACE_EVENLY_MODE, *INFILL_MODES):
                        key = f"{int(b)}{int(e)}/{'-'.join(flags)}/{mode}"
                        with self.subTest(key=key):
                            before = records[key]
                            result = pack_container(selected, rows, mode)
                            physical = assert_transport_result_physical(self, result, selected, rows)
                            total = len(result["placements"])
                            counts = physical["packed_by_row"]
                            self.assertTrue(all(counts.get(i, 0) >= qty
                                                for i, qty in enumerate(before["counts"])))
                            if mode not in INFILL_MODES or total == sum(before["counts"]):
                                encoded = json.dumps(
                                    [asdict(p) for p in result["placements"]], sort_keys=True,
                                    separators=(",", ":"), allow_nan=False,
                                ).encode()
                                self.assertEqual(hashlib.sha256(encoded).hexdigest(), before["signature"])
                            if flags == ("r3",) and mode == FRONT_TO_BACK_INFILL_MODE:
                                self.assertGreaterEqual(total, 123)
                                self.assertTrue(all(p.stackable == rows[p.row_index]["stackable"]
                                                    for p in result["placements"]))
                                stats = result[f"{mode}_supported_constructions"]
                                self.assertLessEqual(sum(t["support_beds"]["candidates_evaluated"]
                                                         for t in stats["trials"]), 1024)
                                if b and e:
                                    foundations = [p for p in result["placements"] if p.row_index == 0]
                                    self.assertEqual(sum(
                                        engine._frontier_supports_full_base(p, foundations)
                                        for p in result["placements"] if p.row_index == 1 and p.z > TOLERANCE
                                    ), 15)

    def test_both_current_row_roles_with_independent_rotation_families(self):
        for scale in (1, 3.7):
            selected = {"L": 100 * scale, "W": 40 * scale, "H": 40 * scale}
            products = normalize_products([
                product("Crates", 20 * scale, 20 * scale, 30 * scale, 8, r2=True, r3=False, weight=1),
                product("Cases", 10 * scale, 35 * scale, 30 * scale, 5, r1=True, r3=False, weight=1),
            ])
            for anchor, policy in zip(products, engine.SUPPORTED_CONSTRUCTION_POLICIES[::-1]):
                with self.subTest(scale=scale, anchor=anchor.name):
                    search = {"remaining_attempts": 256, "policy": policy,
                              "roof_blocks": {}, "tail_depths": {}}
                    args = (anchor, products, {0: 8, 1: 5}, {0: 0, 1: 0}, selected)
                    trial, attempted = engine._choose_supported_construction(*args, 0, 0, True, [], search=search)
                    self.assertGreater(attempted, 0)
                    self.assertIsNotNone(trial)
                    self.assertEqual((trial["foundation_row_index"], trial["upper_row_index"]), (0, 1))
                    upper = [p for p in trial["placements"] if p.row_index == 1]
                    self.assertTrue(all(p.stackable and p.h == 10 * scale and p.z >= 20 * scale for p in upper))
                    self.assertTrue(all(p.h == 20 * scale for p in trial["placements"] if p.row_index == 0))

    def test_middle_coplanar_union_reserves_upper_quantity_and_payload(self):
        upper, middle = normalize_products([
            product("Cases", 30, 30, 10, 3, weight=2),
            product("Inserts", 15, 30, 10, 4, weight=1),
        ])
        roof = Space(0, 0, 16, 60, 30, 24)
        search = {"roof_blocks": {}}
        args = (search, upper, roof, 3, [middle], {0: 3, 1: 4}, {0: 0, 1: 0})
        for payload, expected_middle in ((10, 2), (9, 0)):
            with self.subTest(payload=payload):
                units, usage = engine._stage_supported_roof(
                    *args, {"max_weight": payload}, 2, 512, partial=False,
                )
                self.assertEqual(usage[middle.row_index], expected_middle)
                if expected_middle:
                    inserts = [p for p in units if p.row_index == middle.row_index]
                    cases = [p for p in units if p.row_index == upper.row_index]
                    self.assertEqual(len(cases), 3)
                    staged = next(p for p in cases if p.z == 26 and
                                  engine._frontier_supports_full_base(p, inserts))
                    self.assertFalse(engine._frontier_supports_full_base(staged, inserts[:1]))
                    self.assertTrue(engine._frontier_supports_full_base(staged, inserts))
