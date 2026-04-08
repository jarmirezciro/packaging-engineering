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
        length = selected_material.external_length if selected_material.external_length is not None else selected_material.part_length
        width = selected_material.external_width if selected_material.external_width is not None else selected_material.part_width
        height = selected_material.external_height if selected_material.external_height is not None else selected_material.part_height
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
        length = selected_material.external_length if selected_material.external_length is not None else selected_material.part_length
        width = selected_material.external_width if selected_material.external_width is not None else selected_material.part_width
        height = selected_material.external_height if selected_material.external_height is not None else selected_material.part_height
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