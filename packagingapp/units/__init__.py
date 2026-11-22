"""Shared physical-unit definitions and conversion helpers."""

from .conversion import (
    UnsupportedUnitError,
    convert_film_thickness,
    convert_length,
    convert_mass,
    g_to_kg,
    kg_to_g,
    normalize_unit,
)
from .definitions import (
    FILM_THICKNESS_UNIT_OPTIONS,
    LENGTH_UNITS,
    LENGTH_UNIT_OPTIONS,
    MASS_UNITS,
    MASS_UNIT_OPTIONS,
)
from .formatting import format_dimensions, format_length, format_mass, format_number

__all__ = [
    "FILM_THICKNESS_UNIT_OPTIONS",
    "LENGTH_UNITS",
    "LENGTH_UNIT_OPTIONS",
    "MASS_UNITS",
    "MASS_UNIT_OPTIONS",
    "UnsupportedUnitError",
    "convert_length",
    "convert_film_thickness",
    "convert_mass",
    "format_dimensions",
    "format_length",
    "format_mass",
    "format_number",
    "g_to_kg",
    "kg_to_g",
    "normalize_unit",
]
