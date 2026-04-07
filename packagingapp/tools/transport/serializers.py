def _json_safe_scalar(value):
    if isinstance(value, bool) or value is None:
        return value
    try:
        if hasattr(value, "__float__") and value.__class__.__name__ == "Decimal":
            return float(value)
    except Exception:
        pass
    return value


def sanitize_transport_rows_for_session(rows):
    safe_rows = []
    for row in rows or []:
        safe_rows.append({
            "name": str(row.get("name", "")),
            "length": _json_safe_scalar(row.get("length", "")),
            "width": _json_safe_scalar(row.get("width", "")),
            "height": _json_safe_scalar(row.get("height", "")),
            "qty": _json_safe_scalar(row.get("qty", 1)),
            "weight": _json_safe_scalar(row.get("weight", 0)),
            "sequence": _json_safe_scalar(row.get("sequence", 1)),
            "r1": bool(row.get("r1", False)),
            "r2": bool(row.get("r2", False)),
            "r3": bool(row.get("r3", False)),
        })
    return safe_rows


def serialize_transport_result(result):
    summary = result.get("summary", {}) or {}
    return {
        "summary": {
            "container_volume": float(summary.get("container_volume", 0) or 0),
            "packed_volume": float(summary.get("packed_volume", 0) or 0),
            "utilization_volume_pct": float(summary.get("utilization_volume_pct", 0) or 0),
            "container_max_weight": float(summary.get("container_max_weight", 0) or 0),
            "loaded_weight": float(summary.get("loaded_weight", 0) or 0),
            "utilization_weight_pct": float(summary.get("utilization_weight_pct", 0) or 0),
            "placed_units": int(summary.get("placed_units", 0) or 0),
            "unplaced_units": int(summary.get("unplaced_units", 0) or 0),
            "occupied_length": float(summary.get("occupied_length", 0) or 0),
            "occupied_width": float(summary.get("occupied_width", 0) or 0),
            "occupied_height": float(summary.get("occupied_height", 0) or 0),
            "residual_length": float(summary.get("residual_length", 0) or 0),
            "residual_width": float(summary.get("residual_width", 0) or 0),
            "residual_height": float(summary.get("residual_height", 0) or 0),
            "product_rows": [
                {
                    "name": str(r.get("name", "")),
                    "length": float(r.get("length", 0) or 0),
                    "width": float(r.get("width", 0) or 0),
                    "height": float(r.get("height", 0) or 0),
                    "qty_requested": int(r.get("qty_requested", 0) or 0),
                    "qty_packed": int(r.get("qty_packed", 0) or 0),
                    "weight_each": float(r.get("weight_each", 0) or 0),
                    "sequence": int(r.get("sequence", 0) or 0),
                }
                for r in (summary.get("product_rows") or [])
            ],
        }
    }
