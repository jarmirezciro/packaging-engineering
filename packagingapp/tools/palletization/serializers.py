from .height import pallet_render_components


def _json_safe_scalar(value):
    if isinstance(value, bool) or value is None:
        return value
    try:
        if hasattr(value, "__float__") and value.__class__.__name__ == "Decimal":
            return float(value)
    except Exception:
        pass
    return value


def sanitize_palletization_config_for_session(cfg):
    cfg = cfg or {}
    return {
        "box_source": str(cfg.get("box_source", "manual") or "manual"),
        "box_catalogue_id": str(cfg.get("box_catalogue_id", "") or ""),
        "selected_box_id": str(cfg.get("selected_box_id", "") or ""),
        "box_l": _json_safe_scalar(cfg.get("box_l", "")),
        "box_w": _json_safe_scalar(cfg.get("box_w", "")),
        "box_h": _json_safe_scalar(cfg.get("box_h", "")),
        # Missing unit metadata is intentionally metric for legacy sessions.
        "box_dimension_unit": str(cfg.get("box_dimension_unit", "mm") or "mm"),
        "box_weight": _json_safe_scalar(cfg.get("box_weight", "")),
        "max_weight_on_bottom_box": _json_safe_scalar(cfg.get("max_weight_on_bottom_box", "")),
        "mass_unit": str(cfg.get("mass_unit", "g") or "g"),
        "pallet_source": str(cfg.get("pallet_source", "manual") or "manual"),
        "pallet_catalogue_id": str(cfg.get("pallet_catalogue_id", "") or ""),
        "pallet_id": str(cfg.get("pallet_id", "") or ""),
        "pallet_l": _json_safe_scalar(cfg.get("pallet_l", "")),
        "pallet_w": _json_safe_scalar(cfg.get("pallet_w", "")),
        "pallet_height": _json_safe_scalar(cfg.get("pallet_height", "")),
        "pallet_dimension_unit": str(cfg.get("pallet_dimension_unit", "mm") or "mm"),
        "max_stack_height": _json_safe_scalar(cfg.get("max_stack_height", "")),
        "max_pallet_load": _json_safe_scalar(cfg.get("max_pallet_load", "")),
        "max_width_stickout": _json_safe_scalar(cfg.get("max_width_stickout", 0)),
        "max_length_stickout": _json_safe_scalar(cfg.get("max_length_stickout", 0)),
        "show_advanced": bool(cfg.get("show_advanced", False)),
    }


def serialize_pallet_row(row, pallet_height_mm=0.0):
    pattern = str(row["pattern"])
    stacking = str(row["stacking"])
    base_result_key = f"{pattern}__{stacking}"
    arrangement_height_mm = float(row["used_height_mm"])
    pallet_height_mm = float(pallet_height_mm or 0.0)
    max_bottom_load_g = row.get("max_bottom_load_g", row.get("max_bottom_load_kg"))
    avg_bottom_load_g = row.get("avg_bottom_load_g", row.get("avg_bottom_load_kg"))
    weight_limit_g = row.get("weight_limit_g", row.get("weight_limit_kg"))
    max_pallet_load_g = row.get("max_pallet_load_g")
    actual_pallet_load_g = row.get("actual_pallet_load_g")
    max_bottom_load_g = None if max_bottom_load_g is None else float(max_bottom_load_g)
    avg_bottom_load_g = None if avg_bottom_load_g is None else float(avg_bottom_load_g)
    weight_limit_g = None if weight_limit_g is None else float(weight_limit_g)
    max_pallet_load_g = None if max_pallet_load_g is None else float(max_pallet_load_g)
    actual_pallet_load_g = None if actual_pallet_load_g is None else float(actual_pallet_load_g)
    return {
        "pattern": pattern,
        "stacking": stacking,
        "result_key": base_result_key,
        "interlock_result_key": f"{base_result_key}__interlock_preview",
        "debug_label": f"{pattern} / {stacking}",
        "boxes_layer_A": int(row["boxes_layer_A"]),
        "boxes_layer_B": int(row["boxes_layer_B"]),
        "layers": int(row["layers"]),
        "total_boxes": int(row["total_boxes"]),
        "used_height_mm": arrangement_height_mm,
        "pallet_height_mm": pallet_height_mm,
        "total_height_mm": arrangement_height_mm + pallet_height_mm,
        "layer_footprint_util_pct": float(row["layer_footprint_util_pct"]),
        "volumetric_util_pct": float(row["volumetric_util_pct"]),
        "feasible_weight": bool(row["feasible_weight"]),
        "max_bottom_load_g": max_bottom_load_g,
        "avg_bottom_load_g": avg_bottom_load_g,
        "weight_limit_g": weight_limit_g,
        "max_pallet_load_g": max_pallet_load_g,
        "actual_pallet_load_g": actual_pallet_load_g,
        "load_utilization_pct": (
            None
            if row.get("load_utilization_pct") is None
            else float(row.get("load_utilization_pct"))
        ),
        "feasible_pallet_load": bool(row.get("feasible_pallet_load", True)),
        "weight_capacity_boxes": (
            None
            if row.get("weight_capacity_boxes") is None
            else int(row.get("weight_capacity_boxes"))
        ),
        "geometric_capacity_boxes": int(row.get("geometric_capacity_boxes") or 0),
        "limiting_constraint": str(row.get("limiting_constraint") or "Geometry"),
        # Temporary compatibility aliases; values are grams.
        "max_bottom_load_kg": max_bottom_load_g,
        "avg_bottom_load_kg": avg_bottom_load_g,
        "weight_limit_kg": weight_limit_g,
        "interlock_relation": str(row.get("interlock_relation", "") or ""),
        "interlock_possible": bool(row.get("interlock_possible", False)),
        "interlock_possible_relation": str(row.get("interlock_possible_relation", "") or ""),
        "interlock_render_active": bool(row.get("interlock_render_active", False)),
        "debug_equivalent_results": [str(item) for item in (row.get("debug_equivalent_results") or [])],
    }


def serialize_pallet_threejs_scene(render_row, effective_config, selected_row=None):
    """Serialize authoritative engine placements for the shared browser viewer."""
    if not render_row:
        return None

    cfg = effective_config or {}
    selected = selected_row or render_row
    pallet_l = float(cfg.get("pallet_l") or 0)
    pallet_w = float(cfg.get("pallet_w") or 0)
    pallet_height = float(cfg.get("pallet_height") or 0)
    deck_thickness, runner_height = pallet_render_components(pallet_height)
    overhang_l = float(cfg.get("max_length_stickout") or 0)
    overhang_w = float(cfg.get("max_width_stickout") or 0)
    box_l = float(cfg.get("box_l") or 0)
    box_w = float(cfg.get("box_w") or 0)
    box_h = float(cfg.get("box_h") or 0)

    placements = []
    for placement in render_row.get("placements3d") or []:
        placements.append({
            "x": float(placement.x),
            "y": float(placement.y),
            "z": float(placement.z) + pallet_height,
            "dx": float(placement.l),
            "dy": float(placement.w),
            "dz": float(placement.h),
            "layer": int(placement.layer_index) + 1,
            "pattern": str(selected.get("pattern") or ""),
            "orientation": str(placement.orientation or ""),
            "layer_kind": str(placement.layer_kind or "base"),
        })

    return {
        "units": "mm",
        "coordinate_system": {
            "python": "X=length, Y=width, Z=height",
            "threejs": "X=length, Y=height, Z=width",
        },
        "pallet": {
            "length": pallet_l,
            "width": pallet_w,
            "height": pallet_height,
            "deck_thickness": deck_thickness,
            "runner_height": runner_height,
        },
        "allowed_footprint": {
            "x": -overhang_l / 2.0,
            "y": -overhang_w / 2.0,
            "length": pallet_l + overhang_l,
            "width": pallet_w + overhang_w,
            "length_overhang": overhang_l,
            "width_overhang": overhang_w,
        },
        "case": {
            "length": box_l,
            "width": box_w,
            "height": box_h,
        },
        "placements": placements,
        "layers": int(selected.get("layers") or 0),
        "total_cases": int(selected.get("total_boxes") or len(placements)),
        "metadata": {
            "pattern_name": str(selected.get("pattern") or ""),
            "stacking": str(selected.get("stacking") or ""),
            "alternate_layer_view": bool(selected.get("interlock_render_active", False)),
            "alternate_layer_possible": bool(selected.get("interlock_possible", False)),
            "overhang": {
                "length_mm": overhang_l,
                "width_mm": overhang_w,
            },
            "pallet_usage_pct": float(selected.get("layer_footprint_util_pct") or 0),
            "stack_volume_usage_pct": float(selected.get("volumetric_util_pct") or 0),
            "stack_height_mm": float(selected.get("used_height_mm") or 0),
            "total_render_height_mm": (
                pallet_height + float(selected.get("used_height_mm") or 0)
            ),
        },
    }


def serialize_pallet_analysis_result(
    raw_results,
    selected_row=None,
    image_rel_path=None,
    selected_result_key=None,
    threejs_scene=None,
    pallet_height_mm=0.0,
):
    raw_results = raw_results or []
    safe_results = [
        serialize_pallet_row(row, pallet_height_mm=pallet_height_mm)
        for row in raw_results
    ]
    safe_selected = (
        serialize_pallet_row(selected_row, pallet_height_mm=pallet_height_mm)
        if selected_row
        else None
    )
    if selected_result_key is None:
        selected_result_key = ""
        if selected_row:
            selected_result_key = f'{selected_row["pattern"]}__{selected_row["stacking"]}'

    return {
        "results_table": safe_results,
        "selected_result_key": selected_result_key,
        "selected_result": safe_selected,
        "image_rel_path": image_rel_path,
        "threejs_scene": threejs_scene,
    }
