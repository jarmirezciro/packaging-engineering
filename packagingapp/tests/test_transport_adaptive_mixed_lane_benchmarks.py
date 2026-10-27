from collections import Counter
from copy import deepcopy
import json

from django.test import SimpleTestCase

from packagingapp.tests.transport_physical_validator import (
    assert_transport_result_physical,
)
from packagingapp.tools.transport.case_presets import (
    get_transport_container_case_preset,
)
from packagingapp.tools.transport.modes import (
    FRONT_TO_BACK_INFILL_MODE,
    FRONT_TO_BACK_MODE,
    SPACE_EVENLY_INFILL_MODE,
    SPACE_EVENLY_MODE,
)
from packagingapp.utils.container_tool.engine import pack_container


TOPS_CONTAINER = {
    "L": 12039.6,
    "W": 2362.2,
    "H": 2692.4,
    "max_weight": None,
}
TOPS_MODES = (
    FRONT_TO_BACK_MODE,
    FRONT_TO_BACK_INFILL_MODE,
    SPACE_EVENLY_MODE,
    SPACE_EVENLY_INFILL_MODE,
)
TOPS_QUANTITIES = {
    "original": (375, 405, 288, 160, 0),
    "optimized": (400, 405, 288, 160, 32),
    "probe_a": (434, 405, 288, 160, 32),
    "probe_b": (400, 405, 288, 160, 40),
}

# The first four rows come from the route's checked-in public preset. The
# checked-in optimized result image supplies P5's dimensions, weight,
# stackability and sequence, but does not expose its rotation checkboxes. R1
# only is therefore an explicit reconstruction assumption, matching every row
# in the canonical preset; the regression report retains this provenance gap.
TOPS_P5_RECONSTRUCTION = {
    "name": "Case 1",
    "length": 558.8,
    "width": 406.4,
    "height": 317.5,
    "qty": 0,
    "max_qty": False,
    "stackable": True,
    "weight": 4.54,
    "sequence": 1,
    "r1": True,
    "r2": False,
    "r3": False,
}


def tops_rows(quantities):
    preset = get_transport_container_case_preset(
        "tops-max-load-high-cube-benchmark"
    )
    rows = deepcopy(preset["rows"])
    if quantities[4]:
        rows.append(deepcopy(TOPS_P5_RECONSTRUCTION))
    for row, quantity in zip(rows, quantities):
        row["qty"] = quantity
    return rows


class TopsAdaptiveMixedLaneBenchmarkTests(SimpleTestCase):
    def test_all_four_manifests_run_independently_in_all_active_modes(self):
        # These are KolliPack regression outcomes for the exact test fixture,
        # not assertions about what TOPS itself must pack.
        expected_loaded = {
            "original": {
                FRONT_TO_BACK_MODE: 1228,
                FRONT_TO_BACK_INFILL_MODE: 1228,
                SPACE_EVENLY_MODE: 1228,
                SPACE_EVENLY_INFILL_MODE: 1228,
            },
            "optimized": {
                FRONT_TO_BACK_MODE: 1285,
                FRONT_TO_BACK_INFILL_MODE: 1285,
                SPACE_EVENLY_MODE: 1285,
                SPACE_EVENLY_INFILL_MODE: 1285,
            },
            "probe_a": {
                FRONT_TO_BACK_MODE: 1319,
                FRONT_TO_BACK_INFILL_MODE: 1319,
                SPACE_EVENLY_MODE: 1315,
                SPACE_EVENLY_INFILL_MODE: 1315,
            },
            "probe_b": {
                FRONT_TO_BACK_MODE: 1293,
                FRONT_TO_BACK_INFILL_MODE: 1293,
                SPACE_EVENLY_MODE: 1280,
                SPACE_EVENLY_INFILL_MODE: 1280,
            },
        }
        requested_ft3 = {
            "original": 2271.019314,
            "optimized": 2388.308087,
            "probe_a": 2437.006004,
            "probe_b": 2408.678458,
        }

        for fixture_name, quantities in TOPS_QUANTITIES.items():
            rows = tops_rows(quantities)
            requested_volume = sum(
                row["qty"] * row["length"] * row["width"] * row["height"]
                for row in rows
            )
            self.assertAlmostEqual(
                requested_volume / 28_316_846.592,
                requested_ft3[fixture_name],
                places=5,
            )
            for mode in TOPS_MODES:
                with self.subTest(fixture=fixture_name, mode=mode):
                    selected_container = {
                        **TOPS_CONTAINER,
                        "packing_mode": mode,
                    }
                    result = pack_container(selected_container, rows)
                    physical = assert_transport_result_physical(
                        self,
                        result,
                        selected_container,
                        rows,
                    )
                    self.assertEqual(
                        len(result["placements"]),
                        expected_loaded[fixture_name][mode],
                    )
                    self.assertEqual(
                        sum(physical["packed_by_row"].values()),
                        len(result["placements"]),
                    )
                    self.assertLessEqual(
                        physical["placement_volume"],
                        requested_volume + 1e-3,
                    )
                    prefix = (
                        "front_to_back"
                        if mode.startswith("front_to_back")
                        else "space_evenly"
                    )
                    json.dumps(
                        {
                            "product_blocks": result[
                                f"{prefix}_product_blocks"
                            ],
                            "main_blocks": result[f"{prefix}_main_blocks"],
                        }
                    )

    def test_probe_manifests_are_not_combined(self):
        probe_a = tops_rows(TOPS_QUANTITIES["probe_a"])
        probe_b = tops_rows(TOPS_QUANTITIES["probe_b"])
        self.assertEqual([row["qty"] for row in probe_a], [434, 405, 288, 160, 32])
        self.assertEqual([row["qty"] for row in probe_b], [400, 405, 288, 160, 40])
        self.assertNotEqual(
            Counter((row["name"], row["qty"]) for row in probe_a),
            Counter((row["name"], row["qty"]) for row in probe_b),
        )
