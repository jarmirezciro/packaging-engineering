"""One-shot builder for the immutable Stage 2 Palletization baseline.

This module intentionally refuses to overwrite the checked-in fixture and the
command-line entry point only runs against the exact pre-migration source.  The
test suite imports :func:`build_baseline` to compare the current implementation
with the frozen data; it never updates the fixture on failure.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from packagingapp.tools.palletization.export import _analysis_rows
from packagingapp.tools.palletization.service import analyze_palletization_config
from packagingapp.tools.palletization.state import default_palletization_config
from packagingapp.utils.palletization import engine


BASELINE_COMMIT = "5754ef9e82b409b93984ac4ffa0672ce55324950"
BASELINE_ENGINE_SHA256 = "c7cc040b3c1f5c2cec68b35337ff729043e66042b5cfd3525b992363d0cb912d"
FIXTURE_PATH = Path(__file__).with_name("palletization_stage2_baseline.json")
ENGINE_PATH = Path(engine.__file__).resolve()


PATTERN_SCENARIOS = (
    ("splitrow_tops", 1244.0, 1041.0, 411.0, 289.0),
    ("splitrow_na4840", 1219.0, 1016.0, 308.0, 147.0),
    ("splitrow_compact_filler", 1219.0, 1016.0, 284.0, 160.0),
    ("splitrow_sparse_362", 1219.0, 1016.0, 362.0, 146.0),
    ("splitrow_sparse_364", 1219.0, 1016.0, 364.0, 288.0),
    ("standard_230_170", 1200.0, 800.0, 230.0, 170.0),
    ("brick_spiral", 1200.0, 1200.0, 400.0, 200.0),
    ("container_reference", 384.81, 368.3, 152.4, 101.6),
    ("square_carton", 1200.0, 1200.0, 200.0, 200.0),
    ("near_square_carton", 1200.0, 800.0, 201.0, 200.0),
    ("elongated_carton", 1200.0, 800.0, 300.0, 80.0),
    ("exact_fit", 1200.0, 800.0, 300.0, 200.0),
    ("fractional", 401.5, 287.9, 73.2, 41.7),
    ("beyond_shared_parameter_cap", 1200.0, 800.0, 70.0, 40.0),
    ("large_carton", 500.0, 400.0, 300.0, 220.0),
    ("significant_residual", 1000.0, 800.0, 290.0, 190.0),
    ("equal_count_alternatives", 800.0, 800.0, 200.0, 100.0),
    ("slightly_insufficient", 229.9, 169.9, 230.0, 170.0),
    (
        "imperial_equivalent",
        1200.0 / 25.4,
        800.0 / 25.4,
        230.0 / 25.4,
        170.0 / 25.4,
    ),
)


PATTERN_VARIANTS = (
    ("block", engine.pattern_block, {}),
    ("row", engine.pattern_row, {}),
    ("splitrow", engine.pattern_splitrow, {}),
    ("splitrow_swapped", engine.pattern_splitrow, {"swapped": True}),
    ("brick", engine.pattern_brick_best, {}),
    ("pinwheel", engine.pattern_pinwheel, {}),
    ("pinwheel_rotated", engine.pattern_pinwheel, {"rotated": True}),
    ("hybrid_pinwheel", engine.pattern_hybrid_pinwheel, {}),
    (
        "hybrid_pinwheel_rotated",
        engine.pattern_hybrid_pinwheel,
        {"rotated": True},
    ),
    ("nested_pinwheel", engine.pattern_nested_pinwheel, {}),
    (
        "nested_pinwheel_rotated",
        engine.pattern_nested_pinwheel,
        {"rotated": True},
    ),
    ("centre_filled_pinwheel", engine.pattern_center_filled_pinwheel, {}),
)


ANALYSIS_SCENARIOS = (
    (
        "tops_splitrow_overhang",
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
        "na4840_splitrow",
        {
            "box_l": 308.0,
            "box_w": 147.0,
            "box_h": 193.0,
            "pallet_l": 1219.0,
            "pallet_w": 1016.0,
            "pallet_height": 141.0,
            "max_stack_height": 1346.0,
        },
    ),
    (
        "standard_pallet",
        {
            "box_l": 230.0,
            "box_w": 170.0,
            "box_h": 130.0,
            "box_weight": 1250.0,
            "max_weight_on_bottom_box": 9000.0,
            "pallet_l": 1200.0,
            "pallet_w": 800.0,
            "pallet_height": 150.0,
            "max_stack_height": 1200.0,
        },
    ),
    (
        "brick_and_centre_filled",
        {
            "box_l": 400.0,
            "box_w": 200.0,
            "box_h": 200.0,
            "pallet_l": 1200.0,
            "pallet_w": 1200.0,
            "pallet_height": 150.0,
            "max_stack_height": 1150.0,
        },
    ),
    (
        "maximum_pallet_load",
        {
            "box_l": 400.0,
            "box_w": 400.0,
            "box_h": 200.0,
            "box_weight": 1000.0,
            "pallet_l": 1200.0,
            "pallet_w": 800.0,
            "pallet_height": 150.0,
            "max_stack_height": 1150.0,
            "max_pallet_load": 22000.0,
        },
    ),
    (
        "fractional_dimensions",
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
    (
        "container_reference_geometry",
        {
            "box_l": 152.4,
            "box_w": 101.6,
            "box_h": 152.4,
            "pallet_l": 384.81,
            "pallet_w": 368.3,
            "pallet_height": 50.8,
            "max_stack_height": 355.6,
        },
    ),
)


def _number(value):
    rounded = round(float(value), 9)
    return 0.0 if rounded == 0 else rounded


def _placement2d(placement):
    return [
        _number(placement.x),
        _number(placement.y),
        _number(placement.l),
        _number(placement.w),
        str(placement.orientation),
    ]


def _placement3d(placement):
    return [
        _number(placement.x),
        _number(placement.y),
        _number(placement.z),
        _number(placement.l),
        _number(placement.w),
        _number(placement.h),
        str(placement.orientation),
        str(placement.layer_kind),
        int(placement.layer_index),
    ]


def _bounding_box(layer):
    if not layer:
        return [0.0, 0.0, 0.0, 0.0]
    return [
        _number(min(item.x for item in layer)),
        _number(min(item.y for item in layer)),
        _number(max(item.x + item.l for item in layer)),
        _number(max(item.y + item.w for item in layer)),
    ]


def _occupied_contour(layer):
    """Return deterministic exterior segments for the union of rectangles."""
    if not layer:
        return []
    xs = sorted({float(value) for item in layer for value in (item.x, item.x + item.l)})
    ys = sorted({float(value) for item in layer for value in (item.y, item.y + item.w)})
    occupied = set()
    for xi, (x1, x2) in enumerate(zip(xs, xs[1:])):
        cx = (x1 + x2) / 2.0
        for yi, (y1, y2) in enumerate(zip(ys, ys[1:])):
            cy = (y1 + y2) / 2.0
            if any(
                item.x <= cx < item.x + item.l
                and item.y <= cy < item.y + item.w
                for item in layer
            ):
                occupied.add((xi, yi))
    segments = []
    for xi, yi in sorted(occupied):
        if (xi - 1, yi) not in occupied:
            segments.append([_number(xs[xi]), _number(ys[yi]), _number(xs[xi]), _number(ys[yi + 1])])
        if (xi + 1, yi) not in occupied:
            segments.append([_number(xs[xi + 1]), _number(ys[yi]), _number(xs[xi + 1]), _number(ys[yi + 1])])
        if (xi, yi - 1) not in occupied:
            segments.append([_number(xs[xi]), _number(ys[yi]), _number(xs[xi + 1]), _number(ys[yi])])
        if (xi, yi + 1) not in occupied:
            segments.append([_number(xs[xi]), _number(ys[yi + 1]), _number(xs[xi + 1]), _number(ys[yi + 1])])
    return sorted(segments)


def _layer(layer):
    return {
        "quantity": len(layer),
        "placements": [_placement2d(item) for item in layer],
        "bounding_box": _bounding_box(layer),
        "occupied_contour": _occupied_contour(layer),
    }


def _stable_scalar(value):
    if isinstance(value, float):
        return _number(value)
    if isinstance(value, list):
        return [_stable_scalar(item) for item in value]
    if isinstance(value, tuple):
        return [_stable_scalar(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _stable_scalar(item) for key, item in value.items()}
    return value


def _analysis_row(row):
    excluded = {
        "placements3d",
        "layer_A_2d",
        "layer_B_2d",
        "layers_2d",
        "interlock_possible_layer",
        "debug_render_signature",
    }
    metrics = {
        key: _stable_scalar(value)
        for key, value in row.items()
        if key not in excluded
    }
    return {
        "metrics": metrics,
        "layer_A": _layer(row.get("layer_A_2d") or []),
        "layer_B": _layer(row.get("layer_B_2d") or []),
        "interlock_possible_layer": _layer(
            row.get("interlock_possible_layer") or []
        ),
        "layers_2d": [
            [_placement2d(item) for item in layer]
            for layer in (row.get("layers_2d") or [])
        ],
        "placements3d": [
            _placement3d(item) for item in (row.get("placements3d") or [])
        ],
    }


def _pattern_fixtures():
    fixtures = []
    for name, area_l, area_w, box_l, box_w in PATTERN_SCENARIOS:
        variants = {}
        for variant_name, function, kwargs in PATTERN_VARIANTS:
            variants[variant_name] = _layer(
                function(area_l, area_w, box_l, box_w, **kwargs)
            )
        fixtures.append(
            {
                "name": name,
                "input": {
                    "area_l": _number(area_l),
                    "area_w": _number(area_w),
                    "box_l": _number(box_l),
                    "box_w": _number(box_w),
                },
                "variants": variants,
            }
        )
    return fixtures


def _analysis_fixtures():
    fixtures = []
    for name, updates in ANALYSIS_SCENARIOS:
        config = default_palletization_config()
        config.update(updates)
        analysis = analyze_palletization_config(config)
        if not analysis["ok"]:
            raise RuntimeError(f"baseline scenario {name!r} failed: {analysis['messages']}")
        selected = analysis["result"]["selected_row"]
        fixtures.append(
            {
                "name": name,
                "input": _stable_scalar(updates),
                "rows": [
                    _analysis_row(row) for row in analysis["result"]["raw_results"]
                ],
                "serialized_result": _stable_scalar(analysis["serialized_result"]),
                "threejs_scene": _stable_scalar(analysis["threejs_scene"]),
                "export_analysis_rows": _stable_scalar(_analysis_rows(selected)),
            }
        )
    return fixtures


def build_baseline():
    return {
        "metadata": {
            "baseline_commit": BASELINE_COMMIT,
            "baseline_engine_sha256": BASELINE_ENGINE_SHA256,
            "float_decimals": 9,
            "pattern_scenario_count": len(PATTERN_SCENARIOS),
            "analysis_scenario_count": len(ANALYSIS_SCENARIOS),
        },
        "pattern_scenarios": _pattern_fixtures(),
        "analysis_scenarios": _analysis_fixtures(),
    }


def _assert_pristine_baseline_source():
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    engine_hash = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if commit != BASELINE_COMMIT or engine_hash != BASELINE_ENGINE_SHA256:
        raise RuntimeError(
            "baseline generation is locked to the recorded pre-migration commit "
            "and engine source"
        )


def main():
    _assert_pristine_baseline_source()
    payload = json.dumps(build_baseline(), indent=2, sort_keys=True) + "\n"
    with FIXTURE_PATH.open("x", encoding="utf-8", newline="\n") as fixture:
        fixture.write(payload)
    print(f"wrote immutable baseline: {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
