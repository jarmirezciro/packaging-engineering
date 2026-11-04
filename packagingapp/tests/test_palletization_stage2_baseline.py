import json
from pathlib import Path

from django.test import SimpleTestCase

from packagingapp.tests.build_palletization_stage2_baseline import (
    FIXTURE_PATH,
    build_baseline,
)


class PalletizationStage2BaselineTests(SimpleTestCase):
    """Exact ordered-geometry and customer-contract migration baseline."""

    maxDiff = 4000

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.expected = json.loads(Path(FIXTURE_PATH).read_text(encoding="utf-8"))
        cls.actual = build_baseline()

    def test_pattern_geometry_matches_pre_migration_fixture(self):
        self.assertEqual(
            self.actual["pattern_scenarios"],
            self.expected["pattern_scenarios"],
        )

    def test_full_analysis_and_customer_contract_match_pre_migration_fixture(self):
        self.assertEqual(
            self.actual["analysis_scenarios"],
            self.expected["analysis_scenarios"],
        )

    def test_fixture_records_the_locked_source_and_complete_matrix(self):
        self.assertEqual(self.actual["metadata"], self.expected["metadata"])
        self.assertEqual(self.expected["metadata"]["pattern_scenario_count"], 19)
        self.assertEqual(self.expected["metadata"]["analysis_scenario_count"], 7)
