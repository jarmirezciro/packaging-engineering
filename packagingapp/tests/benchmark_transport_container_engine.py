"""Optional direct Transport Container timing baseline.

Compare Maximum Utilization and Space Evenly with:

    python -m packagingapp.tests.benchmark_transport_container_engine

Add ``--floor-first`` to include the isolated Maximum Utilization Floor First
variant, or ``--all-modes`` to include every mode. Timings are diagnostic output
only; this module intentionally has no wall-clock test assertions.
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
        "four_products_200_units": [
            pallet,
            product("Medium load", 500, 400, 700, 100),
            product("Small load", 300, 300, 500, 50),
            product("Door residual load", 250, 200, 400, 30),
        ],
        "reported_four_products_1228_units": [
            product("SKU302473", 457.2, 279.4, 317.5, 375, weight=0.227, sequence=1),
            product("SKU503739", 431.8, 318.77, 317.5, 405, weight=0.907, sequence=2),
            product("Case Pack 12", 558.8, 377.444, 317.5, 288, weight=0.907, sequence=3),
            product("Case Pack", 558.8, 355.6, 381.0, 160, weight=2.268, sequence=4),
        ],
    }


def measure(mode, name, products):
    reported_case = name == "reported_four_products_1228_units"
    container = {
        "L": 12039.0 if reported_case else 12032.0,
        "W": 2362.0 if reported_case else 2352.0,
        "H": 2692.0 if reported_case else 2395.0,
        "max_weight": 26000.0 if reported_case else 26500.0,
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
            "space_evenly_main_block_count",
            "space_evenly_main_block_units",
            "space_evenly_residual_units",
            "space_evenly_residual_zone_start",
            "space_evenly_block_candidates_generated",
            "space_evenly_beam_states_evaluated",
            "space_evenly_residual_states_evaluated",
            "space_evenly_residual_candidates_evaluated",
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
        "--floor-first",
        action="store_true",
        help="Also benchmark Maximum Utilization Floor First.",
    )
    parser.add_argument(
        "--all-modes",
        action="store_true",
        help="Benchmark every Transport Container packing mode.",
    )
    parser.add_argument(
        "--space-only",
        action="store_true",
        help="Run only the bounded Space Evenly scenarios.",
    )
    args = parser.parse_args()
    modes = (
        ["space_evenly"]
        if args.space_only
        else ["maximum_utilization", "space_evenly"]
    )
    if args.all_modes:
        modes.extend([
            "maximum_utilization_floor_first",
            "accessible_sequence_loading",
            "sequence_loading",
        ])
    elif args.floor_first:
        modes.append("maximum_utilization_floor_first")

    results = [
        measure(mode, name, products)
        for name, products in scenarios().items()
        for mode in modes
    ]
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
