"""Presentation-only formatting for canonical physical values.

The helpers in this module never change an engine or storage payload.  They
convert one canonical numeric value into a readable string for a web page or
report and keep the selected unit explicit in the returned text.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .conversion import convert_length, convert_mass, normalize_unit
from .definitions import LENGTH_UNITS, MASS_UNITS


def _decimal(value):
    if value in (None, "", "None"):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Physical display values must be numeric.") from exc
    if not number.is_finite():
        raise ValueError("Physical display values must be finite.")
    return number


def format_number(value, *, max_decimal_places=3):
    """Return a compact decimal string without altering the source value."""
    number = _decimal(value)
    if number is None:
        return "—"
    quantum = Decimal("1").scaleb(-int(max_decimal_places))
    rounded = number.quantize(quantum, rounding=ROUND_HALF_UP)
    text = format(rounded, "f").rstrip("0").rstrip(".")
    return text or "0"


def _format_physical_value(
    value,
    *,
    canonical_unit,
    display_unit,
    definitions,
    converter,
    default_unit,
    max_decimal_places=3,
):
    number = _decimal(value)
    target = normalize_unit(display_unit, definitions, default_unit)
    if number is None:
        return "—"
    converted = converter(number, canonical_unit, target)
    return f"{format_number(converted, max_decimal_places=max_decimal_places)} {target}"


def format_length(
    value,
    *,
    canonical_unit="mm",
    display_unit="mm",
    max_decimal_places=3,
):
    return _format_physical_value(
        value,
        canonical_unit=canonical_unit,
        display_unit=display_unit,
        definitions=LENGTH_UNITS,
        converter=convert_length,
        default_unit="mm",
        max_decimal_places=max_decimal_places,
    )


def format_mass(
    value,
    *,
    canonical_unit="g",
    display_unit="g",
    max_decimal_places=3,
):
    return _format_physical_value(
        value,
        canonical_unit=canonical_unit,
        display_unit=display_unit,
        definitions=MASS_UNITS,
        converter=convert_mass,
        default_unit="g",
        max_decimal_places=max_decimal_places,
    )


def format_dimensions(
    *values,
    canonical_unit="mm",
    display_unit="mm",
    max_decimal_places=3,
):
    """Format two or three canonical dimensions with one coherent unit."""
    target = normalize_unit(display_unit, LENGTH_UNITS, "mm")
    converted = []
    for value in values:
        number = _decimal(value)
        if number is None:
            return "—"
        converted.append(
            format_number(
                convert_length(number, canonical_unit, target),
                max_decimal_places=max_decimal_places,
            )
        )
    return f"{' × '.join(converted)} {target}"
