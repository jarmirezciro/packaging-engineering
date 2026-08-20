"""
Run the KolliPack BR1-BR7 benchmark.

Place this file in:
C:\PackagingEngineering\engine_development_notes\transport_container_selection

Then run it in Spyder.

It reads:
KolliPack_BR1_BR7_All_700_Cases_Inputs.csv

It always imports the current engine from:
C:\PackagingEngineering\packagingapp\utils\container_tool\engine.py

It creates:
kollipack_br1_br7_benchmark_YYYYMMDD.csv
"""

# ============================================================
# 1. SETTINGS
# ============================================================

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(r"C:\PackagingEngineering")

BENCHMARK_FOLDER = (
    PROJECT_ROOT
    / "engine_development_notes"
    / "transport_container_selection"
)

INPUT_FILE = (
    BENCHMARK_FOLDER
    / "KolliPack_BR1_BR7_All_700_Cases_Inputs.csv"
)

TODAY = datetime.now().strftime("%Y%m%d")

OUTPUT_FILE = (
    BENCHMARK_FOLDER
    / f"kollipack_br1_br7_benchmark_{TODAY}.csv"
)


# All four Transport Container modes.
MODES = [
    "space_evenly",
    "space_evenly_infill",
    "front_to_back",
    "front_to_back_infill",
]


# None = run all 700 cases.
#
# If you only want to test that the script works first:
# MAX_CASES = 5
#
# For the real benchmark:
MAX_CASES = None


# ============================================================
# 2. IMPORT THE CURRENT ENGINE
# ============================================================

# This allows the script to find "packagingapp" even if Spyder's
# working directory is the benchmark folder.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packagingapp.utils.container_tool import engine


# ============================================================
# 3. HELPERS
# ============================================================

def to_bool(value):
    """Convert CSV True/False values to Python booleans."""
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
    }


def make_container(case_rows):
    """Create the container input expected by engine.pack_container()."""

    first = case_rows.iloc[0]

    return {
        "L": float(first["container_length_mm"]),
        "W": float(first["container_width_mm"]),
        "H": float(first["container_height_mm"]),

        # BR1-BR7 is a geometry benchmark.
        # We do not use weight restrictions here.
        "max_weight": None,
        "tare_weight": None,
    }


def make_products(case_rows):
    """Create the list of KolliPack product inputs for one BR case."""

    products = []

    # Keep the original academic product order.
    case_rows = case_rows.sort_values("product_id")

    for row_index, (_, row) in enumerate(case_rows.iterrows()):

        products.append(
            {
                "name": str(row["product_name"]),

                "length": float(row["length_mm"]),
                "width": float(row["width_mm"]),
                "height": float(row["height_mm"]),

                "qty": int(row["qty"]),

                # No weight restriction in BR1-BR7.
                "weight": 0.0,

                "stackable": to_bool(row["stackable"]),
                "sequence": int(row["sequence"]),

                # Orientation permissions are already converted
                # to KolliPack R1/R2/R3 in the input CSV.
                "r1": to_bool(row["R1"]),
                "r2": to_bool(row["R2"]),
                "r3": to_bool(row["R3"]),

                # Stable identity used by the engine.
                "_row_index": row_index,
            }
        )

    return products


def calculate_requested_volume(products):
    """Requested cargo volume in mm³."""

    return sum(
        product["length"]
        * product["width"]
        * product["height"]
        * product["qty"]
        for product in products
    )


def calculate_loaded_volume(placements):
    """Volume actually loaded by KolliPack in mm³."""

    return sum(
        placement.l
        * placement.w
        * placement.h
        for placement in placements
    )


def validate_geometry(placements, container):
    """
    Use KolliPack's current geometry validator.

    It checks:
    - container bounds
    - positive-volume overlaps
    - support for elevated placements
    """

    validator = getattr(
        engine,
        "_validate_frontier_geometry",
        None,
    )

    if validator is None:
        return False, "KolliPack geometry validator not found"

    valid, reason = validator(
        placements,
        container,
    )

    return bool(valid), reason or ""


# ============================================================
# 4. RUN ONE CASE / ONE MODE
# ============================================================

def run_case(case_rows, mode):

    first = case_rows.iloc[0]

    container = make_container(case_rows)
    products = make_products(case_rows)

    container_volume = (
        container["L"]
        * container["W"]
        * container["H"]
    )

    requested_units = sum(
        product["qty"]
        for product in products
    )

    requested_volume = calculate_requested_volume(products)

    requested_volume_util_pct = (
        100.0
        * requested_volume
        / container_volume
    )

    # --------------------------------------------------------
    # Run the actual KolliPack engine
    # --------------------------------------------------------

    start = time.perf_counter()

    result = engine.pack_container(
        container,
        products,
        mode=mode,
    )

    runtime_s = time.perf_counter() - start

    placements = list(
        result.get("placements") or []
    )

    loaded_units = len(placements)

    loaded_volume = calculate_loaded_volume(
        placements
    )

    util_pct = (
        100.0
        * loaded_volume
        / container_volume
    )

    valid, validation_reason = validate_geometry(
        placements,
        container,
    )

    # Same columns as our original 2026-08-18 benchmark.
    return {
        "class": str(first["benchmark_class"]),
        "instance": int(first["case_number"]),
        "seed": int(first["seed"]),
        "mode": mode,
        "box_types": int(first["number_of_box_types"]),
        "requested_units": int(requested_units),
        "loaded_units": int(loaded_units),
        "requested_volume_util_pct": float(
            requested_volume_util_pct
        ),
        "util_pct": float(util_pct),
        "runtime_s": float(runtime_s),
        "valid": bool(valid),
        "validation_reason": validation_reason,
    }


# ============================================================
# 5. PRINT RESULTS SUMMARY
# ============================================================

def print_summary(results):

    print("\n")
    print("=" * 70)
    print("KOLLIPACK BR1-BR7 SUMMARY")
    print("=" * 70)

    overall = (
        results
        .groupby("mode", sort=False)
        .agg(
            cases=("util_pct", "count"),
            average_utilization=("util_pct", "mean"),
            median_utilization=("util_pct", "median"),
            average_runtime_s=("runtime_s", "mean"),
            invalid_results=(
                "valid",
                lambda values: int((~values).sum()),
            ),
        )
    )

    print("\nOverall:")
    print(overall.round(3))

    by_class = results.pivot_table(
        index="class",
        columns="mode",
        values="util_pct",
        aggfunc="mean",
    )

    print("\nAverage utilization by BR class:")
    print(by_class.round(3))


# ============================================================
# 6. MAIN
# ============================================================

def main():

    print("=" * 70)
    print("KolliPack BR1-BR7 Benchmark")
    print("=" * 70)

    print("\nCurrent engine:")
    print(
        PROJECT_ROOT
        / "packagingapp"
        / "utils"
        / "container_tool"
        / "engine.py"
    )

    print("\nInput:")
    print(INPUT_FILE)

    print("\nOutput:")
    print(OUTPUT_FILE)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"\nInput file not found:\n{INPUT_FILE}"
        )

    # --------------------------------------------------------
    # Read all 700 academic cases
    # --------------------------------------------------------

    data = pd.read_csv(INPUT_FILE)

    # Get the 700 case IDs in BR1 -> BR7 order.
    cases = (
        data[
            [
                "benchmark_class",
                "case_number",
                "case_id",
            ]
        ]
        .drop_duplicates()
        .copy()
    )

    cases["class_number"] = (
        cases["benchmark_class"]
        .str.extract(r"(\d+)")
        .astype(int)
    )

    cases = cases.sort_values(
        [
            "class_number",
            "case_number",
        ]
    )

    case_ids = cases["case_id"].tolist()

    if MAX_CASES is not None:
        case_ids = case_ids[:MAX_CASES]

    total_cases = len(case_ids)
    total_runs = total_cases * len(MODES)

    print(f"\nCases: {total_cases}")
    print(f"Modes: {len(MODES)}")
    print(f"Total engine runs: {total_runs}\n")

    benchmark_start = time.perf_counter()

    benchmark_rows = []

    # --------------------------------------------------------
    # Main benchmark loop
    # --------------------------------------------------------

    for case_number, case_id in enumerate(
        case_ids,
        start=1,
    ):

        case_rows = data[
            data["case_id"] == case_id
        ]

        for mode in MODES:

            try:
                benchmark_row = run_case(
                    case_rows,
                    mode,
                )

            except Exception as error:

                # Keep the benchmark running if an experimental
                # engine version fails on one case.
                first = case_rows.iloc[0]

                print(
                    f"ERROR: {case_id} / {mode} -> {error}"
                )

                benchmark_row = {
                    "class": str(
                        first["benchmark_class"]
                    ),
                    "instance": int(
                        first["case_number"]
                    ),
                    "seed": int(first["seed"]),
                    "mode": mode,
                    "box_types": int(
                        first["number_of_box_types"]
                    ),
                    "requested_units": int(
                        case_rows["qty"].sum()
                    ),
                    "loaded_units": 0,
                    "requested_volume_util_pct": float("nan"),
                    "util_pct": 0.0,
                    "runtime_s": float("nan"),
                    "valid": False,
                    "validation_reason": (
                        f"{type(error).__name__}: {error}"
                    ),
                }

            benchmark_rows.append(
                benchmark_row
            )

        # Simple progress information.
        if (
            case_number == 1
            or case_number % 25 == 0
            or case_number == total_cases
        ):

            elapsed = (
                time.perf_counter()
                - benchmark_start
            )

            print(
                f"Completed "
                f"{case_number}/{total_cases} cases "
                f"- elapsed {elapsed:.1f} s"
            )

    # --------------------------------------------------------
    # Create and save the result CSV
    # --------------------------------------------------------

    results = pd.DataFrame(
        benchmark_rows
    )

    # Keep the column order identical to the original benchmark.
    results = results[
        [
            "class",
            "instance",
            "seed",
            "mode",
            "box_types",
            "requested_units",
            "loaded_units",
            "requested_volume_util_pct",
            "util_pct",
            "runtime_s",
            "valid",
            "validation_reason",
        ]
    ]

    results.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    total_time = (
        time.perf_counter()
        - benchmark_start
    )

    # --------------------------------------------------------
    # Console summary
    # --------------------------------------------------------

    print_summary(results)

    print("\n")
    print("=" * 70)
    print("FINISHED")
    print("=" * 70)

    print(
        f"\nTotal benchmark time: "
        f"{total_time:.1f} seconds"
    )

    print("\nCSV saved here:")
    print(OUTPUT_FILE)

    invalid_count = int(
        (~results["valid"]).sum()
    )

    if invalid_count == 0:
        print(
            "\nGeometry validation: "
            "ALL RUNS VALID"
        )
    else:
        print(
            f"\nWARNING: "
            f"{invalid_count} runs failed "
            f"or produced invalid geometry."
        )


# ============================================================
# 7. START
# ============================================================

if __name__ == "__main__":
    main()
