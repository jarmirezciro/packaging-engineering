from .state import CONTAINER_ADVANCED_STATE_DEFAULTS, default_container_config, normalize_container_override_scope
from ..selection_mode import normalize_selection_mode
from ..product_shape import normalize_product_shape


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _safe_str(value, default=""):
    if value is None:
        return default
    return str(value)


def sanitize_container_config_for_session(config):
    original = config or {}
    base = default_container_config()
    base.update(original)
    thickness_override = base.get("box_thickness_user_override")
    if "box_thickness_user_override" not in original:
        # Existing sessions with an explicit thickness must keep behaving as
        # manual overrides after the new auto-caliper state is introduced.
        thickness_override = bool(str(base.get("box_thickness_mm") or "").strip())
    for key, flag in (("box_weight", "box_weight_user_override"), ("box_max_payload", "box_max_payload_user_override"), ("product_weight", "product_weight_user_override")):
        if flag not in original and base.get(key) not in (None, ""):
            base[flag] = "1"
    base["box_thickness_user_override"] = "1" if _as_bool(thickness_override) else ""
    base = normalize_container_override_scope(base)
    thickness_override = base.get("box_thickness_user_override")

    return {
        **{key: _safe_str(base.get(key)) if key.endswith("_target") else "1" if _as_bool(base.get(key)) else ""
           for key in CONTAINER_ADVANCED_STATE_DEFAULTS},
        "mode": normalize_selection_mode(base),
        "action": _safe_str(base.get("action") or ""),

        "product_source": _safe_str(base.get("product_source") or "manual"),
        "product_catalogue_id": _safe_str(base.get("product_catalogue_id") or ""),
        "selected_product_id": _safe_str(base.get("selected_product_id") or ""),
        "product_l": _safe_str(base.get("product_l") or ""),
        "product_w": _safe_str(base.get("product_w") or ""),
        "product_h": _safe_str(base.get("product_h") or ""),
        "product_dimension_unit": _safe_str(base.get("product_dimension_unit") or "mm"),
        "product_allowance_l": _safe_str(base.get("product_allowance_l") or "0"),
        "product_allowance_w": _safe_str(base.get("product_allowance_w") or "0"),
        "product_allowance_h": _safe_str(base.get("product_allowance_h") or "0"),
        "product_weight": _safe_str(base.get("product_weight")),
        "product_mass_unit": _safe_str(base.get("product_mass_unit") or "g"),
        "desired_qty": _safe_str(base.get("desired_qty") or "1"),
        "product_shape": normalize_product_shape(base.get("product_shape")),
        "r1": bool(base.get("r1", True)),
        "r2": bool(base.get("r2", True)),
        "r3": bool(base.get("r3", True)),

        "container_source": _safe_str(base.get("container_source") or "manual"),
        "catalogue_id": _safe_str(base.get("catalogue_id") or ""),
        "container_id": _safe_str(base.get("container_id") or ""),
        "box_l": _safe_str(base.get("box_l") or ""),
        "box_w": _safe_str(base.get("box_w") or ""),
        "box_h": _safe_str(base.get("box_h") or ""),
        "box_thickness_mm": _safe_str(base.get("box_thickness_mm") or ""),
        "box_thickness_user_override": "1" if _as_bool(thickness_override) else "",
        "combined_grammage_g_m2": _safe_str(base.get("combined_grammage_g_m2") or ""),
        "grammage_user_override": "1" if _as_bool(base.get("grammage_user_override")) else "",
        "corrugated_material_id": _safe_str(base.get("corrugated_material_id") or ""),
        "corrugated_material_user_selected": "1" if _as_bool(
            base.get("corrugated_material_user_selected")
        ) else "",
        "custom_combined_grammage_g_m2": _safe_str(
            base.get("custom_combined_grammage_g_m2") or ""
        ),
        "container_dimension_unit": _safe_str(base.get("container_dimension_unit") or "mm"),
        "box_weight": _safe_str(base.get("box_weight")),
        "box_max_payload": _safe_str(base.get("box_max_payload")),
        "container_mass_unit": _safe_str(base.get("container_mass_unit") or "g"),
        "selected_design_candidate_id": _safe_str(base.get("selected_design_candidate_id") or ""),
    }
