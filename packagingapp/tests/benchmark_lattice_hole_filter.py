"""Paired Palletization lattice benchmark; never rewrites historical fixtures.

Run: .\\.venv\\Scripts\\python.exe -m packagingapp.tests.benchmark_lattice_hole_filter
Only the original lattice enumeration is loaded from Git. Both runs use the
same current shared geometry, including any independent calibration changes.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time
from unittest.mock import patch

from packagingapp.tools.palletization.case_presets import PALLETIZATION_CASE_PRESETS
from packagingapp.utils.palletization import engine


BASELINE_COMMIT = "4d511fe3fd05ff9a813af6385d19386e424ea0f6"
LATTICE_FAMILIES = ("Nested Simple Lattice — 1D", "Nested Simple Lattice — 2D")
TIMED_CASES = tuple(f"calibration-case-{n}" for n in (2, 4, 7, 8, 9)) + (
    "pinwheel-mosaic", "fractional-dimensions", "small-carton",
)


def load_baseline_entries():
    """Run the locked, pre-filter function with the current geometry adapters."""
    source = subprocess.run(
        ["git", "show", f"{BASELINE_COMMIT}:packagingapp/utils/palletization/engine.py"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    function = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "_nested_simple_lattice_entries"
    )
    namespace = dict(vars(engine))
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<locked-lattice-enumeration>", "exec"), namespace)
    return namespace[function.name]


def case_arguments(slug):
    from packagingapp.tools.palletization.service import build_effective_palletization_config

    config = (
        {"box_l": 70, "box_w": 40, "box_h": 150, "pallet_l": 1200,
         "pallet_w": 800, "pallet_height": 150, "max_stack_height": 1150}
        if slug == "small-carton" else PALLETIZATION_CASE_PRESETS[slug]["config"]
    )
    built = build_effective_palletization_config(config)
    assert built["ok"], built["messages"]
    effective = built["effective_config"]
    return {key: effective[key] for key in (
        "box_l", "box_w", "box_h", "pallet_l", "pallet_w", "pallet_height",
        "max_stack_height", "max_width_stickout", "max_length_stickout",
        "box_weight", "max_weight_on_bottom_box", "max_pallet_load",
    )}


def summarize(rows):
    keys = ("pattern", "stacking", "boxes_layer_A", "layers", "total_boxes", "lattice_parameters")
    summaries = [{key: row[key] for key in keys if key in row} for row in rows]
    return {"winner": summaries[0], "rows": summaries}


def paired_timings(before, after, repetitions):
    # Warm both paths, then alternate order to reduce systematic timing bias.
    before()
    after()
    samples = {"before": [], "after": []}
    values = {}
    for iteration in range(repetitions):
        calls = (("before", before), ("after", after))
        for label, call in calls if iteration % 2 == 0 else reversed(calls):
            start = time.perf_counter()
            values[label] = call()
            samples[label].append((time.perf_counter() - start) * 1000)
    medians = {key: statistics.median(value) for key, value in samples.items()}
    delta = medians["after"] - medians["before"]
    change = delta / medians["before"] * 100
    return {
        "before_ms": round(medians["before"], 3), "after_ms": round(medians["after"], 3),
        "change_pct": round(change, 2), "material_regression": delta > 25 and change > 20,
        "samples_ms": {key: [round(n, 3) for n in value] for key, value in samples.items()},
    }, values


def run_benchmark(repetitions=7):
    baseline = load_baseline_entries()
    current = engine._nested_simple_lattice_entries

    def analysis(entries, arguments):
        with patch.object(engine, "_nested_simple_lattice_entries", entries):
            return engine.run_palletization_analysis(**arguments)

    impacts, timings = [], []
    # Compare every existing public preset, not just the motivating examples.
    for slug in (*PALLETIZATION_CASE_PRESETS, "small-carton"):
        arguments = case_arguments(slug)
        before = analysis(baseline, arguments)
        after = analysis(current, arguments)
        other_before = [row for row in before if row["pattern"] not in LATTICE_FAMILIES]
        other_after = [row for row in after if row["pattern"] not in LATTICE_FAMILIES]
        assert other_before == other_after, f"Non-lattice results changed: {slug}"
        if slug in {"calibration-case-2", "nested-simple-lattice-1d-16", "nested-simple-lattice-2d-16"}:
            assert before == after, f"Positive lattice changed: {slug}"
        impacts.append({"case": slug, "unchanged": before == after,
                        "before": summarize(before), "after": summarize(after)})
        if slug not in TIMED_CASES:
            continue
        timing, _ = paired_timings(
            lambda: analysis(baseline, arguments), lambda: analysis(current, arguments), repetitions,
        )
        timings.append({"case": slug, "surface": "full_analysis", **timing})
        area_l, area_w = engine.effective_pallet_size(
            arguments["pallet_l"], arguments["pallet_w"],
            arguments["max_length_stickout"], arguments["max_width_stickout"],
        )
        for family in LATTICE_FAMILIES:
            args = family, area_l, area_w, arguments["box_l"], arguments["box_w"]
            timing, _ = paired_timings(lambda: list(baseline(*args)), lambda: list(current(*args)), repetitions)
            timings.append({"case": slug, "surface": family, **timing})
    return {
        "baseline_commit": BASELINE_COMMIT, "repetitions": repetitions,
        "shared_core_sha256": hashlib.sha256(Path(engine.shared_pattern_core.__file__).read_bytes()).hexdigest(),
        "search_limits": {"parameter": engine.PALLETIZATION_SEARCH_POLICY.max_pinwheel_parameter,
                          "candidate": engine.PALLETIZATION_SEARCH_POLICY.max_pinwheel_candidates,
                          "distinct_per_family": engine.PALLET_LATTICE_VARIANTS_PER_FAMILY},
        "all_non_lattice_rows_identical": True, "impacts": impacts, "timings": timings,
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
