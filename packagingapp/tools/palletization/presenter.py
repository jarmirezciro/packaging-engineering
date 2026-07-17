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

    return {
        "prefix": prefix,
        "names": {
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
            "box_weight": f"box_weight{suffix}",
            "max_weight_on_bottom_box": f"max_weight_on_bottom_box{suffix}",
            "pallet_source": f"pallet_source{suffix}",
            "pallet_catalogue_id": f"pallet_catalogue_id{suffix}",
            "pallet_l": f"pallet_l{suffix}",
            "pallet_w": f"pallet_w{suffix}",
            "max_stack_height": f"max_stack_height{suffix}",
            "max_width_stickout": f"max_width_stickout{suffix}",
            "max_length_stickout": f"max_length_stickout{suffix}",
        },
        "ids": {
            "root": f"palletizationToolRoot{suffix}",
            "box_catalogue_chooser": f"boxCatalogueChooser{suffix}",
            "manual_box_fields": f"manualBoxFields{suffix}",
            "pallet_catalogue_chooser": f"palletCatalogueChooser{suffix}",
            "manual_pallet_fields": f"manualPalletFields{suffix}",
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
    if selected_material:
        length = _catalogue_dimension(selected_material, "external_length", "part_length")
        width = _catalogue_dimension(selected_material, "external_width", "part_width")
        height = _catalogue_dimension(selected_material, "external_height", "part_height")
        return {
            "title": f"{selected_material.part_number} — {selected_material.part_description}",
            "dims": f"{length} × {width} × {height}",
            "meta": f"{selected_material.packaging_type} | {selected_material.branding}",
            "weight": getattr(selected_material, "part_weight", "") or _read_value(data, "box_weight", ""),
        }

    return {
        "title": "Manual box",
        "dims": f'{_read_value(data, "box_l", "")} × {_read_value(data, "box_w", "")} × {_read_value(data, "box_h", "")}',
        "meta": "Manual dimensions",
        "weight": _read_value(data, "box_weight", ""),
    }


def selected_pallet_summary(selected_material, data):
    if selected_material:
        length = _catalogue_dimension(selected_material, "external_length", "part_length")
        width = _catalogue_dimension(selected_material, "external_width", "part_width")
        height = _catalogue_dimension(selected_material, "external_height", "part_height")
        return {
            "title": f"{selected_material.part_number} — {selected_material.part_description}",
            "dims": f"{length} × {width} × {height}",
            "meta": f"{selected_material.packaging_type} | {selected_material.branding}",
        }

    return {
        "title": "Manual pallet",
        "dims": f'{_read_value(data, "pallet_l", "")} × {_read_value(data, "pallet_w", "")}',
        "meta": "Manual dimensions",
    }


def result_card_from_row(row, pallet_l, pallet_w):
    return {
        "kind": "pallet",
        "pattern": row["pattern"],
        "stacking": row["stacking"],
        "pallet_l": round(float(pallet_l), 2),
        "pallet_w": round(float(pallet_w), 2),
        "total_height_mm": round(float(row["used_height_mm"]) + 100.0, 2),
        "total_boxes": int(row["total_boxes"]),
        "layers": int(row["layers"]),
        "layer_footprint_util_pct": round(float(row["layer_footprint_util_pct"]), 2),
        "volumetric_util_pct": round(float(row["volumetric_util_pct"]), 2),
        "feasible_weight": bool(row["feasible_weight"]),
        "max_bottom_load_kg": row.get("max_bottom_load_kg"),
    }


def build_pallet_pending_result(pallet_l, pallet_w, selected_row, selected_pallet_material=None, upstream_units=1):
    label = "Manual Pallet"
    if selected_pallet_material:
        label = selected_pallet_material.part_number or "Selected Pallet"

    units_per_parent = int(selected_row["total_boxes"])
    return {
        "label": f'{label} | {selected_row["pattern"]} / {selected_row["stacking"]}',
        "length": round(float(pallet_l), 2),
        "width": round(float(pallet_w), 2),
        "height": round(float(selected_row["used_height_mm"]) + 100.0, 2),
        "units_per_parent": units_per_parent,
        "total_base_units": units_per_parent * int(upstream_units or 1),
    }
