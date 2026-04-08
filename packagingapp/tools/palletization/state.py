def default_palletization_config():
    return {
        "box_source": "manual",
        "box_catalogue_id": "",
        "selected_box_id": "",
        "box_l": "",
        "box_w": "",
        "box_h": "",
        "box_weight": "",
        "max_weight_on_bottom_box": "",
        "pallet_source": "manual",
        "pallet_catalogue_id": "",
        "pallet_id": "",
        "pallet_l": "",
        "pallet_w": "",
        "max_stack_height": "",
        "max_width_stickout": 0,
        "max_length_stickout": 0,
        "show_advanced": False,
    }


def default_palletization_ui_state():
    return {
        "selected_result_key": "",
        "show_box_catalogue": False,
        "show_pallet_catalogue": False,
        "analysis_ran": False,
    }