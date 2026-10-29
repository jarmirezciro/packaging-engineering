"""Shared physical-unit definitions and conversion helpers."""

from .conversion import (
    UnsupportedUnitError,
    convert_length,
    convert_mass,
    g_to_kg,
    kg_to_g,
    normalize_unit,
)
from .definitions import (
    LENGTH_UNITS,
    LENGTH_UNIT_OPTIONS,
    MASS_UNITS,
    MASS_UNIT_OPTIONS,
)
from .formatting import format_dimensions, format_length, format_mass, format_number

__all__ = [
    "LENGTH_UNITS",
    "LENGTH_UNIT_OPTIONS",
    "MASS_UNITS",
    "MASS_UNIT_OPTIONS",
    "UnsupportedUnitError",
    "convert_length",
    "convert_mass",
    "format_dimensions",
    "format_length",
    "format_mass",
    "format_number",
    "g_to_kg",
    "kg_to_g",
    "normalize_unit",
]
