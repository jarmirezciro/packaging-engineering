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
        "box_weight": _json_safe_scalar(cfg.get("box_weight", "")),
        "max_weight_on_bottom_box": _json_safe_scalar(cfg.get("max_weight_on_bottom_box", "")),
        "pallet_source": str(cfg.get("pallet_source", "manual") or "manual"),
        "pallet_catalogue_id": str(cfg.get("pallet_catalogue_id", "") or ""),
        "pallet_id": str(cfg.get("pallet_id", "") or ""),
        "pallet_l": _json_safe_scalar(cfg.get("pallet_l", "")),
        "pallet_w": _json_safe_scalar(cfg.get("pallet_w", "")),
        "max_stack_height": _json_safe_scalar(cfg.get("max_stack_height", "")),
        "max_width_stickout": _json_safe_scalar(cfg.get("max_width_stickout", 0)),
        "max_length_stickout": _json_safe_scalar(cfg.get("max_length_stickout", 0)),
        "show_advanced": bool(cfg.get("show_advanced", False)),
    }


def serialize_pallet_row(row):
    return {
        "pattern": str(row["pattern"]),
        "stacking": str(row["stacking"]),
        "boxes_layer_A": int(row["boxes_layer_A"]),
        "boxes_layer_B": int(row["boxes_layer_B"]),
        "layers": int(row["layers"]),
        "total_boxes": int(row["total_boxes"]),
        "used_height_mm": float(row["used_height_mm"]),
        "layer_footprint_util_pct": float(row["layer_footprint_util_pct"]),
        "volumetric_util_pct": float(row["volumetric_util_pct"]),
        "feasible_weight": bool(row["feasible_weight"]),
        "max_bottom_load_kg": None if row.get("max_bottom_load_kg") is None else float(row.get("max_bottom_load_kg")),
        "avg_bottom_load_kg": None if row.get("avg_bottom_load_kg") is None else float(row.get("avg_bottom_load_kg")),
        "weight_limit_kg": None if row.get("weight_limit_kg") is None else float(row.get("weight_limit_kg")),
    }


def serialize_pallet_analysis_result(raw_results, selected_row=None, image_rel_path=None):
    raw_results = raw_results or []
    safe_results = [serialize_pallet_row(row) for row in raw_results]
    safe_selected = serialize_pallet_row(selected_row) if selected_row else None
    selected_result_key = ""
    if selected_row:
        selected_result_key = f'{selected_row["pattern"]}__{selected_row["stacking"]}'

    return {
        "results_table": safe_results,
        "selected_result_key": selected_result_key,
        "selected_result": safe_selected,
        "image_rel_path": image_rel_path,
    }