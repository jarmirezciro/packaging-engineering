"""Named Transport Container examples and fixture-backed regression inputs."""

from copy import deepcopy


TRANSPORT_CONTAINER_CASE_PRESETS = {
    "mix_load_case_hight_cube": {
        "label": "Mix Load High Cube Case",
        "config": {
            "container_source": "manual",
            "container_l": 12032,
            "container_w": 2352,
            "container_h": 2395,
            "max_weight": 26500,
            "tare_weight": "",
            "packing_mode": "front_to_back",
        },
        "rows": [
            {
                "name": "EUR palletized load",
                "length": 1200,
                "width": 800,
                "height": 1100,
                "qty": 20,
                "max_qty": False,
                "stackable": True,
                "weight": 900,
                "sequence": 1,
                "r1": False,
                "r2": False,
                "r3": True,
            },
            {
                "name": "Product 2",
                "length": 500,
                "width": 400,
                "height": 700,
                "qty": 100,
                "max_qty": False,
                "stackable": True,
                "weight": 0,
                "sequence": 1,
                "r1": False,
                "r2": False,
                "r3": True,
            },
            {
                "name": "Product 3",
                "length": 500,
                "width": 200,
                "height": 700,
                "qty": 100,
                "max_qty": False,
                "stackable": True,
                "weight": 0,
                "sequence": 1,
                "r1": False,
                "r2": False,
                "r3": True,
            },
        ],
    },
    "tops-max-load-high-cube-benchmark": {
        "label": "TOPS Max Load High Cube Benchmark",
        "config": {
            "container_source": "manual",
            "container_l": 12039,
            "container_w": 2362,
            "container_h": 2692,
            "max_weight": "",
            "tare_weight": "",
            "packing_mode": "front_to_back",
        },
        "rows": [
            {
                "name": "SKU302473",
                "length": 457.2,
                "width": 279.4,
                "height": 317.5,
                "qty": 375,
                "max_qty": False,
                "stackable": True,
                "weight": 0.2427,
                "sequence": 4,
                "r1": False,
                "r2": False,
                "r3": True,
            },
            {
                "name": "SKU503739",
                "length": 431.8,
                "width": 318.77,
                "height": 317.5,
                "qty": 405,
                "max_qty": False,
                "stackable": True,
                "weight": 0.907,
                "sequence": 3,
                "r1": False,
                "r2": False,
                "r3": True,
            },
            {
                "name": "Case Pack 12",
                "length": 558.8,
                "width": 377.444,
                "height": 317.5,
                "qty": 288,
                "max_qty": False,
                "stackable": True,
                "weight": 0.907,
                "sequence": 1,
                "r1": False,
                "r2": False,
                "r3": True,
            },
            {
                "name": "Case Pack",
                "length": 558.8,
                "width": 355.6,
                "height": 381.0,
                "qty": 160,
                "max_qty": False,
                "stackable": True,
                "weight": 2.268,
                "sequence": 2,
                "r1": False,
                "r2": False,
                "r3": True,
            },
        ],
    },
    "easycargo-40hc-mixed-cargo-benchmark": {
        "label": "EasyCargo 40' HC Mixed-Cargo Reproduction",
        "config": {
            "container_source": "manual",
            "container_l": 12117,
            "container_w": 2388,
            "container_h": 2694,
            "max_weight": "",
            "tare_weight": "",
            "packing_mode": "front_to_back_infill",
            "load_unit_dimension_unit": "mm",
            "load_unit_mass_unit": "kg",
            "transport_dimension_unit": "mm",
            "transport_mass_unit": "kg",
        },
        "rows": [
            {
                "name": "Microwave WH352",
                "length": 414, "width": 503, "height": 400,
                "qty": 220, "max_qty": False, "weight": 9.3,
                "sequence": 1, "r1": True, "r2": True, "r3": True,
                "stackable": True,
            },
            {
                "name": "Breather pipe 15A",
                "length": 2500, "width": 150, "height": 150,
                "qty": 130, "max_qty": False, "weight": 2.4,
                "sequence": 1, "r1": False, "r2": False, "r3": True,
                "stackable": True,
            },
            {
                "name": "Microwave WD102",
                "length": 380, "width": 420, "height": 370,
                "qty": 193, "max_qty": False, "weight": 7.0,
                "sequence": 2, "r1": True, "r2": True, "r3": True,
                "stackable": True,
            },
            {
                "name": "Fridge Alhambra R3",
                "length": 570, "width": 576, "height": 500,
                "qty": 58, "max_qty": False, "weight": 58.0,
                "sequence": 2, "r1": False, "r2": False, "r3": True,
                "stackable": True,
            },
            {
                "name": "Ceramic stove 45-LOC-13",
                "length": 350, "width": 360, "height": 80,
                "qty": 26, "max_qty": False, "weight": 2.9,
                "sequence": 3, "r1": True, "r2": True, "r3": True,
                "stackable": False,
            },
            {
                "name": "Microwave RW 230",
                "length": 380, "width": 420, "height": 370,
                "qty": 193, "max_qty": False, "weight": 7.0,
                "sequence": 3, "r1": True, "r2": True, "r3": True,
                "stackable": True,
            },
            {
                "name": "Freezer BD53V",
                "length": 570, "width": 300, "height": 200,
                "qty": 58, "max_qty": False, "weight": 58.0,
                "sequence": 3, "r1": True, "r2": True, "r3": True,
                "stackable": True,
            },
        ],
    },
    "48ft-semitrailer-3stop-benchmark": {
        "label": "48-ft Semitrailer — 3-Stop Mixed Cargo Benchmark",
        "config": {
            "container_source": "manual",
            "container_l": 566.9,
            "container_w": 98.5,
            "container_h": 108,
            "max_weight": "",
            "tare_weight": "",
            "packing_mode": "front_to_back_infill",
            "load_unit_dimension_unit": "in",
            "load_unit_mass_unit": "lb",
            "transport_dimension_unit": "in",
            "transport_mass_unit": "lb",
        },
        "rows": [
            {
                "name": "A",
                "length": 15.7, "width": 55.1, "height": 63,
                "qty": 30, "max_qty": False, "weight": 88.11,
                "sequence": 1, "r1": False, "r2": False, "r3": True,
                "stackable": True,
            },
            {
                "name": "B",
                "length": 63, "width": 23.6, "height": 39.4,
                "qty": 17, "max_qty": False, "weight": 191.93,
                "sequence": 2, "r1": False, "r2": False, "r3": True,
                "stackable": True,
            },
            {
                "name": "C",
                "length": 23.6, "width": 17.7, "height": 51.2,
                "qty": 16, "max_qty": False, "weight": 1198.76,
                "sequence": 2, "r1": False, "r2": False, "r3": True,
                "stackable": True,
            },
            {
                "name": "D",
                "length": 31.5, "width": 47.2, "height": 15.7,
                "qty": 48, "max_qty": False, "weight": 11.02,
                "sequence": 3, "r1": False, "r2": False, "r3": True,
                "stackable": True,
            },
            {
                "name": "E",
                "length": 47.2, "width": 47.2, "height": 21.7,
                "qty": 14, "max_qty": False, "weight": 1375.67,
                "sequence": 3, "r1": False, "r2": False, "r3": True,
                "stackable": True,
            },
            {
                "name": "F",
                "length": 47.2, "width": 47.2, "height": 21.7,
                "qty": 4, "max_qty": False, "weight": 661.38,
                "sequence": 3, "r1": False, "r2": False, "r3": True,
                "stackable": True,
            },
            {
                "name": "G",
                "length": 47.2, "width": 47.2, "height": 21.7,
                "qty": 4, "max_qty": False, "weight": 165.35,
                "sequence": 3, "r1": False, "r2": False, "r3": True,
                "stackable": True,
            },
        ],
    },
    # Existing imperial service check, not a reconstruction of the hidden truck
    # inputs: artifacts/transport-supported-top/evidence.json,
    # equivalent_unit_checks[0].imperial_input (TC-REG-013/015).
    "p1-p2-imperial-supported-roof": {
        "label": "P1/P2 Upper Residual — Imperial Supported-Roof Fixture",
        "config": {
            "container_source": "manual",
            "container_l": 275.5,
            "container_w": 94.2,
            "container_h": 108.01,
            "max_weight": "",
            "tare_weight": "",
            "packing_mode": "front_to_back_infill",
            "load_unit_dimension_unit": "in",
            "load_unit_mass_unit": "kg",
            "transport_dimension_unit": "in",
            "transport_mass_unit": "kg",
        },
        "rows": [
            {
                "name": "Support",
                "length": 275.5, "width": 94.2, "height": 63,
                "qty": 1, "max_qty": False, "weight": 0,
                "sequence": 1, "r1": False, "r2": False, "r3": True,
                "stackable": True,
            },
            {
                "name": "Cargo",
                "length": 63, "width": 23.6, "height": 39.44,
                "qty": 17, "max_qty": False, "weight": 2,
                "sequence": 1, "r1": False, "r2": False, "r3": True,
                "stackable": True,
            },
        ],
    },
    # TC-REG-005: test_transport_adaptive_mixed_lane.
    # test_perturbed_pallet_builds_unequal_lane_tails_and_loads_25.
    # The 801 mm width is deliberate; this is not a standard 800 mm pallet.
    "40hc-euro-pallet-unequal-lane-tails": {
        "label": "40HC Euro Pallet — Unequal Lane Tails (1200 × 801 mm)",
        "config": {
            "container_source": "manual",
            "container_l": 12032,
            "container_w": 2352,
            "container_h": 2698,
            "max_weight": "",
            "tare_weight": "",
            "packing_mode": "front_to_back",
            "load_unit_dimension_unit": "mm",
            "load_unit_mass_unit": "kg",
            "transport_dimension_unit": "mm",
            "transport_mass_unit": "kg",
        },
        "rows": [
            {
                "name": "Test load",
                "length": 1200, "width": 801, "height": 144,
                "qty": 30, "max_qty": False, "weight": 1,
                "sequence": 1, "r1": False, "r2": False, "r3": True,
                "stackable": False,
            },
        ],
    },
}


# Reuse the existing benchmark inputs for constraint variants. Keep the four
# original presets unchanged; the normal tool supplies strategy switching.
# TC-REG-003/004: test_transport_front_to_back.primary_case_products(). The
# common group enables the P4/P2 Native and P2/P1 DGFE transitions; the article
# preset instead separates those products into four loading groups.
_tops_dgfe = deepcopy(TRANSPORT_CONTAINER_CASE_PRESETS["tops-max-load-high-cube-benchmark"])
_tops_dgfe["label"] = "TOPS DGFE — Shared Loading Group Frontier Regression"
for _row in _tops_dgfe["rows"]:
    _row["sequence"] = 1
TRANSPORT_CONTAINER_CASE_PRESETS["tops-dgfe-shared-loading-group"] = _tops_dgfe

# TC-REG-001: EasyCargoEngineTests.benchmark_inputs(all_rotations=False).
_easycargo_r3 = deepcopy(TRANSPORT_CONTAINER_CASE_PRESETS["easycargo-40hc-mixed-cargo-benchmark"])
_easycargo_r3["label"] = "EasyCargo 40' HC — R3-Only DGFE Regression"
for _row in _easycargo_r3["rows"]:
    _row.update(r1=False, r2=False, r3=True)
TRANSPORT_CONTAINER_CASE_PRESETS["easycargo-40hc-r3-only-dgfe"] = _easycargo_r3

# TC-REG-017: test_transport_mixed_cargo_infill.stackability_expv2_2().
# Preserve that rounded task reconstruction in its original inches/pounds;
# its documented helper converts these same inputs to canonical mm/kg.
_support_beds = deepcopy(TRANSPORT_CONTAINER_CASE_PRESETS["48ft-semitrailer-3stop-benchmark"])
_support_beds["label"] = "48-ft Semitrailer — ExpV2-2 Support Beds (Reconstruction)"
_support_beds["rows"][0].update(length=15.75, width=55.15)
for _index, _row in enumerate(_support_beds["rows"]):
    _row.update(
        sequence=1 if _index < 3 else 3,
        r1=True, r2=True, r3=True,
        stackable=_index not in (1, 4),
    )
TRANSPORT_CONTAINER_CASE_PRESETS["48ft-semitrailer-expv2-2-support-beds"] = _support_beds


def get_transport_container_case_preset(slug):
    """Return an isolated preset payload for a Transport example or regression."""
    preset = TRANSPORT_CONTAINER_CASE_PRESETS.get(str(slug or "").strip())
    return deepcopy(preset) if preset else None
