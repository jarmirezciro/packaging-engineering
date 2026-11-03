"""Independent physical validation for generated 2D mosaics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

from .geometry import Placement2D, fits_within, representation_tolerance


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: Tuple[str, ...] = ()


def layout_signature(
    placements: Sequence[Placement2D],
) -> Tuple[Tuple[float, float, float, float, str], ...]:
    return tuple(
        sorted(
            (
                round(p.x, 9),
                round(p.y, 9),
                round(p.l, 9),
                round(p.w, 9),
                p.orientation,
            )
            for p in placements
        )
    )


def geometry_signature(
    placements: Sequence[Placement2D],
) -> Tuple[Tuple[float, float, float, float], ...]:
    return tuple(item[:4] for item in layout_signature(placements))


def positive_area_overlap(
    first: Placement2D, second: Placement2D, tolerance: float
) -> bool:
    overlap_x = min(first.x + first.l, second.x + second.l) - max(
        first.x, second.x
    )
    overlap_y = min(first.y + first.w, second.y + second.w) - max(
        first.y, second.y
    )
    return overlap_x > tolerance and overlap_y > tolerance


def validate_placements(
    placements: Sequence[Placement2D],
    area_l: float,
    area_w: float,
    *,
    expected_footprint: Optional[Tuple[float, float]] = None,
) -> ValidationResult:
    errors = []
    if area_l <= 0 or area_w <= 0:
        return ValidationResult(False, ("non-positive available footprint",))

    tolerance = representation_tolerance(
        area_l,
        area_w,
        *(value for p in placements for value in (p.x, p.y, p.l, p.w)),
    )
    seen = set()
    for index, placement in enumerate(placements):
        if placement.l <= 0 or placement.w <= 0:
            errors.append(f"placement {index} has non-positive dimensions")
            continue
        if placement.x < -tolerance or placement.y < -tolerance:
            errors.append(f"placement {index} starts outside the footprint")
        if not fits_within(placement.x + placement.l, area_l) or not fits_within(
            placement.y + placement.w, area_w
        ):
            errors.append(f"placement {index} exceeds the footprint")
        key = (
            round(placement.x, 9),
            round(placement.y, 9),
            round(placement.l, 9),
            round(placement.w, 9),
        )
        if key in seen:
            errors.append(f"placement {index} duplicates an earlier placement")
        seen.add(key)

        if expected_footprint is not None:
            base_l, base_w = expected_footprint
            same = abs(placement.l - base_l) <= tolerance and abs(
                placement.w - base_w
            ) <= tolerance
            swapped = abs(placement.l - base_w) <= tolerance and abs(
                placement.w - base_l
            ) <= tolerance
            if not (same or swapped):
                errors.append(f"placement {index} has a foreign footprint")

    ordered = sorted(placements, key=lambda p: (p.x, p.y, p.l, p.w))
    for index, first in enumerate(ordered):
        first_end = first.x + first.l
        for second in ordered[index + 1 :]:
            if second.x >= first_end - tolerance:
                break
            if positive_area_overlap(first, second, tolerance):
                errors.append("placements overlap")
                return ValidationResult(False, tuple(errors))
    return ValidationResult(not errors, tuple(errors))
