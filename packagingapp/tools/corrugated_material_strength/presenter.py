"""Presentation adapter for canonical Corrugated calculation results."""

from ...units import (
    LENGTH_UNITS,
    MASS_UNITS,
    format_dimensions,
    format_length,
    format_mass,
    normalize_unit,
)


def _units(inputs):
    data = inputs or {}
    return {
        "box_dimension": normalize_unit(
            data.get("box_dimension_unit"), LENGTH_UNITS, "mm"
        ),
        "product_mass": normalize_unit(
            data.get("product_mass_unit"), MASS_UNITS, "g"
        ),
        "pallet_dimension": normalize_unit(
            data.get("pallet_dimension_unit"), LENGTH_UNITS, "mm"
        ),
        "pallet_mass": normalize_unit(
            data.get("pallet_mass_unit"), MASS_UNITS, "kg"
        ),
        "material_dimension": normalize_unit(
            data.get("material_dimension_unit"), LENGTH_UNITS, "mm"
        ),
    }


def _display_explanation(result, units):
    geometry = result.get("box_geometry") or {}
    dimensions = result.get("dimensions") or {}
    lines = []
    if dimensions.get("external_dimensions_available"):
        caliper = dimensions.get("caliper_used_mm")
        for label, internal_key, external_key in (
            ("length", "internal_length_mm", "external_length_mm"),
            ("width", "internal_width_mm", "external_width_mm"),
            ("height", "internal_height_mm", "external_height_mm"),
        ):
            lines.append(
                f"External {label} = "
                f"{format_length(dimensions.get(internal_key), display_unit=units['box_dimension'])} "
                f"+ 2 × {format_length(caliper, display_unit=units['material_dimension'])} "
                f"= {format_length(dimensions.get(external_key), display_unit=units['box_dimension'])}"
            )
    else:
        lines.append(
            "External dimensions unavailable: enter actual caliper or select a "
            "reference grade containing caliper."
        )
    lines.extend([
        f"Blank size = {format_dimensions(geometry.get('blank_length_mm'), geometry.get('blank_width_mm'), display_unit=units['box_dimension'])}",
        f"Required sheet size = {format_dimensions(geometry.get('production_sheet_length_mm'), geometry.get('production_sheet_width_mm'), display_unit=units['box_dimension'])}",
    ])
    pallet = result.get("pallet") or {}
    if pallet.get("boxes_per_layer") is not None:
        lines.append(
            "Boxes per layer use external footprint "
            f"{format_dimensions(pallet.get('box_length_used_mm'), pallet.get('box_width_used_mm'), display_unit=units['pallet_dimension'])}; "
            f"selected count = {pallet.get('boxes_per_layer')}."
        )
    strength = result.get("strength") or {}
    if strength.get("required_bct_n") is not None:
        lines.append(
            "Required BCT remains on the specialist force contract: "
            f"{strength.get('required_bct_n')} N."
        )
    return lines


def present_corrugated_result(result, inputs):
    """Attach display strings while preserving every canonical result field."""
    canonical = dict(result or {})
    units = _units(inputs)
    dimensions = canonical.get("dimensions") or {}
    geometry = canonical.get("box_geometry") or {}
    material = canonical.get("material") or {}
    pallet = canonical.get("pallet") or {}
    capacity = (canonical.get("strength") or {}).get("compression_capacity") or {}

    display = {
        "units": units,
        "internal_dimensions": format_dimensions(
            dimensions.get("internal_length_mm"),
            dimensions.get("internal_width_mm"),
            dimensions.get("internal_height_mm"),
            display_unit=units["box_dimension"],
        ),
        "external_dimensions": (
            format_dimensions(
                dimensions.get("external_length_mm"),
                dimensions.get("external_width_mm"),
                dimensions.get("external_height_mm"),
                display_unit=units["box_dimension"],
            )
            if dimensions.get("external_dimensions_available")
            else "External dimensions unavailable"
        ),
        "caliper_used": format_length(
            dimensions.get("caliper_used_mm"),
            display_unit=units["material_dimension"],
        ),
        "blank_dimensions": format_dimensions(
            geometry.get("blank_length_mm"),
            geometry.get("blank_width_mm"),
            display_unit=units["box_dimension"],
        ),
        "production_sheet_dimensions": format_dimensions(
            geometry.get("production_sheet_length_mm"),
            geometry.get("production_sheet_width_mm"),
            display_unit=units["box_dimension"],
        ),
        "finished_box_weight": format_mass(
            material.get("finished_box_weight_g"),
            canonical_unit="g",
            display_unit=units["product_mass"],
        ),
        "blank_bounding_weight": format_mass(
            material.get("blank_bounding_weight_g"),
            canonical_unit="g",
            display_unit=units["product_mass"],
        ),
        "production_sheet_weight": format_mass(
            material.get("production_sheet_weight_g"),
            canonical_unit="g",
            display_unit=units["product_mass"],
        ),
        "cutting_scrap_weight": format_mass(
            material.get("cutting_scrap_weight_g"),
            canonical_unit="g",
            display_unit=units["product_mass"],
        ),
        "gross_packed_box_weight": format_mass(
            material.get("gross_packed_box_weight_g"),
            canonical_unit="g",
            display_unit=units["product_mass"],
        ),
        "pallet_dimensions": format_dimensions(
            pallet.get("pallet_length_mm"),
            pallet.get("pallet_width_mm"),
            pallet.get("pallet_height_mm"),
            display_unit=units["pallet_dimension"],
        ),
        "pallet_box_dimensions": format_dimensions(
            pallet.get("box_length_used_mm"),
            pallet.get("box_width_used_mm"),
            pallet.get("box_height_used_mm"),
            display_unit=units["pallet_dimension"],
        ),
        "palletized_height": format_length(
            pallet.get("palletized_height_mm"),
            display_unit=units["pallet_dimension"],
        ),
        "supported_mass": format_mass(
            pallet.get("supported_mass_kg"),
            canonical_unit="kg",
            display_unit=units["pallet_mass"],
        ),
        "allowable_supported_mass": format_mass(
            capacity.get("allowable_supported_mass_kg"),
            canonical_unit="kg",
            display_unit=units["pallet_mass"],
        ),
        "current_supported_mass": format_mass(
            capacity.get("current_supported_mass_kg"),
            canonical_unit="kg",
            display_unit=units["pallet_mass"],
        ),
        "remaining_supported_mass": format_mass(
            capacity.get("remaining_supported_mass_kg"),
            canonical_unit="kg",
            display_unit=units["pallet_mass"],
        ),
        "overload_mass": format_mass(
            capacity.get("overload_mass_kg"),
            canonical_unit="kg",
            display_unit=units["pallet_mass"],
        ),
    }
    display["explanation"] = _display_explanation(canonical, units)
    canonical["display"] = display
    return canonical
