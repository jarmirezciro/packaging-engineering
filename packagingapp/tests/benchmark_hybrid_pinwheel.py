"""Paired Hybrid calibration benchmark against the unmodified core.

Run: .\\.venv\\Scripts\\python.exe -m packagingapp.tests.benchmark_hybrid_pinwheel
The baseline comes from Git, never from regenerated golden fixtures.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import types
from unittest.mock import patch

from packagingapp.utils.packing_patterns import core, patterns
from packagingapp.utils.palletization import engine


BASELINE_COMMIT = "4d511fe3fd05ff9a813af6385d19386e424ea0f6"
CASES = (
    ("case_4", (48 * 25.4, 40 * 25.4, 16 * 25.4, 8 * 25.4)),
    ("case_5", (1200.0, 800.0, 292.0, 312.0)),
    ("case_9", (2000.0, 2000.0, 300.0, 400.0)),
    ("standard", (1200.0, 800.0, 230.0, 170.0)),
    ("fractional", (401.5, 287.9, 73.2, 41.7)),
    ("small_carton", (1200.0, 800.0, 70.0, 40.0)),
)


def load_baseline_core():
    source = subprocess.run(
        ["git", "show", f"{BASELINE_COMMIT}:packagingapp/utils/packing_patterns/core.py"],
        check=True, capture_output=True, text=True,
    ).stdout
    name = "packagingapp.utils.packing_patterns._hybrid_baseline_core"
    module = types.ModuleType(name)
    module.__file__ = f"{BASELINE_COMMIT}:packagingapp/utils/packing_patterns/core.py"
    module.__package__ = "packagingapp.utils.packing_patterns"
    sys.modules[name] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def paired_timings(before, after, repetitions):
    samples = {"before": [], "after": []}
    values = {}
    for iteration in range(repetitions):
        calls = (("before", before), ("after", after))
        for label, function in calls if iteration % 2 == 0 else reversed(calls):
            start = time.perf_counter()
            values[label] = function()
            samples[label].append(time.perf_counter() - start)
    medians = {label: statistics.median(value) for label, value in samples.items()}
    delta = medians["after"] - medians["before"]
    change = delta / medians["before"] * 100
    return {
        "before_ms": round(medians["before"] * 1000, 3),
        "after_ms": round(medians["after"] * 1000, 3),
        "change_pct": round(change, 2),
        "material_regression": delta > 0.025 and change > 20,
    }, values


def run_benchmark(repetitions=7):
    baseline = load_baseline_core()
    results = []
    for name, args in CASES:
        for rotated in (False, True):
            timing, values = paired_timings(
                lambda: baseline.pattern_hybrid_pinwheel(
                    *args, rotated=rotated, policy=baseline.PALLETIZATION_SEARCH_POLICY,
                ),
                lambda: core.pattern_hybrid_pinwheel(
                    *args, rotated=rotated, policy=core.PALLETIZATION_SEARCH_POLICY,
                ), repetitions,
            )
            results.append({
                "case": name, "surface": "hybrid_layer", "rotated": rotated,
                "before_count": len(values["before"]), "after_count": len(values["after"]),
                **timing,
            })

        def analysis(module):
            with patch.object(patterns, "_core", module), patch.object(
                engine, "PALLETIZATION_SEARCH_POLICY", module.PALLETIZATION_SEARCH_POLICY,
            ):
                return engine.run_palletization_analysis(
                    pallet_l=args[0], pallet_w=args[1], box_l=args[2], box_w=args[3],
                    box_h=150.0, pallet_height=150.0, max_stack_height=1150.0,
                )

        timing, values = paired_timings(
            lambda: analysis(baseline), lambda: analysis(core), repetitions,
        )
        # Other families retain all metrics and ordered placements. A change
        # here is a regression, even when the top quantity happens to tie.
        for label in values:
            values[label] = [row for row in values[label] if row["pattern"] != "Hybrid pinwheel"]
        if values["before"] != values["after"]:
            raise AssertionError(f"Non-Hybrid analysis changed: {name}")
        results.append({"case": name, "surface": "full_analysis", **timing})

    return {
        "baseline_commit": BASELINE_COMMIT, "repetitions": repetitions,
        "search_limits": {
            "before": [baseline.PALLETIZATION_SEARCH_POLICY.max_pinwheel_parameter,
                       baseline.PALLETIZATION_SEARCH_POLICY.max_pinwheel_candidates],
            "after": [core.PALLETIZATION_SEARCH_POLICY.max_pinwheel_parameter,
                      core.PALLETIZATION_SEARCH_POLICY.max_pinwheel_candidates],
        },
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=7)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    print(json.dumps(run_benchmark(args.repetitions), indent=2))
