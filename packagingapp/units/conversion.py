"""Numeric-only physical unit conversion without display rounding."""

from decimal import Decimal
import math
from numbers import Real

from .definitions import LENGTH_UNITS, MASS_UNITS


class UnsupportedUnitError(ValueError):
    """Raised when a unit token is outside the supported vocabulary."""


def _normalized_unit(unit, definitions, quantity_name):
    if not isinstance(unit, str):
        raise UnsupportedUnitError(
            f"Unsupported {quantity_name} unit {unit!r}. "
            f"Use one of: {', '.join(definitions)}."
        )

    normalized = unit.strip().lower()
    if normalized not in definitions:
        raise UnsupportedUnitError(
            f"Unsupported {quantity_name} unit {unit!r}. "
            f"Use one of: {', '.join(definitions)}."
        )
    return normalized


def normalize_unit(unit, definitions, default):
    """Return a validated unit token, applying a legacy-safe default."""
    token = default if unit in (None, "") else unit
    return _normalized_unit(token, definitions, "physical quantity")


def _convert(value, from_unit, to_unit, definitions, quantity_name):
    source = _normalized_unit(from_unit, definitions, quantity_name)
    destination = _normalized_unit(to_unit, definitions, quantity_name)

    if isinstance(value, bool) or not isinstance(value, (Decimal, Real)):
        raise TypeError("Unit conversion value must be an int, float, or Decimal.")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Unit conversion value must be finite.")
    elif not math.isfinite(float(value)):
        raise ValueError("Unit conversion value must be finite.")

    if isinstance(value, Decimal):
        return (value * definitions[source]) / definitions[destination]
    factor = definitions[source] / definitions[destination]
    return float(value) * float(factor)


def convert_length(value, from_unit, to_unit):
    """Convert a numeric length; Decimal input produces Decimal output."""
    return _convert(value, from_unit, to_unit, LENGTH_UNITS, "length")


def convert_mass(value, from_unit, to_unit):
    """Convert a numeric mass; Decimal input produces Decimal output."""
    return _convert(value, from_unit, to_unit, MASS_UNITS, "mass")


def kg_to_g(value):
    """Explicit high-risk boundary helper for catalogue kg to gram tools."""
    return convert_mass(value, "kg", "g")


def g_to_kg(value):
    """Explicit high-risk boundary helper for gram tools to logistics kg."""
    return convert_mass(value, "g", "kg")
