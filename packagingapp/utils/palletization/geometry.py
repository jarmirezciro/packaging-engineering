"""Shared physical geometry helpers for palletized-load handoffs."""

import math


def _placement_value(placement, attribute, default=None):
    if isinstance(placement, dict):
        return placement.get(attribute, default)
    return getattr(placement, attribute, default)


def palletized_load_footprint(pallet_l, pallet_w, placements=None):
    """Return the physical XY envelope of a pallet and its carton placements.

    Inputs and outputs use canonical millimetres. Invalid placements are ignored
    and an empty or invalid placement set safely falls back to the physical
    pallet envelope. No display rounding is applied here.
    """
    try:
        pallet_l = float(pallet_l)
        pallet_w = float(pallet_w)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(pallet_l) or not math.isfinite(pallet_w):
        return None
    if pallet_l <= 0 or pallet_w <= 0:
        return None

    min_x = 0.0
    max_x = pallet_l
    min_y = 0.0
    max_y = pallet_w
    valid_placements = 0

    for placement in placements or ():
        try:
            x = float(_placement_value(placement, "x"))
            y = float(_placement_value(placement, "y"))
            length = float(
                _placement_value(placement, "l", _placement_value(placement, "dx"))
            )
            width = float(
                _placement_value(placement, "w", _placement_value(placement, "dy"))
            )
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (x, y, length, width)):
            continue
        if length <= 0 or width <= 0:
            continue

        min_x = min(min_x, x)
        max_x = max(max_x, x + length)
        min_y = min(min_y, y)
        max_y = max(max_y, y + width)
        valid_placements += 1

    return {
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "length": max_x - min_x,
        "width": max_y - min_y,
        "center_x": (min_x + max_x) / 2.0,
        "center_y": (min_y + max_y) / 2.0,
        "placement_count": valid_placements,
    }
