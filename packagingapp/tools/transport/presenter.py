from decimal import Decimal


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


def selected_container_summary(selected_material, data):
    """
    Summary for the transport container card.
    Works with both:
    - standalone form object
    - workflow config dict
    """
    max_weight = _read_value(data, "max_weight", "")
    container_l = _read_value(data, "container_l", "")
    container_w = _read_value(data, "container_w", "")
    container_h = _read_value(data, "container_h", "")

    if selected_material:
        return {
            "title": f"{getattr(selected_material, 'part_number', '')} — {getattr(selected_material, 'part_description', '')}",
            "dims": f"{getattr(selected_material, 'part_length', '')} × {getattr(selected_material, 'part_width', '')} × {getattr(selected_material, 'part_height', '')}",
            "meta": f"{getattr(selected_material, 'packaging_type', '')} | {getattr(selected_material, 'branding', '')}",
            "max_weight": max_weight or "",
        }

    return {
        "title": "Manual container",
        "dims": f"{container_l or ''} × {container_w or ''} × {container_h or ''}",
        "meta": "Manual dimensions",
        "max_weight": max_weight or "",
    }


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