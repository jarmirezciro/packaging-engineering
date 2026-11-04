CONTAINER_ADVANCED_STATE_DEFAULTS = {
    "product_weight_user_override": "",
    "box_weight_user_override": "",
    "box_max_payload_user_override": "",
    "container_override_target": "",
    "product_override_target": "",
    "product_advanced_open": "",
    "container_advanced_open": "",
}


def normalize_container_override_scope(config):
    """Keep analysis overrides attached to the selected physical item."""
    config = dict(config)
    catalogue = config.get("mode") == "optimal" or (
        config.get("mode") != "design" and config.get("container_source") == "catalogue"
    )
    target = ("catalogue:" + str(config.get("container_id") or "pending:" + str(config.get("catalogue_id") or ""))) if catalogue else "manual"
    previous = config.get("container_override_target") or ""
    if previous != target and (previous or catalogue):
        for key in ("box_thickness_mm", "box_thickness_user_override", "combined_grammage_g_m2",
                    "grammage_user_override", "box_weight", "box_weight_user_override",
                    "box_max_payload", "box_max_payload_user_override", "corrugated_material_id",
                    "corrugated_material_user_selected", "custom_combined_grammage_g_m2"):
            config[key] = ""
    config["container_override_target"] = target
    product_target = ("catalogue:" + str(config.get("selected_product_id") or "pending:" + str(config.get("product_catalogue_id") or ""))) if config.get("product_source") == "catalogue" else "manual"
    previous = config.get("product_override_target") or ""
    if previous != product_target and (previous or product_target != "manual"):
        config["product_weight"] = ""
        config["product_weight_user_override"] = ""
    config["product_override_target"] = product_target
    return config


def default_container_config():
    return {
        **CONTAINER_ADVANCED_STATE_DEFAULTS,
        "mode": "single",
        "action": "",

        "product_source": "manual",
        "product_catalogue_id": "",
        "selected_product_id": "",
        "product_l": "",
        "product_w": "",
        "product_h": "",
        "product_dimension_unit": "mm",
        "product_allowance_l": "0",
        "product_allowance_w": "0",
        "product_allowance_h": "0",
        "product_weight": "",
        "product_mass_unit": "g",
        "desired_qty": "1",
        "product_shape": "cuboid",
        "r1": True,
        "r2": True,
        "r3": True,

        "container_source": "manual",
        "catalogue_id": "",
        "container_id": "",
        "box_l": "",
        "box_w": "",
        "box_h": "",
        "box_thickness_mm": "",
        "box_thickness_user_override": "",
        "combined_grammage_g_m2": "",
        "grammage_user_override": "",
        "corrugated_material_id": "",
        "corrugated_material_user_selected": "",
        "custom_combined_grammage_g_m2": "",
        "container_dimension_unit": "mm",
        "box_weight": "",
        "box_max_payload": "",
        "container_mass_unit": "g",
        "selected_design_candidate_id": "",
    }
