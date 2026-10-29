"""Shared helpers for validating and normalizing manual form quantities."""

from .conversion import UnsupportedUnitError


def validate_unit(unit, definitions, default, label):
    token = default if unit in (None, "") else str(unit).strip().lower()
    if token not in definitions:
        raise UnsupportedUnitError(
            f"Unsupported {label} unit {unit!r}. "
            f"Use one of: {', '.join(definitions)}."
        )
    return token


def convert_optional(value, unit, converter, canonical_unit):
    if value in (None, "", "None"):
        return None
    return float(converter(float(value), unit, canonical_unit))
