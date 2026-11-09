from copy import deepcopy


_TOPS_CASE_PACK_PALLET = {
    "pallet_l": 1219,
    "pallet_w": 1016,
    "pallet_height": 127,
    "max_stack_height": 1346,
}

# The CapePack Flow cases retain inch pallet inputs and pass external carton
# dimensions from the shared design calculation. Store those dimensions in mm.
_CAPEPACK_PALLET = {
    "box_dimension_unit": "mm",
    "pallet_dimension_unit": "in",
    "mass_unit": "lb",
    "pallet_l": 48,
    "pallet_w": 40,
    "pallet_height": 5.5,
}

_STANDARD_MOSAIC = {
    "box_l": 230,
    "box_w": 170,
    "box_h": 130,
    "pallet_l": 1200,
    "pallet_w": 800,
    "pallet_height": 150,
    "max_stack_height": 1200,
}

_THINK_BEYOND_THE_BOX_PALLET = {
    "pallet_l": 1200,
    "pallet_w": 800,
    "pallet_height": 80,
    "max_stack_height": 1350,
    "max_length_stickout": 25.4,
    "max_width_stickout": 25.4,
    "show_advanced": True,
}


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
    # Exact external dimensions from the TOPS case-pack Palletization captures.
    "tops-case-pack-8": {
        "label": "TOPS Case-Pack: 8 Units",
        "config": {**_TOPS_CASE_PACK_PALLET, "box_l": 314, "box_w": 148, "box_h": 194},
    },
    "tops-case-pack-16": {
        "label": "TOPS Case-Pack: 16 Units",
        "config": {**_TOPS_CASE_PACK_PALLET, "box_l": 364, "box_w": 288, "box_h": 169},
    },
    # CapePack Flow reproductions run geometrically when gross carton mass is unknown.
    "capepack-original-216": {
        "label": "CapePack Original: 216 Units",
        "config": {
            **_CAPEPACK_PALLET,
            "box_l": 389,
            "box_w": 312.8,
            "box_h": 422.4,
            "max_stack_height": 50,
        },
    },
    "capepack-original-240": {
        "label": "CapePack Original: 240 Units",
        "config": {
            **_CAPEPACK_PALLET,
            "box_l": 516,
            "box_w": 465.2,
            "box_h": 219.2,
            "max_stack_height": 50,
        },
    },
    "capepack-72in-12-pack": {
        "label": "CapePack 72-in: 12-Pack",
        "config": {
            **_CAPEPACK_PALLET,
            "box_l": 465.2,
            "box_w": 211.2,
            "box_h": 524,
            "max_stack_height": 72,
        },
    },
    "capepack-72in-16-pack": {
        "label": "CapePack 72-in: 16-Pack",
        "config": {
            **_CAPEPACK_PALLET,
            "box_l": 414.4,
            "box_w": 312.8,
            "box_h": 524,
            "max_stack_height": 72,
        },
    },
    # Stage 2 na4840_splitrow and test_pallet_splitrow.py.
    "north-american-splitrow": {
        "label": "North American Splitrow",
        "config": {
            "box_l": 308,
            "box_w": 147,
            "box_h": 193,
            "pallet_l": 1219,
            "pallet_w": 1016,
            "pallet_height": 141,
            "max_stack_height": 1346,
        },
    },
    # Unweighted standard analysis in benchmark_palletization_stage2.py.
    "pinwheel-mosaic": {
        "label": "Pinwheel & Mosaic",
        "config": {**_STANDARD_MOSAIC},
    },
    # Stage 2 brick_and_centre_filled, maximum_pallet_load and standard_pallet.
    "brick-centre-filled": {
        "label": "Brick & Centre-Filled",
        "config": {
            "box_l": 400,
            "box_w": 200,
            "box_h": 200,
            "pallet_l": 1200,
            "pallet_w": 1200,
            "pallet_height": 150,
            "max_stack_height": 1150,
        },
    },
    "maximum-pallet-load": {
        "label": "Maximum Pallet Load",
        "config": {
            "box_l": 400,
            "box_w": 400,
            "box_h": 200,
            "box_weight": 1000,
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 150,
            "max_stack_height": 1150,
            "max_pallet_load": 22000,
            "show_advanced": True,
        },
    },
    "bottom-carton-load": {
        "label": "Bottom-Carton Load",
        "config": {
            **_STANDARD_MOSAIC,
            "box_weight": 1250,
            "max_weight_on_bottom_box": 9000,
            "show_advanced": True,
        },
    },
    # The feasible branch of test_configured_overhang_is_included_in_footprint_feasibility.
    "overhang-feasibility": {
        "label": "Overhang Feasibility",
        "config": {
            "box_l": 1100,
            "box_w": 700,
            "box_h": 200,
            "pallet_l": 1000,
            "pallet_w": 800,
            "pallet_height": 100,
            "max_stack_height": 500,
            "max_length_stickout": 200,
            "show_advanced": True,
        },
    },
    # Stage 2 fractional_dimensions.
    "fractional-dimensions": {
        "label": "Fractional Dimensions",
        "config": {
            "box_l": 73.2,
            "box_w": 41.7,
            "box_h": 29.3,
            "pallet_l": 401.5,
            "pallet_w": 287.9,
            "pallet_height": 42.5,
            "max_stack_height": 218.3,
        },
    },
    # test_exact_height_boundary_and_known_standard_capacity_are_preserved.
    "exact-stack-height": {
        "label": "Exact Stack Height",
        "config": {
            "box_l": 400,
            "box_w": 300,
            "box_h": 1050,
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 150,
            "max_stack_height": 1200,
        },
    },
    # External carton dimensions handed off by the think-beyond-the-box Flow case.
    "think-beyond-the-box-compact": {
        "label": "Think Beyond the Box: Compact Proposal",
        "config": {
            **_THINK_BEYOND_THE_BOX_PALLET,
            "box_l": 508,
            "box_w": 308,
            "box_h": 316,
        },
    },
    "think-beyond-the-box-alternative-7": {
        "label": "Think Beyond the Box: Alternative 7",
        "config": {
            **_THINK_BEYOND_THE_BOX_PALLET,
            "box_l": 608,
            "box_w": 258,
            "box_h": 316,
        },
    },
}


def get_palletization_case_preset(slug):
    """Return an isolated public Palletization demo-case payload."""
    preset = PALLETIZATION_CASE_PRESETS.get(str(slug or "").strip())
    return deepcopy(preset) if preset else None
