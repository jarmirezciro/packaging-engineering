"""Named, public Packaging Flow examples for the compendium and articles.

The preset only describes inputs and the preferred starting alternative. The
shared tool engines remain the single source of calculation logic.
"""

from copy import deepcopy

from ...units import convert_length, convert_mass
from ..bag.case_presets import SEO_BAG_SELECTION_EXAMPLE_CONFIG
from ..container.case_presets import get_container_selection_case_preset


_DEMO_PALLET = {
    "length": 1200,
    "width": 800,
    "height": 144,
    "max_stack_height": 1200,
    "max_width_stickout": 0,
    "max_length_stickout": 0,
}

_DEMO_TRANSPORT = {
    "length": 6000,
    "width": 2500,
    "height": 2600,
    "max_weight": 20000,
    "tare_weight": 1000,
    "packing_mode": "space_evenly",
    "calculate_max_quantity": True,
}

_BAG_DEMO_CARTON = {
    "box_l": 590,
    "box_w": 390,
    "box_h": 250,
    "box_weight": 450,
    "box_thickness_mm": 4,
    "box_max_payload": 15000,
    "r3": "on",
}

_UNIT_DEMO_CARTON = {
    "box_l": 400,
    "box_w": 300,
    "box_h": 250,
    "box_weight": 450,
    "box_max_payload": 35000,
    "r1": "on",
    "r2": "on",
    "r3": "on",
}

_CAPE_BOTTLE_DISPLAY_UNITS = {
    "container_dimension_unit": "in",
    "pallet_dimension_unit": "in",
    "mass_unit": "lb",
}

_CAPE_BOTTLE_PALLET = {
    # Manual equivalent of the captured NA4840 catalogue pallet.
    "length": convert_length(1219, "mm", "in"),
    "width": 40,
    "height": convert_length(141, "mm", "in"),
    "max_stack_height": 50,
    "max_width_stickout": 0,
    "max_length_stickout": 0,
}


def _bottle_carton_design(source_case, *, weight_lb, dimensions_mm, arrangement, **product_overrides):
    config = get_container_selection_case_preset(source_case)["config"]
    config.pop("selected_design_candidate_id", None)
    config.update(
        product_weight=weight_lb,
        product_mass_unit="lb",
        container_mass_unit="lb",
        corrugated_material_id="FEFCO_C_175_140_175",
        **product_overrides,
    )
    return {
        "config": config,
        "preferred_dimensions": dimensions_mm,
        "preferred_arrangement": arrangement,
    }


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
            "transport_r1": False,
            "transport_r2": False,
            "transport_r3": True,
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
    "full-chain-with-bag": {
        "slug": "full-chain-with-bag",
        "title": "Full Chain with Bag",
        "description": (
            "Engineering demonstration using the public Bag Selection example, "
            "a manual shipping carton, a pallet, and a short transport unit."
        ),
        "bag": {**SEO_BAG_SELECTION_EXAMPLE_CONFIG},
        "carton": _BAG_DEMO_CARTON,
        "pallet": _DEMO_PALLET,
        "transport": _DEMO_TRANSPORT,
    },
    "bag-design-final-capacity": {
        "slug": "bag-design-final-capacity",
        "title": "Bag Design Final Capacity",
        "description": (
            "Engineering demonstration for comparing bag designs against the "
            "same downstream carton and pallet. Use Optimize final capacity "
            "to rank alternatives by products per pallet."
        ),
        "bag": {
            "mode": "design",
            "action": "run_design",
            "product_l": 90,
            "product_w": 60,
            "product_h": 20,
            "product_weight": 50,
            "desired_qty": 4,
        },
        "carton": {**_BAG_DEMO_CARTON, "box_h": 375, "box_max_payload": 30000},
        "pallet": _DEMO_PALLET,
    },
    "mixed-units-across-the-chain": {
        "slug": "mixed-units-across-the-chain",
        "title": "Mixed Units Across the Chain",
        "description": (
            "Engineering demonstration based on the unit-equivalence fixture. "
            "Inspect the same physical load as the chain moves between inches, "
            "centimetres, millimetres, feet, grams, kilograms, and pounds."
        ),
        "carton": {
            **_UNIT_DEMO_CARTON,
            "product_l": convert_length(100, "mm", "in"),
            "product_w": convert_length(80, "mm", "in"),
            "product_h": convert_length(60, "mm", "in"),
            "product_dimension_unit": "in",
            "product_weight": 1,
            "product_mass_unit": "lb",
            "box_l": 40,
            "box_w": 30,
            "box_h": 25,
            "container_dimension_unit": "cm",
        },
        "display_units": {
            "pallet_box_dimension_unit": "in",
            "mass_unit": "kg",
            "load_unit_dimension_unit": "ft",
            "load_unit_mass_unit": "lb",
            "transport_dimension_unit": "ft",
            "transport_mass_unit": "lb",
        },
        "pallet": {**_DEMO_PALLET, "max_weight_on_bottom_box": 100},
        "transport": {
            **_DEMO_TRANSPORT,
            **{
                key: convert_length(_DEMO_TRANSPORT[key], "mm", "ft")
                for key in ("length", "width", "height")
            },
            **{
                key: convert_mass(_DEMO_TRANSPORT[key], "kg", "lb")
                for key in ("max_weight", "tare_weight")
            },
        },
    },
    "nested-packaging-chain": {
        "slug": "nested-packaging-chain",
        "title": "Nested Packaging Chain",
        "description": (
            "Engineering demonstration using two Container Selection steps. "
            "The outer carton receives the inner carton's finished dimensions "
            "and gross weight. The product allowance applies at the first step."
        ),
        "carton": {
            **_UNIT_DEMO_CARTON,
            "product_l": 100,
            "product_w": 80,
            "product_h": 60,
            "product_allowance_l": 5,
            "product_weight": 453.59237,
        },
        "outer_carton": {
            "box_l": 820,
            "box_w": 320,
            "box_h": 280,
            "box_weight": 650,
            "box_max_payload": 80000,
            "r3": "on",
        },
        "pallet": _DEMO_PALLET,
        "transport": _DEMO_TRANSPORT,
    },
    "capepack-bottle-24": {
        "slug": "capepack-bottle-24",
        "title": "CapePack Bottle — 24 Units / 1,008 per Pallet",
        "description": (
            "The captured two-tier bottle carton and 42-carton pallet layout, "
            "reproduced with zero overhang. The capture leaves its overhang controls collapsed."
        ),
        "box_design": _bottle_carton_design(
            "bottle-packaging-24", weight_lb=3.19, dimensions_mm=(397.76, 132.59, 508),
            arrangement=(6, 2, 2),
        ),
        "display_units": _CAPE_BOTTLE_DISPLAY_UNITS,
        "pallet": _CAPE_BOTTLE_PALLET,
    },
    "capepack-bottle-15": {
        "slug": "capepack-bottle-15",
        "title": "CapePack Bottle — 15 Units / 1,080 per Pallet",
        "description": (
            "The captured 5 × 3 × 1 bottle carton and four-layer pallet layout "
            "with 1.45 in length and 1 in width overhang allowed."
        ),
        "box_design": _bottle_carton_design(
            "bottle-packaging-15", weight_lb=1.19, dimensions_mm=(335.28, 201.17, 247.65),
            arrangement=(5, 3, 1),
        ),
        "display_units": _CAPE_BOTTLE_DISPLAY_UNITS,
        "pallet": {
            **_CAPE_BOTTLE_PALLET,
            "length": 48,
            "max_width_stickout": 1,
            "max_length_stickout": 1.45,
        },
    },
    "capepack-bottle-20": {
        "slug": "capepack-bottle-20",
        "title": "CapePack Bottle — 20 Units / 960 per Pallet",
        "description": (
            "The captured 5 × 4 × 1 bottle carton and four-layer pallet layout "
            "with zero permitted overhang."
        ),
        "box_design": _bottle_carton_design(
            "bottle-packaging-24", weight_lb=1.19, dimensions_mm=(327.66, 262.13, 260.35),
            arrangement=(5, 4, 1), product_l=2.46, product_w=2.46, product_h=10.25,
            desired_qty=20,
        ),
        "display_units": _CAPE_BOTTLE_DISPLAY_UNITS,
        "pallet": _CAPE_BOTTLE_PALLET,
    },
}


def get_case_preset(slug):
    """Return a defensive copy of one named case, or ``None`` when unknown."""
    preset = _CASE_PRESETS.get(str(slug or "").strip())
    return deepcopy(preset) if preset else None


def get_case_titles():
    """Return compendium links in registry order without exposing preset inputs."""
    return [(slug, preset["title"]) for slug, preset in _CASE_PRESETS.items()]
