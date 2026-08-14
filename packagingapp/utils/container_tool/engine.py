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


TOLERANCE = 1e-7
FRONTIER_EFFICIENCY_TOLERANCE = 1e-9
YZ_UTILIZATION_EQ_TOL = 0.0025
RESIDUAL_WIDTH_UTILIZATION_EQ_TOL = 0.001
SPACE_EVENLY_MODE = "space_evenly"
MAXIMUM_UTILIZATION_MODE = "maximum_utilization"
FRONT_TO_BACK_MODE = "maximum_utilization_floor_first"
FRONT_TO_BACK_STRATEGY = "front_to_back_blocks"
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
    if mode is None or str(mode).strip() == "":
        return SPACE_EVENLY_MODE
    value = str(mode).strip().lower().replace("-", "_").replace(" ", "_")
    if value in {"space_evenly", "evenly_spaced", "spread_evenly"}:
        return SPACE_EVENLY_MODE
    if value == MAXIMUM_UTILIZATION_MODE:
        return MAXIMUM_UTILIZATION_MODE
    if value in {
        FRONT_TO_BACK_MODE,
        "front_to_back",
        "front_to_back_blocks",
        "load_front_to_back",
    }:
        return FRONT_TO_BACK_MODE
    return value


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
            if support.stackable and support.z + support.h <= container["H"] + TOLERANCE:
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
) -> Dict:
    """Evaluate one isolated current-residual/next-product transition."""
    candidate_depth, _ = _frontier_required_depth(
        current_product,
        current_residual_qty,
        current_orientation,
        container,
        loaded_weight,
        x_depth if remaining_length is None else remaining_length,
    )
    trial_placements = list(placements)
    current_placements, loaded_after_current, current_qty = (
        _frontier_grid_placements(
            current_product,
            current_residual_qty,
            x_start,
            candidate_depth,
            current_orientation,
            container,
            trial_placements,
            current_first_item_index,
            loaded_weight,
            traversal=strategy,
        )
    )

    next_placements: List[Placement] = []
    next_selected_orientation = None
    next_orientation_candidates: List[Dict] = []
    next_valid_orientation_count = 0
    next_qty = 0
    loaded_after = loaded_after_current
    candidate_evaluations = 0

    if current_qty == current_residual_qty:
        (
            next_selected_orientation,
            next_orientation_candidates,
            candidate_evaluations,
        ) = _evaluate_next_product_frontier_orientations(
            next_product,
            next_remaining_qty,
            x_start,
            candidate_depth,
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
            next_placements, loaded_after, next_qty, _ = _frontier_fill_next_product(
                next_product,
                next_remaining_qty,
                x_start,
                candidate_depth,
                next_selected_orientation,
                container,
                trial_placements,
                next_first_item_index,
                loaded_after_current,
            )

    current_packed_volume = current_qty * current_product.unit_volume
    next_packed_volume = next_qty * next_product.unit_volume
    total_packed_volume = current_packed_volume + next_packed_volume
    frontier_prism_volume = (
        candidate_depth * container["W"] * container["H"]
    )
    frontier_volume_efficiency = (
        total_packed_volume / frontier_prism_volume
        if frontier_prism_volume > TOLERANCE
        else 0.0
    )

    return {
        "strategy": strategy,
        "current_product_orientation": [
            float(value) for value in current_orientation
        ],
        "current_product_orientation_index": int(current_orientation_index),
        "placements": current_placements + next_placements,
        "current_product_placements": current_placements,
        "next_product_placements": next_placements,
        "current_product_qty_packed": int(current_qty),
        "frontier_depth": float(candidate_depth),
        "frontier_x_start": float(x_start),
        "frontier_x_end": float(x_start + candidate_depth),
        "next_product_qty_packed": int(next_qty),
        "next_product_selected_orientation": next_selected_orientation,
        "next_product_orientation_candidates": next_orientation_candidates,
        "next_product_valid_orientation_count": int(next_valid_orientation_count),
        "current_product_packed_volume": float(current_packed_volume),
        "next_product_packed_volume": float(next_packed_volume),
        "total_frontier_packed_volume": float(total_packed_volume),
        "frontier_prism_volume": float(frontier_prism_volume),
        "frontier_volume_efficiency": float(frontier_volume_efficiency),
        "loaded_weight_after": float(loaded_after),
        "candidate_evaluations": int(candidate_evaluations),
        "valid": bool(current_qty == current_residual_qty),
    }


def _select_frontier_transition_candidate(
    candidates: List[Dict],
) -> Tuple[Dict, str]:
    """Select by current quantity, then efficient deterministic frontier use."""
    maximum_current_qty = max(
        candidate["current_product_qty_packed"] for candidate in candidates
    )
    current_shortlist = [
        candidate
        for candidate in candidates
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

    maximum_efficiency = max(
        candidate["frontier_volume_efficiency"]
        for candidate in current_shortlist
    )
    efficiency_shortlist = [
        candidate
        for candidate in current_shortlist
        if maximum_efficiency - candidate["frontier_volume_efficiency"]
        <= FRONTIER_EFFICIENCY_TOLERANCE
    ]
    row_first_shortlist = [
        candidate
        for candidate in efficiency_shortlist
        if candidate["strategy"] == "row_first"
    ]
    row_first_tie = bool(row_first_shortlist) and any(
        candidate["strategy"] == "column_first"
        for candidate in efficiency_shortlist
    )
    ranking_pool = row_first_shortlist or efficiency_shortlist
    maximum_next_qty = max(
        candidate["next_product_qty_packed"] for candidate in ranking_pool
    )
    next_qty_shortlist = [
        candidate
        for candidate in ranking_pool
        if candidate["next_product_qty_packed"] == maximum_next_qty
    ]
    minimum_depth = min(candidate["frontier_depth"] for candidate in next_qty_shortlist)
    depth_shortlist = [
        candidate
        for candidate in next_qty_shortlist
        if abs(candidate["frontier_depth"] - minimum_depth) <= TOLERANCE
    ]
    winner = min(
        depth_shortlist,
        key=lambda candidate: candidate["current_product_orientation_index"],
    )

    if maximum_efficiency - min(
        candidate["frontier_volume_efficiency"] for candidate in current_shortlist
    ) > FRONTIER_EFFICIENCY_TOLERANCE:
        return winner, "better_frontier_efficiency"
    if row_first_tie:
        return winner, "tie_prefer_row_first"
    if len({candidate["next_product_qty_packed"] for candidate in ranking_pool}) > 1:
        return winner, "more_next_product_units"
    if len({candidate["frontier_depth"] for candidate in next_qty_shortlist}) > 1:
        return winner, "smaller_frontier_depth"
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


def _pack_container_front_to_back(
    container: Dict,
    products: List[Dict],
    requested_mode: str,
) -> Dict:
    """Load complete blocks, then close each bounded local transition frontier."""
    normalized_container = _normalize_container(container)
    normalized_products = normalize_products(
        [
            {**dict(product or {}), "sequence": 1}
            for product in products or []
        ]
    )
    ordered_products = sort_products(normalized_products, normalized_container)

    placements: List[Placement] = []
    main_blocks: List[Dict] = []
    product_summaries: List[Dict] = []
    frontiers: List[Dict] = []
    phase_order: List[Dict] = []
    regular_loaded = {product.row_index: 0 for product in ordered_products}
    frontier_loaded = {product.row_index: 0 for product in ordered_products}
    next_item_index = {product.row_index: 0 for product in ordered_products}
    frontier_x = 0.0
    loaded_weight = 0.0
    block_candidates_generated = 0
    block_candidates_evaluated = 0
    frontier_candidates_evaluated = 0

    for product_index, product in enumerate(ordered_products):
        prior_frontier_qty = frontier_loaded[product.row_index]
        entering_qty = max(product.qty - prior_frontier_qty, 0)
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
            "selected_frontier_depth": None,
            "selected_frontier_volume_efficiency": None,
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
                ordered_products[product_index + 1]
                if product_index + 1 < len(ordered_products)
                else None
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
                selection_reason = "no_next_product"
                current_product_residual_strategy = "row_first"
                next_product_population_strategy = None
                residual_strategy_candidates: List[Dict] = []
                selected_residual_orientation = None
                selected_frontier_volume_efficiency = 0.0

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
                    next_remaining = max(
                        next_product.qty - frontier_loaded[next_product.row_index],
                        0,
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

                    transition_candidates = [
                        _evaluate_frontier_transition_candidate(
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
                        for orientation_index, orientation in enumerate(
                            product.orientations
                        )
                        for strategy in ("row_first", "column_first")
                    ]
                    winner, selection_reason = _select_frontier_transition_candidate(
                        transition_candidates
                    )
                    selected_residual_strategy = winner["strategy"]
                    current_product_residual_strategy = winner["strategy"]
                    next_product_population_strategy = "row_first"
                    local_frontier = winner["placements"]
                    own_frontier_qty = winner["current_product_qty_packed"]
                    next_frontier_qty = winner["next_product_qty_packed"]
                    frontier_depth = winner["frontier_depth"]
                    selected_residual_orientation = winner[
                        "current_product_orientation"
                    ]
                    selected_frontier_volume_efficiency = winner[
                        "frontier_volume_efficiency"
                    ]
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
                            "current_product_orientation": candidate[
                                "current_product_orientation"
                            ],
                            "current_product_orientation_index": int(
                                candidate["current_product_orientation_index"]
                            ),
                            "strategy": candidate["strategy"],
                            "current_product_residual_requested": int(
                                residual_qty
                            ),
                            "current_product_residual_packed": int(
                                candidate["current_product_qty_packed"]
                            ),
                            "next_product_qty_packed": int(
                                candidate["next_product_qty_packed"]
                            ),
                            "frontier_depth": float(candidate["frontier_depth"]),
                            "frontier_x_start": float(candidate["frontier_x_start"]),
                            "frontier_x_end": float(candidate["frontier_x_end"]),
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
                            "next_product_valid_orientation_count": int(
                                candidate["next_product_valid_orientation_count"]
                            ),
                            "next_product_orientation_candidates": candidate[
                                "next_product_orientation_candidates"
                            ],
                            "current_product_packed_volume": float(
                                candidate["current_product_packed_volume"]
                            ),
                            "next_product_packed_volume": float(
                                candidate["next_product_packed_volume"]
                            ),
                            "total_frontier_packed_volume": float(
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
                        }
                        for candidate in transition_candidates
                    ]

                next_item_index[product.row_index] += own_frontier_qty
                frontier_loaded[product.row_index] += own_frontier_qty
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
                summary["selected_frontier_depth"] = float(frontier_depth)
                summary["selected_frontier_volume_efficiency"] = float(
                    selected_frontier_volume_efficiency
                )
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
                        "current_product_residual_packed": int(own_frontier_qty),
                        "next_product_qty_packed": int(next_frontier_qty),
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
                        "selected_residual_strategy": selected_residual_strategy,
                        "selected_frontier_depth": float(frontier_depth),
                        "selected_frontier_volume_efficiency": float(
                            selected_frontier_volume_efficiency
                        ),
                        "selection_reason": selection_reason,
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
                        "closed": True,
                    }
                )
                frontier_x = frontier_end

        product_summaries.append(summary)

    loaded_by_row = {
        product.row_index: int(
            regular_loaded[product.row_index]
            + frontier_loaded[product.row_index]
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
        "strategy": FRONT_TO_BACK_STRATEGY,
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
            sum(frontier_loaded.values())
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
        "floor_first_residual_packed_units": int(sum(frontier_loaded.values())),
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
        MAXIMUM_UTILIZATION_MODE,
        FRONT_TO_BACK_MODE,
    }:
        normalized_input_products = [
            {**dict(product or {}), "sequence": 1} for product in products or []
        ]
    normalized_products = normalize_products(normalized_input_products)
    if requested_mode in {MAXIMUM_UTILIZATION_MODE, FRONT_TO_BACK_MODE}:
        return _pack_container_front_to_back(
            normalized_container,
            normalized_input_products,
            requested_mode,
        )
    if requested_mode != SPACE_EVENLY_MODE:
        return _unsupported_mode_result(
            normalized_container,
            normalized_products,
            requested_mode,
        )

    ordered_products = sort_products(normalized_products, normalized_container)
    placements: List[Placement] = []
    main_blocks: List[Dict] = []
    product_blocks: List[Dict] = []
    residual_miniblocks: List[Dict] = []
    phase_order: List[Dict] = []
    regular_loaded = {product.row_index: 0 for product in ordered_products}
    residual_loaded = {product.row_index: 0 for product in ordered_products}
    residual_quantities = {product.row_index: product.qty for product in ordered_products}
    next_item_index = {product.row_index: 0 for product in ordered_products}

    frontier = 0.0
    loaded_weight = 0.0
    generated_candidates = 0
    evaluated_candidates = 0

    # Phase 1: every complete Product Block, in universal product order.
    for product in ordered_products:
        available_length = max(normalized_container["L"] - frontier, 0.0)
        payload_qty = _payload_units_available(
            normalized_container,
            loaded_weight,
            product.weight,
            product.qty,
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

        residual_qty = product.qty - regular_loaded[product.row_index]
        residual_quantities[product.row_index] = residual_qty
        product_summary = {
            "row_index": product.row_index,
            "product_name": product.name,
            "requested_qty": product.qty,
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
    (
        frontier,
        loaded_weight,
        residual_miniblocks,
        residual_candidates_evaluated,
        support_checks,
        support_relationships,
    ) = pack_residuals_support_greedy(
        normalized_container,
        ordered_products,
        residual_quantities,
        placements,
        residual_loaded,
        next_item_index,
        loaded_weight,
        frontier,
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

    loaded_by_row = {
        product.row_index: (
            regular_loaded[product.row_index] + residual_loaded[product.row_index]
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
    # Compatibility diagnostics describe the quantities the bounded V1
    # construction actually established as its feasible target.
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
        "strategy": "space_evenly_blocks",
        "packing_mode": SPACE_EVENLY_MODE,
        "sequence_zones": [],
        "main_blocks": main_blocks,
        "main_block_units": int(sum(regular_loaded.values())),
        "main_blocks_end_x": float(complete_frontier),
        "leftover_units_requested": int(total_residual_requested),
        "leftover_units_packed": int(total_residual_packed),
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
        "space_evenly_support_surface_count": sum(
            band["support_surface_count"] for band in residual_miniblocks
        ),
        "space_evenly_support_checks": support_checks,
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
