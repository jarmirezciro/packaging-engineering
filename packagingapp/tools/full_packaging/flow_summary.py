"""Presentation model for the compact Packaging Flow quantity summary.

The workflow engines already expose two authoritative quantity fields on their
JSON-safe chaining payloads:

* ``units_per_parent``: immediate units loaded in the current package;
* ``total_base_units``: cumulative base units represented by that package.

This module does not run or duplicate any packaging calculation. It only turns
the active workflow payloads into display-ready labels and validates the
step-by-step multiplication used by the summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class UnitDefinition:
    key: str
    singular: str
    plural: str


BASE_PRODUCT = UnitDefinition("base_product", "base product", "base products")

STEP_DEFINITIONS = {
    "container": {
        "title": "Box",
        "icon": "bi-box-seam",
        "unit": UnitDefinition("box", "box", "boxes"),
    },
    "bag": {
        "title": "Bag",
        "icon": "bi-handbag",
        "unit": UnitDefinition("bag", "bag", "bags"),
    },
    "pallet": {
        "title": "Pallet",
        "icon": "bi-boxes",
        "unit": UnitDefinition("pallet", "pallet", "pallets"),
    },
    "transport": {
        "title": "Transport container",
        "icon": "bi-truck",
        "unit": UnitDefinition(
            "transport_container",
            "transport container",
            "transport containers",
        ),
    },
}


def _positive_decimal(value: Any) -> Decimal | None:
    if value in (None, "", "None"):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number > 0 else None


def _format_quantity(value: Decimal) -> str:
    integral = value.to_integral_value()
    if value == integral:
        return f"{int(integral):,}"
    return f"{value.normalize():,f}".rstrip("0").rstrip(".")


def _unit_label(unit: UnitDefinition, quantity: Decimal) -> str:
    return unit.singular if quantity == 1 else unit.plural


def _active_payload(step: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Mirror Packaging Flow's existing effective-output preference."""
    pending = step.get("pending_result")
    if isinstance(pending, Mapping):
        return pending
    selected = step.get("selected")
    if isinstance(selected, Mapping):
        return selected
    return None


def _secondary_line(unit: UnitDefinition, quantity: Decimal, output: UnitDefinition) -> dict[str, Any]:
    return {
        "value": _format_quantity(quantity),
        "label": f"{_unit_label(unit, quantity)} / {output.singular}",
        "is_base_total": unit.key == BASE_PRODUCT.key,
    }


def build_packaging_flow_summary(steps: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a JSON-safe display model for the top-of-flow summary.

    The chain fails closed after the first incomplete or inconsistent stage.
    This prevents a later result from being multiplied onto an unknown earlier
    quantity. Existing completed stages remain visible as a progressive summary.
    """

    stages: list[dict[str, Any]] = []
    current_unit = BASE_PRODUCT
    chain_available = True

    # Counts represented by one current unit, ordered from base product to the
    # current package. Example after palletization:
    # [(base product, 3000), (box, 60), (pallet, 1)].
    contained_counts: list[tuple[UnitDefinition, Decimal]] = [(BASE_PRODUCT, Decimal(1))]

    for raw_step in steps:
        if not isinstance(raw_step, Mapping):
            continue
        definition = STEP_DEFINITIONS.get(str(raw_step.get("type") or ""))
        if definition is None:
            continue

        output_unit: UnitDefinition = definition["unit"]
        payload = _active_payload(raw_step)
        units_per_output = _positive_decimal((payload or {}).get("units_per_parent"))
        reported_total = _positive_decimal((payload or {}).get("total_base_units"))

        can_calculate = chain_available and units_per_output is not None
        if not can_calculate:
            stages.append({
                "title": definition["title"],
                "icon": definition["icon"],
                "completed": False,
                "status": "Not calculated",
                "output_unit": output_unit.singular,
            })
            chain_available = False
            continue

        multiplied_counts = [
            (unit, quantity * units_per_output)
            for unit, quantity in contained_counts
        ]
        calculated_total = multiplied_counts[0][1]

        # The payload total is produced by the existing workflow chaining
        # contract. A disagreement means that this display chain is incomplete
        # or stale, so do not present a potentially false cumulative result.
        if reported_total is not None and reported_total != calculated_total:
            stages.append({
                "title": definition["title"],
                "icon": definition["icon"],
                "completed": False,
                "status": "Quantity chain unavailable",
                "output_unit": output_unit.singular,
            })
            chain_available = False
            continue

        secondary = [
            _secondary_line(unit, quantity, output_unit)
            for unit, quantity in reversed(multiplied_counts[:-1])
        ]

        stages.append({
            "title": definition["title"],
            "icon": definition["icon"],
            "completed": True,
            "output_unit": output_unit.singular,
            "primary_value": _format_quantity(units_per_output),
            "primary_label": f"{_unit_label(current_unit, units_per_output)} / {output_unit.singular}",
            "secondary": secondary,
        })

        contained_counts = multiplied_counts + [(output_unit, Decimal(1))]
        current_unit = output_unit

    completed_stages = [stage for stage in stages if stage.get("completed")]
    final = None
    if completed_stages and contained_counts:
        base_total = contained_counts[0][1]
        intermediate_details = [
            f"{_format_quantity(quantity)} {_unit_label(unit, quantity)}"
            for unit, quantity in contained_counts[1:-1]
        ]
        final = {
            "title": f"Final capacity per {current_unit.singular}",
            "value": _format_quantity(base_total),
            "label": f"{_unit_label(BASE_PRODUCT, base_total)} / {current_unit.singular}",
            "details": " · ".join(intermediate_details),
        }

    return {
        "has_steps": bool(stages),
        "stages": stages,
        "final": final,
        "completed_count": len(completed_stages),
        "is_complete": bool(stages) and len(completed_stages) == len(stages),
    }
