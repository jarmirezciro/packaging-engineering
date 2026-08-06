from copy import deepcopy


PALLETIZATION_CASE_PRESETS = {
    "tops-pro-48x40-benchmark": {
        "label": "TOPS Pro 48 x 40 pallet benchmark",
        "config": {
            "box_source": "manual",
            "box_catalogue_id": "",
            "selected_box_id": "",
            "box_l": 411,
            "box_w": 289,
            "box_h": 231,
            "box_weight": 2268,
            "max_weight_on_bottom_box": "",
            "pallet_source": "manual",
            "pallet_catalogue_id": "",
            "pallet_id": "",
            "pallet_l": 1219,
            "pallet_w": 1016,
            "pallet_height": 101,
            "max_stack_height": 1346,
            "max_width_stickout": 25,
            "max_length_stickout": 25,
            "show_advanced": False,
        },
    },
}


def get_palletization_case_preset(slug):
    """Return an isolated public Palletization demo-case payload."""
    preset = PALLETIZATION_CASE_PRESETS.get(str(slug or "").strip())
    return deepcopy(preset) if preset else None
