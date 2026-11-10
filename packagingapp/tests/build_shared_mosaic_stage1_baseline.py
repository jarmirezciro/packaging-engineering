"""One-shot exact-signature baseline for the Stage 1 Container consumer."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from packagingapp.tests.benchmark_shared_mosaic_patterns import BENCHMARK_CASES
from packagingapp.tests.build_palletization_stage2_baseline import PATTERN_SCENARIOS
from packagingapp.utils.box_selection.engine import (
    calculate_placements,
    compare_packing_candidates,
)
from packagingapp.utils.box_selection.mosaic import _vertical_families
from packagingapp.utils.packing_patterns.geometry import count_fitting_units
from packagingapp.utils.packing_patterns import enumerate_pattern_candidates
from packagingapp.utils.packing_patterns import patterns


BASELINE_COMMIT = "5754ef9e82b409b93984ac4ffa0672ce55324950"
BASELINE_PATTERNS_SHA256 = "45b739ed645f4125330fd448c348c7ac4e605a0dc132abe63a9e481ab1c2e4c0"
FIXTURE_PATH = Path(__file__).with_name("shared_mosaic_stage1_baseline.json")
PATTERNS_PATH = Path(patterns.__file__).resolve()
ADDITIVE_PATTERN_FAMILIES = frozenset({"perimeter_core_mosaic"})


def _number(value):
    rounded = round(float(value), 9)
    return 0.0 if rounded == 0 else rounded


def _digest(payload):
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _pattern_signature(placements):
    return [
        [
            _number(item.x),
            _number(item.y),
            _number(item.l),
            _number(item.w),
            str(item.orientation),
        ]
        for item in placements
    ]


def _box_signature(placements):
    return [
        [
            *[_number(value) for value in item.origin],
            *[_number(value) for value in item.dimensions],
        ]
        for item in placements
    ]


def _historical_candidates(candidates):
    return tuple(
        candidate
        for candidate in candidates
        if candidate.family not in ADDITIVE_PATTERN_FAMILIES
    )


def _additive_candidate_count(product, container, flags):
    count = 0
    for _axis, footprint_l, footprint_w, vertical in _vertical_families(
        product, *flags
    ):
        if count_fitting_units(container[2], vertical) <= 0:
            continue
        candidates = enumerate_pattern_candidates(
            container[0], container[1], footprint_l, footprint_w
        )
        count += sum(
            candidate.family in ADDITIVE_PATTERN_FAMILIES
            for candidate in candidates
        )
    return count


def build_baseline():
    enumerations = []
    for name, area_l, area_w, box_l, box_w in PATTERN_SCENARIOS:
        candidates = _historical_candidates(
            enumerate_pattern_candidates(area_l, area_w, box_l, box_w)
        )
        enumerations.append(
            {
                "name": name,
                "candidate_count": len(candidates),
                "candidates": [
                    {
                        "family": candidate.family,
                        "variant": candidate.variant,
                        "quantity": candidate.quantity,
                        "ordered_geometry_sha256": _digest(
                            _pattern_signature(candidate.placements)
                        ),
                    }
                    for candidate in candidates
                ],
            }
        )

    selections = []
    for name, product, container, flags in BENCHMARK_CASES:
        result = compare_packing_candidates(product, container, *flags)
        selected_placements = calculate_placements(product, container, *flags)
        selections.append(
            {
                "name": name,
                "legacy_quantity": result.legacy_quantity,
                "mosaic_quantity": result.mosaic_quantity,
                "selected_quantity": result.selected_quantity,
                "winning_family": result.winning_family,
                "geometry_valid": result.geometry_valid,
                "mosaic_candidate_count": result.mosaic_candidate_count
                - _additive_candidate_count(product, container, flags),
                "mosaic_resource_limited": result.mosaic_resource_limited,
                "selected_geometry_sha256": _digest(
                    _box_signature(selected_placements)
                ),
            }
        )

    return {
        "metadata": {
            "baseline_commit": BASELINE_COMMIT,
            "baseline_patterns_sha256": BASELINE_PATTERNS_SHA256,
            "enumeration_scenario_count": len(PATTERN_SCENARIOS),
            "selection_scenario_count": len(BENCHMARK_CASES),
        },
        "enumerations": enumerations,
        "container_selections": selections,
    }


def main():
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source_hash = hashlib.sha256(PATTERNS_PATH.read_bytes()).hexdigest()
    if commit != BASELINE_COMMIT or source_hash != BASELINE_PATTERNS_SHA256:
        raise RuntimeError("Stage 1 baseline generation is locked to its source")
    payload = build_baseline()
    with FIXTURE_PATH.open("x", encoding="utf-8", newline="\n") as fixture:
        json.dump(payload, fixture, indent=2, sort_keys=True)
        fixture.write("\n")
    print(f"wrote immutable baseline: {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
