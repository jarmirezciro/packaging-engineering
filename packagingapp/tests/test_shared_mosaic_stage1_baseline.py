import json
from pathlib import Path

from django.test import SimpleTestCase

from packagingapp.tests.build_shared_mosaic_stage1_baseline import (
    FIXTURE_PATH,
    build_baseline,
)


class SharedMosaicStage1BaselineTests(SimpleTestCase):
    """Container defaults must retain the approved Stage 1 search contract."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.expected = json.loads(Path(FIXTURE_PATH).read_text(encoding="utf-8"))
        cls.actual = build_baseline()

    def test_candidate_enumeration_is_unchanged(self):
        self.assertEqual(
            self.actual["enumerations"],
            self.expected["enumerations"],
        )

    def test_container_selection_is_unchanged(self):
        self.assertEqual(
            self.actual["container_selections"],
            self.expected["container_selections"],
        )

    def test_fixture_metadata_is_locked(self):
        self.assertEqual(self.actual["metadata"], self.expected["metadata"])
