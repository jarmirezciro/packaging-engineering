"""Authoritative, policy-driven rectangular mosaic pattern geometry.

The construction logic is shared by Container Selection and Palletization.
Policies vary only numerical fit behavior and bounded search coverage; pallet
stacking, interlock display, load checks, and ranking remain outside this module.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Dict, List, Optional, Tuple

from .geometry import (
    Placement2D,
    PlacementBudgetExceeded,
    count_fitting_units,
    fits_within,
    orientation_name as robust_orientation_name,
    representation_tolerance,
)


@dataclass(frozen=True)
class PatternSearchPolicy:
    name: str
    fit_mode: str
    max_pinwheel_parameter: int
    max_pinwheel_candidates: int
    max_materialized_placements: Optional[int] = None


CONTAINER_SEARCH_POLICY = PatternSearchPolicy(
    name="container",
    fit_mode="representation_safe",
    max_pinwheel_parameter=12,
    max_pinwheel_candidates=8,
    max_materialized_placements=20_000,
)

PALLETIZATION_SEARCH_POLICY = PatternSearchPolicy(
    name="palletization",
    fit_mode="legacy_floor",
    max_pinwheel_parameter=30,
    max_pinwheel_candidates=80,
    max_materialized_placements=None,
)

_ACTIVE_POLICY: ContextVar[Optional[PatternSearchPolicy]] = ContextVar(
    "packing_pattern_search_policy", default=None
)


def _policy() -> PatternSearchPolicy:
    return _ACTIVE_POLICY.get() or CONTAINER_SEARCH_POLICY


def _policy_scoped(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        requested = kwargs.pop("policy", None)
        active = _ACTIVE_POLICY.get()
        if requested is None and active is not None:
            return function(*args, **kwargs)
        if requested is active and active is not None:
            return function(*args, **kwargs)
        selected = requested or active or CONTAINER_SEARCH_POLICY
        token = _ACTIVE_POLICY.set(selected)
        try:
            return function(*args, **kwargs)
        finally:
            _ACTIVE_POLICY.reset(token)

    return wrapper


def call_with_policy(function, *args, policy: PatternSearchPolicy, **kwargs):
    """Run a non-public geometry helper under an explicit consumer policy."""
    active = _ACTIVE_POLICY.get()
    if active is policy:
        return function(*args, **kwargs)
    token = _ACTIVE_POLICY.set(policy)
    try:
        return function(*args, **kwargs)
    finally:
        _ACTIVE_POLICY.reset(token)


def _fit_count(available: float, unit: float) -> int:
    if _policy().fit_mode == "representation_safe":
        return count_fitting_units(available, unit)
    if available <= 0 or unit <= 0:
        return 0
    return max(int(available // unit), 0)

def orientation_name(l: float, w: float, base_l: float, base_w: float) -> str:
    if _policy().fit_mode == "representation_safe":
        return robust_orientation_name(l, w, base_l, base_w)
    if abs(l - base_l) < 1e-9 and abs(w - base_w) < 1e-9:
        return "LxW"
    return "WxL"

def rect_overlap_area(a: Placement2D, b: Placement2D) -> float:
    x_overlap = max(0, min(a.x + a.l, b.x + b.l) - max(a.x, b.x))
    y_overlap = max(0, min(a.y + a.w, b.y + b.w) - max(a.y, b.y))
    return x_overlap * y_overlap

def within_area(p: Placement2D, area_l: float, area_w: float) -> bool:
    if _policy().fit_mode == "representation_safe":
        tolerance = representation_tolerance(p.x, p.y, p.l, p.w, area_l, area_w)
        return (
            p.x >= -tolerance
            and p.y >= -tolerance
            and fits_within(p.x + p.l, area_l)
            and fits_within(p.y + p.w, area_w)
        )
    return (
        p.x >= 0
        and p.y >= 0
        and p.x + p.l <= area_l + 1e-9
        and p.y + p.w <= area_w + 1e-9
    )

def grid_fill(
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
    base_l: float,
    base_w: float,
    x0: float = 0,
    y0: float = 0,
) -> List[Placement2D]:
    nx = _fit_count(area_l, box_l)
    ny = _fit_count(area_w, box_w)
    quantity = nx * ny
    budget = _policy().max_materialized_placements
    if budget is not None and quantity > budget:
        raise PlacementBudgetExceeded(
            f"grid requires {quantity} placements; budget is {budget}"
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

def try_two_orientations_grid(
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
    base_l: float,
    base_w: float,
    x0: float = 0,
    y0: float = 0,
) -> List[Placement2D]:
    p1 = grid_fill(area_l, area_w, box_l, box_w, base_l, base_w, x0, y0)
    p2 = grid_fill(area_l, area_w, box_w, box_l, base_l, base_w, x0, y0)
    return p1 if len(p1) >= len(p2) else p2

@_policy_scoped
def pattern_block(area_l, area_w, box_l, box_w):
    p1 = grid_fill(area_l, area_w, box_l, box_w, box_l, box_w)
    p2 = grid_fill(area_l, area_w, box_w, box_l, box_l, box_w)
    return p1 if len(p1) >= len(p2) else p2

@_policy_scoped
def pattern_row(area_l, area_w, box_l, box_w):
    p1 = grid_fill(area_l, area_w, box_l, box_w, box_l, box_w)
    p2 = grid_fill(area_l, area_w, box_w, box_l, box_l, box_w)

    rows1 = _fit_count(area_w, box_w)
    rows2 = _fit_count(area_w, box_l)

    if rows1 > rows2:
        return p1
    if rows2 > rows1:
        return p2
    return p1 if len(p1) >= len(p2) else p2

def _near_integer(value: float, tolerance: float = 1e-6) -> Optional[int]:
    """Return the nearest integer when a dimension ratio is effectively exact."""
    if value <= 0:
        return None
    rounded = int(round(value))
    if rounded <= 0:
        return None
    return rounded if abs(value - rounded) <= tolerance else None

def _is_brick_ratio(box_l: float, box_w: float, tolerance: float = 0.02) -> bool:
    """Return True when the carton footprint is close to a 2:1 ratio.

    The customer-facing Brick result represents a bonded / basket-weave /
    spiral mosaic, not a generic staggered row. The normalized footprint ratio
    must therefore be close to 2.0. With the default tolerance, the accepted
    range is approximately 1.98 <= ratio <= 2.02.
    """
    short_side = min(box_l, box_w)
    long_side = max(box_l, box_w)

    if short_side <= 0:
        return False

    ratio = long_side / short_side
    return abs(ratio - 2.0) <= tolerance

def _spiral_domino_pairs(cols: int, rows: int) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """Return adjacent cell pairs following a clockwise inward spiral.

    The bonded brick drawing used in pallet-pattern charts is often easier to
    think of as dominoes on a short-side grid. For a 400 x 200 carton on a
    1200 x 1200 pallet the grid is 6 x 6; pairing the cells ring-by-ring gives
    18 cartons and creates the visible spiral instead of a checkerboard of
    independent 400 x 400 modules.
    """
    if cols < 2 or rows < 2 or (cols * rows) % 2 != 0:
        return []

    pairs: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
    left, top = 0, 0
    right, bottom = cols - 1, rows - 1

    while left <= right and top <= bottom:
        path: List[Tuple[int, int]] = []

        for x in range(left, right + 1):
            path.append((x, top))
        for y in range(top + 1, bottom + 1):
            path.append((right, y))
        if bottom > top:
            for x in range(right - 1, left - 1, -1):
                path.append((x, bottom))
        if right > left:
            for y in range(bottom - 1, top, -1):
                path.append((left, y))

        # Odd rings cannot be fully tiled by same-size cartons. Fallback to the
        # alternative brick candidates instead of producing an awkward partial
        # pattern.
        if len(path) % 2 != 0:
            return []

        for idx in range(0, len(path), 2):
            a = path[idx]
            b = path[idx + 1]
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                return []
            pairs.append((a, b))

        left += 1
        top += 1
        right -= 1
        bottom -= 1

    return pairs

@_policy_scoped
def pattern_brick_spiral_weave(area_l, area_w, box_l, box_w):
    """Return a spiral bonded-brick layer for clean 2:1 cartons.

    This is the customer-facing brick illustration users expect for examples
    like 400 x 200 on a 1200 x 1200 pallet: the cartons follow a continuous
    clockwise/inward bond, so the top view reads as a spiral rather than a
    checkerboard.
    """
    if min(area_l, area_w, box_l, box_w) <= 0:
        return []

    short_side = min(box_l, box_w)
    long_side = max(box_l, box_w)
    ratio = _near_integer(long_side / short_side)

    # The spiral domino construction is exact for the common 2:1 carton. Other
    # clean ratios continue to use the module basket-weave fallback below.
    if ratio != 2:
        return []

    cols = _fit_count(area_l, short_side)
    rows = _fit_count(area_w, short_side)
    if cols < 2 or rows < 2:
        return []

    used_l = cols * short_side
    used_w = rows * short_side
    x0 = (area_l - used_l) / 2.0
    y0 = (area_w - used_w) / 2.0

    pairs = _spiral_domino_pairs(cols, rows)
    if not pairs:
        return []

    placements: List[Placement2D] = []
    for a, b in pairs:
        x_cell = min(a[0], b[0])
        y_cell = min(a[1], b[1])
        cell_l = abs(a[0] - b[0]) + 1
        cell_w = abs(a[1] - b[1]) + 1
        l = cell_l * short_side
        w = cell_w * short_side
        placements.append(
            Placement2D(
                x=x0 + x_cell * short_side,
                y=y0 + y_cell * short_side,
                l=l,
                w=w,
                orientation=orientation_name(l, w, box_l, box_w),
            )
        )

    return placements if placements_are_valid(placements, area_l, area_w) else []

@_policy_scoped
def pattern_brick_basket_weave(area_l, area_w, box_l, box_w):
    """Return bonded brick candidates for integer-ratio rectangular cartons.

    Preference order:

    * spiral bonded brick for exact 2:1 cartons, which matches the usual brick
      pattern illustration and is most readable in the render;
    * square-module basket weave fallback for other clean integer ratios.
    """
    if min(area_l, area_w, box_l, box_w) <= 0:
        return []

    candidates: List[List[Placement2D]] = []

    spiral_layer = pattern_brick_spiral_weave(area_l, area_w, box_l, box_w)
    if spiral_layer:
        candidates.append(spiral_layer)

    short_side = min(box_l, box_w)
    long_side = max(box_l, box_w)
    ratio = _near_integer(long_side / short_side)

    # The classic module basket-weave layer is meaningful when the long side can
    # be decomposed into an integer number of short-side strips.
    if ratio is None or ratio < 2 or ratio > 6:
        return candidates

    modules_x = _fit_count(area_l, long_side)
    modules_y = _fit_count(area_w, long_side)
    if modules_x <= 0 or modules_y <= 0:
        return candidates

    used_l = modules_x * long_side
    used_w = modules_y * long_side
    x0 = (area_l - used_l) / 2.0
    y0 = (area_w - used_w) / 2.0

    for phase in (0, 1):
        placements: List[Placement2D] = []
        for my in range(modules_y):
            for mx in range(modules_x):
                module_x = x0 + mx * long_side
                module_y = y0 + my * long_side
                horizontal_module = ((mx + my + phase) % 2 == 0)

                if horizontal_module:
                    for k in range(ratio):
                        placements.append(
                            Placement2D(
                                x=module_x,
                                y=module_y + k * short_side,
                                l=long_side,
                                w=short_side,
                                orientation=orientation_name(long_side, short_side, box_l, box_w),
                            )
                        )
                else:
                    for k in range(ratio):
                        placements.append(
                            Placement2D(
                                x=module_x + k * short_side,
                                y=module_y,
                                l=short_side,
                                w=long_side,
                                orientation=orientation_name(short_side, long_side, box_l, box_w),
                            )
                        )

        if placements_are_valid(placements, area_l, area_w):
            signature = layer_geometry_signature(placements)
            if all(layer_geometry_signature(existing) != signature for existing in candidates):
                candidates.append(placements)

    return candidates

@_policy_scoped
def pattern_brick(area_l, area_w, box_l, box_w, rotated=False):
    """Return a conservative, customer-facing brick layer.

    A brick pattern should look like a brick wall: full rows alternate with
    rows shifted by half a case. The previous implementation started every
    layer at x=0 and only moved alternate rows to the right. That sometimes
    preserved the case count, but it created visually unbalanced rows and could
    even fall back to a plain block layout while still being labelled "Brick".

    This generator is intentionally stricter:

    * every row group is centered on the pallet footprint;
    * shifted rows use one fewer case and are centered between the full rows;
    * the function returns an empty layer when a real staggered brick layout is
      not possible, instead of silently returning a block pattern.
    """
    base_l, base_w = box_l, box_w
    work_l, work_w = (box_w, box_l) if rotated else (box_l, box_w)

    if min(area_l, area_w, work_l, work_w) <= 0:
        return []

    rows = _fit_count(area_w, work_w)
    full_cols = _fit_count(area_l, work_l)

    # A visible brick pattern needs at least two rows and two cases in a full
    # row. The shifted row then contains full_cols - 1 centered cases.
    if rows < 2 or full_cols < 2:
        return []

    shifted_cols = full_cols - 1
    used_w = rows * work_w
    full_row_l = full_cols * work_l
    full_x0 = (area_l - full_row_l) / 2.0
    y0 = (area_w - used_w) / 2.0
    shifted_x0 = full_x0 + (work_l / 2.0)
    ori = orientation_name(work_l, work_w, base_l, base_w)

    placements: List[Placement2D] = []
    for j in range(rows):
        is_shifted = j % 2 == 1
        cols = shifted_cols if is_shifted else full_cols
        x_start = shifted_x0 if is_shifted else full_x0
        y = y0 + j * work_w

        for i in range(cols):
            placements.append(
                Placement2D(
                    x=x_start + i * work_l,
                    y=y,
                    l=work_l,
                    w=work_w,
                    orientation=ori,
                )
            )

    return placements if placements_are_valid(placements, area_l, area_w) else []

def placements_bbox(placements: List[Placement2D]) -> Tuple[float, float, float, float]:
    if not placements:
        return 0.0, 0.0, 0.0, 0.0
    min_x = min(p.x for p in placements)
    min_y = min(p.y for p in placements)
    max_x = max(p.x + p.l for p in placements)
    max_y = max(p.y + p.w for p in placements)
    return min_x, min_y, max_x, max_y

@_policy_scoped
def pattern_brick_best(area_l, area_w, box_l, box_w):
    """Return the best customer-facing brick layout.

    Brick is intentionally restricted to carton footprints that are close to a
    2:1 ratio. The customer-facing Brick result represents a bonded /
    basket-weave / spiral mosaic, not a generic staggered row. For non-2:1
    cartons, other pattern families should carry the result instead.
    """
    if not _is_brick_ratio(box_l, box_w):
        return []

    candidates: List[Tuple[List[Placement2D], int]] = []

    for layer in pattern_brick_basket_weave(area_l, area_w, box_l, box_w):
        if layer:
            # Family priority 2: preferred brick/bonded module.
            candidates.append((layer, 2))

    for rotated in (False, True):
        layer = pattern_brick(area_l, area_w, box_l, box_w, rotated=rotated)
        if layer:
            # Family priority 1: valid fallback, but less representative of the
            # brick-pattern illustration for 2:1 rectangular cartons.
            candidates.append((layer, 1))

    if not candidates:
        return []

    def score(candidate: Tuple[List[Placement2D], int]) -> Tuple[int, float, int, float, float]:
        layer, family_priority = candidate
        min_x, min_y, max_x, max_y = placements_bbox(layer)
        used_l = max_x - min_x
        used_w = max_y - min_y
        pallet_area = area_l * area_w
        layer_area = sum(p.l * p.w for p in layer)
        pallet_util = layer_area / pallet_area if pallet_area > 0 else 0.0
        bbox_area = used_l * used_w
        bbox_util = layer_area / bbox_area if bbox_area > 0 else 0.0
        orientations = {p.orientation for p in layer}
        mixed_orientation_bonus = 1 if len(orientations) > 1 else 0
        return len(layer), pallet_util, family_priority, mixed_orientation_bonus, bbox_util

    return max(candidates, key=score)[0]

def translate_placements(placements: List[Placement2D], dx: float, dy: float) -> List[Placement2D]:
    return [
        Placement2D(
            x=p.x + dx,
            y=p.y + dy,
            l=p.l,
            w=p.w,
            orientation=p.orientation,
        )
        for p in placements
    ]

def center_placements_on_area(
    placements: List[Placement2D],
    area_l: float,
    area_w: float,
) -> List[Placement2D]:
    """Center one layer footprint inside the available pallet area.

    Most pattern generators naturally start at (0, 0). That is valid
    mathematically, but it leaves all remaining clearance on the far edges when
    the selected pattern does not use the complete pallet contour. For customer
    facing interlock results, both alternating layers should share a centered
    footprint so their outside vertices are aligned and the load is visually
    balanced on the pallet.
    """
    if not placements:
        return []

    min_x, min_y, max_x, max_y = placements_bbox(placements)
    used_l = max_x - min_x
    used_w = max_y - min_y

    if used_l <= 0 or used_w <= 0:
        return placements

    dx = ((area_l - used_l) / 2.0) - min_x
    dy = ((area_w - used_w) / 2.0) - min_y

    centered = translate_placements(placements, dx, dy)

    # Avoid exposing tiny floating point artifacts in signatures/rendering.
    cleaned: List[Placement2D] = []
    for p in centered:
        cleaned.append(
            Placement2D(
                x=0.0 if abs(p.x) < 1e-9 else p.x,
                y=0.0 if abs(p.y) < 1e-9 else p.y,
                l=p.l,
                w=p.w,
                orientation=p.orientation,
            )
        )

    return cleaned if placements_are_valid(cleaned, area_l, area_w) else placements

def placements_are_valid(
    placements: List[Placement2D],
    area_l: float,
    area_w: float,
    tolerance: float = 1e-9,
) -> bool:
    for p in placements:
        if not within_area(p, area_l, area_w):
            return False

    # Sweep by x-position so large, dense pallet layers do not pay a full
    # O(n�) overlap check. Once the next rectangle starts after the current
    # rectangle ends in x, later rectangles cannot overlap it.
    ordered = sorted(placements, key=lambda item: (item.x, item.y, item.l, item.w))
    for i, a in enumerate(ordered):
        a_x_end = a.x + a.l
        for b in ordered[i + 1:]:
            if b.x >= a_x_end - tolerance:
                break
            if rect_overlap_area(a, b) > tolerance:
                return False
    return True

def layout_signature(placements: List[Placement2D]) -> Tuple[Tuple[float, float, float, float, str], ...]:
    decimals = 9 if _policy().fit_mode == "representation_safe" else 6
    return tuple(
        sorted(
            (round(p.x, decimals), round(p.y, decimals), round(p.l, decimals), round(p.w, decimals), p.orientation)
            for p in placements
        )
    )

def layer_geometry_signature(placements: List[Placement2D]) -> Tuple[Tuple[float, float, float, float], ...]:
    decimals = 9 if _policy().fit_mode == "representation_safe" else 6
    return tuple(
        sorted(
            (round(p.x, decimals), round(p.y, decimals), round(p.l, decimals), round(p.w, decimals))
            for p in placements
        )
    )

def pinwheel_motif(x0, y0, box_l, box_w, base_l, base_w):
    """Return one 1x1 simple pinwheel motif.

    This is the classical four-leaf pinwheel: H, V, H, V around a central
    square/rectangular hole. It is still useful as a fallback/tiled motif,
    but the main ``pattern_pinwheel`` function below also searches larger
    block pinwheels so Euro-pallet cases such as 230x170 on 1200x800 produce
    one proper full-layer pinwheel instead of six small independent motifs.
    """
    t = box_l + box_w
    placements = [
        Placement2D(x0 + 0,     y0 + 0,     box_l, box_w, orientation_name(box_l, box_w, base_l, base_w)),
        Placement2D(x0 + box_l, y0 + 0,     box_w, box_l, orientation_name(box_w, box_l, base_l, base_w)),
        Placement2D(x0 + box_w, y0 + box_l, box_l, box_w, orientation_name(box_l, box_w, base_l, base_w)),
        Placement2D(x0 + 0,     y0 + box_w, box_w, box_l, orientation_name(box_w, box_l, base_l, base_w)),
    ]
    return placements, t, t

def block_pinwheel_motif(
    x0: float,
    y0: float,
    box_l: float,
    box_w: float,
    base_l: float,
    base_w: float,
    m: int,
    n: int,
    p: int,
    q: int,
) -> Tuple[List[Placement2D], float, float]:
    """Return one m x n - p x q block pinwheel.

    The four leaves are generated as blocks of uniform orientation:

    * bottom horizontal leaf: ``m`` rows x ``n`` columns
    * right vertical leaf: ``p`` rows x ``q`` columns
    * top horizontal leaf: ``m`` rows x ``n`` columns
    * left vertical leaf: ``p`` rows x ``q`` columns

    This follows the practical block-pinwheel family described in the
    pallet-loading literature and gives a single, regular pinwheel contour.
    """
    horizontal_l = n * box_l
    horizontal_w = m * box_w
    vertical_l = q * box_w
    vertical_w = p * box_l

    placements: List[Placement2D] = []

    # 1H: lower-left horizontal block
    placements.extend(grid_fill(horizontal_l, horizontal_w, box_l, box_w, base_l, base_w, x0=x0, y0=y0))

    # 2V: lower-right vertical block
    placements.extend(
        grid_fill(vertical_l, vertical_w, box_w, box_l, base_l, base_w, x0=x0 + horizontal_l, y0=y0)
    )

    # 3H: upper-right horizontal block
    placements.extend(
        grid_fill(horizontal_l, horizontal_w, box_l, box_w, base_l, base_w, x0=x0 + vertical_l, y0=y0 + vertical_w)
    )

    # 4V: upper-left vertical block
    placements.extend(
        grid_fill(vertical_l, vertical_w, box_w, box_l, base_l, base_w, x0=x0, y0=y0 + horizontal_w)
    )

    contour_l = horizontal_l + vertical_l
    contour_w = horizontal_w + vertical_w
    return placements, contour_l, contour_w

def _pinwheel_candidate_score(
    placements: List[Placement2D],
    area_l: float,
    area_w: float,
    candidate_rank: int,
) -> Tuple[int, int, float, float]:
    if not placements:
        return 0, candidate_rank, 0.0, 0.0

    _, _, max_x, max_y = placements_bbox(placements)
    bbox_area = max_x * max_y
    box_area = sum(p.l * p.w for p in placements)
    pallet_area = area_l * area_w
    bbox_util = box_area / bbox_area if bbox_area > 0 else 0.0
    pallet_util = box_area / pallet_area if pallet_area > 0 else 0.0
    return len(placements), candidate_rank, pallet_util, bbox_util

def _dedupe_valid_candidates(
    candidates: List[Tuple[List[Placement2D], int]],
    area_l: float,
    area_w: float,
) -> List[Tuple[List[Placement2D], int]]:
    valid: List[Tuple[List[Placement2D], int]] = []
    seen = set()
    for placements, rank in candidates:
        if not placements_are_valid(placements, area_l, area_w):
            continue
        signature = layout_signature(placements)
        if signature in seen:
            continue
        seen.add(signature)
        valid.append((placements, rank))
    return valid

def _pattern_tiled_simple_pinwheel(area_l, area_w, box_l, box_w, base_l, base_w):
    placements: List[Placement2D] = []
    _, tile_l, tile_w = pinwheel_motif(0, 0, box_l, box_w, base_l, base_w)

    nx = _fit_count(area_l, tile_l)
    ny = _fit_count(area_w, tile_w)

    for j in range(ny):
        for i in range(nx):
            x0 = i * tile_l
            y0 = j * tile_w
            motif, _, _ = pinwheel_motif(x0, y0, box_l, box_w, base_l, base_w)
            placements.extend(motif)

    return placements

def _rotate_layer_90_clockwise(
    placements: List[Placement2D],
    contour_l: float,
    contour_w: float,
    base_l: float,
    base_w: float,
) -> List[Placement2D]:
    """Rotate a complete same-product layer 90 degrees around its contour."""
    rotated: List[Placement2D] = []
    for p in placements:
        new_l = p.w
        new_w = p.l
        rotated.append(
            Placement2D(
                x=contour_w - p.y - p.w,
                y=p.x,
                l=new_l,
                w=new_w,
                orientation=orientation_name(new_l, new_w, base_l, base_w),
            )
        )
    return rotated

def _nine_case_center_filled_pinwheel_motif(
    box_l: float,
    box_w: float,
    base_l: float,
    base_w: float,
) -> Tuple[List[Placement2D], float, float]:
    """Return the verified nine-carton stepped pinwheel topology.

    Every placement is the same carton footprint. Six cartons use the long-side
    horizontal orientation and three are rotated 90 degrees. No pallet or SKU
    dimensions are hardcoded.

    Outside dimensions:

        contour length = 2 * long_side + short_side
        contour width  = long_side + 2 * short_side

    For the confirmed 162 x 114 mm carton this produces a 438 x 390 mm motif.
    """
    if min(box_l, box_w) <= 0:
        return [], 0.0, 0.0

    long_side = max(box_l, box_w)
    short_side = min(box_l, box_w)

    # This topology is compact for ordinary rectangular cartons up to 2:1.
    # More elongated cartons are left to the existing block/tiled generators.
    if long_side <= short_side + 1e-9 or long_side > 2.0 * short_side + 1e-9:
        return [], 0.0, 0.0

    horizontal_l, horizontal_w = long_side, short_side
    vertical_l, vertical_w = short_side, long_side

    horizontal_orientation = orientation_name(
        horizontal_l, horizontal_w, base_l, base_w
    )
    vertical_orientation = orientation_name(
        vertical_l, vertical_w, base_l, base_w
    )

    placements = [
        Placement2D(0.0, 0.0, horizontal_l, horizontal_w, horizontal_orientation),
        Placement2D(long_side, 0.0, horizontal_l, horizontal_w, horizontal_orientation),
        Placement2D(0.0, short_side, horizontal_l, horizontal_w, horizontal_orientation),
        Placement2D(2.0 * long_side, 0.0, vertical_l, vertical_w, vertical_orientation),
        Placement2D(long_side, short_side, vertical_l, vertical_w, vertical_orientation),
        Placement2D(0.0, 2.0 * short_side, vertical_l, vertical_w, vertical_orientation),
        Placement2D(
            long_side + short_side,
            long_side,
            horizontal_l,
            horizontal_w,
            horizontal_orientation,
        ),
        Placement2D(
            short_side,
            long_side + short_side,
            horizontal_l,
            horizontal_w,
            horizontal_orientation,
        ),
        Placement2D(
            long_side + short_side,
            long_side + short_side,
            horizontal_l,
            horizontal_w,
            horizontal_orientation,
        ),
    ]

    contour_l = 2.0 * long_side + short_side
    contour_w = long_side + 2.0 * short_side
    return placements, contour_l, contour_w

@_policy_scoped
def pattern_center_filled_pinwheel(area_l, area_w, box_l, box_w):
    """Return the best valid orientation of the nine-carton topology.

    This is a separate customer candidate. It does not modify the existing
    Pinwheel or Hybrid pinwheel generators, their scoring, or their geometry.
    """
    motif, contour_l, contour_w = _nine_case_center_filled_pinwheel_motif(
        box_l, box_w, box_l, box_w
    )
    if not motif:
        return []

    candidates: List[List[Placement2D]] = []

    def compact_enough(used_l: float, used_w: float) -> bool:
        # The verified nine-carton topology is an explicit catalogue candidate.
        # Do not suppress it with utilization heuristics: if the complete motif
        # fits and validates, keep it available for normal ranking/deduplication.
        return (
            area_l > 0
            and area_w > 0
            and used_l <= area_l + 1e-9
            and used_w <= area_w + 1e-9
        )

    if compact_enough(contour_l, contour_w):
        candidates.append(center_placements_on_area(motif, area_l, area_w))

    rotated = _rotate_layer_90_clockwise(
        motif, contour_l, contour_w, box_l, box_w
    )
    if compact_enough(contour_w, contour_l):
        candidates.append(center_placements_on_area(rotated, area_l, area_w))

    valid = [
        candidate
        for candidate in candidates
        if len(candidate) == 9 and placements_are_valid(candidate, area_l, area_w)
    ]
    if not valid:
        return []

    def clearance_score(layer: List[Placement2D]) -> Tuple[float, float]:
        min_x, min_y, max_x, max_y = placements_bbox(layer)
        free_l = area_l - (max_x - min_x)
        free_w = area_w - (max_y - min_y)
        return (-abs(free_l - free_w), -(free_l + free_w))

    return max(valid, key=clearance_score)


def _perimeter_core_mosaic_motif(
    box_l: float,
    box_w: float,
) -> Tuple[List[Placement2D], float, float]:
    """Build the ten-carton perimeter/core topology in local coordinates.

    The construction is deliberately expressed in the carton dimensions.  It
    is the mathematically validated reconstruction of the Cape Pack reference:
    six ``L x S`` cartons surround four ``S x L`` cartons, where ``L`` is the
    long carton side and ``S`` is the short side.
    """
    if min(box_l, box_w) <= 0:
        return [], 0.0, 0.0

    long_side = max(box_l, box_w)
    short_side = min(box_l, box_w)
    if long_side < 2.0 * short_side - 1e-9:
        return [], 0.0, 0.0

    horizontal_orientation = orientation_name(
        long_side, short_side, box_l, box_w
    )
    rotated_orientation = orientation_name(
        short_side, long_side, box_l, box_w
    )
    placements = [
        Placement2D(0.0, 0.0, short_side, long_side, rotated_orientation),
        Placement2D(0.0, long_side, short_side, long_side, rotated_orientation),
        Placement2D(short_side, 0.0, long_side, short_side, horizontal_orientation),
        Placement2D(short_side + long_side, 0.0, long_side, short_side, horizontal_orientation),
        Placement2D(short_side, 2.0 * long_side - short_side, long_side, short_side, horizontal_orientation),
        Placement2D(short_side + long_side, 2.0 * long_side - short_side, long_side, short_side, horizontal_orientation),
        Placement2D(short_side, short_side, short_side, long_side, rotated_orientation),
        Placement2D(2.0 * long_side, short_side, short_side, long_side, rotated_orientation),
        Placement2D(2.0 * short_side, short_side, long_side, short_side, horizontal_orientation),
        Placement2D(2.0 * short_side, 2.0 * short_side, long_side, short_side, horizontal_orientation),
    ]
    footprint_l = 2.0 * long_side + short_side
    footprint_w = 2.0 * long_side
    if not placements_are_valid(placements, footprint_l, footprint_w):
        return [], 0.0, 0.0
    return placements, footprint_l, footprint_w


def _mirror_layer_x(
    placements: List[Placement2D], contour_l: float
) -> List[Placement2D]:
    return [
        Placement2D(
            contour_l - placement.x - placement.l,
            placement.y,
            placement.l,
            placement.w,
            placement.orientation,
        )
        for placement in placements
    ]


def _mirror_layer_y(
    placements: List[Placement2D], contour_w: float
) -> List[Placement2D]:
    return [
        Placement2D(
            placement.x,
            contour_w - placement.y - placement.w,
            placement.l,
            placement.w,
            placement.orientation,
        )
        for placement in placements
    ]


@_policy_scoped
def pattern_perimeter_core_mosaic(area_l, area_w, box_l, box_w):
    """Return a centered, validated ten-carton perimeter/core mosaic.

    The family is feasible only when ``max(box_l, box_w) >=
    2 * min(box_l, box_w)`` and the complete ``(2L + S) x (2L)`` footprint,
    or its whole-pattern rotation, fits the available area.  No upper aspect
    ratio is imposed.  Mirror and rotation equivalents are independently
    validated before the first deterministic fitting candidate is returned.
    """
    if min(area_l, area_w, box_l, box_w) <= 0:
        return []

    motif, contour_l, contour_w = _perimeter_core_mosaic_motif(box_l, box_w)
    if not motif:
        return []

    candidates = []
    for layer in (
        motif,
        _mirror_layer_x(motif, contour_l),
        _mirror_layer_y(motif, contour_w),
        _mirror_layer_y(_mirror_layer_x(motif, contour_l), contour_w),
    ):
        candidates.append((layer, contour_l, contour_w))

    rotated = _rotate_layer_90_clockwise(
        motif, contour_l, contour_w, box_l, box_w
    )
    for layer in (
        rotated,
        _mirror_layer_x(rotated, contour_w),
        _mirror_layer_y(rotated, contour_l),
        _mirror_layer_y(_mirror_layer_x(rotated, contour_w), contour_l),
    ):
        candidates.append((layer, contour_w, contour_l))

    for layer, used_l, used_w in candidates:
        if used_l > area_l + 1e-9 or used_w > area_w + 1e-9:
            continue
        centered = center_placements_on_area(layer, area_l, area_w)
        if len(centered) == 10 and placements_are_valid(centered, area_l, area_w):
            return centered
    return []

def _enumerate_nested_pinwheel_candidates(
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
    base_l: float,
    base_w: float,
) -> List[List[Placement2D]]:
    """Enumerate block pinwheels whose central opening accepts a simple pinwheel.

    The outer and inner motifs use the same carton SKU. This is additive and
    independent of the existing block-pinwheel enumeration.
    """
    candidates: List[List[Placement2D]] = []
    if min(area_l, area_w, box_l, box_w) <= 0:
        return candidates

    inner_span = box_l + box_w
    box_area = box_l * box_w
    max_param = _policy().max_pinwheel_parameter
    max_generated_candidates = _policy().max_pinwheel_candidates

    horizontal_pairs = []
    vertical_pairs = []

    for n in range(1, min(_fit_count(area_l, box_l), max_param) + 1):
        for q in range(1, min(_fit_count(area_l, box_w), max_param) + 1):
            horizontal_l = n * box_l
            vertical_l = q * box_w
            contour_l = horizontal_l + vertical_l
            if contour_l <= area_l + 1e-9:
                horizontal_pairs.append((n, q, horizontal_l, vertical_l, contour_l))

    for m in range(1, min(_fit_count(area_w, box_w), max_param) + 1):
        for p in range(1, min(_fit_count(area_w, box_l), max_param) + 1):
            horizontal_w = m * box_w
            vertical_w = p * box_l
            contour_w = horizontal_w + vertical_w
            if contour_w <= area_w + 1e-9:
                vertical_pairs.append((m, p, horizontal_w, vertical_w, contour_w))

    parameter_candidates = []
    for n, q, horizontal_l, vertical_l, contour_l in horizontal_pairs:
        for m, p, horizontal_w, vertical_w, contour_w in vertical_pairs:
            if horizontal_l + 1e-9 < vertical_l:
                continue
            if vertical_w + 1e-9 < horizontal_w:
                continue

            hole_l = horizontal_l - vertical_l
            hole_w = vertical_w - horizontal_w
            if hole_l + 1e-9 < inner_span or hole_w + 1e-9 < inner_span:
                continue

            # Keep the inner pinwheel visually connected to the outer topology.
            # Large unused central regions are better handled by generic packing.
            if hole_l > 2.0 * inner_span + 1e-9:
                continue
            if hole_w > 2.0 * inner_span + 1e-9:
                continue

            outer_count = 2 * (m * n + p * q)
            total_count = outer_count + 4
            pallet_util = (total_count * box_area) / (area_l * area_w)
            bbox_util = (total_count * box_area) / (contour_l * contour_w)
            residual_area = (hole_l * hole_w) - (inner_span * inner_span)

            parameter_candidates.append(
                (
                    total_count,
                    pallet_util,
                    bbox_util,
                    -residual_area,
                    m,
                    n,
                    p,
                    q,
                    horizontal_l,
                    horizontal_w,
                    vertical_l,
                    vertical_w,
                    hole_l,
                    hole_w,
                )
            )

    parameter_candidates.sort(reverse=True)

    for (
        _total_count,
        _pallet_util,
        _bbox_util,
        _negative_residual,
        m,
        n,
        p,
        q,
        horizontal_l,
        horizontal_w,
        vertical_l,
        vertical_w,
        hole_l,
        hole_w,
    ) in parameter_candidates[:max_generated_candidates]:
        outer, contour_l, contour_w = block_pinwheel_motif(
            0.0,
            0.0,
            box_l,
            box_w,
            base_l,
            base_w,
            m=m,
            n=n,
            p=p,
            q=q,
        )

        hole_x = vertical_l
        hole_y = horizontal_w
        inner_x = hole_x + (hole_l - inner_span) / 2.0
        inner_y = hole_y + (hole_w - inner_span) / 2.0
        inner, _, _ = pinwheel_motif(
            inner_x,
            inner_y,
            box_l,
            box_w,
            base_l,
            base_w,
        )

        nested = outer + inner
        if placements_are_valid(nested, area_l, area_w):
            candidates.append(nested)

    return candidates

@_policy_scoped
def pattern_nested_pinwheel(area_l, area_w, box_l, box_w, rotated=False):
    """Return the strongest same-product nested pinwheel candidate."""
    base_l, base_w = box_l, box_w
    if rotated:
        box_l, box_w = box_w, box_l

    raw_candidates: List[Tuple[List[Placement2D], int]] = []
    for candidate in _enumerate_nested_pinwheel_candidates(
        area_l, area_w, box_l, box_w, base_l, base_w
    ):
        raw_candidates.append((candidate, 1))

    candidates = _dedupe_valid_candidates(raw_candidates, area_l, area_w)
    if not candidates:
        return []

    best, _ = max(
        candidates,
        key=lambda item: _pinwheel_candidate_score(
            item[0], area_l, area_w, item[1]
        ),
    )
    return best

def _enumerate_block_pinwheel_candidates(area_l, area_w, box_l, box_w, base_l, base_w):
    candidates: List[List[Placement2D]] = []
    box_area = box_l * box_w

    if min(area_l, area_w, box_l, box_w) <= 0:
        return candidates

    # Practical cap: prevents a very small SKU from making the request too slow,
    # while still covering normal packaging/pallet combinations generously.
    max_param = _policy().max_pinwheel_parameter
    max_generated_candidates = _policy().max_pinwheel_candidates
    horizontal_pairs = []
    vertical_pairs = []

    for n in range(1, min(_fit_count(area_l, box_l), max_param) + 1):
        for q in range(1, min(_fit_count(area_l, box_w), max_param) + 1):
            horizontal_l = n * box_l
            vertical_l = q * box_w
            contour_l = horizontal_l + vertical_l
            if contour_l <= area_l + 1e-9:
                horizontal_pairs.append((n, q, horizontal_l, vertical_l, contour_l))

    for m in range(1, min(_fit_count(area_w, box_w), max_param) + 1):
        for p in range(1, min(_fit_count(area_w, box_l), max_param) + 1):
            horizontal_w = m * box_w
            vertical_w = p * box_l
            contour_w = horizontal_w + vertical_w
            if contour_w <= area_w + 1e-9:
                vertical_pairs.append((m, p, horizontal_w, vertical_w, contour_w))

    parameter_candidates = []
    for n, q, horizontal_l, vertical_l, contour_l in horizontal_pairs:
        for m, p, horizontal_w, vertical_w, contour_w in vertical_pairs:
            # This implementation generates the common P1 block-pinwheel style:
            # the lower horizontal leaf reaches further than the left vertical
            # leaf, and the right vertical leaf reaches above the lower
            # horizontal leaf. Those two inequalities create the central hole
            # and avoid leaf overlap without expensive pairwise checks.
            if horizontal_l + 1e-9 < vertical_l or vertical_w + 1e-9 < horizontal_w:
                continue

            hole_l = horizontal_l - vertical_l
            hole_w = vertical_w - horizontal_w
            hole_area = hole_l * hole_w

            # A very large inner hole is not a useful/stable pinwheel.
            # The common practical rule is that the central hole should be
            # smaller than one case footprint.
            if hole_area > box_area + 1e-9:
                continue

            count = 2 * (m * n + p * q)
            pallet_util = (count * box_area) / (area_l * area_w) if area_l and area_w else 0.0
            bbox_util = (count * box_area) / (contour_l * contour_w) if contour_l and contour_w else 0.0
            parameter_candidates.append((count, pallet_util, bbox_util, m, n, p, q))

    parameter_candidates.sort(reverse=True)

    for _, _, _, m, n, p, q in parameter_candidates[:max_generated_candidates]:
        placements, _, _ = block_pinwheel_motif(
            0, 0, box_l, box_w, base_l, base_w, m=m, n=n, p=p, q=q
        )
        if placements_are_valid(placements, area_l, area_w):
            candidates.append(placements)

    return candidates

@_policy_scoped
def pattern_pinwheel(area_l, area_w, box_l, box_w, rotated=False):
    base_l, base_w = box_l, box_w
    if rotated:
        box_l, box_w = box_w, box_l

    raw_candidates: List[Tuple[List[Placement2D], int]] = []

    # Rank 2: true block pinwheels. Prefer these over tiled simple motifs when
    # the quantity is equal, because they create one regular pinwheel layer.
    for candidate in _enumerate_block_pinwheel_candidates(area_l, area_w, box_l, box_w, base_l, base_w):
        raw_candidates.append((candidate, 2))

    # Rank 1: repeated simple pinwheels. Useful when no larger block pinwheel
    # fits or when repeated motifs genuinely load more boxes.
    raw_candidates.append((_pattern_tiled_simple_pinwheel(area_l, area_w, box_l, box_w, base_l, base_w), 1))

    candidates = _dedupe_valid_candidates(raw_candidates, area_l, area_w)
    if not candidates:
        return []

    best, _ = max(
        candidates,
        key=lambda item: _pinwheel_candidate_score(item[0], area_l, area_w, item[1]),
    )
    return best

def _splitrow_arithmetic_choice(
    area_l,
    area_w,
    a_l,
    a_w,
    b_l,
    b_w,
    axis,
):
    """Choose a two-band split without materializing every candidate."""
    if axis == "rows":
        max_a_units = _fit_count(area_w, a_w)
        a_across = _fit_count(area_l, a_l)
        b_across = _fit_count(area_l, b_l)
        for_a = lambda units: (
            units * a_w,
            _fit_count(area_w - units * a_w, b_w),
        )
    else:
        max_a_units = _fit_count(area_l, a_l)
        a_across = _fit_count(area_w, a_w)
        b_across = _fit_count(area_w, b_w)
        for_a = lambda units: (
            units * a_l,
            _fit_count(area_l - units * a_l, b_l),
        )

    best = None
    best_score = None
    for a_units in range(max_a_units + 1):
        band_a, b_units = for_a(a_units)
        a_count = a_units * a_across
        b_count = b_units * b_across
        total = a_count + b_count
        mixed = a_count > 0 and b_count > 0
        # Prefer a genuine mixed split when it ties an all-one-orientation
        # grid. This is what makes the reference 6x3 + 1x6 topology visible
        # instead of silently falling back to a rotated Block layer.
        score = (
            total,
            int(mixed),
            -b_units if mixed else 0,
            min(a_count, b_count) if mixed else 0,
        )
        if best_score is None or score > best_score:
            best_score = score
            best = {
                "axis": axis,
                "a_units": a_units,
                "b_units": b_units,
                "a_count": a_count,
                "b_count": b_count,
                "band_a": band_a,
            }
    return best

def _materialize_splitrow_choice(choice, area_l, area_w, a_l, a_w, b_l, b_w, box_l, box_w):
    if not choice or (not choice["a_count"] and not choice["b_count"]):
        return []

    placements: List[Placement2D] = []
    if choice["axis"] == "rows":
        band_a_w = choice["band_a"]
        band_b_w = area_w - band_a_w
        if band_a_w > 0:
            placements.extend(
                grid_fill(area_l, band_a_w, a_l, a_w, box_l, box_w, x0=0, y0=0)
            )
        if band_b_w > 0:
            placements.extend(
                grid_fill(area_l, band_b_w, b_l, b_w, box_l, box_w, x0=0, y0=band_a_w)
            )
    else:
        band_a_l = choice["band_a"]
        band_b_l = area_l - band_a_l
        if band_a_l > 0:
            placements.extend(
                grid_fill(band_a_l, area_w, a_l, a_w, box_l, box_w, x0=0, y0=0)
            )
        if band_b_l > 0:
            placements.extend(
                grid_fill(band_b_l, area_w, b_l, b_w, box_l, box_w, x0=band_a_l, y0=0)
            )
    return placements

@_policy_scoped
def pattern_splitrow(area_l, area_w, box_l, box_w, swapped=False):
    """Build the best deterministic mixed row/column split.

    Split Row is allowed to divide the footprint along either pallet axis. The
    reference layout for 308 x 147 mm cartons is a side-by-side split, so a
    row-only search cannot represent it. Arithmetic scoring still evaluates
    only integer band counts; geometry is materialized for the winning choice
    and the unchanged Block fallback.
    """
    orientation_pairs = [
        (box_w, box_l, box_l, box_w),
        (box_l, box_w, box_w, box_l),
    ]
    if swapped:
        orientation_pairs.reverse()

    best_choice = None
    best_params = None
    best_score = None
    for a_l, a_w, b_l, b_w in orientation_pairs:
        for axis in ("rows", "columns"):
            choice = _splitrow_arithmetic_choice(
                area_l, area_w, a_l, a_w, b_l, b_w, axis
            )
            if not choice:
                continue
            score = (
                choice["a_count"] + choice["b_count"],
                int(choice["a_count"] > 0 and choice["b_count"] > 0),
                -choice["b_units"]
                if choice["a_count"] > 0 and choice["b_count"] > 0
                else 0,
                min(choice["a_count"], choice["b_count"])
                if choice["a_count"] > 0 and choice["b_count"] > 0
                else 0,
            )
            if best_score is None or score > best_score:
                best_score = score
                best_choice = choice
                best_params = (a_l, a_w, b_l, b_w)

    best = _materialize_splitrow_choice(
        best_choice,
        area_l,
        area_w,
        *(best_params or (box_l, box_w, box_w, box_l)),
        box_l,
        box_w,
    )
    plain = pattern_block(area_l, area_w, box_l, box_w)
    return best if len(best) >= len(plain) else plain

def _balance_margin_fill_lines(
    fillers: List[Placement2D],
    strip_x: float,
    strip_y: float,
    strip_l: float,
    strip_w: float,
    axis: str,
) -> List[Placement2D]:
    """Balance only sparse Hybrid-pinwheel margin fillers.

    Cartons in each uniform filler line are split across opposite strip ends.
    The pinwheel core, filler quantity, orientation, and cross-axis position are
    preserved. Full lines are left unchanged.
    """
    if len(fillers) < 2 or axis not in {"x", "y"}:
        return fillers

    groups: Dict[Tuple, List[Placement2D]] = {}
    for p in fillers:
        key = (
            round(p.y if axis == "x" else p.x, 6),
            round(p.l, 6),
            round(p.w, 6),
            p.orientation,
        )
        groups.setdefault(key, []).append(p)

    balanced: List[Placement2D] = []
    changed = False

    for group in groups.values():
        ordered = sorted(group, key=lambda p: p.x if axis == "x" else p.y)
        count = len(ordered)
        if count < 2:
            balanced.extend(ordered)
            continue

        unit = ordered[0].l if axis == "x" else ordered[0].w
        span = strip_l if axis == "x" else strip_w
        origin = strip_x if axis == "x" else strip_y

        if count * unit >= span - 1e-9:
            balanced.extend(ordered)
            continue

        side_count = count // 2
        positions = [origin + i * unit for i in range(side_count)]
        if count % 2:
            positions.append(origin + (span - unit) / 2.0)
        far_start = origin + span - side_count * unit
        positions.extend(far_start + i * unit for i in range(side_count))
        positions.sort()

        candidate_group = [
            Placement2D(
                x=position if axis == "x" else source.x,
                y=source.y if axis == "x" else position,
                l=source.l,
                w=source.w,
                orientation=source.orientation,
            )
            for source, position in zip(ordered, positions)
        ]

        inside_strip = all(
            p.x >= strip_x - 1e-9
            and p.x + p.l <= strip_x + strip_l + 1e-9
            and p.y >= strip_y - 1e-9
            and p.y + p.w <= strip_y + strip_w + 1e-9
            for p in candidate_group
        )
        non_overlapping = all(
            rect_overlap_area(a, b) <= 1e-9
            for i, a in enumerate(candidate_group)
            for b in candidate_group[i + 1:]
        )

        if inside_strip and non_overlapping:
            balanced.extend(candidate_group)
            changed = changed or layout_signature(candidate_group) != layout_signature(ordered)
        else:
            balanced.extend(ordered)

    return balanced if changed else fillers

def _add_rectangular_margin_fill(
    base: List[Placement2D],
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
    base_l: float,
    base_w: float,
    balance_fillers: bool = True,
) -> List[Placement2D]:
    if not base:
        return []

    _, _, used_l, used_w = placements_bbox(base)
    placements = list(base)

    if area_l - used_l > 1e-9:
        right_strip = pattern_brick(area_l - used_l, area_w, box_l, box_w, rotated=False)
        right_strip = [
            Placement2D(x=p.x + used_l, y=p.y, l=p.l, w=p.w, orientation=p.orientation)
            for p in right_strip
        ]
        if balance_fillers:
            right_strip = _balance_margin_fill_lines(
                right_strip,
                strip_x=used_l,
                strip_y=0.0,
                strip_l=area_l - used_l,
                strip_w=area_w,
                axis="y",
            )
        placements.extend(right_strip)

    if area_w - used_w > 1e-9 and used_l > 1e-9:
        top_strip = try_two_orientations_grid(
            used_l, area_w - used_w, box_l, box_w, base_l, base_w, x0=0, y0=used_w
        )
        if balance_fillers:
            top_strip = _balance_margin_fill_lines(
                top_strip,
                strip_x=0.0,
                strip_y=used_w,
                strip_l=used_l,
                strip_w=area_w - used_w,
                axis="x",
            )
        placements.extend(top_strip)

    return placements if placements_are_valid(placements, area_l, area_w) else base

@_policy_scoped
def pattern_hybrid_pinwheel(area_l, area_w, box_l, box_w, rotated=False):
    base_l, base_w = box_l, box_w
    if rotated:
        box_l, box_w = box_w, box_l

    raw_candidates: List[Tuple[List[Placement2D], int]] = []

    # Start from the improved true pinwheel family. The hybrid variant may add
    # rectangular margin fills, but should not replace the pinwheel core with a
    # plain block layout.
    for candidate in _enumerate_block_pinwheel_candidates(area_l, area_w, box_l, box_w, base_l, base_w):
        raw_candidates.append((candidate, 2))
        raw_candidates.append((
            _add_rectangular_margin_fill(
                candidate, area_l, area_w, box_l, box_w, base_l, base_w,
                balance_fillers=not rotated,
            ),
            1,
        ))

    simple = _pattern_tiled_simple_pinwheel(area_l, area_w, box_l, box_w, base_l, base_w)
    raw_candidates.append((simple, 1))
    raw_candidates.append((
        _add_rectangular_margin_fill(
            simple, area_l, area_w, box_l, box_w, base_l, base_w,
            balance_fillers=not rotated,
        ),
        0,
    ))

    candidates = _dedupe_valid_candidates(raw_candidates, area_l, area_w)
    if not candidates:
        return []

    best, _ = max(
        candidates,
        key=lambda item: _pinwheel_candidate_score(item[0], area_l, area_w, item[1]),
    )
    return best


