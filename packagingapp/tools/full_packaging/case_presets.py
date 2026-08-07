"""Named, public Packaging Flow examples used by KolliLabs articles.

The preset only describes inputs and the preferred starting alternative. The
existing shared Container, Palletization, and Transport engines remain the
single source of calculation logic.
"""

from copy import deepcopy


_CASE_PRESETS = {
    "think-beyond-the-box": {
        "slug": "think-beyond-the-box",
        "title": "Think Beyond the Box",
        "description": (
            "A preloaded article case with a 12-unit box design, Euro-pallet "
            "palletization, and 40 ft high-cube container loading."
        ),
        "product": {
            "length": 250,
            "width": 150,
            "height": 100,
            "desired_quantity": 12,
            "r1": True,
            "r2": True,
            "r3": True,
        },
        "box_design": {
            # Article Alternative 7. Selection is resolved from the dimensions,
            # not a stored engine candidate ID, so regenerated IDs remain safe.
            "preferred_dimensions": (600, 250, 300),
        },
        "pallet": {
            "length": 1200,
            "width": 800,
            "max_stack_height": 1200,
            "max_width_stickout": 0,
            "max_length_stickout": 0,
        },
        "transport": {
            "length": 12032,
            "width": 2352,
            "height": 2698,
            "max_weight": 26000,
            "tare_weight": "",
            "packing_mode": "maximum_utilization",
            "calculate_max_quantity": True,
        },
    },
    "tops-product-pallet-optimization": {
        "slug": "tops-product-pallet-optimization",
        "title": "TOPS Product and Pallet Optimization Benchmark",
        "description": (
            "A preloaded 8-product case-pack benchmark using the supplied TOPS "
            "product, pallet, orientation, and carton-caliper assumptions."
        ),
        "product": {
            "length": 153,
            "width": 70,
            "height": 89,
            "weight": 68,
            "desired_quantity": 8,
            "r1": True,
            "r2": False,
            "r3": True,
        },
        "box_design": {
            "preferred_dimensions": (314, 148, 194),
            "thickness_mm": 4,
        },
        "pallet": {
            "length": 1219,
            "width": 1016,
            "height": 127,
            "max_stack_height": 1346,
            "max_width_stickout": 0,
            "max_length_stickout": 0,
        },
        "transport": {
            "length": 12032,
            "width": 2352,
            "height": 2698,
            "max_weight": 26000,
            "tare_weight": "",
            "packing_mode": "maximum_utilization",
            "calculate_max_quantity": True,
        },
    },
}


def get_case_preset(slug):
    """Return a defensive copy of one named case, or ``None`` when unknown."""
    preset = _CASE_PRESETS.get(str(slug or "").strip())
    return deepcopy(preset) if preset else None
