from .state import default_bag_config


def _safe_str(value, default=""):
    if value is None:
        return default
    return str(value)


def sanitize_bag_config_for_session(config):
    base = default_bag_config()
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
        "desired_qty": _safe_str(base.get("desired_qty") or "1"),
        "bag_source": _safe_str(base.get("bag_source") or "manual"),
        "catalogue_id": _safe_str(base.get("catalogue_id") or ""),
        "bag_id": _safe_str(base.get("bag_id") or ""),
        "bag_length": _safe_str(base.get("bag_length") or ""),
        "bag_width": _safe_str(base.get("bag_width") or ""),
    }
