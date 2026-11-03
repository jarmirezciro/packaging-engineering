"""Numerically safe, tool-independent 2D rectangle geometry helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple


REPRESENTATION_TOLERANCE_ULPS = 8
DEFAULT_MAX_MATERIALIZED_PLACEMENTS = 20_000


class PlacementBudgetExceeded(RuntimeError):
    """Raised before a pattern materializes an unbounded number of rectangles."""


@dataclass(frozen=True)
class Placement2D:
    x: float
    y: float
    l: float
    w: float
    orientation: str


def representation_tolerance(*values: float) -> float:
    """Return an ULP-scaled tolerance for representation error only."""
    finite = [abs(float(value)) for value in values if math.isfinite(float(value))]
    scale = max(finite or [1.0])
    return REPRESENTATION_TOLERANCE_ULPS * math.ulp(scale)


def fits_within(required: float, available: float) -> bool:
    required = float(required)
    available = float(available)
    if not math.isfinite(required) or not math.isfinite(available):
        return False
    return required <= available or required - available <= representation_tolerance(
        required, available
    )


def count_fitting_units(available: float, unit: float) -> int:
    """Floor ``available / unit`` without losing a converted exact multiple."""
    try:
        available = float(available)
        unit = float(unit)
    except (TypeError, ValueError, OverflowError):
        return 0
    if (
        not math.isfinite(available)
        or not math.isfinite(unit)
        or available <= 0
        or unit <= 0
    ):
        return 0
    quotient = available / unit
    if not math.isfinite(quotient):
        return 0
    count = max(math.floor(quotient), 0)
    return count + 1 if fits_within((count + 1) * unit, available) else count


def orientation_name(l: float, w: float, base_l: float, base_w: float) -> str:
    tolerance = representation_tolerance(l, w, base_l, base_w)
    if abs(l - base_l) <= tolerance and abs(w - base_w) <= tolerance:
        return "LxW"
    return "WxL"


def grid_quantity(area_l: float, area_w: float, box_l: float, box_w: float) -> int:
    return count_fitting_units(area_l, box_l) * count_fitting_units(area_w, box_w)


def grid_fill(
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
    base_l: float,
    base_w: float,
    x0: float = 0.0,
    y0: float = 0.0,
    *,
    max_placements: int = DEFAULT_MAX_MATERIALIZED_PLACEMENTS,
) -> List[Placement2D]:
    nx = count_fitting_units(area_l, box_l)
    ny = count_fitting_units(area_w, box_w)
    quantity = nx * ny
    if quantity > max_placements:
        raise PlacementBudgetExceeded(
            f"grid requires {quantity} placements; budget is {max_placements}"
        )
    orientation = orientation_name(box_l, box_w, base_l, base_w)
    return [
        Placement2D(
            x=x0 + i * box_l,
            y=y0 + j * box_w,
            l=box_l,
            w=box_w,
            orientation=orientation,
        )
        for j in range(ny)
        for i in range(nx)
    ]


def best_grid(
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
    x0: float = 0.0,
    y0: float = 0.0,
) -> List[Placement2D]:
    first_count = grid_quantity(area_l, area_w, box_l, box_w)
    second_count = grid_quantity(area_l, area_w, box_w, box_l)
    if first_count >= second_count:
        return grid_fill(area_l, area_w, box_l, box_w, box_l, box_w, x0, y0)
    return grid_fill(area_l, area_w, box_w, box_l, box_l, box_w, x0, y0)


def translate(
    placements: Sequence[Placement2D], dx: float, dy: float
) -> List[Placement2D]:
    return [
        Placement2D(p.x + dx, p.y + dy, p.l, p.w, p.orientation)
        for p in placements
    ]


def bounding_box(
    placements: Sequence[Placement2D],
) -> Tuple[float, float, float, float]:
    if not placements:
        return 0.0, 0.0, 0.0, 0.0
    return (
        min(p.x for p in placements),
        min(p.y for p in placements),
        max(p.x + p.l for p in placements),
        max(p.y + p.w for p in placements),
    )


def center_on_area(
    placements: Sequence[Placement2D], area_l: float, area_w: float
) -> List[Placement2D]:
    if not placements:
        return []
    min_x, min_y, max_x, max_y = bounding_box(placements)
    dx = (area_l - (max_x - min_x)) / 2.0 - min_x
    dy = (area_w - (max_y - min_y)) / 2.0 - min_y
    tolerance = representation_tolerance(area_l, area_w)
    return [
        Placement2D(
            0.0 if abs(p.x + dx) <= tolerance else p.x + dx,
            0.0 if abs(p.y + dy) <= tolerance else p.y + dy,
            p.l,
            p.w,
            p.orientation,
        )
        for p in placements
    ]
