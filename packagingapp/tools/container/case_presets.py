from copy import deepcopy


_UPRIGHT_BOTTLE_DESIGN = {
    "mode": "design",
    "action": "run_design",
    "product_shape": "bottle",
    "product_dimension_unit": "in",
    "product_allowance_l": 0.12,
    "product_allowance_w": 0.12,
    "product_allowance_h": "0",
    "r1": False,
    "r2": False,
    "r3": True,
    "container_dimension_unit": "in",
    "box_thickness_mm": 0.16,  # This form field uses the active container unit.
    "box_thickness_user_override": "1",
}


CONTAINER_SELECTION_CASE_PRESETS = {
    # Historical rectangular-subbox example in docs/research/benchmarks.md.
    "mosaic-packing-benchmark": {
        "label": "Mosaic Packing Benchmark",
        "product_dimensions_display": "130 × 70 × 30 mm",
        "container_dimensions_display": "500 × 300 × 200 mm",
        "config": {
            "mode": "single",
            "action": "run_single",
            "product_l": 130,
            "product_w": 70,
            "product_h": 30,
            "box_l": 500,
            "box_w": 300,
            "box_h": 200,
            "r1": True,
            "r2": True,
            "r3": True,
        },
    },
    "product-orientation-capacity": {
        "label": "Product Orientation Capacity",
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
    # reference_imperial_equivalent in the shared Mosaic benchmark fixture.
    "pinwheel-packing-benchmark": {
        "label": "Pinwheel Packing Benchmark",
        "product_dimensions_display": "152.4 × 101.6 × 152.4 mm",
        "container_dimensions_display": "384.81 × 368.3 × 342.9 mm",
        "config": {
            "mode": "single",
            "action": "run_single",
            "product_l": 152.4,
            "product_w": 101.6,
            "product_h": 152.4,
            "box_l": 384.81,
            "box_w": 368.3,
            "box_h": 342.9,
            "r1": False,
            "r2": False,
            "r3": True,
        },
    },
    "capepack-perimeter-core-10": {
        "label": "Cape Pack Perimeter-Core Mosaic: 10 Cartons",
        "product_dimensions_display": "18.32 × 8.64 × 20.32 in",
        "container_dimensions_display": "48 × 40 × 20.32 in usable",
        "config": {
            "mode": "single",
            "action": "run_single",
            "product_dimension_unit": "in",
            "product_l": 18.32,
            "product_w": 8.64,
            "product_h": 20.32,
            "container_dimension_unit": "in",
            "box_l": 48,
            "box_w": 40,
            "box_h": 20.32,
            "r1": False,
            "r2": False,
            "r3": True,
        },
    },
    # KolliPack inputs from the CapePack bottle benchmark article, cases A and B.
    "bottle-packaging-24": {
        "label": "Bottle Packaging — 24 Units",
        "product_dimensions_display": "2.49 × 2.49 × 10 in",
        "container_dimensions_display": "15.66 × 5.22 × 20 in",
        "config": {
            **_UPRIGHT_BOTTLE_DESIGN,
            "product_l": 2.49,
            "product_w": 2.49,
            "product_h": 10,
            "desired_qty": 24,
            # Select the documented 6 × 2 × 2 arrangement.
            "selected_design_candidate_id": "container-design-864beee47bd29be8",
        },
    },
    "bottle-packaging-15": {
        "label": "Bottle Packaging — 15 Units",
        "product_dimensions_display": "2.52 × 2.52 × 9.75 in",
        "container_dimensions_display": "13.2 × 7.92 × 9.75 in",
        "config": {
            **_UPRIGHT_BOTTLE_DESIGN,
            "product_l": 2.52,
            "product_w": 2.52,
            "product_h": 9.75,
            "desired_qty": 15,
            # Select the documented 5 × 3 × 1 arrangement.
            "selected_design_candidate_id": "container-design-6fc031013e539628",
        },
    },
    # Existing asymmetric seven-unit Design fixture in test_product_shape_visualization.
    "design-mode-quantity-optimization": {
        "label": "Design Mode Quantity Optimization",
        "product_dimensions_display": "180 × 120 × 80 mm",
        "container_dimensions_display": "240 × 180 × 320 mm",
        "config": {
            "mode": "design",
            "action": "run_design",
            "product_l": 180,
            "product_w": 120,
            "product_h": 80,
            "desired_qty": 7,
            "r1": True,
            "r2": True,
            "r3": True,
        },
    },
}


def get_container_selection_case_preset(slug):
    """Return an isolated preset payload for a Container Selection case."""
    preset = CONTAINER_SELECTION_CASE_PRESETS.get(str(slug or "").strip())
    return deepcopy(preset) if preset else None
