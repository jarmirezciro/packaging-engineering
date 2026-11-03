"""Deterministic rectangular mosaic pattern families.

The constructive geometry is adapted from KolliPack's approved Palletization
patterns, without pallet ranking, overhang, stacking, interlock presentation,
or load calculations.  Stage 1 keeps the original Palletization implementation
in place while Container Selection benchmarks this tool-independent copy.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Sequence, Tuple

from .geometry import (
    Placement2D,
    PlacementBudgetExceeded,
    best_grid,
    bounding_box,
    center_on_area,
    count_fitting_units,
    fits_within,
    grid_fill,
    grid_quantity,
    orientation_name,
    translate,
)
from .validation import geometry_signature, layout_signature, validate_placements


# Stage 1 deliberately limits every block leaf to twelve rows/columns.  This
# covers the established pallet fixtures while keeping each parameter cross
# product below 12^4 rather than allowing runtime to grow with footprint size.
MAX_PINWHEEL_PARAMETER = 12
MAX_PINWHEEL_CANDIDATES = 8
MAX_REGIONAL_CUTS_PER_AXIS = 16
DEFAULT_CANDIDATE_BUDGET = 96

PATTERN_FAMILIES = (
    "block",
    "row",
    "splitrow",
    "brick",
    "pinwheel",
    "hybrid_pinwheel",
    "nested_pinwheel",
    "centre_filled_pinwheel",
    "regional_mosaic",
)


@dataclass(frozen=True)
class PatternCandidate:
    family: str
    variant: str
    placements: Tuple[Placement2D, ...]

    @property
    def quantity(self) -> int:
        return len(self.placements)


def _valid(
    placements: Sequence[Placement2D],
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
) -> bool:
    return bool(placements) and validate_placements(
        placements,
        area_l,
        area_w,
        expected_footprint=(box_l, box_w),
    ).valid


def pattern_block(area_l, area_w, box_l, box_w):
    first = grid_quantity(area_l, area_w, box_l, box_w)
    second = grid_quantity(area_l, area_w, box_w, box_l)
    if first >= second:
        return grid_fill(area_l, area_w, box_l, box_w, box_l, box_w)
    return grid_fill(area_l, area_w, box_w, box_l, box_l, box_w)


def pattern_row(area_l, area_w, box_l, box_w):
    rows_first = count_fitting_units(area_w, box_w)
    rows_second = count_fitting_units(area_w, box_l)
    first = grid_quantity(area_l, area_w, box_l, box_w)
    second = grid_quantity(area_l, area_w, box_w, box_l)
    use_first = rows_first > rows_second or (
        rows_first == rows_second and first >= second
    )
    if use_first:
        return grid_fill(area_l, area_w, box_l, box_w, box_l, box_w)
    return grid_fill(area_l, area_w, box_w, box_l, box_l, box_w)


def _near_integer(value: float, tolerance: float = 1e-6):
    if value <= 0:
        return None
    rounded = int(round(value))
    return rounded if rounded > 0 and abs(value - rounded) <= tolerance else None


def _spiral_domino_pairs(cols: int, rows: int):
    if cols < 2 or rows < 2 or (cols * rows) % 2:
        return []
    pairs = []
    left, top, right, bottom = 0, 0, cols - 1, rows - 1
    while left <= right and top <= bottom:
        path = [(x, top) for x in range(left, right + 1)]
        path.extend((right, y) for y in range(top + 1, bottom + 1))
        if bottom > top:
            path.extend((x, bottom) for x in range(right - 1, left - 1, -1))
        if right > left:
            path.extend((left, y) for y in range(bottom - 1, top, -1))
        if len(path) % 2:
            return []
        for index in range(0, len(path), 2):
            first, second = path[index], path[index + 1]
            if abs(first[0] - second[0]) + abs(first[1] - second[1]) != 1:
                return []
            pairs.append((first, second))
        left += 1
        top += 1
        right -= 1
        bottom -= 1
    return pairs


def _brick_spiral(area_l, area_w, box_l, box_w):
    short = min(box_l, box_w)
    long = max(box_l, box_w)
    if short <= 0 or _near_integer(long / short) != 2:
        return []
    cols = count_fitting_units(area_l, short)
    rows = count_fitting_units(area_w, short)
    pairs = _spiral_domino_pairs(cols, rows)
    if not pairs:
        return []
    x0 = (area_l - cols * short) / 2.0
    y0 = (area_w - rows * short) / 2.0
    placements = []
    for first, second in pairs:
        x = min(first[0], second[0])
        y = min(first[1], second[1])
        l = (abs(first[0] - second[0]) + 1) * short
        w = (abs(first[1] - second[1]) + 1) * short
        placements.append(
            Placement2D(
                x0 + x * short,
                y0 + y * short,
                l,
                w,
                orientation_name(l, w, box_l, box_w),
            )
        )
    return placements if _valid(placements, area_l, area_w, box_l, box_w) else []


def _brick_basket_candidates(area_l, area_w, box_l, box_w):
    candidates = []
    spiral = _brick_spiral(area_l, area_w, box_l, box_w)
    if spiral:
        candidates.append(spiral)
    short = min(box_l, box_w)
    long = max(box_l, box_w)
    ratio = _near_integer(long / short) if short > 0 else None
    if ratio is None or ratio < 2 or ratio > 6:
        return candidates
    modules_x = count_fitting_units(area_l, long)
    modules_y = count_fitting_units(area_w, long)
    if not modules_x or not modules_y:
        return candidates
    x0 = (area_l - modules_x * long) / 2.0
    y0 = (area_w - modules_y * long) / 2.0
    for phase in (0, 1):
        layer = []
        for module_y in range(modules_y):
            for module_x in range(modules_x):
                origin_x = x0 + module_x * long
                origin_y = y0 + module_y * long
                horizontal = (module_x + module_y + phase) % 2 == 0
                for offset in range(ratio):
                    l, w = (long, short) if horizontal else (short, long)
                    x = origin_x if horizontal else origin_x + offset * short
                    y = origin_y + offset * short if horizontal else origin_y
                    layer.append(
                        Placement2D(x, y, l, w, orientation_name(l, w, box_l, box_w))
                    )
        if _valid(layer, area_l, area_w, box_l, box_w):
            signature = geometry_signature(layer)
            if all(geometry_signature(existing) != signature for existing in candidates):
                candidates.append(layer)
    return candidates


def _brick_staggered(area_l, area_w, box_l, box_w, rotated=False):
    work_l, work_w = (box_w, box_l) if rotated else (box_l, box_w)
    rows = count_fitting_units(area_w, work_w)
    cols = count_fitting_units(area_l, work_l)
    if rows < 2 or cols < 2:
        return []
    x0 = (area_l - cols * work_l) / 2.0
    y0 = (area_w - rows * work_w) / 2.0
    orientation = orientation_name(work_l, work_w, box_l, box_w)
    placements = []
    for row in range(rows):
        shifted = row % 2 == 1
        row_cols = cols - 1 if shifted else cols
        row_x = x0 + work_l / 2.0 if shifted else x0
        placements.extend(
            Placement2D(
                row_x + column * work_l,
                y0 + row * work_w,
                work_l,
                work_w,
                orientation,
            )
            for column in range(row_cols)
        )
    return placements if _valid(placements, area_l, area_w, box_l, box_w) else []


def pattern_brick_best(area_l, area_w, box_l, box_w):
    short = min(box_l, box_w)
    if short <= 0 or abs(max(box_l, box_w) / short - 2.0) > 0.02:
        return []
    candidates = [(layer, 2) for layer in _brick_basket_candidates(area_l, area_w, box_l, box_w)]
    candidates.extend(
        (layer, 1)
        for layer in (
            _brick_staggered(area_l, area_w, box_l, box_w, False),
            _brick_staggered(area_l, area_w, box_l, box_w, True),
        )
        if layer
    )
    if not candidates:
        return []

    def score(item):
        layer, priority = item
        min_x, min_y, max_x, max_y = bounding_box(layer)
        occupied = sum(p.l * p.w for p in layer)
        bbox_area = (max_x - min_x) * (max_y - min_y)
        return (
            len(layer),
            occupied / (area_l * area_w),
            priority,
            int(len({p.orientation for p in layer}) > 1),
            occupied / bbox_area if bbox_area else 0.0,
        )

    return max(candidates, key=score)[0]


def _split_choice(area_l, area_w, a_l, a_w, b_l, b_w, axis):
    if axis == "rows":
        max_units = count_fitting_units(area_w, a_w)
        a_across = count_fitting_units(area_l, a_l)
        b_across = count_fitting_units(area_l, b_l)
        split = lambda units: (
            units * a_w,
            count_fitting_units(area_w - units * a_w, b_w),
        )
    else:
        max_units = count_fitting_units(area_l, a_l)
        a_across = count_fitting_units(area_w, a_w)
        b_across = count_fitting_units(area_w, b_w)
        split = lambda units: (
            units * a_l,
            count_fitting_units(area_l - units * a_l, b_l),
        )
    best = None
    best_score = None
    for a_units in range(max_units + 1):
        band_a, b_units = split(a_units)
        a_count = a_units * a_across
        b_count = b_units * b_across
        mixed = a_count > 0 and b_count > 0
        score = (a_count + b_count, int(mixed), -b_units if mixed else 0, min(a_count, b_count) if mixed else 0)
        if best_score is None or score > best_score:
            best_score = score
            best = (axis, band_a, a_count, b_count, b_units)
    return best


def _materialize_split(choice, area_l, area_w, a_l, a_w, b_l, b_w, box_l, box_w):
    if not choice or not (choice[2] or choice[3]):
        return []
    axis, band_a, _a_count, _b_count, _b_units = choice
    if axis == "rows":
        first = grid_fill(area_l, band_a, a_l, a_w, box_l, box_w) if band_a > 0 else []
        remaining = area_w - band_a
        second = grid_fill(area_l, remaining, b_l, b_w, box_l, box_w, 0.0, band_a) if remaining > 0 else []
    else:
        first = grid_fill(band_a, area_w, a_l, a_w, box_l, box_w) if band_a > 0 else []
        remaining = area_l - band_a
        second = grid_fill(remaining, area_w, b_l, b_w, box_l, box_w, band_a, 0.0) if remaining > 0 else []
    return first + second


def pattern_splitrow(area_l, area_w, box_l, box_w, swapped=False):
    pairs = [(box_w, box_l, box_l, box_w), (box_l, box_w, box_w, box_l)]
    if swapped:
        pairs.reverse()
    best = []
    best_score = None
    for params in pairs:
        for axis in ("rows", "columns"):
            choice = _split_choice(area_l, area_w, *params, axis)
            layer = _materialize_split(choice, area_l, area_w, *params, box_l, box_w)
            if not _valid(layer, area_l, area_w, box_l, box_w):
                continue
            mixed = choice[2] > 0 and choice[3] > 0
            score = (
                choice[2] + choice[3],
                int(mixed),
                -choice[4] if mixed else 0,
                min(choice[2], choice[3]) if mixed else 0,
            )
            if best_score is None or score > best_score:
                best_score, best = score, layer
    plain = pattern_block(area_l, area_w, box_l, box_w)
    return best if len(best) >= len(plain) else plain


def _pinwheel_motif(x0, y0, box_l, box_w, base_l, base_w):
    span = box_l + box_w
    placements = [
        Placement2D(x0, y0, box_l, box_w, orientation_name(box_l, box_w, base_l, base_w)),
        Placement2D(x0 + box_l, y0, box_w, box_l, orientation_name(box_w, box_l, base_l, base_w)),
        Placement2D(x0 + box_w, y0 + box_l, box_l, box_w, orientation_name(box_l, box_w, base_l, base_w)),
        Placement2D(x0, y0 + box_w, box_w, box_l, orientation_name(box_w, box_l, base_l, base_w)),
    ]
    return placements, span, span


def _block_pinwheel(box_l, box_w, base_l, base_w, m, n, p, q):
    horizontal_l, horizontal_w = n * box_l, m * box_w
    vertical_l, vertical_w = q * box_w, p * box_l
    placements = grid_fill(horizontal_l, horizontal_w, box_l, box_w, base_l, base_w)
    placements += grid_fill(vertical_l, vertical_w, box_w, box_l, base_l, base_w, horizontal_l, 0.0)
    placements += grid_fill(horizontal_l, horizontal_w, box_l, box_w, base_l, base_w, vertical_l, vertical_w)
    placements += grid_fill(vertical_l, vertical_w, box_w, box_l, base_l, base_w, 0.0, horizontal_w)
    return placements, horizontal_l + vertical_l, horizontal_w + vertical_w


def _block_pinwheel_candidates(area_l, area_w, box_l, box_w, base_l, base_w):
    if min(area_l, area_w, box_l, box_w) <= 0:
        return []
    horizontal = []
    vertical = []
    for n in range(1, min(count_fitting_units(area_l, box_l), MAX_PINWHEEL_PARAMETER) + 1):
        for q in range(1, min(count_fitting_units(area_l, box_w), MAX_PINWHEEL_PARAMETER) + 1):
            h_l, v_l = n * box_l, q * box_w
            if fits_within(h_l + v_l, area_l):
                horizontal.append((n, q, h_l, v_l, h_l + v_l))
    for m in range(1, min(count_fitting_units(area_w, box_w), MAX_PINWHEEL_PARAMETER) + 1):
        for p in range(1, min(count_fitting_units(area_w, box_l), MAX_PINWHEEL_PARAMETER) + 1):
            h_w, v_w = m * box_w, p * box_l
            if fits_within(h_w + v_w, area_w):
                vertical.append((m, p, h_w, v_w, h_w + v_w))
    params = []
    box_area = box_l * box_w
    for n, q, h_l, v_l, contour_l in horizontal:
        for m, p, h_w, v_w, contour_w in vertical:
            if h_l < v_l or v_w < h_w or (h_l - v_l) * (v_w - h_w) > box_area:
                continue
            count = 2 * (m * n + p * q)
            params.append((count, count * box_area / (area_l * area_w), count * box_area / (contour_l * contour_w), m, n, p, q))
    params.sort(reverse=True)
    layers = []
    for _count, _area, _bbox, m, n, p, q in params[:MAX_PINWHEEL_CANDIDATES]:
        layer, _contour_l, _contour_w = _block_pinwheel(box_l, box_w, base_l, base_w, m, n, p, q)
        if _valid(layer, area_l, area_w, base_l, base_w):
            layers.append(layer)
    return layers


def _tiled_pinwheel(area_l, area_w, box_l, box_w, base_l, base_w):
    _motif, tile_l, tile_w = _pinwheel_motif(0.0, 0.0, box_l, box_w, base_l, base_w)
    placements = []
    for y in range(count_fitting_units(area_w, tile_w)):
        for x in range(count_fitting_units(area_l, tile_l)):
            motif, _l, _w = _pinwheel_motif(x * tile_l, y * tile_w, box_l, box_w, base_l, base_w)
            placements.extend(motif)
    return placements


def _pinwheel_score(layer, area_l, area_w, priority):
    if not layer:
        return (0, priority, 0.0, 0.0)
    min_x, min_y, max_x, max_y = bounding_box(layer)
    occupied = sum(p.l * p.w for p in layer)
    bbox = (max_x - min_x) * (max_y - min_y)
    return (len(layer), priority, occupied / (area_l * area_w), occupied / bbox if bbox else 0.0)


def _best_valid(candidates, area_l, area_w, box_l, box_w):
    unique = []
    seen = set()
    for item in candidates:
        layer, priority = item[:2]
        already_valid = bool(item[2]) if len(item) > 2 else False
        if not already_valid and not _valid(layer, area_l, area_w, box_l, box_w):
            continue
        signature = layout_signature(layer)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append((layer, priority))
    return max(unique, key=lambda item: _pinwheel_score(item[0], area_l, area_w, item[1]))[0] if unique else []


def pattern_pinwheel(area_l, area_w, box_l, box_w, rotated=False):
    base_l, base_w = box_l, box_w
    work_l, work_w = (box_w, box_l) if rotated else (box_l, box_w)
    candidates = [(layer, 2, True) for layer in _block_pinwheel_candidates(area_l, area_w, work_l, work_w, base_l, base_w)]
    candidates.append((_tiled_pinwheel(area_l, area_w, work_l, work_w, base_l, base_w), 1))
    return _best_valid(candidates, area_l, area_w, base_l, base_w)


def _balance_margin_fill_lines(fillers, strip_x, strip_y, strip_l, strip_w, axis):
    if len(fillers) < 2 or axis not in {"x", "y"}:
        return fillers
    groups = {}
    for placement in fillers:
        key = (
            round(placement.y if axis == "x" else placement.x, 6),
            round(placement.l, 6),
            round(placement.w, 6),
            placement.orientation,
        )
        groups.setdefault(key, []).append(placement)
    balanced = []
    changed = False
    for group in groups.values():
        ordered = sorted(group, key=lambda item: item.x if axis == "x" else item.y)
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
        positions = [origin + index * unit for index in range(side_count)]
        if count % 2:
            positions.append(origin + (span - unit) / 2.0)
        far_start = origin + span - side_count * unit
        positions.extend(far_start + index * unit for index in range(side_count))
        positions.sort()
        candidate = [
            Placement2D(
                position if axis == "x" else source.x,
                source.y if axis == "x" else position,
                source.l,
                source.w,
                source.orientation,
            )
            for source, position in zip(ordered, positions)
        ]
        balanced.extend(candidate)
        changed = changed or layout_signature(candidate) != layout_signature(ordered)
    return balanced if changed else fillers


def _add_margin_fill(
    base,
    area_l,
    area_w,
    box_l,
    box_w,
    base_l,
    base_w,
    *,
    balance_fillers=True,
):
    if not base:
        return []
    _min_x, _min_y, max_x, max_y = bounding_box(base)
    placements = list(base)
    if area_l - max_x > 0:
        right = _brick_staggered(area_l - max_x, area_w, box_l, box_w)
        right = translate(right, max_x, 0.0)
        if balance_fillers:
            right = _balance_margin_fill_lines(
                right, max_x, 0.0, area_l - max_x, area_w, "y"
            )
        placements.extend(right)
    if area_w - max_y > 0 and max_x > 0:
        if grid_quantity(max_x, area_w - max_y, box_l, box_w) >= grid_quantity(
            max_x, area_w - max_y, box_w, box_l
        ):
            top = grid_fill(
                max_x,
                area_w - max_y,
                box_l,
                box_w,
                base_l,
                base_w,
                0.0,
                max_y,
            )
        else:
            top = grid_fill(
                max_x,
                area_w - max_y,
                box_w,
                box_l,
                base_l,
                base_w,
                0.0,
                max_y,
            )
        if balance_fillers:
            top = _balance_margin_fill_lines(
                top, 0.0, max_y, max_x, area_w - max_y, "x"
            )
        placements.extend(top)
    return placements if _valid(placements, area_l, area_w, base_l, base_w) else list(base)


def pattern_hybrid_pinwheel(area_l, area_w, box_l, box_w, rotated=False):
    base_l, base_w = box_l, box_w
    work_l, work_w = (box_w, box_l) if rotated else (box_l, box_w)
    candidates = []
    for layer in _block_pinwheel_candidates(area_l, area_w, work_l, work_w, base_l, base_w):
        candidates.extend(((layer, 2, True), (_add_margin_fill(
            layer,
            area_l,
            area_w,
            work_l,
            work_w,
            base_l,
            base_w,
            balance_fillers=not rotated,
        ), 1, True)))
    simple = _tiled_pinwheel(area_l, area_w, work_l, work_w, base_l, base_w)
    candidates.extend(((simple, 1), (_add_margin_fill(
        simple,
        area_l,
        area_w,
        work_l,
        work_w,
        base_l,
        base_w,
        balance_fillers=not rotated,
    ), 0, True)))
    return _best_valid(candidates, area_l, area_w, base_l, base_w)


def _nested_candidates(area_l, area_w, box_l, box_w, base_l, base_w):
    inner_span = box_l + box_w
    box_area = box_l * box_w
    params = []
    for n in range(1, min(count_fitting_units(area_l, box_l), MAX_PINWHEEL_PARAMETER) + 1):
        for q in range(1, min(count_fitting_units(area_l, box_w), MAX_PINWHEEL_PARAMETER) + 1):
            h_l, v_l = n * box_l, q * box_w
            if not fits_within(h_l + v_l, area_l):
                continue
            for m in range(1, min(count_fitting_units(area_w, box_w), MAX_PINWHEEL_PARAMETER) + 1):
                for p in range(1, min(count_fitting_units(area_w, box_l), MAX_PINWHEEL_PARAMETER) + 1):
                    h_w, v_w = m * box_w, p * box_l
                    if not fits_within(h_w + v_w, area_w) or h_l < v_l or v_w < h_w:
                        continue
                    hole_l, hole_w = h_l - v_l, v_w - h_w
                    if hole_l < inner_span or hole_w < inner_span or hole_l > 2 * inner_span or hole_w > 2 * inner_span:
                        continue
                    count = 2 * (m * n + p * q) + 4
                    params.append((count, count * box_area / (area_l * area_w), -(hole_l * hole_w - inner_span * inner_span), m, n, p, q, h_w, v_l, hole_l, hole_w))
    params.sort(reverse=True)
    layers = []
    for _count, _util, _residual, m, n, p, q, h_w, v_l, hole_l, hole_w in params[:MAX_PINWHEEL_CANDIDATES]:
        outer, _l, _w = _block_pinwheel(box_l, box_w, base_l, base_w, m, n, p, q)
        inner, _l, _w = _pinwheel_motif(v_l + (hole_l - inner_span) / 2.0, h_w + (hole_w - inner_span) / 2.0, box_l, box_w, base_l, base_w)
        layer = outer + inner
        if _valid(layer, area_l, area_w, base_l, base_w):
            layers.append(layer)
    return layers


def pattern_nested_pinwheel(area_l, area_w, box_l, box_w, rotated=False):
    base_l, base_w = box_l, box_w
    work_l, work_w = (box_w, box_l) if rotated else (box_l, box_w)
    return _best_valid([(layer, 1, True) for layer in _nested_candidates(area_l, area_w, work_l, work_w, base_l, base_w)], area_l, area_w, base_l, base_w)


def _rotate_90(layer, contour_w, base_l, base_w):
    return [Placement2D(contour_w - p.y - p.w, p.x, p.w, p.l, orientation_name(p.w, p.l, base_l, base_w)) for p in layer]


def _center_filled_motif(box_l, box_w):
    long, short = max(box_l, box_w), min(box_l, box_w)
    if short <= 0 or long <= short or long > 2 * short:
        return [], 0.0, 0.0
    horizontal = orientation_name(long, short, box_l, box_w)
    vertical = orientation_name(short, long, box_l, box_w)
    layer = [
        Placement2D(0, 0, long, short, horizontal),
        Placement2D(long, 0, long, short, horizontal),
        Placement2D(0, short, long, short, horizontal),
        Placement2D(2 * long, 0, short, long, vertical),
        Placement2D(long, short, short, long, vertical),
        Placement2D(0, 2 * short, short, long, vertical),
        Placement2D(long + short, long, long, short, horizontal),
        Placement2D(short, long + short, long, short, horizontal),
        Placement2D(long + short, long + short, long, short, horizontal),
    ]
    return layer, 2 * long + short, long + 2 * short


def pattern_center_filled_pinwheel(area_l, area_w, box_l, box_w):
    motif, contour_l, contour_w = _center_filled_motif(box_l, box_w)
    candidates = []
    if motif and fits_within(contour_l, area_l) and fits_within(contour_w, area_w):
        candidates.append(center_on_area(motif, area_l, area_w))
    rotated = _rotate_90(motif, contour_w, box_l, box_w) if motif else []
    if rotated and fits_within(contour_w, area_l) and fits_within(contour_l, area_w):
        candidates.append(center_on_area(rotated, area_l, area_w))
    candidates = [layer for layer in candidates if len(layer) == 9 and _valid(layer, area_l, area_w, box_l, box_w)]
    if not candidates:
        return []
    def score(layer):
        min_x, min_y, max_x, max_y = bounding_box(layer)
        free_l, free_w = area_l - (max_x - min_x), area_w - (max_y - min_y)
        return (-abs(free_l - free_w), -(free_l + free_w))
    return max(candidates, key=score)


def _regional_candidates(area_l, area_w, box_l, box_w):
    """Bounded two-region mosaics with cuts derived only from carton multiples."""
    candidates = []
    x_cuts = sorted({
        value
        for step in (box_l, box_w)
        for index in range(1, min(count_fitting_units(area_l, step), MAX_REGIONAL_CUTS_PER_AXIS) + 1)
        if (value := index * step) < area_l
    })[:MAX_REGIONAL_CUTS_PER_AXIS]
    y_cuts = sorted({
        value
        for step in (box_l, box_w)
        for index in range(1, min(count_fitting_units(area_w, step), MAX_REGIONAL_CUTS_PER_AXIS) + 1)
        if (value := index * step) < area_w
    })[:MAX_REGIONAL_CUTS_PER_AXIS]
    for cut in x_cuts:
        layer = best_grid(cut, area_w, box_l, box_w)
        layer += best_grid(area_l - cut, area_w, box_l, box_w, cut, 0.0)
        if _valid(layer, area_l, area_w, box_l, box_w):
            candidates.append(("length", cut, layer))
    for cut in y_cuts:
        layer = best_grid(area_l, cut, box_l, box_w)
        layer += best_grid(area_l, area_w - cut, box_l, box_w, 0.0, cut)
        if _valid(layer, area_l, area_w, box_l, box_w):
            candidates.append(("width", cut, layer))
    return candidates


@lru_cache(maxsize=256)
def enumerate_pattern_candidates(
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
    *,
    candidate_budget: int = DEFAULT_CANDIDATE_BUDGET,
) -> Tuple[PatternCandidate, ...]:
    """Enumerate valid, distinct candidates in stable family/variant order."""
    values = (float(area_l), float(area_w), float(box_l), float(box_w))
    if not all(value > 0 for value in values) or candidate_budget <= 0:
        return ()
    candidates = []
    seen = set()

    def add(family, variant, layer):
        if len(candidates) >= candidate_budget or not _valid(layer, area_l, area_w, box_l, box_w):
            return
        signature = layout_signature(layer)
        if signature in seen:
            return
        seen.add(signature)
        candidates.append(PatternCandidate(family, variant, tuple(layer)))

    try:
        add("block", "best", pattern_block(*values))
        add("row", "best", pattern_row(*values))
        add("splitrow", "primary", pattern_splitrow(*values))
        add("splitrow", "swapped", pattern_splitrow(*values, swapped=True))
        add("brick", "best", pattern_brick_best(*values))
        add("pinwheel", "primary", pattern_pinwheel(*values))
        add("pinwheel", "rotated", pattern_pinwheel(*values, rotated=True))
        add("hybrid_pinwheel", "primary", pattern_hybrid_pinwheel(*values))
        add("hybrid_pinwheel", "rotated", pattern_hybrid_pinwheel(*values, rotated=True))
        add("nested_pinwheel", "primary", pattern_nested_pinwheel(*values))
        add("nested_pinwheel", "rotated", pattern_nested_pinwheel(*values, rotated=True))
        add("centre_filled_pinwheel", "best", pattern_center_filled_pinwheel(*values))
        for axis, cut, layer in _regional_candidates(*values):
            add("regional_mosaic", f"{axis}:{cut:.9g}", layer)
            if len(candidates) >= candidate_budget:
                break
    except PlacementBudgetExceeded:
        # The caller receives the valid bounded prefix and can safely retain its
        # legacy solution. No partial geometry is emitted by a failed pattern.
        pass
    return tuple(candidates)
