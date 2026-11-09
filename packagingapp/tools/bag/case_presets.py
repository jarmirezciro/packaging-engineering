from copy import deepcopy

from ...units import convert_length, convert_mass


SEO_BAG_SELECTION_EXAMPLE_CONFIG = {
    "mode": "single",
    "action": "run_single",
    "product_source": "manual",
    "product_l": 180,
    "product_w": 120,
    "product_h": 40,
    "product_weight": 250,
    "desired_qty": 4,
    "bag_source": "manual",
    "bag_length": 450,
    "bag_width": 330,
    "bag_weight": 18,
    "bag_max_payload": 5000,
}


BAG_SELECTION_CASE_PRESETS = {
    "maximum-bag-capacity": {
        "label": "Maximum Bag Capacity",
        "config": {
            "mode": "single",
            "action": "run_single",
            "product_l": 300,
            "product_w": 350,
            "product_h": 200,
            "bag_length": 800,
            "bag_width": 800,
        },
    },
    "sealing-and-bag-orientation": {
        "label": "Sealing & Bag Orientation",
        "config": {
            "mode": "single",
            "action": "run_single",
            "product_l": 100,
            "product_w": 50,
            "product_h": 10,
            "bag_length": 130,
            "bag_width": 65,
        },
    },
    "three-dimensional-bag-design": {
        "label": "3D Bag Design",
        "config": {
            "mode": "design",
            "action": "run_design",
            "product_l": 400,
            "product_w": 200,
            "product_h": 200,
            "desired_qty": 12,
        },
    },
    "non-smooth-quantity-design": {
        "label": "Non-Smooth Quantity Design",
        "config": {
            "mode": "design",
            "action": "run_design",
            "product_l": 180,
            "product_w": 120,
            "product_h": 80,
            "desired_qty": 7,
        },
    },
    "bottle-dimensional-allowances": {
        "label": "Bottle & Dimensional Allowances",
        "config": {
            "mode": "single",
            "action": "run_single",
            "product_shape": "bottle",
            "product_l": 63.246,
            "product_w": 63.246,
            "product_h": 254,
            "product_allowance_l": 3.048,
            "product_allowance_w": 3.048,
            "product_allowance_h": 3.048,
            "bag_length": 900,
            "bag_width": 500,
        },
    },
    "imperial-metric-units": {
        "label": "Mixed Imperial and Metric Units",
        "config": {
            "mode": "single",
            "action": "run_single",
            "product_l": 10,
            "product_w": 8,
            "product_h": 6,
            "product_dimension_unit": "cm",
            "product_weight": 1,
            "product_mass_unit": "lb",
            "bag_length": round(convert_length(450, "mm", "in"), 8),
            "bag_width": round(convert_length(330, "mm", "in"), 8),
            "bag_dimension_unit": "in",
            "bag_weight": round(convert_mass(450, "g", "lb"), 9),
            "bag_max_payload": round(convert_mass(5000, "g", "lb"), 9),
            "bag_mass_unit": "lb",
        },
    },
    "pillow-bag-visualization": {
        "label": "Pillow Bag Visualization",
        "config": {**SEO_BAG_SELECTION_EXAMPLE_CONFIG, "product_shape": "pillow_bag"},
    },
}


def get_bag_selection_case_preset(slug):
    """Return an isolated preset payload for a Bag Selection case."""
    preset = BAG_SELECTION_CASE_PRESETS.get(str(slug or "").strip())
    return deepcopy(preset) if preset else None
