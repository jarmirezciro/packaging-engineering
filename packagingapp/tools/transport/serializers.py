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
            "max_qty": bool(row.get("max_qty", False)),
            "stackable": bool(row.get("stackable", True)),
            "weight": _json_safe_scalar(row.get("weight", 0)),
            "sequence": _json_safe_scalar(row.get("sequence", 1)),
            "r1": bool(row.get("r1", False)),
            "r2": bool(row.get("r2", False)),
            "r3": bool(row.get("r3", False)),
        })
    return safe_rows


_TRANSPORT_ITEM_COLORS = (
    "#f59e0b",
    "#2563eb",
    "#0d9488",
    "#dc2626",
    "#7c3aed",
    "#65a30d",
    "#ea580c",
    "#0891b2",
)


def _transport_product_identity(row_index):
    stable_index = max(int(row_index or 0), 0)
    return {
        "index": stable_index,
        "id": f"P{stable_index + 1}",
        "color": _TRANSPORT_ITEM_COLORS[
            stable_index % len(_TRANSPORT_ITEM_COLORS)
        ],
    }


def serialize_transport_threejs_scene(container, placements, summary):
    """Serialize authoritative engine placements for the browser renderer.

    Engine/Python coordinates use X=length, Y=width, Z=height. The Three.js
    viewer owns only the coordinate-axis mapping and presentation.
    """
    container = container or {}
    summary = summary or {}
    summary_rows = list(summary.get("product_rows") or [])
    loaded_by_row = {}
    items = []

    for placement in placements or []:
        row_index = max(int(getattr(placement, "row_index", 0) or 0), 0)
        identity = _transport_product_identity(row_index)
        label = str(
            getattr(placement, "product_name", "")
            or f"Load unit {row_index + 1}"
        )
        loaded_by_row[row_index] = loaded_by_row.get(row_index, 0) + 1
        items.append({
            "x": float(getattr(placement, "x", 0) or 0),
            "y": float(getattr(placement, "y", 0) or 0),
            "z": float(getattr(placement, "z", 0) or 0),
            "dx": float(getattr(placement, "l", 0) or 0),
            "dy": float(getattr(placement, "w", 0) or 0),
            "dz": float(getattr(placement, "h", 0) or 0),
            "label": label,
            "product_index": identity["index"],
            "product_id": identity["id"],
            "kind": "load_unit",
            "color": identity["color"],
            "opacity": 1.0,
        })

    products = []
    for row_index in sorted(loaded_by_row):
        identity = _transport_product_identity(row_index)
        row = summary_rows[row_index] if row_index < len(summary_rows) else {}
        first_item = next(
            (item for item in items if item["product_index"] == row_index),
            {},
        )
        products.append({
            "product_index": identity["index"],
            "product_id": identity["id"],
            "name": str(
                row.get("name")
                or first_item.get("label")
                or f"Load unit {row_index + 1}"
            ),
            "length": float(row.get("length", 0) or 0),
            "width": float(row.get("width", 0) or 0),
            "height": float(row.get("height", 0) or 0),
            "qty_loaded": int(loaded_by_row[row_index]),
            "qty_requested": (
                int(row.get("qty_requested", 0) or 0)
                if row.get("qty_requested") is not None
                else None
            ),
            "color": identity["color"],
        })

    return {
        "version": 2,
        "units": "mm",
        "transport_unit": {
            "length": float(container.get("L", 0) or 0),
            "width": float(container.get("W", 0) or 0),
            "height": float(container.get("H", 0) or 0),
            "type": str(container.get("type", "TRANSPORT_UNIT") or "TRANSPORT_UNIT"),
        },
        "items": items,
        "products": products,
        "metadata": {
            "total_items": int(summary.get("placed_units", len(items)) or 0),
            "used_length": float(summary.get("occupied_length", 0) or 0),
            "remaining_length": float(summary.get("residual_length", 0) or 0),
        },
    }


def serialize_transport_result(result, threejs_scene=None):
    summary = result.get("summary", {}) or {}
    serialized = {
        "packing_mode": str(result.get("packing_mode", "maximum_utilization") or "maximum_utilization"),
        "strategy": str(result.get("strategy", "") or ""),
        "sequence_zones": list(result.get("sequence_zones") or []),
        "summary": {
            "container_volume": float(summary.get("container_volume", 0) or 0),
            "packed_volume": float(summary.get("packed_volume", 0) or 0),
            "container_volume_m3": float(summary.get("container_volume_m3", 0) or 0),
            "packed_volume_m3": float(summary.get("packed_volume_m3", 0) or 0),
            "utilization_volume_pct": float(summary.get("utilization_volume_pct", 0) or 0),
            "container_max_weight": float(summary.get("container_max_weight", 0)) if summary.get("container_max_weight") is not None else None,
            "has_payload_limit": bool(summary.get("has_payload_limit", False)),
            "loaded_weight": float(summary.get("loaded_weight", 0) or 0),
            "tare_weight": float(summary.get("tare_weight", 0)) if summary.get("tare_weight") is not None else None,
            "gross_weight": float(summary.get("gross_weight", 0) or 0),
            "utilization_weight_pct": float(summary.get("utilization_weight_pct", 0)) if summary.get("utilization_weight_pct") is not None else None,
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
                    "max_qty": bool(r.get("max_qty", False)),
                    "stackable": bool(r.get("stackable", True)),
                    "weight_each": float(r.get("weight_each", 0) or 0),
                    "sequence": int(r.get("sequence", 0) or 0),
                }
                for r in (summary.get("product_rows") or [])
            ],
        }
    }
    if threejs_scene is not None:
        serialized["threejs_scene"] = threejs_scene
    serialized.update({
        key: value
        for key, value in result.items()
        if key.startswith("space_evenly_")
        or key.startswith("front_to_back_")
        or key.startswith("floor_first_")
    })
    return serialized
