"""Optional direct Transport Container timing baseline.

Compare Maximum Utilization and Space Evenly with:

    python -m packagingapp.tests.benchmark_transport_container_engine

Add ``--all-modes`` to include Accessible and Strict Sequence Loading. Timings
are diagnostic output only; this module intentionally has no wall-clock test
assertions.
"""

import argparse
import json
from collections import Counter
from time import perf_counter

from packagingapp.utils.container_tool.engine import pack_container


def product(name, length, width, height, qty, *, weight=0.0, sequence=1):
    return {
        "name": name,
        "length": float(length),
        "width": float(width),
        "height": float(height),
        "qty": int(qty),
        "weight": float(weight),
        "sequence": int(sequence),
        "stackable": True,
        "r1": True,
        "r2": False,
        "r3": False,
    }


def scenarios():
    pallet = product(
        "EUR palletized load",
        1200,
        800,
        1100,
        20,
        weight=900,
    )
    return {
        "one_product_100_units": [
            product("Medium load", 500, 400, 700, 100),
        ],
        "two_products_120_units": [
            pallet,
            product("Medium load", 500, 400, 700, 100),
        ],
        "three_products_170_units": [
            pallet,
            product("Medium load", 500, 400, 700, 100),
            product("Small load", 300, 300, 500, 50),
        ],
    }


def measure(mode, name, products):
    container = {
        "L": 12032.0,
        "W": 2352.0,
        "H": 2395.0,
        "max_weight": 26500.0,
        "packing_mode": mode,
    }
    started = perf_counter()
    result = pack_container(container, products)
    elapsed = perf_counter() - started
    counts = Counter(
        placement.row_index for placement in result["placements"]
    )
    diagnostics = {
        key: result.get(key)
        for key in (
            "space_evenly_effective_height",
            "space_evenly_ceiling_candidate_count",
            "space_evenly_ceiling_candidates_evaluated",
            "space_evenly_block_candidates_evaluated",
            "space_evenly_total_block_candidates_evaluated",
        )
        if key in result
    }
    return {
        "scenario": name,
        "mode": mode,
        "requested_units": sum(item["qty"] for item in products),
        "packed_by_row": {
            str(row_index): counts[row_index]
            for row_index in range(len(products))
        },
        "unplaced_units": len(result["unplaced"]),
        "strategy": result.get("strategy"),
        "elapsed_seconds": round(elapsed, 6),
        **diagnostics,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all-modes",
        action="store_true",
        help="Also benchmark Accessible and Strict Sequence Loading.",
    )
    args = parser.parse_args()
    modes = ["maximum_utilization", "space_evenly"]
    if args.all_modes:
        modes.extend(["accessible_sequence_loading", "sequence_loading"])

    results = [
        measure(mode, name, products)
        for name, products in scenarios().items()
        for mode in modes
    ]
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
