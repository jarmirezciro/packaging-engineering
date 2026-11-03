"""Container Selection adapter for shared 2D mosaic patterns."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Sequence, Tuple

from packagingapp.utils.box_selection.box_selection_tool_arrays_2_origin_coordinates import (
    allowed_product_orientations,
)
from packagingapp.utils.packing_patterns import enumerate_pattern_candidates
from packagingapp.utils.packing_patterns.geometry import (
    count_fitting_units,
    fits_within,
    grid_quantity,
    representation_tolerance,
)


Dims = Tuple[float, float, float]
Point = Tuple[float, float, float]

MOSAIC_CANDIDATE_BUDGET = 192
MOSAIC_MAX_LAYER_PLACEMENTS = 20_000
MOSAIC_MAX_TOTAL_PLACEMENTS = 100_000


@dataclass(frozen=True)
class MosaicPlacement:
    origin: Point
    dimensions: Dims
    layer: int


@dataclass(frozen=True)
class MosaicSearchResult:
    placements: Tuple[MosaicPlacement, ...] = ()
    family: str = "none"
    variant: str = "none"
    vertical_axis_index: int = -1
    candidate_count: int = 0
    valid_candidate_count: int = 0
    resource_limited: bool = False
    validation_error: str = ""
    elapsed_seconds: float = 0.0
    reported_quantity: int = 0
    arithmetic_only: bool = False

    @property
    def quantity(self) -> int:
        return self.reported_quantity or len(self.placements)


def _same_dimensions(first: Dims, second: Dims, tolerance: float) -> bool:
    return all(abs(first[index] - second[index]) <= tolerance for index in range(3))


def validate_mosaic_placements(
    placements: Sequence[MosaicPlacement],
    product: Dims,
    container: Dims,
    r1: int,
    r2: int,
    r3: int,
) -> Tuple[bool, str]:
    """Independently validate bounds, orientations, duplicates, and collisions."""
    if not all(math.isfinite(value) and value > 0 for value in (*product, *container)):
        return False, "non-positive or non-finite physical dimensions"
    allowed = tuple(
        tuple(float(value) for value in item["dimensions"])
        for item in allowed_product_orientations(product, r1, r2, r3)
    )
    if not allowed:
        return False, "no product orientation is permitted"
    tolerance = representation_tolerance(
        *product,
        *container,
        *(value for placement in placements for value in (*placement.origin, *placement.dimensions)),
    )
    seen = set()
    by_layer = {}
    for index, placement in enumerate(placements):
        if not all(math.isfinite(value) and value > 0 for value in placement.dimensions):
            return False, f"placement {index} has invalid dimensions"
        if not any(_same_dimensions(placement.dimensions, dims, tolerance) for dims in allowed):
            return False, f"placement {index} violates rotation permissions"
        for axis in range(3):
            if placement.origin[axis] < -tolerance:
                return False, f"placement {index} starts outside the container"
            if not fits_within(
                placement.origin[axis] + placement.dimensions[axis], container[axis]
            ):
                return False, f"placement {index} exceeds the container"
        key = tuple(round(value, 9) for value in (*placement.origin, *placement.dimensions))
        if key in seen:
            return False, f"placement {index} duplicates an earlier placement"
        seen.add(key)
        by_layer.setdefault(round(placement.origin[2], 9), []).append(placement)

    for layer in by_layer.values():
        ordered = sorted(layer, key=lambda item: (item.origin[0], item.origin[1]))
        for position, first in enumerate(ordered):
            first_x_end = first.origin[0] + first.dimensions[0]
            for second in ordered[position + 1 :]:
                if second.origin[0] >= first_x_end - tolerance:
                    break
                overlap_x = min(
                    first.origin[0] + first.dimensions[0],
                    second.origin[0] + second.dimensions[0],
                ) - max(first.origin[0], second.origin[0])
                overlap_y = min(
                    first.origin[1] + first.dimensions[1],
                    second.origin[1] + second.dimensions[1],
                ) - max(first.origin[1], second.origin[1])
                overlap_z = min(
                    first.origin[2] + first.dimensions[2],
                    second.origin[2] + second.dimensions[2],
                ) - max(first.origin[2], second.origin[2])
                if overlap_x > tolerance and overlap_y > tolerance and overlap_z > tolerance:
                    return False, "placements collide"
    return True, ""


def _vertical_families(product: Dims, r1: int, r2: int, r3: int):
    """Yield one horizontal footprint per permitted original vertical axis."""
    permitted = allowed_product_orientations(product, r1, r2, r3)
    seen = set()
    for item in permitted:
        x, y, z = (float(value) for value in item["dimensions"])
        key = (round(z, 12), tuple(sorted((round(x, 12), round(y, 12)))))
        if key in seen:
            continue
        seen.add(key)
        yield int(item["index"]), x, y, z


def search_mosaic_placements(
    product: Dims,
    container: Dims,
    r1: int,
    r2: int,
    r3: int,
    *,
    candidate_budget: int = MOSAIC_CANDIDATE_BUDGET,
    legacy_quantity: int = 0,
) -> MosaicSearchResult:
    """Return the strongest independently valid mosaic within fixed resources."""
    started = time.perf_counter()
    product = tuple(float(value) for value in product)
    container = tuple(float(value) for value in container)
    if not all(math.isfinite(value) and value > 0 for value in (*product, *container)):
        return MosaicSearchResult(
            validation_error="non-positive or non-finite physical dimensions",
            elapsed_seconds=time.perf_counter() - started,
        )

    families = tuple(_vertical_families(product, r1, r2, r3))
    arithmetic_bounds = []
    for _orientation_index, footprint_l, footprint_w, vertical in families:
        layers = count_fitting_units(container[2], vertical)
        regular = max(
            grid_quantity(container[0], container[1], footprint_l, footprint_w),
            grid_quantity(container[0], container[1], footprint_w, footprint_l),
        ) * layers
        area_bound = count_fitting_units(
            container[0] * container[1], footprint_l * footprint_w
        ) * layers
        arithmetic_bounds.append((regular, area_bound))
    best_regular = max((item[0] for item in arithmetic_bounds), default=0)
    best_area_bound = max((item[1] for item in arithmetic_bounds), default=0)
    if (
        legacy_quantity > 0
        and best_regular == best_area_bound
        and best_area_bound <= legacy_quantity
    ):
        # A regular grid reaches the footprint area upper bound, so no 2D
        # mosaic can improve it. Report that proven capacity arithmetically and
        # avoid materializing thousands of duplicate tie placements.
        return MosaicSearchResult(
            family="block",
            variant="area-bound",
            candidate_count=1,
            valid_candidate_count=1,
            reported_quantity=best_regular,
            arithmetic_only=True,
            elapsed_seconds=time.perf_counter() - started,
        )

    best = ()
    best_layer = ()
    best_vertical = 0.0
    best_layers = 0
    best_quantity = 0
    best_family = "none"
    best_variant = "none"
    best_axis = -1
    candidate_count = 0
    valid_count = 0
    resource_limited = False

    for orientation_index, footprint_l, footprint_w, vertical in families:
        if candidate_count >= candidate_budget:
            resource_limited = True
            break
        layers = count_fitting_units(container[2], vertical)
        if layers <= 0:
            continue
        area_upper_bound = count_fitting_units(
            container[0] * container[1], footprint_l * footprint_w
        )
        if area_upper_bound > MOSAIC_MAX_LAYER_PLACEMENTS:
            resource_limited = True
            continue
        remaining_budget = candidate_budget - candidate_count
        candidates = enumerate_pattern_candidates(
            container[0],
            container[1],
            footprint_l,
            footprint_w,
            candidate_budget=remaining_budget,
        )
        for candidate in candidates:
            candidate_count += 1
            valid_count += 1
            total_quantity = candidate.quantity * layers
            if total_quantity > MOSAIC_MAX_TOTAL_PLACEMENTS:
                resource_limited = True
                continue
            if total_quantity <= best_quantity:
                continue
            best_quantity = total_quantity
            best_layer = candidate.placements
            best_vertical = vertical
            best_layers = layers
            best_family = candidate.family
            best_variant = candidate.variant
            best_axis = orientation_index

    validation_error = ""
    if best_layer:
        best = tuple(
            MosaicPlacement(
                origin=(placement.x, placement.y, layer * best_vertical),
                dimensions=(placement.l, placement.w, best_vertical),
                layer=layer,
            )
            for layer in range(best_layers)
            for placement in best_layer
        )
        valid, validation_error = validate_mosaic_placements(
            best, product, container, r1, r2, r3
        )
        if not valid or len(best) != best_quantity:
            if valid:
                validation_error = "reported quantity differs from placements"
            best = ()
            best_family = "none"
            best_variant = "none"
            best_axis = -1
    return MosaicSearchResult(
        placements=best,
        family=best_family,
        variant=best_variant,
        vertical_axis_index=best_axis,
        candidate_count=candidate_count,
        valid_candidate_count=valid_count,
        resource_limited=resource_limited,
        validation_error=validation_error,
        elapsed_seconds=time.perf_counter() - started,
    )
