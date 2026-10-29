"""Display-only physical-unit helpers for Packaging Flow.

Workflow chaining payloads remain canonical millimetres and kilograms.  These
helpers add strings for the unit context selected by each consuming step; they
never mutate the stored payload or feed converted values back into an engine.
"""

from __future__ import annotations

from typing import Any, Mapping

from ...units import format_dimensions, format_mass, normalize_unit
from ...units.definitions import LENGTH_UNITS, MASS_UNITS


STEP_UNIT_KEYS = {
    "container": {
        "input_dimension": ("product_dimension_unit", "mm"),
        "input_mass": ("product_mass_unit", "g"),
        "output_dimension": ("container_dimension_unit", "mm"),
        "output_mass": ("container_mass_unit", "g"),
    },
    "bag": {
        "input_dimension": ("product_dimension_unit", "mm"),
        "input_mass": ("product_mass_unit", "g"),
        "output_dimension": ("bag_dimension_unit", "mm"),
        "output_mass": ("bag_mass_unit", "g"),
    },
    "pallet": {
        "input_dimension": ("box_dimension_unit", "mm"),
        "input_mass": ("mass_unit", "g"),
        "output_dimension": ("pallet_dimension_unit", "mm"),
        "output_mass": ("mass_unit", "g"),
    },
    "transport": {
        "input_dimension": ("load_unit_dimension_unit", "mm"),
        "input_mass": ("load_unit_mass_unit", "kg"),
        "output_dimension": ("transport_dimension_unit", "mm"),
        "output_mass": ("transport_mass_unit", "kg"),
    },
}


def step_display_units(step: Mapping[str, Any] | None) -> dict[str, str]:
    step = step or {}
    config = step.get("config") if isinstance(step.get("config"), Mapping) else {}
    keys = STEP_UNIT_KEYS.get(str(step.get("type") or "container"), STEP_UNIT_KEYS["container"])
    units: dict[str, str] = {}
    for role, (key, default) in keys.items():
        definitions = MASS_UNITS if role.endswith("mass") else LENGTH_UNITS
        units[role] = normalize_unit(config.get(key), definitions, default)
    return units


def payload_for_display(
    payload: Mapping[str, Any] | None,
    *,
    dimension_unit: str,
    mass_unit: str,
) -> dict[str, Any] | None:
    """Return a shallow display copy of one canonical workflow payload."""
    if not isinstance(payload, Mapping):
        return None

    display = dict(payload)
    dimensions = (payload.get("length"), payload.get("width"), payload.get("height"))
    if all(value not in (None, "", "None") for value in dimensions):
        display["dimensions_display"] = format_dimensions(
            *dimensions,
            canonical_unit="mm",
            display_unit=dimension_unit,
        )

    weight_kg = payload.get("weight_kg")
    if weight_kg not in (None, "", "None"):
        display["weight_display"] = format_mass(
            weight_kg,
            canonical_unit="kg",
            display_unit=mass_unit,
        )
    else:
        weight_g = payload.get("weight_g")
        if weight_g not in (None, "", "None"):
            display["weight_display"] = format_mass(
                weight_g,
                canonical_unit="g",
                display_unit=mass_unit,
            )
    return display


def physical_summary(payload: Mapping[str, Any] | None) -> str:
    """Join already-presented dimensions and mass for compact UI summaries."""
    if not payload:
        return ""
    parts = [
        payload.get("dimensions_display"),
        payload.get("weight_display"),
    ]
    return " · ".join(str(value) for value in parts if value not in (None, "", "—"))
