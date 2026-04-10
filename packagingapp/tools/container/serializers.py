from .state import default_container_config


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _safe_str(value, default=""):
    if value is None:
        return default
    return str(value)


def sanitize_container_config_for_session(config):
    base = default_container_config()
    base.update(config or {})

    return {
        "mode": _safe_str(base.get("mode") or "single"),
        "action": _safe_str(base.get("action") or ""),

        "product_source": _safe_str(base.get("product_source") or "manual"),
        "product_catalogue_id": _safe_str(base.get("product_catalogue_id") or ""),
        "selected_product_id": _safe_str(base.get("selected_product_id") or ""),
        "product_l": _safe_str(base.get("product_l") or ""),
        "product_w": _safe_str(base.get("product_w") or ""),
        "product_h": _safe_str(base.get("product_h") or ""),
        "product_weight": _safe_str(base.get("product_weight") or ""),
        "desired_qty": _safe_str(base.get("desired_qty") or "1"),
        "r1": bool(base.get("r1", True)),
        "r2": bool(base.get("r2", True)),
        "r3": bool(base.get("r3", True)),

        "container_source": _safe_str(base.get("container_source") or "manual"),
        "catalogue_id": _safe_str(base.get("catalogue_id") or ""),
        "container_id": _safe_str(base.get("container_id") or ""),
        "box_l": _safe_str(base.get("box_l") or ""),
        "box_w": _safe_str(base.get("box_w") or ""),
        "box_h": _safe_str(base.get("box_h") or ""),
    }