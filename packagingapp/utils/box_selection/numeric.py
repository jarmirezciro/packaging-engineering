"""Numerical helpers for canonical-millimetre box selection geometry."""

import math


# A handful of ulps covers the division/multiplication error introduced while
# converting display units and deriving residual cuboids, without turning a
# physically meaningful shortfall into an extra product.
GRID_COUNT_TOLERANCE_ULPS = 8


def count_fitting_units(available, unit):
    """Return the deterministic floor of ``available / unit``.

    Floating-point values produced by unit conversion or residual-space
    subtraction can land a few ulps below an exact integer multiple.  In that
    narrow case only, accept the next integer when its required physical
    extent is within an ulp-scaled tolerance of the available extent.

    Invalid, non-finite, or non-positive dimensions do not fit any unit.
    The tolerance is based on the physical millimetre values rather than
    rounding either input, so a meaningful shortfall remains a floor result.
    """
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

    count = math.floor(quotient)
    next_count = count + 1
    required = next_count * unit
    if math.isfinite(required) and required <= available:
        return next_count
    if required > available and math.isfinite(required):
        scale = max(abs(available), abs(required), abs(unit))
        tolerance = GRID_COUNT_TOLERANCE_ULPS * math.ulp(scale)
        if required - available <= tolerance:
            return next_count

    return max(count, 0)
