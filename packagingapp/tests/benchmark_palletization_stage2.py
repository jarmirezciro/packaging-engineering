"""Reproducible before/after benchmark for the Stage 2 pattern migration.

The original engine is loaded directly from the locked baseline commit in a
separate module namespace, so current and pre-migration calls run in the same
Python process and environment.

Run with:
    python -m packagingapp.tests.benchmark_palletization_stage2
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import tracemalloc
import types

from packagingapp.utils.packing_patterns import core as shared_core
from packagingapp.utils.packing_patterns.core import PALLETIZATION_SEARCH_POLICY
from packagingapp.utils.palletization import engine as migrated_engine


BASELINE_COMMIT = "5754ef9e82b409b93984ac4ffa0672ce55324950"
MATERIAL_RELATIVE_CHANGE_PCT = 20.0
MATERIAL_ABSOLUTE_CHANGE_SECONDS = 0.025


PATTERN_CASES = (
    ("standard", (1200.0, 800.0, 230.0, 170.0)),
    ("fractional", (401.5, 287.9, 73.2, 41.7)),
    ("beyond_container_cap", (1200.0, 800.0, 70.0, 40.0)),
)

PATTERN_FUNCTIONS = (
    ("block", "pattern_block", {}),
    ("splitrow", "pattern_splitrow", {}),
    ("pinwheel", "pattern_pinwheel", {}),
    ("pinwheel_rotated", "pattern_pinwheel", {"rotated": True}),
    ("hybrid_pinwheel", "pattern_hybrid_pinwheel", {}),
    ("nested_pinwheel", "pattern_nested_pinwheel", {}),
    ("centre_filled_pinwheel", "pattern_center_filled_pinwheel", {}),
)

ANALYSIS_CASES = (
    (
        "standard",
        {
            "box_l": 230.0,
            "box_w": 170.0,
            "box_h": 130.0,
            "pallet_l": 1200.0,
            "pallet_w": 800.0,
            "pallet_height": 150.0,
            "max_stack_height": 1200.0,
        },
    ),
    (
        "tops",
        {
            "box_l": 411.0,
            "box_w": 289.0,
            "box_h": 231.0,
            "pallet_l": 1219.0,
            "pallet_w": 1016.0,
            "pallet_height": 101.0,
            "max_stack_height": 1346.0,
            "max_width_stickout": 25.0,
            "max_length_stickout": 25.0,
        },
    ),
    (
        "fractional",
        {
            "box_l": 73.2,
            "box_w": 41.7,
            "box_h": 29.3,
            "pallet_l": 401.5,
            "pallet_w": 287.9,
            "pallet_height": 42.5,
            "max_stack_height": 218.3,
        },
    ),
)


def _load_baseline_engine():
    source = subprocess.run(
        [
            "git",
            "show",
            f"{BASELINE_COMMIT}:packagingapp/utils/palletization/engine.py",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    name = "packagingapp.utils.palletization._stage2_baseline_engine"
    module = types.ModuleType(name)
    module.__file__ = f"{BASELINE_COMMIT}:packagingapp/utils/palletization/engine.py"
    module.__package__ = "packagingapp.utils.palletization"
    sys.modules[name] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def _layer_signature(layer):
    return tuple(
        (
            round(item.x, 9),
            round(item.y, 9),
            round(item.l, 9),
            round(item.w, 9),
            item.orientation,
        )
        for item in layer
    )


def _analysis_signature(rows):
    return tuple(
        (
            row["pattern"],
            row["stacking"],
            row["total_boxes"],
            row["layers"],
            tuple(
                (
                    round(item.x, 9),
                    round(item.y, 9),
                    round(item.z, 9),
                    round(item.l, 9),
                    round(item.w, 9),
                    round(item.h, 9),
                    item.orientation,
                    item.layer_kind,
                    item.layer_index,
                )
                for item in row["placements3d"]
            ),
        )
        for row in rows
    )


def _paired_timings(baseline_call, migrated_call, repetitions):
    samples = {"baseline": [], "migrated": []}
    baseline_value = migrated_value = None
    for index in range(repetitions):
        ordered = (
            (("baseline", baseline_call), ("migrated", migrated_call))
            if index % 2 == 0
            else (("migrated", migrated_call), ("baseline", baseline_call))
        )
        for label, function in ordered:
            start = time.perf_counter()
            value = function()
            samples[label].append(time.perf_counter() - start)
            if label == "baseline":
                baseline_value = value
            else:
                migrated_value = value
    return samples, baseline_value, migrated_value


def _percentage_change(before, after):
    return ((after - before) / before * 100.0) if before else 0.0


def _performance_fields(before, after):
    change_seconds = after - before
    change_pct = _percentage_change(before, after)
    return {
        "change_seconds": change_seconds,
        "change_pct": round(change_pct, 3),
        "material_regression": bool(
            change_seconds > MATERIAL_ABSOLUTE_CHANGE_SECONDS
            and change_pct > MATERIAL_RELATIVE_CHANGE_PCT
        ),
    }


def _search_candidate_counts(baseline_engine):
    results = []
    for name, args in PATTERN_CASES:
        area_l, area_w, box_l, box_w = args
        migrated_block = len(
            shared_core.call_with_policy(
                shared_core._enumerate_block_pinwheel_candidates,
                area_l, area_w, box_l, box_w, box_l, box_w,
                policy=PALLETIZATION_SEARCH_POLICY,
            )
        )
        migrated_nested = len(
            shared_core.call_with_policy(
                shared_core._enumerate_nested_pinwheel_candidates,
                area_l, area_w, box_l, box_w, box_l, box_w,
                policy=PALLETIZATION_SEARCH_POLICY,
            )
        )
        baseline_block = len(
            baseline_engine._enumerate_block_pinwheel_candidates(
                area_l, area_w, box_l, box_w, box_l, box_w
            )
        )
        baseline_nested = len(
            baseline_engine._enumerate_nested_pinwheel_candidates(
                area_l, area_w, box_l, box_w, box_l, box_w
            )
        )
        results.append(
            {
                "case": name,
                "block_pinwheel": {
                    "baseline": baseline_block,
                    "migrated": migrated_block,
                },
                "nested_pinwheel": {
                    "baseline": baseline_nested,
                    "migrated": migrated_nested,
                },
            }
        )
    return results


def _peak_bytes(function):
    tracemalloc.start()
    try:
        function()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def run_benchmark(repetitions=3, include_memory=False):
    baseline_engine = _load_baseline_engine()
    pattern_results = []
    for case_name, args in PATTERN_CASES:
        for family, function_name, kwargs in PATTERN_FUNCTIONS:
            baseline_function = getattr(baseline_engine, function_name)
            migrated_function = getattr(migrated_engine, function_name)
            samples, baseline_layer, migrated_layer = _paired_timings(
                lambda f=baseline_function: f(*args, **kwargs),
                lambda f=migrated_function: f(*args, **kwargs),
                repetitions,
            )
            if _layer_signature(baseline_layer) != _layer_signature(migrated_layer):
                raise AssertionError(f"geometry changed for {case_name}/{family}")
            baseline_seconds = statistics.median(samples["baseline"])
            migrated_seconds = statistics.median(samples["migrated"])
            pattern_results.append(
                {
                    "case": case_name,
                    "pattern": family,
                    "quantity": len(migrated_layer),
                    "baseline_seconds": baseline_seconds,
                    "migrated_seconds": migrated_seconds,
                    **_performance_fields(baseline_seconds, migrated_seconds),
                }
            )

    analysis_results = []
    for case_name, kwargs in ANALYSIS_CASES:
        samples, baseline_rows, migrated_rows = _paired_timings(
            lambda: baseline_engine.run_palletization_analysis(**kwargs),
            lambda: migrated_engine.run_palletization_analysis(**kwargs),
            repetitions,
        )
        if _analysis_signature(baseline_rows) != _analysis_signature(migrated_rows):
            raise AssertionError(f"full analysis changed for {case_name}")
        baseline_seconds = statistics.median(samples["baseline"])
        migrated_seconds = statistics.median(samples["migrated"])
        record = {
            "case": case_name,
            "rows": len(migrated_rows),
            "top_quantity": migrated_rows[0]["total_boxes"] if migrated_rows else 0,
            "baseline_seconds": baseline_seconds,
            "migrated_seconds": migrated_seconds,
            **_performance_fields(baseline_seconds, migrated_seconds),
        }
        if include_memory:
            record["baseline_peak_bytes"] = _peak_bytes(
                lambda: baseline_engine.run_palletization_analysis(**kwargs)
            )
            record["migrated_peak_bytes"] = _peak_bytes(
                lambda: migrated_engine.run_palletization_analysis(**kwargs)
            )
        analysis_results.append(record)

    return {
        "baseline_commit": BASELINE_COMMIT,
        "repetitions": repetitions,
        "material_threshold": {
            "relative_change_pct": MATERIAL_RELATIVE_CHANGE_PCT,
            "absolute_change_seconds": MATERIAL_ABSOLUTE_CHANGE_SECONDS,
            "rule": "both thresholds must be exceeded",
        },
        "pattern_results": pattern_results,
        "analysis_results": analysis_results,
        "candidate_counts": _search_candidate_counts(baseline_engine),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--memory", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run_benchmark(
                repetitions=max(args.repetitions, 1),
                include_memory=args.memory,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
