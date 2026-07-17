from __future__ import annotations

import os
import math
import uuid
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Placement2D:
    x: float
    y: float
    l: float
    w: float
    orientation: str  # "LxW" or "WxL"


@dataclass
class Placement3D:
    x: float
    y: float
    z: float
    l: float
    w: float
    h: float
    orientation: str
    layer_kind: str   # "base" or "interlock"
    layer_index: int


@dataclass(frozen=True)
class PalletizationRenderResult:
    image_rel_path: str


PALLET_DECK_THICKNESS_MM = 18.0
PALLET_RUNNER_HEIGHT_MM = 90.0
PALLET_RENDER_HEIGHT_MM = PALLET_DECK_THICKNESS_MM + PALLET_RUNNER_HEIGHT_MM


# ============================================================
# BASIC HELPERS
# ============================================================

def box_volume(l: float, w: float, h: float) -> float:
    return l * w * h


def orientation_name(l: float, w: float, base_l: float, base_w: float) -> str:
    if abs(l - base_l) < 1e-9 and abs(w - base_w) < 1e-9:
        return "LxW"
    return "WxL"


def effective_pallet_size(
    pallet_l: float,
    pallet_w: float,
    stick_l: float,
    stick_w: float,
) -> Tuple[float, float]:
    return pallet_l + stick_l, pallet_w + stick_w


def rect_overlap_area(a: Placement2D, b: Placement2D) -> float:
    x_overlap = max(0, min(a.x + a.l, b.x + b.l) - max(a.x, b.x))
    y_overlap = max(0, min(a.y + a.w, b.y + b.w) - max(a.y, b.y))
    return x_overlap * y_overlap


def within_area(p: Placement2D, area_l: float, area_w: float) -> bool:
    return (
        p.x >= 0 and p.y >= 0 and
        p.x + p.l <= area_l + 1e-9 and
        p.y + p.w <= area_w + 1e-9
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
    placements: List[Placement2D] = []
    nx = int(area_l // box_l)
    ny = int(area_w // box_w)
    ori = orientation_name(box_l, box_w, base_l, base_w)

    for j in range(ny):
        for i in range(nx):
            placements.append(
                Placement2D(
                    x=x0 + i * box_l,
                    y=y0 + j * box_w,
                    l=box_l,
                    w=box_w,
                    orientation=ori,
                )
            )
    return placements


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


# ============================================================
# PATTERN GENERATORS - SINGLE LAYER
# ============================================================

def pattern_block(area_l, area_w, box_l, box_w):
    p1 = grid_fill(area_l, area_w, box_l, box_w, box_l, box_w)
    p2 = grid_fill(area_l, area_w, box_w, box_l, box_l, box_w)
    return p1 if len(p1) >= len(p2) else p2


def pattern_row(area_l, area_w, box_l, box_w):
    p1 = grid_fill(area_l, area_w, box_l, box_w, box_l, box_w)
    p2 = grid_fill(area_l, area_w, box_w, box_l, box_l, box_w)

    rows1 = int(area_w // box_w)
    rows2 = int(area_w // box_l)

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

    cols = int(area_l // short_side)
    rows = int(area_w // short_side)
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

    modules_x = int(area_l // long_side)
    modules_y = int(area_w // long_side)
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

    rows = int(area_w // work_w)
    full_cols = int(area_l // work_l)

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


def pattern_brick_best(area_l, area_w, box_l, box_w):
    """Return the best customer-facing brick layout.

    Candidate families are evaluated in this order of engineering preference:

    * basket-weave / bonded brick modules for clean integer-ratio cartons;
    * conservative running-bond rows as a fallback.

    Quantity remains the primary decision criterion, but when two candidates fit
    the same number of cartons the orthogonal bonded-brick candidate wins over a
    simple row-offset candidate because it better matches the pattern normally
    shown in pallet-pattern charts for rectangular cartons.
    """
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


def placements_bbox(placements: List[Placement2D]) -> Tuple[float, float, float, float]:
    if not placements:
        return 0.0, 0.0, 0.0, 0.0
    min_x = min(p.x for p in placements)
    min_y = min(p.y for p in placements)
    max_x = max(p.x + p.l for p in placements)
    max_y = max(p.y + p.w for p in placements)
    return min_x, min_y, max_x, max_y


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



def _dimension_step(values: List[float]) -> float:
    """Return a practical grid step for candidate balancing positions."""
    ints = [int(round(v)) for v in values if v and v > 0 and abs(v - round(v)) < 1e-6]
    if not ints:
        return max(1.0, min([v for v in values if v and v > 0] or [1.0]))
    step = ints[0]
    for value in ints[1:]:
        step = math.gcd(step, value)
    # Avoid excessive loops on very small tolerances/dimensions.
    return float(max(step, 10))


def _generate_position_values(limit: float, size: float, step: float, anchors: List[float]) -> List[float]:
    values = {0.0, max(0.0, limit - size)}
    for anchor in anchors:
        for value in (anchor, anchor - size):
            if -1e-6 <= value <= limit - size + 1e-6:
                values.add(0.0 if abs(value) < 1e-6 else round(float(value), 6))

    if step > 0 and limit / step <= 250:
        count = int((limit - size) // step)
        for idx in range(count + 1):
            value = idx * step
            if -1e-6 <= value <= limit - size + 1e-6:
                values.add(round(float(value), 6))

    return sorted(values)


def _candidate_positions_for_filler(
    fixed: List[Placement2D],
    filler_l: float,
    filler_w: float,
    area_l: float,
    area_w: float,
) -> List[Placement2D]:
    anchors_x: List[float] = []
    anchors_y: List[float] = []
    for p in fixed:
        anchors_x.extend([p.x, p.x + p.l])
        anchors_y.extend([p.y, p.y + p.w])

    step = _dimension_step([filler_l, filler_w, area_l, area_w])
    x_values = _generate_position_values(area_l, filler_l, step, anchors_x)
    y_values = _generate_position_values(area_w, filler_w, step, anchors_y)

    candidates: List[Placement2D] = []
    for y in y_values:
        for x in x_values:
            candidate = Placement2D(
                x=x,
                y=y,
                l=filler_l,
                w=filler_w,
                orientation=orientation_name(filler_l, filler_w, filler_l, filler_w),
            )
            if placements_are_valid(fixed + [candidate], area_l, area_w):
                candidates.append(candidate)
    return candidates


def _select_balanced_edge_positions(
    fixed: List[Placement2D],
    filler_template: Placement2D,
    filler_count: int,
    area_l: float,
    area_w: float,
    axis: str,
) -> List[Placement2D]:
    """Place filler boxes split across opposite edges when feasible."""
    positions = _candidate_positions_for_filler(
        fixed=fixed,
        filler_l=filler_template.l,
        filler_w=filler_template.w,
        area_l=area_l,
        area_w=area_w,
    )
    if len(positions) < filler_count:
        return []

    low_target = filler_count // 2
    high_target = filler_count - low_target

    if low_target == 0 or high_target == 0:
        return []

    def axis_coord(p: Placement2D) -> float:
        return p.x if axis == "x" else p.y

    def opposite_coord(p: Placement2D) -> float:
        return p.y if axis == "x" else p.x

    low_candidates = sorted(
        positions,
        key=lambda p: (axis_coord(p), abs(opposite_coord(p) - (area_w if axis == "x" else area_l) / 2), opposite_coord(p)),
    )
    high_candidates = sorted(
        positions,
        key=lambda p: (-axis_coord(p), abs(opposite_coord(p) - (area_w if axis == "x" else area_l) / 2), opposite_coord(p)),
    )

    selected: List[Placement2D] = []

    def add_from(candidates: List[Placement2D], target: int) -> bool:
        for candidate in candidates:
            if len(selected) >= target:
                return True
            # Avoid selecting the exact same slot from both edge lists.
            if any(abs(candidate.x - s.x) < 1e-6 and abs(candidate.y - s.y) < 1e-6 for s in selected):
                continue
            if placements_are_valid(fixed + selected + [candidate], area_l, area_w):
                selected.append(candidate)
        return len(selected) >= target

    if not add_from(low_candidates, low_target):
        return []

    # Now fill from the opposite edge until total count is reached.
    for candidate in high_candidates:
        if len(selected) >= filler_count:
            break
        if any(abs(candidate.x - s.x) < 1e-6 and abs(candidate.y - s.y) < 1e-6 for s in selected):
            continue
        if placements_are_valid(fixed + selected + [candidate], area_l, area_w):
            selected.append(candidate)

    if len(selected) != filler_count:
        return []

    # Verify that both edges are truly represented.
    coords = [axis_coord(p) for p in selected]
    if max(coords) - min(coords) < (filler_template.l if axis == "x" else filler_template.w) - 1e-6:
        return []

    return selected if placements_are_valid(fixed + selected, area_l, area_w) else []


def _orientation_counts(placements: List[Placement2D]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for p in placements:
        counts[p.orientation] = counts.get(p.orientation, 0) + 1
    return counts


def _filler_edge_balance_score(
    placements: List[Placement2D],
    area_l: float,
    area_w: float,
) -> Tuple[float, float]:
    """Higher is better. Measures whether minority-orientation boxes are edge-balanced."""
    if not placements:
        return (0.0, 0.0)

    counts = _orientation_counts(placements)
    if len(counts) < 2:
        return (0.0, 0.0)

    filler_orientation = min(counts, key=lambda key: counts[key])
    filler = [p for p in placements if p.orientation == filler_orientation]
    if len(filler) < 2:
        return (0.0, 0.0)

    centers_x = [p.x + p.l / 2 for p in filler]
    centers_y = [p.y + p.w / 2 for p in filler]

    def axis_score(centers: List[float], limit: float) -> float:
        low = sum(1 for c in centers if c <= limit / 2)
        high = len(centers) - low
        split_score = min(low, high) / max(len(centers), 1)
        mean_center = sum(centers) / len(centers)
        centering_score = 1.0 - min(1.0, abs(mean_center - limit / 2) / max(limit / 2, 1.0))
        spread_score = (max(centers) - min(centers)) / max(limit, 1.0)
        return split_score * 10.0 + centering_score * 2.0 + spread_score

    return (max(axis_score(centers_x, area_l), axis_score(centers_y, area_w)), -abs(len(filler) - (len(placements) - len(filler))))


def prefer_edge_balanced_filler_layer(
    placements: List[Placement2D],
    area_l: float,
    area_w: float,
) -> List[Placement2D]:
    """Prefer a symmetric split-filler layout when it preserves quantity.

    If a mixed layer has a smaller filler group in one orientation, try to split
    that filler group across opposite pallet edges. This generalizes the desired
    behavior:

        2 filler units -> 1 + 1
        4 filler units -> 2 + 2
        6 filler units -> 3 + 3

    The transformation is accepted only when it keeps the same number of boxes,
    stays inside the pallet area, and does not overlap the main block.
    """
    if not placements or len(placements) < 3:
        return placements

    counts = _orientation_counts(placements)
    if len(counts) != 2:
        return placements

    ordered_groups = sorted(counts.items(), key=lambda item: item[1])
    filler_orientation, filler_count = ordered_groups[0]
    main_orientation, main_count = ordered_groups[1]

    if filler_count < 2 or filler_count >= main_count:
        return placements

    filler = [p for p in placements if p.orientation == filler_orientation]
    fixed = [p for p in placements if p.orientation != filler_orientation]

    # Only handle uniform filler units. This keeps the rule predictable.
    dims = {(round(p.l, 6), round(p.w, 6)) for p in filler}
    if len(dims) != 1:
        return placements

    template = filler[0]
    candidates: List[List[Placement2D]] = [placements]

    for axis in ("x", "y"):
        split_positions = _select_balanced_edge_positions(
            fixed=fixed,
            filler_template=template,
            filler_count=filler_count,
            area_l=area_l,
            area_w=area_w,
            axis=axis,
        )
        if split_positions:
            candidate = fixed + [
                Placement2D(
                    x=p.x,
                    y=p.y,
                    l=p.l,
                    w=p.w,
                    orientation=filler_orientation,
                )
                for p in split_positions
            ]
            if len(candidate) == len(placements) and placements_are_valid(candidate, area_l, area_w):
                candidates.append(candidate)

    best = max(candidates, key=lambda layer: _filler_edge_balance_score(layer, area_l, area_w))
    original_score = _filler_edge_balance_score(placements, area_l, area_w)
    best_score = _filler_edge_balance_score(best, area_l, area_w)

    # Require a meaningful improvement so we do not move boxes unnecessarily.
    if best is not placements and best_score > original_score:
        return best
    return placements



def _line_group_key(p: Placement2D, direction: str) -> Tuple:
    """Group boxes that form the same horizontal or vertical filler line."""
    if direction == "horizontal":
        return (
            "horizontal",
            p.orientation,
            round(p.l, 6),
            round(p.w, 6),
            round(p.y, 6),
            round(p.w, 6),
        )
    return (
        "vertical",
        p.orientation,
        round(p.l, 6),
        round(p.w, 6),
        round(p.x, 6),
        round(p.l, 6),
    )


def _group_line_indices(placements: List[Placement2D], direction: str) -> Dict[Tuple, List[int]]:
    groups: Dict[Tuple, List[int]] = {}
    for idx, p in enumerate(placements):
        key = _line_group_key(p, direction)
        groups.setdefault(key, []).append(idx)
    return groups


def _sparse_line_score_for_group(
    group: List[Placement2D],
    area_l: float,
    area_w: float,
    direction: str,
) -> float:
    if len(group) < 2:
        return 0.0

    if direction == "horizontal":
        centers = [p.x + p.l / 2 for p in group]
        limit = area_l
        unit = group[0].l
        total_span = len(group) * unit
    else:
        centers = [p.y + p.w / 2 for p in group]
        limit = area_w
        unit = group[0].w
        total_span = len(group) * unit

    # Only score sparse lines. Full lines do not need edge splitting.
    if total_span >= limit - 1e-6:
        return 0.0

    low = sum(1 for c in centers if c <= limit / 2)
    high = len(centers) - low
    split_score = min(low, high) / max(len(centers), 1)
    spread_score = (max(centers) - min(centers)) / max(limit, 1.0)
    mean_center = sum(centers) / len(centers)
    center_score = 1.0 - min(1.0, abs(mean_center - limit / 2) / max(limit / 2, 1.0))

    return split_score * 10.0 + spread_score * 3.0 + center_score


def _sparse_line_balance_score(
    placements: List[Placement2D],
    area_l: float,
    area_w: float,
) -> float:
    """Score local sparse filler lines, not only minority-orientation fillers."""
    if len(_orientation_counts(placements)) < 2:
        return 0.0

    total = 0.0
    for direction in ("horizontal", "vertical"):
        for indices in _group_line_indices(placements, direction).values():
            group = [placements[i] for i in indices]
            total += _sparse_line_score_for_group(group, area_l, area_w, direction)
    return total


def _make_edge_split_line_candidate(
    placements: List[Placement2D],
    indices: List[int],
    area_l: float,
    area_w: float,
    direction: str,
) -> List[Placement2D]:
    """Return a candidate where one sparse line starts from opposite edges."""
    if len(indices) < 2:
        return []

    group = [placements[i] for i in indices]
    template = group[0]

    # Uniform line only. This avoids changing intentional complex bonded areas.
    if any(
        abs(p.l - template.l) > 1e-6
        or abs(p.w - template.w) > 1e-6
        or p.orientation != template.orientation
        for p in group
    ):
        return []

    low_count = len(group) // 2
    high_count = len(group) - low_count
    if low_count <= 0 or high_count <= 0:
        return []

    fixed = [p for i, p in enumerate(placements) if i not in set(indices)]
    new_group: List[Placement2D] = []

    if direction == "horizontal":
        y = template.y
        if len(group) * template.l >= area_l - 1e-6:
            return []
        for i in range(low_count):
            new_group.append(
                Placement2D(
                    x=i * template.l,
                    y=y,
                    l=template.l,
                    w=template.w,
                    orientation=template.orientation,
                )
            )
        start_high = area_l - high_count * template.l
        for i in range(high_count):
            new_group.append(
                Placement2D(
                    x=start_high + i * template.l,
                    y=y,
                    l=template.l,
                    w=template.w,
                    orientation=template.orientation,
                )
            )
    else:
        x = template.x
        if len(group) * template.w >= area_w - 1e-6:
            return []
        for i in range(low_count):
            new_group.append(
                Placement2D(
                    x=x,
                    y=i * template.w,
                    l=template.l,
                    w=template.w,
                    orientation=template.orientation,
                )
            )
        start_high = area_w - high_count * template.w
        for i in range(high_count):
            new_group.append(
                Placement2D(
                    x=x,
                    y=start_high + i * template.w,
                    l=template.l,
                    w=template.w,
                    orientation=template.orientation,
                )
            )

    candidate = fixed + new_group
    if len(candidate) != len(placements):
        return []
    if not placements_are_valid(candidate, area_l, area_w):
        return []

    return candidate


def prefer_edge_balanced_sparse_filler_lines(
    placements: List[Placement2D],
    area_l: float,
    area_w: float,
) -> List[Placement2D]:
    """Balance local horizontal filler rows inside mixed composite layers.

    This catches the specific class of issue where a sparse filler row is
    compacted on one side, even though the same cartons could start from
    opposite pallet edges. It intentionally does not move vertical internal
    columns, because that can create a visually different pattern instead of
    merely improving filler symmetry.

    Example:

        1×2 filler row -> one box from the left edge and one from the right edge
        1×4 filler row -> two boxes from the left edge and two from the right edge

    Quantity, orientation, row position, and collision validity are preserved.
    """
    if not placements or len(_orientation_counts(placements)) < 2:
        return placements

    current = placements
    improved = True
    passes = 0

    while improved and passes < 3:
        improved = False
        passes += 1

        groups = _group_line_indices(current, "horizontal")
        for indices in groups.values():
            if len(indices) < 2:
                continue

            original_group = [current[i] for i in indices]
            candidate = _make_edge_split_line_candidate(current, indices, area_l, area_w, "horizontal")
            if not candidate:
                continue

            # _make_edge_split_line_candidate appends the redistributed line at
            # the end of the candidate list.
            candidate_group = candidate[-len(indices):]

            original_score = _sparse_line_score_for_group(original_group, area_l, area_w, "horizontal")
            candidate_score = _sparse_line_score_for_group(candidate_group, area_l, area_w, "horizontal")

            if candidate_score > original_score + 1e-6:
                current = candidate
                improved = True
                break

    return current


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
    # O(n²) overlap check. Once the next rectangle starts after the current
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
    return tuple(
        sorted(
            (round(p.x, 6), round(p.y, 6), round(p.l, 6), round(p.w, 6), p.orientation)
            for p in placements
        )
    )

def layer_geometry_signature(placements: List[Placement2D]) -> Tuple[Tuple[float, float, float, float], ...]:
    """Canonical layer signature used for interlock compatibility checks.

    Orientation labels are intentionally ignored because geometry is enough to
    confirm whether two pallet layers are the same, mirrored, or rotated 180°.
    The actual length/width of every case is still part of the signature, so a
    90°-rotated but otherwise unrelated layer is not accepted.
    """
    return tuple(
        sorted(
            (round(p.x, 6), round(p.y, 6), round(p.l, 6), round(p.w, 6))
            for p in placements
        )
    )


def layer_bounds_signature(
    placements: List[Placement2D],
) -> Tuple[float, float, float, float]:
    """Rounded footprint bounds for checking aligned A/B layers."""
    min_x, min_y, max_x, max_y = placements_bbox(placements)
    return (round(min_x, 6), round(min_y, 6), round(max_x, 6), round(max_y, 6))


def layer_bounds_match(
    base_layer: List[Placement2D],
    candidate_layer: List[Placement2D],
) -> bool:
    """Return True when layer B keeps the same outer footprint as layer A.

    Customer-facing interlock should not jump to the opposite side of the
    pallet when a layer does not use the full pallet contour. Mirroring inside
    the base footprint keeps both layer outlines aligned while still reversing
    the internal box joints.
    """
    return layer_bounds_signature(base_layer) == layer_bounds_signature(candidate_layer)


def _rounded_unique_edges(values: List[float], tolerance: float = 1e-6) -> List[float]:
    rounded = sorted(round(value, 6) for value in values)
    unique: List[float] = []
    for value in rounded:
        if not unique or abs(value - unique[-1]) > tolerance:
            unique.append(value)
    return unique


def _cell_is_covered(
    x_mid: float,
    y_mid: float,
    placements: List[Placement2D],
    tolerance: float = 1e-6,
) -> bool:
    for p in placements:
        if (
            p.x - tolerance <= x_mid <= p.x + p.l + tolerance
            and p.y - tolerance <= y_mid <= p.y + p.w + tolerance
        ):
            return True
    return False


def layer_occupied_contour_match(
    base_layer: List[Placement2D],
    candidate_layer: List[Placement2D],
) -> bool:
    """Return True when two layers occupy the same outside silhouette.

    Bounding boxes alone are not enough for interlock. A mirrored L-shaped
    layer can keep the same outer min/max coordinates while moving an empty
    corner to another side. In the 3D result that looks like the alternating
    layers are misaligned. This comparison ignores internal box joints and
    checks the occupied footprint area itself, so visible interlock is kept
    only when the outside vertices/contour remain aligned.
    """
    if not base_layer or not candidate_layer:
        return False

    x_edges = _rounded_unique_edges(
        [edge for p in base_layer + candidate_layer for edge in (p.x, p.x + p.l)]
    )
    y_edges = _rounded_unique_edges(
        [edge for p in base_layer + candidate_layer for edge in (p.y, p.y + p.w)]
    )

    if len(x_edges) < 2 or len(y_edges) < 2:
        return False

    for x1, x2 in zip(x_edges, x_edges[1:]):
        if x2 - x1 <= 1e-6:
            continue
        x_mid = (x1 + x2) / 2.0
        for y1, y2 in zip(y_edges, y_edges[1:]):
            if y2 - y1 <= 1e-6:
                continue
            y_mid = (y1 + y2) / 2.0
            if _cell_is_covered(x_mid, y_mid, base_layer) != _cell_is_covered(x_mid, y_mid, candidate_layer):
                return False

    return True


def transform_layer(
    placements: List[Placement2D],
    area_l: float,
    area_w: float,
    transform_name: str,
    *,
    align_to_footprint: bool = True,
) -> List[Placement2D]:
    """Return a same/mirror/180° transformed copy of one pallet layer.

    By default, mirror/rotation is done inside the layer footprint, not across
    the complete pallet. This keeps alternating interlock layers vertically
    aligned in the render and in the load calculation, especially when the
    layer does not occupy the full pallet length/width.
    """
    if align_to_footprint and placements:
        min_x, min_y, max_x, max_y = placements_bbox(placements)
    else:
        min_x, min_y, max_x, max_y = 0.0, 0.0, area_l, area_w

    transformed: List[Placement2D] = []

    for p in placements:
        if transform_name == "same":
            x = p.x
            y = p.y
        elif transform_name == "mirror_length":
            x = min_x + max_x - p.x - p.l
            y = p.y
        elif transform_name == "mirror_width":
            x = p.x
            y = min_y + max_y - p.y - p.w
        elif transform_name == "rotate_180":
            x = min_x + max_x - p.x - p.l
            y = min_y + max_y - p.y - p.w
        else:
            raise ValueError(f"Unknown layer transform: {transform_name}")

        transformed.append(
            Placement2D(
                x=x,
                y=y,
                l=p.l,
                w=p.w,
                orientation=p.orientation,
            )
        )

    return transformed


INTERLOCK_TRANSFORM_LABELS = {
    "same": "same layer",
    "mirror_length": "mirror along pallet length",
    "mirror_width": "mirror along pallet width",
    "rotate_180": "180° rotation",
}


def interlock_relation(
    base_layer: List[Placement2D],
    candidate_layer: List[Placement2D],
    area_l: float,
    area_w: float,
) -> Optional[str]:
    """Return relation name when layer B is a clean compatible interlock.

    Customer-facing interlock should be conservative: layer B must contain the
    same number of boxes, keep the same outer footprint, and be exactly the
    same layer, a mirror, or a 180° rotation of layer A. Mixed/generated layers
    that do not satisfy this are treated as internal/invalid and are not used
    for visible results.
    """
    if not base_layer or not candidate_layer:
        return None
    if len(base_layer) != len(candidate_layer):
        return None
    if not placements_are_valid(candidate_layer, area_l, area_w):
        return None
    if not layer_bounds_match(base_layer, candidate_layer):
        return None
    if not layer_occupied_contour_match(base_layer, candidate_layer):
        return None

    candidate_signature = layer_geometry_signature(candidate_layer)
    for transform_name in ("same", "mirror_length", "mirror_width", "rotate_180"):
        transformed = transform_layer(
            base_layer,
            area_l,
            area_w,
            transform_name,
            align_to_footprint=True,
        )
        if layer_geometry_signature(transformed) == candidate_signature:
            return transform_name

    return None


def build_customer_safe_interlock_layer(
    base_layer: List[Placement2D],
    generated_interlock_layer: List[Placement2D],
    area_l: float,
    area_w: float,
) -> Tuple[List[Placement2D], Optional[str]]:
    """Build the visible interlock layer using only compatible layer relations.

    Older pattern-specific interlock generators could return unrelated rotated
    layouts with different counts or strange visual behaviour. This function
    first accepts a generated layer only if it is cleanly compatible; otherwise
    it derives a conservative mirror/180° layer from the base layer. That keeps
    the result easy to explain and prevents odd A/B layer combinations.
    """
    if not base_layer or not placements_are_valid(base_layer, area_l, area_w):
        return [], None

    base_signature = layer_geometry_signature(base_layer)
    candidates: List[Tuple[List[Placement2D], str, int]] = []

    generated_relation = interlock_relation(base_layer, generated_interlock_layer, area_l, area_w)
    if generated_relation and generated_relation != "same":
        # Prefer a valid generated mirror/rotation over a derived one, but do
        # not show duplicate interlock rows that are actually just column
        # stacking.
        candidates.append((generated_interlock_layer, generated_relation, 4))

    transform_priorities = (
        ("mirror_length", 3),
        ("mirror_width", 3),
        ("rotate_180", 2),
    )
    for transform_name, priority in transform_priorities:
        transformed = transform_layer(base_layer, area_l, area_w, transform_name)
        if not placements_are_valid(transformed, area_l, area_w):
            continue
        relation = interlock_relation(base_layer, transformed, area_l, area_w)
        if not relation or relation == "same":
            continue
        candidates.append((transformed, relation, priority))

    if not candidates:
        return [], None

    # De-duplicate by geometry and prefer non-identical mirrors. This avoids
    # showing interlock as a strange generated layer and avoids unnecessary
    # column duplicates when a clean mirror is available.
    unique: Dict[Tuple[Tuple[float, float, float, float], ...], Tuple[List[Placement2D], str, int, bool]] = {}
    for layer, relation, priority in candidates:
        signature = layer_geometry_signature(layer)
        is_different_from_base = signature != base_signature
        existing = unique.get(signature)
        record = (layer, relation, priority, is_different_from_base)
        if existing is None or (is_different_from_base, priority) > (existing[3], existing[2]):
            unique[signature] = record

    best_layer, best_relation, _, _ = max(
        unique.values(),
        key=lambda item: (item[3], item[2], len(item[0])),
    )
    return best_layer, best_relation


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

    nx = int(area_l // tile_l)
    ny = int(area_w // tile_w)

    for j in range(ny):
        for i in range(nx):
            x0 = i * tile_l
            y0 = j * tile_w
            motif, _, _ = pinwheel_motif(x0, y0, box_l, box_w, base_l, base_w)
            placements.extend(motif)

    return placements


def _enumerate_block_pinwheel_candidates(area_l, area_w, box_l, box_w, base_l, base_w):
    candidates: List[List[Placement2D]] = []
    box_area = box_l * box_w

    if min(area_l, area_w, box_l, box_w) <= 0:
        return candidates

    # Practical cap: prevents a very small SKU from making the request too slow,
    # while still covering normal packaging/pallet combinations generously.
    max_param = 30
    max_generated_candidates = 80
    horizontal_pairs = []
    vertical_pairs = []

    for n in range(1, min(int(area_l // box_l), max_param) + 1):
        for q in range(1, min(int(area_l // box_w), max_param) + 1):
            horizontal_l = n * box_l
            vertical_l = q * box_w
            contour_l = horizontal_l + vertical_l
            if contour_l <= area_l + 1e-9:
                horizontal_pairs.append((n, q, horizontal_l, vertical_l, contour_l))

    for m in range(1, min(int(area_w // box_w), max_param) + 1):
        for p in range(1, min(int(area_w // box_l), max_param) + 1):
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


def pattern_splitrow(area_l, area_w, box_l, box_w, swapped=False):
    best: List[Placement2D] = []

    if not swapped:
        a_l, a_w = box_l, box_w
        b_l, b_w = box_w, box_l
    else:
        a_l, a_w = box_w, box_l
        b_l, b_w = box_l, box_w

    max_rows_a = int(area_w // a_w)

    for rows_a in range(max_rows_a + 1):
        band_a_w = rows_a * a_w
        band_b_w = area_w - band_a_w

        placements: List[Placement2D] = []
        if band_a_w > 0:
            placements.extend(grid_fill(area_l, band_a_w, a_l, a_w, box_l, box_w, x0=0, y0=0))
        if band_b_w > 0:
            placements.extend(grid_fill(area_l, band_b_w, b_l, b_w, box_l, box_w, x0=0, y0=band_a_w))

        if len(placements) > len(best):
            best = placements

    plain = pattern_block(area_l, area_w, box_l, box_w)
    return best if len(best) >= len(plain) else plain


def _add_rectangular_margin_fill(
    base: List[Placement2D],
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
    base_l: float,
    base_w: float,
) -> List[Placement2D]:
    if not base:
        return []

    _, _, used_l, used_w = placements_bbox(base)
    placements = list(base)

    if area_l - used_l > 1e-9:
        right_strip = pattern_brick(area_l - used_l, area_w, box_l, box_w, rotated=False)
        for p in right_strip:
            placements.append(
                Placement2D(x=p.x + used_l, y=p.y, l=p.l, w=p.w, orientation=p.orientation)
            )

    if area_w - used_w > 1e-9 and used_l > 1e-9:
        top_strip = try_two_orientations_grid(
            used_l, area_w - used_w, box_l, box_w, base_l, base_w, x0=0, y0=used_w
        )
        placements.extend(top_strip)

    return placements if placements_are_valid(placements, area_l, area_w) else base


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
            _add_rectangular_margin_fill(candidate, area_l, area_w, box_l, box_w, base_l, base_w),
            1,
        ))

    simple = _pattern_tiled_simple_pinwheel(area_l, area_w, box_l, box_w, base_l, base_w)
    raw_candidates.append((simple, 1))
    raw_candidates.append((
        _add_rectangular_margin_fill(simple, area_l, area_w, box_l, box_w, base_l, base_w),
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


# ============================================================
# STACKING BUILDERS
# ============================================================

def build_layers(
    base_layer: List[Placement2D],
    interlock_layer: List[Placement2D],
    box_h: float,
    max_stack_height: float,
    stacking_mode: str,
) -> Tuple[List[Placement3D], int, List[List[Placement2D]]]:
    max_layers = int(max_stack_height // box_h)
    placements3d: List[Placement3D] = []
    layers_2d: List[List[Placement2D]] = []

    for layer_idx in range(max_layers):
        z = layer_idx * box_h

        if stacking_mode == "column":
            layer = base_layer
            layer_kind = "base"
        else:
            if layer_idx % 2 == 0:
                layer = base_layer
                layer_kind = "base"
            else:
                layer = interlock_layer
                layer_kind = "interlock"

        layers_2d.append(layer)

        for p in layer:
            placements3d.append(
                Placement3D(
                    x=p.x,
                    y=p.y,
                    z=z,
                    l=p.l,
                    w=p.w,
                    h=box_h,
                    orientation=p.orientation,
                    layer_kind=layer_kind,
                    layer_index=layer_idx,
                )
            )

    return placements3d, max_layers, layers_2d


# ============================================================
# LOAD CHECK
# ============================================================

def compute_bottom_loads(layers_2d: List[List[Placement2D]], box_weight: Optional[float]) -> List[float]:
    if box_weight is None or len(layers_2d) == 0:
        return [0.0] * (len(layers_2d[0]) if layers_2d else 0)

    n_layers = len(layers_2d)
    transmitted_loads = [[0.0] * len(layer) for layer in layers_2d]

    for upper_idx in range(n_layers - 1, 0, -1):
        upper_layer = layers_2d[upper_idx]
        lower_layer = layers_2d[upper_idx - 1]

        for ui, ub in enumerate(upper_layer):
            load_to_transfer = box_weight + transmitted_loads[upper_idx][ui]

            overlaps = []
            total_overlap = 0.0
            for li, lb in enumerate(lower_layer):
                ov = rect_overlap_area(ub, lb)
                if ov > 0:
                    overlaps.append((li, ov))
                    total_overlap += ov

            if total_overlap > 0:
                lower_idx = upper_idx - 1
                for li, ov in overlaps:
                    transmitted_loads[lower_idx][li] += load_to_transfer * (ov / total_overlap)

    return transmitted_loads[0]


def evaluate_weight_feasibility(layers_2d, box_weight, max_weight_on_bottom_box):
    if box_weight is None or max_weight_on_bottom_box is None:
        return True, 0.0, 0.0, []

    bottom_loads = compute_bottom_loads(layers_2d, box_weight)
    max_bottom_load = max(bottom_loads) if bottom_loads else 0.0
    avg_bottom_load = sum(bottom_loads) / len(bottom_loads) if bottom_loads else 0.0
    feasible = max_bottom_load <= max_weight_on_bottom_box + 1e-9

    return feasible, max_bottom_load, avg_bottom_load, bottom_loads


def result_metrics(
    name,
    stacking_mode,
    area_l,
    area_w,
    max_stack_height,
    box_l,
    box_w,
    box_h,
    base_layer,
    interlock_layer,
    placements3d,
    layers_2d,
    box_weight,
    max_weight_on_bottom_box,
    interlock_relation_name=None,
):
    max_layers = int(max_stack_height // box_h)

    if max_layers <= 0:
        counts = []
    elif stacking_mode == "column":
        counts = [len(base_layer)] * max_layers
    else:
        counts = [len(base_layer) if i % 2 == 0 else len(interlock_layer) for i in range(max_layers)]

    total_boxes = sum(counts)
    used_height = max_layers * box_h
    footprint_area = area_l * area_w
    layer_avg = sum(counts) / len(counts) if counts else 0.0

    layer_footprint_util = (layer_avg * box_l * box_w) / footprint_area if footprint_area > 0 else 0.0
    volumetric_util = (
        (total_boxes * box_volume(box_l, box_w, box_h)) / (area_l * area_w * max_stack_height)
        if area_l > 0 and area_w > 0 and max_stack_height > 0 else 0.0
    )

    feasible, max_bottom_load, avg_bottom_load, bottom_loads = evaluate_weight_feasibility(
        layers_2d, box_weight, max_weight_on_bottom_box
    )

    return {
        "pattern": name,
        "stacking": stacking_mode,
        "boxes_layer_A": len(base_layer),
        "boxes_layer_B": len(interlock_layer),
        "layers": max_layers,
        "total_boxes": total_boxes,
        "used_height_mm": used_height,
        "layer_footprint_util_pct": round(layer_footprint_util * 100, 2),
        "volumetric_util_pct": round(volumetric_util * 100, 2),
        "feasible_weight": feasible,
        "max_bottom_load_kg": round(max_bottom_load, 2),
        "avg_bottom_load_kg": round(avg_bottom_load, 2),
        "weight_limit_kg": max_weight_on_bottom_box,
        "interlock_relation": INTERLOCK_TRANSFORM_LABELS.get(interlock_relation_name, interlock_relation_name or ""),
        "placements3d": placements3d,
        "layer_A_2d": base_layer,
        "layer_B_2d": interlock_layer,
        "layers_2d": layers_2d,
        "bottom_loads": bottom_loads,
    }


def get_base_and_interlock_layers(pattern_name, area_l, area_w, box_l, box_w):
    if pattern_name == "Block":
        base = pattern_block(area_l, area_w, box_l, box_w)
        interlock = pattern_block(area_l, area_w, box_w, box_l)
    elif pattern_name == "Row":
        base = pattern_row(area_l, area_w, box_l, box_w)
        interlock = pattern_row(area_l, area_w, box_w, box_l)
    elif pattern_name == "Brick":
        base = pattern_brick_best(area_l, area_w, box_l, box_w)
        # Do not use a rotated brick layer as a visible interlock layer. It can
        # have a different row count/contour and creates the asymmetric brick
        # results we want to avoid. The customer-safe interlock builder will
        # derive a mirror/180° layer from this base layer only when that layer
        # keeps the same aligned contour.
        interlock = []
    elif pattern_name == "Pinwheel":
        base = pattern_pinwheel(area_l, area_w, box_l, box_w, rotated=False)
        interlock = pattern_pinwheel(area_l, area_w, box_l, box_w, rotated=True)
    elif pattern_name == "Splitrow":
        base = pattern_splitrow(area_l, area_w, box_l, box_w, swapped=False)
        interlock = pattern_splitrow(area_l, area_w, box_l, box_w, swapped=True)
    elif pattern_name == "Hybrid pinwheel":
        base = pattern_hybrid_pinwheel(area_l, area_w, box_l, box_w, rotated=False)
        interlock = pattern_hybrid_pinwheel(area_l, area_w, box_l, box_w, rotated=True)
    else:
        raise ValueError(f"Unknown pattern: {pattern_name}")

    base = center_placements_on_area(base, area_l, area_w)
    interlock = center_placements_on_area(interlock, area_l, area_w)

    base = prefer_edge_balanced_filler_layer(base, area_l, area_w)
    interlock = prefer_edge_balanced_filler_layer(interlock, area_l, area_w)

    base = prefer_edge_balanced_sparse_filler_lines(base, area_l, area_w)
    interlock = prefer_edge_balanced_sparse_filler_lines(interlock, area_l, area_w)

    return base, interlock


# ============================================================
# MAIN ANALYSIS
# ============================================================

PATTERNS = [
    "Block",
    "Row",
    "Brick",
    "Pinwheel",
    "Splitrow",
    "Hybrid pinwheel",
]

STACKINGS = [
    "column",
    "interlock",
]



def _customer_visible_render_signature(row: Dict) -> Tuple:
    """Return a stable signature for what the customer actually sees.

    The earlier dedupe compared the full internal 3D stack. That was too strict:
    for example, Column and Interlock can be internally different, but if the
    top visible layer and the customer-facing result metrics are the same, the
    rendered image looks repeated to the user. This signature intentionally
    focuses on the visible/top layer plus the visible result metrics.

    Pattern/stacking names, orientation labels, and layer kind are excluded.
    They are still stored for development/debugging, but they should not create
    duplicate customer rows when the render looks the same.
    """
    def n(value):
        return round(float(value), 4)

    placements3d = list(row.get("placements3d") or [])
    if not placements3d:
        visible_layer = []
        visible_layer_index = 0
    else:
        visible_layer_index = max(int(p.layer_index) for p in placements3d)
        visible_layer = [p for p in placements3d if int(p.layer_index) == visible_layer_index]

    visible_top_signature = tuple(
        sorted(
            (
                n(p.x), n(p.y),
                n(p.l), n(p.w),
            )
            for p in visible_layer
        )
    )

    return (
        int(row.get("layers") or 0),
        int(row.get("total_boxes") or 0),
        int(row.get("boxes_layer_A") or 0),
        int(row.get("boxes_layer_B") or 0),
        n(row.get("used_height_mm") or 0),
        n(row.get("layer_footprint_util_pct") or 0),
        n(row.get("volumetric_util_pct") or 0),
        visible_top_signature,
    )


def _interlock_feasibility_relation(
    base_layer: List[Placement2D],
    generated_interlock_layer: List[Placement2D],
    area_l: float,
    area_w: float,
) -> Tuple[bool, str, List[Placement2D]]:
    """Return whether an alternate interlock layer is engineering-feasible.

    This is intentionally less strict than the visible interlock renderer.

    Strict visible interlock requires the same occupied contour so the 3D render
    does not look odd. But for customer information, we still want to say
    "Interlock possible" when there is a valid alternate layer with the same
    box count and aligned footprint, even if we do not show it as a separate
    rendered option.
    """
    if not base_layer or not placements_are_valid(base_layer, area_l, area_w):
        return False, "", []

    base_signature = layer_geometry_signature(base_layer)
    candidates: List[Tuple[str, List[Placement2D], int]] = []

    if generated_interlock_layer:
        candidates.append(("alternate layer", generated_interlock_layer, 4))

    for transform_name, priority in (
        ("mirror_length", 3),
        ("mirror_width", 3),
        ("rotate_180", 2),
    ):
        candidates.append((
            INTERLOCK_TRANSFORM_LABELS.get(transform_name, transform_name),
            transform_layer(base_layer, area_l, area_w, transform_name),
            priority,
        ))

    accepted: List[Tuple[str, int, List[Placement2D]]] = []
    for label, candidate_layer, priority in candidates:
        if not candidate_layer:
            continue
        if len(candidate_layer) != len(base_layer):
            continue
        if not placements_are_valid(candidate_layer, area_l, area_w):
            continue
        if not layer_bounds_match(base_layer, candidate_layer):
            continue
        if layer_geometry_signature(candidate_layer) == base_signature:
            continue
        accepted.append((label, priority, candidate_layer))

    if not accepted:
        return False, "", []

    best_label, _, best_layer = max(accepted, key=lambda item: item[1])
    return True, best_label, best_layer


def _set_interlock_available(row: Dict) -> None:
    """Expose whether an equivalent or alternate interlock layer exists."""
    equivalents = [str(item).lower() for item in (row.get("debug_equivalent_results") or [])]
    already_possible = bool(row.get("interlock_possible", False))
    hidden_interlock = any("/ interlock" in item for item in equivalents)
    is_interlock_row = str(row.get("stacking", "")).lower() == "interlock"

    row["interlock_possible"] = already_possible or hidden_interlock or is_interlock_row

    if row["interlock_possible"] and not row.get("interlock_possible_relation"):
        if is_interlock_row:
            row["interlock_possible_relation"] = str(row.get("interlock_relation", "") or "alternate layer")
        elif hidden_interlock:
            row["interlock_possible_relation"] = "alternate layer"


def _dedupe_same_render_results(results: List[Dict]) -> List[Dict]:
    """Remove repeated customer-visible renderings while preserving dev data.

    We keep the first already-ranked representative and store removed engineering
    labels in debug_equivalent_results. At least one representative of each
    visible arrangement is always kept.
    """
    unique: List[Dict] = []
    seen: Dict[Tuple, Dict] = {}

    for row in results:
        signature = _customer_visible_render_signature(row)
        debug_label = f'{row.get("pattern", "")} / {row.get("stacking", "")}'
        row["debug_render_signature"] = signature
        row.setdefault("debug_equivalent_results", [])

        if signature in seen:
            kept_row = seen[signature]
            kept_row.setdefault("debug_equivalent_results", []).append(debug_label)
            if row.get("interlock_possible"):
                kept_row["interlock_possible"] = True
                if row.get("interlock_possible_relation") and not kept_row.get("interlock_possible_relation"):
                    kept_row["interlock_possible_relation"] = row.get("interlock_possible_relation")
                if row.get("interlock_possible_layer") and not kept_row.get("interlock_possible_layer"):
                    kept_row["interlock_possible_layer"] = row.get("interlock_possible_layer")
            continue

        seen[signature] = row
        unique.append(row)

    for row in unique:
        _set_interlock_available(row)

    return unique


def run_palletization_analysis(
    box_l: float,
    box_w: float,
    box_h: float,
    pallet_l: float,
    pallet_w: float,
    max_stack_height: float,
    max_width_stickout: float = 0.0,
    max_length_stickout: float = 0.0,
    box_weight: Optional[float] = None,
    max_weight_on_bottom_box: Optional[float] = None,
) -> List[Dict]:
    area_l, area_w = effective_pallet_size(
        pallet_l, pallet_w, max_length_stickout, max_width_stickout
    )

    results: List[Dict] = []

    for pattern_name in PATTERNS:
        base_layer, generated_interlock_layer = get_base_and_interlock_layers(
            pattern_name, area_l, area_w, box_l, box_w
        )
        if not base_layer:
            continue

        interlock_layer, interlock_relation_name = build_customer_safe_interlock_layer(
            base_layer, generated_interlock_layer, area_l, area_w
        )
        interlock_possible, interlock_possible_relation, interlock_possible_layer = _interlock_feasibility_relation(
            base_layer, generated_interlock_layer, area_l, area_w
        )

        for stacking_mode in STACKINGS:
            if stacking_mode == "interlock" and not interlock_relation_name:
                continue

            active_interlock_layer = interlock_layer if stacking_mode == "interlock" else base_layer

            placements3d, max_layers, layers_2d = build_layers(
                base_layer=base_layer,
                interlock_layer=active_interlock_layer,
                box_h=box_h,
                max_stack_height=max_stack_height,
                stacking_mode=stacking_mode,
            )

            row = result_metrics(
                pattern_name,
                stacking_mode,
                area_l,
                area_w,
                max_stack_height,
                box_l,
                box_w,
                box_h,
                base_layer,
                active_interlock_layer,
                placements3d,
                layers_2d,
                box_weight,
                max_weight_on_bottom_box,
                interlock_relation_name if stacking_mode == "interlock" else "same",
            )
            row["interlock_possible"] = bool(interlock_possible)
            row["interlock_possible_relation"] = interlock_possible_relation
            row["interlock_possible_layer"] = interlock_possible_layer if interlock_possible else []
            results.append(row)

    results.sort(
        key=lambda r: (
            0 if r["feasible_weight"] else 1,
            -r["total_boxes"],
            -r["volumetric_util_pct"],
            -r["layer_footprint_util_pct"],
        )
    )
    return _dedupe_same_render_results(results)


# ============================================================
# VISUALIZATION
# ============================================================

def get_3d_color(orientation, layer_kind):
    """Customer-facing colors for pallet boxes.

    Keep interlock and column renders in the same blue family. The interlock
    state is now explained with the toggle/label instead of orange layer colors,
    which avoids making alternate layers look like a different product.
    """
    if orientation == "LxW":
        return "#2FA8DC"
    return "#1F7FA6"


def draw_box_top_face(ax, p: Placement3D, z_top: float, color: str):
    """Redraw the top face so the layer pattern is legible in 3D."""
    x0, x1 = p.x, p.x + p.l
    y0, y1 = p.y, p.y + p.w
    verts = [[
        (x0, y0, z_top),
        (x1, y0, z_top),
        (x1, y1, z_top),
        (x0, y1, z_top),
    ]]
    poly = Poly3DCollection(
        verts,
        facecolors=color,
        edgecolors="#111111",
        linewidths=0.35,
        alpha=1.0,
    )
    try:
        poly.set_zsort("max")
    except Exception:
        pass
    ax.add_collection3d(poly)


def draw_box_top_outline(ax, p: Placement3D, z_top: float):
    """Add crisp top edges so bonded/spiral brick joints read clearly."""
    x0, x1 = p.x, p.x + p.l
    y0, y1 = p.y, p.y + p.w
    xs = [x0, x1, x1, x0, x0]
    ys = [y0, y0, y1, y1, y0]
    zs = [z_top] * 5
    ax.plot(xs, ys, zs, color="#111111", linewidth=0.65, alpha=1.0)


def clean_3d_axes(ax):
    ax.set_axis_off()
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])

    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        try:
            axis.pane.fill = False
            axis.pane.set_edgecolor("white")
        except Exception:
            pass


def plot_3d_result(ax, placements3d, pallet_l, pallet_w, max_h, title=None):
    deck_thickness = PALLET_DECK_THICKNESS_MM
    runner_height = PALLET_RUNNER_HEIGHT_MM
    pallet_total_height = PALLET_RENDER_HEIGHT_MM

    # top deck
    ax.bar3d(
        0, 0, runner_height,
        pallet_l, pallet_w, deck_thickness,
        color="#C8A26A",
        alpha=0.16,
        shade=True,
        edgecolor="black",
        linewidth=0.4,
    )

    # three runners
    runner_width = min(100, pallet_w / 6) if pallet_w else 100
    runner_positions_y = [
        0,
        (pallet_w - runner_width) / 2,
        pallet_w - runner_width,
    ]

    for y0 in runner_positions_y:
        ax.bar3d(
            0, y0, 0,
            pallet_l, runner_width, runner_height,
            color="#A67C52",
            alpha=0.20,
            shade=True,
            edgecolor="black",
            linewidth=0.4,
        )

    # Draw from lower to upper layers and from back to front. Matplotlib 3D
    # depth sorting can make bonded brick patterns look broken when the boxes
    # are semi-transparent, so customer-facing boxes are intentionally opaque
    # and their top joints are redrawn after each box.
    ordered_boxes = sorted(
        placements3d,
        key=lambda item: (item.z, item.y + item.w, item.x + item.l),
    )

    top_edges: List[Tuple[Placement3D, float]] = []
    for p in ordered_boxes:
        color = get_3d_color(p.orientation, p.layer_kind)
        z_base = p.z + pallet_total_height
        ax.bar3d(
            p.x, p.y, z_base,
            p.l, p.w, p.h,
            color=color,
            alpha=1.0,
            shade=False,
            edgecolor="#111111",
            linewidth=0.34,
            zsort="max",
        )
        top_edges.append((p, z_base + p.h))

    for p, z_top in top_edges:
        draw_box_top_face(ax, p, z_top + 0.01, get_3d_color(p.orientation, p.layer_kind))
    for p, z_top in top_edges:
        draw_box_top_outline(ax, p, z_top + 0.02)

    ax.set_xlim(0, pallet_l)
    ax.set_ylim(0, pallet_w)
    ax.set_zlim(0, max_h + pallet_total_height)
    try:
        ax.set_box_aspect((pallet_l, pallet_w, max_h + pallet_total_height))
    except Exception:
        pass
    # Keep the cleaner customer-facing colors and top-joint rendering from the
    # latest brick update, but restore the previous camera angle/perspective so
    # the pallet view matches the earlier familiar presentation.
    ax.view_init(elev=24, azim=-58)
    try:
        # Orthographic projection avoids perspective/parallax distortion, so
        # stacked interlock layers look vertically aligned when their geometry
        # is actually aligned.
        ax.set_proj_type("ortho")
    except Exception:
        pass
    clean_3d_axes(ax)


def _interlock_render_row(selected_result: Dict, max_stack_height: float) -> Dict:
    """Build a temporary render row that alternates base/interlock layers.

    This is only used when the user turns the interlock preview on. The result
    table remains deduplicated, but the selected option can still be visualized
    as an interlocked stack when an alternate layer is feasible.
    """
    interlock_layer = selected_result.get("interlock_possible_layer") or []
    base_layer = selected_result.get("layer_A_2d") or []

    if not interlock_layer or not base_layer:
        return selected_result

    placements = selected_result.get("placements3d") or []
    if placements:
        box_h = float(placements[0].h)
    else:
        box_h = float(selected_result.get("used_height_mm") or 0) / max(int(selected_result.get("layers") or 1), 1)

    if box_h <= 0:
        return selected_result

    placements3d, _max_layers, layers_2d = build_layers(
        base_layer=base_layer,
        interlock_layer=interlock_layer,
        box_h=box_h,
        max_stack_height=max_stack_height,
        stacking_mode="interlock",
    )

    render_row = dict(selected_result)
    render_row["placements3d"] = placements3d
    render_row["layers_2d"] = layers_2d
    render_row["layer_B_2d"] = interlock_layer
    render_row["stacking"] = "interlock"
    render_row["interlock_render_active"] = True
    return render_row


def selected_result_for_render(
    selected_result: Dict,
    max_stack_height: float,
    render_interlock: bool = False,
) -> Dict:
    """Return the authoritative selected placement set for any renderer.

    Browser and server renderers must consume the same placements. Alternate
    layer preview remains a presentation choice and does not alter ranking or
    the selected analysis result.
    """
    if render_interlock:
        return _interlock_render_row(selected_result, max_stack_height)
    return selected_result


def render_selected_result(
    selected_result: Dict,
    pallet_l: float,
    pallet_w: float,
    max_stack_height: float,
    media_root: str,
    render_interlock: bool = False,
) -> PalletizationRenderResult:
    rel_dir = "palletization"
    file_name = f"pallet_{uuid.uuid4().hex}.png"
    rel_path = os.path.join(rel_dir, file_name)
    abs_path = os.path.join(media_root, rel_path)

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    render_row = selected_result_for_render(
        selected_result,
        max_stack_height,
        render_interlock=render_interlock,
    )

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    plot_3d_result(ax, render_row["placements3d"], pallet_l, pallet_w, max_stack_height)

    plt.tight_layout(pad=0.1)
    plt.savefig(abs_path, dpi=120, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)

    return PalletizationRenderResult(image_rel_path=rel_path)
