# packagingapp/utils/container_tool/engine.py
"""Deterministic block-based Transport Container packing engines.

Space Evenly and Load Front-to-Back use the same normalized product and block
mathematics.  Their orchestration is intentionally separate.  Historical
algorithms are preserved in ``engine_legacy.py`` and are never imported here.
"""

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Optional, Tuple

from packagingapp.tools.transport.modes import (
    FRONT_TO_BACK_INFILL_MODE,
    FRONT_TO_BACK_MODE,
    SPACE_EVENLY_INFILL_MODE,
    SPACE_EVENLY_MODE,
    normalize_transport_packing_mode,
)


TOLERANCE = 1e-7
FRONTIER_EFFICIENCY_TOLERANCE = 1e-9
YZ_UTILIZATION_EQ_TOL = 0.0025
RESIDUAL_WIDTH_UTILIZATION_EQ_TOL = 0.001
FRONT_TO_BACK_STRATEGY = "front_to_back_blocks"
DGFE_RESIDUAL_STRATEGIES = (
    "top_down_column_first",
    "top_down_row_first",
    "bottom_up_column_first",
    "bottom_up_row_first",
)
SPACE_EVENLY_RESIDUAL_STRATEGIES = (
    "bottom_up_row_first",
    "top_down_row_first",
)
DGFE_POSITION_DIAGNOSTIC_LIMIT = 64
UNSUPPORTED_MODE_MESSAGE = (
    "Only Space Evenly and Load Front-to-Back are currently available."
)


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
        return (
            l <= self.L + TOLERANCE
            and w <= self.W + TOLERANCE
            and h <= self.H + TOLERANCE
        )


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


@dataclass(frozen=True)
class NormalizedProduct:
    name: str
    length: float
    width: float
    height: float
    qty: int
    weight: float
    stackable: bool
    sequence: int
    r1: bool
    r2: bool
    r3: bool
    row_index: int
    input_order: int
    orientations: Tuple[Tuple[float, float, float], ...]

    @property
    def unit_volume(self) -> float:
        return self.length * self.width * self.height

    @property
    def longest_dimension(self) -> float:
        return max(self.length, self.width, self.height)


@dataclass(frozen=True)
class ProductBlockCandidate:
    pattern: str
    orientations: Tuple[Tuple[float, float, float], ...]
    orientation_indices: Tuple[int, ...]
    lane_counts: Tuple[int, ...]
    x_repetitions: Tuple[int, ...]
    nz: int
    depth: float
    occupied_width: float
    occupied_height: float
    module_capacity: int
    transverse_capacity: int
    transverse_utilization: float


@dataclass
class SupportSurface:
    surface_index: int
    x: float
    y: float
    z: float
    length: float
    width: float
    product: NormalizedProduct
    orientation_index: int
    source_placement_count: int

    @property
    def stackable(self) -> bool:
        return self.product.stackable


@dataclass(frozen=True)
class ResidualOrientationRun:
    orientation_index: int
    orientation: Tuple[float, float, float]
    quantity: int
    occupied_width: float


@dataclass(frozen=True)
class ResidualRowPlan:
    product: NormalizedProduct
    runs: Tuple[ResidualOrientationRun, ...]
    available_width: float
    occupied_width: float
    width_utilization: float
    support_potential: int


def allowed_orientations(
    dims: Tuple[float, float, float],
    r1: bool,
    r2: bool,
    r3: bool,
) -> List[Tuple[float, float, float]]:
    """Return enabled axis-aligned orientations in stable R1/R2/R3 order."""
    length, width, height = (float(value) for value in dims)
    rotations: List[Tuple[float, float, float]] = []

    if r1:
        rotations.extend(((length, width, height), (width, length, height)))
    if r2:
        rotations.extend(((length, height, width), (height, length, width)))
    if r3:
        rotations.extend(((width, height, length), (height, width, length)))

    unique: List[Tuple[float, float, float]] = []
    seen = set()
    for rotation in rotations:
        key = tuple(round(value, 9) for value in rotation)
        if key not in seen:
            seen.add(key)
            unique.append(rotation)
    return unique


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "on", "yes"}
    return bool(value)


def _fit_count(available: float, unit: float) -> int:
    if available <= 0 or unit <= 0:
        return 0
    return max(0, int(math.floor((available + TOLERANCE) / unit)))


def _normalize_container(container: Dict) -> Dict:
    normalized = dict(container or {})
    try:
        normalized["L"] = float(normalized["L"])
        normalized["W"] = float(normalized["W"])
        normalized["H"] = float(normalized["H"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Container L, W and H must be valid numbers.") from exc

    if any(normalized[axis] <= 0 for axis in ("L", "W", "H")):
        raise ValueError("Container L, W and H must be greater than zero.")

    for key in ("max_weight", "tare_weight"):
        value = normalized.get(key)
        if value in (None, ""):
            normalized[key] = None
        else:
            normalized[key] = float(value)
            if normalized[key] < 0:
                raise ValueError(f"Container {key} cannot be negative.")
    return normalized


def normalize_products(products: List[Dict]) -> List[NormalizedProduct]:
    """Normalize inputs without changing their original row identity."""
    normalized: List[NormalizedProduct] = []
    for input_order, raw in enumerate(products or []):
        try:
            length = float(raw["length"])
            width = float(raw["width"])
            height = float(raw["height"])
            qty = int(float(raw.get("qty", 0) or 0))
            weight = float(raw.get("weight", 0) or 0)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Product row {input_order + 1} has invalid dimensions, quantity or weight."
            ) from exc

        if min(length, width, height) <= 0:
            raise ValueError(f"Product row {input_order + 1} dimensions must be positive.")
        if qty < 0:
            raise ValueError(f"Product row {input_order + 1} quantity cannot be negative.")
        if weight < 0:
            raise ValueError(f"Product row {input_order + 1} weight cannot be negative.")

        raw_sequence = raw.get("sequence", 1)
        sequence = 1 if raw_sequence in (None, "") else int(float(raw_sequence))
        r1 = _as_bool(raw.get("r1", False))
        r2 = _as_bool(raw.get("r2", False))
        r3 = _as_bool(raw.get("r3", False))
        orientations = tuple(
            allowed_orientations((length, width, height), r1, r2, r3)
        )

        normalized.append(
            NormalizedProduct(
                name=str(raw.get("name") or f"Product {input_order + 1}"),
                length=length,
                width=width,
                height=height,
                qty=qty,
                weight=weight,
                stackable=_as_bool(raw.get("stackable", True)),
                sequence=sequence,
                r1=r1,
                r2=r2,
                r3=r3,
                row_index=int(raw.get("_row_index", input_order)),
                input_order=input_order,
                orientations=orientations,
            )
        )
    return normalized


def _largest_valid_footprint(product: NormalizedProduct, container: Dict) -> float:
    valid = [
        orientation[0] * orientation[1]
        for orientation in product.orientations
        if orientation[0] <= container["L"] + TOLERANCE
        and orientation[1] <= container["W"] + TOLERANCE
        and orientation[2] <= container["H"] + TOLERANCE
    ]
    return max(valid, default=0.0)


def sort_products(
    products: List[NormalizedProduct],
    container: Dict,
) -> List[NormalizedProduct]:
    """Apply universal sequence and same-sequence size priority."""
    return sorted(
        products,
        key=lambda product: (
            product.sequence,
            -_largest_valid_footprint(product, container),
            -product.unit_volume,
            -product.longest_dimension,
            product.input_order,
        ),
    )


def _candidate_stable_key(candidate: ProductBlockCandidate) -> Tuple:
    stable_orientations = tuple(
        tuple(round(value, 9) for value in orientation)
        for orientation in candidate.orientations
    )
    return (
        candidate.orientation_indices,
        candidate.lane_counts,
        candidate.x_repetitions,
        candidate.nz,
        round(candidate.depth, 9),
        round(candidate.occupied_width, 9),
        round(candidate.occupied_height, 9),
        stable_orientations,
    )


def _best_single_orientation_block(
    orientation: Tuple[float, float, float],
    orientation_index: int,
    product: NormalizedProduct,
    container: Dict,
    max_depth: float,
) -> Tuple[Optional[ProductBlockCandidate], int]:
    depth, lane_width, unit_height = orientation
    if depth > max_depth + TOLERANCE:
        return None, 0

    max_ny = _fit_count(container["W"], lane_width)
    max_nz = _fit_count(container["H"], unit_height)
    if not product.stackable:
        max_nz = min(max_nz, 1)
    if min(max_ny, max_nz) <= 0:
        return None, 0

    transverse_capacity = max_ny * max_nz
    occupied_width = max_ny * lane_width
    occupied_height = max_nz * unit_height
    return ProductBlockCandidate(
        pattern="single_orientation",
        orientations=(orientation,),
        orientation_indices=(orientation_index,),
        lane_counts=(max_ny,),
        x_repetitions=(1,),
        nz=max_nz,
        depth=depth,
        occupied_width=occupied_width,
        occupied_height=occupied_height,
        module_capacity=transverse_capacity,
        transverse_capacity=transverse_capacity,
        transverse_utilization=(
            occupied_width
            * occupied_height
            / (container["W"] * container["H"])
        ),
    ), 1


def _synchronized_depth(
    first_depth: float,
    second_depth: float,
) -> Optional[Tuple[float, int, int]]:
    """Find the smallest exact decimal common depth algebraically."""
    first = Fraction(str(first_depth)).limit_denominator(1_000_000)
    second = Fraction(str(second_depth)).limit_denominator(1_000_000)
    numerator = math.lcm(first.numerator, second.numerator)
    denominator = math.gcd(first.denominator, second.denominator)
    common = Fraction(numerator, denominator)
    first_repetitions = common / first
    second_repetitions = common / second
    if first_repetitions.denominator != 1 or second_repetitions.denominator != 1:
        return None
    return (
        float(common),
        int(first_repetitions),
        int(second_repetitions),
    )


def _mixed_orientation_blocks(
    first: Tuple[float, float, float],
    second: Tuple[float, float, float],
    first_index: int,
    second_index: int,
    product: NormalizedProduct,
    container: Dict,
    max_depth: float,
) -> Tuple[List[ProductBlockCandidate], int]:
    if abs(first[2] - second[2]) > TOLERANCE:
        return [], 0

    synchronized = _synchronized_depth(first[0], second[0])
    if synchronized is None:
        return [], 0
    depth, first_repetitions, second_repetitions = synchronized
    if depth > max_depth + TOLERANCE:
        return [], 0

    max_nz = _fit_count(container["H"], first[2])
    if not product.stackable:
        max_nz = min(max_nz, 1)
    if max_nz <= 0:
        return [], 0

    max_first_lanes = _fit_count(container["W"] - second[1], first[1])
    candidates = []
    evaluated = 0

    for first_lanes in range(1, max_first_lanes + 1):
        remaining_width = container["W"] - first_lanes * first[1]
        max_second_lanes = _fit_count(remaining_width, second[1])
        for second_lanes in range(1, max_second_lanes + 1):
            transverse_capacity = (first_lanes + second_lanes) * max_nz
            module_capacity = max_nz * (
                first_lanes * first_repetitions
                + second_lanes * second_repetitions
            )
            occupied_width = first_lanes * first[1] + second_lanes * second[1]
            occupied_height = max_nz * first[2]
            candidates.append(
                ProductBlockCandidate(
                    pattern="synchronized_mixed_orientation",
                    orientations=(first, second),
                    orientation_indices=(first_index, second_index),
                    lane_counts=(first_lanes, second_lanes),
                    x_repetitions=(first_repetitions, second_repetitions),
                    nz=max_nz,
                    depth=depth,
                    occupied_width=occupied_width,
                    occupied_height=occupied_height,
                    module_capacity=module_capacity,
                    transverse_capacity=transverse_capacity,
                    transverse_utilization=(
                        occupied_width
                        * occupied_height
                        / (container["W"] * container["H"])
                    ),
                )
            )
            evaluated += 1
    return candidates, evaluated


def build_product_block_candidates(
    product: NormalizedProduct,
    container: Dict,
    max_depth: float,
) -> Tuple[List[ProductBlockCandidate], int]:
    """Build quantity-independent YZ candidates for each orientation/pair."""
    candidates: List[ProductBlockCandidate] = []
    evaluated = 0

    for index, orientation in enumerate(product.orientations):
        candidate, count = _best_single_orientation_block(
            orientation,
            index,
            product,
            container,
            max_depth,
        )
        evaluated += count
        if candidate is not None:
            candidates.append(candidate)

    for first_index in range(len(product.orientations)):
        for second_index in range(first_index + 1, len(product.orientations)):
            mixed_candidates, count = _mixed_orientation_blocks(
                product.orientations[first_index],
                product.orientations[second_index],
                first_index,
                second_index,
                product,
                container,
                max_depth,
            )
            evaluated += count
            candidates.extend(mixed_candidates)

    candidates.sort(key=_candidate_stable_key)
    return candidates, evaluated


def _regular_candidate_is_eligible(
    candidate: ProductBlockCandidate,
    feasible_qty: int,
    remaining_length: float,
) -> bool:
    return (
        candidate.module_capacity <= feasible_qty
        and candidate.depth <= remaining_length + TOLERANCE
    )


def _geometrically_equivalent(
    first: ProductBlockCandidate,
    second: ProductBlockCandidate,
) -> bool:
    return (
        first.transverse_capacity == second.transverse_capacity
        and abs(first.depth - second.depth) <= TOLERANCE
        and abs(first.occupied_width - second.occupied_width) <= TOLERANCE
        and abs(first.occupied_height - second.occupied_height) <= TOLERANCE
    )


def choose_product_block(
    candidates: List[ProductBlockCandidate],
    feasible_qty: int,
    remaining_length: float,
) -> Optional[ProductBlockCandidate]:
    eligible = [
        candidate
        for candidate in candidates
        if _regular_candidate_is_eligible(
            candidate,
            feasible_qty,
            remaining_length,
        )
    ]
    if not eligible:
        return None

    best_utilization = max(
        candidate.transverse_utilization for candidate in eligible
    )
    shortlisted = [
        candidate
        for candidate in eligible
        if best_utilization - candidate.transverse_utilization
        <= YZ_UTILIZATION_EQ_TOL
    ]

    best_transverse_capacity = max(
        candidate.transverse_capacity for candidate in shortlisted
    )
    shortlisted = [
        candidate
        for candidate in shortlisted
        if candidate.transverse_capacity == best_transverse_capacity
    ]

    minimum_depth = min(candidate.depth for candidate in shortlisted)
    shortlisted = [
        candidate
        for candidate in shortlisted
        if abs(candidate.depth - minimum_depth) <= TOLERANCE
    ]

    single_orientation_candidates = [
        candidate
        for candidate in shortlisted
        if len(candidate.orientations) == 1
    ]
    shortlisted = [
        candidate
        for candidate in shortlisted
        if len(candidate.orientations) == 1
        or not any(
            _geometrically_equivalent(candidate, single)
            for single in single_orientation_candidates
        )
    ]
    return min(shortlisted, key=_candidate_stable_key)


def _candidate_metadata(candidate: ProductBlockCandidate) -> Dict:
    lanes = []
    for orientation, lane_count, repetitions in zip(
        candidate.orientations,
        candidate.lane_counts,
        candidate.x_repetitions,
    ):
        lanes.append(
            {
                "orientation": [float(value) for value in orientation],
                "lane_count": int(lane_count),
                "x_repetitions": int(repetitions),
            }
        )
    return {
        "pattern": candidate.pattern,
        # Compatibility aliases retained for consumers that previously saw a
        # single-orientation homogeneous grid.  ``orientations`` and ``lanes``
        # remain authoritative for synchronized mixed blocks.
        "orientation": [float(value) for value in candidate.orientations[0]],
        "nx": (
            int(candidate.x_repetitions[0])
            if len(candidate.orientations) == 1
            else int(max(candidate.x_repetitions))
        ),
        "y_start": 0.0,
        "orientations": [
            [float(value) for value in orientation]
            for orientation in candidate.orientations
        ],
        "lanes": lanes,
        "ny": int(sum(candidate.lane_counts)),
        "nz": int(candidate.nz),
        "depth": float(candidate.depth),
        "width": float(candidate.occupied_width),
        "height": float(candidate.occupied_height),
        "capacity": int(candidate.module_capacity),
        "module_capacity": int(candidate.module_capacity),
        "transverse_capacity": int(candidate.transverse_capacity),
        "transverse_utilization": float(candidate.transverse_utilization),
    }


def _materialize_product_block(
    product: NormalizedProduct,
    candidate: ProductBlockCandidate,
    x_start: float,
    first_item_index: int,
) -> List[Placement]:
    """Materialize known block coordinates, ordered y then z then x."""
    cells = []
    y_start = 0.0
    for group_index, (orientation, lane_count, repetitions) in enumerate(
        zip(
            candidate.orientations,
            candidate.lane_counts,
            candidate.x_repetitions,
        )
    ):
        depth, lane_width, unit_height = orientation
        for lane_index in range(lane_count):
            y = y_start + lane_index * lane_width
            for x_index in range(repetitions):
                for z_index in range(candidate.nz):
                    cells.append(
                        (
                            x_index * depth,
                            z_index * unit_height,
                            y,
                            group_index,
                            orientation,
                        )
                    )
        y_start += lane_count * lane_width

    cells.sort(
        key=lambda cell: (
            round(cell[0], 9),
            round(cell[1], 9),
            round(cell[2], 9),
            cell[3],
        )
    )
    placements = []
    for offset, (local_x, z, y, _group_index, orientation) in enumerate(cells):
        placements.append(
            Placement(
                product_name=product.name,
                item_index=first_item_index + offset,
                row_index=product.row_index,
                sequence=product.sequence,
                weight=product.weight,
                stackable=product.stackable,
                x=x_start + local_x,
                y=y,
                z=z,
                l=orientation[0],
                w=orientation[1],
                h=orientation[2],
            )
        )
    return placements


def _materialize_product_block_in_space(
    product: NormalizedProduct,
    candidate: ProductBlockCandidate,
    space: Space,
    first_item_index: int,
    quantity: int,
) -> List[Placement]:
    """Materialize a Product Block at XYZ offsets with stable item ordering."""
    maximum_modules = _fit_count(space.L, candidate.depth)
    maximum_quantity = maximum_modules * candidate.module_capacity
    target_quantity = min(max(int(quantity), 0), maximum_quantity)
    placements: List[Placement] = []

    for module_index in range(maximum_modules):
        if len(placements) >= target_quantity:
            break
        module = _materialize_product_block(
            product,
            candidate,
            space.x + module_index * candidate.depth,
            first_item_index + len(placements),
        )
        for placement in module[: target_quantity - len(placements)]:
            placements.append(
                Placement(
                    product_name=placement.product_name,
                    item_index=placement.item_index,
                    row_index=placement.row_index,
                    sequence=placement.sequence,
                    weight=placement.weight,
                    stackable=placement.stackable,
                    x=placement.x,
                    y=space.y + placement.y,
                    z=space.z + placement.z,
                    l=placement.l,
                    w=placement.w,
                    h=placement.h,
                )
            )
    return placements


def _support_orientation_key(orientation: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return tuple(round(float(value), 9) for value in orientation)


def _build_support_matrix(
    products: List[NormalizedProduct],
) -> Dict[Tuple[int, int, Tuple[float, float, float]], bool]:
    """Precompute orientation-aware XY support compatibility for one group."""
    matrix: Dict[Tuple[int, int, Tuple[float, float, float]], bool] = {}
    for supporter in products:
        for supporter_index, supporter_orientation in enumerate(
            supporter.orientations
        ):
            for upper in products:
                for upper_orientation in upper.orientations:
                    matrix[
                        (
                            supporter.row_index,
                            supporter_index,
                            _support_orientation_key(upper_orientation),
                        )
                    ] = bool(
                        supporter.stackable
                        and upper_orientation[0]
                        <= supporter_orientation[0] + TOLERANCE
                        and upper_orientation[1]
                        <= supporter_orientation[1] + TOLERANCE
                    )
    return matrix


def _surface_accepts_orientation(
    surface: SupportSurface,
    orientation: Tuple[float, float, float],
    container: Dict,
    stats: Dict[str, int],
) -> bool:
    stats["support_checks"] += 1
    # A residual support surface may represent a contiguous run of lower
    # units, but V1 support is deliberately per-unit: an upper item may not
    # bridge across two adjacent supporters.  Use the actual lower unit's
    # footprint, not the aggregate run width, for the XY containment check.
    supporter_orientation = surface.product.orientations[surface.orientation_index]
    strict_single_support = bool(stats.get("strict_single_support", True))
    matrix = stats.get("support_matrix")
    matrix_key = (
        surface.product.row_index,
        surface.orientation_index,
        _support_orientation_key(orientation),
    )
    xy_compatible = (
        matrix.get(matrix_key)
        if strict_single_support
        and isinstance(matrix, dict)
        and matrix_key in matrix
        else (
            orientation[0] <= supporter_orientation[0] + TOLERANCE
            and orientation[1] <= supporter_orientation[1] + TOLERANCE
            if strict_single_support
            else (
                orientation[0] <= surface.length + TOLERANCE
                and orientation[1] <= surface.width + TOLERANCE
            )
        )
    )
    compatible = (
        surface.stackable
        and xy_compatible
        and surface.z + orientation[2] <= container["H"] + TOLERANCE
    )
    if compatible:
        stats["support_relationships"] += 1
    return compatible


def _surface_support_potential(
    surface: SupportSurface,
    products: List[NormalizedProduct],
    remaining: Dict[int, int],
    container: Dict,
    stats: Dict[str, int],
) -> int:
    potential = 0
    for product in products:
        if remaining.get(product.row_index, 0) <= 0:
            continue
        if any(
            _surface_accepts_orientation(surface, orientation, container, stats)
            for orientation in product.orientations
        ):
            potential += 1
    return potential


def _surface_metadata(surface: SupportSurface) -> Dict:
    return {
        "surface_index": surface.surface_index,
        "x": float(surface.x),
        "y": float(surface.y),
        "top_z": float(surface.z),
        "length": float(surface.length),
        "width": float(surface.width),
        "area": float(surface.length * surface.width),
        "row_index": surface.product.row_index,
        "product_name": surface.product.name,
        "orientation_index": surface.orientation_index,
        "orientation": [
            float(value)
            for value in surface.product.orientations[surface.orientation_index]
        ],
        "stackable": surface.stackable,
        "sequence": surface.product.sequence,
        "source_placement_count": surface.source_placement_count,
    }


def _choose_residual_foundation(
    products: List[NormalizedProduct],
    container: Dict,
    remaining: Dict[int, int],
    product_order: Dict[int, int],
    loaded_weight: float,
    frontier: float,
    available_length: float,
    stats: Dict[str, int],
) -> Optional[
    Tuple[
        NormalizedProduct,
        int,
        Tuple[float, float, float],
        int,
        float,
        float,
        int,
    ]
]:
    candidates = []
    for product in products:
        quantity = remaining.get(product.row_index, 0)
        if quantity <= 0:
            continue
        payload_quantity = _payload_units_available(
            container,
            loaded_weight,
            product.weight,
            quantity,
        )
        if payload_quantity <= 0:
            continue
        for orientation_index, orientation in enumerate(product.orientations):
            stats["candidate_evaluations"] += 1
            if (
                orientation[0] > available_length + TOLERANCE
                or orientation[1] > container["W"] + TOLERANCE
                or orientation[2] > container["H"] + TOLERANCE
            ):
                continue
            foundation_quantity = min(
                _fit_count(container["W"], orientation[1]),
                quantity,
                payload_quantity,
            )
            if foundation_quantity <= 0:
                continue
            surface = SupportSurface(
                surface_index=0,
                x=frontier,
                y=0.0,
                z=orientation[2],
                length=orientation[0],
                width=foundation_quantity * orientation[1],
                product=product,
                orientation_index=orientation_index,
                source_placement_count=foundation_quantity,
            )
            simulated_remaining = dict(remaining)
            simulated_remaining[product.row_index] -= foundation_quantity
            potential = _surface_support_potential(
                surface,
                products,
                simulated_remaining,
                container,
                stats,
            )
            occupied_width = foundation_quantity * orientation[1]
            width_utilization = occupied_width / container["W"]
            candidates.append(
                (
                    product,
                    orientation_index,
                    orientation,
                    foundation_quantity,
                    occupied_width,
                    width_utilization,
                    potential,
                )
            )
    if not candidates:
        return None

    # Fix the foundation SKU by support semantics before optimizing its row width.
    product_support_potential = {}
    for candidate in candidates:
        row_index = candidate[0].row_index
        product_support_potential[row_index] = max(
            product_support_potential.get(row_index, 0),
            candidate[6],
        )
    best_product_support = max(product_support_potential.values())
    selected_product = min(
        (
            candidate[0]
            for candidate in candidates
            if product_support_potential[candidate[0].row_index]
            == best_product_support
        ),
        key=lambda product: product_order[product.row_index],
    )
    shortlisted = [
        candidate
        for candidate in candidates
        if candidate[0].row_index == selected_product.row_index
    ]
    best_potential = max(candidate[6] for candidate in shortlisted)
    shortlisted = [
        candidate for candidate in shortlisted if candidate[6] == best_potential
    ]
    best_width_utilization = max(candidate[5] for candidate in shortlisted)
    shortlisted = [
        candidate
        for candidate in shortlisted
        if best_width_utilization - candidate[5]
        <= RESIDUAL_WIDTH_UTILIZATION_EQ_TOL
    ]
    best_quantity = max(candidate[3] for candidate in shortlisted)
    shortlisted = [
        candidate for candidate in shortlisted if candidate[3] == best_quantity
    ]
    minimum_depth = min(candidate[2][0] for candidate in shortlisted)
    shortlisted = [
        candidate
        for candidate in shortlisted
        if candidate[2][0] - minimum_depth <= TOLERANCE
    ]
    return min(
        shortlisted,
        key=lambda candidate: (
            product_order[candidate[0].row_index],
            candidate[1],
        ),
    )


def _upper_child_surface(
    parent: SupportSurface,
    row_y: float,
    product: NormalizedProduct,
    orientation_index: int,
    orientation: Tuple[float, float, float],
    quantity: int,
) -> SupportSurface:
    return SupportSurface(
        surface_index=-1,
        x=parent.x + max((parent.length - orientation[0]) / 2.0, 0.0),
        y=row_y,
        z=parent.z + orientation[2],
        length=orientation[0],
        width=quantity * orientation[1],
        product=product,
        orientation_index=orientation_index,
        source_placement_count=quantity,
    )


def _build_residual_row_plan(
    parent: SupportSurface,
    row_y: float,
    available_width: float,
    product: NormalizedProduct,
    run_specs: List[Tuple[int, Tuple[float, float, float], int]],
    products: List[NormalizedProduct],
    remaining: Dict[int, int],
    container: Dict,
    stats: Dict[str, int],
) -> ResidualRowPlan:
    total_quantity = sum(quantity for _, _, quantity in run_specs)
    simulated_remaining = dict(remaining)
    simulated_remaining[product.row_index] -= total_quantity
    support_potential = 0
    occupied_width = 0.0
    runs = []
    run_y = row_y
    for orientation_index, orientation, quantity in run_specs:
        run_width = quantity * orientation[1]
        child = _upper_child_surface(
            parent,
            run_y,
            product,
            orientation_index,
            orientation,
            quantity,
        )
        support_potential += _surface_support_potential(
            child,
            products,
            simulated_remaining,
            container,
            stats,
        )
        runs.append(
            ResidualOrientationRun(
                orientation_index=orientation_index,
                orientation=orientation,
                quantity=quantity,
                occupied_width=run_width,
            )
        )
        occupied_width += run_width
        run_y += run_width
    return ResidualRowPlan(
        product=product,
        runs=tuple(runs),
        available_width=available_width,
        occupied_width=occupied_width,
        width_utilization=occupied_width / available_width,
        support_potential=support_potential,
    )


def _residual_row_plan_quantity(plan: ResidualRowPlan) -> int:
    return sum(run.quantity for run in plan.runs)


def _select_width_optimized_upper_plan(
    plans: List[ResidualRowPlan],
) -> ResidualRowPlan:
    """Apply the approved deterministic upper-row ranking."""
    best_width_utilization = max(plan.width_utilization for plan in plans)
    shortlisted = [
        plan
        for plan in plans
        if best_width_utilization - plan.width_utilization
        <= RESIDUAL_WIDTH_UTILIZATION_EQ_TOL
    ]
    best_quantity = max(
        _residual_row_plan_quantity(plan) for plan in shortlisted
    )
    shortlisted = [
        plan
        for plan in shortlisted
        if _residual_row_plan_quantity(plan) == best_quantity
    ]
    minimum_orientation_count = min(len(plan.runs) for plan in shortlisted)
    shortlisted = [
        plan
        for plan in shortlisted
        if len(plan.runs) == minimum_orientation_count
    ]
    best_support_potential = max(plan.support_potential for plan in shortlisted)
    shortlisted = [
        plan
        for plan in shortlisted
        if plan.support_potential == best_support_potential
    ]
    minimum_depth = min(
        max(run.orientation[0] for run in plan.runs) for plan in shortlisted
    )
    shortlisted = [
        plan
        for plan in shortlisted
        if max(run.orientation[0] for run in plan.runs) - minimum_depth
        <= TOLERANCE
    ]
    return min(
        shortlisted,
        key=lambda plan: tuple(
            (run.orientation_index, run.quantity) for run in plan.runs
        ),
    )


def _try_continue_parent_pattern(
    parent: SupportSurface,
    row_y: float,
    available_width: float,
    products: List[NormalizedProduct],
    remaining: Dict[int, int],
    loaded_weight: float,
    current_product: Optional[NormalizedProduct],
    container: Dict,
    stats: Dict[str, int],
) -> Optional[ResidualRowPlan]:
    if (
        current_product is None
        or current_product.row_index != parent.product.row_index
    ):
        return None

    quantity = remaining.get(current_product.row_index, 0)
    if quantity <= 0:
        return None
    payload_quantity = _payload_units_available(
        container,
        loaded_weight,
        current_product.weight,
        quantity,
    )
    if payload_quantity <= 0:
        return None

    orientation_index = parent.orientation_index
    if not 0 <= orientation_index < len(current_product.orientations):
        return None
    orientation = current_product.orientations[orientation_index]
    segment = SupportSurface(
        surface_index=parent.surface_index,
        x=parent.x,
        y=row_y,
        z=parent.z,
        length=parent.length,
        width=available_width,
        product=parent.product,
        orientation_index=parent.orientation_index,
        source_placement_count=parent.source_placement_count,
    )
    stats["candidate_evaluations"] += 1
    if not _surface_accepts_orientation(
        segment,
        orientation,
        container,
        stats,
    ):
        return None

    repeat_quantity = min(
        parent.source_placement_count,
        _fit_count(available_width, orientation[1]),
        quantity,
        payload_quantity,
    )
    if repeat_quantity <= 0:
        return None
    return _build_residual_row_plan(
        parent,
        row_y,
        available_width,
        current_product,
        [(orientation_index, orientation, repeat_quantity)],
        products,
        remaining,
        container,
        stats,
    )


def _choose_width_optimized_upper_plan(
    parent: SupportSurface,
    row_y: float,
    available_width: float,
    product: NormalizedProduct,
    orientations: List[Tuple[int, Tuple[float, float, float]]],
    available_quantity: int,
    products: List[NormalizedProduct],
    remaining: Dict[int, int],
    container: Dict,
    stats: Dict[str, int],
) -> Optional[ResidualRowPlan]:
    plans = []
    # One upper unit must be assigned to one immediate lower support unit.
    # ``source_placement_count`` is the number of lower units represented by
    # this (possibly aggregated) diagnostic surface.
    support_capacity = (
        max(int(parent.source_placement_count), 1)
        if stats.get("strict_single_support", True)
        else available_quantity
    )
    available_quantity = min(available_quantity, support_capacity)
    for orientation_index, orientation in orientations:
        quantity = min(
            _fit_count(available_width, orientation[1]),
            available_quantity,
        )
        if quantity > 0:
            plans.append(
                _build_residual_row_plan(
                    parent,
                    row_y,
                    available_width,
                    product,
                    [(orientation_index, orientation, quantity)],
                    products,
                    remaining,
                    container,
                    stats,
                )
            )

    for first_index in range(len(orientations)):
        orientation_index_1, orientation_1 = orientations[first_index]
        max_first = min(
            _fit_count(available_width, orientation_1[1]),
            available_quantity - 1,
        )
        for second_index in range(first_index + 1, len(orientations)):
            orientation_index_2, orientation_2 = orientations[second_index]
            for quantity_1 in range(1, max_first + 1):
                remaining_width = available_width - quantity_1 * orientation_1[1]
                quantity_2 = min(
                    _fit_count(remaining_width, orientation_2[1]),
                    available_quantity - quantity_1,
                )
                if quantity_2 <= 0:
                    continue
                plans.append(
                    _build_residual_row_plan(
                        parent,
                        row_y,
                        available_width,
                        product,
                        [
                            (orientation_index_1, orientation_1, quantity_1),
                            (orientation_index_2, orientation_2, quantity_2),
                        ],
                        products,
                        remaining,
                        container,
                        stats,
                    )
                )

    if not plans:
        return None
    selected = _select_width_optimized_upper_plan(plans)
    product_remaining = remaining.get(product.row_index, 0)
    selected_quantity = _residual_row_plan_quantity(selected)
    terminal_product_row = (
        product_remaining > 0
        and available_quantity >= product_remaining
        and selected_quantity == product_remaining
    )
    if not terminal_product_row:
        return selected

    # _build_residual_row_plan() subtracts the complete plan quantity before
    # calculating support_potential. For a terminal plan, any positive value
    # therefore refers to another remaining SKU, never the selected product.
    support_preserving_terminal_plans = [
        plan
        for plan in plans
        if _residual_row_plan_quantity(plan) == product_remaining
        and plan.support_potential > 0
    ]
    if support_preserving_terminal_plans:
        return _select_width_optimized_upper_plan(
            support_preserving_terminal_plans
        )
    return selected


def _choose_upper_run(
    parent: SupportSurface,
    row_y: float,
    available_width: float,
    products: List[NormalizedProduct],
    remaining: Dict[int, int],
    product_order: Dict[int, int],
    loaded_weight: float,
    current_product: Optional[NormalizedProduct],
    container: Dict,
    stats: Dict[str, int],
) -> Optional[ResidualRowPlan]:
    continuation = _try_continue_parent_pattern(
        parent,
        row_y,
        available_width,
        products,
        remaining,
        loaded_weight,
        current_product,
        container,
        stats,
    )
    if continuation is not None:
        return continuation

    segment = SupportSurface(
        surface_index=parent.surface_index,
        x=parent.x,
        y=row_y,
        z=parent.z,
        length=parent.length,
        width=available_width,
        product=parent.product,
        orientation_index=parent.orientation_index,
        source_placement_count=parent.source_placement_count,
    )
    candidates = []
    orientations_by_product = {}
    available_by_product = {}
    for product in products:
        quantity = remaining.get(product.row_index, 0)
        if quantity <= 0:
            continue
        payload_quantity = _payload_units_available(
            container,
            loaded_weight,
            product.weight,
            quantity,
        )
        if payload_quantity <= 0:
            continue
        for orientation_index, orientation in enumerate(product.orientations):
            stats["candidate_evaluations"] += 1
            if not _surface_accepts_orientation(
                segment,
                orientation,
                container,
                stats,
            ):
                continue
            run_quantity = min(
                _fit_count(available_width, orientation[1]),
                quantity,
                payload_quantity,
            )
            if run_quantity <= 0:
                continue
            child = SupportSurface(
                surface_index=-1,
                x=parent.x + max((parent.length - orientation[0]) / 2.0, 0.0),
                y=row_y,
                z=parent.z + orientation[2],
                length=orientation[0],
                width=run_quantity * orientation[1],
                product=product,
                orientation_index=orientation_index,
                source_placement_count=run_quantity,
            )
            simulated_remaining = dict(remaining)
            simulated_remaining[product.row_index] -= run_quantity
            potential = _surface_support_potential(
                child,
                products,
                simulated_remaining,
                container,
                stats,
            )
            key = (
                0
                if current_product is not None
                and product.row_index == current_product.row_index
                else 1,
                -round(orientation[0] * orientation[1], 9),
                -potential,
                -round(product.unit_volume, 9),
                product_order[product.row_index],
                orientation_index,
            )
            candidates.append(
                (key, product, orientation_index, orientation, run_quantity)
            )
            orientations_by_product.setdefault(product.row_index, []).append(
                (orientation_index, orientation)
            )
            available_by_product[product.row_index] = payload_quantity
    if not candidates:
        return None
    # Retain the existing continuity/support-aware SKU choice. The selected
    # product's orientation geometry is optimized only after this decision.
    _, product, _orientation_index, _orientation, _run_quantity = min(
        candidates,
        key=lambda item: item[0],
    )
    return _choose_width_optimized_upper_plan(
        parent,
        row_y,
        available_width,
        product,
        orientations_by_product[product.row_index],
        available_by_product[product.row_index],
        products,
        remaining,
        container,
        stats,
    )


def _fill_upper_row(
    parent: SupportSurface,
    pass_index: int,
    next_surface_index: int,
    products: List[NormalizedProduct],
    container: Dict,
    remaining: Dict[int, int],
    product_order: Dict[int, int],
    current_product: Optional[NormalizedProduct],
    placements: List[Placement],
    residual_loaded: Dict[int, int],
    next_item_index: Dict[int, int],
    quantities_by_product: Dict[int, int],
    above_by_product: Dict[int, int],
    loaded_weight: float,
    stats: Dict[str, int],
) -> Tuple[
    List[SupportSurface],
    Optional[Dict],
    Optional[NormalizedProduct],
    float,
    int,
]:
    if not parent.stackable:
        return [], None, current_product, loaded_weight, next_surface_index

    children = []
    runs = []
    supporter_orientation = parent.product.orientations[parent.orientation_index]
    supporter_width = supporter_orientation[1]
    row_y = parent.y
    row_end = parent.y + parent.source_placement_count * supporter_width
    while row_end - row_y > TOLERANCE:
        continuing_product = current_product
        selected = _choose_upper_run(
            parent,
            row_y,
            row_end - row_y,
            products,
            remaining,
            product_order,
            loaded_weight,
            current_product,
            container,
            stats,
        )
        if selected is None:
            break
        product = selected.product
        selected_quantity = _residual_row_plan_quantity(selected)
        pattern_continuation = (
            continuing_product is not None
            and continuing_product.row_index == parent.product.row_index
            and selected.product.row_index == continuing_product.row_index
            and len(selected.runs) == 1
            and selected.runs[0].orientation_index == parent.orientation_index
        )
        terminal_product_row = (
            selected_quantity == remaining.get(product.row_index, 0)
        )
        preserves_next_support = (
            terminal_product_row and selected.support_potential > 0
        )
        orientation_runs = [
            {
                "orientation_index": run.orientation_index,
                "orientation": [float(value) for value in run.orientation],
                "quantity": int(run.quantity),
                "occupied_width": float(run.occupied_width),
            }
            for run in selected.runs
        ]
        action_y_start = row_y
        for selected_run in selected.runs:
            orientation_index = selected_run.orientation_index
            orientation = selected_run.orientation
            run_quantity = selected_run.quantity
            run_children = []
            for lane_index in range(run_quantity):
                child = SupportSurface(
                    surface_index=next_surface_index,
                    x=parent.x + max((parent.length - orientation[0]) / 2.0, 0.0),
                    y=(
                        row_y
                        + lane_index * supporter_width
                        + max((supporter_width - orientation[1]) / 2.0, 0.0)
                    ),
                    z=parent.z + orientation[2],
                    length=orientation[0],
                    width=orientation[1],
                    product=product,
                    orientation_index=orientation_index,
                    source_placement_count=1,
                )
                next_surface_index += 1
                placement = Placement(
                    product_name=product.name,
                    item_index=next_item_index[product.row_index],
                    row_index=product.row_index,
                    sequence=product.sequence,
                    weight=product.weight,
                    stackable=product.stackable,
                    x=child.x,
                    y=child.y,
                    z=parent.z,
                    l=orientation[0],
                    w=orientation[1],
                    h=orientation[2],
                )
                placements.append(placement)
                next_item_index[product.row_index] += 1
                residual_loaded[product.row_index] += 1
                remaining[product.row_index] -= 1
                loaded_weight += product.weight
                quantities_by_product[product.row_index] = (
                    quantities_by_product.get(product.row_index, 0) + 1
                )
                above_by_product[product.row_index] = (
                    above_by_product.get(product.row_index, 0) + 1
                )
                children.append(child)
                run_children.append(child)
            first_child = run_children[0]
            runs.append(
                {
                    "product_name": product.name,
                    "row_index": product.row_index,
                    "orientation_index": orientation_index,
                    "orientation": [float(value) for value in orientation],
                    "quantity": run_quantity,
                    "x": float(first_child.x),
                    "y_start": float(row_y),
                    "y_end": float(row_y + run_quantity * supporter_width),
                    "base_z": float(parent.z),
                    "top_z": float(first_child.z),
                    "support_surface_index": first_child.surface_index,
                    "row_available_width": float(selected.available_width),
                    "row_occupied_width": float(selected.occupied_width),
                    "width_utilization": float(selected.width_utilization),
                    "orientation_count": len(selected.runs),
                    "orientation_runs": orientation_runs,
                    "support_potential": int(selected.support_potential),
                    "terminal_product_row": terminal_product_row,
                    "preserves_next_support": preserves_next_support,
                    "pattern_continuation": pattern_continuation,
                    "continued_parent_surface_index": (
                        parent.surface_index if pattern_continuation else None
                    ),
                    "continued_orientation_index": (
                        parent.orientation_index if pattern_continuation else None
                    ),
                    "continuation_quantity": (
                        selected_quantity if pattern_continuation else 0
                    ),
                    "action_y_start": float(action_y_start),
                    "action_y_end": float(
                        action_y_start + selected.occupied_width
                    ),
                }
            )
            row_y += run_quantity * supporter_width
        current_product = (
            product if remaining.get(product.row_index, 0) > 0 else None
        )

    row = None
    if runs:
        row = {
            "pass_index": pass_index,
            "parent_surface_index": parent.surface_index,
            "parent_product": parent.product.name,
            "y_start": float(parent.y),
            "available_width": float(parent.width),
            "runs": runs,
        }
    return children, row, current_product, loaded_weight, next_surface_index


def pack_residuals_support_greedy(
    container: Dict,
    ordered_products: List[NormalizedProduct],
    residual_quantities: Dict[int, int],
    placements: List[Placement],
    residual_loaded: Dict[int, int],
    next_item_index: Dict[int, int],
    loaded_weight: float,
    frontier: float,
) -> Tuple[float, float, List[Dict], int, int, int]:
    """Pack residuals in sequence-isolated support-surface Y/Z/X bands."""
    remaining = dict(residual_quantities)
    product_order = {
        product.row_index: index for index, product in enumerate(ordered_products)
    }
    bands: List[Dict] = []
    stats = {
        "candidate_evaluations": 0,
        "support_checks": 0,
        "support_relationships": 0,
        "strict_single_support": True,
    }

    sequences = sorted(
        {
            product.sequence
            for product in ordered_products
            if remaining.get(product.row_index, 0) > 0
        }
    )
    for sequence in sequences:
        products = [
            product
            for product in ordered_products
            if product.sequence == sequence
            and remaining.get(product.row_index, 0) > 0
        ]
        stats["support_matrix"] = _build_support_matrix(products)
        stats["support_relationships_precomputed"] = sum(
            1 for compatible in stats["support_matrix"].values() if compatible
        )
        sequence_band_index = 0
        while any(remaining.get(product.row_index, 0) > 0 for product in products):
            available_length = max(container["L"] - frontier, 0.0)
            if available_length <= TOLERANCE:
                break
            foundation = _choose_residual_foundation(
                products,
                container,
                remaining,
                product_order,
                loaded_weight,
                frontier,
                available_length,
                stats,
            )
            if foundation is None:
                break

            (
                product,
                orientation_index,
                orientation,
                foundation_quantity,
                foundation_occupied_width,
                foundation_width_utilization,
                foundation_support_potential,
            ) = foundation
            before = {
                str(item.row_index): int(remaining.get(item.row_index, 0))
                for item in products
            }
            band_x = frontier
            quantities_by_product: Dict[int, int] = {}
            above_by_product: Dict[int, int] = {}
            foundation_surfaces: List[SupportSurface] = []
            for lane_index in range(foundation_quantity):
                placements.append(
                    Placement(
                        product_name=product.name,
                        item_index=next_item_index[product.row_index],
                        row_index=product.row_index,
                        sequence=product.sequence,
                        weight=product.weight,
                        stackable=product.stackable,
                        x=band_x,
                        y=lane_index * orientation[1],
                        z=0.0,
                        l=orientation[0],
                        w=orientation[1],
                        h=orientation[2],
                    )
                )
                foundation_surfaces.append(
                    SupportSurface(
                        surface_index=lane_index,
                        x=band_x,
                        y=lane_index * orientation[1],
                        z=orientation[2],
                        length=orientation[0],
                        width=orientation[1],
                        product=product,
                        orientation_index=orientation_index,
                        source_placement_count=1,
                    )
                )
                next_item_index[product.row_index] += 1
                residual_loaded[product.row_index] += 1
                remaining[product.row_index] -= 1
                loaded_weight += product.weight
                quantities_by_product[product.row_index] = (
                    quantities_by_product.get(product.row_index, 0) + 1
                )

            foundation_surface = SupportSurface(
                surface_index=-1,
                x=band_x,
                y=0.0,
                z=orientation[2],
                length=orientation[0],
                width=foundation_quantity * orientation[1],
                product=product,
                orientation_index=orientation_index,
                source_placement_count=foundation_quantity,
            )
            surfaces = list(foundation_surfaces)
            active_surfaces = list(foundation_surfaces)
            upper_rows = []
            next_surface_index = foundation_quantity
            current_product = (
                product if remaining.get(product.row_index, 0) > 0 else None
            )
            vertical_passes = 0

            while active_surfaces:
                next_surfaces = []
                pass_index = vertical_passes + 1
                for surface in sorted(
                    active_surfaces,
                    key=lambda item: (
                        round(item.y, 9),
                        round(item.x, 9),
                        item.surface_index,
                    ),
                ):
                    (
                        children,
                        row,
                        current_product,
                        loaded_weight,
                        next_surface_index,
                    ) = _fill_upper_row(
                        surface,
                        pass_index,
                        next_surface_index,
                        products,
                        container,
                        remaining,
                        product_order,
                        current_product,
                        placements,
                        residual_loaded,
                        next_item_index,
                        quantities_by_product,
                        above_by_product,
                        loaded_weight,
                        stats,
                    )
                    next_surfaces.extend(children)
                    surfaces.extend(children)
                    if row is not None:
                        upper_rows.append(row)
                if not next_surfaces:
                    break
                vertical_passes += 1
                active_surfaces = next_surfaces

            frontier = band_x + orientation[0]
            after = {
                str(item.row_index): int(remaining.get(item.row_index, 0))
                for item in products
            }
            products_added_above = [
                {
                    "row_index": item.row_index,
                    "product_name": item.name,
                    "quantity": int(above_by_product[item.row_index]),
                }
                for item in products
                if above_by_product.get(item.row_index, 0) > 0
            ]
            maximum_z = max(surface.z for surface in surfaces)
            band = {
                "pattern": "support_surface_row_first_band",
                "sequence": sequence,
                "band_index": len(bands),
                "sequence_band_index": sequence_band_index,
                "x_start": float(band_x),
                "x_end": float(frontier),
                "foundation_product": product.name,
                "foundation_row_index": product.row_index,
                "foundation_orientation": [float(value) for value in orientation],
                "foundation_quantity": int(foundation_quantity),
                "foundation_available_width": float(container["W"]),
                "foundation_occupied_width": float(foundation_occupied_width),
                "foundation_width_utilization": float(
                    foundation_width_utilization
                ),
                "foundation_orientation_count": 1,
                "foundation_orientation_runs": [
                    {
                        "orientation_index": orientation_index,
                        "orientation": [float(value) for value in orientation],
                        "quantity": int(foundation_quantity),
                        "occupied_width": float(foundation_occupied_width),
                    }
                ],
                "foundation_support_potential": int(
                    foundation_support_potential
                ),
                "foundation_surface": _surface_metadata(foundation_surface),
                "support_surface_count": len(surfaces),
                "support_relationships_precomputed": int(
                    stats.get("support_relationships_precomputed", 0)
                ),
                "support_surfaces": [
                    _surface_metadata(surface) for surface in surfaces
                ],
                "upper_rows": upper_rows,
                "products_added_above": products_added_above,
                "vertical_passes": vertical_passes,
                "maximum_z": float(maximum_z),
                "residual_quantities_before": before,
                "residual_quantities_after": after,
                "quantities_by_product": {
                    str(item.row_index): int(
                        quantities_by_product.get(item.row_index, 0)
                    )
                    for item in products
                    if quantities_by_product.get(item.row_index, 0) > 0
                },
                # Compatibility aliases for the former residual mini-block list.
                "row_index": product.row_index,
                "product_name": product.name,
                "orientation": [float(value) for value in orientation],
                "nx": 1,
                "ny": foundation_quantity,
                "nz": vertical_passes + 1,
                "qty": int(sum(quantities_by_product.values())),
                "width": float(foundation_surface.width),
                "height": float(maximum_z),
            }
            bands.append(band)
            sequence_band_index += 1

    return (
        frontier,
        loaded_weight,
        bands,
        stats["candidate_evaluations"],
        stats["support_checks"],
        stats["support_relationships"],
    )


def _has_payload_limit(container: Dict) -> bool:
    try:
        return (
            container.get("max_weight") is not None
            and float(container["max_weight"]) > 0
        )
    except (TypeError, ValueError):
        return False


def _payload_units_available(
    container: Dict,
    loaded_weight: float,
    unit_weight: float,
    requested: int,
) -> int:
    if requested <= 0:
        return 0
    if not _has_payload_limit(container) or unit_weight <= 0:
        return requested
    remaining_weight = max(float(container["max_weight"]) - loaded_weight, 0.0)
    return min(requested, _fit_count(remaining_weight, unit_weight))


def _new_side_infill_stats(sequence_group_count: int) -> Dict:
    return {
        "side_residual_count": 0,
        "side_residuals_evaluated": 0,
        "side_residuals_filled": 0,
        "side_residual_volume_available": 0.0,
        "side_residual_volume_filled": 0.0,
        "infill_units_total": 0,
        "infill_volume_total": 0.0,
        "infill_units_by_product": {},
        "infill_block_count": 0,
        "infill_block_candidates_generated": 0,
        "infill_block_candidates_evaluated": 0,
        "sequence_group_count": int(sequence_group_count),
        "sequence_restricted": bool(sequence_group_count > 1),
        "historical_gap_searches": 0,
        "backtracking_count": 0,
        "beam_states_evaluated": 0,
        "side_residual_envelopes": [],
        "residual_frontiers_closed": 0,
        "post_frontier_side_residuals_derived": 0,
        "post_frontier_side_residuals_filled": 0,
        "post_frontier_units": 0,
        "post_frontier_volume": 0.0,
        "post_frontier_closures": [],
        "residual_evaluation_reasons": [],
        "actions": [],
    }


def _merge_side_infill_stats(target: Dict, addition: Dict) -> None:
    for key in (
        "side_residual_count",
        "side_residuals_evaluated",
        "side_residuals_filled",
        "side_residual_volume_available",
        "side_residual_volume_filled",
        "infill_units_total",
        "infill_volume_total",
        "infill_block_count",
        "infill_block_candidates_generated",
        "infill_block_candidates_evaluated",
        "residual_frontiers_closed",
        "post_frontier_side_residuals_derived",
        "post_frontier_side_residuals_filled",
        "post_frontier_units",
        "post_frontier_volume",
    ):
        target[key] += addition[key]
    for row_index, quantity in addition["infill_units_by_product"].items():
        target["infill_units_by_product"][row_index] = (
            target["infill_units_by_product"].get(row_index, 0) + quantity
        )
    target["actions"].extend(addition["actions"])
    target["side_residual_envelopes"].extend(
        addition.get("side_residual_envelopes", [])
    )
    target["post_frontier_closures"].extend(
        addition.get("post_frontier_closures", [])
    )
    target["residual_evaluation_reasons"].extend(
        addition.get("residual_evaluation_reasons", [])
    )


def _side_infill_metadata(prefix: str, stats: Dict) -> Dict:
    return {
        f"{prefix}_{key}": value
        for key, value in stats.items()
    }


def _deduplicate_sorted_coordinates(values: List[float]) -> List[float]:
    """Return stable, tolerance-aware coordinates for a local geometry window."""
    result: List[float] = []
    for value in sorted(float(item) for item in values):
        if not result or abs(value - result[-1]) > TOLERANCE:
            result.append(value)
    return result


def _merge_local_side_residual_pair(
    first: Space,
    second: Space,
) -> Optional[Space]:
    """Merge only residuals that share a complete lateral face."""
    if (
        abs(first.y - second.y) <= TOLERANCE
        and abs(first.z - second.z) <= TOLERANCE
        and abs(first.W - second.W) <= TOLERANCE
        and abs(first.H - second.H) <= TOLERANCE
        and (
            abs(first.x + first.L - second.x) <= TOLERANCE
            or abs(second.x + second.L - first.x) <= TOLERANCE
        )
    ):
        return Space(
            min(first.x, second.x),
            first.y,
            first.z,
            first.L + second.L,
            first.W,
            first.H,
        )
    if (
        abs(first.x - second.x) <= TOLERANCE
        and abs(first.z - second.z) <= TOLERANCE
        and abs(first.L - second.L) <= TOLERANCE
        and abs(first.H - second.H) <= TOLERANCE
        and (
            abs(first.y + first.W - second.y) <= TOLERANCE
            or abs(second.y + second.W - first.y) <= TOLERANCE
        )
    ):
        return Space(
            first.x,
            min(first.y, second.y),
            first.z,
            first.L,
            first.W + second.W,
            first.H,
        )
    return None


def merge_local_side_residuals(spaces: List[Space]) -> List[Space]:
    """Repeatedly merge complete-face-compatible floor-to-ceiling spaces."""
    merged = [
        space
        for space in spaces
        if space.L > TOLERANCE and space.W > TOLERANCE and space.H > TOLERANCE
    ]
    changed = True
    while changed:
        changed = False
        merged.sort(
            key=lambda space: (
                round(space.x, 9),
                round(space.y, 9),
                round(space.L, 9),
                round(space.W, 9),
                round(space.H, 9),
            )
        )
        for first_index, first in enumerate(merged):
            for second_index in range(first_index + 1, len(merged)):
                combined = _merge_local_side_residual_pair(
                    first,
                    merged[second_index],
                )
                if combined is None:
                    continue
                merged = [
                    space
                    for index, space in enumerate(merged)
                    if index not in (first_index, second_index)
                ]
                merged.append(combined)
                changed = True
                break
            if changed:
                break

    unique: List[Space] = []
    seen = set()
    for space in merged:
        key = (
            round(space.x, 9),
            round(space.y, 9),
            round(space.z, 9),
            round(space.L, 9),
            round(space.W, 9),
            round(space.H, 9),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(space)
    return sorted(
        unique,
        key=lambda space: (
            round(space.x, 9),
            -round(space.volume, 9),
            round(space.y, 9),
            -round(space.W, 9),
            round(space.L, 9),
            round(space.H, 9),
        ),
    )


def derive_local_side_residuals(
    placements: List[Placement],
    container: Dict,
    window_x_start: float,
    window_x_end: float,
) -> List[Space]:
    """Derive full-height lateral residuals from committed XY geometry.

    The window is deliberately local.  X breakpoints are generated from the
    actual committed placement projections, each slab is complemented in Y,
    and only complete-face-compatible residuals are merged.  Z is ignored for
    occupancy by design: any cargo over an XY footprint removes that footprint
    from the side-space envelope.
    """
    x_start = float(window_x_start)
    x_end = float(window_x_end)
    width = float(container.get("W", 0.0) or 0.0)
    height = float(container.get("H", 0.0) or 0.0)
    if x_end <= x_start + TOLERANCE or width <= TOLERANCE or height <= TOLERANCE:
        return []

    relevant: List[Placement] = []
    breakpoints = [x_start, x_end]
    for placement in placements:
        placement_x_start = float(placement.x)
        placement_x_end = placement_x_start + float(placement.l)
        if (
            placement_x_end <= x_start + TOLERANCE
            or placement_x_start >= x_end - TOLERANCE
        ):
            continue
        relevant.append(placement)
        breakpoints.extend(
            (
                max(x_start, min(x_end, placement_x_start)),
                max(x_start, min(x_end, placement_x_end)),
            )
        )

    x_breakpoints = _deduplicate_sorted_coordinates(breakpoints)
    residuals: List[Space] = []
    for slab_start, slab_end in zip(x_breakpoints, x_breakpoints[1:]):
        if slab_end <= slab_start + TOLERANCE:
            continue
        occupied_y: List[Tuple[float, float]] = []
        for placement in relevant:
            placement_x_start = float(placement.x)
            placement_x_end = placement_x_start + float(placement.l)
            if (
                placement_x_end <= slab_start + TOLERANCE
                or placement_x_start >= slab_end - TOLERANCE
            ):
                continue
            y_start = max(0.0, min(width, float(placement.y)))
            y_end = max(0.0, min(width, float(placement.y + placement.w)))
            if y_end > y_start + TOLERANCE:
                occupied_y.append((y_start, y_end))

        occupied_y.sort(key=lambda interval: (interval[0], interval[1]))
        merged_occupied: List[Tuple[float, float]] = []
        for y_start, y_end in occupied_y:
            if not merged_occupied or y_start > merged_occupied[-1][1] + TOLERANCE:
                merged_occupied.append((y_start, y_end))
            else:
                merged_occupied[-1] = (
                    merged_occupied[-1][0],
                    max(merged_occupied[-1][1], y_end),
                )

        y_cursor = 0.0
        for occupied_start, occupied_end in merged_occupied:
            if occupied_start > y_cursor + TOLERANCE:
                residuals.append(
                    Space(
                        slab_start,
                        y_cursor,
                        0.0,
                        slab_end - slab_start,
                        occupied_start - y_cursor,
                        height,
                    )
                )
            y_cursor = max(y_cursor, occupied_end)
        if width > y_cursor + TOLERANCE:
            residuals.append(
                Space(
                    slab_start,
                    y_cursor,
                    0.0,
                    slab_end - slab_start,
                    width - y_cursor,
                    height,
                )
            )

    return merge_local_side_residuals(residuals)


def fill_side_residual_deterministically(
    residual_space: Space,
    anchor_product: NormalizedProduct,
    ordered_products: List[NormalizedProduct],
    remaining_quantities: Dict[int, int],
    next_item_index: Dict[int, int],
    container: Dict,
    loaded_weight: float,
    sequence_restricted: bool,
    eligible_row_indices: Optional[set] = None,
    reserved_payload_weight: float = 0.0,
    committed_placements: Optional[List[Placement]] = None,
    window_x_start: Optional[float] = None,
    window_x_end: Optional[float] = None,
) -> Tuple[List[Placement], float, Dict]:
    """Constructively close one bounded local side envelope.

    The closure is recomputed from actual committed XY projections after each
    filler block.  This preserves X tails and removes computational Product
    Block boundaries without reopening any geometry outside the fixed local
    window.
    """
    sequence_group_count = len({product.sequence for product in ordered_products})
    stats = _new_side_infill_stats(sequence_group_count)
    local_x_start = (
        float(residual_space.x)
        if window_x_start is None
        else float(window_x_start)
    )
    local_x_end = (
        float(residual_space.x + residual_space.L)
        if window_x_end is None
        else float(window_x_end)
    )
    if local_x_end <= local_x_start + TOLERANCE:
        return [], loaded_weight, stats
    committed: List[Placement] = []
    product_priority = {
        product.row_index: index for index, product in enumerate(ordered_products)
    }

    def current_residuals() -> List[Space]:
        if committed_placements is None:
            return [residual_space]
        return derive_local_side_residuals(
            list(committed_placements) + committed,
            container,
            local_x_start,
            local_x_end,
        )

    residuals = current_residuals()
    stats["side_residual_count"] = len(residuals)
    stats["side_residual_volume_available"] = float(
        sum(space.volume for space in residuals)
    )

    def record_envelope(envelope: List[Space]) -> None:
        stats["side_residual_envelopes"].append(
            [
                {
                    "x": float(space.x),
                    "y": float(space.y),
                    "z": float(space.z),
                    "L": float(space.L),
                    "W": float(space.W),
                    "H": float(space.H),
                }
                for space in envelope
            ]
        )

    record_envelope(residuals)

    while residuals:
        active_space = min(
            residuals,
            key=lambda space: (
                round(space.x, 9),
                -round(space.volume, 9),
                round(space.y, 9),
                -round(space.W, 9),
                round(space.L, 9),
                round(space.H, 9),
            ),
        )
        residuals.remove(active_space)
        stats["side_residuals_evaluated"] += 1
        bounded_container = {
            "L": active_space.L,
            "W": active_space.W,
            "H": active_space.H,
            "max_weight": container.get("max_weight"),
            "tare_weight": container.get("tare_weight"),
        }
        ranked_candidates = []
        eligible_product_names: List[str] = []
        sequence_filtered = 0
        payload_blocked = 0
        generated_candidate_count = 0
        fit_candidate_count = 0
        width_capable = False
        depth_capable = False

        for product in ordered_products:
            remaining_quantity = int(remaining_quantities.get(product.row_index, 0))
            if product.row_index == anchor_product.row_index or remaining_quantity <= 0:
                continue
            if (
                eligible_row_indices is not None
                and product.row_index not in eligible_row_indices
            ):
                continue
            if sequence_restricted and product.sequence != anchor_product.sequence:
                if remaining_quantity > 0:
                    sequence_filtered += 1
                continue
            eligible_product_names.append(product.name)
            width_capable = width_capable or any(
                orientation[1] <= active_space.W + TOLERANCE
                and orientation[2] <= active_space.H + TOLERANCE
                for orientation in product.orientations
            )
            depth_capable = depth_capable or any(
                orientation[0] <= active_space.L + TOLERANCE
                and orientation[2] <= active_space.H + TOLERANCE
                for orientation in product.orientations
            )
            payload_quantity = _payload_units_available(
                container,
                loaded_weight + reserved_payload_weight,
                product.weight,
                remaining_quantity,
            )
            if payload_quantity <= 0:
                payload_blocked += 1
                continue

            candidates, evaluated = build_product_block_candidates(
                product,
                bounded_container,
                active_space.L,
            )
            generated_candidate_count += len(candidates)
            stats["infill_block_candidates_generated"] += len(candidates)
            stats["infill_block_candidates_evaluated"] += evaluated
            residual_footprint = _largest_valid_footprint(
                product,
                bounded_container,
            )
            for candidate in candidates:
                module_count = _fit_count(active_space.L, candidate.depth)
                quantity = min(
                    payload_quantity,
                    module_count * candidate.module_capacity,
                )
                if quantity <= 0:
                    continue
                fit_candidate_count += 1
                depth_required = (
                    int(math.ceil(quantity / candidate.module_capacity))
                    * candidate.depth
                )
                packed_volume = quantity * product.unit_volume
                ranking_key = (
                    -round(packed_volume, 9),
                    -round(candidate.transverse_utilization, 12),
                    -int(quantity),
                    round(depth_required, 9),
                    -round(residual_footprint, 9),
                    -round(product.unit_volume, 9),
                    -round(product.longest_dimension, 9),
                    product_priority[product.row_index],
                    _candidate_stable_key(candidate),
                )
                ranked_candidates.append(
                    {
                        "product": product,
                        "candidate": candidate,
                        "quantity": int(quantity),
                        "depth_required": float(depth_required),
                        "packed_volume": float(packed_volume),
                        "residual_footprint": float(residual_footprint),
                        "ranking_key": ranking_key,
                    }
                )

        if not ranked_candidates:
            if not eligible_product_names:
                reason = (
                    "sequence_restriction"
                    if sequence_filtered
                    else "no_remaining_quantity"
                )
            elif payload_blocked == len(eligible_product_names):
                reason = "payload_exhausted"
            elif not width_capable:
                reason = "insufficient_width"
            elif not depth_capable:
                reason = "insufficient_x_depth"
            elif fit_candidate_count == 0 and generated_candidate_count == 0:
                reason = "no_enabled_orientation_fits"
            else:
                reason = "no_enabled_orientation_fits"
            stats["residual_evaluation_reasons"].append(
                {
                    "x_start": float(active_space.x),
                    "x_end": float(active_space.x + active_space.L),
                    "y_start": float(active_space.y),
                    "width": float(active_space.W),
                    "reason": reason,
                    "eligible_products": list(eligible_product_names),
                }
            )
            # This residual is physically valid but may be too narrow for any
            # eligible Product Block.  Continue through the remaining local
            # envelope rather than letting one narrow slab hide another usable
            # side region.
            continue

        winner = min(ranked_candidates, key=lambda item: item["ranking_key"])
        filler = winner["product"]
        candidate = winner["candidate"]
        filler_placements = _materialize_product_block_in_space(
            filler,
            candidate,
            active_space,
            next_item_index[filler.row_index],
            winner["quantity"],
        )
        if not filler_placements:
            continue
        used_width = max(
            placement.y + placement.w - active_space.y
            for placement in filler_placements
        )
        if used_width <= TOLERANCE:
            continue

        used_depth = max(
            placement.x + placement.l - active_space.x
            for placement in filler_placements
        )

        quantity = len(filler_placements)
        committed.extend(filler_placements)
        remaining_quantities[filler.row_index] = max(
            remaining_quantities.get(filler.row_index, 0) - quantity,
            0,
        )
        next_item_index[filler.row_index] += quantity
        loaded_weight += quantity * filler.weight
        filled_volume = quantity * filler.unit_volume
        stats["infill_units_total"] += quantity
        stats["infill_volume_total"] += filled_volume
        stats["side_residual_volume_filled"] += filled_volume
        stats["infill_block_count"] += 1
        row_key = str(filler.row_index)
        stats["infill_units_by_product"][row_key] = (
            stats["infill_units_by_product"].get(row_key, 0) + quantity
        )
        stats["actions"].append(
            {
                "anchor_product": anchor_product.name,
                "anchor_row_index": int(anchor_product.row_index),
                "filler_product": filler.name,
                "filler_row_index": int(filler.row_index),
                "sequence": int(filler.sequence),
                "residual_x_start": float(active_space.x),
                "residual_x_end": float(active_space.x + active_space.L),
                "residual_y_start": float(active_space.y),
                "residual_y_end": float(active_space.y + active_space.W),
                "residual_width": float(active_space.W),
                "selected_orientations": [
                    [float(value) for value in orientation]
                    for orientation in candidate.orientations
                ],
                "selected_block": {
                    **_candidate_metadata(candidate),
                    "y_start": float(active_space.y),
                    "actual_depth_required": float(winner["depth_required"]),
                    "actual_depth_committed": float(used_depth),
                    "actual_width_committed": float(used_width),
                },
                "quantity": int(quantity),
                "packed_volume": float(filled_volume),
                "residual_local_footprint": float(
                    winner["residual_footprint"]
                ),
                "selection_reason": (
                    "packed_volume_then_transverse_utilization_then_quantity_"
                    "then_depth_then_residual_local_priority"
                ),
            }
        )
        residuals = (
            current_residuals()
            if committed_placements is not None
            else []
        )
        if committed_placements is not None:
            record_envelope(residuals)

    stats["side_residuals_filled"] = int(bool(committed))
    return committed, loaded_weight, stats


def _new_top_infill_stats(sequence_group_count: int) -> Dict:
    """Create diagnostics for the separate supported-top closure."""
    return {
        "top_residual_windows": [],
        "top_support_planes_evaluated": 0,
        "top_atomic_cells_evaluated": 0,
        "top_residual_count": 0,
        "top_residuals_evaluated": 0,
        "top_residuals_filled": 0,
        "top_residual_volume_available": 0.0,
        "top_residual_volume_filled": 0.0,
        "top_infill_units_total": 0,
        "top_infill_volume_total": 0.0,
        "top_infill_units_by_product": {},
        "top_infill_block_count": 0,
        "top_infill_block_candidates_generated": 0,
        "top_infill_block_candidates_evaluated": 0,
        "top_anchor_candidate_evaluations": 0,
        "top_complete_face_merges": 0,
        "top_support_checks": 0,
        "top_candidates_rejected_support": 0,
        "top_candidates_rejected_overlap": 0,
        "top_residual_frontiers_closed": 0,
        "top_frontier_closures": [],
        "top_sequence_group_count": int(sequence_group_count),
        "top_sequence_restricted": bool(sequence_group_count > 1),
        "top_historical_gap_searches": 0,
        "top_backtracking_count": 0,
        "top_beam_states_evaluated": 0,
        "top_product_permutation_searches": 0,
        "top_global_free_space_searches": 0,
        "historical_gap_searches": 0,
        "backtracking_count": 0,
        "beam_states_evaluated": 0,
        "product_permutation_searches": 0,
        "global_free_space_searches": 0,
        "top_residual_evaluation_reasons": [],
        "top_actions": [],
    }


def _merge_top_infill_stats(target: Dict, addition: Dict) -> None:
    for key in (
        "top_support_planes_evaluated",
        "top_atomic_cells_evaluated",
        "top_residual_count",
        "top_residuals_evaluated",
        "top_residuals_filled",
        "top_residual_volume_available",
        "top_residual_volume_filled",
        "top_infill_units_total",
        "top_infill_volume_total",
        "top_infill_block_count",
        "top_infill_block_candidates_generated",
        "top_infill_block_candidates_evaluated",
        "top_anchor_candidate_evaluations",
        "top_complete_face_merges",
        "top_support_checks",
        "top_candidates_rejected_support",
        "top_candidates_rejected_overlap",
        "top_residual_frontiers_closed",
        "historical_gap_searches",
        "backtracking_count",
        "beam_states_evaluated",
        "product_permutation_searches",
        "global_free_space_searches",
    ):
        target[key] += addition.get(key, 0)
    for row_index, quantity in addition.get(
        "top_infill_units_by_product", {}
    ).items():
        target["top_infill_units_by_product"][row_index] = (
            target["top_infill_units_by_product"].get(row_index, 0)
            + quantity
        )
    target["top_residual_windows"].extend(
        addition.get("top_residual_windows", [])
    )
    target["top_residual_evaluation_reasons"].extend(
        addition.get("top_residual_evaluation_reasons", [])
    )
    target["top_actions"].extend(addition.get("top_actions", []))
    target["top_frontier_closures"].extend(
        addition.get("top_frontier_closures", [])
    )


def _top_infill_metadata(prefix: str, stats: Dict) -> Dict:
    metadata = {
        f"{prefix}_{key}": value
        for key, value in stats.items()
    }
    metadata[f"{prefix}_top_infill_actions"] = stats.get("top_actions", [])
    metadata[f"{prefix}_top_infill_residual_evaluation_reasons"] = stats.get(
        "top_residual_evaluation_reasons", []
    )
    return metadata


def _merge_local_top_residual_pair(
    first: Space,
    second: Space,
) -> Optional[Space]:
    """Merge only complete-face-compatible spaces on one support plane."""
    if (
        abs(first.z - second.z) <= TOLERANCE
        and abs(first.H - second.H) <= TOLERANCE
        and abs(first.y - second.y) <= TOLERANCE
        and abs(first.W - second.W) <= TOLERANCE
        and (
            abs(first.x + first.L - second.x) <= TOLERANCE
            or abs(second.x + second.L - first.x) <= TOLERANCE
        )
    ):
        return Space(
            min(first.x, second.x),
            first.y,
            first.z,
            first.L + second.L,
            first.W,
            first.H,
        )
    if (
        abs(first.z - second.z) <= TOLERANCE
        and abs(first.H - second.H) <= TOLERANCE
        and abs(first.x - second.x) <= TOLERANCE
        and abs(first.L - second.L) <= TOLERANCE
        and (
            abs(first.y + first.W - second.y) <= TOLERANCE
            or abs(second.y + second.W - first.y) <= TOLERANCE
        )
    ):
        return Space(
            first.x,
            min(first.y, second.y),
            first.z,
            first.L,
            first.W + second.W,
            first.H,
        )
    return None


def _merge_local_top_residuals_detailed(
    spaces: List[Space],
) -> Tuple[List[Space], int]:
    merged = [
        space
        for space in spaces
        if space.L > TOLERANCE
        and space.W > TOLERANCE
        and space.H > TOLERANCE
    ]
    complete_face_merges = 0
    changed = True
    while changed:
        changed = False
        merged.sort(
            key=lambda space: (
                round(space.z, 9),
                round(space.x, 9),
                round(space.y, 9),
                round(space.L, 9),
                round(space.W, 9),
                round(space.H, 9),
            )
        )
        for first_index, first in enumerate(merged):
            for second_index in range(first_index + 1, len(merged)):
                combined = _merge_local_top_residual_pair(
                    first,
                    merged[second_index],
                )
                if combined is None:
                    continue
                merged = [
                    space
                    for index, space in enumerate(merged)
                    if index not in (first_index, second_index)
                ]
                merged.append(combined)
                complete_face_merges += 1
                changed = True
                break
            if changed:
                break

    unique: List[Space] = []
    seen = set()
    for space in merged:
        key = (
            round(space.x, 9),
            round(space.y, 9),
            round(space.z, 9),
            round(space.L, 9),
            round(space.W, 9),
            round(space.H, 9),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(space)
    return (
        sorted(
            unique,
            key=lambda space: (
                round(space.z, 9),
                round(space.x, 9),
                -round(space.L * space.W, 9),
                -round(space.volume, 9),
                round(space.y, 9),
                round(space.L, 9),
                round(space.W, 9),
                round(space.H, 9),
            ),
        ),
        complete_face_merges,
    )


def merge_local_top_residuals(spaces: List[Space]) -> List[Space]:
    """Merge complete faces without ever combining different support heights."""
    merged, _ = _merge_local_top_residuals_detailed(spaces)
    return merged


def _top_rect_intersection(
    placement: Placement,
    window_x_start: float,
    window_x_end: float,
    container_width: float,
) -> Optional[Tuple[float, float, float, float]]:
    x_start = max(window_x_start, float(placement.x))
    x_end = min(window_x_end, float(placement.x + placement.l))
    y_start = max(0.0, min(container_width, float(placement.y)))
    y_end = max(0.0, min(container_width, float(placement.y + placement.w)))
    if x_end <= x_start + TOLERANCE or y_end <= y_start + TOLERANCE:
        return None
    return x_start, x_end, y_start, y_end


def _derive_local_top_residuals_detailed(
    placements: List[Placement],
    container: Dict,
    window_x_start: float,
    window_x_end: float,
) -> Tuple[List[Space], Dict[str, int]]:
    """Derive roof-clear supported top spaces from committed geometry."""
    x_start = float(window_x_start)
    x_end = float(window_x_end)
    width = float(container.get("W", 0.0) or 0.0)
    height = float(container.get("H", 0.0) or 0.0)
    if x_end <= x_start + TOLERANCE or width <= TOLERANCE or height <= TOLERANCE:
        return [], {
            "support_planes": 0,
            "atomic_cells": 0,
            "complete_face_merges": 0,
        }

    relevant = [
        placement
        for placement in placements
        if _top_rect_intersection(placement, x_start, x_end, width)
        is not None
    ]
    support_planes = _deduplicate_sorted_coordinates(
        [
            placement.z + placement.h
            for placement in relevant
            if placement.stackable
            and height - (placement.z + placement.h) > TOLERANCE
        ]
    )
    residuals: List[Space] = []
    atomic_cells = 0
    complete_face_merges = 0
    for support_z in support_planes:
        support_rectangles = []
        blocker_rectangles = []
        for placement in relevant:
            rectangle = _top_rect_intersection(
                placement,
                x_start,
                x_end,
                width,
            )
            if rectangle is None:
                continue
            if (
                placement.stackable
                and abs(placement.z + placement.h - support_z) <= TOLERANCE
            ):
                support_rectangles.append(rectangle)
            if (
                placement.z < height - TOLERANCE
                and placement.z + placement.h > support_z + TOLERANCE
            ):
                blocker_rectangles.append(rectangle)

        if not support_rectangles:
            continue
        x_breakpoints = [x_start, x_end]
        y_breakpoints = [0.0, width]
        for rect_x_start, rect_x_end, rect_y_start, rect_y_end in (
            support_rectangles + blocker_rectangles
        ):
            x_breakpoints.extend((rect_x_start, rect_x_end))
            y_breakpoints.extend((rect_y_start, rect_y_end))
        x_coordinates = _deduplicate_sorted_coordinates(x_breakpoints)
        y_coordinates = _deduplicate_sorted_coordinates(y_breakpoints)
        plane_spaces: List[Space] = []
        for cell_x_start, cell_x_end in zip(
            x_coordinates,
            x_coordinates[1:],
        ):
            for cell_y_start, cell_y_end in zip(
                y_coordinates,
                y_coordinates[1:],
            ):
                if (
                    cell_x_end <= cell_x_start + TOLERANCE
                    or cell_y_end <= cell_y_start + TOLERANCE
                ):
                    continue
                atomic_cells += 1
                supported = any(
                    cell_x_start >= rect_x_start - TOLERANCE
                    and cell_x_end <= rect_x_end + TOLERANCE
                    and cell_y_start >= rect_y_start - TOLERANCE
                    and cell_y_end <= rect_y_end + TOLERANCE
                    for rect_x_start, rect_x_end, rect_y_start, rect_y_end in (
                        support_rectangles
                    )
                )
                if not supported:
                    continue
                blocked = any(
                    min(cell_x_end, rect_x_end)
                    > max(cell_x_start, rect_x_start) + TOLERANCE
                    and min(cell_y_end, rect_y_end)
                    > max(cell_y_start, rect_y_start) + TOLERANCE
                    for rect_x_start, rect_x_end, rect_y_start, rect_y_end in (
                        blocker_rectangles
                    )
                )
                if blocked:
                    continue
                plane_spaces.append(
                    Space(
                        cell_x_start,
                        cell_y_start,
                        support_z,
                        cell_x_end - cell_x_start,
                        cell_y_end - cell_y_start,
                        height - support_z,
                    )
                )
        merged_plane, plane_merges = _merge_local_top_residuals_detailed(
            plane_spaces
        )
        residuals.extend(merged_plane)
        complete_face_merges += plane_merges

    return (
        merge_local_top_residuals(residuals),
        {
            "support_planes": len(support_planes),
            "atomic_cells": atomic_cells,
            "complete_face_merges": complete_face_merges,
        },
    )


def derive_local_top_residuals(
    placements: List[Placement],
    container: Dict,
    window_x_start: float,
    window_x_end: float,
) -> List[Space]:
    """Return deterministic, roof-clear residuals above coplanar support unions."""
    residuals, _ = _derive_local_top_residuals_detailed(
        placements,
        container,
        window_x_start,
        window_x_end,
    )
    return residuals


def _top_candidate_validation_reason(
    placements: List[Placement],
    context: List[Placement],
    active_space: Space,
    container: Dict,
) -> Optional[str]:
    local_context = list(context) + list(placements)
    for placement in placements:
        if (
            placement.x < active_space.x - TOLERANCE
            or placement.y < active_space.y - TOLERANCE
            or placement.z < active_space.z - TOLERANCE
            or placement.x + placement.l
            > active_space.x + active_space.L + TOLERANCE
            or placement.y + placement.w
            > active_space.y + active_space.W + TOLERANCE
            or placement.z + placement.h
            > active_space.z + active_space.H + TOLERANCE
            or placement.x < -TOLERANCE
            or placement.y < -TOLERANCE
            or placement.z < -TOLERANCE
            or placement.x + placement.l > container["L"] + TOLERANCE
            or placement.y + placement.w > container["W"] + TOLERANCE
            or placement.z + placement.h > container["H"] + TOLERANCE
        ):
            return "placement_out_of_bounds"
    for first_index, first in enumerate(placements):
        if any(
            _frontier_rectangles_overlap(first, second)
            for second in placements[first_index + 1 :]
        ):
            return "overlap_validation_failed"
        if any(
            _frontier_rectangles_overlap(first, second)
            for second in context
        ):
            return "overlap_validation_failed"
    for placement in placements:
        if placement.z > TOLERANCE:
            if not _frontier_supports_full_base(placement, local_context):
                return "support_validation_failed"
    return None


def fill_top_residual_deterministically(
    residual_space: Space,
    anchor_product: NormalizedProduct,
    ordered_products: List[NormalizedProduct],
    remaining_quantities: Dict[int, int],
    next_item_index: Dict[int, int],
    container: Dict,
    loaded_weight: float,
    sequence_restricted: bool,
    eligible_row_indices: Optional[set] = None,
    reserved_payload_weight: float = 0.0,
    committed_placements: Optional[List[Placement]] = None,
    window_x_start: Optional[float] = None,
    window_x_end: Optional[float] = None,
) -> Tuple[List[Placement], float, Dict]:
    """Fill local supported-top spaces bottom-up using Product Blocks."""
    stats = _new_top_infill_stats(
        len({product.sequence for product in ordered_products})
    )
    local_x_start = (
        float(residual_space.x)
        if window_x_start is None
        else float(window_x_start)
    )
    local_x_end = (
        float(residual_space.x + residual_space.L)
        if window_x_end is None
        else float(window_x_end)
    )
    if local_x_end <= local_x_start + TOLERANCE:
        return [], loaded_weight, stats
    committed: List[Placement] = []
    product_priority = {
        product.row_index: index for index, product in enumerate(ordered_products)
    }

    def anchor_eligibility() -> Tuple[bool, Optional[str]]:
        remaining_quantity = int(
            remaining_quantities.get(anchor_product.row_index, 0)
        )
        if remaining_quantity <= 0:
            return False, "no_remaining_quantity"
        if (
            eligible_row_indices is not None
            and anchor_product.row_index not in eligible_row_indices
        ):
            return False, "not_in_eligible_rows"
        return True, None

    def current_residuals() -> Tuple[List[Space], Dict[str, int]]:
        return _derive_local_top_residuals_detailed(
            list(committed_placements or []) + committed,
            container,
            local_x_start,
            local_x_end,
        )

    def record_envelope(
        envelope: List[Space],
        detail: Dict[str, int],
    ) -> None:
        anchor_is_eligible, anchor_eligibility_reason = anchor_eligibility()
        anchor_remaining_quantity = int(
            remaining_quantities.get(anchor_product.row_index, 0)
        )
        stats["top_support_planes_evaluated"] += int(
            detail.get("support_planes", 0)
        )
        stats["top_atomic_cells_evaluated"] += int(
            detail.get("atomic_cells", 0)
        )
        stats["top_complete_face_merges"] += int(
            detail.get("complete_face_merges", 0)
        )
        stats["top_residual_count"] += len(envelope)
        stats["top_residual_volume_available"] += float(
            sum(space.volume for space in envelope)
        )
        stats["top_residual_windows"].append(
            {
                "x_start": float(local_x_start),
                "x_end": float(local_x_end),
                "anchor_product": anchor_product.name,
                "anchor_row_index": int(anchor_product.row_index),
                "anchor_remaining_quantity": anchor_remaining_quantity,
                "anchor_eligible": anchor_is_eligible,
                "anchor_eligibility_reason": anchor_eligibility_reason,
                "support_planes": int(detail.get("support_planes", 0)),
                "residuals": [
                    {
                        "x": float(space.x),
                        "y": float(space.y),
                        "z": float(space.z),
                        "L": float(space.L),
                        "W": float(space.W),
                        "H": float(space.H),
                        "anchor_product": anchor_product.name,
                        "anchor_row_index": int(anchor_product.row_index),
                        "anchor_remaining_quantity": anchor_remaining_quantity,
                        "anchor_eligible": anchor_is_eligible,
                        "anchor_eligibility_reason": anchor_eligibility_reason,
                    }
                    for space in envelope
                ],
            }
        )

    residuals, detail = current_residuals()
    record_envelope(residuals, detail)
    while residuals:
        active_space = min(
            residuals,
            key=lambda space: (
                round(space.z, 9),
                round(space.x, 9),
                -round(space.L * space.W, 9),
                -round(space.volume, 9),
                round(space.y, 9),
                round(space.L, 9),
                round(space.W, 9),
                round(space.H, 9),
            ),
        )
        residuals.remove(active_space)
        stats["top_residuals_evaluated"] += 1
        bounded_container = {
            "L": active_space.L,
            "W": active_space.W,
            "H": active_space.H,
            "max_weight": container.get("max_weight"),
            "tare_weight": container.get("tare_weight"),
        }
        ranked_candidates = []
        eligible_product_names: List[str] = []
        sequence_filtered = 0
        payload_blocked = 0
        generated_candidate_count = 0
        fit_candidate_count = 0
        width_capable = False
        depth_capable = False
        height_capable = False
        rejected_support = 0
        rejected_overlap = 0
        anchor_candidate_evaluated = False

        context = [
            placement
            for placement in (committed_placements or [])
            if placement.x + placement.l > local_x_start + TOLERANCE
            and placement.x < local_x_end - TOLERANCE
        ] + list(committed)
        for product in ordered_products:
            remaining_quantity = int(
                remaining_quantities.get(product.row_index, 0)
            )
            if remaining_quantity <= 0:
                continue
            if (
                eligible_row_indices is not None
                and product.row_index not in eligible_row_indices
            ):
                continue
            if sequence_restricted and product.sequence != anchor_product.sequence:
                if remaining_quantity > 0:
                    sequence_filtered += 1
                continue
            eligible_product_names.append(product.name)
            width_capable = width_capable or any(
                orientation[1] <= active_space.W + TOLERANCE
                for orientation in product.orientations
            )
            depth_capable = depth_capable or any(
                orientation[0] <= active_space.L + TOLERANCE
                for orientation in product.orientations
            )
            height_capable = height_capable or any(
                orientation[2] <= active_space.H + TOLERANCE
                for orientation in product.orientations
            )
            payload_quantity = _payload_units_available(
                container,
                loaded_weight + reserved_payload_weight,
                product.weight,
                remaining_quantity,
            )
            if payload_quantity <= 0:
                payload_blocked += 1
                continue
            if product.row_index == anchor_product.row_index:
                anchor_candidate_evaluated = True
            candidates, evaluated = build_product_block_candidates(
                product,
                bounded_container,
                active_space.L,
            )
            generated_candidate_count += len(candidates)
            stats["top_infill_block_candidates_generated"] += len(candidates)
            stats["top_infill_block_candidates_evaluated"] += evaluated
            residual_footprint = _largest_valid_footprint(
                product,
                bounded_container,
            )
            for candidate in candidates:
                module_count = _fit_count(active_space.L, candidate.depth)
                quantity = min(
                    payload_quantity,
                    module_count * candidate.module_capacity,
                )
                if quantity <= 0:
                    continue
                fit_candidate_count += 1
                depth_required = (
                    int(math.ceil(quantity / candidate.module_capacity))
                    * candidate.depth
                )
                candidate_placements = _materialize_product_block_in_space(
                    product,
                    candidate,
                    active_space,
                    next_item_index[product.row_index],
                    quantity,
                )
                validation_reason = _top_candidate_validation_reason(
                    candidate_placements,
                    context,
                    active_space,
                    container,
                )
                stats["top_support_checks"] += sum(
                    1
                    for placement in candidate_placements
                    if placement.z > TOLERANCE
                )
                if validation_reason is not None:
                    if validation_reason == "support_validation_failed":
                        rejected_support += 1
                    elif validation_reason == "overlap_validation_failed":
                        rejected_overlap += 1
                    continue
                packed_volume = quantity * product.unit_volume
                ranking_key = (
                    -round(packed_volume, 9),
                    -round(
                        candidate.transverse_utilization,
                        12,
                    ),
                    -int(quantity),
                    round(depth_required, 9),
                    -round(residual_footprint, 9),
                    -round(product.unit_volume, 9),
                    -round(product.longest_dimension, 9),
                    product_priority[product.row_index],
                    _candidate_stable_key(candidate),
                )
                ranked_candidates.append(
                    {
                        "product": product,
                        "candidate": candidate,
                        "quantity": int(quantity),
                        "placements": candidate_placements,
                        "depth_required": float(depth_required),
                        "packed_volume": float(packed_volume),
                        "residual_footprint": float(residual_footprint),
                        "ranking_key": ranking_key,
                    }
                )

        if anchor_candidate_evaluated:
            stats["top_anchor_candidate_evaluations"] += 1

        if not ranked_candidates:
            stats["top_candidates_rejected_support"] += rejected_support
            stats["top_candidates_rejected_overlap"] += rejected_overlap
            if not eligible_product_names:
                reason = (
                    "sequence_restriction"
                    if sequence_filtered
                    else "no_remaining_eligible_product"
                )
            elif payload_blocked == len(eligible_product_names):
                reason = "payload_exhausted"
            elif not width_capable:
                reason = "insufficient_width"
            elif not depth_capable:
                reason = "insufficient_x_depth"
            elif not height_capable:
                reason = "insufficient_residual_height"
            elif rejected_support and not rejected_overlap:
                reason = "support_validation_failed"
            elif rejected_overlap:
                reason = "overlap_validation_failed"
            elif fit_candidate_count == 0 and generated_candidate_count == 0:
                reason = "no_enabled_orientation_fits"
            else:
                reason = "no_enabled_orientation_fits"
            stats["top_residual_evaluation_reasons"].append(
                {
                    "x_start": float(active_space.x),
                    "x_end": float(active_space.x + active_space.L),
                    "y_start": float(active_space.y),
                    "y_end": float(active_space.y + active_space.W),
                    "z": float(active_space.z),
                    "support_z": float(active_space.z),
                    "length": float(active_space.L),
                    "width": float(active_space.W),
                    "height": float(active_space.H),
                    "reason": reason,
                    "eligible_products": list(eligible_product_names),
                    "anchor_product": anchor_product.name,
                    "anchor_row_index": int(anchor_product.row_index),
                    "anchor_remaining_quantity": int(
                        remaining_quantities.get(anchor_product.row_index, 0)
                    ),
                    "anchor_eligible": anchor_eligibility()[0],
                    "anchor_eligibility_reason": anchor_eligibility()[1],
                    "anchor_candidate_evaluated": anchor_candidate_evaluated,
                }
            )
            continue

        winner = min(ranked_candidates, key=lambda item: item["ranking_key"])
        filler = winner["product"]
        filler_placements = winner["placements"]
        quantity = len(filler_placements)
        if quantity <= 0:
            continue
        anchor_remaining_before_commit = int(
            remaining_quantities.get(anchor_product.row_index, 0)
        )
        anchor_eligible_before_commit = anchor_eligibility()[0]
        used_depth = max(
            placement.x + placement.l - active_space.x
            for placement in filler_placements
        )
        used_width = max(
            placement.y + placement.w - active_space.y
            for placement in filler_placements
        )
        actual_top_z = max(
            placement.z + placement.h for placement in filler_placements
        )
        committed.extend(filler_placements)
        remaining_quantities[filler.row_index] = max(
            remaining_quantities.get(filler.row_index, 0) - quantity,
            0,
        )
        next_item_index[filler.row_index] += quantity
        loaded_weight += quantity * filler.weight
        filled_volume = quantity * filler.unit_volume
        stats["top_residuals_filled"] += 1
        stats["top_infill_units_total"] += quantity
        stats["top_infill_volume_total"] += filled_volume
        stats["top_residual_volume_filled"] += filled_volume
        stats["top_infill_block_count"] += 1
        row_key = str(filler.row_index)
        stats["top_infill_units_by_product"][row_key] = (
            stats["top_infill_units_by_product"].get(row_key, 0) + quantity
        )
        stats["top_actions"].append(
            {
                "anchor_product": anchor_product.name,
                "anchor_row_index": int(anchor_product.row_index),
                "anchor_remaining_quantity": anchor_remaining_before_commit,
                "anchor_eligible": anchor_eligible_before_commit,
                "anchor_candidate_evaluated": anchor_candidate_evaluated,
                "filler_product": filler.name,
                "filler_row_index": int(filler.row_index),
                "sequence": int(filler.sequence),
                "window_x_start": float(local_x_start),
                "window_x_end": float(local_x_end),
                "support_z": float(active_space.z),
                "residual_x_start": float(active_space.x),
                "residual_x_end": float(active_space.x + active_space.L),
                "residual_y_start": float(active_space.y),
                "residual_y_end": float(active_space.y + active_space.W),
                "residual": {
                    "x": float(active_space.x),
                    "y": float(active_space.y),
                    "z": float(active_space.z),
                    "L": float(active_space.L),
                    "W": float(active_space.W),
                    "H": float(active_space.H),
                },
                "selected_orientations": [
                    [float(value) for value in orientation]
                    for orientation in winner["candidate"].orientations
                ],
                "selected_block": {
                    **_candidate_metadata(winner["candidate"]),
                    "x_start": float(active_space.x),
                    "y_start": float(active_space.y),
                    "z_start": float(active_space.z),
                    "actual_depth_required": float(winner["depth_required"]),
                    "actual_depth_committed": float(used_depth),
                    "actual_width_committed": float(used_width),
                    "actual_top_z": float(actual_top_z),
                },
                "quantity": int(quantity),
                "packed_volume": float(filled_volume),
                "actual_x_depth_used": float(used_depth),
                "actual_width_used": float(used_width),
                "actual_top_z": float(actual_top_z),
                "support_validation": "full_union_supported",
                "selection_reason": (
                    "packed_volume_then_transverse_utilization_then_quantity_"
                    "then_depth_then_residual_local_priority"
                ),
            }
        )
        residuals, detail = current_residuals()
        record_envelope(residuals, detail)

    return committed, loaded_weight, stats


def _unplaced_item(product: NormalizedProduct, item_index: int, reason: str) -> Dict:
    return {
        "product_name": product.name,
        "dims": (product.length, product.width, product.height),
        "orientations": [tuple(orientation) for orientation in product.orientations],
        "weight": product.weight,
        "stackable": product.stackable,
        "sequence": product.sequence,
        "item_index": item_index,
        "row_index": product.row_index,
        "reason": reason,
    }


def _normalize_packing_mode(mode: Optional[str]) -> str:
    return normalize_transport_packing_mode(mode, default=SPACE_EVENLY_MODE)


def _unsupported_mode_result(
    container: Dict,
    products: List[NormalizedProduct],
    requested_mode: str,
) -> Dict:
    unplaced = [
        _unplaced_item(product, item_index, UNSUPPORTED_MODE_MESSAGE)
        for product in products
        for item_index in range(product.qty)
    ]
    return {
        "placements": [],
        "unplaced": unplaced,
        "spaces": [
            Space(0.0, 0.0, 0.0, container["L"], container["W"], container["H"])
        ],
        "loaded_weight": 0.0,
        "strategy": "unavailable",
        "packing_mode": requested_mode,
        "sequence_zones": [],
        "error": UNSUPPORTED_MODE_MESSAGE,
        "errors": [UNSUPPORTED_MODE_MESSAGE],
        "messages": [UNSUPPORTED_MODE_MESSAGE],
    }


def _unplaced_reason(
    product: NormalizedProduct,
    container: Dict,
    loaded_weight: float,
    frontier: float,
) -> str:
    if not any(
        orientation[0] <= container["L"] + TOLERANCE
        and orientation[1] <= container["W"] + TOLERANCE
        and orientation[2] <= container["H"] + TOLERANCE
        for orientation in product.orientations
    ):
        return "No enabled orientation fits the container bounds."
    if (
        product.weight > 0
        and _has_payload_limit(container)
        and loaded_weight + product.weight > container["max_weight"] + TOLERANCE
    ):
        return "Container payload limit reached."
    if frontier >= container["L"] - TOLERANCE:
        return "No longitudinal container residual space remains."
    return "No larger valid Space Evenly residual mini-block fits."


def _frontier_rectangles_overlap(
    first: Placement,
    second: Placement,
) -> bool:
    return (
        min(first.x + first.l, second.x + second.l)
        > max(first.x, second.x) + TOLERANCE
        and min(first.y + first.w, second.y + second.w)
        > max(first.y, second.y) + TOLERANCE
        and min(first.z + first.h, second.z + second.h)
        > max(first.z, second.z) + TOLERANCE
    )


def _frontier_supports_full_base(
    candidate: Placement,
    placements: List[Placement],
) -> bool:
    """Check full rectangular support using only the active local frontier."""
    if candidate.z <= TOLERANCE:
        return True

    unsupported = [(candidate.x, candidate.y, candidate.l, candidate.w)]
    for support in placements:
        if not support.stackable:
            continue
        if abs(support.z + support.h - candidate.z) > TOLERANCE:
            continue

        sx0, sy0 = support.x, support.y
        sx1, sy1 = support.x + support.l, support.y + support.w
        updated = []
        for x0, y0, length, width in unsupported:
            x1, y1 = x0 + length, y0 + width
            ix0, iy0 = max(x0, sx0), max(y0, sy0)
            ix1, iy1 = min(x1, sx1), min(y1, sy1)
            if ix1 <= ix0 + TOLERANCE or iy1 <= iy0 + TOLERANCE:
                updated.append((x0, y0, length, width))
                continue

            if ix0 > x0 + TOLERANCE:
                updated.append((x0, y0, ix0 - x0, width))
            if x1 > ix1 + TOLERANCE:
                updated.append((ix1, y0, x1 - ix1, width))
            middle_length = ix1 - ix0
            if iy0 > y0 + TOLERANCE:
                updated.append((ix0, y0, middle_length, iy0 - y0))
            if y1 > iy1 + TOLERANCE:
                updated.append((ix0, iy1, middle_length, y1 - iy1))

        unsupported = [
            rectangle
            for rectangle in updated
            if rectangle[2] > TOLERANCE and rectangle[3] > TOLERANCE
        ]
        if not unsupported:
            return True
    return False


def _frontier_orientation(
    product: NormalizedProduct,
    candidates: List[ProductBlockCandidate],
    max_depth: float,
    container: Dict,
) -> Tuple[Optional[Tuple[float, float, float]], float]:
    """Choose one stable frontier orientation from shared block candidates."""
    selected = None
    if candidates:
        selected = choose_product_block(
            candidates,
            max(
                candidate.module_capacity
                for candidate in candidates
            ),
            max_depth,
        )
    if selected is not None:
        preferred = list(selected.orientations) + list(product.orientations)
    else:
        preferred = list(product.orientations)

    for orientation in preferred:
        if (
            orientation[0] <= max_depth + TOLERANCE
            and orientation[1] <= container["W"] + TOLERANCE
            and orientation[2] <= container["H"] + TOLERANCE
        ):
            return orientation, float(
                max(orientation[0], selected.depth if selected else 0.0)
            )
    return None, 0.0


def _frontier_grid_placements(
    product: NormalizedProduct,
    quantity: int,
    x_start: float,
    x_depth: float,
    orientation: Tuple[float, float, float],
    container: Dict,
    placements: List[Placement],
    first_item_index: int,
    loaded_weight: float,
    traversal: str = "row_first",
) -> Tuple[List[Placement], float, int]:
    """Populate one bounded frontier slice with a deterministic traversal."""
    length, width, height = orientation
    x_count = _fit_count(x_depth, length)
    y_count = _fit_count(container["W"], width)
    z_count = _fit_count(container["H"], height)
    if not product.stackable:
        z_count = min(z_count, 1)
    if min(x_count, y_count, z_count, quantity) <= 0:
        return [], loaded_weight, 0

    payload_quantity = _payload_units_available(
        container,
        loaded_weight,
        product.weight,
        quantity,
    )
    local = []
    item_offset = 0
    if traversal == "row_first":
        indices = (
            (x_index, z_index, y_index)
            for x_index in range(x_count)
            for z_index in range(z_count)
            for y_index in range(y_count)
        )
    elif traversal == "column_first":
        indices = (
            (x_index, z_index, y_index)
            for x_index in range(x_count)
            for y_index in range(y_count)
            for z_index in range(z_count)
        )
    else:
        raise ValueError(f"Unsupported frontier traversal: {traversal}")

    for x_index, z_index, y_index in indices:
        if item_offset >= payload_quantity:
            return local, loaded_weight, item_offset
        placement = Placement(
            product_name=product.name,
            item_index=first_item_index + item_offset,
            row_index=product.row_index,
            sequence=product.sequence,
            weight=product.weight,
            stackable=product.stackable,
            x=x_start + x_index * length,
            y=y_index * width,
            z=z_index * height,
            l=length,
            w=width,
            h=height,
        )
        if placement.z > TOLERANCE and not _frontier_supports_full_base(
            placement,
            local,
        ):
            continue
        local.append(placement)
        placements.append(placement)
        loaded_weight += product.weight
        item_offset += 1
    return local, loaded_weight, item_offset


def _dgfe_strategy_parts(strategy: str) -> Tuple[str, str]:
    """Return the gravity mode and residual traversal for one DGFE strategy."""
    mapping = {
        "top_down_column_first": ("deferred_top_down", "column_first"),
        "top_down_row_first": ("deferred_top_down", "row_first"),
        "bottom_up_column_first": ("bottom_up", "column_first"),
        "bottom_up_row_first": ("bottom_up", "row_first"),
    }
    try:
        return mapping[strategy]
    except KeyError as exc:
        raise ValueError(f"Unsupported DGFE residual strategy: {strategy}") from exc


def _frontier_residual_candidate_placements(
    product: NormalizedProduct,
    quantity: int,
    x_start: float,
    x_depth: float,
    orientation: Tuple[float, float, float],
    container: Dict,
    first_item_index: int,
    loaded_weight: float,
    strategy: str,
) -> Tuple[List[Placement], float, int]:
    """Construct one quantity-agnostic DGFE residual reservation/layout."""
    gravity_mode, traversal = _dgfe_strategy_parts(strategy)
    if gravity_mode == "bottom_up":
        trial: List[Placement] = []
        return _frontier_grid_placements(
            product,
            quantity,
            x_start,
            x_depth,
            orientation,
            container,
            trial,
            first_item_index,
            loaded_weight,
            traversal=traversal,
        )

    length, width, height = orientation
    x_count = _fit_count(x_depth, length)
    y_count = _fit_count(container["W"], width)
    z_count = _fit_count(container["H"], height)
    if not product.stackable:
        z_count = min(z_count, 1)
    if min(x_count, y_count, z_count, quantity) <= 0:
        return [], loaded_weight, 0

    payload_quantity = _payload_units_available(
        container,
        loaded_weight,
        product.weight,
        quantity,
    )
    top_down_z = [
        float(container["H"] - (level + 1) * height)
        for level in range(z_count)
    ]
    if traversal == "row_first":
        indices = (
            (x_index, z, y_index)
            for x_index in range(x_count)
            for z in top_down_z
            for y_index in range(y_count)
        )
    else:
        indices = (
            (x_index, z, y_index)
            for x_index in range(x_count)
            for y_index in range(y_count)
            for z in top_down_z
        )

    reserved: List[Placement] = []
    for x_index, z, y_index in indices:
        if len(reserved) >= payload_quantity:
            break
        reserved.append(
            Placement(
                product_name=product.name,
                item_index=first_item_index + len(reserved),
                row_index=product.row_index,
                sequence=product.sequence,
                weight=product.weight,
                stackable=product.stackable,
                x=x_start + x_index * length,
                y=y_index * width,
                z=z,
                l=length,
                w=width,
                h=height,
            )
        )
    return (
        reserved,
        loaded_weight + len(reserved) * product.weight,
        len(reserved),
    )


def _frontier_collision_only(placements: List[Placement]) -> List[Placement]:
    """Copy virtual residuals as obstacles that cannot support incoming cargo."""
    return [
        Placement(
            product_name=placement.product_name,
            item_index=placement.item_index,
            row_index=placement.row_index,
            sequence=placement.sequence,
            weight=placement.weight,
            stackable=False,
            x=placement.x,
            y=placement.y,
            z=placement.z,
            l=placement.l,
            w=placement.w,
            h=placement.h,
        )
        for placement in placements
    ]


def _dgfe_envelope_dimensions(
    x_start: float,
    residual_placements: List[Placement],
    next_length: float,
    remaining_length: float,
) -> Tuple[float, int, Optional[int]]:
    """Include all Pi-intersecting X rows and the first clean Pi+1 row."""
    if not residual_placements or next_length <= 0 or remaining_length <= 0:
        return 0.0, 0, None
    residual_x_end = max(
        placement.x + placement.l for placement in residual_placements
    )
    residual_depth = max(residual_x_end - x_start, 0.0)
    intersecting_rows = max(
        1,
        int(math.ceil(max(residual_depth - TOLERANCE, 0.0) / next_length)),
    )
    rows_available = _fit_count(remaining_length, next_length)
    rows_evaluated = min(rows_available, intersecting_rows + 1)
    first_clean_row_index = (
        intersecting_rows
        if rows_available >= intersecting_rows + 1
        else None
    )
    return (
        float(rows_evaluated * next_length),
        int(rows_evaluated),
        first_clean_row_index,
    )


def _placement_with_z(placement: Placement, z: float) -> Placement:
    return Placement(
        product_name=placement.product_name,
        item_index=placement.item_index,
        row_index=placement.row_index,
        sequence=placement.sequence,
        weight=placement.weight,
        stackable=placement.stackable,
        x=placement.x,
        y=placement.y,
        z=float(z),
        l=placement.l,
        w=placement.w,
        h=placement.h,
    )


def _frontier_vertical_path_is_clear(
    reserved: Placement,
    settled_z: float,
    obstacles: List[Placement],
) -> bool:
    """Validate the swept cuboid for a vertical-only deferred-gravity drop."""
    for obstacle in obstacles:
        xy_overlap = (
            min(reserved.x + reserved.l, obstacle.x + obstacle.l)
            > max(reserved.x, obstacle.x) + TOLERANCE
            and min(reserved.y + reserved.w, obstacle.y + obstacle.w)
            > max(reserved.y, obstacle.y) + TOLERANCE
        )
        swept_z_overlap = (
            min(reserved.z + reserved.h, obstacle.z + obstacle.h)
            > max(settled_z, obstacle.z) + TOLERANCE
        )
        if xy_overlap and swept_z_overlap:
            return False
    return True


def _settle_deferred_frontier_residuals(
    reserved: List[Placement],
    fixed_placements: List[Placement],
    container: Dict,
) -> Tuple[List[Placement], List[float], Optional[str]]:
    """Settle virtual Pi cuboids vertically onto full union support."""
    settled_by_item: Dict[int, Placement] = {}
    drops_by_item: Dict[int, float] = {}
    settlement_order = sorted(
        reserved,
        key=lambda placement: (
            placement.z,
            placement.x,
            placement.y,
            placement.item_index,
        ),
    )
    for virtual in settlement_order:
        obstacles = list(fixed_placements) + list(settled_by_item.values())
        support_planes = {0.0}
        support_planes.update(
            float(obstacle.z + obstacle.h)
            for obstacle in obstacles
            if obstacle.stackable
            and obstacle.z + obstacle.h <= virtual.z + TOLERANCE
        )
        selected = None
        for support_z in sorted(support_planes, reverse=True):
            candidate = _placement_with_z(virtual, support_z)
            if candidate.z < -TOLERANCE:
                continue
            if candidate.z + candidate.h > container["H"] + TOLERANCE:
                continue
            if any(
                _frontier_rectangles_overlap(candidate, obstacle)
                for obstacle in obstacles
            ):
                continue
            if not _frontier_supports_full_base(candidate, obstacles):
                continue
            if not _frontier_vertical_path_is_clear(
                virtual,
                support_z,
                obstacles,
            ):
                continue
            selected = candidate
            break
        if selected is None:
            return [], [], "no_vertical_union_supported_settlement"
        settled_by_item[virtual.item_index] = selected
        drops_by_item[virtual.item_index] = float(virtual.z - selected.z)

    settled = [
        settled_by_item[placement.item_index]
        for placement in sorted(reserved, key=lambda item: item.item_index)
    ]
    drops = [
        drops_by_item[placement.item_index]
        for placement in sorted(reserved, key=lambda item: item.item_index)
    ]
    return settled, drops, None


def _validate_frontier_geometry(
    placements: List[Placement],
    container: Dict,
) -> Tuple[bool, Optional[str]]:
    """Validate final local bounds, collisions, and union support."""
    for placement in placements:
        if (
            placement.x < -TOLERANCE
            or placement.y < -TOLERANCE
            or placement.z < -TOLERANCE
            or placement.x + placement.l > container["L"] + TOLERANCE
            or placement.y + placement.w > container["W"] + TOLERANCE
            or placement.z + placement.h > container["H"] + TOLERANCE
        ):
            return False, "placement_out_of_bounds"
    for first_index, first in enumerate(placements):
        if any(
            _frontier_rectangles_overlap(first, second)
            for second in placements[first_index + 1 :]
        ):
            return False, "positive_volume_overlap"
    for placement in placements:
        if placement.z > TOLERANCE and not _frontier_supports_full_base(
            placement,
            placements,
        ):
            return False, "unsupported_elevated_placement"
    return True, None


def _diagnostic_positions(placements: List[Placement]) -> List[List[float]]:
    return [
        [float(placement.x), float(placement.y), float(placement.z)]
        for placement in placements[:DGFE_POSITION_DIAGNOSTIC_LIMIT]
    ]


def _dgfe_x_row_diagnostics(
    placements: List[Placement],
    x_start: float,
    orientation: Optional[Tuple[float, float, float]],
    x_rows_evaluated: int,
    first_clean_x_row_index: Optional[int],
) -> List[Dict]:
    if orientation is None or x_rows_evaluated <= 0:
        return []
    length = orientation[0]
    rows = []
    for row_index in range(x_rows_evaluated):
        row_x = x_start + row_index * length
        rows.append(
            {
                "row_index": int(row_index),
                "x_start": float(row_x),
                "x_end": float(row_x + length),
                "quantity": int(
                    sum(
                        1
                        for placement in placements
                        if abs(placement.x - row_x) <= TOLERANCE
                    )
                ),
                "clean_resynchronization_row": bool(
                    first_clean_x_row_index == row_index
                ),
            }
        )
    return rows


def _frontier_required_depth(
    product: NormalizedProduct,
    quantity: int,
    orientation: Tuple[float, float, float],
    container: Dict,
    loaded_weight: float,
    remaining_length: float,
) -> Tuple[float, int]:
    """Return the bounded X depth needed for one residual orientation."""
    length, width, height = orientation
    payload_quantity = _payload_units_available(
        container,
        loaded_weight,
        product.weight,
        quantity,
    )
    y_count = _fit_count(container["W"], width)
    z_count = _fit_count(container["H"], height)
    if not product.stackable:
        z_count = min(z_count, 1)
    capacity_per_x_slice = y_count * z_count
    if (
        capacity_per_x_slice <= 0
        or length <= 0
        or remaining_length <= 0
    ):
        return 0.0, int(payload_quantity)
    if payload_quantity <= 0:
        return min(float(length), float(remaining_length)), int(payload_quantity)

    nx_required = math.ceil(payload_quantity / capacity_per_x_slice)
    required_depth = nx_required * length
    return min(float(required_depth), float(remaining_length)), int(payload_quantity)


def _frontier_fill_next_product(
    product: NormalizedProduct,
    quantity: int,
    x_start: float,
    x_depth: float,
    orientation: Tuple[float, float, float],
    container: Dict,
    placements: List[Placement],
    first_item_index: int,
    loaded_weight: float,
) -> Tuple[List[Placement], float, int, int]:
    """Fill only the active frontier with a bounded row-first placement pass."""
    length, width, height = orientation
    if (
        length > x_depth + TOLERANCE
        or width > container["W"] + TOLERANCE
        or height > container["H"] + TOLERANCE
        or quantity <= 0
    ):
        return [], loaded_weight, 0, 0

    local = [
        placement
        for placement in placements
        if placement.x >= x_start - TOLERANCE
        and placement.x + placement.l <= x_start + x_depth + TOLERANCE
    ]
    placed = []
    evaluated = 0
    while len(placed) < quantity:
        payload_quantity = _payload_units_available(
            container,
            loaded_weight,
            product.weight,
            quantity - len(placed),
        )
        if payload_quantity <= 0:
            break

        x_values = [
            x_start + index * length
            for index in range(_fit_count(x_depth, length))
        ]
        z_values = {0.0}
        for support in local:
            if (
                support.stackable
                and support.z + support.h <= container["H"] + TOLERANCE
            ):
                z_values.add(float(support.z + support.h))
        y_values = {0.0}
        for existing in local:
            y_values.add(float(existing.y + existing.w))
        y_values.update(
            float(index * width)
            for index in range(_fit_count(container["W"], width) + 1)
        )

        inserted = False
        for x in sorted(set(round(value, 9) for value in x_values)):
            for z in sorted(set(round(value, 9) for value in z_values)):
                for y in sorted(set(round(value, 9) for value in y_values)):
                    evaluated += 1
                    candidate = Placement(
                        product_name=product.name,
                        item_index=first_item_index + len(placed),
                        row_index=product.row_index,
                        sequence=product.sequence,
                        weight=product.weight,
                        stackable=product.stackable,
                        x=x,
                        y=y,
                        z=z,
                        l=length,
                        w=width,
                        h=height,
                    )
                    if (
                        candidate.x < x_start - TOLERANCE
                        or candidate.x + candidate.l
                        > x_start + x_depth + TOLERANCE
                        or candidate.y + candidate.w
                        > container["W"] + TOLERANCE
                        or candidate.z + candidate.h
                        > container["H"] + TOLERANCE
                        or any(
                            _frontier_rectangles_overlap(candidate, existing)
                            for existing in local
                        )
                        or not _frontier_supports_full_base(candidate, local)
                    ):
                        continue
                    local.append(candidate)
                    placements.append(candidate)
                    placed.append(candidate)
                    loaded_weight += product.weight
                    inserted = True
                    break
                if inserted:
                    break
            if inserted:
                break
        if not inserted:
            break
    return placed, loaded_weight, len(placed), evaluated


def _populate_dgfe_next_product_envelope(
    product: NormalizedProduct,
    quantity: int,
    x_start: float,
    x_depth: float,
    orientation: Tuple[float, float, float],
    container: Dict,
    placements: List[Placement],
    first_item_index: int,
    loaded_weight: float,
) -> Tuple[List[Placement], float, int, int]:
    """Populate every deterministic Row-First position in a DGFE envelope."""
    length, width, height = orientation
    if (
        length > x_depth + TOLERANCE
        or width > container["W"] + TOLERANCE
        or height > container["H"] + TOLERANCE
        or quantity <= 0
    ):
        return [], loaded_weight, 0, 0

    local = [
        placement
        for placement in placements
        if placement.x >= x_start - TOLERANCE
        and placement.x + placement.l <= x_start + x_depth + TOLERANCE
    ]
    placed: List[Placement] = []
    evaluated = 0
    payload_quantity = _payload_units_available(
        container,
        loaded_weight,
        product.weight,
        quantity,
    )
    if payload_quantity <= 0:
        return placed, loaded_weight, 0, evaluated

    x_values = [
        x_start + index * length
        for index in range(_fit_count(x_depth, length))
    ]
    y_seeds = {0.0}
    y_seeds.update(float(existing.y + existing.w) for existing in local)
    y_values = set()
    for seed in y_seeds:
        offset = 0
        while seed + offset * width + width <= container["W"] + TOLERANCE:
            y_values.add(float(seed + offset * width))
            offset += 1

    z_seeds = {0.0}
    z_seeds.update(
        float(support.z + support.h)
        for support in local
        if support.stackable
        and support.z + support.h <= container["H"] + TOLERANCE
    )
    z_values = set()
    for seed in z_seeds:
        level = 0
        while seed + level * height + height <= container["H"] + TOLERANCE:
            z_values.add(float(seed + level * height))
            level += 1

    for x in sorted(set(round(value, 9) for value in x_values)):
        for z in sorted(set(round(value, 9) for value in z_values)):
            for y in sorted(set(round(value, 9) for value in y_values)):
                if len(placed) >= payload_quantity:
                    return placed, loaded_weight, len(placed), evaluated
                evaluated += 1
                candidate = Placement(
                    product_name=product.name,
                    item_index=first_item_index + len(placed),
                    row_index=product.row_index,
                    sequence=product.sequence,
                    weight=product.weight,
                    stackable=product.stackable,
                    x=x,
                    y=y,
                    z=z,
                    l=length,
                    w=width,
                    h=height,
                )
                if (
                    candidate.x < x_start - TOLERANCE
                    or candidate.x + candidate.l
                    > x_start + x_depth + TOLERANCE
                    or candidate.y + candidate.w
                    > container["W"] + TOLERANCE
                    or candidate.z + candidate.h
                    > container["H"] + TOLERANCE
                    or any(
                        _frontier_rectangles_overlap(candidate, existing)
                        for existing in local
                    )
                    or not _frontier_supports_full_base(candidate, local)
                ):
                    continue
                local.append(candidate)
                placements.append(candidate)
                placed.append(candidate)
                loaded_weight += product.weight
    return placed, loaded_weight, len(placed), evaluated


def _evaluate_next_product_frontier_orientations(
    product: NormalizedProduct,
    quantity: int,
    x_start: float,
    x_depth: float,
    container: Dict,
    placements: List[Placement],
    first_item_index: int,
    loaded_weight: float,
    preferred_orientation: Optional[Tuple[float, float, float]] = None,
) -> Tuple[Optional[Tuple[float, float, float]], List[Dict], int]:
    """Evaluate every enabled orientation against one active frontier.

    Candidate evaluation uses a shallow copy of the placement list because the
    frontier filler appends only newly-created placements.  The real layout is
    therefore untouched until the deterministic winner has been selected.
    """
    candidates: List[Dict] = []
    for orientation_index, orientation in enumerate(product.orientations):
        length, width, height = orientation
        fits_frontier = (
            length <= x_depth + TOLERANCE
            and width <= container["W"] + TOLERANCE
            and height <= container["H"] + TOLERANCE
            and quantity > 0
        )
        quantity_packed = 0
        evaluated = 0
        if fits_frontier:
            trial_placements = list(placements)
            _, _, quantity_packed, evaluated = _frontier_fill_next_product(
                product,
                quantity,
                x_start,
                x_depth,
                orientation,
                container,
                trial_placements,
                first_item_index,
                loaded_weight,
            )

        row_capacity = _fit_count(container["W"], width)
        width_utilization = (
            min(quantity_packed, row_capacity) * width / container["W"]
            if container["W"] > TOLERANCE
            else 0.0
        )
        candidates.append(
            {
                "orientation_index": orientation_index,
                "orientation": [float(value) for value in orientation],
                "fits_frontier": bool(fits_frontier),
                "quantity_packed": int(quantity_packed),
                "width_utilization": float(width_utilization),
                "evaluated": int(evaluated),
            }
        )

    valid = [candidate for candidate in candidates if candidate["fits_frontier"]]
    if not valid:
        return None, candidates, sum(candidate["evaluated"] for candidate in candidates)

    def rank(candidate: Dict) -> Tuple:
        orientation = tuple(candidate["orientation"])
        preferred = (
            preferred_orientation is not None
            and all(
                abs(value - preferred_value) <= TOLERANCE
                for value, preferred_value in zip(orientation, preferred_orientation)
            )
        )
        return (
            candidate["quantity_packed"],
            candidate["width_utilization"],
            int(preferred),
            -orientation[0],
            -candidate["orientation_index"],
        )

    selected = max(valid, key=rank)
    return (
        tuple(selected["orientation"]),
        candidates,
        sum(candidate["evaluated"] for candidate in candidates),
    )


def _evaluate_frontier_transition_candidate(
    current_product: NormalizedProduct,
    current_residual_qty: int,
    next_product: NormalizedProduct,
    next_remaining_qty: int,
    strategy: str,
    x_start: float,
    x_depth: float,
    current_orientation: Tuple[float, float, float],
    container: Dict,
    placements: List[Placement],
    current_first_item_index: int,
    next_first_item_index: int,
    loaded_weight: float,
    preferred_next_orientation: Optional[Tuple[float, float, float]] = None,
    current_orientation_index: int = 0,
    remaining_length: Optional[float] = None,
    candidate_family: str = "dgfe_extended",
) -> Dict:
    """Evaluate one Native or DGFE-extended residual transition candidate."""
    if candidate_family not in {"native", "dgfe_extended"}:
        raise ValueError(f"Unsupported frontier candidate family: {candidate_family}")
    gravity_mode, residual_traversal = _dgfe_strategy_parts(strategy)
    residual_depth, _ = _frontier_required_depth(
        current_product,
        current_residual_qty,
        current_orientation,
        container,
        loaded_weight,
        x_depth if remaining_length is None else remaining_length,
    )
    (
        virtual_or_bottom_up,
        loaded_after_current,
        current_reserved_qty,
    ) = _frontier_residual_candidate_placements(
        current_product,
        current_residual_qty,
        x_start,
        residual_depth,
        current_orientation,
        container,
        current_first_item_index,
        loaded_weight,
        strategy,
    )
    virtual_positions = (
        _diagnostic_positions(virtual_or_bottom_up)
        if gravity_mode == "deferred_top_down"
        else []
    )
    pi_residual_x_footprint = (
        max(
            placement.x + placement.l
            for placement in virtual_or_bottom_up
        )
        - x_start
        if virtual_or_bottom_up
        else 0.0
    )
    current_obstacles = (
        _frontier_collision_only(virtual_or_bottom_up)
        if gravity_mode == "deferred_top_down"
        else list(virtual_or_bottom_up)
    )
    trial_placements = list(placements) + current_obstacles

    next_placements: List[Placement] = []
    next_selected_orientation = None
    next_selected_orientation_index = None
    next_orientation_candidates: List[Dict] = []
    next_valid_orientation_count = 0
    next_qty = 0
    loaded_after = loaded_after_current
    candidate_evaluations = 0
    envelope_depth = (
        pi_residual_x_footprint
        if candidate_family == "native"
        else residual_depth
    )
    x_rows_evaluated = 0
    first_clean_x_row_index = None

    if current_reserved_qty == current_residual_qty:
        (
            next_selected_orientation,
            next_orientation_candidates,
            candidate_evaluations,
        ) = _evaluate_next_product_frontier_orientations(
            next_product,
            next_remaining_qty,
            x_start,
            pi_residual_x_footprint,
            container,
            trial_placements,
            next_first_item_index,
            loaded_after_current,
            preferred_next_orientation,
        )
        next_valid_orientation_count = sum(
            1
            for candidate in next_orientation_candidates
            if candidate["fits_frontier"]
        )
        if next_selected_orientation is not None:
            next_selected_orientation_index = next(
                candidate["orientation_index"]
                for candidate in next_orientation_candidates
                if tuple(candidate["orientation"]) == next_selected_orientation
            )
            if candidate_family == "native":
                envelope_depth = pi_residual_x_footprint
                x_rows_evaluated = _fit_count(
                    envelope_depth,
                    next_selected_orientation[0],
                )
                first_clean_x_row_index = None
            else:
                envelope_depth, x_rows_evaluated, first_clean_x_row_index = (
                    _dgfe_envelope_dimensions(
                        x_start,
                        virtual_or_bottom_up,
                        next_selected_orientation[0],
                        x_depth if remaining_length is None else remaining_length,
                    )
                )
            population_trial = list(placements) + current_obstacles
            (
                next_placements,
                loaded_after,
                next_qty,
                population_evaluations,
            ) = (
                _frontier_fill_next_product
                if candidate_family == "native"
                else _populate_dgfe_next_product_envelope
            )(
                next_product,
                next_remaining_qty,
                x_start,
                envelope_depth,
                next_selected_orientation,
                container,
                population_trial,
                next_first_item_index,
                loaded_after_current,
            )
            candidate_evaluations += population_evaluations

    gravity_applied = gravity_mode == "deferred_top_down"
    gravity_drop_distances: List[float] = []
    invalid_reason = None
    if gravity_applied:
        (
            current_placements,
            gravity_drop_distances,
            invalid_reason,
        ) = _settle_deferred_frontier_residuals(
            virtual_or_bottom_up,
            next_placements,
            container,
        )
    else:
        current_placements = virtual_or_bottom_up

    final_local = current_placements + next_placements
    support_valid = False
    if invalid_reason is None:
        support_valid, invalid_reason = _validate_frontier_geometry(
            final_local,
            container,
        )
    if current_reserved_qty <= 0:
        support_valid = False
        invalid_reason = "current_residual_does_not_fit"
    current_final_qty = len(current_placements) if support_valid else 0
    valid = bool(support_valid and current_final_qty == current_reserved_qty)
    committed_placements = final_local if valid else []
    if not valid:
        loaded_after = loaded_weight

    current_packed_volume = current_final_qty * current_product.unit_volume
    next_packed_volume = next_qty * next_product.unit_volume if valid else 0.0
    total_packed_volume = current_packed_volume + next_packed_volume
    frontier_prism_volume = (
        envelope_depth * container["W"] * container["H"]
    )
    frontier_volume_efficiency = (
        total_packed_volume / frontier_prism_volume
        if frontier_prism_volume > TOLERANCE
        else 0.0
    )
    phase_diagnostics = [
        (
            "candidate_residual_reserved"
            if gravity_mode == "deferred_top_down"
            else "candidate_residual_bottom_up"
        )
    ]
    if current_reserved_qty == current_residual_qty:
        phase_diagnostics.extend(
            [
                "next_product_all_orientation_evaluation",
                "next_product_row_first_population",
            ]
        )
    if gravity_applied:
        phase_diagnostics.append("gravity_settlement")
    phase_diagnostics.extend(["physical_validation", "candidate_scoring"])

    return {
        "candidate_family": candidate_family,
        "strategy": strategy,
        "current_product_orientation": [
            float(value) for value in current_orientation
        ],
        "current_product_orientation_index": int(current_orientation_index),
        "gravity_mode": gravity_mode,
        "residual_traversal": residual_traversal,
        "placements": committed_placements,
        "current_product_placements": current_placements,
        "next_product_placements": next_placements,
        "current_product_qty_reserved_or_placed": int(current_reserved_qty),
        "current_product_qty_packed": int(current_final_qty),
        "pi_residual_x_footprint": float(pi_residual_x_footprint),
        "residual_frontier_depth": float(residual_depth),
        "frontier_depth": float(envelope_depth),
        "frontier_x_start": float(x_start),
        "frontier_x_end": float(x_start + envelope_depth),
        "envelope_x_start": float(x_start),
        "envelope_x_end": float(x_start + envelope_depth),
        "envelope_depth": float(envelope_depth),
        "x_rows_evaluated": int(x_rows_evaluated),
        "first_clean_x_row_index": first_clean_x_row_index,
        "next_product_qty_packed": int(next_qty if valid else 0),
        "next_product_selected_orientation": next_selected_orientation,
        "next_product_selected_orientation_index": next_selected_orientation_index,
        "next_product_orientation_candidates": next_orientation_candidates,
        "next_product_valid_orientation_count": int(next_valid_orientation_count),
        "next_product_width_used": float(
            _fit_count(container["W"], next_selected_orientation[1])
            * next_selected_orientation[1]
            if next_selected_orientation is not None
            else 0.0
        ),
        "next_product_width_utilization": float(
            (
                _fit_count(container["W"], next_selected_orientation[1])
                * next_selected_orientation[1]
                / container["W"]
            )
            if next_selected_orientation is not None
            and container["W"] > TOLERANCE
            else 0.0
        ),
        "next_product_x_rows": _dgfe_x_row_diagnostics(
            next_placements,
            x_start,
            next_selected_orientation,
            x_rows_evaluated,
            first_clean_x_row_index,
        ),
        "virtual_residual_positions": virtual_positions,
        "settled_residual_positions": _diagnostic_positions(current_placements),
        "residual_positions_truncated": bool(
            len(virtual_or_bottom_up) > DGFE_POSITION_DIAGNOSTIC_LIMIT
        ),
        "gravity_applied": bool(gravity_applied),
        "gravity_drop_distances": [
            float(distance) for distance in gravity_drop_distances
        ],
        "support_valid": bool(support_valid),
        "support_plane_count": int(
            len(
                {
                    round(placement.z, 9)
                    for placement in current_placements
                    if placement.z > TOLERANCE
                }
            )
        ),
        "current_product_packed_volume": float(current_packed_volume),
        "next_product_packed_volume": float(next_packed_volume),
        "total_frontier_packed_volume": float(total_packed_volume),
        "frontier_prism_volume": float(frontier_prism_volume),
        "frontier_volume_efficiency": float(frontier_volume_efficiency),
        "loaded_weight_after": float(loaded_after),
        "candidate_evaluations": int(candidate_evaluations),
        "valid": valid,
        "invalid_reason": invalid_reason,
        "phase_diagnostics": phase_diagnostics,
    }


def _frontier_regular_block_efficiency(
    product: NormalizedProduct,
    quantity: int,
    container: Dict,
    remaining_length: float,
    loaded_weight: float,
) -> Tuple[Optional[float], Optional[Dict]]:
    """Return the best normal Product Block alternative after a Native frontier."""
    if quantity <= 0 or remaining_length <= TOLERANCE:
        return None, None

    feasible_qty = _payload_units_available(
        container,
        loaded_weight,
        product.weight,
        quantity,
    )
    candidates, _ = build_product_block_candidates(
        product,
        container,
        remaining_length,
    )
    selected = choose_product_block(
        candidates,
        feasible_qty,
        remaining_length,
    )
    if selected is None:
        return None, None
    return float(selected.transverse_utilization), _candidate_metadata(selected)


def _evaluate_frontier_transition_candidate_pair(
    current_product: NormalizedProduct,
    current_residual_qty: int,
    next_product: NormalizedProduct,
    next_remaining_qty: int,
    strategy: str,
    x_start: float,
    x_depth: float,
    current_orientation: Tuple[float, float, float],
    container: Dict,
    placements: List[Placement],
    current_first_item_index: int,
    next_first_item_index: int,
    loaded_weight: float,
    preferred_next_orientation: Optional[Tuple[float, float, float]] = None,
    current_orientation_index: int = 0,
    remaining_length: Optional[float] = None,
) -> Tuple[Dict, Dict]:
    """Preserve Native and DGFE-extended outcomes for one base candidate.

    The extended family is eligible only when Native is physically invalid or
    the volume gained per extra X prism beats the next product's normal block
    transverse utilization. This keeps extension value local and bounded.
    """
    evaluation_arguments = (
        current_product,
        current_residual_qty,
        next_product,
        next_remaining_qty,
        strategy,
        x_start,
        x_depth,
        current_orientation,
        container,
        placements,
        current_first_item_index,
        next_first_item_index,
        loaded_weight,
        preferred_next_orientation,
    )
    evaluation_keywords = {
        "current_orientation_index": current_orientation_index,
        "remaining_length": remaining_length,
    }
    native = _evaluate_frontier_transition_candidate(
        *evaluation_arguments,
        **evaluation_keywords,
        candidate_family="native",
    )
    extended = _evaluate_frontier_transition_candidate(
        *evaluation_arguments,
        **evaluation_keywords,
        candidate_family="dgfe_extended",
    )

    native_depth = float(native["frontier_depth"])
    extended_depth = float(extended["frontier_depth"])
    extra_depth = max(extended_depth - native_depth, 0.0)
    native_next_qty = int(native["next_product_qty_packed"])
    extended_next_qty = int(extended["next_product_qty_packed"])
    pair_is_valid = bool(native["valid"] and extended["valid"])
    extra_volume = (
        max(
            float(extended["total_frontier_packed_volume"])
            - float(native["total_frontier_packed_volume"]),
            0.0,
        )
        if pair_is_valid
        else 0.0
    )
    extra_prism_volume = extra_depth * container["W"] * container["H"]
    marginal_efficiency = (
        extra_volume / extra_prism_volume
        if pair_is_valid and extra_prism_volume > TOLERANCE
        else None
    )

    regular_block_efficiency = None
    regular_block = None
    if native["valid"]:
        remaining_after_native = max(
            (
                x_depth if remaining_length is None else remaining_length
            )
            - native_depth,
            0.0,
        )
        regular_block_efficiency, regular_block = (
            _frontier_regular_block_efficiency(
                next_product,
                max(next_remaining_qty - native_next_qty, 0),
                container,
                remaining_after_native,
                native["loaded_weight_after"],
            )
        )

    extension_value_delta = (
        marginal_efficiency - regular_block_efficiency
        if marginal_efficiency is not None
        and regular_block_efficiency is not None
        else None
    )
    if not extended["valid"]:
        extension_justified = False
        extension_decision_reason = "extended_invalid"
    elif not native["valid"]:
        extension_justified = True
        extension_decision_reason = "native_invalid"
    elif extra_depth <= TOLERANCE:
        extension_justified = False
        extension_decision_reason = "no_meaningful_extension"
    elif extra_volume <= TOLERANCE or extended_next_qty <= native_next_qty:
        extension_justified = False
        extension_decision_reason = "no_additional_packed_volume"
    elif regular_block_efficiency is None:
        extension_justified = True
        extension_decision_reason = "no_regular_block_alternative"
    elif extension_value_delta is not None and (
        extension_value_delta > FRONTIER_EFFICIENCY_TOLERANCE
    ):
        extension_justified = True
        extension_decision_reason = "marginal_efficiency_exceeds_regular_block"
    elif extension_value_delta is not None and (
        abs(extension_value_delta) <= FRONTIER_EFFICIENCY_TOLERANCE
    ):
        extension_justified = False
        extension_decision_reason = "native_preferred_equal_extension_value"
    else:
        extension_justified = False
        extension_decision_reason = (
            "native_preferred_regular_block_more_efficient"
        )

    shared_diagnostics = {
        "native_frontier_depth": native_depth,
        "extended_frontier_depth": extended_depth,
        "extra_extension_depth": float(extra_depth),
        "native_next_product_qty": native_next_qty,
        "extended_next_product_qty": extended_next_qty,
        "dgfe_extra_packed_volume": float(extra_volume),
        "dgfe_marginal_efficiency": (
            float(marginal_efficiency)
            if marginal_efficiency is not None
            else None
        ),
        "next_product_regular_block_efficiency": (
            float(regular_block_efficiency)
            if regular_block_efficiency is not None
            else None
        ),
        "next_product_regular_block": regular_block,
        "extension_value_delta": (
            float(extension_value_delta)
            if extension_value_delta is not None
            else None
        ),
        "extension_justified": bool(extension_justified),
        "extension_decision_reason": extension_decision_reason,
    }
    native.update(
        {
            **shared_diagnostics,
            "family_eligible": bool(native["valid"] and not extension_justified),
        }
    )
    extended.update(
        {
            **shared_diagnostics,
            "family_eligible": bool(extended["valid"] and extension_justified),
        }
    )
    return native, extended


def _select_frontier_transition_candidate(
    candidates: List[Dict],
) -> Tuple[Dict, str]:
    """Select a physical transition candidate with the stable Pi-first ranking."""
    valid_candidates = [candidate for candidate in candidates if candidate.get("valid")]
    ranking_candidates = valid_candidates or candidates
    maximum_current_qty = max(
        candidate["current_product_qty_packed"] for candidate in ranking_candidates
    )
    current_shortlist = [
        candidate
        for candidate in ranking_candidates
        if candidate["current_product_qty_packed"] == maximum_current_qty
    ]
    positive_depth_shortlist = [
        candidate
        for candidate in current_shortlist
        if candidate.get("frontier_depth", 1.0) > TOLERANCE
    ]
    if positive_depth_shortlist:
        current_shortlist = positive_depth_shortlist
    if len(current_shortlist) == 1:
        winner = current_shortlist[0]
        return winner, "current_product_quantity"

    minimum_pi_footprint = min(
        candidate.get(
            "pi_residual_x_footprint",
            candidate.get("frontier_depth", 0.0),
        )
        for candidate in current_shortlist
    )
    footprint_shortlist = [
        candidate
        for candidate in current_shortlist
        if abs(
            candidate.get(
                "pi_residual_x_footprint",
                candidate.get("frontier_depth", 0.0),
            )
            - minimum_pi_footprint
        )
        <= TOLERANCE
    ]
    footprint_decided = len(footprint_shortlist) < len(current_shortlist)
    if len(footprint_shortlist) == 1:
        return footprint_shortlist[0], "smaller_pi_residual_x_footprint"

    eligible_family_shortlist = [
        candidate
        for candidate in footprint_shortlist
        if candidate.get("family_eligible", True)
    ]
    family_shortlist = eligible_family_shortlist or footprint_shortlist
    if len(family_shortlist) == 1:
        winner = family_shortlist[0]
        if footprint_decided:
            return winner, "smaller_pi_residual_x_footprint"
        return winner, winner.get(
            "extension_decision_reason",
            "candidate_family_value",
        )

    maximum_efficiency = max(
        candidate.get("frontier_volume_efficiency", 0.0)
        for candidate in family_shortlist
    )
    efficiency_shortlist = [
        candidate
        for candidate in family_shortlist
        if maximum_efficiency - candidate.get("frontier_volume_efficiency", 0.0)
        <= FRONTIER_EFFICIENCY_TOLERANCE
    ]
    maximum_next_qty = max(
        candidate["next_product_qty_packed"] for candidate in efficiency_shortlist
    )
    next_qty_shortlist = [
        candidate
        for candidate in efficiency_shortlist
        if candidate["next_product_qty_packed"] == maximum_next_qty
    ]
    minimum_depth = min(
        candidate.get("frontier_depth", 0.0)
        for candidate in next_qty_shortlist
    )
    depth_shortlist = [
        candidate
        for candidate in next_qty_shortlist
        if abs(candidate.get("frontier_depth", 0.0) - minimum_depth) <= TOLERANCE
    ]
    row_first_shortlist = [
        candidate
        for candidate in depth_shortlist
        if candidate.get("residual_traversal", candidate.get("strategy"))
        in {"row_first", "top_down_row_first", "bottom_up_row_first"}
    ]
    row_first_tie = bool(row_first_shortlist) and len(row_first_shortlist) < len(
        depth_shortlist
    )
    traversal_shortlist = row_first_shortlist or depth_shortlist
    bottom_up_shortlist = [
        candidate
        for candidate in traversal_shortlist
        if candidate.get("gravity_mode", "bottom_up") == "bottom_up"
    ]
    bottom_up_tie = bool(bottom_up_shortlist) and len(bottom_up_shortlist) < len(
        traversal_shortlist
    )
    gravity_shortlist = bottom_up_shortlist or traversal_shortlist
    winner = min(
        gravity_shortlist,
        key=lambda candidate: candidate.get("current_product_orientation_index", 0),
    )

    if footprint_decided:
        return winner, "smaller_pi_residual_x_footprint"
    if maximum_efficiency - min(
        candidate.get("frontier_volume_efficiency", 0.0)
        for candidate in family_shortlist
    ) > FRONTIER_EFFICIENCY_TOLERANCE:
        return winner, "better_frontier_efficiency"
    if len(
        {candidate["next_product_qty_packed"] for candidate in efficiency_shortlist}
    ) > 1:
        return winner, "more_next_product_units"
    if len(
        {candidate.get("frontier_depth", 0.0) for candidate in next_qty_shortlist}
    ) > 1:
        return winner, "smaller_frontier_depth"
    if row_first_tie:
        return winner, "tie_prefer_row_first"
    if bottom_up_tie:
        return winner, "tie_prefer_bottom_up"
    return winner, "stable_orientation_tiebreak"


def _frontier_support_surface_count(placements: List[Placement]) -> int:
    """Count contiguous local top surfaces available to the frontier."""
    grouped = {}
    for placement in placements:
        if not placement.stackable:
            continue
        key = (
            round(placement.x, 9),
            round(placement.z + placement.h, 9),
            round(placement.l, 9),
            placement.row_index,
        )
        grouped.setdefault(key, []).append(
            (placement.y, placement.y + placement.w)
        )

    surface_count = 0
    for intervals in grouped.values():
        current_end = None
        for start, end in sorted(intervals):
            if current_end is None or start > current_end + TOLERANCE:
                surface_count += 1
            current_end = max(
                current_end if current_end is not None else end,
                end,
            )
    return surface_count


def _select_space_evenly_residual_anchor(
    ordered_products: List[NormalizedProduct],
    remaining: Dict[int, int],
    container: Dict,
    loaded_weight: float,
    available_length: float,
) -> Optional[NormalizedProduct]:
    """Return the first feasible residual product in established product order."""
    for product in ordered_products:
        quantity = remaining.get(product.row_index, 0)
        if quantity <= 0:
            continue
        if _payload_units_available(
            container,
            loaded_weight,
            product.weight,
            quantity,
        ) <= 0:
            continue
        if any(
            orientation[0] <= available_length + TOLERANCE
            and orientation[1] <= container["W"] + TOLERANCE
            and orientation[2] <= container["H"] + TOLERANCE
            for orientation in product.orientations
        ):
            return product
    return None


def _space_evenly_secondary_orientation_candidates(
    product: NormalizedProduct,
    quantity: int,
    x_start: float,
    x_depth: float,
    container: Dict,
    local_placements: List[Placement],
    first_item_index: int,
    loaded_weight: float,
    preferred_orientation: Optional[Tuple[float, float, float]],
) -> Tuple[Optional[Dict], List[Dict]]:
    """Evaluate every enabled orientation without mutating the frontier state."""
    candidates: List[Dict] = []
    prism_volume = x_depth * container["W"] * container["H"]
    for orientation_index, orientation in enumerate(product.orientations):
        trial = list(local_placements)
        placed, loaded_after, packed, evaluated = _frontier_fill_next_product(
            product,
            quantity,
            x_start,
            x_depth,
            orientation,
            container,
            trial,
            first_item_index,
            loaded_weight,
        )
        row_capacity = _fit_count(container["W"], orientation[1])
        width_utilization = (
            min(packed, row_capacity) * orientation[1] / container["W"]
            if container["W"] > TOLERANCE
            else 0.0
        )
        local_volume_utilization = (
            packed * product.unit_volume / prism_volume
            if prism_volume > TOLERANCE
            else 0.0
        )
        preferred = bool(
            preferred_orientation is not None
            and all(
                abs(value - preferred_value) <= TOLERANCE
                for value, preferred_value in zip(
                    orientation,
                    preferred_orientation,
                )
            )
        )
        candidates.append(
            {
                "orientation_index": int(orientation_index),
                "orientation": [float(value) for value in orientation],
                "quantity_packed": int(packed),
                "width_utilization": float(width_utilization),
                "local_volume_utilization": float(local_volume_utilization),
                "additional_x_requirement": float(orientation[0]),
                "preferred_orientation": preferred,
                "local_placement_evaluations": int(evaluated),
                "placements": placed,
                "loaded_weight_after": float(loaded_after),
            }
        )

    if not candidates:
        return None, []
    winner = max(
        candidates,
        key=lambda candidate: (
            candidate["quantity_packed"],
            candidate["width_utilization"],
            candidate["local_volume_utilization"],
            -candidate["additional_x_requirement"],
            int(candidate["preferred_orientation"]),
            -candidate["orientation_index"],
        ),
    )
    if winner["quantity_packed"] <= 0:
        winner = None
    return winner, candidates


def _populate_space_evenly_frontier_pool(
    ordered_products: List[NormalizedProduct],
    anchor: NormalizedProduct,
    remaining: Dict[int, int],
    x_start: float,
    x_depth: float,
    container: Dict,
    base_placements: List[Placement],
    next_item_index: Dict[int, int],
    loaded_weight: float,
    preferred_orientations: Dict[int, Tuple[float, float, float]],
) -> Tuple[List[Placement], float, Dict[int, int], List[Dict], int]:
    """Populate other residual SKUs across one complete bounded frontier."""
    local = list(base_placements)
    packed_by_product: Dict[int, int] = {}
    orientation_diagnostics: List[Dict] = []
    local_evaluations = 0

    for product in ordered_products:
        if product.row_index == anchor.row_index:
            continue
        quantity = remaining.get(product.row_index, 0)
        if quantity <= 0:
            continue
        winner, candidates = _space_evenly_secondary_orientation_candidates(
            product,
            quantity,
            x_start,
            x_depth,
            container,
            local,
            next_item_index[product.row_index],
            loaded_weight,
            preferred_orientations.get(product.row_index),
        )
        local_evaluations += sum(
            candidate["local_placement_evaluations"]
            for candidate in candidates
        )
        orientation_diagnostics.append(
            {
                "row_index": int(product.row_index),
                "product_name": product.name,
                "selected_orientation_index": (
                    int(winner["orientation_index"])
                    if winner is not None
                    else None
                ),
                "selected_orientation": (
                    list(winner["orientation"])
                    if winner is not None
                    else None
                ),
                "quantity_packed": (
                    int(winner["quantity_packed"])
                    if winner is not None
                    else 0
                ),
                "orientation_candidates": [
                    {
                        key: value
                        for key, value in candidate.items()
                        if key not in {"placements", "loaded_weight_after"}
                    }
                    for candidate in candidates
                ],
            }
        )
        if winner is None:
            continue
        selected_placements = list(winner["placements"])
        local.extend(selected_placements)
        loaded_weight = float(winner["loaded_weight_after"])
        packed_by_product[product.row_index] = len(selected_placements)

    return (
        local[len(base_placements) :],
        loaded_weight,
        packed_by_product,
        orientation_diagnostics,
        local_evaluations,
    )


def _evaluate_space_evenly_anchor_candidate(
    anchor: NormalizedProduct,
    anchor_quantity: int,
    anchor_orientation: Tuple[float, float, float],
    anchor_orientation_index: int,
    strategy: str,
    candidate_family: str,
    x_start: float,
    anchor_depth: float,
    committed_depth: float,
    container: Dict,
    ordered_products: List[NormalizedProduct],
    remaining: Dict[int, int],
    next_item_index: Dict[int, int],
    loaded_weight: float,
    preferred_orientations: Dict[int, Tuple[float, float, float]],
) -> Dict:
    """Build, populate, settle, and validate one Space Evenly frontier trial."""
    gravity_mode, residual_traversal = _dgfe_strategy_parts(strategy)
    reserved_or_bottom_up, loaded_after_anchor, reserved_qty = (
        _frontier_residual_candidate_placements(
            anchor,
            anchor_quantity,
            x_start,
            anchor_depth,
            anchor_orientation,
            container,
            next_item_index[anchor.row_index],
            loaded_weight,
            strategy,
        )
    )
    pi_x_footprint = (
        max(placement.x + placement.l for placement in reserved_or_bottom_up)
        - x_start
        if reserved_or_bottom_up
        else 0.0
    )
    effective_depth = (
        pi_x_footprint
        if candidate_family == "native"
        else max(committed_depth, pi_x_footprint)
    )
    anchor_obstacles = (
        _frontier_collision_only(reserved_or_bottom_up)
        if gravity_mode == "deferred_top_down"
        else list(reserved_or_bottom_up)
    )
    remaining_after_anchor = dict(remaining)
    remaining_after_anchor[anchor.row_index] = max(
        remaining_after_anchor.get(anchor.row_index, 0) - reserved_qty,
        0,
    )
    (
        secondary_placements,
        loaded_after,
        secondary_counts,
        secondary_orientation_diagnostics,
        local_evaluations,
    ) = _populate_space_evenly_frontier_pool(
        ordered_products,
        anchor,
        remaining_after_anchor,
        x_start,
        effective_depth,
        container,
        anchor_obstacles,
        next_item_index,
        loaded_after_anchor,
        preferred_orientations,
    )

    invalid_reason = None
    gravity_drop_distances: List[float] = []
    if gravity_mode == "deferred_top_down":
        anchor_placements, gravity_drop_distances, invalid_reason = (
            _settle_deferred_frontier_residuals(
                reserved_or_bottom_up,
                secondary_placements,
                container,
            )
        )
    else:
        anchor_placements = reserved_or_bottom_up

    final_local = anchor_placements + secondary_placements
    valid = False
    if invalid_reason is None:
        valid, invalid_reason = _validate_frontier_geometry(
            final_local,
            container,
        )
    if reserved_qty <= 0:
        valid = False
        invalid_reason = "anchor_does_not_fit"

    anchor_packed = len(anchor_placements) if valid else 0
    if not valid:
        final_local = []
        secondary_counts = {}
        loaded_after = loaded_weight
    packed_by_product = {
        anchor.row_index: int(anchor_packed),
        **{
            row_index: int(quantity)
            for row_index, quantity in secondary_counts.items()
        },
    }
    packed_volume = sum(
        placement.l * placement.w * placement.h
        for placement in final_local
    )
    frontier_prism_volume = effective_depth * container["W"] * container["H"]
    frontier_efficiency = (
        packed_volume / frontier_prism_volume
        if frontier_prism_volume > TOLERANCE
        else 0.0
    )
    other_volume = packed_volume - anchor_packed * anchor.unit_volume
    remaining_after = {
        row_index: max(remaining.get(row_index, 0) - packed, 0)
        for row_index, packed in packed_by_product.items()
    }
    for product in ordered_products:
        remaining_after.setdefault(
            product.row_index,
            int(remaining.get(product.row_index, 0)),
        )
    support_planes = {0.0}
    support_planes.update(
        float(placement.z + placement.h)
        for placement in final_local
        if placement.stackable
    )
    support_relationships = sum(
        1 for placement in final_local if placement.z > TOLERANCE
    )
    return {
        "candidate_family": candidate_family,
        "strategy": strategy,
        "gravity_mode": gravity_mode,
        "residual_traversal": residual_traversal,
        "anchor_orientation": [float(value) for value in anchor_orientation],
        "anchor_orientation_index": int(anchor_orientation_index),
        "anchor_qty_requested": int(anchor_quantity),
        "anchor_qty_reserved_or_placed": int(reserved_qty),
        "anchor_qty_packed": int(anchor_packed),
        "anchor_pi_x_footprint": float(pi_x_footprint),
        "native_depth": float(pi_x_footprint),
        "committed_depth": float(effective_depth),
        "x_start": float(x_start),
        "x_end": float(x_start + effective_depth),
        "placements": final_local,
        "anchor_placements": anchor_placements,
        "products_quantities_packed": packed_by_product,
        "other_products_packed": [
            {
                "row_index": int(product.row_index),
                "product_name": product.name,
                "quantity": int(packed_by_product.get(product.row_index, 0)),
            }
            for product in ordered_products
            if product.row_index != anchor.row_index
            and packed_by_product.get(product.row_index, 0) > 0
        ],
        "other_products_quantity_packed": int(sum(secondary_counts.values())),
        "other_products_packed_volume": float(other_volume),
        "frontier_packed_volume": float(packed_volume),
        "frontier_prism_volume": float(frontier_prism_volume),
        "frontier_volume_efficiency": float(frontier_efficiency),
        "support_plane_count": int(len(support_planes)),
        "support_surface_count": int(
            _frontier_support_surface_count(final_local)
        ),
        "support_relationship_count": int(support_relationships),
        "secondary_orientation_diagnostics": secondary_orientation_diagnostics,
        "local_placement_evaluations": int(local_evaluations),
        "candidate_evaluations": int(
            1
            + local_evaluations
            + sum(
                len(item["orientation_candidates"])
                for item in secondary_orientation_diagnostics
            )
        ),
        "gravity_applied": bool(gravity_mode == "deferred_top_down"),
        "gravity_drop_distances": [
            float(distance) for distance in gravity_drop_distances
        ],
        "physical_validation": {
            "valid": bool(valid),
            "invalid_reason": invalid_reason,
            "bounds": bool(valid),
            "overlap": bool(valid),
            "full_base_union_support": bool(valid),
        },
        "valid": bool(valid),
        "invalid_reason": invalid_reason,
        "loaded_weight_after": float(loaded_after),
        "remaining_after": remaining_after,
        "extension_evaluated": candidate_family == "extended",
        "extension_justified": False,
        "extension_marginal_efficiency": None,
        "next_clean_frontier_efficiency": None,
        "extension_decision_reason": "native_candidate",
        "family_eligible": candidate_family == "native" and bool(valid),
    }


def _space_evenly_clean_frontier_efficiency(
    product: NormalizedProduct,
    quantity: int,
    container: Dict,
    remaining_length: float,
    loaded_weight: float,
    ordered_products: List[NormalizedProduct],
    remaining: Dict[int, int],
    next_item_index: Dict[int, int],
    preferred_orientations: Dict[int, Tuple[float, float, float]],
) -> Tuple[Optional[float], int, int]:
    """Estimate Pj cleanly using the same whole-pool native frontier physics."""
    candidates: List[Dict] = []
    for orientation_index, orientation in enumerate(product.orientations):
        if (
            orientation[0] > remaining_length + TOLERANCE
            or orientation[1] > container["W"] + TOLERANCE
            or orientation[2] > container["H"] + TOLERANCE
        ):
            continue
        required_depth, _ = _frontier_required_depth(
            product,
            quantity,
            orientation,
            container,
            loaded_weight,
            remaining_length,
        )
        for strategy in SPACE_EVENLY_RESIDUAL_STRATEGIES:
            candidates.append(
                _evaluate_space_evenly_anchor_candidate(
                    product,
                    quantity,
                    orientation,
                    orientation_index,
                    strategy,
                    "native",
                    0.0,
                    required_depth,
                    required_depth,
                    container,
                    ordered_products,
                    remaining,
                    next_item_index,
                    loaded_weight,
                    preferred_orientations,
                )
            )
    if not candidates:
        return None, 0, 0
    winner, _ = _select_space_evenly_residual_candidate(candidates)
    return (
        (
            float(winner["frontier_volume_efficiency"])
            if winner is not None
            else None
        ),
        int(sum(candidate["candidate_evaluations"] for candidate in candidates)),
        int(
            sum(
                candidate["local_placement_evaluations"]
                for candidate in candidates
            )
        ),
    )


def _apply_space_evenly_extension_value(
    native: Dict,
    extended: Dict,
    next_clean_efficiency: Optional[float],
    container: Dict,
) -> None:
    extra_depth = max(
        extended["committed_depth"] - native["committed_depth"],
        0.0,
    )
    extra_volume = max(
        extended["frontier_packed_volume"] - native["frontier_packed_volume"],
        0.0,
    )
    extra_prism = extra_depth * container["W"] * container["H"]
    marginal_efficiency = (
        extra_volume / extra_prism
        if extra_prism > TOLERANCE
        else None
    )
    if not extended["valid"]:
        justified = False
        reason = "extended_invalid"
    elif not native["valid"]:
        justified = True
        reason = "native_invalid"
    elif extra_depth <= TOLERANCE:
        justified = False
        reason = "no_meaningful_extension"
    elif extra_volume <= TOLERANCE:
        justified = False
        reason = "no_additional_packed_volume"
    elif next_clean_efficiency is None:
        justified = True
        reason = "no_clean_next_frontier_alternative"
    elif (
        marginal_efficiency is not None
        and marginal_efficiency
        > next_clean_efficiency + FRONTIER_EFFICIENCY_TOLERANCE
    ):
        justified = True
        reason = "marginal_efficiency_exceeds_clean_frontier"
    elif (
        marginal_efficiency is not None
        and abs(marginal_efficiency - next_clean_efficiency)
        <= FRONTIER_EFFICIENCY_TOLERANCE
    ):
        justified = False
        reason = "native_preferred_equal_extension_value"
    else:
        justified = False
        reason = "native_preferred_clean_frontier_more_efficient"

    extended.update(
        {
            "extension_evaluated": True,
            "extension_justified": bool(justified),
            "extension_depth": float(extra_depth),
            "extension_extra_packed_volume": float(extra_volume),
            "extension_marginal_efficiency": (
                float(marginal_efficiency)
                if marginal_efficiency is not None
                else None
            ),
            "next_clean_frontier_efficiency": (
                float(next_clean_efficiency)
                if next_clean_efficiency is not None
                else None
            ),
            "extension_decision_reason": reason,
            "family_eligible": bool(justified and extended["valid"]),
        }
    )


def _select_space_evenly_residual_candidate(
    candidates: List[Dict],
) -> Tuple[Optional[Dict], str]:
    """Apply the approved Pi-first Residual Frontier Closure ranking."""
    shortlist = [
        candidate
        for candidate in candidates
        if candidate["valid"] and candidate.get("family_eligible", True)
    ]
    if not shortlist:
        shortlist = [candidate for candidate in candidates if candidate["valid"]]
    if not shortlist:
        return None, "no_physically_valid_candidate"

    stages = (
        (
            "maximum_anchor_quantity",
            max,
            lambda candidate: candidate["anchor_qty_packed"],
            TOLERANCE,
        ),
        (
            "minimum_anchor_pi_x_footprint",
            min,
            lambda candidate: candidate["anchor_pi_x_footprint"],
            TOLERANCE,
        ),
        (
            "maximum_frontier_volume_efficiency",
            max,
            lambda candidate: candidate["frontier_volume_efficiency"],
            FRONTIER_EFFICIENCY_TOLERANCE,
        ),
        (
            "maximum_other_products_volume",
            max,
            lambda candidate: candidate["other_products_packed_volume"],
            TOLERANCE,
        ),
        (
            "maximum_other_products_quantity",
            max,
            lambda candidate: candidate["other_products_quantity_packed"],
            TOLERANCE,
        ),
        (
            "minimum_committed_frontier_depth",
            min,
            lambda candidate: candidate["committed_depth"],
            TOLERANCE,
        ),
    )
    selection_reason = "stable_orientation_tiebreak"
    for reason, selector, value, tolerance in stages:
        best = selector(value(candidate) for candidate in shortlist)
        filtered = [
            candidate
            for candidate in shortlist
            if abs(value(candidate) - best) <= tolerance
        ]
        if len(filtered) < len(shortlist):
            selection_reason = reason
        shortlist = filtered
        if len(shortlist) == 1:
            return shortlist[0], selection_reason

    row_first = [
        candidate
        for candidate in shortlist
        if candidate["residual_traversal"] == "row_first"
    ]
    if row_first and len(row_first) < len(shortlist):
        shortlist = row_first
        selection_reason = "tie_prefer_row_first"
    bottom_up = [
        candidate
        for candidate in shortlist
        if candidate["gravity_mode"] == "bottom_up"
    ]
    if bottom_up and len(bottom_up) < len(shortlist):
        shortlist = bottom_up
        selection_reason = "tie_prefer_bottom_up"
    winner = min(
        shortlist,
        key=lambda candidate: (
            candidate["anchor_orientation_index"],
            0 if candidate["candidate_family"] == "native" else 1,
            round(candidate["committed_depth"], 9),
        ),
    )
    return winner, selection_reason


def pack_space_evenly_residual_frontiers(
    container: Dict,
    ordered_products: List[NormalizedProduct],
    residual_quantities: Dict[int, int],
    placements: List[Placement],
    residual_loaded: Dict[int, int],
    next_item_index: Dict[int, int],
    loaded_weight: float,
    frontier: float,
    preferred_orientations: Dict[int, Tuple[float, float, float]],
    enable_side_infill: bool = False,
    infill_loaded: Optional[Dict[int, int]] = None,
    infill_stats: Optional[Dict] = None,
    enable_top_infill: bool = False,
    side_infill_loaded: Optional[Dict[int, int]] = None,
    top_infill_loaded: Optional[Dict[int, int]] = None,
    top_infill_stats: Optional[Dict] = None,
) -> Tuple[float, float, List[Dict], int, int, int]:
    """Close deterministic whole-volume Space Evenly residual frontiers.

    ``enable_side_infill`` and ``enable_top_infill`` are deliberately opt-in.
    Approved baseline calls retain the original frontier-only behavior;
    Mixed Cargo Infill uses the same local ``remaining`` state for post-commit
    side then supported-top closures.
    """
    remaining = dict(residual_quantities)
    if enable_side_infill:
        if infill_loaded is None:
            infill_loaded = {}
        if infill_stats is None:
            infill_stats = _new_side_infill_stats(
                len({product.sequence for product in ordered_products})
            )
        if side_infill_loaded is None:
            side_infill_loaded = {}
    if enable_top_infill:
        if infill_loaded is None:
            infill_loaded = {}
        if top_infill_loaded is None:
            top_infill_loaded = {}
        if top_infill_stats is None:
            top_infill_stats = _new_top_infill_stats(
                len({product.sequence for product in ordered_products})
            )
    frontiers: List[Dict] = []
    total_candidate_evaluations = 0
    total_local_evaluations = 0
    total_support_relationships = 0

    while any(remaining.get(product.row_index, 0) > 0 for product in ordered_products):
        available_length = max(container["L"] - frontier, 0.0)
        if available_length <= TOLERANCE:
            break
        anchor = _select_space_evenly_residual_anchor(
            ordered_products,
            remaining,
            container,
            loaded_weight,
            available_length,
        )
        if anchor is None:
            break
        anchor_quantity = int(remaining.get(anchor.row_index, 0))
        before = {
            str(product.row_index): int(remaining.get(product.row_index, 0))
            for product in ordered_products
        }
        candidates: List[Dict] = []
        for orientation_index, orientation in enumerate(anchor.orientations):
            if (
                orientation[0] > available_length + TOLERANCE
                or orientation[1] > container["W"] + TOLERANCE
                or orientation[2] > container["H"] + TOLERANCE
            ):
                continue
            anchor_depth, _ = _frontier_required_depth(
                anchor,
                anchor_quantity,
                orientation,
                container,
                loaded_weight,
                available_length,
            )
            if anchor_depth <= TOLERANCE:
                continue
            for strategy in SPACE_EVENLY_RESIDUAL_STRATEGIES:
                native = _evaluate_space_evenly_anchor_candidate(
                    anchor,
                    anchor_quantity,
                    orientation,
                    orientation_index,
                    strategy,
                    "native",
                    frontier,
                    anchor_depth,
                    anchor_depth,
                    container,
                    ordered_products,
                    remaining,
                    next_item_index,
                    loaded_weight,
                    preferred_orientations,
                )
                candidates.append(native)
                justified_extension_found = False
                paired_extensions: List[Dict] = []
                next_product = next(
                    (
                        product
                        for product in ordered_products
                        if product.row_index != anchor.row_index
                        and native["remaining_after"].get(product.row_index, 0) > 0
                        and _payload_units_available(
                            container,
                            native["loaded_weight_after"],
                            product.weight,
                            native["remaining_after"].get(product.row_index, 0),
                        )
                        > 0
                    ),
                    None,
                )
                if next_product is None:
                    continue
                extension_depths = set()
                for next_orientation in next_product.orientations:
                    extended_depth, _, _ = _dgfe_envelope_dimensions(
                        frontier,
                        native["anchor_placements"],
                        next_orientation[0],
                        available_length,
                    )
                    if (
                        extended_depth > native["committed_depth"] + TOLERANCE
                        and extended_depth <= available_length + TOLERANCE
                    ):
                        extension_depths.add(round(extended_depth, 9))
                if not extension_depths:
                    continue
                (
                    clean_efficiency,
                    clean_candidate_evaluations,
                    clean_local_evaluations,
                ) = _space_evenly_clean_frontier_efficiency(
                    next_product,
                    native["remaining_after"][next_product.row_index],
                    container,
                    max(available_length - native["committed_depth"], 0.0),
                    native["loaded_weight_after"],
                    ordered_products,
                    native["remaining_after"],
                    next_item_index,
                    preferred_orientations,
                )
                native["candidate_evaluations"] += clean_candidate_evaluations
                native["local_placement_evaluations"] += clean_local_evaluations
                native["clean_frontier_candidate_evaluations"] = int(
                    clean_candidate_evaluations
                )
                native["clean_frontier_local_placement_evaluations"] = int(
                    clean_local_evaluations
                )
                for extended_depth in sorted(extension_depths):
                    extended = _evaluate_space_evenly_anchor_candidate(
                        anchor,
                        anchor_quantity,
                        orientation,
                        orientation_index,
                        strategy,
                        "extended",
                        frontier,
                        anchor_depth,
                        float(extended_depth),
                        container,
                        ordered_products,
                        remaining,
                        next_item_index,
                        loaded_weight,
                        preferred_orientations,
                    )
                    _apply_space_evenly_extension_value(
                        native,
                        extended,
                        clean_efficiency,
                        container,
                    )
                    justified_extension_found = (
                        justified_extension_found
                        or bool(extended["extension_justified"])
                    )
                    paired_extensions.append(extended)
                    candidates.append(extended)
                if paired_extensions:
                    extension_diagnostic = max(
                        paired_extensions,
                        key=lambda candidate: (
                            int(candidate["extension_justified"]),
                            candidate["extension_marginal_efficiency"]
                            if candidate["extension_marginal_efficiency"]
                            is not None
                            else -1.0,
                            candidate["extension_extra_packed_volume"],
                            -candidate["committed_depth"],
                        ),
                    )
                    native.update(
                        {
                            "extension_evaluated": True,
                            "extension_justified": bool(
                                extension_diagnostic["extension_justified"]
                            ),
                            "extension_marginal_efficiency": (
                                extension_diagnostic[
                                    "extension_marginal_efficiency"
                                ]
                            ),
                            "next_clean_frontier_efficiency": (
                                extension_diagnostic[
                                    "next_clean_frontier_efficiency"
                                ]
                            ),
                            "extension_decision_reason": (
                                extension_diagnostic[
                                    "extension_decision_reason"
                                ]
                            ),
                        }
                    )
                if justified_extension_found:
                    native["family_eligible"] = False

        winner, selection_reason = _select_space_evenly_residual_candidate(
            candidates
        )
        if winner is None or winner["anchor_qty_packed"] <= 0:
            break

        placements.extend(winner["placements"])
        for row_index, quantity in winner["products_quantities_packed"].items():
            residual_loaded[row_index] += quantity
            remaining[row_index] = max(remaining.get(row_index, 0) - quantity, 0)
            next_item_index[row_index] += quantity
        loaded_weight = float(winner["loaded_weight_after"])
        frontier_start = frontier
        frontier = frontier_start + winner["committed_depth"]
        after = {
            str(product.row_index): int(remaining.get(product.row_index, 0))
            for product in ordered_products
        }
        post_frontier_diagnostics = {
            "residual_count_before_infill": 0,
            "residual_count_after_infill": 0,
            "units_added_by_product": {},
            "infill_actions": [],
            "residual_evaluation_reasons": [],
        }
        post_frontier_top_diagnostics = {
            "top_residual_count_before_infill": 0,
            "top_residual_count_after_infill": 0,
            "top_units_added_by_product": {},
            "top_infill_actions": [],
            "top_residual_evaluation_reasons": [],
        }
        if enable_side_infill:
            before_infill = dict(remaining)
            side_space = Space(
                frontier_start,
                0.0,
                0.0,
                winner["committed_depth"],
                container["W"],
                container["H"],
            )
            eligible_row_indices = {
                product.row_index
                for product in ordered_products
                if remaining.get(product.row_index, 0) > 0
            }
            side_placements, loaded_weight, side_stats = (
                fill_side_residual_deterministically(
                    side_space,
                    anchor,
                    ordered_products,
                    remaining,
                    next_item_index,
                    container,
                    loaded_weight,
                    len({product.sequence for product in ordered_products}) > 1,
                    eligible_row_indices=eligible_row_indices,
                    committed_placements=placements,
                    window_x_start=frontier_start,
                    window_x_end=frontier,
                )
            )
            placements.extend(side_placements)
            units_added_by_product: Dict[str, int] = {}
            for product in ordered_products:
                quantity = int(
                    before_infill.get(product.row_index, 0)
                    - remaining.get(product.row_index, 0)
                )
                if quantity <= 0:
                    continue
                infill_loaded[product.row_index] = int(
                    infill_loaded.get(product.row_index, 0) + quantity
                )
                if side_infill_loaded is not None:
                    side_infill_loaded[product.row_index] = int(
                        side_infill_loaded.get(product.row_index, 0) + quantity
                    )
                units_added_by_product[str(product.row_index)] = quantity
            _merge_side_infill_stats(infill_stats, side_stats)
            envelopes = side_stats.get("side_residual_envelopes", [])
            initial_envelope = envelopes[0] if envelopes else []
            final_envelope = envelopes[-1] if envelopes else []
            post_frontier_diagnostics = {
                "residual_count_before_infill": int(len(initial_envelope)),
                "residual_count_after_infill": int(len(final_envelope)),
                "units_added_by_product": units_added_by_product,
                "infill_actions": list(side_stats.get("actions", [])),
                "residual_evaluation_reasons": list(
                    side_stats.get("residual_evaluation_reasons", [])
                ),
            }
        if enable_top_infill:
            before_top_infill = dict(remaining)
            top_space = Space(
                frontier_start,
                0.0,
                0.0,
                winner["committed_depth"],
                container["W"],
                container["H"],
            )
            eligible_row_indices = {
                product.row_index
                for product in ordered_products
                if remaining.get(product.row_index, 0) > 0
            }
            top_placements, loaded_weight, top_stats = (
                fill_top_residual_deterministically(
                    top_space,
                    anchor,
                    ordered_products,
                    remaining,
                    next_item_index,
                    container,
                    loaded_weight,
                    len({product.sequence for product in ordered_products}) > 1,
                    eligible_row_indices=eligible_row_indices,
                    committed_placements=placements,
                    window_x_start=frontier_start,
                    window_x_end=frontier,
                )
            )
            placements.extend(top_placements)
            top_units_added_by_product: Dict[str, int] = {}
            for product in ordered_products:
                quantity = int(
                    before_top_infill.get(product.row_index, 0)
                    - remaining.get(product.row_index, 0)
                )
                if quantity <= 0:
                    continue
                infill_loaded[product.row_index] = int(
                    infill_loaded.get(product.row_index, 0) + quantity
                )
                if top_infill_loaded is not None:
                    top_infill_loaded[product.row_index] = int(
                        top_infill_loaded.get(product.row_index, 0) + quantity
                    )
                top_units_added_by_product[str(product.row_index)] = quantity
            _merge_top_infill_stats(top_infill_stats, top_stats)
            top_envelopes = top_stats.get("top_residual_windows", [])
            initial_top_envelope = (
                top_envelopes[0].get("residuals", [])
                if top_envelopes
                else []
            )
            final_top_envelope = (
                top_envelopes[-1].get("residuals", [])
                if top_envelopes
                else []
            )
            post_frontier_top_diagnostics = {
                "top_residual_count_before_infill": int(
                    len(initial_top_envelope)
                ),
                "top_residual_count_after_infill": int(
                    len(final_top_envelope)
                ),
                "top_units_added_by_product": top_units_added_by_product,
                "top_infill_actions": list(top_stats.get("top_actions", [])),
                "top_residual_evaluation_reasons": list(
                    top_stats.get("top_residual_evaluation_reasons", [])
                ),
                "top_residual_windows": list(top_envelopes),
                "top_support_planes_evaluated": int(
                    top_stats.get("top_support_planes_evaluated", 0)
                ),
            }
            if top_infill_stats is not None:
                top_infill_stats.setdefault("top_residual_frontiers_closed", 0)
                top_infill_stats["top_residual_frontiers_closed"] += 1
                top_infill_stats.setdefault("top_frontier_closures", [])
                top_infill_stats["top_frontier_closures"].append(
                    {
                        "frontier_index": int(len(frontiers)),
                        "x_start": float(frontier_start),
                        "x_end": float(frontier),
                        "anchor_product": anchor.name,
                        "anchor_row_index": int(anchor.row_index),
                        **post_frontier_top_diagnostics,
                    }
                )
            closure_record = {
                "frontier_index": int(len(frontiers)),
                "x_start": float(frontier_start),
                "x_end": float(frontier),
                "anchor_product": anchor.name,
                "anchor_row_index": int(anchor.row_index),
                **post_frontier_diagnostics,
                **post_frontier_top_diagnostics,
            }
            infill_stats["residual_frontiers_closed"] += 1
            infill_stats["post_frontier_side_residuals_derived"] += int(
                len(initial_envelope)
            )
            infill_stats["post_frontier_side_residuals_filled"] += int(
                len(side_stats.get("actions", []))
            )
            infill_stats["post_frontier_units"] += int(
                side_stats.get("infill_units_total", 0)
            )
            infill_stats["post_frontier_volume"] += float(
                side_stats.get("infill_volume_total", 0.0)
            )
            infill_stats["post_frontier_closures"].append(closure_record)
            if enable_top_infill:
                infill_stats.setdefault("top_frontier_closures", [])
                infill_stats.setdefault("top_residual_frontiers_closed", 0)
        after_side_infill = {
            str(product.row_index): int(remaining.get(product.row_index, 0))
            for product in ordered_products
        }
        after_top_infill = {
            str(product.row_index): int(remaining.get(product.row_index, 0))
            for product in ordered_products
        }
        total_candidate_evaluations += sum(
            candidate["candidate_evaluations"] for candidate in candidates
        )
        total_local_evaluations += sum(
            candidate["local_placement_evaluations"] for candidate in candidates
        )
        total_support_relationships += winner["support_relationship_count"]
        anchor_floor = [
            placement
            for placement in winner["anchor_placements"]
            if placement.z <= TOLERANCE
            and abs(placement.x - frontier_start) <= TOLERANCE
        ]
        anchor_floor_width = sum(placement.w for placement in anchor_floor)
        maximum_z = max(
            (placement.z + placement.h for placement in winner["placements"]),
            default=0.0,
        )
        diagnostic_candidates = [
            {
                key: value
                for key, value in candidate.items()
                if key
                not in {
                    "placements",
                    "anchor_placements",
                    "remaining_after",
                    "loaded_weight_after",
                }
            }
            for candidate in candidates
        ]
        frontier_metadata = {
            "pattern": "space_evenly_residual_frontier_closure",
            "sequence": 1,
            "frontier_index": len(frontiers),
            "band_index": len(frontiers),
            "sequence_band_index": len(frontiers),
            "anchor_product": anchor.name,
            "anchor_row_index": int(anchor.row_index),
            "x_start": float(frontier_start),
            "x_end": float(frontier),
            "native_depth": float(winner["native_depth"]),
            "committed_depth": float(winner["committed_depth"]),
            "anchor_qty_requested": int(anchor_quantity),
            "anchor_qty_packed": int(winner["anchor_qty_packed"]),
            "anchor_orientation": list(winner["anchor_orientation"]),
            "anchor_pi_x_footprint": float(
                winner["anchor_pi_x_footprint"]
            ),
            "candidate_family": winner["candidate_family"],
            "gravity_mode": winner["gravity_mode"],
            "residual_traversal": winner["residual_traversal"],
            "frontier_volume_efficiency": float(
                winner["frontier_volume_efficiency"]
            ),
            "frontier_packed_volume": float(
                winner["frontier_packed_volume"]
            ),
            "frontier_prism_volume": float(
                winner["frontier_prism_volume"]
            ),
            "other_products_packed": winner["other_products_packed"],
            "products_quantities_packed": {
                str(row_index): int(quantity)
                for row_index, quantity in winner[
                    "products_quantities_packed"
                ].items()
            },
            "support_plane_count": int(winner["support_plane_count"]),
            "support_surface_count": int(winner["support_surface_count"]),
            "candidate_count": len(candidates),
            "candidate_evaluations": int(
                sum(
                    candidate["candidate_evaluations"]
                    for candidate in candidates
                )
            ),
            "local_placement_evaluations": int(
                sum(
                    candidate["local_placement_evaluations"]
                    for candidate in candidates
                )
            ),
            "extension_evaluated": any(
                candidate["candidate_family"] == "extended"
                for candidate in candidates
            ),
            "extension_justified": bool(winner["extension_justified"]),
            "extension_marginal_efficiency": winner[
                "extension_marginal_efficiency"
            ],
            "next_clean_frontier_efficiency": winner[
                "next_clean_frontier_efficiency"
            ],
            "extension_decision_reason": winner[
                "extension_decision_reason"
            ],
            "selection_reason": selection_reason,
            "physical_validation": winner["physical_validation"],
            "secondary_orientation_diagnostics": winner[
                "secondary_orientation_diagnostics"
            ],
            "residual_frontier_candidates": diagnostic_candidates,
            "residual_quantities_before": before,
            "residual_quantities_after": after,
            **(
                {
                    "residual_quantities_after_side_infill": after_side_infill,
                    "residual_quantities_after_top_infill": after_top_infill,
                    **post_frontier_diagnostics,
                    **post_frontier_top_diagnostics,
                }
                if enable_side_infill
                else {}
            ),
            "maximum_z": float(maximum_z),
            "support_relationship_count": int(
                winner["support_relationship_count"]
            ),
            # Compatibility aliases consumed by established result surfaces.
            "foundation_product": anchor.name,
            "foundation_row_index": int(anchor.row_index),
            "foundation_orientation": list(winner["anchor_orientation"]),
            "foundation_quantity": int(winner["anchor_qty_packed"]),
            "foundation_available_width": float(container["W"]),
            "foundation_occupied_width": float(anchor_floor_width),
            "foundation_width_utilization": float(
                anchor_floor_width / container["W"]
                if container["W"] > TOLERANCE
                else 0.0
            ),
            "foundation_orientation_count": 1,
            "foundation_orientation_runs": [
                {
                    "orientation_index": int(
                        winner["anchor_orientation_index"]
                    ),
                    "orientation": list(winner["anchor_orientation"]),
                    "quantity": int(len(anchor_floor)),
                    "occupied_width": float(anchor_floor_width),
                }
            ],
            "foundation_support_potential": 0,
            "upper_rows": [],
            "products_added_above": [
                {
                    "row_index": int(product.row_index),
                    "product_name": product.name,
                    "quantity": int(
                        sum(
                            1
                            for placement in winner["placements"]
                            if placement.row_index == product.row_index
                            and placement.z > TOLERANCE
                        )
                    ),
                }
                for product in ordered_products
                if any(
                    placement.row_index == product.row_index
                    and placement.z > TOLERANCE
                    for placement in winner["placements"]
                )
            ],
            "vertical_passes": max(winner["support_plane_count"] - 1, 0),
            "quantities_by_product": {
                str(row_index): int(quantity)
                for row_index, quantity in winner[
                    "products_quantities_packed"
                ].items()
            },
            "row_index": int(anchor.row_index),
            "product_name": anchor.name,
            "orientation": list(winner["anchor_orientation"]),
            "nx": max(
                _fit_count(
                    winner["anchor_pi_x_footprint"],
                    winner["anchor_orientation"][0],
                ),
                1,
            ),
            "ny": len(anchor_floor),
            "nz": max(winner["support_plane_count"], 1),
            "qty": int(sum(winner["products_quantities_packed"].values())),
            "width": float(anchor_floor_width),
            "height": float(maximum_z),
        }
        frontiers.append(frontier_metadata)

    return (
        frontier,
        loaded_weight,
        frontiers,
        int(total_candidate_evaluations),
        int(total_local_evaluations),
        int(total_support_relationships),
    )


def _pack_container_front_to_back(
    container: Dict,
    products: List[Dict],
    requested_mode: str,
) -> Dict:
    """Load complete blocks, then close each bounded local transition frontier."""
    normalized_container = _normalize_container(container)
    enable_infill = requested_mode == FRONT_TO_BACK_INFILL_MODE
    normalized_products = normalize_products(
        products
        if enable_infill
        else [
            {**dict(product or {}), "sequence": 1}
            for product in products or []
        ]
    )
    ordered_products = sort_products(normalized_products, normalized_container)
    sequence_groups = sorted({product.sequence for product in ordered_products})
    sequence_restricted = len(sequence_groups) > 1

    placements: List[Placement] = []
    main_blocks: List[Dict] = []
    product_summaries: List[Dict] = []
    frontiers: List[Dict] = []
    phase_order: List[Dict] = []
    regular_loaded = {product.row_index: 0 for product in ordered_products}
    frontier_loaded = {product.row_index: 0 for product in ordered_products}
    infill_loaded = {product.row_index: 0 for product in ordered_products}
    side_infill_loaded = {product.row_index: 0 for product in ordered_products}
    top_infill_loaded = {product.row_index: 0 for product in ordered_products}
    remaining_quantities = {
        product.row_index: product.qty for product in ordered_products
    }
    next_item_index = {product.row_index: 0 for product in ordered_products}
    frontier_x = 0.0
    loaded_weight = 0.0
    block_candidates_generated = 0
    block_candidates_evaluated = 0
    frontier_candidates_evaluated = 0
    infill_stats = _new_side_infill_stats(len(sequence_groups))
    top_infill_stats = _new_top_infill_stats(len(sequence_groups))

    for product_index, product in enumerate(ordered_products):
        prior_frontier_qty = frontier_loaded[product.row_index]
        prior_infill_qty = infill_loaded[product.row_index]
        entering_qty = (
            int(remaining_quantities[product.row_index])
            if enable_infill
            else max(product.qty - prior_frontier_qty, 0)
        )
        product_x_start = frontier_x
        available_length = max(normalized_container["L"] - frontier_x, 0.0)
        payload_qty = _payload_units_available(
            normalized_container,
            loaded_weight,
            product.weight,
            entering_qty,
        )
        candidates, evaluated = build_product_block_candidates(
            product,
            normalized_container,
            available_length,
        )
        block_candidates_generated += len(candidates)
        block_candidates_evaluated += evaluated
        selected = choose_product_block(
            candidates,
            payload_qty,
            available_length,
        )
        complete_blocks = 0
        if selected is not None:
            complete_blocks = min(
                payload_qty // selected.module_capacity,
                _fit_count(available_length, selected.depth),
            )
            for block_index in range(complete_blocks):
                block_x_start = frontier_x
                block_placements = _materialize_product_block(
                    product,
                    selected,
                    block_x_start,
                    next_item_index[product.row_index],
                )
                placements.extend(block_placements)
                placed_qty = len(block_placements)
                next_item_index[product.row_index] += placed_qty
                regular_loaded[product.row_index] += placed_qty
                remaining_quantities[product.row_index] = max(
                    remaining_quantities[product.row_index] - placed_qty,
                    0,
                )
                loaded_weight += placed_qty * product.weight
                frontier_x = block_x_start + selected.depth
                block_metadata = {
                    "row_index": product.row_index,
                    "product_name": product.name,
                    "block_index": block_index,
                    "x_start": float(block_x_start),
                    "x_end": float(frontier_x),
                    "qty": int(placed_qty),
                    **_candidate_metadata(selected),
                }
                main_blocks.append(block_metadata)
                phase_order.append(
                    {
                        "phase": "complete_block",
                        "row_index": product.row_index,
                        "product_name": product.name,
                        "quantity": int(placed_qty),
                        "x_start": float(block_x_start),
                        "x_end": float(frontier_x),
                    }
                )
        regular_qty = regular_loaded[product.row_index]
        residual_qty = max(entering_qty - regular_qty, 0)
        summary = {
            "row_index": product.row_index,
            "product_name": product.name,
            "requested_qty": int(product.qty),
            "qty_entering_product_phase": int(entering_qty),
            "qty_already_loaded_in_previous_frontier": int(prior_frontier_qty),
            **(
                {"qty_already_loaded_as_side_infill": int(prior_infill_qty)}
                if enable_infill
                else {}
            ),
            "complete_blocks": int(complete_blocks),
            "regular_block_qty": int(regular_qty),
            "regular_qty": int(regular_qty),
            "residual_qty": int(residual_qty),
            "qty_loaded_in_own_frontier": 0,
            "qty_of_next_product_loaded_in_frontier": 0,
            "x_start": float(product_x_start),
            "main_block_end_x": float(frontier_x),
            "frontier_start_x": None,
            "frontier_end_x": None,
            "current_product_residual_strategy": None,
            "next_product_population_strategy": None,
            "selected_residual_strategy": None,
            "selected_residual_orientation": None,
            "selected_candidate_family": None,
            "selected_gravity_mode": None,
            "selected_residual_traversal": None,
            "pi_residual_x_footprint": None,
            "selected_frontier_depth": None,
            "selected_frontier_volume_efficiency": None,
            "native_frontier_depth": None,
            "extended_frontier_depth": None,
            "extra_extension_depth": None,
            "native_next_product_qty": None,
            "extended_next_product_qty": None,
            "dgfe_extra_packed_volume": None,
            "dgfe_marginal_efficiency": None,
            "next_product_regular_block_efficiency": None,
            "extension_value_delta": None,
            "extension_justified": None,
            "extension_decision_reason": None,
            "selection_reason": None,
            "block": _candidate_metadata(selected) if selected else None,
        }

        if residual_qty > 0 and frontier_x < normalized_container["L"] - TOLERANCE:
            frontier_start = frontier_x
            available_length = max(normalized_container["L"] - frontier_start, 0.0)
            current_orientation, current_depth = _frontier_orientation(
                product,
                [selected] if selected is not None else [],
                available_length,
                normalized_container,
            )
            next_product = (
                next(
                    (
                        candidate
                        for candidate in ordered_products[product_index + 1 :]
                        if remaining_quantities.get(candidate.row_index, 0) > 0
                    ),
                    None,
                )
                if enable_infill
                else (
                    ordered_products[product_index + 1]
                    if product_index + 1 < len(ordered_products)
                    else None
                )
            )

            if current_orientation is not None:
                # The transition is one bounded local slice adjacent to the
                # current block. A later product may use unused capacity in
                # that slice, but it may not extend the frontier toward the
                # doors to accept individual units.
                frontier_depth = min(current_depth, available_length)
                next_product_orientation_candidates: List[Dict] = []
                next_product_selected_orientation = None
                next_product_valid_orientation_count = 0
                next_frontier_qty = 0
                transition_frontier_candidates_evaluated = 0
                local_frontier: List[Placement] = []
                own_frontier_qty = 0
                selected_residual_strategy = "row_first"
                selected_gravity_mode = "bottom_up"
                selected_residual_traversal = "row_first"
                selection_reason = "no_next_product"
                current_product_residual_strategy = "row_first"
                next_product_population_strategy = None
                residual_strategy_candidates: List[Dict] = []
                transition_base_candidate_count = 0
                selected_residual_orientation = None
                selected_candidate_family = None
                selected_pi_residual_x_footprint = None
                selected_frontier_volume_efficiency = 0.0
                selected_value_diagnostics = {
                    "native_frontier_depth": None,
                    "extended_frontier_depth": None,
                    "extra_extension_depth": None,
                    "native_next_product_qty": None,
                    "extended_next_product_qty": None,
                    "dgfe_extra_packed_volume": None,
                    "dgfe_marginal_efficiency": None,
                    "next_product_regular_block_efficiency": None,
                    "next_product_regular_block": None,
                    "extension_value_delta": None,
                    "extension_justified": None,
                    "extension_decision_reason": None,
                }

                if next_product is None:
                    local_frontier, loaded_weight, own_frontier_qty = (
                        _frontier_grid_placements(
                            product,
                            residual_qty,
                            frontier_start,
                            frontier_depth,
                            current_orientation,
                            normalized_container,
                            placements,
                            next_item_index[product.row_index],
                            loaded_weight,
                        )
                    )
                    selected_residual_orientation = [
                        float(value) for value in current_orientation
                    ]
                    selected_frontier_volume_efficiency = (
                        own_frontier_qty * product.unit_volume
                        / (
                            frontier_depth
                            * normalized_container["W"]
                            * normalized_container["H"]
                        )
                        if frontier_depth > TOLERANCE
                        else 0.0
                    )
                else:
                    next_remaining = (
                        int(remaining_quantities[next_product.row_index])
                        if enable_infill
                        else max(
                            next_product.qty
                            - frontier_loaded[next_product.row_index],
                            0,
                        )
                    )
                    preferred_next_orientation = None
                    if next_remaining > 0:
                        preferred_candidates, _ = build_product_block_candidates(
                            next_product,
                            normalized_container,
                            available_length,
                        )
                        preferred_block = choose_product_block(
                            preferred_candidates,
                            _payload_units_available(
                                normalized_container,
                                loaded_weight
                                + residual_qty * product.weight,
                                next_product.weight,
                                next_remaining,
                            ),
                            available_length,
                        )
                        if preferred_block is not None:
                            preferred_next_orientation = preferred_block.orientations[0]

                    transition_base_candidate_count = (
                        len(product.orientations) * len(DGFE_RESIDUAL_STRATEGIES)
                    )
                    transition_candidates = [
                        family_candidate
                        for orientation_index, orientation in enumerate(
                            product.orientations
                        )
                        for strategy in DGFE_RESIDUAL_STRATEGIES
                        for family_candidate in _evaluate_frontier_transition_candidate_pair(
                            product,
                            residual_qty,
                            next_product,
                            next_remaining,
                            strategy,
                            frontier_start,
                            available_length,
                            orientation,
                            normalized_container,
                            placements,
                            next_item_index[product.row_index],
                            next_item_index[next_product.row_index],
                            loaded_weight,
                            preferred_next_orientation,
                            current_orientation_index=orientation_index,
                            remaining_length=available_length,
                        )
                    ]
                    winner, selection_reason = _select_frontier_transition_candidate(
                        transition_candidates
                    )
                    selected_residual_strategy = winner["strategy"]
                    selected_gravity_mode = winner["gravity_mode"]
                    selected_residual_traversal = winner["residual_traversal"]
                    current_product_residual_strategy = winner[
                        "residual_traversal"
                    ]
                    next_product_population_strategy = "row_first"
                    local_frontier = winner["placements"]
                    own_frontier_qty = winner["current_product_qty_packed"]
                    next_frontier_qty = winner["next_product_qty_packed"]
                    frontier_depth = winner["frontier_depth"]
                    selected_residual_orientation = winner[
                        "current_product_orientation"
                    ]
                    selected_candidate_family = winner["candidate_family"]
                    selected_pi_residual_x_footprint = winner[
                        "pi_residual_x_footprint"
                    ]
                    selected_frontier_volume_efficiency = winner[
                        "frontier_volume_efficiency"
                    ]
                    selected_value_diagnostics = {
                        key: winner[key]
                        for key in selected_value_diagnostics
                    }
                    loaded_weight = winner["loaded_weight_after"]
                    placements.extend(winner["placements"])
                    next_product_selected_orientation = winner[
                        "next_product_selected_orientation"
                    ]
                    next_product_orientation_candidates = winner[
                        "next_product_orientation_candidates"
                    ]
                    next_product_valid_orientation_count = winner[
                        "next_product_valid_orientation_count"
                    ]
                    transition_frontier_candidates_evaluated = sum(
                        candidate["candidate_evaluations"]
                        for candidate in transition_candidates
                    )
                    frontier_candidates_evaluated += (
                        transition_frontier_candidates_evaluated
                    )
                    residual_strategy_candidates = [
                        {
                            "current_product": product.name,
                            "next_product": next_product.name,
                            "current_product_orientation": candidate[
                                "current_product_orientation"
                            ],
                            "current_product_orientation_index": int(
                                candidate["current_product_orientation_index"]
                            ),
                            "candidate_family": candidate["candidate_family"],
                            "family_eligible": bool(
                                candidate["family_eligible"]
                            ),
                            "strategy": candidate["strategy"],
                            "gravity_mode": candidate["gravity_mode"],
                            "residual_traversal": candidate[
                                "residual_traversal"
                            ],
                            "current_product_residual_requested": int(
                                residual_qty
                            ),
                            "residual_requested": int(residual_qty),
                            "current_product_residual_reserved_or_placed": int(
                                candidate[
                                    "current_product_qty_reserved_or_placed"
                                ]
                            ),
                            "current_product_residual_packed": int(
                                candidate["current_product_qty_packed"]
                            ),
                            "residual_final_packed": int(
                                candidate["current_product_qty_packed"]
                            ),
                            "next_product_qty_packed": int(
                                candidate["next_product_qty_packed"]
                            ),
                            "frontier_depth": float(candidate["frontier_depth"]),
                            "pi_residual_x_footprint": float(
                                candidate["pi_residual_x_footprint"]
                            ),
                            "native_frontier_depth": float(
                                candidate["native_frontier_depth"]
                            ),
                            "extended_frontier_depth": float(
                                candidate["extended_frontier_depth"]
                            ),
                            "extra_extension_depth": float(
                                candidate["extra_extension_depth"]
                            ),
                            "native_next_product_qty": int(
                                candidate["native_next_product_qty"]
                            ),
                            "extended_next_product_qty": int(
                                candidate["extended_next_product_qty"]
                            ),
                            "dgfe_extra_packed_volume": float(
                                candidate["dgfe_extra_packed_volume"]
                            ),
                            "dgfe_marginal_efficiency": candidate[
                                "dgfe_marginal_efficiency"
                            ],
                            "next_product_regular_block_efficiency": candidate[
                                "next_product_regular_block_efficiency"
                            ],
                            "next_product_regular_block": candidate[
                                "next_product_regular_block"
                            ],
                            "extension_value_delta": candidate[
                                "extension_value_delta"
                            ],
                            "extension_justified": bool(
                                candidate["extension_justified"]
                            ),
                            "extension_decision_reason": candidate[
                                "extension_decision_reason"
                            ],
                            "frontier_x_start": float(candidate["frontier_x_start"]),
                            "frontier_x_end": float(candidate["frontier_x_end"]),
                            "residual_frontier_depth": float(
                                candidate["residual_frontier_depth"]
                            ),
                            "envelope_x_start": float(
                                candidate["envelope_x_start"]
                            ),
                            "envelope_x_end": float(
                                candidate["envelope_x_end"]
                            ),
                            "envelope_depth": float(
                                candidate["envelope_depth"]
                            ),
                            "x_rows_evaluated": int(
                                candidate["x_rows_evaluated"]
                            ),
                            "first_clean_x_row_index": candidate[
                                "first_clean_x_row_index"
                            ],
                            "next_product_selected_orientation": (
                                [
                                    float(value)
                                    for value in candidate[
                                        "next_product_selected_orientation"
                                    ]
                                ]
                                if candidate["next_product_selected_orientation"]
                                is not None
                                else None
                            ),
                            "next_product_orientation": (
                                [
                                    float(value)
                                    for value in candidate[
                                        "next_product_selected_orientation"
                                    ]
                                ]
                                if candidate[
                                    "next_product_selected_orientation"
                                ] is not None
                                else None
                            ),
                            "next_product_valid_orientation_count": int(
                                candidate["next_product_valid_orientation_count"]
                            ),
                            "next_product_selected_orientation_index": candidate[
                                "next_product_selected_orientation_index"
                            ],
                            "next_product_orientation_index": candidate[
                                "next_product_selected_orientation_index"
                            ],
                            "next_product_qty_in_envelope": int(
                                candidate["next_product_qty_packed"]
                            ),
                            "next_product_width_used": float(
                                candidate["next_product_width_used"]
                            ),
                            "next_product_width_utilization": float(
                                candidate["next_product_width_utilization"]
                            ),
                            "next_product_x_rows": candidate[
                                "next_product_x_rows"
                            ],
                            "next_product_orientation_candidates": candidate[
                                "next_product_orientation_candidates"
                            ],
                            "virtual_residual_positions": candidate[
                                "virtual_residual_positions"
                            ],
                            "settled_residual_positions": candidate[
                                "settled_residual_positions"
                            ],
                            "residual_positions_truncated": bool(
                                candidate["residual_positions_truncated"]
                            ),
                            "gravity_applied": bool(
                                candidate["gravity_applied"]
                            ),
                            "gravity_drop_distances": candidate[
                                "gravity_drop_distances"
                            ],
                            "support_valid": bool(candidate["support_valid"]),
                            "support_plane_count": int(
                                candidate["support_plane_count"]
                            ),
                            "current_product_packed_volume": float(
                                candidate["current_product_packed_volume"]
                            ),
                            "next_product_packed_volume": float(
                                candidate["next_product_packed_volume"]
                            ),
                            "total_frontier_packed_volume": float(
                                candidate["total_frontier_packed_volume"]
                            ),
                            "frontier_packed_volume": float(
                                candidate["total_frontier_packed_volume"]
                            ),
                            "frontier_prism_volume": float(
                                candidate["frontier_prism_volume"]
                            ),
                            "frontier_volume_efficiency": float(
                                candidate["frontier_volume_efficiency"]
                            ),
                            "candidate_evaluations": int(
                                candidate["candidate_evaluations"]
                            ),
                            "valid": bool(candidate["valid"]),
                            "invalid_reason": candidate["invalid_reason"],
                            "phase_diagnostics": candidate[
                                "phase_diagnostics"
                            ],
                        }
                        for candidate in transition_candidates
                    ]

                next_item_index[product.row_index] += own_frontier_qty
                frontier_loaded[product.row_index] += own_frontier_qty
                if enable_infill:
                    remaining_quantities[product.row_index] = max(
                        remaining_quantities[product.row_index]
                        - own_frontier_qty,
                        0,
                    )
                summary["qty_loaded_in_own_frontier"] = int(own_frontier_qty)
                summary["current_product_residual_strategy"] = (
                    current_product_residual_strategy
                )
                summary["next_product_population_strategy"] = (
                    next_product_population_strategy
                )
                summary["selected_residual_strategy"] = selected_residual_strategy
                summary["selected_residual_orientation"] = (
                    selected_residual_orientation
                )
                summary["selected_candidate_family"] = selected_candidate_family
                summary["selected_gravity_mode"] = selected_gravity_mode
                summary["selected_residual_traversal"] = (
                    selected_residual_traversal
                )
                summary["pi_residual_x_footprint"] = (
                    float(selected_pi_residual_x_footprint)
                    if selected_pi_residual_x_footprint is not None
                    else None
                )
                summary["selected_frontier_depth"] = float(frontier_depth)
                summary["selected_frontier_volume_efficiency"] = float(
                    selected_frontier_volume_efficiency
                )
                summary.update(selected_value_diagnostics)
                summary["selection_reason"] = selection_reason
                phase_order.append(
                    {
                        "phase": "current_product_residual",
                        "row_index": product.row_index,
                        "product_name": product.name,
                        "quantity_requested": int(residual_qty),
                        "quantity_packed": int(own_frontier_qty),
                        "x_start": float(frontier_start),
                        "strategy": current_product_residual_strategy,
                    }
                )

                if next_product is not None and own_frontier_qty == residual_qty:
                    next_item_index[next_product.row_index] += next_frontier_qty
                    frontier_loaded[next_product.row_index] += next_frontier_qty
                    if enable_infill:
                        remaining_quantities[next_product.row_index] = max(
                            remaining_quantities[next_product.row_index]
                            - next_frontier_qty,
                            0,
                        )
                    summary["qty_of_next_product_loaded_in_frontier"] = int(
                        next_frontier_qty
                    )
                    phase_order.append(
                        {
                            "phase": "next_product_frontier_fill",
                            "row_index": next_product.row_index,
                            "product_name": next_product.name,
                            "quantity": int(next_frontier_qty),
                            "from_product_name": product.name,
                            "x_start": float(frontier_start),
                            "strategy": "row_first",
                        }
                    )

                frontier_end = frontier_start + frontier_depth
                summary["frontier_start_x"] = float(frontier_start)
                summary["frontier_end_x"] = float(frontier_end)
                frontiers.append(
                    {
                        "frontier_index": len(frontiers),
                        "current_product": product.name,
                        "current_row_index": product.row_index,
                        "next_product": next_product.name if next_product else None,
                        "next_row_index": next_product.row_index if next_product else None,
                        "x_start": float(frontier_start),
                        "x_end": float(frontier_end),
                        "current_product_residual_requested": int(residual_qty),
                        "residual_requested": int(residual_qty),
                        "current_product_residual_packed": int(own_frontier_qty),
                        "residual_final_packed": int(own_frontier_qty),
                        "next_product_qty_packed": int(next_frontier_qty),
                        "next_product_qty_in_envelope": int(next_frontier_qty),
                        "frontier_depth": float(frontier_depth),
                        "population_strategy": "row_first",
                        "current_product_residual_strategy": (
                            current_product_residual_strategy
                        ),
                        "next_product_population_strategy": (
                            next_product_population_strategy
                        ),
                        "selected_residual_orientation": (
                            selected_residual_orientation
                        ),
                        "selected_current_orientation": (
                            selected_residual_orientation
                        ),
                        "selected_residual_strategy": selected_residual_strategy,
                        "selected_candidate_family": selected_candidate_family,
                        "candidate_count": len(residual_strategy_candidates),
                        "base_candidate_count": int(
                            transition_base_candidate_count
                        ),
                        "selected_gravity_mode": selected_gravity_mode,
                        "selected_residual_traversal": (
                            selected_residual_traversal
                        ),
                        "selected_frontier_depth": float(frontier_depth),
                        "pi_residual_x_footprint": (
                            float(selected_pi_residual_x_footprint)
                            if selected_pi_residual_x_footprint is not None
                            else None
                        ),
                        "envelope_depth": float(frontier_depth),
                        "selected_frontier_volume_efficiency": float(
                            selected_frontier_volume_efficiency
                        ),
                        "frontier_efficiency": float(
                            selected_frontier_volume_efficiency
                        ),
                        **selected_value_diagnostics,
                        "selection_reason": selection_reason,
                        "first_clean_x_row_index": (
                            winner["first_clean_x_row_index"]
                            if next_product is not None
                            else None
                        ),
                        "gravity_applied": bool(
                            winner["gravity_applied"]
                            if next_product is not None
                            else False
                        ),
                        "support_valid": bool(
                            winner["support_valid"]
                            if next_product is not None
                            else True
                        ),
                        "residual_strategy_candidates": residual_strategy_candidates,
                        "support_surface_count": _frontier_support_surface_count(
                            local_frontier
                        ),
                        "frontier_candidates_evaluated": int(
                            transition_frontier_candidates_evaluated
                        ),
                        "next_product_orientation_candidates": (
                            next_product_orientation_candidates
                        ),
                        "next_product_valid_orientation_count": int(
                            next_product_valid_orientation_count
                        ),
                        "next_product_selected_orientation": (
                            [
                                float(value)
                                for value in next_product_selected_orientation
                            ]
                            if next_product_selected_orientation is not None
                            else None
                        ),
                        "selected_next_product_orientation": (
                            [
                                float(value)
                                for value in next_product_selected_orientation
                            ]
                            if next_product_selected_orientation is not None
                            else None
                        ),
                        "phase_diagnostics": (
                            ["product_block"]
                            + (
                                [
                                    "residual_candidates_generated",
                                    "next_product_all_orientation_evaluation",
                                    "next_product_row_first_population",
                                ]
                                if next_product is not None
                                else ["candidate_residual_bottom_up"]
                            )
                            + (
                                ["gravity_settlement"]
                                if next_product is not None
                                and winner["gravity_applied"]
                                else []
                            )
                            + (
                                [
                                    "physical_validation",
                                    "candidate_scoring",
                                    "candidate_selected",
                                ]
                                if next_product is not None
                                else []
                            )
                            + ["frontier_closed"]
                        ),
                        "closed": True,
                    }
                )
                frontier_x = frontier_end

        if (
            enable_infill
            and frontier_x > product_x_start + TOLERANCE
        ):
            # Front-to-Back closes side space only after the complete current
            # product phase and its Native/DGFE frontier have been committed.
            # This lets the envelope see stepped local geometry from both
            # products without reopening an earlier frontier.
            side_space = Space(
                product_x_start,
                0.0,
                0.0,
                frontier_x - product_x_start,
                normalized_container["W"],
                normalized_container["H"],
            )
            before_infill = dict(remaining_quantities)
            side_placements, loaded_weight, side_stats = (
                fill_side_residual_deterministically(
                    side_space,
                    product,
                    ordered_products,
                    remaining_quantities,
                    next_item_index,
                    normalized_container,
                    loaded_weight,
                    sequence_restricted,
                    eligible_row_indices={
                        candidate.row_index
                        for candidate in ordered_products[product_index + 1 :]
                    },
                    committed_placements=placements,
                    window_x_start=product_x_start,
                    window_x_end=frontier_x,
                )
            )
            placements.extend(side_placements)
            for row_index, before_quantity in before_infill.items():
                quantity = before_quantity - remaining_quantities[row_index]
                if quantity > 0:
                    infill_loaded[row_index] += quantity
                    side_infill_loaded[row_index] += quantity
            _merge_side_infill_stats(infill_stats, side_stats)
            for action in side_stats["actions"]:
                phase_order.append(
                    {
                        "phase": "side_infill",
                        "row_index": action["filler_row_index"],
                        "product_name": action["filler_product"],
                        "quantity": action["quantity"],
                        "from_product_name": product.name,
                        "x_start": action["residual_x_start"],
                        "x_end": action["residual_x_end"],
                    }
                )
            top_eligible_row_indices = {
                candidate.row_index
                for candidate in ordered_products[product_index + 1 :]
            }
            if remaining_quantities.get(product.row_index, 0) > 0:
                top_eligible_row_indices.add(product.row_index)
            before_top_infill = dict(remaining_quantities)
            top_placements, loaded_weight, top_stats = (
                fill_top_residual_deterministically(
                    side_space,
                    product,
                    ordered_products,
                    remaining_quantities,
                    next_item_index,
                    normalized_container,
                    loaded_weight,
                    sequence_restricted,
                    eligible_row_indices=top_eligible_row_indices,
                    committed_placements=placements,
                    window_x_start=product_x_start,
                    window_x_end=frontier_x,
                )
            )
            placements.extend(top_placements)
            for row_index, before_quantity in before_top_infill.items():
                quantity = before_quantity - remaining_quantities[row_index]
                if quantity > 0:
                    infill_loaded[row_index] += quantity
                    top_infill_loaded[row_index] += quantity
            _merge_top_infill_stats(top_infill_stats, top_stats)
            for action in top_stats["top_actions"]:
                phase_order.append(
                    {
                        "phase": "top_infill",
                        "row_index": action["filler_row_index"],
                        "product_name": action["filler_product"],
                        "quantity": action["quantity"],
                        "from_product_name": product.name,
                        "x_start": action["residual"]["x"],
                        "x_end": action["residual"]["x"]
                        + action["residual"]["L"],
                    }
                )
            if enable_infill:
                summary["qty_already_loaded_as_side_infill"] = int(
                    side_infill_loaded[product.row_index]
                )
                summary["qty_already_loaded_as_top_infill"] = int(
                    top_infill_loaded[product.row_index]
                )

        product_summaries.append(summary)

    loaded_by_row = {
        product.row_index: int(
            regular_loaded[product.row_index]
            + frontier_loaded[product.row_index]
            + infill_loaded[product.row_index]
        )
        for product in ordered_products
    }
    unplaced = []
    for product in ordered_products:
        reason = _unplaced_reason(
            product,
            normalized_container,
            loaded_weight,
            frontier_x,
        )
        for item_index in range(loaded_by_row[product.row_index], product.qty):
            unplaced.append(_unplaced_item(product, item_index, reason))

    remaining_length = max(normalized_container["L"] - frontier_x, 0.0)
    spaces = (
        [
            Space(
                frontier_x,
                0.0,
                0.0,
                remaining_length,
                normalized_container["W"],
                normalized_container["H"],
            )
        ]
        if remaining_length > TOLERANCE
        else []
    )
    x_used = max(
        (placement.x + placement.l for placement in placements),
        default=0.0,
    )
    total_packed = len(placements)
    total_unplaced = len(unplaced)
    product_order_metadata = [
        {
            "row_index": product.row_index,
            "product_name": product.name,
            "sequence": product.sequence,
            "input_order": product.input_order,
        }
        for product in ordered_products
    ]
    return {
        "placements": placements,
        "unplaced": unplaced,
        "spaces": spaces,
        "loaded_weight": float(sum(placement.weight for placement in placements)),
        "strategy": (
            "front_to_back_blocks_infill"
            if enable_infill
            else FRONT_TO_BACK_STRATEGY
        ),
        "packing_mode": requested_mode,
        "sequence_zones": [],
        "main_blocks": main_blocks,
        "main_block_units": int(sum(regular_loaded.values())),
        "main_blocks_end_x": float(
            max((block["x_end"] for block in main_blocks), default=0.0)
        ),
        "leftover_units_requested": int(
            sum(product.qty for product in ordered_products)
            - sum(regular_loaded.values())
        ),
        "leftover_units_packed": int(
            sum(frontier_loaded.values()) + sum(infill_loaded.values())
        ),
        "front_to_back_product_order": product_order_metadata,
        "front_to_back_product_blocks": product_summaries,
        "front_to_back_main_blocks": main_blocks,
        "front_to_back_main_block_count": len(main_blocks),
        "front_to_back_block_packed_units": int(sum(regular_loaded.values())),
        "front_to_back_frontiers": frontiers,
        "front_to_back_frontier_count": len(frontiers),
        "front_to_back_phase_order": phase_order,
        "front_to_back_block_candidates_generated": int(
            block_candidates_generated
        ),
        "front_to_back_block_candidates_evaluated": int(
            block_candidates_evaluated
        ),
        "front_to_back_frontier_candidates_evaluated": int(
            frontier_candidates_evaluated
        ),
        "front_to_back_frontiers_evaluated": len(frontiers),
        "front_to_back_total_packed_units": int(total_packed),
        "front_to_back_total_unplaced_units": int(total_unplaced),
        "front_to_back_x_used": float(x_used),
        "front_to_back_clean_frontier_x": float(frontier_x),
        **(
            _side_infill_metadata(FRONT_TO_BACK_INFILL_MODE, infill_stats)
            if enable_infill
            else {}
        ),
        **(
            _top_infill_metadata(FRONT_TO_BACK_INFILL_MODE, top_infill_stats)
            if enable_infill
            else {}
        ),
        **(
            {
                f"{FRONT_TO_BACK_INFILL_MODE}_side_infill_units_total": int(
                    sum(side_infill_loaded.values())
                ),
                f"{FRONT_TO_BACK_INFILL_MODE}_top_infill_units_total": int(
                    sum(top_infill_loaded.values())
                ),
                f"{FRONT_TO_BACK_INFILL_MODE}_mixed_infill_units_total": int(
                    sum(infill_loaded.values())
                ),
            }
            if enable_infill
            else {}
        ),
        # Compatibility aliases for existing result consumers.  They expose
        # the new local-frontier diagnostics without invoking legacy packing.
        "floor_first_candidate_selected": bool(main_blocks),
        "floor_first_candidate_source": "space_evenly_block_primitives",
        "floor_first_main_blocks": main_blocks,
        "floor_first_frontier_evaluations": frontiers,
        "floor_first_frontiers_evaluated": len(frontiers),
        "floor_first_residual_units": int(
            sum(product.qty for product in ordered_products)
            - sum(regular_loaded.values())
        ),
        "floor_first_residual_packed_units": int(
            sum(frontier_loaded.values()) + sum(infill_loaded.values())
        ),
        "floor_first_residual_unplaced_units": int(total_unplaced),
    }


def pack_container(
    container: Dict,
    products: List[Dict],
    mode: Optional[str] = None,
) -> Dict:
    """Pack with an active mode or return a graceful unsupported-mode result."""
    normalized_container = _normalize_container(container)
    requested_mode = _normalize_packing_mode(
        mode if mode is not None else (container or {}).get("packing_mode")
    )
    normalized_input_products = products
    if requested_mode in {
        SPACE_EVENLY_MODE,
        FRONT_TO_BACK_MODE,
    }:
        normalized_input_products = [
            {**dict(product or {}), "sequence": 1} for product in products or []
        ]
    normalized_products = normalize_products(normalized_input_products)
    if requested_mode in {FRONT_TO_BACK_MODE, FRONT_TO_BACK_INFILL_MODE}:
        return _pack_container_front_to_back(
            normalized_container,
            normalized_input_products,
            requested_mode,
        )
    if requested_mode not in {SPACE_EVENLY_MODE, SPACE_EVENLY_INFILL_MODE}:
        return _unsupported_mode_result(
            normalized_container,
            normalized_products,
            requested_mode,
        )

    enable_infill = requested_mode == SPACE_EVENLY_INFILL_MODE
    ordered_products = sort_products(normalized_products, normalized_container)
    sequence_groups = sorted({product.sequence for product in ordered_products})
    sequence_restricted = len(sequence_groups) > 1
    placements: List[Placement] = []
    main_blocks: List[Dict] = []
    product_blocks: List[Dict] = []
    residual_miniblocks: List[Dict] = []
    phase_order: List[Dict] = []
    regular_loaded = {product.row_index: 0 for product in ordered_products}
    residual_loaded = {product.row_index: 0 for product in ordered_products}
    infill_loaded = {product.row_index: 0 for product in ordered_products}
    side_infill_loaded = {product.row_index: 0 for product in ordered_products}
    top_infill_loaded = {product.row_index: 0 for product in ordered_products}
    residual_quantities = {product.row_index: product.qty for product in ordered_products}
    remaining_quantities = {
        product.row_index: product.qty for product in ordered_products
    }
    next_item_index = {product.row_index: 0 for product in ordered_products}
    preferred_orientations: Dict[int, Tuple[float, float, float]] = {}

    frontier = 0.0
    loaded_weight = 0.0
    generated_candidates = 0
    evaluated_candidates = 0
    infill_stats = _new_side_infill_stats(len(sequence_groups))
    top_infill_stats = _new_top_infill_stats(len(sequence_groups))

    # Phase 1: every complete Product Block, in universal product order.
    for product_index, product in enumerate(ordered_products):
        entering_qty = int(remaining_quantities[product.row_index])
        available_length = max(normalized_container["L"] - frontier, 0.0)
        payload_qty = _payload_units_available(
            normalized_container,
            loaded_weight,
            product.weight,
            entering_qty,
        )
        candidates, evaluated = build_product_block_candidates(
            product,
            normalized_container,
            available_length,
        )
        generated_candidates += len(candidates)
        evaluated_candidates += evaluated
        selected = choose_product_block(
            candidates,
            payload_qty,
            available_length,
        )
        product_x_start = frontier
        complete_blocks = 0

        if selected is not None:
            preferred_orientations[product.row_index] = selected.orientations[0]
            complete_blocks = min(
                payload_qty // selected.module_capacity,
                _fit_count(available_length, selected.depth),
            )
            for block_index in range(complete_blocks):
                block_x_start = frontier
                block_placements = _materialize_product_block(
                    product,
                    selected,
                    block_x_start,
                    next_item_index[product.row_index],
                )
                placements.extend(block_placements)
                placed_qty = len(block_placements)
                next_item_index[product.row_index] += placed_qty
                regular_loaded[product.row_index] += placed_qty
                remaining_quantities[product.row_index] = max(
                    remaining_quantities[product.row_index] - placed_qty,
                    0,
                )
                loaded_weight += placed_qty * product.weight
                frontier = block_x_start + selected.depth

                block_metadata = {
                    "row_index": product.row_index,
                    "product_name": product.name,
                    "block_index": block_index,
                    "x_start": float(block_x_start),
                    "x_end": float(frontier),
                    "qty": placed_qty,
                    **_candidate_metadata(selected),
                }
                main_blocks.append(block_metadata)
                phase_order.append(
                    {
                        "phase": "complete_block",
                        "row_index": product.row_index,
                        "product_name": product.name,
                        "quantity": placed_qty,
                        "x_start": float(block_x_start),
                        "x_end": float(frontier),
                    }
                )
            if (
                enable_infill
                and complete_blocks > 0
                and frontier > product_x_start + TOLERANCE
            ):
                # Close all complete blocks from this product as one local
                # window.  The approved block placements remain untouched;
                # only the side envelope is derived after they are committed.
                side_space = Space(
                    product_x_start,
                    0.0,
                    0.0,
                    frontier - product_x_start,
                    normalized_container["W"],
                    normalized_container["H"],
                )
                before_infill = dict(remaining_quantities)
                side_placements, loaded_weight, side_stats = (
                    fill_side_residual_deterministically(
                        side_space,
                        product,
                        ordered_products,
                        remaining_quantities,
                        next_item_index,
                        normalized_container,
                        loaded_weight,
                        sequence_restricted,
                        eligible_row_indices={
                            candidate.row_index
                            for candidate in ordered_products[product_index + 1 :]
                        },
                        committed_placements=placements,
                        window_x_start=product_x_start,
                        window_x_end=frontier,
                    )
                )
                placements.extend(side_placements)
                for row_index, before_quantity in before_infill.items():
                    quantity = before_quantity - remaining_quantities[row_index]
                    if quantity > 0:
                        infill_loaded[row_index] += quantity
                        side_infill_loaded[row_index] += quantity
                _merge_side_infill_stats(infill_stats, side_stats)
                for action in side_stats["actions"]:
                    phase_order.append(
                        {
                            "phase": "side_infill",
                            "row_index": action["filler_row_index"],
                            "product_name": action["filler_product"],
                            "quantity": action["quantity"],
                            "from_product_name": product.name,
                            "x_start": action["residual_x_start"],
                            "x_end": action["residual_x_end"],
                        }
                    )
                top_eligible_row_indices = {
                    candidate.row_index
                    for candidate in ordered_products[product_index + 1 :]
                }
                if remaining_quantities.get(product.row_index, 0) > 0:
                    top_eligible_row_indices.add(product.row_index)
                before_top_infill = dict(remaining_quantities)
                top_placements, loaded_weight, top_stats = (
                    fill_top_residual_deterministically(
                        side_space,
                        product,
                        ordered_products,
                        remaining_quantities,
                        next_item_index,
                        normalized_container,
                        loaded_weight,
                        sequence_restricted,
                        eligible_row_indices=top_eligible_row_indices,
                        committed_placements=placements,
                        window_x_start=product_x_start,
                        window_x_end=frontier,
                    )
                )
                placements.extend(top_placements)
                for row_index, before_quantity in before_top_infill.items():
                    quantity = before_quantity - remaining_quantities[row_index]
                    if quantity > 0:
                        infill_loaded[row_index] += quantity
                        top_infill_loaded[row_index] += quantity
                _merge_top_infill_stats(top_infill_stats, top_stats)
                for action in top_stats["top_actions"]:
                    phase_order.append(
                        {
                            "phase": "top_infill",
                            "row_index": action["filler_row_index"],
                            "product_name": action["filler_product"],
                            "quantity": action["quantity"],
                            "from_product_name": product.name,
                            "x_start": action["residual"]["x"],
                            "x_end": action["residual"]["x"]
                            + action["residual"]["L"],
                        }
                    )

        residual_qty = int(remaining_quantities[product.row_index])
        residual_quantities[product.row_index] = residual_qty
        product_summary = {
            "row_index": product.row_index,
            "product_name": product.name,
            "requested_qty": product.qty,
            **(
                {
                    "qty_entering_product_phase": entering_qty,
                    "qty_already_loaded_as_side_infill": int(
                        side_infill_loaded[product.row_index]
                    ),
                    "qty_already_loaded_as_top_infill": int(
                        top_infill_loaded[product.row_index]
                    ),
                }
                if enable_infill
                else {}
            ),
            "complete_blocks": complete_blocks,
            "regular_qty": regular_loaded[product.row_index],
            "residual_qty": residual_qty,
            "x_start": float(product_x_start),
            "x_end": float(frontier),
            "block": _candidate_metadata(selected) if selected else None,
        }
        product_blocks.append(product_summary)

    complete_frontier = frontier
    complete_placement_count = len(placements)
    total_residual_requested = sum(residual_quantities.values())
    if enable_infill and sequence_restricted:
        residual_miniblocks = []
        residual_candidates_evaluated = 0
        support_checks = 0
        support_relationships = 0
        for sequence in sequence_groups:
            group_products = [
                product
                for product in ordered_products
                if product.sequence == sequence
            ]
            group_quantities = {
                product.row_index: residual_quantities[product.row_index]
                for product in group_products
            }
            (
                frontier,
                loaded_weight,
                group_frontiers,
                group_candidate_evaluations,
                group_support_checks,
                group_support_relationships,
            ) = pack_space_evenly_residual_frontiers(
                normalized_container,
                group_products,
                group_quantities,
                placements,
                residual_loaded,
                next_item_index,
                loaded_weight,
                frontier,
                preferred_orientations,
                enable_side_infill=enable_infill,
                infill_loaded=infill_loaded,
                infill_stats=infill_stats,
                enable_top_infill=enable_infill,
                side_infill_loaded=side_infill_loaded,
                top_infill_loaded=top_infill_loaded,
                top_infill_stats=top_infill_stats,
            )
            frontier_offset = len(residual_miniblocks)
            for local_index, band in enumerate(group_frontiers):
                band["sequence"] = int(sequence)
                band["frontier_index"] = frontier_offset + local_index
                band["band_index"] = frontier_offset + local_index
                band["sequence_band_index"] = local_index
            residual_miniblocks.extend(group_frontiers)
            residual_candidates_evaluated += group_candidate_evaluations
            support_checks += group_support_checks
            support_relationships += group_support_relationships
    else:
        (
            frontier,
            loaded_weight,
            residual_miniblocks,
            residual_candidates_evaluated,
            support_checks,
            support_relationships,
        ) = pack_space_evenly_residual_frontiers(
            normalized_container,
            ordered_products,
            residual_quantities,
            placements,
            residual_loaded,
            next_item_index,
            loaded_weight,
            frontier,
            preferred_orientations,
            enable_side_infill=enable_infill,
            infill_loaded=infill_loaded,
            infill_stats=infill_stats,
            enable_top_infill=enable_infill,
            side_infill_loaded=side_infill_loaded,
            top_infill_loaded=top_infill_loaded,
            top_infill_stats=top_infill_stats,
        )
    for band in residual_miniblocks:
        phase_order.append(
            {
                "phase": "residual_band",
                "sequence": band["sequence"],
                "row_index": band["foundation_row_index"],
                "product_name": band["foundation_product"],
                "quantity": band["qty"],
                "x_start": band["x_start"],
                "x_end": band["x_end"],
            }
        )
        for action in band.get("infill_actions", []):
            phase_order.append(
                {
                    "phase": "side_infill",
                    "row_index": action["filler_row_index"],
                    "product_name": action["filler_product"],
                    "quantity": action["quantity"],
                    "from_product_name": band["anchor_product"],
                    "x_start": action["residual_x_start"],
                    "x_end": action["residual_x_end"],
                }
            )
        for action in band.get("top_infill_actions", []):
            phase_order.append(
                {
                    "phase": "top_infill",
                    "row_index": action["filler_row_index"],
                    "product_name": action["filler_product"],
                    "quantity": action["quantity"],
                    "from_product_name": band["anchor_product"],
                    "x_start": action["residual"]["x"],
                    "x_end": action["residual"]["x"]
                    + action["residual"]["L"],
                }
            )

    loaded_by_row = {
        product.row_index: (
            regular_loaded[product.row_index]
            + residual_loaded[product.row_index]
            + infill_loaded[product.row_index]
        )
        for product in ordered_products
    }
    unplaced = []
    for product in ordered_products:
        reason = _unplaced_reason(
            product,
            normalized_container,
            loaded_weight,
            frontier,
        )
        for item_index in range(loaded_by_row[product.row_index], product.qty):
            unplaced.append(_unplaced_item(product, item_index, reason))

    total_residual_packed = sum(residual_loaded.values())
    remaining_length = max(normalized_container["L"] - frontier, 0.0)
    spaces = (
        [
            Space(
                frontier,
                0.0,
                0.0,
                remaining_length,
                normalized_container["W"],
                normalized_container["H"],
            )
        ]
        if remaining_length > TOLERANCE
        else []
    )
    # Compatibility diagnostics describe the quantities the bounded
    # two-phase construction actually established as its feasible target.
    target_counts = dict(loaded_by_row)
    target_volume = sum(
        loaded_by_row[product.row_index] * product.unit_volume
        for product in ordered_products
    )
    packed_volume = sum(placement.l * placement.w * placement.h for placement in placements)

    result = {
        "placements": placements,
        "unplaced": unplaced,
        "spaces": spaces,
        "loaded_weight": float(sum(placement.weight for placement in placements)),
        "strategy": (
            "space_evenly_blocks_infill"
            if enable_infill
            else "space_evenly_blocks"
        ),
        "packing_mode": requested_mode,
        "sequence_zones": [],
        "main_blocks": main_blocks,
        "main_block_units": int(sum(regular_loaded.values())),
        "main_blocks_end_x": float(complete_frontier),
        "leftover_units_requested": int(total_residual_requested),
        "leftover_units_packed": int(
            total_residual_packed + sum(infill_loaded.values())
        ),
        "space_evenly_product_order": [
            {
                "row_index": product.row_index,
                "product_name": product.name,
                "sequence": product.sequence,
            }
            for product in ordered_products
        ],
        "space_evenly_product_blocks": product_blocks,
        "space_evenly_main_blocks": main_blocks,
        "space_evenly_main_block_count": len(main_blocks),
        "space_evenly_block_count": len(main_blocks),
        "space_evenly_main_block_units": int(sum(regular_loaded.values())),
        "space_evenly_block_packed_units": int(sum(regular_loaded.values())),
        "space_evenly_main_blocks_end_x": float(complete_frontier),
        "space_evenly_residual_zone_start": float(complete_frontier),
        "space_evenly_residual_miniblocks": residual_miniblocks,
        "space_evenly_residual_bands": residual_miniblocks,
        "space_evenly_residual_band_count": len(residual_miniblocks),
        "space_evenly_residual_frontiers": residual_miniblocks,
        "space_evenly_residual_frontier_count": len(residual_miniblocks),
        "space_evenly_support_surface_count": sum(
            band["support_surface_count"] for band in residual_miniblocks
        ),
        "space_evenly_support_checks": support_checks,
        "space_evenly_residual_local_placement_evaluations": support_checks,
        "space_evenly_support_relationship_count": support_relationships,
        "space_evenly_residual_units": int(total_residual_requested),
        "space_evenly_residual_packed_units": int(total_residual_packed),
        "space_evenly_residual_unplaced_units": int(
            total_residual_requested - total_residual_packed
        ),
        "space_evenly_leftover_units_requested": int(total_residual_requested),
        "space_evenly_leftover_units_packed": int(total_residual_packed),
        "space_evenly_leftover_units_sent_to_greedy": int(total_residual_requested),
        "space_evenly_complete_placement_count": complete_placement_count,
        "space_evenly_phase_order": phase_order,
        "space_evenly_block_candidates_generated": generated_candidates,
        "space_evenly_block_candidates_evaluated": evaluated_candidates,
        "space_evenly_total_block_candidates_evaluated": evaluated_candidates,
        "space_evenly_residual_candidates_evaluated": residual_candidates_evaluated,
        "space_evenly_total_residual_candidates_evaluated": residual_candidates_evaluated,
        "space_evenly_residual_states_evaluated": len(residual_miniblocks),
        "space_evenly_beam_states_evaluated": 0,
        "space_evenly_ceiling_candidate_count": 0,
        "space_evenly_ceiling_candidates_evaluated": 0,
        "space_evenly_effective_height": float(normalized_container["H"]),
        "space_evenly_actual_container_height": float(normalized_container["H"]),
        "space_evenly_height_reduction": 0.0,
        "space_evenly_theoretical_average_height": (
            target_volume / (normalized_container["L"] * normalized_container["W"])
        ),
        "space_evenly_target_counts": {
            str(product.row_index): target_counts[product.row_index]
            for product in ordered_products
        },
        "space_evenly_target_total_units": int(
            sum(target_counts.values())
        ),
        "space_evenly_target_packed_volume": float(packed_volume),
        "space_evenly_x_used": float(frontier),
        **(
            _side_infill_metadata(SPACE_EVENLY_INFILL_MODE, infill_stats)
            if enable_infill
            else {}
        ),
        **(
            _top_infill_metadata(SPACE_EVENLY_INFILL_MODE, top_infill_stats)
            if enable_infill
            else {}
        ),
        **(
            {
                f"{SPACE_EVENLY_INFILL_MODE}_side_infill_units_total": int(
                    sum(side_infill_loaded.values())
                ),
                f"{SPACE_EVENLY_INFILL_MODE}_top_infill_units_total": int(
                    sum(top_infill_loaded.values())
                ),
                f"{SPACE_EVENLY_INFILL_MODE}_mixed_infill_units_total": int(
                    sum(infill_loaded.values())
                ),
            }
            if enable_infill
            else {}
        ),
    }
    return result


def pack_container_sequence_loading(container: Dict, products: List[Dict]) -> Dict:
    return pack_container(container, products, mode="sequence_loading")


def pack_container_accessible_sequence_loading(
    container: Dict,
    products: List[Dict],
) -> Dict:
    return pack_container(container, products, mode="accessible_sequence_loading")


def pack_container_strict_sequence_loading(
    container: Dict,
    products: List[Dict],
) -> Dict:
    return pack_container(container, products, mode="strict_sequence_loading")


def summarize(container: Dict, products: List[Dict], pack_result: Dict) -> Dict:
    placements: List[Placement] = list(pack_result.get("placements") or [])
    unplaced = list(pack_result.get("unplaced") or [])
    loaded_weight = float(pack_result.get("loaded_weight", 0) or 0)

    container_volume = float(container["L"] * container["W"] * container["H"])
    packed_volume = sum(placement.l * placement.w * placement.h for placement in placements)
    packed_by_row: Dict[int, int] = {}
    for placement in placements:
        packed_by_row[placement.row_index] = packed_by_row.get(placement.row_index, 0) + 1

    rows = []
    for row_index, product in enumerate(products or []):
        identity = int(product.get("_row_index", row_index))
        rows.append(
            {
                "name": product["name"],
                "length": product["length"],
                "width": product["width"],
                "height": product["height"],
                "qty_requested": product["qty"],
                "qty_packed": packed_by_row.get(identity, 0),
                "max_qty": bool(product.get("max_qty", False)),
                "weight_each": product.get("weight", 0),
                "stackable": bool(product.get("stackable", True)),
                "sequence": product.get("sequence", 1),
            }
        )

    if placements:
        occupied_length = max(placement.x + placement.l for placement in placements)
        occupied_width = max(placement.y + placement.w for placement in placements)
        occupied_height = max(placement.z + placement.h for placement in placements)
    else:
        occupied_length = occupied_width = occupied_height = 0.0

    tare_weight = container.get("tare_weight")
    payload_limit = container.get("max_weight")
    has_payload_limit = _has_payload_limit(container)
    gross_weight = loaded_weight + (
        float(tare_weight) if tare_weight is not None else 0.0
    )

    return {
        "container_volume": container_volume,
        "packed_volume": packed_volume,
        "container_volume_m3": container_volume / 1_000_000_000.0,
        "packed_volume_m3": packed_volume / 1_000_000_000.0,
        "utilization_volume_pct": (
            100.0 * packed_volume / container_volume if container_volume > 0 else 0.0
        ),
        "container_max_weight": float(payload_limit) if has_payload_limit else None,
        "has_payload_limit": has_payload_limit,
        "loaded_weight": loaded_weight,
        "tare_weight": float(tare_weight) if tare_weight is not None else None,
        "gross_weight": gross_weight,
        "utilization_weight_pct": (
            100.0 * loaded_weight / float(payload_limit)
            if has_payload_limit
            else None
        ),
        "placed_units": len(placements),
        "unplaced_units": len(unplaced),
        "occupied_length": occupied_length,
        "occupied_width": occupied_width,
        "occupied_height": occupied_height,
        "residual_length": max(float(container["L"]) - occupied_length, 0.0),
        "residual_width": max(float(container["W"]) - occupied_width, 0.0),
        "residual_height": max(float(container["H"]) - occupied_height, 0.0),
        "product_rows": rows,
    }


def run_container_tool(container: Dict, products: List[Dict], media_root: str) -> Dict:
    pack_result = pack_container(container, products)
    summary = summarize(container, products, pack_result)

    result = {
        "summary": summary,
        "placements": pack_result["placements"],
        "unplaced": pack_result["unplaced"],
        "spaces": pack_result.get("spaces") or [],
        "strategy": pack_result.get("strategy", ""),
        "packing_mode": pack_result.get("packing_mode", SPACE_EVENLY_MODE),
        "sequence_zones": pack_result.get("sequence_zones") or [],
        # Kept neutral for callers that still read the historical image keys.
        # Active visualization is generated from placements by Three.js.
        "image_rel_path": "",
        "image_rel_paths": {},
    }
    for key in ("error", "errors", "messages"):
        if key in pack_result:
            result[key] = pack_result[key]
    result.update(
        {
            key: value
            for key, value in pack_result.items()
            if key.startswith("space_evenly_")
            or key.startswith("front_to_back_")
            or key.startswith("floor_first_")
        }
    )
    return result
