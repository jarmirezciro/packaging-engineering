"""Deterministic Stage 1 benchmark for Container Selection mosaics.

Run with:
    python -m packagingapp.tests.benchmark_shared_mosaic_patterns
"""

from __future__ import annotations

import json
from statistics import mean

from packagingapp.utils.box_selection.engine import compare_packing_candidates


BENCHMARK_CASES = (
    ("reference_imperial_equivalent", (152.4, 101.6, 152.4), (384.81, 368.3, 342.9), (0, 0, 1)),
    ("square", (100.0, 100.0, 50.0), (550.0, 450.0, 260.0), (1, 1, 1)),
    ("elongated", (300.0, 80.0, 60.0), (1000.0, 500.0, 360.0), (1, 1, 1)),
    ("near_cubic", (98.0, 95.0, 90.0), (500.0, 420.0, 380.0), (1, 1, 1)),
    ("small_in_large", (25.0, 20.0, 15.0), (800.0, 600.0, 300.0), (0, 0, 1)),
    ("tight_fit", (199.9, 99.9, 50.1), (400.0, 200.0, 51.0), (0, 0, 1)),
    ("significant_residual", (300.0, 200.0, 120.0), (1000.0, 800.0, 500.0), (0, 0, 1)),
    ("fractional", (73.2, 41.7, 29.3), (401.5, 287.9, 190.2), (1, 1, 1)),
    ("r1_only", (120.0, 80.0, 40.0), (500.0, 360.0, 250.0), (1, 0, 0)),
    ("r2_only", (120.0, 80.0, 40.0), (500.0, 360.0, 250.0), (0, 1, 0)),
    ("r3_only", (120.0, 80.0, 40.0), (500.0, 360.0, 250.0), (0, 0, 1)),
    ("combined_rotations", (230.0, 170.0, 130.0), (1200.0, 800.0, 650.0), (1, 0, 1)),
    ("single_layer", (230.0, 170.0, 130.0), (1200.0, 800.0, 135.0), (0, 0, 1)),
    ("legacy_residual_wins", (500.0, 200.0, 300.0), (800.0, 800.0, 900.0), (1, 1, 1)),
)


def run_benchmark():
    cases = []
    for name, product, container, flags in BENCHMARK_CASES:
        result = compare_packing_candidates(product, container, *flags)
        gain = result.selected_quantity - result.legacy_quantity
        gain_pct = (gain / result.legacy_quantity * 100.0) if result.legacy_quantity else 0.0
        cases.append(
            {
                "name": name,
                "legacy_quantity": result.legacy_quantity,
                "best_mosaic_quantity": result.mosaic_quantity,
                "selected_quantity": result.selected_quantity,
                "winning_family": result.winning_family,
                "absolute_gain": gain,
                "percentage_gain": round(gain_pct, 3),
                "geometry_valid": result.geometry_valid,
                "legacy_seconds": result.legacy_seconds,
                "mosaic_seconds": result.mosaic_seconds,
                "combined_seconds": result.combined_seconds,
                "mosaic_candidate_count": result.mosaic_candidate_count,
                "mosaic_resource_limited": result.mosaic_resource_limited,
            }
        )
    improved = [case for case in cases if case["absolute_gain"] > 0]
    aggregate = {
        "case_count": len(cases),
        "improved_count": len(improved),
        "improved_percentage": round(len(improved) / len(cases) * 100.0, 3),
        "average_gain_among_improved": round(
            mean(case["absolute_gain"] for case in improved), 3
        ) if improved else 0.0,
        "maximum_gain": max((case["absolute_gain"] for case in cases), default=0),
        "no_change_count": sum(case["absolute_gain"] == 0 for case in cases),
        "capacity_regressions": sum(case["absolute_gain"] < 0 for case in cases),
        "total_legacy_seconds": sum(case["legacy_seconds"] for case in cases),
        "total_mosaic_seconds": sum(case["mosaic_seconds"] for case in cases),
        "total_combined_seconds": sum(case["combined_seconds"] for case in cases),
        "worst_case_seconds": max((case["combined_seconds"] for case in cases), default=0.0),
    }
    return {"cases": cases, "aggregate": aggregate}


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
