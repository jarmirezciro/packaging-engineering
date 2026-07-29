from copy import deepcopy


CONTAINER_SELECTION_CASE_PRESETS = {
    "product-orientation-capacity": {
        "label": "Product orientation capacity demo",
        "product_dimensions_display": "500 × 200 × 300 mm",
        "container_dimensions_display": "800 × 800 × 900 mm",
        "config": {
            "mode": "single",
            "action": "run_single",
            "product_source": "manual",
            "product_catalogue_id": "",
            "selected_product_id": "",
            "product_l": 500,
            "product_w": 200,
            "product_h": 300,
            "product_weight": 2000,
            "desired_qty": 1,
            "r1": True,
            "r2": True,
            "r3": True,
            "container_source": "manual",
            "catalogue_id": "",
            "container_id": "",
            "box_l": 800,
            "box_w": 800,
            "box_h": 900,
            "box_weight": 5000,
            "box_max_payload": 50000,
            "selected_design_candidate_id": "",
        },
    },
}


def get_container_selection_case_preset(slug):
    """Return an isolated preset payload for a public Container Selection demo."""
    preset = CONTAINER_SELECTION_CASE_PRESETS.get(str(slug or "").strip())
    return deepcopy(preset) if preset else None
