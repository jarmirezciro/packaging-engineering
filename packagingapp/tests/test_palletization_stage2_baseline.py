import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from packagingapp.tests.build_palletization_stage2_baseline import (
    FIXTURE_PATH,
    build_baseline,
)
from packagingapp.utils.palletization import engine


# Explicit deltas for the calibrated Palletization policy. The compatibility
# run still checks every original placement and result against the frozen file.
CALIBRATED_NESTED_QUANTITIES = {
    "splitrow_na4840": {"nested_pinwheel": 0},
    "splitrow_compact_filler": {"nested_pinwheel": 0},
    "splitrow_sparse_362": {"nested_pinwheel": 0},
    "elongated_carton": {"nested_pinwheel": 0},
    "fractional": {"nested_pinwheel": 0, "nested_pinwheel_rotated": 0},
    "beyond_shared_parameter_cap": {"nested_pinwheel": 0, "nested_pinwheel_rotated": 0},
    "equal_count_alternatives": {"nested_pinwheel": 0, "nested_pinwheel_rotated": 24},
}
REMOVED_NESTED_ANALYSIS_QUANTITIES = {
    "na4840_splitrow": 18,
    "fractional_dimensions": 24,
}
# PAL-REG-003: explicit policy deltas, never replacements for the frozen file.
# Split margin bands, staggered right fillers, and sub-60% fallback cores are
# ineligible. Coherent lower-count cores remain available where relevant.
CALIBRATED_HYBRID_QUANTITIES = {
    "splitrow_tops": {"hybrid_pinwheel": 0},
    "splitrow_na4840": {"hybrid_pinwheel_rotated": 0},
    "splitrow_compact_filler": {"hybrid_pinwheel": 20},
    "splitrow_sparse_362": {"hybrid_pinwheel": 16},
    "splitrow_sparse_364": {"hybrid_pinwheel": 0},
    "container_reference": {"hybrid_pinwheel": 0},
    "near_square_carton": {"hybrid_pinwheel": 0, "hybrid_pinwheel_rotated": 0},
    "beyond_shared_parameter_cap": {"hybrid_pinwheel": 340},
    "significant_residual": {"hybrid_pinwheel": 0},
}
REMOVED_HYBRID_ANALYSIS_QUANTITIES = {
    "tops_splitrow_overhang": 8,
    "container_reference_geometry": 5,
}


class PalletizationStage2BaselineTests(SimpleTestCase):
    """Exact ordered-geometry and customer-contract migration baseline."""

    maxDiff = 4000

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.expected = json.loads(Path(FIXTURE_PATH).read_text(encoding="utf-8"))
        cls.actual = build_baseline()
        compatibility_policy = replace(
            engine.PALLETIZATION_SEARCH_POLICY,
            require_compact_nested_pinwheel=False, require_coherent_hybrid_pinwheel=False,
        )
        with patch.object(engine, "PALLETIZATION_SEARCH_POLICY", compatibility_policy):
            cls.compatibility = build_baseline()

    def test_pattern_geometry_matches_pre_migration_fixture(self):
        self.assertEqual(
            self.compatibility["pattern_scenarios"],
            self.expected["pattern_scenarios"],
        )

    def test_full_analysis_and_customer_contract_match_pre_migration_fixture(self):
        self.assertEqual(
            self.compatibility["analysis_scenarios"],
            self.expected["analysis_scenarios"],
        )

    def test_calibrated_patterns_have_only_the_expected_policy_deltas(self):
        actual = deepcopy(self.actual["pattern_scenarios"])
        for before, after in zip(self.expected["pattern_scenarios"], actual, strict=True):
            with self.subTest(scenario=before["name"]):
                deltas = {
                    **CALIBRATED_NESTED_QUANTITIES.get(before["name"], {}),
                    **CALIBRATED_HYBRID_QUANTITIES.get(before["name"], {}),
                }
                for variant, count in deltas.items():
                    self.assertEqual(after["variants"][variant]["quantity"], count)
                    self.assertNotEqual(after["variants"][variant], before["variants"][variant])
                    after["variants"][variant] = before["variants"][variant]
                self.assertEqual(after, before)

    def test_calibrated_analysis_preserves_remaining_customer_contract(self):
        expected = deepcopy(self.expected["analysis_scenarios"])
        for scenario in expected:
            for family, removals in (
                ("Nested pinwheel", REMOVED_NESTED_ANALYSIS_QUANTITIES),
                ("Hybrid pinwheel", REMOVED_HYBRID_ANALYSIS_QUANTITIES),
            ):
                if scenario["name"] not in removals:
                    continue
                removed_rows = [row for row in scenario["rows"] if row["metrics"]["pattern"] == family]
                self.assertEqual(
                    [row["metrics"]["boxes_layer_A"] for row in removed_rows],
                    [removals[scenario["name"]]],
                )
                scenario["rows"] = [row for row in scenario["rows"] if row not in removed_rows]
                table = scenario["serialized_result"]["results_table"]
                scenario["serialized_result"]["results_table"] = [row for row in table if row["pattern"] != family]
        self.assertEqual(self.actual["analysis_scenarios"], expected)

    def test_fixture_records_the_locked_source_and_complete_matrix(self):
        self.assertEqual(self.actual["metadata"], self.expected["metadata"])
        self.assertEqual(self.expected["metadata"]["pattern_scenario_count"], 19)
        self.assertEqual(self.expected["metadata"]["analysis_scenario_count"], 7)
