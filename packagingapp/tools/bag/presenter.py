from decimal import Decimal, DecimalException

from ...units import convert_film_thickness, convert_length, convert_mass, format_dimensions, format_mass, format_number
from .film import (
    FILM_PRESET_CHOICES, FILM_SOURCES, FILM_UNITS, bag_weight_overridden,
    catalogue_bag_mode, film_flag, resolve_bag_film,
)
from .state import resolve_bag_design_rotations


def format_design_bag_dimensions(candidate, display_unit):
    return format_dimensions(
        candidate["bag_length"], candidate["bag_width"], display_unit=display_unit,
    )


def bag_rotation_options(config, selected_product, names):
    return [
        {"code": f"R{index}", "axis": axis, "name": names[f"r{index}"], "checked": checked}
        for index, (axis, checked) in enumerate(
            zip(("Length", "Width", "Height"), resolve_bag_design_rotations(config, selected_product)), start=1
        )
    ]


def bag_film_result_rows(report, *, separate_weight_source=False):
    if not report or "bag_tare_source" not in report:
        return []
    rows = []
    family = report.get("film_material_family")
    if family:
        rows.append(("Film material", "Custom" if family == "custom" else family.upper()))
    caliper = report.get("film_caliper_mm")
    if caliper is not None:
        microns = convert_film_thickness(Decimal(str(caliper)), "mm", "um")
        mil = convert_film_thickness(Decimal(str(caliper)), "mm", "mil")
        rows.append(("Caliper", f"{format_number(mil)} mil ({format_number(microns)} µm)"))
    grammage = report.get("film_grammage_g_m2")
    if grammage is not None:
        rows.append(("Grammage", f"{format_number(grammage, max_decimal_places=2)} g/m²"))
    area = report.get("film_area_m2")
    if area is not None:
        rows.append(("Estimated film area", f"{area * 10000:.2f} cm²"))
    weight = report["bag_tare_display"]
    source = report["bag_tare_source_display"]
    if separate_weight_source:
        rows.extend([("Packaging weight", weight), ("Packaging weight source", source)])
    else:
        rows.append(("Packaging weight", f"{weight} · {source}"))
    return rows


def bag_workflow_dimension_rows(report, unit):
    if not report or not report.get("outer_dimension_source"):
        return []
    rows = [
        ("Flat bag dimensions", format_dimensions(
            report["flat_bag_length_mm"], report["flat_bag_width_mm"], display_unit=unit
        )),
    ]
    bundle = tuple(report.get(f"bundle_{axis}_mm") for axis in ("length", "width", "height"))
    if all(value is not None for value in bundle):
        rows.append(("Packed bundle dimensions", format_dimensions(*bundle, display_unit=unit)))
    outer = tuple(report.get(f"external_{axis}_mm") for axis in ("length", "width", "height"))
    if all(value is not None for value in outer):
        rows.append(("Outer dimensions", format_dimensions(*outer, display_unit=unit)))
    rows.append(("Outer dimensions source", report["outer_dimension_source_display"]))
    return rows


def build_bag_film_context(config, material=None, *, design_dimensions=None):
    catalogue = catalogue_bag_mode(config)
    preset_override = film_flag(config["film_preset_override"])
    preset = config["film_preset"] if not catalogue or preset_override else "catalogue"
    caliper_override = film_flag(config["film_caliper_override"])
    grammage_override = film_flag(config["film_grammage_override"])
    weight_override = bag_weight_overridden(config)
    inputs = {"caliper": "", "grammage": "", "tare": ""}
    sources = dict.fromkeys(inputs, FILM_SOURCES["unavailable"])
    density = ""
    unit = config["film_caliper_unit"]

    try:
        if config["mode"] == "design":
            flat = design_dimensions
        elif catalogue:
            flat = (material.part_length, material.part_width) if material else None
        else:
            length_unit = config["bag_dimension_unit"]
            flat = tuple(
                convert_length(Decimal(config[key]), length_unit, "mm") if config[key] else None
                for key in ("bag_length", "bag_width")
            )
        film = resolve_bag_film(config, flat, material)
        if film["film_caliper_mm"] is not None:
            value = convert_film_thickness(Decimal(str(film["film_caliper_mm"])), "mm", unit)
            inputs["caliper"] = format_number(value, max_decimal_places=8)
        if film["film_grammage_g_m2"] is not None:
            inputs["grammage"] = f"{film['film_grammage_g_m2']:.2f}"
        if film["bag_tare_g"] is not None:
            mass_unit = config["bag_mass_unit"]
            value = convert_mass(film["bag_tare_g"], "g", mass_unit)
            inputs["tare"] = f"{value:.3f}" if mass_unit == "g" else format_number(value, max_decimal_places=8)
        sources.update({
            "caliper": FILM_SOURCES[film["film_caliper_source"]],
            "grammage": FILM_SOURCES[film["film_grammage_source"]],
            "tare": film["bag_tare_source_display"],
        })
        if film["film_density_g_cm3"] is not None:
            density = f"{film['film_material_family'].upper()} density assumption {film['film_density_g_cm3']:.3f} g/cm³"
    except (DecimalException, ValueError):
        # Preserve editable values while an entry is incomplete or invalid.
        pass

    if caliper_override or preset == "custom":
        inputs["caliper"] = config["film_caliper"]
    if grammage_override or preset == "custom":
        inputs["grammage"] = config["film_grammage"]
    if weight_override:
        inputs["tare"] = config["bag_weight"]
    return {
        "open": film_flag(config["bag_advanced_open"]),
        "catalogue": catalogue,
        "preset": preset,
        "preset_choices": FILM_PRESET_CHOICES,
        "inputs": inputs,
        "sources": sources,
        "density": density,
        "unit": unit if unit in FILM_UNITS else "mil",
        "preset_override": preset_override,
        "caliper_override": caliper_override,
        "grammage_override": grammage_override,
        "weight_override": weight_override,
    }


def bag_allowance_rows(assumptions):
    if not assumptions:
        return []
    return [
        ("Sealing allowance", assumptions["sealing_allowance_display"]),
        ("Fit tolerance", assumptions["fit_tolerance_display"]),
    ]


def _read_value(data, key, default=""):
    if isinstance(data, dict):
        return data.get(key, default)

    if hasattr(data, "cleaned_data") and isinstance(getattr(data, "cleaned_data", None), dict):
        cleaned = data.cleaned_data
        if key in cleaned:
            return cleaned.get(key, default)

    try:
        bound = data[key]
        if hasattr(bound, "value"):
            return bound.value()
    except Exception:
        pass

    return getattr(data, key, default)


def selected_product_summary(selected_product, data, mode="single"):
    dimension_unit = _read_value(data, "product_dimension_unit", "mm") or "mm"
    mass_unit = _read_value(data, "product_mass_unit", "g") or "g"
    if selected_product:
        title = selected_product.product_id or "Selected product"
        if selected_product.product_name:
            title = f"{title} — {selected_product.product_name}"

        meta_parts = []
        weight = getattr(selected_product, "weight", None)
        if weight not in (None, "", "None"):
            meta_parts.append(
                "Wt: " + format_mass(weight, canonical_unit="kg", display_unit=mass_unit)
            )

        if mode == "optimal":
            qty = getattr(selected_product, "desired_qty", None)
            if qty not in (None, "", "None"):
                meta_parts.append(f"Desired Qty: {qty}")

        return {
            "title": title,
            "dims": format_dimensions(
                selected_product.product_length,
                selected_product.product_width,
                selected_product.product_height,
                display_unit=dimension_unit,
            ),
            "meta": " | ".join(meta_parts),
        }

    qty = _read_value(data, "desired_qty", "")
    weight = _read_value(data, "product_weight", "")
    meta = []
    if weight not in (None, "", "None"):
        meta.append(f"Wt: {weight} {mass_unit}")
    if mode == "optimal" and qty not in (None, "", "None"):
        meta.append(f"Target Qty: {qty}")

    return {
        "title": "Manual product",
        "dims": f'{_read_value(data, "product_l", "")} × {_read_value(data, "product_w", "")} × {_read_value(data, "product_h", "")} {dimension_unit}',
        "meta": " | ".join(meta),
    }


def selected_bag_summary(selected_material, data):
    dimension_unit = _read_value(data, "bag_dimension_unit", "mm") or "mm"
    if selected_material:
        meta_parts = []
        if getattr(selected_material, "packaging_type", None):
            meta_parts.append(str(selected_material.packaging_type))
        if getattr(selected_material, "branding", None):
            meta_parts.append(str(selected_material.branding))

        return {
            "title": f"{selected_material.part_number} — {selected_material.part_description}",
            "dims": format_dimensions(
                selected_material.part_length,
                selected_material.part_width,
                display_unit=dimension_unit,
            ),
            "meta": " | ".join(meta_parts),
        }

    return {
        "title": "Manual bag",
        "dims": f'{_read_value(data, "bag_length", "")} × {_read_value(data, "bag_width", "")} {dimension_unit}',
        "meta": "Manual dimensions",
    }
