# packagingapp/utils/container_tool/engine.py

import heapq
import math
import os
import uuid
from dataclasses import dataclass, replace
from itertools import permutations
from typing import List, Tuple, Dict, Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image, ImageChops


# =========================================================
# DATA STRUCTURES
# =========================================================

@dataclass
class Space:
    x: float
    y: float
    z: float
    L: float
    W: float
    H: float

    @property
    def volume(self) -> float:
        return self.L * self.W * self.H

    def fits(self, dims: Tuple[float, float, float]) -> bool:
        l, w, h = dims
        return l <= self.L and w <= self.W and h <= self.H


@dataclass
class Placement:
    product_name: str
    item_index: int
    row_index: int
    sequence: int
    weight: float
    stackable: bool
    x: float
    y: float
    z: float
    l: float
    w: float
    h: float


@dataclass
class ResidualPlan:
    """One bounded homogeneous-grid plan inside a free rectangular space."""

    placements: List[Tuple[float, float, float, float, float, float]]
    spaces: List[Space]

    @property
    def count(self) -> int:
        return len(self.placements)


# =========================================================
# ROTATIONS
# =========================================================

def allowed_orientations(
    dims: Tuple[float, float, float],
    r1: bool,
    r2: bool,
    r3: bool
) -> List[Tuple[float, float, float]]:
    """
    Rotation groups aligned with the typical 3-rotation logic used in your app.

    r1 => standing on height H:
        (L, W, H), (W, L, H)

    r2 => standing on width W:
        (L, H, W), (H, L, W)

    r3 => standing on length L:
        (W, H, L), (H, W, L)
    """
    L, W, H = dims
    rots = []

    if r1:
        rots.extend([
            (L, W, H),
            (W, L, H),
        ])

    if r2:
        rots.extend([
            (L, H, W),
            (H, L, W),
        ])

    if r3:
        rots.extend([
            (W, H, L),
            (H, W, L),
        ])

    # remove duplicates while preserving order
    seen = set()
    unique = []
    for r in rots:
        key = (round(r[0], 6), round(r[1], 6), round(r[2], 6))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# =========================================================
# SPACE SPLIT
# =========================================================

def split_space(
    space: Space,
    dims: Tuple[float, float, float],
    *,
    support_stackable: bool = True,
) -> List[Space]:
    """
    Residual-space split after placing one box at the lower-left-bottom corner
    of the selected space.
    """
    l, w, h = dims
    x, y, z = space.x, space.y, space.z

    new_spaces = []

    # Right residual
    if space.L - l > 1e-9:
        new_spaces.append(
            Space(
                x=x + l,
                y=y,
                z=z,
                L=space.L - l,
                W=space.W,
                H=space.H,
            )
        )

    # Front residual
    if space.W - w > 1e-9:
        new_spaces.append(
            Space(
                x=x,
                y=y + w,
                z=z,
                L=l,
                W=space.W - w,
                H=space.H,
            )
        )

    # Top residual is usable only when the placed unit may support cargo.
    if support_stackable and space.H - h > 1e-9:
        new_spaces.append(
            Space(
                x=x,
                y=y,
                z=z + h,
                L=l,
                W=w,
                H=space.H - h,
            )
        )

    return new_spaces


def can_space_contain_any_item(space: Space, remaining_items: List[Dict]) -> bool:
    for item in remaining_items:
        for rot in item["orientations"]:
            if space.fits(rot):
                return True
    return False


def prune_spaces(spaces: List[Space], remaining_items: List[Dict]) -> List[Space]:
    pruned = []
    for s in spaces:
        if s.L <= 1e-9 or s.W <= 1e-9 or s.H <= 1e-9:
            continue
        if remaining_items:
            if can_space_contain_any_item(s, remaining_items):
                pruned.append(s)
        else:
            pruned.append(s)

    # remove spaces fully contained inside another space
    final_spaces = []
    for i, a in enumerate(pruned):
        contained = False
        for j, b in enumerate(pruned):
            if i == j:
                continue
            if (
                a.x >= b.x and a.y >= b.y and a.z >= b.z and
                a.x + a.L <= b.x + b.L and
                a.y + a.W <= b.y + b.W and
                a.z + a.H <= b.z + b.H
            ):
                contained = True
                break
        if not contained:
            final_spaces.append(a)

    final_spaces.sort(key=lambda s: (s.z, s.x, s.y, s.volume))
    return final_spaces


# =========================================================
# PACKING HEURISTIC
# =========================================================

def choose_best_placement(
    spaces: List[Space],
    item: Dict
) -> Optional[Dict]:
    """
    Best-fit heuristic:
    - minimize leftover volume in selected free space
    - then prefer lower z, lower x, lower y
    """
    best = None

    for i, sp in enumerate(spaces):
        for rot in item["orientations"]:
            if sp.fits(rot):
                used_vol = rot[0] * rot[1] * rot[2]
                waste = sp.volume - used_vol

                score = (
                    waste,
                    sp.z,
                    sp.x,
                    sp.y,
                )

                if best is None or score < best["score"]:
                    best = {
                        "score": score,
                        "space_index": i,
                        "space": sp,
                        "rotation": rot,
                    }

    return best


def expand_items(
    products: List[Dict],
    *,
    respect_sequence: bool = True,
) -> List[Dict]:
    items = []
    item_index = 0

    for row_index, p in enumerate(products):
        dims = (p["length"], p["width"], p["height"])
        orientations = allowed_orientations(dims, p["r1"], p["r2"], p["r3"])

        for _ in range(p["qty"]):
            items.append({
                "product_name": p["name"],
                "dims": dims,
                "orientations": orientations,
                "weight": p["weight"],
                "stackable": bool(p.get("stackable", True)),
                "sequence": p["sequence"],
                "item_index": item_index,
                "row_index": row_index,
            })
            item_index += 1

    if respect_sequence:
        # Operational order: loading sequence first, then larger/heavier units.
        items.sort(
            key=lambda x: (
                x["sequence"],
                -(x["dims"][0] * x["dims"][1] * x["dims"][2]),
                -x["weight"],
                x["row_index"],
                x["item_index"],
            )
        )
    else:
        # Optional unrestricted order retained for diagnostic/internal callers.
        # Larger units are attempted first; stable row/item keys make results
        # deterministic when products have identical geometry.
        items.sort(
            key=lambda x: (
                -(x["dims"][0] * x["dims"][1] * x["dims"][2]),
                -max(x["dims"]),
                -x["weight"],
                x["row_index"],
                x["item_index"],
            )
        )
    return items


def _has_payload_limit(container: Dict) -> bool:
    try:
        return container.get("max_weight") is not None and float(container.get("max_weight")) > 0
    except Exception:
        return False


def _pack_container_greedy(
    container: Dict,
    products: List[Dict],
    *,
    respect_sequence: bool = True,
) -> Dict:
    """Item-by-item best-fit heuristic.

    Maximum Utilization calls this heuristic with sequence ordering enabled,
    while still allowing every residual cuboid to be reused by later products.
    Sequence Loading has its own dedicated accessibility-frontier engine.
    """
    items = expand_items(products, respect_sequence=respect_sequence)

    spaces = [Space(0, 0, 0, container["L"], container["W"], container["H"])]
    placements: List[Placement] = []
    unplaced: List[Dict] = []

    loaded_weight = 0.0
    payload_limit = float(container.get("max_weight")) if _has_payload_limit(container) else None
    previous_row_index: Optional[int] = None

    for idx, item in enumerate(items):
        # Maximum Utilization only: when processing moves to another product
        # row, remove computational boundaries left by all earlier rows.
        # Complete-face adjacent cuboids are one physically continuous free
        # region, so later products may cross those former split planes.
        # Running this once per product transition keeps the operation bounded
        # for large requests and naturally supports any number of products.
        if previous_row_index is not None and item["row_index"] != previous_row_index:
            spaces = _clean_residual_spaces(spaces)
            spaces = prune_spaces(spaces, items[idx:])
        previous_row_index = item["row_index"]
        if payload_limit is not None and loaded_weight + item["weight"] > payload_limit:
            unplaced.append({**item, "reason": "Container max payload exceeded"})
            continue

        best = choose_best_placement(spaces, item)
        if best is None:
            unplaced.append({**item, "reason": "No fitting free space"})
            continue

        sp = best["space"]
        rot = best["rotation"]
        i = best["space_index"]

        placements.append(
            Placement(
                product_name=item["product_name"],
                item_index=item["item_index"],
                row_index=item["row_index"],
                sequence=item["sequence"],
                weight=item["weight"],
                stackable=item["stackable"],
                x=sp.x,
                y=sp.y,
                z=sp.z,
                l=rot[0],
                w=rot[1],
                h=rot[2],
            )
        )
        loaded_weight += item["weight"]

        used_space = spaces.pop(i)
        spaces.extend(
            split_space(
                used_space,
                rot,
                support_stackable=item["stackable"],
            )
        )

        remaining_items = items[idx + 1:]
        spaces = prune_spaces(spaces, remaining_items)

    return {
        "placements": placements,
        "unplaced": unplaced,
        "spaces": spaces,
        "loaded_weight": loaded_weight,
        "strategy": "greedy",
    }


# =========================================================
# BOUNDED RESIDUAL / MIXED-ORIENTATION CANDIDATE
# =========================================================

_AXIS_ORDERS = tuple(permutations((0, 1, 2)))
# Main grid plus one bounded residual refill.  This is enough to evaluate the
# Euro-pallet 15 + 10 lane pattern while keeping automatic max-quantity checks
# responsive for small load units.
_RESIDUAL_SEARCH_DEPTH = 1
_EPS = 1e-9


def _space_dimensions(space: Space) -> Tuple[float, float, float]:
    return (space.L, space.W, space.H)


def _space_origin(space: Space) -> Tuple[float, float, float]:
    return (space.x, space.y, space.z)


def _max_grid_counts(space: Space, orientation: Tuple[float, float, float]) -> Tuple[int, int, int]:
    return tuple(
        max(0, int((available + _EPS) // required))
        for available, required in zip(_space_dimensions(space), orientation)
    )


def _grid_shape_candidates(
    max_counts: Tuple[int, int, int],
    qty_limit: int,
) -> List[Tuple[int, int, int]]:
    """Return a small deterministic set of useful rectangular grid blocks.

    The residual candidate deliberately remains bounded.  It tests the full
    regular grid plus six axis-priority ways of clipping that grid to the
    requested quantity.  Residual recursion can then use the remaining units.
    """
    if qty_limit <= 0 or any(value <= 0 for value in max_counts):
        return []

    candidates = set()
    full_capacity = math.prod(max_counts)
    if full_capacity <= qty_limit:
        candidates.add(tuple(max_counts))

    for order in _AXIS_ORDERS:
        counts = [1, 1, 1]
        for axis in order:
            current_product = math.prod(counts)
            counts[axis] = min(
                max_counts[axis],
                max(1, qty_limit // max(current_product, 1)),
            )
        while math.prod(counts) > qty_limit:
            reduced = False
            for axis in reversed(order):
                if counts[axis] > 1:
                    counts[axis] -= 1
                    reduced = True
                    break
            if not reduced:
                break
        if 0 < math.prod(counts) <= qty_limit:
            candidates.add(tuple(counts))

    # Include single-axis strips.  They are important for lane-style pallet
    # arrangements and also give the recursive residual search room to rotate.
    for axis in range(3):
        counts = [1, 1, 1]
        counts[axis] = min(max_counts[axis], qty_limit)
        if math.prod(counts) > 0:
            candidates.add(tuple(counts))

    return sorted(
        candidates,
        key=lambda counts: (
            -math.prod(counts),
            -(counts[0] * counts[1]),
            -counts[2],
            counts,
        ),
    )


def _materialize_grid(
    space: Space,
    orientation: Tuple[float, float, float],
    counts: Tuple[int, int, int],
) -> List[Tuple[float, float, float, float, float, float]]:
    l, w, h = orientation
    placements = []
    for iz in range(counts[2]):
        for iy in range(counts[1]):
            for ix in range(counts[0]):
                placements.append((
                    space.x + ix * l,
                    space.y + iy * w,
                    space.z + iz * h,
                    l,
                    w,
                    h,
                ))
    return placements


def _split_around_block(
    space: Space,
    used_dimensions: Tuple[float, float, float],
    axis_order: Tuple[int, int, int],
) -> List[Space]:
    """Partition ``space - occupied_block`` into three non-overlapping boxes."""
    origin = list(_space_origin(space))
    current = list(_space_dimensions(space))
    used = list(used_dimensions)
    residuals = []

    for axis in axis_order:
        remainder = current[axis] - used[axis]
        if remainder > _EPS:
            residual_origin = list(origin)
            residual_size = list(current)
            residual_origin[axis] += used[axis]
            residual_size[axis] = remainder
            residuals.append(
                Space(
                    x=residual_origin[0],
                    y=residual_origin[1],
                    z=residual_origin[2],
                    L=residual_size[0],
                    W=residual_size[1],
                    H=residual_size[2],
                )
            )
        current[axis] = used[axis]

    return residuals


def _orientation_capacity(space: Space, orientations: List[Tuple[float, float, float]]) -> int:
    best = 0
    for orientation in orientations:
        counts = _max_grid_counts(space, orientation)
        best = max(best, math.prod(counts))
    return best


def _minimum_stack_floor_area(
    space: Space,
    orientations: List[Tuple[float, float, float]],
    qty_limit: int,
) -> float:
    """Optimistic lower bound for the floor area needed by ``qty_limit``.

    Each floor position may use any allowed orientation and may be filled to
    the maximum number of vertical layers supported by the current space.  The
    bound intentionally ignores 2D adjacency constraints, so reaching it means
    the sequence-aware plan cannot improve its floor-stack area further.
    """
    if qty_limit <= 0:
        return 0.0

    stack_types = []
    for l, w, h in orientations:
        if l <= space.L + _EPS and w <= space.W + _EPS and h <= space.H + _EPS:
            layers = max(0, int((space.H + _EPS) // h))
            if layers > 0:
                stack_types.append((layers, l * w))
    if not stack_types:
        return math.inf

    best_area = [math.inf] * (qty_limit + 1)
    best_area[0] = 0.0
    for packed in range(qty_limit):
        if math.isinf(best_area[packed]):
            continue
        for layers, footprint_area in stack_types:
            next_packed = min(qty_limit, packed + layers)
            best_area[next_packed] = min(
                best_area[next_packed],
                best_area[packed] + footprint_area,
            )
    return best_area[qty_limit]


def _floor_projection_area(
    placements: List[Tuple[float, float, float, float, float, float]],
) -> float:
    """Measure the floor positions opened by a placement plan.

    Exact stacks with the same x/y footprint are counted once.  A different
    footprint is counted separately, even when it partially projects over an
    earlier footprint at another height.  That conservative treatment is
    useful here: it rewards simple complete stacks and avoids expensive union
    geometry during repeated automatic-quantity calculations.
    """
    footprints = {
        (
            round(x, 9),
            round(y, 9),
            round(l, 9),
            round(w, 9),
        )
        for x, y, z, l, w, h in placements
        if l > _EPS and w > _EPS
    }
    return sum(l * w for x, y, l, w in footprints)


def _plan_score(plan: ResidualPlan, sequence_aware: bool = False) -> Tuple:
    if not plan.placements:
        return (0, 0.0, 0.0, 0.0, 0.0)
    occupied_length = max(x + l for x, y, z, l, w, h in plan.placements)
    occupied_width = max(y + w for x, y, z, l, w, h in plan.placements)
    occupied_height = max(z + h for x, y, z, l, w, h in plan.placements)

    if sequence_aware:
        floor_area = _floor_projection_area(plan.placements)
        # Count remains authoritative.  For equal counts, use the smallest
        # floor projection first, then keep the block close to the back wall
        # (x=0) and prefer completed vertical stacks.
        return (
            plan.count,
            -floor_area,
            -occupied_length,
            occupied_height,
            -occupied_width,
        )

    # Count is authoritative.  Lower occupied height/width/length are stable
    # tie-breakers that leave compact residual regions for later load rows.
    return (
        plan.count,
        -occupied_height,
        -occupied_width,
        -occupied_length,
        0.0,
    )


def _plan_homogeneous_space(
    space: Space,
    orientations: List[Tuple[float, float, float]],
    qty_limit: int,
    depth: int,
    sequence_aware: bool = False,
    support_stackable: bool = True,
) -> ResidualPlan:
    """Plan one product in one free space using grids plus bounded residuals."""
    empty = ResidualPlan([], [space])
    if qty_limit <= 0 or not orientations:
        return empty

    best = empty
    best_score = _plan_score(best, sequence_aware)
    minimum_floor_area = (
        _minimum_stack_floor_area(space, orientations, qty_limit)
        if sequence_aware
        else math.inf
    )

    for orientation in orientations:
        max_counts = _max_grid_counts(space, orientation)
        if not support_stackable:
            max_counts = (max_counts[0], max_counts[1], min(max_counts[2], 1))
        for counts in _grid_shape_candidates(max_counts, qty_limit):
            main_count = math.prod(counts)
            if main_count <= 0:
                continue

            used_dimensions = tuple(
                orientation[axis] * counts[axis]
                for axis in range(3)
            )
            main_placements = _materialize_grid(space, orientation, counts)

            for axis_order in _AXIS_ORDERS:
                residuals = _split_around_block(space, used_dimensions, axis_order)
                if not support_stackable:
                    residuals = [
                        residual
                        for residual in residuals
                        if residual.z <= space.z + _EPS
                    ]
                placements = list(main_placements)
                final_spaces = []
                remaining_qty = qty_limit - main_count

                # Pack the residual with the greatest homogeneous capacity
                # first.  This is deterministic and preserves long pallet lanes.
                if sequence_aware:
                    # While packing one loading sequence, use vertical
                    # residuals before opening more floor positions.  This is
                    # the floor-to-top behaviour expected for transport loads.
                    residuals.sort(
                        key=lambda residual: (
                            0 if residual.z > space.z + _EPS else 1,
                            -_orientation_capacity(residual, orientations),
                            residual.x,
                            residual.y,
                            residual.z,
                        )
                    )
                else:
                    residuals.sort(
                        key=lambda residual: (
                            -_orientation_capacity(residual, orientations),
                            residual.z,
                            residual.x,
                            residual.y,
                        )
                    )

                for residual in residuals:
                    if remaining_qty > 0 and depth > 0:
                        child = _plan_homogeneous_space(
                            residual,
                            orientations,
                            remaining_qty,
                            depth - 1,
                            sequence_aware=sequence_aware,
                            support_stackable=support_stackable,
                        )
                        placements.extend(child.placements)
                        final_spaces.extend(child.spaces)
                        remaining_qty -= child.count
                    else:
                        final_spaces.append(residual)

                candidate = ResidualPlan(placements, final_spaces)
                candidate_score = _plan_score(candidate, sequence_aware)
                if candidate_score > best_score:
                    best = candidate
                    best_score = candidate_score

                # The original residual candidate keeps its fast early exit.
                # Sequence-aware planning must compare every full-quantity
                # candidate until the theoretical minimum stack footprint is
                # reached; at that point no further floor-space improvement is
                # possible.
                if not sequence_aware and best.count >= qty_limit:
                    return best
                if (
                    sequence_aware
                    and best.count >= qty_limit
                    and not math.isinf(minimum_floor_area)
                    and -best_score[1] <= minimum_floor_area + _EPS
                ):
                    return best

    return best


def _product_groups(
    products: List[Dict],
    *,
    respect_sequence: bool = True,
) -> List[Dict]:
    starts = []
    next_item_index = 0
    for product in products:
        starts.append(next_item_index)
        next_item_index += int(product.get("qty", 0) or 0)

    groups = []
    for row_index, product in enumerate(products):
        dims = (product["length"], product["width"], product["height"])
        groups.append({
            **product,
            "row_index": row_index,
            "item_index_start": starts[row_index],
            "dims": dims,
            "orientations": allowed_orientations(
                dims,
                product["r1"],
                product["r2"],
                product["r3"],
            ),
        })

    if respect_sequence:
        groups.sort(
            key=lambda group: (
                group["sequence"],
                -(group["dims"][0] * group["dims"][1] * group["dims"][2]),
                -group["weight"],
                group["row_index"],
            )
        )
    else:
        groups.sort(
            key=lambda group: (
                -(group["dims"][0] * group["dims"][1] * group["dims"][2]),
                -max(group["dims"]),
                -group["weight"],
                group["row_index"],
            )
        )
    return groups


def _same(a: float, b: float) -> bool:
    return abs(a - b) <= _EPS


def _merge_pair(a: Space, b: Space) -> Optional[Space]:
    """Merge two residual cuboids that share one complete face.

    The bounded residual planner partitions empty volume into non-overlapping
    rectangular spaces. When two spaces later become fully adjacent with the
    same cross-section, keeping the split would create an artificial boundary.
    Recombining only complete-face neighbours is geometrically safe.
    """
    # Adjacent along container length.
    if (
        _same(a.y, b.y)
        and _same(a.z, b.z)
        and _same(a.W, b.W)
        and _same(a.H, b.H)
    ):
        if _same(a.x + a.L, b.x) or _same(b.x + b.L, a.x):
            return Space(
                min(a.x, b.x), a.y, a.z,
                a.L + b.L, a.W, a.H,
            )

    # Adjacent across container width.
    if (
        _same(a.x, b.x)
        and _same(a.z, b.z)
        and _same(a.L, b.L)
        and _same(a.H, b.H)
    ):
        if _same(a.y + a.W, b.y) or _same(b.y + b.W, a.y):
            return Space(
                a.x, min(a.y, b.y), a.z,
                a.L, a.W + b.W, a.H,
            )

    # Adjacent vertically.
    if (
        _same(a.x, b.x)
        and _same(a.y, b.y)
        and _same(a.L, b.L)
        and _same(a.W, b.W)
    ):
        if _same(a.z + a.H, b.z) or _same(b.z + b.H, a.z):
            return Space(
                a.x, a.y, min(a.z, b.z),
                a.L, a.W, a.H + b.H,
            )

    return None


def _merge_adjacent_spaces(spaces: List[Space]) -> List[Space]:
    merged = list(spaces)
    changed = True
    while changed:
        changed = False
        for i, first in enumerate(merged):
            for j in range(i + 1, len(merged)):
                combined = _merge_pair(first, merged[j])
                if combined is None:
                    continue
                merged = [
                    space
                    for index, space in enumerate(merged)
                    if index not in (i, j)
                ]
                merged.append(combined)
                changed = True
                break
            if changed:
                break
    return merged


def _clean_residual_spaces(spaces: List[Space]) -> List[Space]:
    cleaned = [
        space for space in spaces
        if space.L > _EPS and space.W > _EPS and space.H > _EPS
    ]
    cleaned = _merge_adjacent_spaces(cleaned)

    unique_spaces = []
    seen = set()
    for space in cleaned:
        key = (
            round(space.x, 9), round(space.y, 9), round(space.z, 9),
            round(space.L, 9), round(space.W, 9), round(space.H, 9),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_spaces.append(space)
    cleaned = unique_spaces

    # Remove spaces fully contained in a genuinely larger residual.
    final_spaces = []
    for index, candidate in enumerate(cleaned):
        contained = False
        for other_index, other in enumerate(cleaned):
            if index == other_index:
                continue
            if (
                candidate.x >= other.x - _EPS
                and candidate.y >= other.y - _EPS
                and candidate.z >= other.z - _EPS
                and candidate.x + candidate.L <= other.x + other.L + _EPS
                and candidate.y + candidate.W <= other.y + other.W + _EPS
                and candidate.z + candidate.H <= other.z + other.H + _EPS
                and other.volume > candidate.volume + _EPS
            ):
                contained = True
                break
        if not contained:
            final_spaces.append(candidate)

    cleaned = final_spaces
    cleaned.sort(key=lambda space: (space.z, space.x, space.y, space.volume))
    return cleaned


def _maximum_sequence_plan_score(plan: ResidualPlan, space: Space) -> Tuple:
    """Score one Maximum Utilization block without creating a hard frontier.

    Quantity remains authoritative. For equal quantities, the block follows
    the same practical filling preference as Sequence Loading:

    * use the lowest horizontal layers first;
    * stay close to the closed back wall;
    * use the container width before advancing farther toward the doors.

    The score is local to ``space``. Residual spaces remain available to every
    later loading sequence, so this preference does not create an invisible
    boundary.
    """
    if not plan.placements:
        return (0, 0.0, 0.0, 0.0, 0)

    occupied_length = max(
        x + l for x, y, z, l, w, h in plan.placements
    ) - space.x
    occupied_width = max(
        y + w for x, y, z, l, w, h in plan.placements
    ) - space.y
    occupied_height = max(
        z + h for x, y, z, l, w, h in plan.placements
    ) - space.z

    return (
        plan.count,
        -occupied_height,
        -occupied_length,
        occupied_width,
        -len(plan.spaces),
    )


def _subtract_cuboid_from_space(
    space: Space,
    cuboid: Tuple[float, float, float, float, float, float],
) -> List[Space]:
    """Subtract one axis-aligned occupied cuboid from one free cuboid.

    The returned pieces are non-overlapping. This operation preserves the real
    geometric residuals around a sequence block without introducing a full-
    width loading frontier.
    """
    x, y, z, l, w, h = cuboid
    sx0, sy0, sz0 = space.x, space.y, space.z
    sx1, sy1, sz1 = sx0 + space.L, sy0 + space.W, sz0 + space.H
    bx0, by0, bz0 = x, y, z
    bx1, by1, bz1 = x + l, y + w, z + h

    ix0, iy0, iz0 = max(sx0, bx0), max(sy0, by0), max(sz0, bz0)
    ix1, iy1, iz1 = min(sx1, bx1), min(sy1, by1), min(sz1, bz1)
    if ix1 <= ix0 + _EPS or iy1 <= iy0 + _EPS or iz1 <= iz0 + _EPS:
        return [space]

    pieces: List[Space] = []

    # Full-height slabs before and after the occupied x interval.
    if ix0 > sx0 + _EPS:
        pieces.append(Space(sx0, sy0, sz0, ix0 - sx0, space.W, space.H))
    if sx1 > ix1 + _EPS:
        pieces.append(Space(ix1, sy0, sz0, sx1 - ix1, space.W, space.H))

    middle_length = ix1 - ix0

    # Full-height width slabs inside the occupied x interval.
    if iy0 > sy0 + _EPS:
        pieces.append(Space(ix0, sy0, sz0, middle_length, iy0 - sy0, space.H))
    if sy1 > iy1 + _EPS:
        pieces.append(Space(ix0, iy1, sz0, middle_length, sy1 - iy1, space.H))

    middle_width = iy1 - iy0

    # Bottom and top slabs inside the occupied x/y footprint.
    if iz0 > sz0 + _EPS:
        pieces.append(Space(ix0, iy0, sz0, middle_length, middle_width, iz0 - sz0))
    if sz1 > iz1 + _EPS:
        pieces.append(Space(ix0, iy0, iz1, middle_length, middle_width, sz1 - iz1))

    return pieces


def _subtract_cuboids_from_space(
    space: Space,
    cuboids: List[Tuple[float, float, float, float, float, float]],
) -> List[Space]:
    residuals = [space]
    for cuboid in cuboids:
        updated: List[Space] = []
        for residual in residuals:
            updated.extend(_subtract_cuboid_from_space(residual, cuboid))
        residuals = _clean_residual_spaces(updated)
    return residuals


def _plan_maximum_sequence_space(
    space: Space,
    orientations: List[Tuple[float, float, float]],
    qty_limit: int,
    depth: int,
    *,
    support_stackable: bool = True,
) -> ResidualPlan:
    """Build a sequence-style block while preserving unrestricted residuals.

    The block itself follows the operational pattern: width-first, back-to-
    front, and complete horizontal layers from bottom to top. Unlike Sequence
    Loading, the exact side, front and top residual cuboids are returned for
    later products instead of being clipped by an accessibility frontier.

    ``depth`` is retained in the signature for compatibility with the bounded
    residual caller; exact cuboid subtraction replaces recursive guillotine
    splitting for this planner.
    """
    empty = ResidualPlan([], [space])
    if qty_limit <= 0 or not orientations:
        return empty

    local_floor = [Space(0.0, 0.0, 0.0, space.L, space.W, space.H)]
    local_plan = _sequence_group_plan(
        local_floor,
        orientations,
        qty_limit,
        space.H,
        support_stackable=support_stackable,
    )
    if local_plan is None or local_plan["packed_qty"] <= 0:
        return empty

    placements = [
        (
            space.x + x,
            space.y + y,
            space.z + z,
            l,
            w,
            h,
        )
        for x, y, z, l, w, h in local_plan["placements"]
    ]
    placements.sort(
        key=lambda placement: (
            placement[2],
            placement[0],
            placement[1],
            placement[3],
            placement[4],
        )
    )

    residuals = _subtract_cuboids_from_space(space, placements)
    if not support_stackable:
        residuals = [
            residual
            for residual in residuals
            if residual.z <= space.z + _EPS
        ]
    return ResidualPlan(placements, residuals)


def _pack_container_residual(container: Dict, products: List[Dict]) -> Dict:
    """Sequence-respecting, gap-first Maximum Utilization candidate.

    Product rows are completed in loading-sequence order.  For each new
    sequence, the engine first reopens every geometrically valid residual that
    lies inside the length already occupied by earlier products.  Only after
    those inter-product gaps can no longer accept the current product does the
    engine expand the load farther toward the doors.

    This is intentionally different from Sequence Loading: no operational
    frontier is frozen.  Side, top, boundary and deep residuals remain
    available to later sequences, while the primary block construction still
    prefers the floor, the closed back wall and complete horizontal layers.
    """
    groups = _product_groups(products, respect_sequence=True)
    spaces = [Space(0, 0, 0, container["L"], container["W"], container["H"])]
    placements: List[Placement] = []
    loaded_weight = 0.0
    payload_limit = (
        float(container.get("max_weight"))
        if _has_payload_limit(container)
        else None
    )

    state = {
        group["row_index"]: {
            "group": group,
            "requested": int(group.get("qty", 0) or 0),
            "remaining": int(group.get("qty", 0) or 0),
            "packed": 0,
        }
        for group in groups
    }

    for group in groups:
        entry = state[group["row_index"]]

        # This is the occupied-length envelope created by all earlier loading
        # sequences.  Spaces that begin before this plane are real residual
        # gaps between/around earlier product blocks, not operational walls.
        previous_sequence_frontier = max(
            (placement.x + placement.l for placement in placements),
            default=0.0,
        )

        while spaces and entry["remaining"] > 0:
            remaining_payload = (
                math.inf
                if payload_limit is None
                else max(payload_limit - loaded_weight, 0.0)
            )

            remaining_qty = entry["remaining"]
            if payload_limit is not None and group["weight"] > 0:
                payload_capacity = int((remaining_payload + _EPS) // group["weight"])
                qty_limit = min(remaining_qty, payload_capacity)
            else:
                qty_limit = remaining_qty
            if qty_limit <= 0:
                break

            candidates = []
            for space_index, space in enumerate(spaces):
                if _orientation_capacity(space, group["orientations"]) <= 0:
                    continue

                plan = _plan_maximum_sequence_space(
                    space,
                    group["orientations"],
                    qty_limit,
                    _RESIDUAL_SEARCH_DEPTH,
                    support_stackable=bool(group.get("stackable", True)),
                )
                if plan.count <= 0:
                    continue

                local_score = _maximum_sequence_plan_score(plan, space)
                is_existing_gap = (
                    previous_sequence_frontier > _EPS
                    and space.x < previous_sequence_frontier - _EPS
                )

                if is_existing_gap:
                    # Fill the constrained residual nearest the previous
                    # sequence boundary before opening clean floor space in
                    # front.  A partial placement is deliberately accepted:
                    # the remainder of this product can be packed in later
                    # spaces during subsequent iterations.
                    gap_end = min(space.x + space.L, previous_sequence_frontier)
                    choice_score = (
                        1,                   # existing gaps outrank expansion
                        gap_end,             # close the transition boundary
                        space.x,             # prefer the most forward gap
                        -space.z,            # then lower supported positions
                        -space.volume,       # consume constrained gaps first
                        plan.count,
                        *local_score[1:],
                    )
                else:
                    choice_score = (
                        0,
                        plan.count,
                        -space.z,
                        -space.x,
                        -space.y,
                        *local_score[1:],
                        -space.volume,
                    )

                candidates.append({
                    "score": choice_score,
                    "space_index": space_index,
                    "group": group,
                    "plan": plan,
                    "is_existing_gap": is_existing_gap,
                })

            if not candidates:
                break

            # If at least one residual inside the previous occupied envelope
            # fits, restrict this iteration to those spaces.  This prevents a
            # large clean space in front from winning merely because it can
            # hold the complete remaining quantity in one block.
            gap_candidates = [
                candidate for candidate in candidates
                if candidate["is_existing_gap"]
            ]
            candidate_pool = gap_candidates or candidates
            best_choice = max(candidate_pool, key=lambda candidate: candidate["score"])
            plan = best_choice["plan"]

            spaces.pop(best_choice["space_index"])
            spaces.extend(plan.spaces)
            spaces = _clean_residual_spaces(spaces)

            packed_before = entry["packed"]
            ordered_placements = sorted(
                plan.placements,
                key=lambda placement: (
                    placement[2],  # complete the lower layer first
                    placement[0],  # then move from back toward the doors
                    placement[1],  # and fill across the width at each x
                    placement[3],
                    placement[4],
                ),
            )
            for placement_offset, (x, y, z, l, w, h) in enumerate(ordered_placements):
                placements.append(
                    Placement(
                        product_name=group["name"],
                        item_index=group["item_index_start"] + packed_before + placement_offset,
                        row_index=group["row_index"],
                        sequence=group["sequence"],
                        weight=group["weight"],
                        stackable=bool(group.get("stackable", True)),
                        x=x,
                        y=y,
                        z=z,
                        l=l,
                        w=w,
                        h=h,
                    )
                )
                loaded_weight += group["weight"]

            entry["packed"] += plan.count
            entry["remaining"] -= plan.count

            remaining_templates = [
                {"orientations": candidate["group"]["orientations"]}
                for candidate in state.values()
                if candidate["remaining"] > 0
            ]
            if remaining_templates:
                spaces = prune_spaces(spaces, remaining_templates)
                spaces = _clean_residual_spaces(spaces)

    unplaced: List[Dict] = []
    for group in groups:
        entry = state[group["row_index"]]
        packed = entry["packed"]
        remaining = entry["remaining"]
        for offset in range(remaining):
            payload_blocked = (
                payload_limit is not None
                and group["weight"] > 0
                and loaded_weight + group["weight"] > payload_limit + _EPS
            )
            unplaced.append({
                "product_name": group["name"],
                "dims": group["dims"],
                "orientations": group["orientations"],
                "weight": group["weight"],
                "sequence": group["sequence"],
                "item_index": group["item_index_start"] + packed + offset,
                "row_index": group["row_index"],
                "reason": (
                    "Container max payload exceeded"
                    if payload_blocked
                    else "No fitting free space"
                ),
            })

    return {
        "placements": placements,
        "unplaced": unplaced,
        "spaces": spaces,
        "loaded_weight": loaded_weight,
        "strategy": "residual_sequence_maximum",
    }

def _layer_plan_score(plan: ResidualPlan, origin_x: float) -> Tuple:
    """Score one horizontal floor layer for strict sequence loading.

    Quantity is authoritative.  For equal quantities, prefer the shortest
    back-to-front zone, then use more of the container width.  Unlike the
    maximum-utilization heuristic, this score does not reward vertical
    residuals because a sequence layer is deliberately two-dimensional.
    """
    if not plan.placements:
        return (0, 0.0, 0.0, 0)

    occupied_length = max(
        x + l for x, y, z, l, w, h in plan.placements
    ) - origin_x
    occupied_width = max(y + w for x, y, z, l, w, h in plan.placements)
    return (
        plan.count,
        -occupied_length,
        occupied_width,
        -len(plan.spaces),
    )


def _plan_floor_layer(
    space: Space,
    orientations: List[Tuple[float, float, float]],
    qty_limit: int,
    depth: int,
) -> ResidualPlan:
    """Build one bounded horizontal layer inside ``space``.

    All supplied orientations must have the same vertical height.  The layer
    may mix the corresponding 90-degree floor rotations, but it never creates
    placements above the layer.  The objective is to place the requested floor
    positions using the shortest possible container length.
    """
    empty = ResidualPlan([], [space])
    if qty_limit <= 0 or not orientations:
        return empty

    best = empty
    best_score = _layer_plan_score(best, space.x)

    for orientation in orientations:
        if not space.fits(orientation):
            continue

        max_counts = _max_grid_counts(space, orientation)
        for counts in _grid_shape_candidates(max_counts, qty_limit):
            main_count = math.prod(counts)
            if main_count <= 0:
                continue

            used_dimensions = tuple(
                orientation[axis] * counts[axis]
                for axis in range(3)
            )
            main_placements = _materialize_grid(space, orientation, counts)

            for axis_order in _AXIS_ORDERS:
                residuals = _split_around_block(space, used_dimensions, axis_order)
                # The sequence layer is strictly horizontal.  A top residual
                # is intentionally ignored and will be generated later by
                # repeating the completed floor pattern at the next z level.
                residuals = [
                    residual for residual in residuals
                    if abs(residual.z - space.z) <= _EPS
                    and residual.H + _EPS >= orientation[2]
                ]

                placements = list(main_placements)
                final_spaces = []
                remaining_qty = qty_limit - main_count

                residuals.sort(
                    key=lambda residual: (
                        -_orientation_capacity(residual, orientations),
                        residual.x,
                        residual.y,
                        residual.volume,
                    )
                )

                for residual in residuals:
                    if remaining_qty > 0 and depth > 0:
                        child = _plan_floor_layer(
                            residual,
                            orientations,
                            remaining_qty,
                            depth - 1,
                        )
                        placements.extend(child.placements)
                        final_spaces.extend(child.spaces)
                        remaining_qty -= child.count
                    else:
                        final_spaces.append(residual)

                candidate = ResidualPlan(placements, final_spaces)
                candidate_score = _layer_plan_score(candidate, space.x)
                if candidate_score > best_score:
                    best = candidate
                    best_score = candidate_score

    return best


def _lane_compositions(
    container_width: float,
    orientations: List[Tuple[float, float, float]],
) -> List[Tuple[int, ...]]:
    """Return a bounded set of full-width lane combinations.

    For a fixed number of lanes of the first orientation, using the maximum
    feasible number of lanes of the second orientation dominates using fewer:
    an extra lane may simply remain empty.  This keeps the two-orientation
    search linear instead of quadratic.
    """
    if not orientations:
        return []
    if len(orientations) == 1:
        width = orientations[0][1]
        lanes = int((container_width + _EPS) // width) if width > _EPS else 0
        return [(lanes,)] if lanes > 0 else []

    # A vertical-orientation group normally contains the two 90-degree floor
    # rotations.  Additional duplicates are already removed upstream.
    first, second = orientations[:2]
    max_first = int((container_width + _EPS) // first[1]) if first[1] > _EPS else 0

    # Very small products can imply thousands of lane counts.  In that case
    # the regular-grid/residual planner is already strong, so sample a bounded
    # set of lane mixes rather than expanding an unnecessarily large search.
    if max_first <= 200:
        first_counts = range(max_first + 1)
    else:
        first_counts = sorted({
            0,
            max_first,
            *(
                int(round(max_first * index / 64))
                for index in range(65)
            ),
        })

    compositions = set()
    for first_count in first_counts:
        remaining_width = container_width - first_count * first[1]
        if remaining_width < -_EPS:
            continue
        second_count = (
            int((remaining_width + _EPS) // second[1])
            if second[1] > _EPS
            else 0
        )
        if first_count + second_count > 0:
            compositions.add((first_count, second_count))

    return sorted(
        compositions,
        key=lambda counts: (
            -sum(counts),
            -sum(
                counts[index] * orientations[index][1]
                for index in range(len(counts))
            ),
            counts,
        ),
    )


def _plan_lane_layer(
    space: Space,
    orientations: List[Tuple[float, float, float]],
    qty_limit: int,
) -> ResidualPlan:
    """Build a practical width-lane pattern with minimum occupied length.

    Each lane runs from the back wall toward the doors.  Items in a lane share
    one floor orientation.  A heap assigns each next item to the lane whose
    next completion point is closest to the back, which minimizes the required
    zone length for that fixed lane composition.
    """
    empty = ResidualPlan([], [space])
    if qty_limit <= 0 or not orientations:
        return empty

    useful_orientations = [
        orientation for orientation in orientations
        if orientation[0] <= space.L + _EPS
        and orientation[1] <= space.W + _EPS
        and orientation[2] <= space.H + _EPS
    ]
    if not useful_orientations:
        return empty

    # Sequence orientation groups should contain at most two floor rotations.
    useful_orientations = useful_orientations[:2]
    best = empty
    best_score = _layer_plan_score(best, space.x)

    for composition in _lane_compositions(space.W, useful_orientations):
        lanes = []
        y_cursor = space.y
        for orientation_index, lane_count in enumerate(composition):
            l, w, h = useful_orientations[orientation_index]
            capacity = int((space.L + _EPS) // l)
            for _ in range(lane_count):
                if y_cursor + w > space.y + space.W + _EPS:
                    break
                lanes.append({
                    "orientation": (l, w, h),
                    "y": y_cursor,
                    "capacity": capacity,
                    "count": 0,
                })
                y_cursor += w

        total_capacity = sum(lane["capacity"] for lane in lanes)
        target = min(qty_limit, total_capacity)
        if target <= 0:
            continue

        heap = []
        for lane_index, lane in enumerate(lanes):
            if lane["capacity"] > 0:
                l = lane["orientation"][0]
                heapq.heappush(heap, (l, lane_index))

        assigned = 0
        while heap and assigned < target:
            _completion, lane_index = heapq.heappop(heap)
            lane = lanes[lane_index]
            lane["count"] += 1
            assigned += 1
            if lane["count"] < lane["capacity"]:
                next_completion = (lane["count"] + 1) * lane["orientation"][0]
                heapq.heappush(heap, (next_completion, lane_index))

        placements = []
        for lane in lanes:
            l, w, h = lane["orientation"]
            for position in range(lane["count"]):
                placements.append((
                    space.x + position * l,
                    lane["y"],
                    space.z,
                    l,
                    w,
                    h,
                ))

        candidate = ResidualPlan(placements, [])
        candidate_score = _layer_plan_score(candidate, space.x)
        if candidate_score > best_score:
            best = candidate
            best_score = candidate_score

    return best


def _best_sequence_floor_layer(
    space: Space,
    orientations: List[Tuple[float, float, float]],
    qty_limit: int,
) -> ResidualPlan:
    """Compare compact lane-building with bounded residual layer-building."""
    residual_plan = _plan_floor_layer(
        space,
        orientations,
        qty_limit,
        _RESIDUAL_SEARCH_DEPTH,
    )
    lane_plan = _plan_lane_layer(space, orientations, qty_limit)

    if _layer_plan_score(lane_plan, space.x) > _layer_plan_score(residual_plan, space.x):
        return lane_plan
    return residual_plan


def _orientations_by_vertical_height(
    orientations: List[Tuple[float, float, float]],
) -> List[List[Tuple[float, float, float]]]:
    """Group floor rotations that share the same vertical dimension."""
    grouped: Dict[float, List[Tuple[float, float, float]]] = {}
    order: List[float] = []

    for orientation in orientations:
        key = round(orientation[2], 9)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(orientation)

    return [grouped[key] for key in order]


_WIDTH_LOW_TO_HIGH = "low_to_high"
_WIDTH_HIGH_TO_LOW = "high_to_low"


def _normalize_width_direction(direction: Optional[str]) -> str:
    """Normalize the width search direction used by sequence-only engines."""
    value = str(direction or "").strip().lower().replace("-", "_")
    if value in {
        "high",
        "high_to_low",
        "right_to_left",
        "reverse",
        "descending",
    }:
        return _WIDTH_HIGH_TO_LOW
    return _WIDTH_LOW_TO_HIGH


def _floor_space_sort_key(space: Space) -> Tuple:
    """Back-to-front ordering for operational floor spaces."""
    return (space.x, space.y, space.L * space.W, space.W)



def _floor_space_sort_key_directional(
    space: Space,
    width_direction: str,
) -> Tuple:
    """Back-to-front ordering with a selectable side-to-side preference."""
    direction = _normalize_width_direction(width_direction)
    y_key = -space.y if direction == _WIDTH_HIGH_TO_LOW else space.y
    return (space.x, y_key, space.L * space.W, space.W)

def _mirror_residual_plan_across_width(
    plan: ResidualPlan,
    space: Space,
) -> ResidualPlan:
    """Mirror one local layer plan inside ``space`` across its width axis."""
    def mirror_y(y: float, width: float) -> float:
        return space.y + space.W - (y - space.y) - width

    placements = [
        (x, mirror_y(y, w), z, l, w, h)
        for x, y, z, l, w, h in plan.placements
    ]
    residuals = [
        Space(
            x=residual.x,
            y=mirror_y(residual.y, residual.W),
            z=residual.z,
            L=residual.L,
            W=residual.W,
            H=residual.H,
        )
        for residual in plan.spaces
    ]
    return ResidualPlan(placements, residuals)


def _best_sequence_floor_layer_directional(
    space: Space,
    orientations: List[Tuple[float, float, float]],
    qty_limit: int,
    width_direction: str,
) -> ResidualPlan:
    """Run the existing layer planner, optionally mirrored across width."""
    plan = _best_sequence_floor_layer(space, orientations, qty_limit)
    if _normalize_width_direction(width_direction) == _WIDTH_HIGH_TO_LOW:
        return _mirror_residual_plan_across_width(plan, space)
    return plan


def _prune_floor_spaces(spaces: List[Space]) -> List[Space]:
    """Keep a deterministic, non-contained set of positive floor rectangles."""
    cleaned = [
        Space(space.x, space.y, 0.0, space.L, space.W, space.H)
        for space in spaces
        if space.L > _EPS and space.W > _EPS and space.H > _EPS
    ]

    result = []
    for index, candidate in enumerate(cleaned):
        contained = False
        for other_index, other in enumerate(cleaned):
            if index == other_index:
                continue
            if (
                candidate.x >= other.x - _EPS
                and candidate.y >= other.y - _EPS
                and candidate.x + candidate.L <= other.x + other.L + _EPS
                and candidate.y + candidate.W <= other.y + other.W + _EPS
            ):
                contained = True
                break
        if not contained:
            result.append(candidate)

    # Merge exactly adjacent rectangles when their other span is identical.
    # This controls fragmentation without joining spaces across occupied cargo.
    changed = True
    while changed:
        changed = False
        merged = []
        used = [False] * len(result)
        for i, first in enumerate(result):
            if used[i]:
                continue
            current = first
            for j in range(i + 1, len(result)):
                if used[j]:
                    continue
                second = result[j]
                same_y_span = (
                    abs(current.y - second.y) <= _EPS
                    and abs(current.W - second.W) <= _EPS
                    and abs(current.H - second.H) <= _EPS
                )
                same_x_span = (
                    abs(current.x - second.x) <= _EPS
                    and abs(current.L - second.L) <= _EPS
                    and abs(current.H - second.H) <= _EPS
                )
                if same_y_span and (
                    abs(current.x + current.L - second.x) <= _EPS
                    or abs(second.x + second.L - current.x) <= _EPS
                ):
                    x0 = min(current.x, second.x)
                    x1 = max(current.x + current.L, second.x + second.L)
                    current = Space(x0, current.y, 0.0, x1 - x0, current.W, current.H)
                    used[j] = True
                    changed = True
                elif same_x_span and (
                    abs(current.y + current.W - second.y) <= _EPS
                    or abs(second.y + second.W - current.y) <= _EPS
                ):
                    y0 = min(current.y, second.y)
                    y1 = max(current.y + current.W, second.y + second.W)
                    current = Space(current.x, y0, 0.0, current.L, y1 - y0, current.H)
                    used[j] = True
                    changed = True
            used[i] = True
            merged.append(current)
        result = merged

    result.sort(key=_floor_space_sort_key)
    return result


def _subtract_floor_footprint(
    space: Space,
    footprint: Tuple[float, float, float, float],
) -> List[Space]:
    """Subtract one floor rectangle from a free floor rectangle.

    The four returned rectangles are non-overlapping: back and front strips use
    the full width, while the two side strips are limited to the footprint's x
    interval.
    """
    fx, fy, fl, fw = footprint
    sx0, sy0 = space.x, space.y
    sx1, sy1 = space.x + space.L, space.y + space.W
    fx0, fy0 = fx, fy
    fx1, fy1 = fx + fl, fy + fw

    ix0 = max(sx0, fx0)
    iy0 = max(sy0, fy0)
    ix1 = min(sx1, fx1)
    iy1 = min(sy1, fy1)
    if ix1 <= ix0 + _EPS or iy1 <= iy0 + _EPS:
        return [space]

    pieces = []
    if ix0 > sx0 + _EPS:
        pieces.append(Space(sx0, sy0, 0.0, ix0 - sx0, space.W, space.H))
    if sx1 > ix1 + _EPS:
        pieces.append(Space(ix1, sy0, 0.0, sx1 - ix1, space.W, space.H))
    if iy0 > sy0 + _EPS:
        pieces.append(Space(ix0, sy0, 0.0, ix1 - ix0, iy0 - sy0, space.H))
    if sy1 > iy1 + _EPS:
        pieces.append(Space(ix0, iy1, 0.0, ix1 - ix0, sy1 - iy1, space.H))
    return pieces


def _subtract_floor_footprints(
    spaces: List[Space],
    footprints: List[Tuple[float, float, float, float]],
) -> List[Space]:
    remaining = list(spaces)
    for footprint in footprints:
        updated = []
        for space in remaining:
            updated.extend(_subtract_floor_footprint(space, footprint))
        remaining = _prune_floor_spaces(updated)
    return remaining


def _y_intervals_overlap(
    y1: float,
    w1: float,
    y2: float,
    w2: float,
) -> bool:
    return y1 < y2 + w2 - _EPS and y1 + w1 > y2 + _EPS


def _accessible_sequence_floor_spaces(
    spaces: List[Space],
    occupied_floor_footprints: List[Tuple[float, float, float, float]],
    band_start: float,
    container_length: float,
) -> List[Space]:
    """Keep only floor space accessible from the door side.

    ``band_start`` freezes all complete rows behind the current product's final
    floor band.  Inside and in front of that band, a free rectangle is clipped
    to the furthest cargo edge that overlaps its width span.  This permits the
    next loading sequence to use forward-facing gaps in the final partial band,
    while rejecting deep side pockets behind earlier cargo.
    """
    accessible = []
    for space in spaces:
        start_x = max(space.x, band_start)
        end_x = min(space.x + space.L, container_length)
        if end_x <= start_x + _EPS:
            continue

        blocking_end = band_start
        for fx, fy, fl, fw in occupied_floor_footprints:
            if _y_intervals_overlap(space.y, space.W, fy, fw):
                blocking_end = max(blocking_end, fx + fl)

        start_x = max(start_x, blocking_end)
        if end_x <= start_x + _EPS:
            continue
        accessible.append(
            Space(
                x=start_x,
                y=space.y,
                z=0.0,
                L=end_x - start_x,
                W=space.W,
                H=space.H,
            )
        )

    return _prune_floor_spaces(accessible)


def _sequence_group_plan(
    floor_spaces: List[Space],
    orientations: List[Tuple[float, float, float]],
    qty_limit: int,
    container_height: float,
    *,
    support_stackable: bool = True,
) -> Optional[Dict]:
    """Plan one product on accessible floor rectangles, then build layers.

    Floor positions are selected from back to front.  After the minimum number
    of practical floor positions has been chosen, every bottom-layer position
    is placed before the engine starts the next horizontal layer.
    """
    if qty_limit <= 0 or not orientations or not floor_spaces:
        return None

    best = None
    ordered_spaces = sorted(floor_spaces, key=_floor_space_sort_key)

    for height_orientations in _orientations_by_vertical_height(orientations):
        item_height = height_orientations[0][2]
        if item_height <= _EPS or item_height > container_height + _EPS:
            continue

        max_layers = max(0, int((container_height + _EPS) // item_height))
        if not support_stackable:
            max_layers = min(max_layers, 1)
        if max_layers <= 0:
            continue

        required_floor_positions = int(math.ceil(qty_limit / max_layers))
        remaining_positions = required_floor_positions
        base_positions = []

        for floor_space in ordered_spaces:
            if remaining_positions <= 0:
                break
            layer_space = Space(
                x=floor_space.x,
                y=floor_space.y,
                z=0.0,
                L=floor_space.L,
                W=floor_space.W,
                H=item_height,
            )
            plan = _best_sequence_floor_layer(
                layer_space,
                height_orientations,
                remaining_positions,
            )
            if plan.count <= 0:
                continue
            base_positions.extend(plan.placements)
            remaining_positions -= plan.count

        base_positions = sorted(
            base_positions,
            key=lambda placement: (
                placement[0],
                placement[1],
                placement[3],
                placement[4],
            ),
        )
        if not base_positions:
            continue

        packed_qty = min(qty_limit, len(base_positions) * max_layers)
        placements = []
        remaining_qty = packed_qty
        layer_index = 0
        while remaining_qty > 0 and layer_index < max_layers:
            count_in_layer = min(len(base_positions), remaining_qty)
            for x, y, _z, l, w, h in base_positions[:count_in_layer]:
                placements.append((
                    x,
                    y,
                    layer_index * item_height,
                    l,
                    w,
                    h,
                ))
            remaining_qty -= count_in_layer
            layer_index += 1

        zone_end = max(x + l for x, y, z, l, w, h in base_positions)
        footprint_area = sum(l * w for x, y, z, l, w, h in base_positions)
        top_layer_count = packed_qty % len(base_positions) or len(base_positions)
        candidate = {
            "placements": placements,
            "base_positions": base_positions,
            "packed_qty": packed_qty,
            "floor_positions": len(base_positions),
            "layers_used": layer_index,
            "top_layer_count": top_layer_count,
            "zone_end": zone_end,
            "item_height": item_height,
        }
        candidate_score = (
            packed_qty,
            -footprint_area,
            -zone_end,
            -len(base_positions),
            top_layer_count,
        )
        if best is None or candidate_score > best["score"]:
            candidate["score"] = candidate_score
            best = candidate

    return best



def _sequence_group_plan_directional(
    floor_spaces: List[Space],
    orientations: List[Tuple[float, float, float]],
    qty_limit: int,
    container_height: float,
    width_direction: str = _WIDTH_LOW_TO_HIGH,
    *,
    support_stackable: bool = True,
) -> Optional[Dict]:
    """Plan one product on accessible floor rectangles, then build layers.

    Floor positions are selected from back to front.  After the minimum number
    of practical floor positions has been chosen, every bottom-layer position
    is placed before the engine starts the next horizontal layer.
    """
    if qty_limit <= 0 or not orientations or not floor_spaces:
        return None

    best = None
    direction = _normalize_width_direction(width_direction)
    ordered_spaces = sorted(
        floor_spaces,
        key=lambda space: _floor_space_sort_key_directional(space, direction),
    )

    for height_orientations in _orientations_by_vertical_height(orientations):
        item_height = height_orientations[0][2]
        if item_height <= _EPS or item_height > container_height + _EPS:
            continue

        max_layers = max(0, int((container_height + _EPS) // item_height))
        if not support_stackable:
            max_layers = min(max_layers, 1)
        if max_layers <= 0:
            continue

        required_floor_positions = int(math.ceil(qty_limit / max_layers))
        remaining_positions = required_floor_positions
        base_positions = []

        for floor_space in ordered_spaces:
            if remaining_positions <= 0:
                break
            layer_space = Space(
                x=floor_space.x,
                y=floor_space.y,
                z=0.0,
                L=floor_space.L,
                W=floor_space.W,
                H=item_height,
            )
            plan = _best_sequence_floor_layer_directional(
                layer_space,
                height_orientations,
                remaining_positions,
                direction,
            )
            if plan.count <= 0:
                continue
            base_positions.extend(plan.placements)
            remaining_positions -= plan.count

        base_positions = sorted(
            base_positions,
            key=lambda placement: (
                placement[0],
                (
                    -placement[1]
                    if direction == _WIDTH_HIGH_TO_LOW
                    else placement[1]
                ),
                placement[3],
                placement[4],
            ),
        )
        if not base_positions:
            continue

        packed_qty = min(qty_limit, len(base_positions) * max_layers)
        placements = []
        remaining_qty = packed_qty
        layer_index = 0
        while remaining_qty > 0 and layer_index < max_layers:
            count_in_layer = min(len(base_positions), remaining_qty)
            for x, y, _z, l, w, h in base_positions[:count_in_layer]:
                placements.append((
                    x,
                    y,
                    layer_index * item_height,
                    l,
                    w,
                    h,
                ))
            remaining_qty -= count_in_layer
            layer_index += 1

        zone_end = max(x + l for x, y, z, l, w, h in base_positions)
        footprint_area = sum(l * w for x, y, z, l, w, h in base_positions)
        top_layer_count = packed_qty % len(base_positions) or len(base_positions)
        candidate = {
            "placements": placements,
            "base_positions": base_positions,
            "packed_qty": packed_qty,
            "floor_positions": len(base_positions),
            "layers_used": layer_index,
            "top_layer_count": top_layer_count,
            "zone_end": zone_end,
            "item_height": item_height,
            "width_direction": direction,
        }
        candidate_score = (
            packed_qty,
            -footprint_area,
            -zone_end,
            -len(base_positions),
            top_layer_count,
        )
        if best is None or candidate_score > best["score"]:
            candidate["score"] = candidate_score
            best = candidate

    return best




def _subtract_rect_2d(
    rectangle: Tuple[float, float, float, float],
    blocker: Tuple[float, float, float, float],
) -> List[Tuple[float, float, float, float]]:
    """Subtract one axis-aligned 2D rectangle from another.

    Coordinates are generic ``(axis_1, axis_2, size_1, size_2)`` values.  The
    returned rectangles are non-overlapping and preserve the portions that do
    not intersect ``blocker``.
    """
    a0, b0, da, db = rectangle
    c0, d0, dc, dd = blocker
    a1, b1 = a0 + da, b0 + db
    c1, d1 = c0 + dc, d0 + dd

    ia0, ib0 = max(a0, c0), max(b0, d0)
    ia1, ib1 = min(a1, c1), min(b1, d1)
    if ia1 <= ia0 + _EPS or ib1 <= ib0 + _EPS:
        return [rectangle]

    pieces: List[Tuple[float, float, float, float]] = []
    if ia0 > a0 + _EPS:
        pieces.append((a0, b0, ia0 - a0, db))
    if a1 > ia1 + _EPS:
        pieces.append((ia1, b0, a1 - ia1, db))

    middle_size = ia1 - ia0
    if ib0 > b0 + _EPS:
        pieces.append((ia0, b0, middle_size, ib0 - b0))
    if b1 > ib1 + _EPS:
        pieces.append((ia0, ib1, middle_size, b1 - ib1))
    return pieces


def _space_base_is_supported(
    space: Space,
    placements: List[Placement],
) -> bool:
    """Return whether the whole x/y base of ``space`` has physical support."""
    if space.z <= _EPS:
        return True

    unsupported = [(space.x, space.y, space.L, space.W)]
    for placement in placements:
        if abs(placement.z + placement.h - space.z) > _EPS:
            continue
        if not placement.stackable:
            continue
        support = (placement.x, placement.y, placement.l, placement.w)
        updated: List[Tuple[float, float, float, float]] = []
        for rectangle in unsupported:
            updated.extend(_subtract_rect_2d(rectangle, support))
        unsupported = [
            rectangle
            for rectangle in updated
            if rectangle[2] > _EPS and rectangle[3] > _EPS
        ]
        if not unsupported:
            return True
    return False




def _positive_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    """Length of the positive overlap between two one-dimensional intervals."""
    return max(0.0, min(a1, b1) - max(a0, b0))


def _placements_overlap(first: Placement, second: Placement) -> bool:
    """Return True only for a positive-volume cuboid overlap."""
    return (
        _positive_overlap(first.x, first.x + first.l, second.x, second.x + second.l) > _EPS
        and _positive_overlap(first.y, first.y + first.w, second.y, second.y + second.w) > _EPS
        and _positive_overlap(first.z, first.z + first.h, second.z, second.z + second.h) > _EPS
    )


def _placements_face_connected(first: Placement, second: Placement) -> bool:
    """Return whether two placements share a positive-area face.

    The relation is used only to form same-product rigid components. Edge and
    point contact do not connect components because they do not create a
    mechanically meaningful block for this compaction pass.
    """
    x_touch = (
        abs(first.x + first.l - second.x) <= _EPS
        or abs(second.x + second.l - first.x) <= _EPS
    )
    if x_touch:
        return (
            _positive_overlap(first.y, first.y + first.w, second.y, second.y + second.w) > _EPS
            and _positive_overlap(first.z, first.z + first.h, second.z, second.z + second.h) > _EPS
        )

    y_touch = (
        abs(first.y + first.w - second.y) <= _EPS
        or abs(second.y + second.w - first.y) <= _EPS
    )
    if y_touch:
        return (
            _positive_overlap(first.x, first.x + first.l, second.x, second.x + second.l) > _EPS
            and _positive_overlap(first.z, first.z + first.h, second.z, second.z + second.h) > _EPS
        )

    z_touch = (
        abs(first.z + first.h - second.z) <= _EPS
        or abs(second.z + second.h - first.z) <= _EPS
    )
    if z_touch:
        return (
            _positive_overlap(first.x, first.x + first.l, second.x, second.x + second.l) > _EPS
            and _positive_overlap(first.y, first.y + first.w, second.y, second.y + second.w) > _EPS
        )
    return False


def _same_product_components(
    placements: List[Placement],
    placement_indexes: List[int],
) -> List[List[int]]:
    """Connected same-product components using positive-area face contact."""
    remaining = set(placement_indexes)
    components: List[List[int]] = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        component = [seed]
        queue = [seed]
        while queue:
            current = queue.pop()
            neighbours = [
                index
                for index in list(remaining)
                if _placements_face_connected(
                    placements[current],
                    placements[index],
                )
            ]
            for index in neighbours:
                remaining.remove(index)
                component.append(index)
                queue.append(index)
        components.append(component)
    return components


def _virtual_shifted_placements(
    placements: List[Placement],
    moving_indexes: List[int],
    shift: float,
) -> List[Placement]:
    moving = set(moving_indexes)
    return [
        replace(placement, x=placement.x - shift)
        if index in moving
        else placement
        for index, placement in enumerate(placements)
    ]


def _shift_is_valid(
    placements: List[Placement],
    moving_indexes: List[int],
    shift: float,
    container: Dict,
) -> bool:
    """Validate one rigid backward translation, including physical support."""
    if shift <= _EPS:
        return False

    moving = set(moving_indexes)
    shifted = _virtual_shifted_placements(placements, moving_indexes, shift)

    for index in moving_indexes:
        placement = shifted[index]
        if (
            placement.x < -_EPS
            or placement.y < -_EPS
            or placement.z < -_EPS
            or placement.x + placement.l > float(container["L"]) + _EPS
            or placement.y + placement.w > float(container["W"]) + _EPS
            or placement.z + placement.h > float(container["H"]) + _EPS
        ):
            return False

        for other_index, other in enumerate(shifted):
            if other_index == index or other_index in moving:
                continue
            if _placements_overlap(placement, other):
                return False

    # Support is checked against the fully shifted arrangement, so internal
    # stack support moves with the component while external support must still
    # exist at the destination.
    for index in moving_indexes:
        placement = shifted[index]
        if not _space_base_is_supported(
            Space(
                placement.x,
                placement.y,
                placement.z,
                placement.l,
                placement.w,
                placement.h,
            ),
            shifted,
        ):
            return False
    return True


def _backward_shift_candidates(
    placements: List[Placement],
    moving_indexes: List[int],
    minimum_x: float,
) -> List[float]:
    """Meaningful deterministic shifts toward the container back wall.

    Candidates come from wall/frontier contact, cargo contact, and support-edge
    alignment. Arbitrary millimetre scanning is intentionally avoided.
    """
    moving = set(moving_indexes)
    candidates = set()

    for index in moving_indexes:
        placement = placements[index]
        wall_shift = placement.x - minimum_x
        if wall_shift > _EPS:
            candidates.add(round(wall_shift, 9))

        for other_index, other in enumerate(placements):
            if other_index in moving:
                continue

            yz_overlap = (
                _positive_overlap(
                    placement.y,
                    placement.y + placement.w,
                    other.y,
                    other.y + other.w,
                ) > _EPS
                and _positive_overlap(
                    placement.z,
                    placement.z + placement.h,
                    other.z,
                    other.z + other.h,
                ) > _EPS
            )
            if yz_overlap and other.x + other.l <= placement.x + _EPS:
                shift = placement.x - (other.x + other.l)
                if shift > _EPS:
                    candidates.add(round(shift, 9))

            # A moved upper box may need to align with a stackable support
            # rectangle below. Both left- and right-edge alignments are useful.
            if (
                other.stackable
                and abs(other.z + other.h - placement.z) <= _EPS
                and _positive_overlap(
                    placement.y,
                    placement.y + placement.w,
                    other.y,
                    other.y + other.w,
                ) > _EPS
            ):
                for destination_x in (
                    other.x,
                    other.x + other.l - placement.l,
                ):
                    shift = placement.x - destination_x
                    if shift > _EPS:
                        candidates.add(round(shift, 9))

    return sorted(candidates, reverse=True)


def _move_group_backward(
    placements: List[Placement],
    moving_indexes: List[int],
    container: Dict,
    minimum_x: float,
) -> float:
    """Move one rigid group by the largest valid meaningful backward shift."""
    for shift in _backward_shift_candidates(
        placements,
        moving_indexes,
        minimum_x,
    ):
        if _shift_is_valid(placements, moving_indexes, shift, container):
            for index in moving_indexes:
                placements[index].x -= shift
            return shift
    return 0.0


def _vertical_stack_groups(
    placements: List[Placement],
    placement_indexes: List[int],
) -> List[List[int]]:
    """Group floor-rooted placements sharing one exact x/y footprint."""
    grouped: Dict[Tuple[float, float, float, float], List[int]] = {}
    for index in placement_indexes:
        placement = placements[index]
        key = (
            round(placement.x, 6),
            round(placement.y, 6),
            round(placement.l, 6),
            round(placement.w, 6),
        )
        grouped.setdefault(key, []).append(index)

    stacks = []
    for indexes in grouped.values():
        indexes.sort(key=lambda index: placements[index].z)
        if placements[indexes[0]].z <= _EPS:
            stacks.append(indexes)
    return stacks


def _group_has_external_dependents(
    placements: List[Placement],
    group_indexes: List[int],
) -> bool:
    """Return whether a box outside the group rests on any group member.

    Independently moving a floor stack is unsafe when a wider upper box spans
    that stack and a neighbouring one. Such a dependency remains eligible for
    whole-component movement, but not for stack-level splitting.
    """
    group = set(group_indexes)
    for index in group_indexes:
        placement = placements[index]
        top = placement.z + placement.h
        for other_index, other in enumerate(placements):
            if other_index in group or abs(other.z - top) > _EPS:
                continue
            if (
                _positive_overlap(
                    placement.x,
                    placement.x + placement.l,
                    other.x,
                    other.x + other.l,
                ) > _EPS
                and _positive_overlap(
                    placement.y,
                    placement.y + placement.w,
                    other.y,
                    other.y + other.w,
                ) > _EPS
            ):
                return True
    return False


def _placement_supports_anything(
    placements: List[Placement],
    placement_index: int,
) -> bool:
    """Whether another placement rests directly on this placement's top face."""
    placement = placements[placement_index]
    top = placement.z + placement.h
    for other_index, other in enumerate(placements):
        if other_index == placement_index:
            continue
        if abs(other.z - top) > _EPS:
            continue
        if (
            _positive_overlap(
                placement.x,
                placement.x + placement.l,
                other.x,
                other.x + other.l,
            ) > _EPS
            and _positive_overlap(
                placement.y,
                placement.y + placement.w,
                other.y,
                other.y + other.w,
            ) > _EPS
        ):
            return True
    return False


def _hierarchical_backward_compaction(
    placements: List[Placement],
    row_index: int,
    container: Dict,
    minimum_x: float,
) -> Dict[str, float]:
    """Compact one Sequence Loading product toward the back deterministically.

    Hierarchy:
      1. face-connected components move as rigid blocks;
      2. blocked components split into floor-rooted vertical stacks;
      3. non-supporting upper boxes may move individually.

    The function changes only x coordinates. It preserves product orientation,
    y positions, z levels, quantities, stackability, and all support rules.
    """
    row_indexes = [
        index
        for index, placement in enumerate(placements)
        if placement.row_index == row_index
    ]
    if not row_indexes:
        return {
            "component_moves": 0,
            "stack_moves": 0,
            "individual_moves": 0,
            "distance": 0.0,
        }

    component_moves = 0
    stack_moves = 0
    individual_moves = 0
    total_distance = 0.0

    # Phase 1: preserve regular blocks whenever possible.
    components = _same_product_components(placements, row_indexes)
    components.sort(key=lambda indexes: min(placements[index].x for index in indexes))
    for component in components:
        if not any(placements[index].z <= _EPS for index in component):
            continue
        shift = _move_group_backward(
            placements,
            component,
            container,
            minimum_x,
        )
        if shift > _EPS:
            component_moves += 1
            total_distance += shift

    # Phase 2: a single blocked stack must not anchor a complete component.
    # Rebuild stacks after every pass because earlier moves change footprints.
    for _pass in range(3):
        moved_this_pass = False
        stacks = _vertical_stack_groups(placements, row_indexes)
        stacks.sort(key=lambda indexes: min(placements[index].x for index in indexes))
        for stack in stacks:
            if _group_has_external_dependents(placements, stack):
                continue
            shift = _move_group_backward(
                placements,
                stack,
                container,
                minimum_x,
            )
            if shift > _EPS:
                stack_moves += 1
                total_distance += shift
                moved_this_pass = True
        if not moved_this_pass:
            break

    # Phase 3: clean partial upper layers without moving supporting boxes.
    # Only boxes above floor level that support nothing are eligible.
    for _pass in range(2):
        moved_this_pass = False
        top_boxes = [
            index
            for index in row_indexes
            if placements[index].z > _EPS
            and not _placement_supports_anything(placements, index)
        ]
        top_boxes.sort(key=lambda index: (placements[index].z, placements[index].x))
        for index in top_boxes:
            shift = _move_group_backward(
                placements,
                [index],
                container,
                minimum_x,
            )
            if shift > _EPS:
                individual_moves += 1
                total_distance += shift
                moved_this_pass = True
        if not moved_this_pass:
            break

    return {
        "component_moves": component_moves,
        "stack_moves": stack_moves,
        "individual_moves": individual_moves,
        "distance": total_distance,
    }


def _compact_selected_side_gap_components_forward(
    placements: List[Placement],
    selected_indexes: List[int],
    container_length: float,
) -> Dict[str, float]:
    """Slide floor-rooted side-gap components toward the doors.

    ``selected_indexes`` are placements created by the door-accessible
    transition-residual pass for one product sequence.  The routine starts
    from selected placements on the container floor, recursively includes
    selected placements supported by them, and translates each resulting 3D
    component as one rigid object toward the doors.

    Components stop at the nearest cargo in front.  A component is kept fixed
    when it supports cargo outside the component or when no forward obstacle
    exists.  Orientations, y coordinates, z levels, quantities, and internal
    support relationships are preserved.
    """
    def _intervals_overlap_open(a0: float, a1: float, b0: float, b1: float) -> bool:
        return _positive_overlap(a0, a1, b0, b1) > _EPS

    selected = {
        index
        for index in selected_indexes
        if 0 <= index < len(placements)
    }
    if not selected:
        return {
            "moved_components": 0,
            "moved_placements": 0,
            "total_shift": 0.0,
            "maximum_shift": 0.0,
        }

    def supports(lower: Placement, upper: Placement) -> bool:
        return (
            abs(lower.z + lower.h - upper.z) <= _EPS
            and _intervals_overlap_open(
                lower.x,
                lower.x + lower.l,
                upper.x,
                upper.x + upper.l,
            )
            and _intervals_overlap_open(
                lower.y,
                lower.y + lower.w,
                upper.y,
                upper.y + upper.w,
            )
        )

    # Build floor-rooted support components using only side-gap placements.
    remaining = set(selected)
    components: List[List[int]] = []
    floor_roots = sorted(
        (index for index in selected if abs(placements[index].z) <= _EPS),
        key=lambda index: (
            placements[index].x,
            placements[index].y,
            placements[index].l,
            placements[index].w,
        ),
    )

    for root in floor_roots:
        if root not in remaining:
            continue
        component = {root}
        changed = True
        while changed:
            changed = False
            for candidate in list(remaining - component):
                candidate_placement = placements[candidate]
                if any(
                    supports(placements[index], candidate_placement)
                    or supports(candidate_placement, placements[index])
                    for index in component
                ):
                    component.add(candidate)
                    changed = True
        remaining.difference_update(component)
        components.append(sorted(component))

    # Components nearest the doors move first and become obstacles for those
    # behind them, producing deterministic forward horizontal gravity.
    components.sort(
        key=lambda indexes: max(
            placements[index].x + placements[index].l
            for index in indexes
        ),
        reverse=True,
    )

    moved_components = 0
    moved_placements = 0
    total_shift = 0.0
    maximum_shift = 0.0

    for indexes in components:
        index_set = set(indexes)
        component_end = max(
            placements[index].x + placements[index].l
            for index in indexes
        )
        forward_shift = max(0.0, container_length - component_end)
        has_forward_obstacle = False
        blocked = False

        for component_index in indexes:
            moving = placements[component_index]
            for obstacle_index, obstacle in enumerate(placements):
                if obstacle_index in index_set:
                    continue

                # Moving a selected support without cargo resting on it would
                # invalidate the existing layer structure.  Such a component
                # is intentionally left in place.
                if supports(moving, obstacle):
                    blocked = True
                    forward_shift = 0.0
                    break

                if not _intervals_overlap_open(
                    moving.y,
                    moving.y + moving.w,
                    obstacle.y,
                    obstacle.y + obstacle.w,
                ):
                    continue
                if not _intervals_overlap_open(
                    moving.z,
                    moving.z + moving.h,
                    obstacle.z,
                    obstacle.z + obstacle.h,
                ):
                    continue

                moving_end = moving.x + moving.l
                if obstacle.x >= moving_end - _EPS:
                    gap = max(0.0, obstacle.x - moving_end)
                    forward_shift = min(forward_shift, gap)
                    has_forward_obstacle = True
                elif _intervals_overlap_open(
                    moving.x,
                    moving_end,
                    obstacle.x,
                    obstacle.x + obstacle.l,
                ):
                    blocked = True
                    forward_shift = 0.0
                    break

            if blocked:
                break

        # Do not send an isolated side-gap component all the way to the door.
        # The purpose is to join it to the next cargo block, so an actual
        # obstacle/contact target in front is required.
        if (
            blocked
            or not has_forward_obstacle
            or forward_shift <= _EPS
        ):
            continue

        for index in indexes:
            placements[index].x += forward_shift

        moved_components += 1
        moved_placements += len(indexes)
        total_shift += forward_shift
        maximum_shift = max(maximum_shift, forward_shift)

    return {
        "moved_components": moved_components,
        "moved_placements": moved_placements,
        "total_shift": total_shift,
        "maximum_shift": maximum_shift,
    }

def _rebuild_sequence_free_spaces(
    container: Dict,
    placements: List[Placement],
) -> Tuple[
    List[Space],
    List[Space],
    List[Tuple[float, float, float, float]],
]:
    """Rebuild exact 3D and floor free spaces after compaction moves."""
    full = Space(
        0.0,
        0.0,
        0.0,
        float(container["L"]),
        float(container["W"]),
        float(container["H"]),
    )
    cuboids = [
        (placement.x, placement.y, placement.z, placement.l, placement.w, placement.h)
        for placement in placements
    ]
    exact_spaces = _subtract_cuboids_from_spaces([full], cuboids)
    floor_footprints = [
        (placement.x, placement.y, placement.l, placement.w)
        for placement in placements
        if placement.z <= _EPS
    ]
    floor_spaces = _subtract_floor_footprints([full], floor_footprints)
    return exact_spaces, floor_spaces, floor_footprints


def _subtract_cuboids_from_spaces(
    spaces: List[Space],
    cuboids: List[Tuple[float, float, float, float, float, float]],
) -> List[Space]:
    """Subtract occupied cuboids from a complete non-overlapping free-space set."""
    residuals = list(spaces)
    for cuboid in cuboids:
        updated: List[Space] = []
        for residual in residuals:
            updated.extend(_subtract_cuboid_from_space(residual, cuboid))
        residuals = _clean_residual_spaces(updated)
    return residuals


def _door_visible_transition_spaces(
    spaces: List[Space],
    placements: List[Placement],
    band_start: float,
    zone_end: float,
    container_length: float,
) -> List[Space]:
    """Return directly door-accessible 3D gaps in the final sequence band.

    The middle Sequence Loading mode may use residuals only inside the previous
    sequence's transition band: ``band_start <= x < zone_end``.  Deep side or
    top pockets behind that band remain closed.  A retained subspace also needs
    a straight, obstacle-free insertion corridor from its door-facing x face
    to the container doors and full support under its x/y base.
    """
    if zone_end <= band_start + _EPS:
        return []

    visible: List[Space] = []
    for space in spaces:
        x0 = max(space.x, band_start)
        x1 = min(space.x + space.L, zone_end)
        if x1 <= x0 + _EPS:
            continue

        clipped = Space(
            x=x0,
            y=space.y,
            z=space.z,
            L=x1 - x0,
            W=space.W,
            H=space.H,
        )

        # Project every cargo item lying between the candidate's front face
        # and the doors onto the y/z cross-section.  The remaining rectangles
        # have a straight insertion corridor along +x.
        yz_rectangles: List[Tuple[float, float, float, float]] = [
            (clipped.y, clipped.z, clipped.W, clipped.H)
        ]
        front_x = clipped.x + clipped.L
        for placement in placements:
            if placement.x + placement.l <= front_x + _EPS:
                continue
            if placement.x >= container_length - _EPS:
                continue

            blocker = (
                placement.y,
                placement.z,
                placement.w,
                placement.h,
            )
            updated: List[Tuple[float, float, float, float]] = []
            for rectangle in yz_rectangles:
                updated.extend(_subtract_rect_2d(rectangle, blocker))
            yz_rectangles = [
                rectangle
                for rectangle in updated
                if rectangle[2] > _EPS and rectangle[3] > _EPS
            ]
            if not yz_rectangles:
                break

        for y, z, width, height in yz_rectangles:
            candidate = Space(
                x=clipped.x,
                y=y,
                z=z,
                L=clipped.L,
                W=width,
                H=height,
            )
            if _space_base_is_supported(candidate, placements):
                visible.append(candidate)

    return _clean_residual_spaces(visible)


def _best_transition_layer(
    space: Space,
    orientations: List[Tuple[float, float, float]],
    qty_limit: int,
    width_direction: str = _WIDTH_LOW_TO_HIGH,
) -> Optional[ResidualPlan]:
    """Build one horizontal layer inside an accessible transition residual."""
    best: Optional[ResidualPlan] = None
    best_score: Optional[Tuple] = None

    for height_orientations in _orientations_by_vertical_height(orientations):
        item_height = height_orientations[0][2]
        if item_height <= _EPS or item_height > space.H + _EPS:
            continue

        layer_space = Space(
            x=space.x,
            y=space.y,
            z=space.z,
            L=space.L,
            W=space.W,
            H=item_height,
        )
        plan = _best_sequence_floor_layer_directional(
            layer_space,
            height_orientations,
            qty_limit,
            width_direction,
        )
        if plan.count <= 0:
            continue

        footprint_area = sum(
            l * w for x, y, z, l, w, h in plan.placements
        )
        occupied_length = max(
            x + l for x, y, z, l, w, h in plan.placements
        ) - space.x
        score = (
            plan.count,
            -occupied_length,
            -footprint_area,
            -len(plan.spaces),
        )
        if best is None or score > best_score:
            best = plan
            best_score = score

    return best

def _pack_container_sequence_layers_once(
    container: Dict,
    products: List[Dict],
    width_directions: Optional[Dict[int, str]] = None,
) -> Dict:
    """Strict operational loading with a full-width frontier per product row.

    Coordinate convention:
      * x = 0 is the closed back wall;
      * x = container length is the door end;
      * products are completed in loading-sequence order;
      * each product uses horizontal layers from floor to top;
      * after a product row is placed, every side, top, and deep residual
        behind its furthest x face is closed to all later product rows.

    The next product therefore receives exactly one full-width floor space
    beginning at the preceding product's x_end. Side-gap reuse belongs only
    to Accessible Sequence Loading and is deliberately excluded here.
    """
    groups = _product_groups(products)
    placements: List[Placement] = []
    unplaced: List[Dict] = []
    sequence_zones = []
    loaded_weight = 0.0
    payload_limit = float(container.get("max_weight")) if _has_payload_limit(container) else None
    container_length = float(container["L"])
    container_width = float(container["W"])
    container_height = float(container["H"])

    floor_spaces = [
        Space(0.0, 0.0, 0.0, container_length, container_width, container_height)
    ]
    occupied_floor_footprints: List[Tuple[float, float, float, float]] = []
    band_start = 0.0

    for group in groups:
        width_direction = _normalize_width_direction(
            (width_directions or {}).get(group["row_index"])
        )
        requested_qty = int(group.get("qty", 0) or 0)
        geometrically_requested = requested_qty
        payload_rejected = 0

        if payload_limit is not None and group["weight"] > 0:
            remaining_payload = max(payload_limit - loaded_weight, 0.0)
            payload_capacity = int((remaining_payload + _EPS) // group["weight"])
            geometrically_requested = min(requested_qty, payload_capacity)
            payload_rejected = requested_qty - geometrically_requested

        plan = _sequence_group_plan_directional(
            floor_spaces,
            group["orientations"],
            geometrically_requested,
            container_height,
            width_direction=width_direction,
            support_stackable=bool(group.get("stackable", True)),
        )

        packed_for_group = 0
        if plan is not None:
            for x, y, z, l, w, h in plan["placements"]:
                placements.append(
                    Placement(
                        product_name=group["name"],
                        item_index=group["item_index_start"] + packed_for_group,
                        row_index=group["row_index"],
                        sequence=group["sequence"],
                        weight=group["weight"],
                        stackable=bool(group.get("stackable", True)),
                        x=x,
                        y=y,
                        z=z,
                        l=l,
                        w=w,
                        h=h,
                    )
                )
                packed_for_group += 1
                loaded_weight += group["weight"]

            base_footprints = [
                (x, y, l, w)
                for x, y, z, l, w, h in plan["base_positions"]
            ]
            occupied_floor_footprints.extend(base_footprints)

            # Strict mode closes the complete cross-section behind the
            # product row's furthest x face.  Do not preserve side residuals,
            # top residuals, or a partial final band for later product rows.
            group_zone_end = max(band_start, float(plan["zone_end"]))
            band_start = group_zone_end
            final_band_start = group_zone_end

            remaining_length = container_length - group_zone_end
            if remaining_length > _EPS:
                floor_spaces = [
                    Space(
                        x=group_zone_end,
                        y=0.0,
                        z=0.0,
                        L=remaining_length,
                        W=container_width,
                        H=container_height,
                    )
                ]
            else:
                floor_spaces = []

            sequence_zones.append({
                "product_name": group["name"],
                "row_index": group["row_index"],
                "sequence": group["sequence"],
                "x_start": min(
                    (position[0] for position in plan["base_positions"]),
                    default=band_start,
                ),
                "x_end": group_zone_end,
                "final_band_start": final_band_start,
                "qty_packed": packed_for_group,
                "floor_positions": plan["floor_positions"],
                "layers_used": plan["layers_used"],
                "accessible_residual_spaces": len(floor_spaces),
                "strict_full_width_frontier": True,
                "width_direction": width_direction,
            })

        geometry_rejected = geometrically_requested - packed_for_group
        for offset in range(geometry_rejected):
            unplaced.append({
                "product_name": group["name"],
                "dims": group["dims"],
                "orientations": group["orientations"],
                "weight": group["weight"],
                "sequence": group["sequence"],
                "item_index": group["item_index_start"] + packed_for_group + offset,
                "row_index": group["row_index"],
                "reason": "No accessible floor position remains for this loading sequence",
            })

        for offset in range(payload_rejected):
            unplaced.append({
                "product_name": group["name"],
                "dims": group["dims"],
                "orientations": group["orientations"],
                "weight": group["weight"],
                "sequence": group["sequence"],
                "item_index": group["item_index_start"] + geometrically_requested + offset,
                "row_index": group["row_index"],
                "reason": "Container max payload exceeded",
            })

    return {
        "placements": placements,
        "unplaced": unplaced,
        "spaces": floor_spaces,
        "loaded_weight": loaded_weight,
        "strategy": "sequence_loading",
        "packing_mode": "sequence_loading",
        "sequence_zones": sequence_zones,
        "sequence_band_start": band_start,
    }



def _pack_container_accessible_sequence_layers_once(
    container: Dict,
    products: List[Dict],
    width_directions: Optional[Dict[int, str]] = None,
) -> Dict:
    """Sequence loading with door-accessible inter-zone residual filling.

    This middle mode preserves the same product order, back-to-front direction,
    width-first floor planning and horizontal layer construction as Strict
    Sequence Loading.  Before opening the next main floor block, however, it
    may populate supported three-dimensional residuals in the previous
    sequence's final transition band when those residuals have a straight
    insertion corridor from the container doors.

    Deep pockets behind the final band and spaces blocked by previously loaded
    cargo remain unavailable.  Maximum Utilization and Strict Sequence Loading
    use their existing, separate engine functions and are not modified here.
    """
    groups = _product_groups(products)
    placements: List[Placement] = []
    unplaced: List[Dict] = []
    sequence_zones = []
    loaded_weight = 0.0
    payload_limit = (
        float(container.get("max_weight"))
        if _has_payload_limit(container)
        else None
    )
    container_length = float(container["L"])
    container_width = float(container["W"])
    container_height = float(container["H"])

    floor_spaces = [
        Space(0.0, 0.0, 0.0, container_length, container_width, container_height)
    ]
    exact_spaces = [
        Space(0.0, 0.0, 0.0, container_length, container_width, container_height)
    ]
    occupied_floor_footprints: List[Tuple[float, float, float, float]] = []
    band_start = 0.0
    zone_end = 0.0

    for group in groups:
        previous_band_start = band_start
        previous_zone_end = zone_end
        group_start_index = len(placements)
        width_direction = _normalize_width_direction(
            (width_directions or {}).get(group["row_index"])
        )
        requested_qty = int(group.get("qty", 0) or 0)
        geometrically_requested = requested_qty
        payload_rejected = 0

        if payload_limit is not None and group["weight"] > 0:
            remaining_payload = max(payload_limit - loaded_weight, 0.0)
            payload_capacity = int((remaining_payload + _EPS) // group["weight"])
            geometrically_requested = min(requested_qty, payload_capacity)
            payload_rejected = requested_qty - geometrically_requested

        remaining_qty = geometrically_requested
        packed_for_group = 0
        boundary_packed = 0
        side_gap_placement_indexes: List[int] = []
        main_packed = 0
        group_placement_tuples: List[
            Tuple[float, float, float, float, float, float]
        ] = []

        # Fill only supported, door-visible residuals in the previous
        # sequence's final band. One layer is selected per iteration so lower
        # accessible layers are completed before higher ones.
        while remaining_qty > 0 and placements and zone_end > band_start + _EPS:
            transition_spaces = _door_visible_transition_spaces(
                exact_spaces,
                placements,
                band_start,
                zone_end,
                container_length,
            )
            candidates = []
            for space in transition_spaces:
                if _orientation_capacity(space, group["orientations"]) <= 0:
                    continue
                plan = _best_transition_layer(
                    space,
                    group["orientations"],
                    remaining_qty,
                    width_direction=width_direction,
                )
                if plan is None or plan.count <= 0:
                    continue

                # Operational order inside the transition band: lowest layer,
                # then deepest position, then width progression. Small
                # constrained gaps win ties before larger open rectangles.
                width_priority = (
                    space.y
                    if width_direction == _WIDTH_HIGH_TO_LOW
                    else -space.y
                )
                score = (
                    -space.z,
                    -space.x,
                    width_priority,
                    -space.volume,
                    plan.count,
                )
                candidates.append((score, space, plan))

            if not candidates:
                break

            _score, _space, plan = max(candidates, key=lambda candidate: candidate[0])
            ordered = sorted(
                plan.placements,
                key=lambda placement: (
                    placement[2],
                    placement[0],
                    (
                        -placement[1]
                        if width_direction == _WIDTH_HIGH_TO_LOW
                        else placement[1]
                    ),
                    placement[3],
                    placement[4],
                ),
            )
            exact_spaces = _subtract_cuboids_from_spaces(exact_spaces, ordered)

            floor_footprints = [
                (x, y, l, w)
                for x, y, z, l, w, h in ordered
                if z <= _EPS
            ]
            if floor_footprints:
                floor_spaces = _subtract_floor_footprints(
                    floor_spaces,
                    floor_footprints,
                )
                occupied_floor_footprints.extend(floor_footprints)

            for x, y, z, l, w, h in ordered:
                placement_index = len(placements)
                placements.append(
                    Placement(
                        product_name=group["name"],
                        item_index=group["item_index_start"] + packed_for_group,
                        row_index=group["row_index"],
                        sequence=group["sequence"],
                        weight=group["weight"],
                        stackable=bool(group.get("stackable", True)),
                        x=x,
                        y=y,
                        z=z,
                        l=l,
                        w=w,
                        h=h,
                    )
                )
                side_gap_placement_indexes.append(placement_index)
                group_placement_tuples.append((x, y, z, l, w, h))
                packed_for_group += 1
                boundary_packed += 1
                remaining_qty -= 1
                loaded_weight += group["weight"]

        # The remaining quantity uses the unchanged strict floor/layer planner.
        plan = _sequence_group_plan_directional(
            floor_spaces,
            group["orientations"],
            remaining_qty,
            container_height,
            width_direction=width_direction,
            support_stackable=bool(group.get("stackable", True)),
        )

        if plan is not None:
            ordered_main = sorted(
                plan["placements"],
                key=lambda placement: (
                    placement[2],
                    placement[0],
                    (
                        -placement[1]
                        if width_direction == _WIDTH_HIGH_TO_LOW
                        else placement[1]
                    ),
                    placement[3],
                    placement[4],
                ),
            )
            exact_spaces = _subtract_cuboids_from_spaces(
                exact_spaces,
                ordered_main,
            )

            for x, y, z, l, w, h in ordered_main:
                placements.append(
                    Placement(
                        product_name=group["name"],
                        item_index=group["item_index_start"] + packed_for_group,
                        row_index=group["row_index"],
                        sequence=group["sequence"],
                        weight=group["weight"],
                        stackable=bool(group.get("stackable", True)),
                        x=x,
                        y=y,
                        z=z,
                        l=l,
                        w=w,
                        h=h,
                    )
                )
                group_placement_tuples.append((x, y, z, l, w, h))
                packed_for_group += 1
                main_packed += 1
                loaded_weight += group["weight"]

            base_footprints = [
                (x, y, l, w)
                for x, y, z, l, w, h in plan["base_positions"]
            ]
            floor_spaces = _subtract_floor_footprints(
                floor_spaces,
                base_footprints,
            )
            occupied_floor_footprints.extend(base_footprints)

            group_zone_end = plan["zone_end"]
            end_positions = [
                position
                for position in plan["base_positions"]
                if abs(position[0] + position[3] - group_zone_end) <= _EPS
            ]
            final_band_start = min(
                (position[0] for position in end_positions),
                default=group_zone_end,
            )
            band_start = max(band_start, final_band_start)
            zone_end = max(zone_end, group_zone_end)
            floor_spaces = _accessible_sequence_floor_spaces(
                floor_spaces,
                occupied_floor_footprints,
                band_start,
                container_length,
            )
        else:
            # A sequence may fit completely inside accessible transition gaps.
            # In that case the operational frontier does not advance.
            group_zone_end = max(
                (x + l for x, y, z, l, w, h in group_placement_tuples),
                default=zone_end,
            )
            final_band_start = band_start

        compaction = {
            "component_moves": 0,
            "stack_moves": 0,
            "individual_moves": 0,
            "distance": 0.0,
        }
        if group_start_index > 0 and packed_for_group > 0:
            compaction = _hierarchical_backward_compaction(
                placements,
                group["row_index"],
                container,
                previous_band_start,
            )

        # Restore the previously accepted forward side-gap compaction after
        # hierarchical backward gravity. Running it last prevents the backward
        # pass from immediately undoing the intentional move toward the main
        # same-product block. Only placements created by the accessible
        # transition-residual pass are eligible.
        forward_compaction = {
            "moved_components": 0,
            "moved_placements": 0,
            "total_shift": 0.0,
            "maximum_shift": 0.0,
        }
        if side_gap_placement_indexes and main_packed > 0:
            forward_compaction = _compact_selected_side_gap_components_forward(
                placements,
                side_gap_placement_indexes,
                container_length,
            )

        if (
            compaction["distance"] > _EPS
            or forward_compaction["total_shift"] > _EPS
        ):
            group_placements = [
                placement
                for placement in placements
                if placement.row_index == group["row_index"]
            ]
            group_placement_tuples = [
                (
                    placement.x,
                    placement.y,
                    placement.z,
                    placement.l,
                    placement.w,
                    placement.h,
                )
                for placement in group_placements
            ]
            group_floor = [
                placement
                for placement in group_placements
                if placement.z <= _EPS
            ]
            actual_group_end = max(
                (placement.x + placement.l for placement in group_floor),
                default=max(
                    (placement.x + placement.l for placement in group_placements),
                    default=previous_zone_end,
                ),
            )

            if actual_group_end > previous_zone_end + _EPS:
                group_zone_end = actual_group_end
                end_positions = [
                    placement
                    for placement in group_floor
                    if abs(placement.x + placement.l - group_zone_end) <= _EPS
                ]
                final_band_start = min(
                    (placement.x for placement in end_positions),
                    default=group_zone_end,
                )
                band_start = max(previous_band_start, final_band_start)
                zone_end = group_zone_end
            else:
                group_zone_end = max(previous_zone_end, actual_group_end)
                final_band_start = previous_band_start
                band_start = previous_band_start
                zone_end = previous_zone_end

            exact_spaces, floor_spaces, occupied_floor_footprints = (
                _rebuild_sequence_free_spaces(container, placements)
            )
            floor_spaces = _accessible_sequence_floor_spaces(
                floor_spaces,
                occupied_floor_footprints,
                band_start,
                container_length,
            )

        sequence_zones.append({
            "product_name": group["name"],
            "row_index": group["row_index"],
            "sequence": group["sequence"],
            "x_start": min(
                (x for x, y, z, l, w, h in group_placement_tuples),
                default=band_start,
            ),
            "x_end": group_zone_end,
            "final_band_start": final_band_start,
            "qty_packed": packed_for_group,
            "boundary_residual_qty": boundary_packed,
            "side_gap_qty": boundary_packed,
            "forward_compacted_components": int(
                forward_compaction["moved_components"]
            ),
            "forward_compacted_placements": int(
                forward_compaction["moved_placements"]
            ),
            "forward_compaction_total_shift": forward_compaction["total_shift"],
            "forward_compaction_maximum_shift": forward_compaction["maximum_shift"],
            "main_zone_qty": main_packed,
            "floor_positions": (
                plan["floor_positions"] if plan is not None else 0
            ),
            "layers_used": plan["layers_used"] if plan is not None else 0,
            "accessible_residual_spaces": len(
                _door_visible_transition_spaces(
                    exact_spaces,
                    placements,
                    band_start,
                    zone_end,
                    container_length,
                )
            ),
            "width_direction": width_direction,
            "compaction_component_moves": compaction["component_moves"],
            "compaction_stack_moves": compaction["stack_moves"],
            "compaction_individual_moves": compaction["individual_moves"],
            "compaction_total_distance": compaction["distance"],
        })

        geometry_rejected = geometrically_requested - packed_for_group
        for offset in range(geometry_rejected):
            unplaced.append({
                "product_name": group["name"],
                "dims": group["dims"],
                "orientations": group["orientations"],
                "weight": group["weight"],
                "sequence": group["sequence"],
                "item_index": group["item_index_start"] + packed_for_group + offset,
                "row_index": group["row_index"],
                "reason": (
                    "No door-accessible inter-zone or forward floor position "
                    "remains for this loading sequence"
                ),
            })

        for offset in range(payload_rejected):
            unplaced.append({
                "product_name": group["name"],
                "dims": group["dims"],
                "orientations": group["orientations"],
                "weight": group["weight"],
                "sequence": group["sequence"],
                "item_index": (
                    group["item_index_start"] + geometrically_requested + offset
                ),
                "row_index": group["row_index"],
                "reason": "Container max payload exceeded",
            })

    accessible_result = {
        "placements": placements,
        "unplaced": unplaced,
        "spaces": floor_spaces,
        "loaded_weight": loaded_weight,
        "strategy": "accessible_sequence_loading",
        "packing_mode": "accessible_sequence_loading",
        "sequence_zones": sequence_zones,
        "sequence_band_start": band_start,
    }

    accessible_result["accessible_sequence_fallback"] = False
    return accessible_result

def _sequence_width_direction_patterns(
    products: List[Dict],
) -> List[Dict[int, str]]:
    """Return a bounded set of per-sequence width-direction candidates.

    For up to four product groups every low/high combination is evaluated.
    Larger requests use deterministic global, alternating and single-flip
    patterns so runtime remains bounded.  The current low-to-high behavior is
    always first and therefore wins exact ties.
    """
    groups = _product_groups(products)
    row_indexes = [
        group["row_index"]
        for group in groups
        if int(group.get("qty", 0) or 0) > 0
    ]
    if not row_indexes:
        return [{}]

    patterns: List[Dict[int, str]] = []
    seen = set()

    def add(values: List[str]) -> None:
        key = tuple(values)
        if key in seen:
            return
        seen.add(key)
        patterns.append(dict(zip(row_indexes, values)))

    count = len(row_indexes)
    if count <= 4:
        for mask in range(1 << count):
            add([
                (
                    _WIDTH_HIGH_TO_LOW
                    if mask & (1 << index)
                    else _WIDTH_LOW_TO_HIGH
                )
                for index in range(count)
            ])
        return patterns

    low = [_WIDTH_LOW_TO_HIGH] * count
    high = [_WIDTH_HIGH_TO_LOW] * count
    add(low)
    add(high)
    add([
        _WIDTH_LOW_TO_HIGH if index % 2 == 0 else _WIDTH_HIGH_TO_LOW
        for index in range(count)
    ])
    add([
        _WIDTH_HIGH_TO_LOW if index % 2 == 0 else _WIDTH_LOW_TO_HIGH
        for index in range(count)
    ])

    # Explore one group from the opposite side while the others keep a common
    # direction. This is the most useful bounded search at sequence boundaries.
    for index in range(count):
        values = list(low)
        values[index] = _WIDTH_HIGH_TO_LOW
        add(values)
        values = list(high)
        values[index] = _WIDTH_LOW_TO_HIGH
        add(values)
        if len(patterns) >= 16:
            break

    return patterns[:16]


def _placement_face_contact_area(first: Placement, second: Placement) -> float:
    """Return shared face area for two non-overlapping placements."""
    def overlap(a0: float, a1: float, b0: float, b1: float) -> float:
        return max(0.0, min(a1, b1) - max(a0, b0))

    area = 0.0
    if (
        abs(first.x + first.l - second.x) <= _EPS
        or abs(second.x + second.l - first.x) <= _EPS
    ):
        area += overlap(first.y, first.y + first.w, second.y, second.y + second.w) * overlap(
            first.z, first.z + first.h, second.z, second.z + second.h
        )
    if (
        abs(first.y + first.w - second.y) <= _EPS
        or abs(second.y + second.w - first.y) <= _EPS
    ):
        area += overlap(first.x, first.x + first.l, second.x, second.x + second.l) * overlap(
            first.z, first.z + first.h, second.z, second.z + second.h
        )
    if (
        abs(first.z + first.h - second.z) <= _EPS
        or abs(second.z + second.h - first.z) <= _EPS
    ):
        area += overlap(first.x, first.x + first.l, second.x, second.x + second.l) * overlap(
            first.y, first.y + first.w, second.y, second.y + second.w
        )
    return area


def _sequence_contact_metrics(placements: List[Placement]) -> Tuple[int, float]:
    """Return same-product component count and total cargo face contact area."""
    count = len(placements)
    if count <= 1:
        return count, 0.0

    # Detailed adjacency remains inexpensive for normal loading plans.  For
    # very large plans, bounding compactness is used without the quadratic
    # contact pass.
    if count > 500:
        return 0, 0.0

    parents = list(range(count))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    contact_area = 0.0
    for left in range(count):
        for right in range(left + 1, count):
            area = _placement_face_contact_area(placements[left], placements[right])
            if area <= _EPS:
                continue
            contact_area += area
            if placements[left].row_index == placements[right].row_index:
                union(left, right)

    components = len({
        (placements[index].row_index, find(index))
        for index in range(count)
    })
    return components, contact_area


def _sequence_compactness_score(
    result: Dict,
    products: List[Dict],
) -> Tuple:
    """Compare complete sequential candidates without changing load priority.

    Product-by-product loaded quantities remain the hard objective.  Equal-load
    results then prefer the shortest occupied length, tighter sequence zones,
    fewer disconnected same-product blocks and greater cargo face contact.
    """
    placements: List[Placement] = result.get("placements", [])
    groups = _product_groups(products)
    counts: Dict[int, int] = {}
    for placement in placements:
        counts[placement.row_index] = counts.get(placement.row_index, 0) + 1
    count_vector = tuple(counts.get(group["row_index"], 0) for group in groups)

    packed_volume = sum(
        placement.l * placement.w * placement.h
        for placement in placements
    )
    if placements:
        min_x = min(placement.x for placement in placements)
        min_y = min(placement.y for placement in placements)
        min_z = min(placement.z for placement in placements)
        max_x = max(placement.x + placement.l for placement in placements)
        max_y = max(placement.y + placement.w for placement in placements)
        max_z = max(placement.z + placement.h for placement in placements)
        occupied_length = max_x - min_x
        bounding_volume = (
            occupied_length * (max_y - min_y) * (max_z - min_z)
        )
    else:
        occupied_length = 0.0
        bounding_volume = 0.0

    zones = result.get("sequence_zones", [])
    zone_end_sum = sum(float(zone.get("x_end", 0.0) or 0.0) for zone in zones)
    zone_span_sum = sum(
        max(0.0, float(zone.get("x_end", 0.0) or 0.0) - float(zone.get("x_start", 0.0) or 0.0))
        for zone in zones
    )
    boundary_residual_qty = sum(
        int(zone.get("boundary_residual_qty", 0) or 0)
        for zone in zones
    )
    components, contact_area = _sequence_contact_metrics(placements)

    return (
        count_vector,
        len(placements),
        packed_volume,
        -occupied_length,
        -components,
        contact_area,
        -bounding_volume,
        -zone_end_sum,
        -zone_span_sum,
        boundary_residual_qty,
        -len(result.get("spaces", [])),
    )


def _sequence_counts_by_row(result: Dict) -> Dict[int, int]:
    counts: Dict[int, int] = {}
    for placement in result.get("placements", []):
        counts[placement.row_index] = counts.get(placement.row_index, 0) + 1
    return counts


def _pack_container_sequence_layers(container: Dict, products: List[Dict]) -> Dict:
    """Strict Sequence Loading with mirrored per-sequence compactness search."""
    patterns = _sequence_width_direction_patterns(products)
    best_result: Optional[Dict] = None
    best_score: Optional[Tuple] = None
    best_pattern: Dict[int, str] = {}

    for pattern in patterns:
        candidate = _pack_container_sequence_layers_once(
            container,
            products,
            width_directions=pattern,
        )
        score = _sequence_compactness_score(candidate, products)
        if best_result is None or score > best_score:
            best_result = candidate
            best_score = score
            best_pattern = pattern

    assert best_result is not None
    best_result["sequence_width_search"] = True
    best_result["sequence_width_candidates_evaluated"] = len(patterns)
    best_result["sequence_width_directions"] = dict(best_pattern)
    return best_result


def _pack_container_accessible_sequence_layers(
    container: Dict,
    products: List[Dict],
) -> Dict:
    """Fast middle Sequence Loading with hierarchical gravity compaction.

    The discarded mirrored-width experiment is intentionally not used here.
    One deterministic low-to-high width plan is generated, compacted, and
    checked against the unchanged strict one-pass geometry as a quantity guard.
    """
    result = _pack_container_accessible_sequence_layers_once(
        container,
        products,
        width_directions=None,
    )

    strict_guard = _pack_container_sequence_layers_once(
        container,
        products,
        width_directions=None,
    )
    accessible_counts = _sequence_counts_by_row(result)
    strict_counts = _sequence_counts_by_row(strict_guard)
    row_indexes = {group["row_index"] for group in _product_groups(products)}
    if any(
        accessible_counts.get(row_index, 0) < strict_counts.get(row_index, 0)
        for row_index in row_indexes
    ):
        fallback = dict(strict_guard)
        fallback["packing_mode"] = ACCESSIBLE_SEQUENCE_LOADING_MODE
        fallback["strategy"] = "accessible_sequence_loading_fallback_strict"
        fallback["accessible_sequence_fallback"] = True
        fallback["sequence_width_search"] = False
        fallback["sequence_width_candidates_evaluated"] = 1
        return fallback

    result["accessible_sequence_fallback"] = False
    result["sequence_width_search"] = False
    result["sequence_width_candidates_evaluated"] = 1
    return result


def _hybrid_score(pack_result: Dict, products: List[Dict]) -> Tuple:
    """Score sequence-respecting Maximum Utilization candidates.

    Packed volume is the primary objective. Unit count follows because some
    users value the number of load units when volume is equal. Compactness is
    used only as a tie-breaker so equal-capacity results stay in continuous
    blocks whenever possible. Exact ties remain with the original greedy path.
    """
    placements = pack_result.get("placements", [])
    packed_volume = sum(
        placement.l * placement.w * placement.h
        for placement in placements
    )

    if placements:
        min_x = min(placement.x for placement in placements)
        min_y = min(placement.y for placement in placements)
        min_z = min(placement.z for placement in placements)
        max_x = max(placement.x + placement.l for placement in placements)
        max_y = max(placement.y + placement.w for placement in placements)
        max_z = max(placement.z + placement.h for placement in placements)
        occupied_length = max_x - min_x
        occupied_width = max_y - min_y
        occupied_height = max_z - min_z
        occupied_bounding_volume = (
            occupied_length * occupied_width * occupied_height
        )
    else:
        occupied_length = occupied_width = occupied_height = 0.0
        occupied_bounding_volume = 0.0

    return (
        packed_volume,
        len(placements),
        -occupied_bounding_volume,
        -occupied_length,
        -occupied_width,
        -occupied_height,
        float(pack_result.get("loaded_weight", 0.0) or 0.0),
    )



# Maximum-only extreme-point candidate.  This path deliberately does not use
# Sequence Loading frontiers, transition bands, width-direction search, or
# sequence compaction.  Loading sequence controls processing order only.
_MAXIMUM_ANCHOR_ITEM_LIMIT = 300
_MAXIMUM_ANCHOR_AXIS_LIMIT = 96
_MAXIMUM_ANCHOR_Z_LIMIT = 32


def _bounded_anchor_values(values, lower: float, upper: float, limit: int) -> List[float]:
    """Return deterministic, evenly retained anchor coordinates."""
    ordered = sorted({
        round(float(value), 9)
        for value in values
        if lower - _EPS <= float(value) <= upper + _EPS
    })
    if len(ordered) <= limit:
        return ordered
    if limit <= 1:
        return ordered[:1]

    indexes = {
        int(round(index * (len(ordered) - 1) / (limit - 1)))
        for index in range(limit)
    }
    return [ordered[index] for index in sorted(indexes)]


def _maximum_anchor_positions(
    placements: List[Placement],
    orientation: Tuple[float, float, float],
    container: Dict,
) -> List[Tuple[float, float, float]]:
    """Generate physical placement anchors without residual-space sectors.

    Anchors come from the container walls and the real faces of already placed
    cargo.  A candidate may therefore cross an internal residual-space split;
    only collision, support, stackability, and container bounds decide whether
    the position is valid.
    """
    l, w, h = orientation
    container_length = float(container["L"])
    container_width = float(container["W"])
    container_height = float(container["H"])

    z_values = {0.0}
    for placement in placements:
        top = placement.z + placement.h
        if placement.stackable and top + h <= container_height + _EPS:
            z_values.add(round(top, 9))
    z_levels = _bounded_anchor_values(
        z_values,
        0.0,
        max(container_height - h, 0.0),
        _MAXIMUM_ANCHOR_Z_LIMIT,
    )

    anchors = set()
    for z in z_levels:
        if z <= _EPS:
            relevant = placements
            x_values = {0.0, max(container_length - l, 0.0)}
            y_values = {0.0, max(container_width - w, 0.0)}
        else:
            relevant = [
                placement
                for placement in placements
                if placement.stackable
                and abs(placement.z + placement.h - z) <= _EPS
            ]
            if not relevant:
                continue
            x_values = set()
            y_values = set()

        for placement in relevant:
            # Align either edge of the candidate with either edge of real cargo.
            x_values.update({
                placement.x,
                placement.x + placement.l,
                placement.x - l,
                placement.x + placement.l - l,
            })
            y_values.update({
                placement.y,
                placement.y + placement.w,
                placement.y - w,
                placement.y + placement.w - w,
            })

        bounded_x = _bounded_anchor_values(
            x_values,
            0.0,
            max(container_length - l, 0.0),
            _MAXIMUM_ANCHOR_AXIS_LIMIT,
        )
        bounded_y = _bounded_anchor_values(
            y_values,
            0.0,
            max(container_width - w, 0.0),
            _MAXIMUM_ANCHOR_AXIS_LIMIT,
        )
        for x in bounded_x:
            for y in bounded_y:
                anchors.add((x, y, z))

    return sorted(anchors, key=lambda point: (point[0], point[2], point[1]))


def _maximum_anchor_candidate_metrics(
    candidate: Placement,
    placements: List[Placement],
    container: Dict,
) -> Optional[Tuple[float, float]]:
    """Validate one anchor and return same-product/all-cargo face contact."""
    if (
        candidate.x < -_EPS
        or candidate.y < -_EPS
        or candidate.z < -_EPS
        or candidate.x + candidate.l > float(container["L"]) + _EPS
        or candidate.y + candidate.w > float(container["W"]) + _EPS
        or candidate.z + candidate.h > float(container["H"]) + _EPS
    ):
        return None

    same_product_contact = 0.0
    all_contact = 0.0
    for existing in placements:
        if _placements_overlap(candidate, existing):
            return None
        contact = _placement_face_contact_area(candidate, existing)
        all_contact += contact
        if existing.row_index == candidate.row_index:
            same_product_contact += contact

    if not _space_base_is_supported(
        Space(
            candidate.x,
            candidate.y,
            candidate.z,
            candidate.l,
            candidate.w,
            candidate.h,
        ),
        placements,
    ):
        return None

    return same_product_contact, all_contact


def _pack_container_maximum_anchor(container: Dict, products: List[Dict]) -> Dict:
    """Unrestricted maximum-utilization candidate based on physical anchors.

    Items are processed in loading-sequence order, but no spatial frontier is
    created.  Each item may use any collision-free, fully supported anchor
    formed by container walls or actual cargo faces.  Internal residual-space
    partitions have no authority in this candidate.
    """
    items = expand_items(products, respect_sequence=True)
    placements: List[Placement] = []
    unplaced: List[Dict] = []
    loaded_weight = 0.0
    payload_limit = (
        float(container.get("max_weight"))
        if _has_payload_limit(container)
        else None
    )

    for item in items:
        if payload_limit is not None and loaded_weight + item["weight"] > payload_limit + _EPS:
            unplaced.append({**item, "reason": "Container max payload exceeded"})
            continue

        current_max_x = max(
            (placement.x + placement.l for placement in placements),
            default=0.0,
        )
        current_max_y = max(
            (placement.y + placement.w for placement in placements),
            default=0.0,
        )
        current_max_z = max(
            (placement.z + placement.h for placement in placements),
            default=0.0,
        )

        best: Optional[Tuple[Tuple, Placement]] = None
        for orientation_index, orientation in enumerate(item["orientations"]):
            l, w, h = orientation
            for x, y, z in _maximum_anchor_positions(
                placements,
                orientation,
                container,
            ):
                candidate_max_x = max(current_max_x, x + l)
                candidate_max_z = max(current_max_z, z + h)
                candidate_max_y = max(current_max_y, y + w)
                if best is not None:
                    best_score = best[0]
                    if candidate_max_x > best_score[0] + _EPS:
                        continue
                    if (
                        abs(candidate_max_x - best_score[0]) <= _EPS
                        and candidate_max_z > best_score[1] + _EPS
                    ):
                        continue
                    if (
                        abs(candidate_max_x - best_score[0]) <= _EPS
                        and abs(candidate_max_z - best_score[1]) <= _EPS
                        and candidate_max_y > best_score[2] + _EPS
                    ):
                        continue

                candidate = Placement(
                    product_name=item["product_name"],
                    item_index=item["item_index"],
                    row_index=item["row_index"],
                    sequence=item["sequence"],
                    weight=item["weight"],
                    stackable=item["stackable"],
                    x=x,
                    y=y,
                    z=z,
                    l=l,
                    w=w,
                    h=h,
                )
                contacts = _maximum_anchor_candidate_metrics(
                    candidate,
                    placements,
                    container,
                )
                if contacts is None:
                    continue
                same_product_contact, all_contact = contacts

                max_x = candidate_max_x
                max_y = candidate_max_y
                max_z = candidate_max_z
                bounding_volume = max_x * max_y * max_z

                # Short occupied length is preferred first.  Face contact then
                # prevents a physically continuous product region from being
                # split into visual parcels when capacity is equal.
                score = (
                    max_x,
                    max_z,
                    max_y,
                    bounding_volume,
                    -same_product_contact,
                    -all_contact,
                    z,
                    x,
                    y,
                    orientation_index,
                )
                if best is None or score < best[0]:
                    best = (score, candidate)

        if best is None:
            unplaced.append({**item, "reason": "No fitting physical anchor"})
            continue

        placements.append(best[1])
        loaded_weight += item["weight"]

    surface_regularization = _regularize_maximum_supported_top_layers(
        placements,
        products,
        container,
    )

    full_space = Space(
        0.0,
        0.0,
        0.0,
        float(container["L"]),
        float(container["W"]),
        float(container["H"]),
    )
    occupied = [
        (
            placement.x,
            placement.y,
            placement.z,
            placement.l,
            placement.w,
            placement.h,
        )
        for placement in placements
    ]
    spaces = _subtract_cuboids_from_spaces([full_space], occupied)

    return {
        "placements": placements,
        "unplaced": unplaced,
        "spaces": spaces,
        "loaded_weight": loaded_weight,
        "strategy": "maximum_anchor",
        "maximum_surface_regularization": surface_regularization,
    }


# Maximum-only supported-surface regularization.  This pass does not call or
# modify either Sequence Loading engine.  It replaces item-by-item mosaics on
# one continuous physical support plane with a coherent lane arrangement when
# the same quantity fits with fewer orientation sectors.
_MAXIMUM_SURFACE_LANE_LIMIT = 200


def _maximum_supported_rectangles_at_height(
    placements: List[Placement],
    z: float,
    container: Dict,
) -> List[Tuple[float, float, float, float]]:
    """Return non-overlapping rectangles fully supported at height ``z``.

    Rectangles are derived from the union of actual stackable top faces rather
    than from residual-space partitions.  Adjacent support faces therefore
    form one physical surface when their union is rectangular.
    """
    if z <= _EPS:
        return [(0.0, 0.0, float(container["L"]), float(container["W"]))]

    supports = [
        placement
        for placement in placements
        if placement.stackable
        and abs(placement.z + placement.h - z) <= _EPS
    ]
    if not supports:
        return []

    x_edges = sorted({
        round(value, 9)
        for placement in supports
        for value in (placement.x, placement.x + placement.l)
    })
    y_edges = sorted({
        round(value, 9)
        for placement in supports
        for value in (placement.y, placement.y + placement.w)
    })
    if len(x_edges) < 2 or len(y_edges) < 2:
        return []

    horizontal_runs: List[List[float]] = []
    for y_index in range(len(y_edges) - 1):
        y0, y1 = y_edges[y_index], y_edges[y_index + 1]
        covered_cells = []
        centre_y = (y0 + y1) / 2.0
        for x_index in range(len(x_edges) - 1):
            x0, x1 = x_edges[x_index], x_edges[x_index + 1]
            centre_x = (x0 + x1) / 2.0
            covered_cells.append(any(
                placement.x - _EPS <= centre_x <= placement.x + placement.l + _EPS
                and placement.y - _EPS <= centre_y <= placement.y + placement.w + _EPS
                for placement in supports
            ))

        cell_index = 0
        while cell_index < len(covered_cells):
            if not covered_cells[cell_index]:
                cell_index += 1
                continue
            run_start = cell_index
            while cell_index < len(covered_cells) and covered_cells[cell_index]:
                cell_index += 1
            horizontal_runs.append([
                x_edges[run_start],
                y0,
                x_edges[cell_index] - x_edges[run_start],
                y1 - y0,
            ])

    # Merge vertically adjacent runs with exactly the same x span.
    rectangles = horizontal_runs
    changed = True
    while changed:
        changed = False
        merged: List[List[float]] = []
        used = [False] * len(rectangles)
        for index, rectangle in enumerate(rectangles):
            if used[index]:
                continue
            current = list(rectangle)
            used[index] = True
            extended = True
            while extended:
                extended = False
                for other_index, other in enumerate(rectangles):
                    if used[other_index]:
                        continue
                    if (
                        abs(current[0] - other[0]) <= _EPS
                        and abs(current[2] - other[2]) <= _EPS
                        and abs(current[1] + current[3] - other[1]) <= _EPS
                    ):
                        current[3] += other[3]
                        used[other_index] = True
                        changed = True
                        extended = True
            merged.append(current)
        rectangles = merged

    result = [
        (x, y, length, width)
        for x, y, length, width in rectangles
        if length > _EPS and width > _EPS
    ]
    result.sort(key=lambda rectangle: (rectangle[0], rectangle[1], -rectangle[2] * rectangle[3]))
    return result


def _maximum_surface_lane_compositions(
    available_width: float,
    orientations: List[Tuple[float, float, float]],
) -> List[Tuple[int, ...]]:
    """Bounded lane combinations for one Maximum-only support surface."""
    if not orientations:
        return []
    if len(orientations) == 1:
        width = orientations[0][1]
        lanes = int((available_width + _EPS) // width) if width > _EPS else 0
        return [(lanes,)] if lanes > 0 else []

    first, second = orientations[:2]
    max_first = int((available_width + _EPS) // first[1]) if first[1] > _EPS else 0
    if max_first <= _MAXIMUM_SURFACE_LANE_LIMIT:
        first_counts = range(max_first + 1)
    else:
        first_counts = sorted({
            0,
            max_first,
            *(
                int(round(max_first * index / 64))
                for index in range(65)
            ),
        })

    compositions = set()
    for first_count in first_counts:
        remaining_width = available_width - first_count * first[1]
        if remaining_width < -_EPS:
            continue
        second_count = (
            int((remaining_width + _EPS) // second[1])
            if second[1] > _EPS
            else 0
        )
        if first_count + second_count > 0:
            compositions.add((first_count, second_count))

    return sorted(compositions)


def _plan_maximum_supported_layer(
    rectangle: Tuple[float, float, float, float],
    orientations: List[Tuple[float, float, float]],
    qty_limit: int,
) -> List[Tuple[float, float, float, float, float]]:
    """Plan one coherent horizontal layer on a physical support rectangle."""
    if qty_limit <= 0:
        return []

    origin_x, origin_y, available_length, available_width = rectangle
    useful = [
        orientation
        for orientation in orientations
        if orientation[0] <= available_length + _EPS
        and orientation[1] <= available_width + _EPS
    ]
    if not useful:
        return []

    best_placements: List[Tuple[float, float, float, float, float]] = []
    best_score: Optional[Tuple] = None

    by_height: Dict[float, List[Tuple[float, float, float]]] = {}
    for orientation in useful:
        by_height.setdefault(round(orientation[2], 9), []).append(orientation)

    for height_orientations in by_height.values():
        # A cuboid height group contains at most two 90-degree floor rotations.
        height_orientations = height_orientations[:2]
        for composition in _maximum_surface_lane_compositions(
            available_width,
            height_orientations,
        ):
            lanes = []
            y_cursor = origin_y
            for orientation_index, lane_count in enumerate(composition):
                length, width, height = height_orientations[orientation_index]
                capacity = int((available_length + _EPS) // length)
                for _ in range(lane_count):
                    if y_cursor + width > origin_y + available_width + _EPS:
                        break
                    lanes.append({
                        "orientation": (length, width, height),
                        "y": y_cursor,
                        "capacity": capacity,
                        "count": 0,
                    })
                    y_cursor += width

            heap = []
            for lane_index, lane in enumerate(lanes):
                if lane["capacity"] > 0:
                    heapq.heappush(
                        heap,
                        (lane["orientation"][0], lane_index),
                    )

            assigned = 0
            while heap and assigned < qty_limit:
                _completion, lane_index = heapq.heappop(heap)
                lane = lanes[lane_index]
                lane["count"] += 1
                assigned += 1
                if lane["count"] < lane["capacity"]:
                    next_completion = (
                        lane["count"] + 1
                    ) * lane["orientation"][0]
                    heapq.heappush(heap, (next_completion, lane_index))

            placements = []
            for lane in lanes:
                length, width, height = lane["orientation"]
                for position in range(lane["count"]):
                    placements.append((
                        origin_x + position * length,
                        lane["y"],
                        length,
                        width,
                        height,
                    ))
            if not placements:
                continue

            occupied_length = max(
                x + length for x, y, length, width, height in placements
            ) - origin_x
            occupied_width = max(
                y + width for x, y, length, width, height in placements
            ) - origin_y
            orientation_count = len({
                (length, width, height)
                for x, y, length, width, height in placements
            })
            score = (
                len(placements),
                -occupied_length,
                occupied_width,
                -orientation_count,
                -len(lanes),
            )
            if best_score is None or score > best_score:
                best_score = score
                best_placements = placements

    return best_placements


def _maximum_layer_regularity_metrics(
    placements: List[Placement],
) -> Tuple[int, float, float, float]:
    """Lower tuple is a more coherent same-height arrangement."""
    if not placements:
        return (0, 0.0, 0.0, 0.0)
    orientation_count = len({
        (round(placement.l, 9), round(placement.w, 9), round(placement.h, 9))
        for placement in placements
    })
    min_x = min(placement.x for placement in placements)
    max_x = max(placement.x + placement.l for placement in placements)
    min_y = min(placement.y for placement in placements)
    max_y = max(placement.y + placement.w for placement in placements)
    bounding_area = (max_x - min_x) * (max_y - min_y)
    contact_area = 0.0
    for left in range(len(placements)):
        for right in range(left + 1, len(placements)):
            contact_area += _placement_face_contact_area(
                placements[left],
                placements[right],
            )
    return (
        orientation_count,
        bounding_area,
        max_x - min_x,
        -contact_area,
    )


def _regularize_maximum_supported_top_layers(
    placements: List[Placement],
    products: List[Dict],
    container: Dict,
) -> Dict[str, int]:
    """Regularize non-supporting upper layers in Maximum Utilization only.

    A layer is replaced only when the same number of units fits on the same
    physical support rectangle, every replacement remains fully supported and
    collision-free, and the arrangement has a better regularity metric.
    Boxes that support cargo above them are never moved.
    """
    moved_layers = 0
    moved_placements = 0

    product_by_row = {
        row_index: product
        for row_index, product in enumerate(products)
    }
    row_indexes = sorted({placement.row_index for placement in placements})

    for row_index in row_indexes:
        product = product_by_row.get(row_index)
        if product is None:
            continue
        orientations = allowed_orientations(
            (product["length"], product["width"], product["height"]),
            product["r1"],
            product["r2"],
            product["r3"],
        )

        z_levels = sorted({
            round(placement.z, 9)
            for placement in placements
            if placement.row_index == row_index and placement.z > _EPS
        }, reverse=True)

        for z in z_levels:
            support_rectangles = _maximum_supported_rectangles_at_height(
                placements,
                z,
                container,
            )
            for rectangle in support_rectangles:
                rx, ry, rlength, rwidth = rectangle
                candidate_indexes = [
                    index
                    for index, placement in enumerate(placements)
                    if placement.row_index == row_index
                    and abs(placement.z - z) <= _EPS
                    and placement.x >= rx - _EPS
                    and placement.y >= ry - _EPS
                    and placement.x + placement.l <= rx + rlength + _EPS
                    and placement.y + placement.w <= ry + rwidth + _EPS
                    and not _placement_supports_anything(placements, index)
                ]
                if len(candidate_indexes) < 2:
                    continue

                # Keep one common vertical dimension.  Different-height boxes
                # at the same z may have different top planes and are not mixed.
                indexes_by_height: Dict[float, List[int]] = {}
                for index in candidate_indexes:
                    indexes_by_height.setdefault(
                        round(placements[index].h, 9),
                        [],
                    ).append(index)

                for height, indexes in indexes_by_height.items():
                    if len(indexes) < 2:
                        continue
                    allowed_for_height = [
                        orientation
                        for orientation in orientations
                        if abs(orientation[2] - height) <= _EPS
                    ]
                    planned = _plan_maximum_supported_layer(
                        rectangle,
                        allowed_for_height,
                        len(indexes),
                    )
                    if len(planned) != len(indexes):
                        continue

                    ordered_indexes = sorted(
                        indexes,
                        key=lambda index: placements[index].item_index,
                    )
                    virtual = list(placements)
                    for index, planned_placement in zip(
                        ordered_indexes,
                        sorted(planned, key=lambda value: (value[0], value[1], value[2], value[3])),
                    ):
                        x, y, length, width, planned_height = planned_placement
                        virtual[index] = replace(
                            placements[index],
                            x=x,
                            y=y,
                            z=z,
                            l=length,
                            w=width,
                            h=planned_height,
                        )

                    moving = set(ordered_indexes)
                    valid = True
                    for index in ordered_indexes:
                        placement = virtual[index]
                        if (
                            placement.x < -_EPS
                            or placement.y < -_EPS
                            or placement.z < -_EPS
                            or placement.x + placement.l > float(container["L"]) + _EPS
                            or placement.y + placement.w > float(container["W"]) + _EPS
                            or placement.z + placement.h > float(container["H"]) + _EPS
                        ):
                            valid = False
                            break
                        for other_index, other in enumerate(virtual):
                            if other_index == index:
                                continue
                            if _placements_overlap(placement, other):
                                valid = False
                                break
                        if not valid:
                            break
                        if not _space_base_is_supported(
                            Space(
                                placement.x,
                                placement.y,
                                placement.z,
                                placement.l,
                                placement.w,
                                placement.h,
                            ),
                            virtual,
                        ):
                            valid = False
                            break
                    if not valid:
                        continue

                    current_layer = [placements[index] for index in ordered_indexes]
                    proposed_layer = [virtual[index] for index in ordered_indexes]
                    if (
                        _maximum_layer_regularity_metrics(proposed_layer)
                        >= _maximum_layer_regularity_metrics(current_layer)
                    ):
                        continue

                    for index in ordered_indexes:
                        placements[index] = virtual[index]
                    moved_layers += 1
                    moved_placements += len(ordered_indexes)

    return {
        "regularized_layers": moved_layers,
        "regularized_placements": moved_placements,
    }


# =========================================================
# SPACE EVENLY
# =========================================================

# Space Evenly deliberately has its own bounded construction path.  These
# limits cap heuristic breadth; they are not physical limits on requested
# quantity or on the number of product rows.
_SPACE_EVENLY_BLOCK_SHAPE_LIMIT = 24
_SPACE_EVENLY_ANCHOR_AXIS_LIMIT = 24
_SPACE_EVENLY_ANCHOR_Z_LIMIT = 16
_SPACE_EVENLY_CEILING_LIMIT = 128


def _space_evenly_projection_gain(
    footprint: Tuple[float, float, float, float],
    placements: List[Placement],
) -> float:
    """Return footprint area not already used by the cargo projection."""
    remaining = [footprint]
    for placement in placements:
        blocker = (
            placement.x,
            placement.y,
            placement.l,
            placement.w,
        )
        updated = []
        for rectangle in remaining:
            updated.extend(_subtract_rect_2d(rectangle, blocker))
        remaining = updated
        if not remaining:
            return 0.0
    return sum(length * width for x, y, length, width in remaining)


def _space_evenly_block_shapes(
    max_counts: Tuple[int, int, int],
    qty_limit: int,
    *,
    stackable: bool,
) -> List[Tuple[int, int, int]]:
    """Generate a bounded family of useful homogeneous block shapes."""
    if qty_limit <= 1 or any(count <= 0 for count in max_counts):
        return []

    maximum = list(max_counts)
    if not stackable:
        maximum[2] = min(maximum[2], 1)
    max_counts = tuple(maximum)

    candidates = set(_grid_shape_candidates(max_counts, qty_limit))

    # Explicit low/wide and single-layer families.  The generic grid helper
    # already supplies maximum, balanced, and axis-dominant variants.
    floor_counts = (max_counts[0], max_counts[1], 1)
    candidates.update(_grid_shape_candidates(floor_counts, qty_limit))

    # Small structured blocks keep the block phase useful for residual
    # quantities without disguising a lone unit as a block.
    for counts in (
        (min(max_counts[0], 2), 1, 1),
        (1, min(max_counts[1], 2), 1),
        (1, 1, min(max_counts[2], 2)),
    ):
        if 1 < math.prod(counts) <= qty_limit:
            candidates.add(counts)

    valid = [
        counts
        for counts in candidates
        if 1 < math.prod(counts) <= qty_limit
        and all(counts[axis] <= max_counts[axis] for axis in range(3))
    ]

    def shape_key(counts):
        nx, ny, nz = counts
        dimensions = [value for value in counts if value > 0]
        aspect = max(dimensions) / min(dimensions)
        return (
            -math.prod(counts),
            -(nx * ny),
            nz,
            aspect,
            counts,
        )

    return sorted(valid, key=shape_key)[:_SPACE_EVENLY_BLOCK_SHAPE_LIMIT]


def _space_evenly_anchor_positions(
    placements: List[Placement],
    dimensions: Tuple[float, float, float],
    container: Dict,
    effective_height: float,
) -> List[Tuple[float, float, float]]:
    """Generate physical cargo-face anchors under an artificial ceiling."""
    length, width, height = dimensions
    container_length = float(container["L"])
    container_width = float(container["W"])

    z_values = {0.0}
    for placement in placements:
        top = placement.z + placement.h
        if placement.stackable and top + height <= effective_height + _EPS:
            z_values.add(round(top, 9))
    z_levels = _bounded_anchor_values(
        z_values,
        0.0,
        max(effective_height - height, 0.0),
        _SPACE_EVENLY_ANCHOR_Z_LIMIT,
    )

    anchors = set()
    for z in z_levels:
        if z <= _EPS:
            relevant = placements
            x_values = {0.0, max(container_length - length, 0.0)}
            y_values = {0.0, max(container_width - width, 0.0)}
        else:
            relevant = [
                placement
                for placement in placements
                if placement.stackable
                and abs(placement.z + placement.h - z) <= _EPS
            ]
            if not relevant:
                continue
            x_values = set()
            y_values = set()

        for placement in relevant:
            x_values.update({
                placement.x,
                placement.x + placement.l,
                placement.x - length,
                placement.x + placement.l - length,
            })
            y_values.update({
                placement.y,
                placement.y + placement.w,
                placement.y - width,
                placement.y + placement.w - width,
            })

        bounded_x = _bounded_anchor_values(
            x_values,
            0.0,
            max(container_length - length, 0.0),
            _SPACE_EVENLY_ANCHOR_AXIS_LIMIT,
        )
        bounded_y = _bounded_anchor_values(
            y_values,
            0.0,
            max(container_width - width, 0.0),
            _SPACE_EVENLY_ANCHOR_AXIS_LIMIT,
        )
        for x in bounded_x:
            for y in bounded_y:
                anchors.add((x, y, z))

    return sorted(anchors, key=lambda point: (point[2], point[0], point[1]))


def _space_evenly_materialized_block(
    group: Dict,
    orientation: Tuple[float, float, float],
    counts: Tuple[int, int, int],
    origin: Tuple[float, float, float],
    item_index_start: int,
) -> List[Placement]:
    """Materialize one homogeneous block into authoritative placements."""
    origin_space = Space(
        origin[0],
        origin[1],
        origin[2],
        orientation[0] * counts[0],
        orientation[1] * counts[1],
        orientation[2] * counts[2],
    )
    raw = _materialize_grid(origin_space, orientation, counts)
    return [
        Placement(
            product_name=group["name"],
            item_index=item_index_start + offset,
            row_index=group["row_index"],
            sequence=group["sequence"],
            weight=group["weight"],
            stackable=bool(group.get("stackable", True)),
            x=x,
            y=y,
            z=z,
            l=length,
            w=width,
            h=height,
        )
        for offset, (x, y, z, length, width, height) in enumerate(raw)
    ]


def _space_evenly_placements_are_valid(
    candidates: List[Placement],
    placements: List[Placement],
    container: Dict,
    effective_height: float,
) -> bool:
    """Validate block units in materialization order, including support."""
    accepted = list(placements)
    for candidate in candidates:
        if (
            candidate.x < -_EPS
            or candidate.y < -_EPS
            or candidate.z < -_EPS
            or candidate.x + candidate.l > float(container["L"]) + _EPS
            or candidate.y + candidate.w > float(container["W"]) + _EPS
            or candidate.z + candidate.h > effective_height + _EPS
        ):
            return False
        if any(_placements_overlap(candidate, existing) for existing in accepted):
            return False
        if not _space_base_is_supported(
            Space(
                candidate.x,
                candidate.y,
                candidate.z,
                candidate.l,
                candidate.w,
                candidate.h,
            ),
            accepted,
        ):
            return False
        accepted.append(candidate)
    return True


def _space_evenly_block_contact(
    candidates: List[Placement],
    placements: List[Placement],
) -> Tuple[float, float]:
    same_product = 0.0
    all_cargo = 0.0
    for candidate in candidates:
        for existing in placements:
            contact = _placement_face_contact_area(candidate, existing)
            all_cargo += contact
            if candidate.row_index == existing.row_index:
                same_product += contact
    return same_product, all_cargo


def _space_evenly_best_block(
    group: Dict,
    remaining_qty: int,
    placements: List[Placement],
    container: Dict,
    effective_height: float,
    item_index_start: int,
) -> Tuple[Optional[List[Placement]], int]:
    """Return the best bounded physical block and candidates evaluated."""
    best = None
    evaluated = 0
    current_height = max(
        (placement.z + placement.h for placement in placements),
        default=0.0,
    )
    current_length = max(
        (placement.x + placement.l for placement in placements),
        default=0.0,
    )
    current_width = max(
        (placement.y + placement.w for placement in placements),
        default=0.0,
    )

    for orientation_index, orientation in enumerate(group["orientations"]):
        max_counts = _max_grid_counts(
            Space(0.0, 0.0, 0.0, container["L"], container["W"], effective_height),
            orientation,
        )
        for counts in _space_evenly_block_shapes(
            max_counts,
            remaining_qty,
            stackable=bool(group.get("stackable", True)),
        ):
            block_dimensions = tuple(
                orientation[axis] * counts[axis]
                for axis in range(3)
            )
            for origin in _space_evenly_anchor_positions(
                placements,
                block_dimensions,
                container,
                effective_height,
            ):
                evaluated += 1
                candidates = _space_evenly_materialized_block(
                    group,
                    orientation,
                    counts,
                    origin,
                    item_index_start,
                )
                if not _space_evenly_placements_are_valid(
                    candidates,
                    placements,
                    container,
                    effective_height,
                ):
                    continue

                block_length, block_width, block_height = block_dimensions
                x, y, z = origin
                projection_gain = _space_evenly_projection_gain(
                    (x, y, block_length, block_width),
                    placements,
                )
                same_contact, all_contact = _space_evenly_block_contact(
                    candidates,
                    placements,
                )
                shape_aspect = max(block_dimensions) / min(block_dimensions)
                resulting_height = max(current_height, z + block_height)
                resulting_length = max(current_length, x + block_length)
                resulting_width = max(current_width, y + block_width)
                score = (
                    len(candidates),
                    projection_gain,
                    -resulting_height,
                    -block_height,
                    -shape_aspect,
                    same_contact,
                    all_contact,
                    -resulting_length,
                    -resulting_width,
                    -z,
                    -x,
                    -y,
                    -orientation_index,
                    tuple(-value for value in counts),
                )
                if best is None or score > best[0]:
                    best = (score, candidates)

    return (best[1] if best is not None else None), evaluated


def _space_evenly_best_residual_unit(
    group: Dict,
    placements: List[Placement],
    container: Dict,
    effective_height: float,
    item_index: int,
) -> Tuple[Optional[Placement], int]:
    """Place one residual unit using physical anchors, never residual walls."""
    best = None
    evaluated = 0
    current_height = max(
        (placement.z + placement.h for placement in placements),
        default=0.0,
    )
    current_length = max(
        (placement.x + placement.l for placement in placements),
        default=0.0,
    )
    current_width = max(
        (placement.y + placement.w for placement in placements),
        default=0.0,
    )

    for orientation_index, orientation in enumerate(group["orientations"]):
        length, width, height = orientation
        for x, y, z in _space_evenly_anchor_positions(
            placements,
            orientation,
            container,
            effective_height,
        ):
            evaluated += 1
            candidate = Placement(
                product_name=group["name"],
                item_index=item_index,
                row_index=group["row_index"],
                sequence=group["sequence"],
                weight=group["weight"],
                stackable=bool(group.get("stackable", True)),
                x=x,
                y=y,
                z=z,
                l=length,
                w=width,
                h=height,
            )
            if not _space_evenly_placements_are_valid(
                [candidate],
                placements,
                container,
                effective_height,
            ):
                continue
            same_contact, all_contact = _space_evenly_block_contact(
                [candidate],
                placements,
            )
            projection_gain = _space_evenly_projection_gain(
                (x, y, length, width),
                placements,
            )
            resulting_height = max(current_height, z + height)
            resulting_length = max(current_length, x + length)
            resulting_width = max(current_width, y + width)
            score = (
                projection_gain,
                -resulting_height,
                same_contact,
                all_contact,
                -resulting_length,
                -resulting_width,
                -z,
                -x,
                -y,
                -orientation_index,
            )
            if best is None or score > best[0]:
                best = (score, candidate)

    return (best[1] if best is not None else None), evaluated


def _space_evenly_construct(
    container: Dict,
    products: List[Dict],
    effective_height: float,
    target_counts: Optional[Dict[int, int]] = None,
) -> Dict:
    """Run one block-first Space Evenly construction at a fixed ceiling."""
    groups = _product_groups(products, respect_sequence=True)
    placements: List[Placement] = []
    loaded_weight = 0.0
    payload_limit = (
        float(container.get("max_weight"))
        if _has_payload_limit(container)
        else None
    )
    packed_counts = {group["row_index"]: 0 for group in groups}
    block_count = 0
    block_packed_units = 0
    residual_packed_units = 0
    block_candidates_evaluated = 0
    residual_candidates_evaluated = 0

    for group in groups:
        row_index = group["row_index"]
        requested = max(0, int(group.get("qty", 0) or 0))
        target = (
            min(requested, max(0, int(target_counts.get(row_index, 0))))
            if target_counts is not None
            else requested
        )

        while packed_counts[row_index] < target:
            remaining = target - packed_counts[row_index]
            if payload_limit is not None and group["weight"] > 0:
                payload_capacity = int(
                    (max(payload_limit - loaded_weight, 0.0) + _EPS)
                    // group["weight"]
                )
                remaining = min(remaining, payload_capacity)
            if remaining <= 1:
                break

            block, evaluated = _space_evenly_best_block(
                group,
                remaining,
                placements,
                container,
                effective_height,
                group["item_index_start"] + packed_counts[row_index],
            )
            block_candidates_evaluated += evaluated
            if not block:
                break
            placements.extend(block)
            packed = len(block)
            packed_counts[row_index] += packed
            loaded_weight += packed * group["weight"]
            block_count += 1
            block_packed_units += packed

        while packed_counts[row_index] < target:
            if (
                payload_limit is not None
                and group["weight"] > 0
                and loaded_weight + group["weight"] > payload_limit + _EPS
            ):
                break
            candidate, evaluated = _space_evenly_best_residual_unit(
                group,
                placements,
                container,
                effective_height,
                group["item_index_start"] + packed_counts[row_index],
            )
            residual_candidates_evaluated += evaluated
            if candidate is None:
                break
            placements.append(candidate)
            packed_counts[row_index] += 1
            loaded_weight += group["weight"]
            residual_packed_units += 1

    unplaced = []
    for group in groups:
        row_index = group["row_index"]
        packed = packed_counts[row_index]
        requested = max(0, int(group.get("qty", 0) or 0))
        for offset in range(requested - packed):
            payload_blocked = (
                payload_limit is not None
                and group["weight"] > 0
                and loaded_weight + group["weight"] > payload_limit + _EPS
            )
            unplaced.append({
                "product_name": group["name"],
                "dims": group["dims"],
                "orientations": group["orientations"],
                "weight": group["weight"],
                "stackable": bool(group.get("stackable", True)),
                "sequence": group["sequence"],
                "item_index": group["item_index_start"] + packed + offset,
                "row_index": row_index,
                "reason": (
                    "Container max payload exceeded"
                    if payload_blocked
                    else "No fitting physical anchor below effective height"
                ),
            })

    full_space = Space(
        0.0,
        0.0,
        0.0,
        float(container["L"]),
        float(container["W"]),
        float(effective_height),
    )
    occupied = [
        (
            placement.x,
            placement.y,
            placement.z,
            placement.l,
            placement.w,
            placement.h,
        )
        for placement in placements
    ]
    spaces = _subtract_cuboids_from_spaces([full_space], occupied)
    return {
        "placements": placements,
        "unplaced": unplaced,
        "spaces": spaces,
        "loaded_weight": loaded_weight,
        "packed_counts": packed_counts,
        "block_count": block_count,
        "block_packed_units": block_packed_units,
        "residual_packed_units": residual_packed_units,
        "block_candidates_evaluated": block_candidates_evaluated,
        "residual_candidates_evaluated": residual_candidates_evaluated,
    }


def _space_evenly_candidate_heights(
    container: Dict,
    products: List[Dict],
    target_counts: Dict[int, int],
    full_height_result: Dict,
) -> Tuple[float, List[float]]:
    """Build a bounded ordered set of physically meaningful ceilings."""
    floor_area = float(container["L"]) * float(container["W"])
    packed_volume = sum(
        placement.l * placement.w * placement.h
        for placement in full_height_result["placements"]
    )
    theoretical_height = packed_volume / floor_area if floor_area > 0 else 0.0
    actual_height = float(container["H"])

    orientation_heights = sorted({
        round(orientation[2], 9)
        for group in _product_groups(products, respect_sequence=True)
        if target_counts.get(group["row_index"], 0) > 0
        for orientation in group["orientations"]
        if orientation[2] > _EPS
    })
    if len(orientation_heights) > 24:
        orientation_heights = _bounded_anchor_values(
            orientation_heights,
            min(orientation_heights),
            max(orientation_heights),
            24,
        )

    levels = {round(actual_height, 9)}
    levels.update(
        round(placement.z + placement.h, 9)
        for placement in full_height_result["placements"]
    )
    total_target = sum(target_counts.values())
    for height in orientation_heights:
        maximum_layers = min(
            int((actual_height + _EPS) // height),
            max(total_target, 1),
            64,
        )
        for layers in range(1, maximum_layers + 1):
            levels.add(round(layers * height, 9))

    for first_index, first in enumerate(orientation_heights):
        for second in orientation_heights[first_index:]:
            if first + second <= actual_height + _EPS:
                levels.add(round(first + second, 9))

    minimum_item_height = min(orientation_heights, default=0.0)
    lower_bound = max(theoretical_height, minimum_item_height)
    ordered = sorted(
        level
        for level in levels
        if lower_bound - _EPS <= level <= actual_height + _EPS
    )
    if not ordered or abs(ordered[-1] - actual_height) > _EPS:
        ordered.append(actual_height)

    if len(ordered) > _SPACE_EVENLY_CEILING_LIMIT:
        indexes = {
            int(round(index * (len(ordered) - 1) / (_SPACE_EVENLY_CEILING_LIMIT - 1)))
            for index in range(_SPACE_EVENLY_CEILING_LIMIT)
        }
        ordered = [ordered[index] for index in sorted(indexes)]
        if abs(ordered[-1] - actual_height) > _EPS:
            ordered[-1] = actual_height

    return theoretical_height, ordered


def _pack_container_space_evenly(container: Dict, products: List[Dict]) -> Dict:
    """Pack through an independent artificial-ceiling, block-first path."""
    actual_height = float(container["H"])
    full_height_result = _space_evenly_construct(
        container,
        products,
        actual_height,
    )
    target_counts = dict(full_height_result["packed_counts"])
    target_total = sum(target_counts.values())
    theoretical_height, candidate_heights = _space_evenly_candidate_heights(
        container,
        products,
        target_counts,
        full_height_result,
    )

    selected = full_height_result
    selected_height = actual_height if target_total else 0.0
    candidates_evaluated = 0
    total_block_candidates_evaluated = full_height_result["block_candidates_evaluated"]
    total_residual_candidates_evaluated = full_height_result["residual_candidates_evaluated"]
    if target_total:
        for candidate_height in candidate_heights:
            candidates_evaluated += 1
            if abs(candidate_height - actual_height) <= _EPS:
                candidate = full_height_result
            else:
                candidate = _space_evenly_construct(
                    container,
                    products,
                    candidate_height,
                    target_counts,
                )
                total_block_candidates_evaluated += candidate["block_candidates_evaluated"]
                total_residual_candidates_evaluated += candidate["residual_candidates_evaluated"]
            if candidate["packed_counts"] == target_counts:
                selected = candidate
                selected_height = candidate_height
                break

    selected.update({
        "strategy": "space_evenly",
        "packing_mode": "space_evenly",
        "sequence_zones": [],
        "space_evenly_effective_height": selected_height,
        "space_evenly_actual_container_height": actual_height,
        "space_evenly_height_reduction": max(actual_height - selected_height, 0.0),
        "space_evenly_theoretical_average_height": theoretical_height,
        "space_evenly_target_total_units": target_total,
        "space_evenly_target_packed_volume": sum(
            placement.l * placement.w * placement.h
            for placement in full_height_result["placements"]
        ),
        "space_evenly_target_counts": {
            str(row_index): target_counts[row_index]
            for row_index in sorted(target_counts)
        },
        "space_evenly_ceiling_candidates_evaluated": candidates_evaluated,
        "space_evenly_ceiling_candidate_count": len(candidate_heights),
        "space_evenly_block_count": selected["block_count"],
        "space_evenly_block_packed_units": selected["block_packed_units"],
        "space_evenly_residual_packed_units": selected["residual_packed_units"],
        "space_evenly_block_candidates_evaluated": selected["block_candidates_evaluated"],
        "space_evenly_residual_candidates_evaluated": selected["residual_candidates_evaluated"],
        "space_evenly_total_block_candidates_evaluated": total_block_candidates_evaluated,
        "space_evenly_total_residual_candidates_evaluated": total_residual_candidates_evaluated,
    })
    return selected


MAXIMUM_UTILIZATION_MODE = "maximum_utilization"
SPACE_EVENLY_MODE = "space_evenly"
ACCESSIBLE_SEQUENCE_LOADING_MODE = "accessible_sequence_loading"
# Legacy internal identifier retained for the existing strict engine.
SEQUENCE_LOADING_MODE = "sequence_loading"
STRICT_SEQUENCE_LOADING_MODE = "strict_sequence_loading"


def _normalize_packing_mode(mode: Optional[str]) -> str:
    value = str(mode or "").strip().lower().replace("-", "_").replace(" ", "_")
    if value in {"space_evenly", "evenly_spaced", "spread_evenly"}:
        return SPACE_EVENLY_MODE
    if value in {
        "accessible_sequence",
        "accessible_sequence_loading",
        "sequence_accessible",
        "sequence_loading_accessible",
        "middle_sequence",
    }:
        return ACCESSIBLE_SEQUENCE_LOADING_MODE
    if value in {
        # ``sequence_loading`` remains the legacy strict identifier so saved
        # sessions and existing integrations preserve their exact geometry.
        "sequence",
        "sequence_loading",
        "sequence_layers",
        "strict_sequence",
        "strict_sequence_loading",
        "operational",
    }:
        return STRICT_SEQUENCE_LOADING_MODE
    return MAXIMUM_UTILIZATION_MODE


def _pack_container_maximum_utilization(container: Dict, products: List[Dict]) -> Dict:
    """Run Maximum Utilization without operational sector boundaries.

    Loading sequence controls processing order only.  The greedy candidate is
    compared with a maximum-only physical-anchor candidate that may use any
    collision-free, fully supported position.  Neither middle nor strict
    Sequence Loading planners, frontiers, transition bands, or compaction
    passes are called from this mode.
    """
    greedy_result = _pack_container_greedy(
        container,
        products,
        respect_sequence=True,
    )
    best_result = greedy_result

    requested_units = sum(
        max(0, int(product.get("qty", 0) or 0))
        for product in products
    )
    has_orientation_choice = any(
        int(product.get("qty", 0) or 0) > 0
        and len(
            allowed_orientations(
                (product["length"], product["width"], product["height"]),
                product["r1"],
                product["r2"],
                product["r3"],
            )
        ) > 1
        for product in products
    )

    if has_orientation_choice and requested_units <= _MAXIMUM_ANCHOR_ITEM_LIMIT:
        anchor_result = _pack_container_maximum_anchor(container, products)
        if _hybrid_score(anchor_result, products) > _hybrid_score(best_result, products):
            best_result = anchor_result

    best_result["packing_mode"] = MAXIMUM_UTILIZATION_MODE
    best_result.setdefault("sequence_zones", [])
    best_result["maximum_uses_sequence_frontier"] = False
    return best_result


def pack_container_sequence_loading(container: Dict, products: List[Dict]) -> Dict:
    """Legacy public entry point for the unchanged strict sequence engine."""
    return _pack_container_sequence_layers(container, products)


def pack_container_accessible_sequence_loading(
    container: Dict,
    products: List[Dict],
) -> Dict:
    """Public entry point for door-accessible inter-zone Sequence Loading."""
    return _pack_container_accessible_sequence_layers(container, products)


def pack_container_strict_sequence_loading(
    container: Dict,
    products: List[Dict],
) -> Dict:
    """Explicit public alias for the unchanged strict sequence engine."""
    return _pack_container_sequence_layers(container, products)


def pack_container(
    container: Dict,
    products: List[Dict],
    mode: Optional[str] = None,
) -> Dict:
    """Pack the Transport Container using one of four explicit modes.

    ``maximum_utilization`` (default)
        Existing sequence-respecting greedy + unrestricted residual engine.
        Every geometrically valid residual may be reused.

    ``space_evenly``
        Preserve the mode's full-height target quantities while searching a
        bounded set of lower artificial ceilings. Construction uses
        homogeneous blocks followed by physical-anchor residual placement.

    ``accessible_sequence_loading``
        New middle mode. Products retain strict sequence, back-to-front
        progression and horizontal layers, while supported door-accessible
        residuals in the previous sequence's final transition band may be
        populated before the next main zone is opened.

    ``sequence_loading`` / ``strict_sequence_loading``
        Existing strict operational engine, unchanged. Only the controlled
        forward floor frontier is carried to later sequences. The legacy
        ``sequence_loading`` identifier remains strict for compatibility.

    The mode can be supplied either as the explicit function argument or as
    ``container["packing_mode"]``. Existing callers that pass no mode retain
    the current Maximum Utilization behaviour.
    """
    selected_mode = _normalize_packing_mode(
        mode if mode is not None else container.get("packing_mode")
    )
    if selected_mode == SPACE_EVENLY_MODE:
        return _pack_container_space_evenly(container, products)
    if selected_mode == ACCESSIBLE_SEQUENCE_LOADING_MODE:
        return _pack_container_accessible_sequence_layers(container, products)
    if selected_mode == STRICT_SEQUENCE_LOADING_MODE:
        return _pack_container_sequence_layers(container, products)
    return _pack_container_maximum_utilization(container, products)


# =========================================================
# SUMMARIES
# =========================================================

def summarize(container: Dict, products: List[Dict], pack_result: Dict) -> Dict:
    placements: List[Placement] = pack_result["placements"]
    unplaced = pack_result["unplaced"]
    loaded_weight = pack_result["loaded_weight"]

    container_volume = container["L"] * container["W"] * container["H"]
    packed_volume = sum(p.l * p.w * p.h for p in placements)

    requested_by_product = {}
    packed_by_product = {}

    for p in products:
        requested_by_product[p["name"]] = requested_by_product.get(p["name"], 0) + p["qty"]

    for pl in placements:
        packed_by_product[pl.product_name] = packed_by_product.get(pl.product_name, 0) + 1

    rows = []
    for p in products:
        rows.append({
            "name": p["name"],
            "length": p["length"],
            "width": p["width"],
            "height": p["height"],
            "qty_requested": p["qty"],
            "qty_packed": packed_by_product.get(p["name"], 0),
            "weight_each": p["weight"],
            "stackable": bool(p.get("stackable", True)),
            "sequence": p["sequence"],
        })

    if placements:
        occupied_length = max(p.x + p.l for p in placements)
        occupied_width = max(p.y + p.w for p in placements)
        occupied_height = max(p.z + p.h for p in placements)
    else:
        occupied_length = occupied_width = occupied_height = 0.0

    tare_weight = container.get("tare_weight")
    payload_limit = container.get("max_weight")
    has_payload_limit = _has_payload_limit(container)
    gross_weight = loaded_weight + (float(tare_weight) if tare_weight is not None else 0.0)

    return {
        "container_volume": container_volume,
        "packed_volume": packed_volume,
        "container_volume_m3": container_volume / 1_000_000_000.0,
        "packed_volume_m3": packed_volume / 1_000_000_000.0,
        "utilization_volume_pct": (100.0 * packed_volume / container_volume) if container_volume > 0 else 0.0,
        "container_max_weight": float(payload_limit) if has_payload_limit else None,
        "has_payload_limit": has_payload_limit,
        "loaded_weight": loaded_weight,
        "tare_weight": float(tare_weight) if tare_weight is not None else None,
        "gross_weight": gross_weight,
        "utilization_weight_pct": (100.0 * loaded_weight / float(payload_limit)) if has_payload_limit else None,
        "placed_units": len(placements),
        "unplaced_units": len(unplaced),
        "occupied_length": occupied_length,
        "occupied_width": occupied_width,
        "occupied_height": occupied_height,
        "residual_length": max(container["L"] - occupied_length, 0.0),
        "residual_width": max(container["W"] - occupied_width, 0.0),
        "residual_height": max(container["H"] - occupied_height, 0.0),
        "product_rows": rows,
    }


# =========================================================
# DRAWING
# =========================================================

def cuboid_faces(x, y, z, l, w, h):
    p0 = [x,     y,     z]
    p1 = [x + l, y,     z]
    p2 = [x + l, y + w, z]
    p3 = [x,     y + w, z]
    p4 = [x,     y,     z + h]
    p5 = [x + l, y,     z + h]
    p6 = [x + l, y + w, z + h]
    p7 = [x,     y + w, z + h]

    return [
        [p0, p1, p2, p3],
        [p4, p5, p6, p7],
        [p0, p1, p5, p4],
        [p1, p2, p6, p5],
        [p2, p3, p7, p6],
        [p3, p0, p4, p7],
    ]


def _color_for_index(idx: int):
    palette = [
        "#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
        "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC",
    ]
    return palette[idx % len(palette)]


def _draw_line(ax, p1, p2, color="#333333", linewidth=1.0, alpha=1.0):
    ax.plot(
        [p1[0], p2[0]],
        [p1[1], p2[1]],
        [p1[2], p2[2]],
        color=color,
        linewidth=linewidth,
        alpha=alpha,
        solid_capstyle="round",
    )


def _draw_container_frame(ax, L, W, H):
    points = {
        "000": (0, 0, 0),
        "100": (L, 0, 0),
        "110": (L, W, 0),
        "010": (0, W, 0),
        "001": (0, 0, H),
        "101": (L, 0, H),
        "111": (L, W, H),
        "011": (0, W, H),
    }
    edges = [
        ("000", "100"), ("100", "110"), ("110", "010"), ("010", "000"),
        ("001", "101"), ("101", "111"), ("111", "011"), ("011", "001"),
        ("000", "001"), ("100", "101"), ("110", "111"), ("010", "011"),
    ]
    for a, b in edges:
        _draw_line(ax, points[a], points[b], color="#202020", linewidth=1.1, alpha=0.95)


def _draw_open_doors(ax, x_face, W, H, angle_deg=135):
    theta = math.radians(angle_deg)
    half_w = W / 2.0

    left_outer_x = x_face + (half_w * math.sin(theta))
    left_outer_y = half_w * math.cos(theta)
    right_outer_x = x_face + (half_w * math.sin(theta))
    right_outer_y = W - (half_w * math.cos(theta))

    left_door = [
        (x_face, 0, 0),
        (left_outer_x, left_outer_y, 0),
        (left_outer_x, left_outer_y, H),
        (x_face, 0, H),
    ]
    right_door = [
        (x_face, W, 0),
        (right_outer_x, right_outer_y, 0),
        (right_outer_x, right_outer_y, H),
        (x_face, W, H),
    ]

    door_poly = Poly3DCollection(
        [left_door, right_door],
        facecolors=["#d8d8d8", "#d8d8d8"],
        edgecolors="#5a5a5a",
        linewidths=1.0,
        alpha=0.35,
    )
    ax.add_collection3d(door_poly)

    for door in (left_door, right_door):
        for i in range(len(door)):
            _draw_line(ax, door[i], door[(i + 1) % len(door)], color="#555555", linewidth=1.0, alpha=0.9)

    # central opening edge for the door frame
    _draw_line(ax, (x_face, W / 2.0, 0), (x_face, W / 2.0, H), color="#444444", linewidth=0.9, alpha=0.8)

    return abs(left_outer_x - x_face), abs(left_outer_y)


def _camera_for_view(view: str):
    views = {
        "main": {"elev": 18, "azim": -58, "dist": 7.5},
        "opposite": {"elev": 18, "azim": 122, "dist": 7.5},
        "top": {"elev": 88, "azim": -90, "dist": 8.2},
        "side": {"elev": 12, "azim": 0, "dist": 7.8},
    }
    return views.get(view, views["main"])


def draw_container(container: Dict, placements: List[Placement], output_path: str, view: str = "main"):
    scale = 1000.0  # mm -> m

    fig = plt.figure(figsize=(16, 6), facecolor="white")
    ax = fig.add_axes([0.01, 0.01, 0.98, 0.98], projection="3d")
    ax.set_facecolor("white")

    L = container["L"] / scale
    W = container["W"] / scale
    H = container["H"] / scale

    product_names = []
    for p in placements:
        if p.product_name not in product_names:
            product_names.append(p.product_name)

    color_map = {name: _color_for_index(i) for i, name in enumerate(product_names)}

    for pl in placements:
        x = pl.x / scale
        y = pl.y / scale
        z = pl.z / scale
        l = pl.l / scale
        w = pl.w / scale
        h = pl.h / scale

        faces = cuboid_faces(x, y, z, l, w, h)
        poly = Poly3DCollection(
            faces,
            facecolors=color_map.get(pl.product_name, "#AAAAAA"),
            edgecolors="#2c2c2c",
            linewidths=0.35,
            alpha=0.78,
        )
        ax.add_collection3d(poly)

    # subtle floor shading for better depth perception
    floor = Poly3DCollection(
        [[(0, 0, 0), (L, 0, 0), (L, W, 0), (0, W, 0)]],
        facecolors="#f2f2f2",
        edgecolors="none",
        alpha=0.25,
    )
    ax.add_collection3d(floor)

    _draw_container_frame(ax, L, W, H)
    door_x_span, door_y_span = _draw_open_doors(ax, L, W, H, angle_deg=135)

    x_pad_left = max(L * 0.015, 0.08)
    x_pad_right = max(door_x_span + 0.08, L * 0.015)
    y_pad = max(W * 0.03, 0.05)
    z_pad = max(H * 0.02, 0.04)

    ax.set_xlim(-x_pad_left, L + x_pad_right)
    ax.set_ylim(-y_pad, W + y_pad)
    ax.set_zlim(0, H + z_pad)

    try:
        ax.set_box_aspect((L + x_pad_left + x_pad_right, W + 2 * y_pad, H + z_pad))
    except Exception:
        pass

    camera = _camera_for_view(view)
    ax.view_init(elev=camera["elev"], azim=camera["azim"])
    try:
        ax.dist = camera["dist"]
    except Exception:
        pass
    ax.set_axis_off()
    ax.grid(False)

    plt.subplots_adjust(left=0, right=1, bottom=0, top=1)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", pad_inches=0.0)
    plt.close(fig)
    _trim_and_fit_render(output_path)




def _trim_and_fit_render(output_path: str, canvas_size=(1600, 700), margin_ratio=0.04):
    img = Image.open(output_path).convert("RGB")
    bg = Image.new("RGB", img.size, "white")
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()

    if bbox:
        img = img.crop(bbox)

    canvas_w, canvas_h = canvas_size
    max_w = int(canvas_w * (1 - 2 * margin_ratio))
    max_h = int(canvas_h * (1 - 2 * margin_ratio))

    scale = min(max_w / img.width, max_h / img.height)
    new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    img = img.resize(new_size, Image.LANCZOS)

    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    x = (canvas_w - img.width) // 2
    y = (canvas_h - img.height) // 2
    canvas.paste(img, (x, y))
    canvas.save(output_path)

# =========================================================
# MAIN WRAPPER
# =========================================================

def run_container_tool(container: Dict, products: List[Dict], media_root: str) -> Dict:
    pack_result = pack_container(container, products)
    summary = summarize(container, products, pack_result)

    rel_dir = os.path.join("generated", "container_tool")
    abs_dir = os.path.join(media_root, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    file_stub = f"container_tool_{uuid.uuid4().hex[:12]}"
    view_order = ["main", "opposite", "top", "side"]
    image_rel_paths = {}

    for view_name in view_order:
        file_name = f"{file_stub}_{view_name}.png"
        abs_path = os.path.join(abs_dir, file_name)
        rel_path = os.path.join(rel_dir, file_name).replace("\\", "/")
        draw_container(container, pack_result["placements"], abs_path, view=view_name)
        image_rel_paths[view_name] = rel_path

    result = {
        "summary": summary,
        "placements": pack_result["placements"],
        "unplaced": pack_result["unplaced"],
        "spaces": pack_result.get("spaces") or [],
        "strategy": pack_result.get("strategy", ""),
        "packing_mode": pack_result.get("packing_mode", MAXIMUM_UTILIZATION_MODE),
        "sequence_zones": pack_result.get("sequence_zones") or [],
        "image_rel_path": image_rel_paths.get("main"),
        "image_rel_paths": image_rel_paths,
    }
    result.update({
        key: value
        for key, value in pack_result.items()
        if key.startswith("space_evenly_")
    })
    return result
