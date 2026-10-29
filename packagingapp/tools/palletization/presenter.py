from ...units import (
    LENGTH_UNIT_OPTIONS,
    MASS_UNIT_OPTIONS,
    format_dimensions,
    format_length,
    format_mass,
)


def _to_float(value, default=None):
    try:
        if value in (None, "", "None"):
            return default
        return float(value)
    except Exception:
        return default

def build_pallet_ui_contract(prefix=""):
    """Return the shared field/action contract used by every pallet surface.

    The standalone KolliPack tool, the Packaging Flow pallet step, and public
    SEO calculator all render the same palletization partials.  Keeping the
    generated names and ids here prevents any one surface from drifting away
    when the shared UI evolves.
    """
    suffix = f"_{prefix}" if prefix else ""

    names = {
        "action": f"action{suffix}",
        "selected_box_id": f"selected_box_id{suffix}",
        "pallet_id": f"pallet_id{suffix}",
        "selected_result_key": f"selected_result_key{suffix}",
        "show_advanced": f"show_advanced{suffix}",
        "box_source": f"box_source{suffix}",
        "box_catalogue_id": f"box_catalogue_id{suffix}",
        "box_l": f"box_l{suffix}",
        "box_w": f"box_w{suffix}",
        "box_h": f"box_h{suffix}",
        "box_dimension_unit": f"box_dimension_unit{suffix}",
        "box_weight": f"box_weight{suffix}",
        "max_weight_on_bottom_box": f"max_weight_on_bottom_box{suffix}",
        "mass_unit": f"mass_unit{suffix}",
        "pallet_source": f"pallet_source{suffix}",
        "pallet_catalogue_id": f"pallet_catalogue_id{suffix}",
        "pallet_l": f"pallet_l{suffix}",
        "pallet_w": f"pallet_w{suffix}",
        "pallet_height": f"pallet_height{suffix}",
        "pallet_dimension_unit": f"pallet_dimension_unit{suffix}",
        "max_stack_height": f"max_stack_height{suffix}",
        "max_width_stickout": f"max_width_stickout{suffix}",
        "max_length_stickout": f"max_length_stickout{suffix}",
    }

    unit_selectors = {
        "box_dimensions": {
            "quantity": "length",
            "label": "carton dimension",
            "group": f"pallet-box-dimensions{suffix}",
            "hidden_name": names["box_dimension_unit"],
            "hidden_id": f"boxDimensionUnit{suffix}",
            "menu_id": f"boxDimensionUnitMenu{suffix}",
            "options": LENGTH_UNIT_OPTIONS,
        },
        "pallet_dimensions": {
            "quantity": "length",
            "label": "pallet and layout dimension",
            "group": f"pallet-layout-dimensions{suffix}",
            "hidden_name": names["pallet_dimension_unit"],
            "hidden_id": f"palletDimensionUnit{suffix}",
            "menu_id": f"palletDimensionUnitMenu{suffix}",
            "options": LENGTH_UNIT_OPTIONS,
        },
        "mass": {
            "quantity": "mass",
            "label": "carton load",
            "group": f"pallet-mass{suffix}",
            "hidden_name": names["mass_unit"],
            "hidden_id": f"palletMassUnit{suffix}",
            "menu_id": f"palletMassUnitMenu{suffix}",
            "options": MASS_UNIT_OPTIONS,
        },
    }

    return {
        "prefix": prefix,
        "names": names,
        "unit_selectors": unit_selectors,
        "ids": {
            "root": f"palletizationToolRoot{suffix}",
            "box_catalogue_chooser": f"boxCatalogueChooser{suffix}",
            "manual_box_fields": f"manualBoxFields{suffix}",
            "pallet_catalogue_chooser": f"palletCatalogueChooser{suffix}",
            "manual_pallet_fields": f"manualPalletFields{suffix}",
            "manual_pallet_height_field": f"manualPalletHeightField{suffix}",
            "catalogue_pallet_main_fields": f"cataloguePalletMainFields{suffix}",
            "stacking_constraints_section": f"stackingConstraintsSection{suffix}",
            "toggle_constraints_text": f"toggleConstraintsText{suffix}",
            "toggle_constraints_icon": f"toggleConstraintsIcon{suffix}",
            "selected_result_key": f"selected_result_key{suffix}",
            "show_advanced": f"show_advanced{suffix}",
            "threejs_viewer": f"palletizationThreeJsViewer{suffix}",
            "threejs_scene": f"palletizationThreeJsScene{suffix}",
        },
        "actions": {
            "browse_box": "palletToolBrowseBoxCatalogue",
            "clear_box": "palletToolClearSelectedBox",
            "select_box": "palletToolSelectBox",
            "browse_pallet": "palletToolBrowsePalletCatalogue",
            "clear_pallet": "palletToolClearSelectedPallet",
            "select_pallet": "palletToolSelectPallet",
            "toggle_advanced": "palletToolToggleConstraints",
            "run_analysis": "palletToolRunAnalysis",
            "select_result": "palletToolSelectResult",
        },
    }


def _catalogue_dimension(material, external_attr, part_attr):
    if material is None:
        return ""
    first_raw = ""
    for attr in (external_attr, part_attr):
        raw_value = getattr(material, attr, None)
        numeric_value = _to_float(raw_value, None)
        if raw_value not in (None, "", "None") and first_raw == "":
            first_raw = raw_value
        if numeric_value is not None and numeric_value > 0:
            return raw_value
    return first_raw


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


def selected_box_summary(selected_material, data):
    dimension_unit = _read_value(data, "box_dimension_unit", "mm") or "mm"
    mass_unit = _read_value(data, "mass_unit", "g") or "g"
    if selected_material:
        length = _catalogue_dimension(selected_material, "external_length", "part_length")
        width = _catalogue_dimension(selected_material, "external_width", "part_width")
        height = _catalogue_dimension(selected_material, "external_height", "part_height")
        return {
            "title": f"{selected_material.part_number} — {selected_material.part_description}",
            "dims": format_dimensions(
                length, width, height, display_unit=dimension_unit
            ),
            "meta": f"{selected_material.packaging_type} | {selected_material.branding}",
            "weight": format_mass(
                getattr(selected_material, "part_weight", None),
                canonical_unit="kg",
                display_unit=mass_unit,
            ),
        }

    return {
        "title": "Manual box",
        "dims": f'{_read_value(data, "box_l", "")} × {_read_value(data, "box_w", "")} × {_read_value(data, "box_h", "")} {dimension_unit}',
        "meta": "Manual dimensions",
        "weight": f'{_read_value(data, "box_weight", "")} {mass_unit}',
    }


def selected_pallet_summary(selected_material, data):
    dimension_unit = _read_value(data, "pallet_dimension_unit", "mm") or "mm"
    mass_unit = _read_value(data, "mass_unit", "g") or "g"
    if selected_material:
        length = _catalogue_dimension(selected_material, "external_length", "part_length")
        width = _catalogue_dimension(selected_material, "external_width", "part_width")
        height = _catalogue_dimension(selected_material, "external_height", "part_height")
        return {
            "title": f"{selected_material.part_number} — {selected_material.part_description}",
            "dims": format_dimensions(
                length, width, height, display_unit=dimension_unit
            ),
            "meta": f"{selected_material.packaging_type} | {selected_material.branding}",
            "weight": format_mass(
                getattr(selected_material, "part_weight", None),
                canonical_unit="kg",
                display_unit=mass_unit,
            ),
        }

    return {
        "title": "Manual pallet",
        "dims": (
            f'{_read_value(data, "pallet_l", "")} × '
            f'{_read_value(data, "pallet_w", "")} × '
            f'{_read_value(data, "pallet_height", "")} {dimension_unit}'
        ),
        "meta": "Manual dimensions",
        "weight": "",
    }


def result_card_from_row(row, pallet_l, pallet_w, pallet_height):
    max_bottom_load_g = row.get("max_bottom_load_g", row.get("max_bottom_load_kg"))
    return {
        "kind": "pallet",
        "pattern": row["pattern"],
        "stacking": row["stacking"],
        "pallet_l": round(float(pallet_l), 2),
        "pallet_w": round(float(pallet_w), 2),
        "total_height_mm": round(float(row["used_height_mm"]) + float(pallet_height), 2),
        "total_boxes": int(row["total_boxes"]),
        "layers": int(row["layers"]),
        "layer_footprint_util_pct": round(float(row["layer_footprint_util_pct"]), 2),
        "volumetric_util_pct": round(float(row["volumetric_util_pct"]), 2),
        "feasible_weight": bool(row["feasible_weight"]),
        "max_bottom_load_g": max_bottom_load_g,
        "max_bottom_load_kg": max_bottom_load_g,
    }


def attach_pallet_result_presentation(serialized_result, config, effective_config):
    """Add display strings without changing canonical serialized result keys."""
    result = serialized_result or {}
    config = config or {}
    effective = effective_config or {}
    dimension_unit = config.get("pallet_dimension_unit") or "mm"
    box_dimension_unit = config.get("box_dimension_unit") or "mm"
    mass_unit = config.get("mass_unit") or "g"

    def decorate(row):
        if not isinstance(row, dict):
            return row
        row["total_height_display"] = format_length(
            row.get("total_height_mm"), display_unit=dimension_unit
        )
        row["used_height_display"] = format_length(
            row.get("used_height_mm"), display_unit=dimension_unit
        )
        row["pallet_height_display"] = format_length(
            row.get("pallet_height_mm"), display_unit=dimension_unit
        )
        row["max_bottom_load_display"] = format_mass(
            row.get("max_bottom_load_g"), canonical_unit="g", display_unit=mass_unit
        )
        row["avg_bottom_load_display"] = format_mass(
            row.get("avg_bottom_load_g"), canonical_unit="g", display_unit=mass_unit
        )
        row["weight_limit_display"] = format_mass(
            row.get("weight_limit_g"), canonical_unit="g", display_unit=mass_unit
        )
        return row

    for row in result.get("results_table") or []:
        decorate(row)
    decorate(result.get("selected_result"))
    result["display"] = {
        "units": {
            "box_dimension": box_dimension_unit,
            "pallet_dimension": dimension_unit,
            "mass": mass_unit,
        },
        "box_dimensions": format_dimensions(
            effective.get("box_l"),
            effective.get("box_w"),
            effective.get("box_h"),
            display_unit=box_dimension_unit,
        ),
        "pallet_dimensions": format_dimensions(
            effective.get("pallet_l"),
            effective.get("pallet_w"),
            effective.get("pallet_height"),
            display_unit=dimension_unit,
        ),
        "max_stack_height": format_length(
            effective.get("max_stack_height"), display_unit=dimension_unit
        ),
        "width_overhang": format_length(
            effective.get("max_width_stickout"), display_unit=dimension_unit
        ),
        "length_overhang": format_length(
            effective.get("max_length_stickout"), display_unit=dimension_unit
        ),
        "box_weight": format_mass(
            effective.get("box_weight"), canonical_unit="g", display_unit=mass_unit
        ),
        "bottom_load_limit": format_mass(
            effective.get("max_weight_on_bottom_box"),
            canonical_unit="g",
            display_unit=mass_unit,
        ),
    }
    return result


def build_pallet_pending_result(
    pallet_l,
    pallet_w,
    pallet_height,
    selected_row,
    selected_pallet_material=None,
    upstream_units=1,
):
    label = "Manual Pallet"
    if selected_pallet_material:
        label = selected_pallet_material.part_number or "Selected Pallet"

    units_per_parent = int(selected_row["total_boxes"])
    return {
        "label": f'{label} | {selected_row["pattern"]} / {selected_row["stacking"]}',
        "length": round(float(pallet_l), 2),
        "width": round(float(pallet_w), 2),
        "height": round(float(selected_row["used_height_mm"]) + float(pallet_height), 2),
        "units_per_parent": units_per_parent,
        "total_base_units": units_per_parent * int(upstream_units or 1),
    }
