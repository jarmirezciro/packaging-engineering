"""Central unit definitions expressed against canonical metric base units."""

from decimal import Decimal
from types import MappingProxyType

from .constants import (
    G_PER_KG,
    G_PER_LB,
    G_PER_OZ,
    G_PER_TONNE,
    MM_PER_CM,
    MM_PER_FT,
    MM_PER_IN,
    MM_PER_M,
)


LENGTH_UNITS = MappingProxyType({
    "mm": Decimal("1"),
    "cm": MM_PER_CM,
    "m": MM_PER_M,
    "in": MM_PER_IN,
    "ft": MM_PER_FT,
})

MASS_UNITS = MappingProxyType({
    "g": Decimal("1"),
    "kg": G_PER_KG,
    "t": G_PER_TONNE,
    "oz": G_PER_OZ,
    "lb": G_PER_LB,
})


# Presentation metadata for reusable manual-input selectors.  Conversion
# factors remain exclusively in LENGTH_UNITS and MASS_UNITS above.
LENGTH_UNIT_OPTIONS = (
    {"value": "mm", "label": "Millimetres", "symbol": "mm"},
    {"value": "cm", "label": "Centimetres", "symbol": "cm"},
    {"value": "m", "label": "Metres", "symbol": "m"},
    {"value": "in", "label": "Inches", "symbol": "in"},
    {"value": "ft", "label": "Feet", "symbol": "ft"},
)

MASS_UNIT_OPTIONS = (
    {"value": "g", "label": "Grams", "symbol": "g"},
    {"value": "kg", "label": "Kilograms", "symbol": "kg"},
    {"value": "t", "label": "Metric tonnes", "symbol": "t"},
    {"value": "oz", "label": "Ounces", "symbol": "oz"},
    {"value": "lb", "label": "Pounds", "symbol": "lb"},
)
