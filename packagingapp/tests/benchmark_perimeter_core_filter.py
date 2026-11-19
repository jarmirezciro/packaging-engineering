"""Paired Perimeter-Core calibration benchmark against the locked pre-filter core.

Run: python -m packagingapp.tests.benchmark_perimeter_core_filter --repetitions 7
Historical fixtures are never regenerated. Only the family entry point is
loaded from Git; all other geometry, ranking and consumer code is identical.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

from packagingapp.tests.benchmark_lattice_hole_filter import (
    case_arguments, paired_timings, summarize,
)
from packagingapp.tools.palletization.case_presets import PALLETIZATION_CASE_PRESETS
from packagingapp.utils.packing_patterns import core
from packagingapp.utils.palletization import engine


BASELINE_COMMIT = "b3915cf14bf1e30da3fb33346000ff75df21bf62"
FAMILY = "Perimeter-Core Mosaic"
TIMED_CASES = tuple(f"calibration-case-{n}" for n in (3, 4, 6, 7, 8)) + (
    "capepack-perimeter-core-10", "pinwheel-mosaic", "fractional-dimensions",
)


def load_baseline_pattern():
    source = subprocess.run(
        ["git", "show", f"{BASELINE_COMMIT}:packagingapp/utils/packing_patterns/core.py"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    function = next(node for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef) and node.name == "pattern_perimeter_core_mosaic")
    namespace = dict(vars(core))
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<locked-perimeter-core>", "exec"), namespace)
    return namespace[function.name]


def digest(rows):
    payload = json.dumps(rows, default=vars, sort_keys=True, allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def run_benchmark(repetitions=7):
    baseline, current = load_baseline_pattern(), core.pattern_perimeter_core_mosaic

    def analysis(pattern, arguments):
        with patch.object(core, "pattern_perimeter_core_mosaic", pattern):
            return engine.run_palletization_analysis(**arguments)

    impacts, timings = [], []
    for slug in PALLETIZATION_CASE_PRESETS:
        arguments = case_arguments(slug)
        before, after = analysis(baseline, arguments), analysis(current, arguments)
        assert [row for row in before if row["pattern"] != FAMILY] == [
            row for row in after if row["pattern"] != FAMILY
        ], f"Unrelated rows changed: {slug}"
        assert before[0] == after[0], f"Winner changed: {slug}"
        before_family = [row for row in before if row["pattern"] == FAMILY]
        after_family = [row for row in after if row["pattern"] == FAMILY]
        if after_family:
            assert before_family == after_family, f"Retained geometry changed: {slug}"
        area_l, area_w = engine.effective_pallet_size(
            arguments["pallet_l"], arguments["pallet_w"],
            arguments["max_length_stickout"], arguments["max_width_stickout"],
        )
        long_side, short_side = sorted((arguments["box_l"], arguments["box_w"]), reverse=True)
        occupied = 10 * long_side * short_side
        impacts.append({
            "case": slug, "unchanged": before == after,
            "motif_density": occupied / ((2 * long_side + short_side) * 2 * long_side),
            "floor_utilization": occupied / (area_l * area_w),
            "before": summarize(before), "after": summarize(after),
            "before_sha256": digest(before), "after_sha256": digest(after),
            "before_perimeter_sha256": digest(before_family),
            "after_perimeter_sha256": digest(after_family),
        })
        if slug in TIMED_CASES:
            timing, _ = paired_timings(
                lambda: analysis(baseline, arguments), lambda: analysis(current, arguments), repetitions,
            )
            timings.append({"case": slug, "surface": "full_analysis", **timing})
            values = area_l, area_w, arguments["box_l"], arguments["box_w"]
            timing, _ = paired_timings(
                lambda: baseline(*values, policy=core.PALLETIZATION_SEARCH_POLICY),
                lambda: current(*values, policy=core.PALLETIZATION_SEARCH_POLICY), repetitions,
            )
            timings.append({"case": slug, "surface": "pattern", **timing})
    return {
        "baseline_commit": BASELINE_COMMIT, "repetitions": repetitions,
        "shared_core_sha256": hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),
        "all_non_perimeter_rows_identical": True, "all_winners_identical": True,
        "impacts": impacts, "timings": timings,
    }


if __name__ == "__main__":
    import os
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "packagingproject.settings")
    django.setup()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=7)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    print(json.dumps(run_benchmark(args.repetitions), indent=2))
