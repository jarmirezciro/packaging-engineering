from decimal import Decimal

from ...units import (
    format_dimensions,
    format_mass,
)
from ...units.ui import build_unit_selector_contract


def build_transport_ui_contract(prefix=""):
    """Return prefix-safe field and shared unit-selector metadata."""
    suffix = f"_{prefix}" if prefix != "" else ""
    names = {
        "load_unit_dimension_unit": f"load_unit_dimension_unit{suffix}",
        "load_unit_mass_unit": f"load_unit_mass_unit{suffix}",
        "transport_dimension_unit": f"transport_dimension_unit{suffix}",
        "transport_mass_unit": f"transport_mass_unit{suffix}",
    }
    return {
        "prefix": prefix,
        "names": names,
        "unit_selectors": {
            "load_unit_dimensions": build_unit_selector_contract(
                quantity="length",
                label="load-unit dimension",
                group=f"transport-load-unit-dimensions{suffix}",
                hidden_name=names["load_unit_dimension_unit"],
                hidden_id=f"transportLoadUnitDimensionUnit{suffix}",
                menu_id=f"transportLoadUnitDimensionUnitMenu{suffix}",
            ),
            "load_unit_mass": build_unit_selector_contract(
                quantity="mass",
                label="load-unit mass",
                group=f"transport-load-unit-mass{suffix}",
                hidden_name=names["load_unit_mass_unit"],
                hidden_id=f"transportLoadUnitMassUnit{suffix}",
                menu_id=f"transportLoadUnitMassUnitMenu{suffix}",
            ),
            "transport_dimensions": build_unit_selector_contract(
                quantity="length",
                label="transport-unit dimension",
                group=f"transport-container-dimensions{suffix}",
                hidden_name=names["transport_dimension_unit"],
                hidden_id=f"transportDimensionUnit{suffix}",
                menu_id=f"transportDimensionUnitMenu{suffix}",
            ),
            "transport_mass": build_unit_selector_contract(
                quantity="mass",
                label="transport-unit mass",
                group=f"transport-container-mass{suffix}",
                hidden_name=names["transport_mass_unit"],
                hidden_id=f"transportMassUnit{suffix}",
                menu_id=f"transportMassUnitMenu{suffix}",
            ),
        },
    }


def _normalize_value(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return float(value)
    return value


def _read_value(data, key, default=""):
    """
    Supports:
    - dict payloads
    - Django forms with cleaned_data
    - bound fields via form["field"].value()
    - simple attribute access
    """
    if isinstance(data, dict):
        return _normalize_value(data.get(key, default))

    if hasattr(data, "cleaned_data") and isinstance(getattr(data, "cleaned_data", None), dict):
        cleaned = data.cleaned_data
        if key in cleaned:
            return _normalize_value(cleaned.get(key, default))

    try:
        bound = data[key]
        if hasattr(bound, "value"):
            return _normalize_value(bound.value())
    except Exception:
        pass

    return _normalize_value(getattr(data, key, default))


def _display_value(value, empty="Not set"):
    return value if value not in (None, "") else empty


def selected_container_summary(selected_material, data):
    """
    Summary for the transport container card.
    Works with both:
    - standalone form object
    - workflow config dict
    """
    max_weight = _read_value(data, "max_weight", "")
    tare_weight = _read_value(data, "tare_weight", "")
    container_l = _read_value(data, "container_l", "")
    container_w = _read_value(data, "container_w", "")
    container_h = _read_value(data, "container_h", "")

    if selected_material:
        tare_display = tare_weight
        if tare_display in (None, ""):
            tare_display = getattr(selected_material, "part_weight", "")
        return {
            "title": f"{getattr(selected_material, 'part_number', '')} — {getattr(selected_material, 'part_description', '')}",
            "dims": format_dimensions(
                getattr(selected_material, "part_length", None),
                getattr(selected_material, "part_width", None),
                getattr(selected_material, "part_height", None),
                display_unit=_read_value(data, "transport_dimension_unit", "mm") or "mm",
            ),
            "meta": f"{getattr(selected_material, 'packaging_type', '')} | {getattr(selected_material, 'branding', '')}",
            "max_weight": (
                f"{_display_value(max_weight)} {_read_value(data, 'transport_mass_unit', 'kg') or 'kg'}"
                if max_weight not in (None, "") else "Not set"
            ),
            "tare_weight": format_mass(
                tare_display,
                canonical_unit="kg",
                display_unit=_read_value(data, "transport_mass_unit", "kg") or "kg",
            ),
        }

    dimension_unit = _read_value(data, "transport_dimension_unit", "mm") or "mm"
    mass_unit = _read_value(data, "transport_mass_unit", "kg") or "kg"

    return {
        "title": "Manual transport unit",
        "dims": (
            f"{container_l} × {container_w} × {container_h} {dimension_unit}"
        ),
        "meta": "Manual internal loading dimensions",
        "max_weight": (
            f"{_display_value(max_weight)} {mass_unit}"
            if max_weight not in (None, "") else "Not set"
        ),
        "tare_weight": (
            f"{_display_value(tare_weight)} {mass_unit}"
            if tare_weight not in (None, "") else "Not set"
        ),
    }


def attach_transport_result_presentation(serialized_result, config):
    """Attach display-only values to the canonical Transport serialization."""
    result = serialized_result or {}
    config = config or {}
    load_dimension_unit = config.get("load_unit_dimension_unit") or "mm"
    load_mass_unit = config.get("load_unit_mass_unit") or "kg"
    transport_dimension_unit = config.get("transport_dimension_unit") or "mm"
    transport_mass_unit = config.get("transport_mass_unit") or "kg"
    summary = result.get("summary") or {}

    for row in summary.get("product_rows") or []:
        row["dimensions_display"] = format_dimensions(
            row.get("length"),
            row.get("width"),
            row.get("height"),
            display_unit=load_dimension_unit,
        )
        row["weight_each_display"] = format_mass(
            row.get("weight_each"),
            canonical_unit="kg",
            display_unit=load_mass_unit,
        )

    result["display"] = {
        "units": {
            "load_dimension": load_dimension_unit,
            "load_mass": load_mass_unit,
            "transport_dimension": transport_dimension_unit,
            "transport_mass": transport_mass_unit,
        },
        "loaded_weight": format_mass(
            summary.get("loaded_weight"),
            canonical_unit="kg",
            display_unit=transport_mass_unit,
        ),
        "tare_weight": format_mass(
            summary.get("tare_weight"),
            canonical_unit="kg",
            display_unit=transport_mass_unit,
        ),
        "gross_weight": format_mass(
            summary.get("gross_weight"),
            canonical_unit="kg",
            display_unit=transport_mass_unit,
        ),
        "max_payload": format_mass(
            summary.get("container_max_weight"),
            canonical_unit="kg",
            display_unit=transport_mass_unit,
        ),
        "occupied_dimensions": format_dimensions(
            summary.get("occupied_length"),
            summary.get("occupied_width"),
            summary.get("occupied_height"),
            display_unit=transport_dimension_unit,
        ),
        "residual_dimensions": format_dimensions(
            summary.get("residual_length"),
            summary.get("residual_width"),
            summary.get("residual_height"),
            display_unit=transport_dimension_unit,
        ),
    }

    scene = result.get("threejs_scene") or {}
    products = scene.get("products") or []
    rows = summary.get("product_rows") or []
    for product, row in zip(products, rows):
        product["display_dimensions"] = row.get("dimensions_display")
    return result


def build_transport_pending_result(container, analysis_result, selected_material=None, upstream_units=1):
    """
    Build JSON-safe workflow chaining payload from transport result.
    """
    summary = (analysis_result or {}).get("summary", {}) or {}
    placed_units = int(summary.get("placed_units", 0) or 0)

    if selected_material:
        label = getattr(selected_material, "part_number", "") or "Selected Container"
    else:
        label = "Manual Container"

    return {
        "label": label,
        "length": round(float(container["L"]), 2),
        "width": round(float(container["W"]), 2),
        "height": round(float(container["H"]), 2),
        "units_per_parent": placed_units,
        "total_base_units": placed_units * int(upstream_units or 1),
    }
