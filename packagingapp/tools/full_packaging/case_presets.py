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
            "height": 80,
            "max_stack_height": 1350,
            "max_width_stickout": 25.4,
            "max_length_stickout": 25.4,
        },
        "transport": {
            "length": 12032,
            "width": 2352,
            "height": 2698,
            "max_weight": 26000,
            "tare_weight": "",
            "packing_mode": "front_to_back",
            "calculate_max_quantity": True,
            "transport_r1": True,
            "transport_r2": False,
            "transport_r3": False,
            "transport_stackable": True,
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
    },
    "cape-pack-12-carton-two-layouts": {
        "slug": "cape-pack-12-carton-two-layouts",
        "title": "216 or 240 Cartons per Pallet?",
        "description": (
            "A bounded 12-carton CapePack reference case with two shared KolliPack "
            "shipping-case geometries and a linked 48 × 40 in pallet calculation."
        ),
        "display_units": {
            "product_dimension_unit": "in",
            "product_mass_unit": "lb",
            "container_dimension_unit": "in",
            "container_mass_unit": "lb",
            "pallet_dimension_unit": "in",
            "mass_unit": "lb",
        },
        "product": {
            "length": 6,
            "width": 5,
            "height": 8,
            "weight": 2.25,
            "desired_quantity": 12,
            "r1": False,
            "r2": False,
            "r3": True,
        },
        "box_design": {
            "preferred_dimensions": (508, 457.2, 203.2),
            "thickness": 0.16,
            "thickness_unit": "in",
        },
        "pallet": {
            "length": 48,
            "width": 40,
            "height": 5.5,
            "max_stack_height": 50,
            "max_pallet_load": 2000,
            "max_width_stickout": 0,
            "max_length_stickout": 0,
            # The current pallet tool reports carton load and intentionally
            # excludes the empty pallet tare from this constraint.
            "reference_tare_lb": 50,
        },
    },
    "capepack-parameter-fine-tuning": {
        "slug": "capepack-parameter-fine-tuning",
        "title": "CapePack Parameter Fine-Tuning",
        "description": (
            "A bounded 12- and 16-carton CapePack continuation with a 72 in "
            "pallet-height limit and linked case-design and palletization results."
        ),
        "display_units": {
            "product_dimension_unit": "in",
            "product_mass_unit": "lb",
            "container_dimension_unit": "in",
            "container_mass_unit": "lb",
            "pallet_dimension_unit": "in",
            "mass_unit": "lb",
        },
        "product": {
            "length": 6,
            "width": 5,
            "height": 8,
            "weight": 2.25,
            "desired_quantity": 12,
            "r1": True,
            "r2": True,
            "r3": True,
        },
        "box_design": {
            # Canonical internal dimensions from the approved case specification.
            # Candidate selection remains geometry-based; no volatile candidate ID
            # is stored in the preset.
            "preferred_dimensions": (457.2, 203.2, 508.0),
            "thickness": 0.16,
            "thickness_unit": "in",
        },
        "pallet": {
            "length": 48,
            "width": 40,
            "height": 5.5,
            "max_stack_height": 72,
            "max_pallet_load": 2000,
            "max_width_stickout": 0,
            "max_length_stickout": 0,
            "reference_tare_lb": 50,
        },
    },
}


def get_case_preset(slug):
    """Return a defensive copy of one named case, or ``None`` when unknown."""
    preset = _CASE_PRESETS.get(str(slug or "").strip())
    return deepcopy(preset) if preset else None
