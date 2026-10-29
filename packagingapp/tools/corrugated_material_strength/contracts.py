from .constants import DEFAULTS, DISTRIBUTION_CHOICES
from .serializers import json_safe
from ...units.ui import build_unit_selector_contract


FIELD_KEYS = (
    "box_dimension_unit", "product_mass_unit", "pallet_dimension_unit",
    "pallet_mass_unit", "material_dimension_unit",
    "box_length_mm", "box_width_mm", "box_height_mm", "product_weight_g",
    "quantity", "fefco_code", "joint_width_mm", "sheet_margin_per_edge_mm",
    "pallet_source", "pallet_code", "pallet_length_mm", "pallet_width_mm",
    "pallet_height_mm", "pallet_weight_kg", "max_palletized_height_mm",
    "pattern", "stacked_pallets", "board_mode", "board_construction_id",
    "manual_wall_type", "manual_flute_1", "manual_flute_2",
    "reference_ect_grade_id",
    "manual_combined_grammage_g_m2", "ect_override_kn_m", "caliper_override_mm",
    "measured_bct_override_n", "distribution_profile", "distribution_factor",
    "co2_mode", "custom_co2_factor_kg_per_kg", "custom_co2_source",
    "custom_co2_boundary",
)


def prefixed_name(prefix, field_name):
    prefix = str(prefix or "").strip("_")
    return f"{prefix}_{field_name}" if prefix else field_name


def prefixed_id(prefix, field_name):
    return prefixed_name(prefix, field_name)


def build_shared_corrugated_material_ui_contract(*, mode="standalone", prefix="", catalogue=None):
    unit_suffix = f"-{prefix}" if str(prefix or "") else ""
    unit_names = {
        key: prefixed_name(prefix, key)
        for key in (
            "box_dimension_unit", "product_mass_unit", "pallet_dimension_unit",
            "pallet_mass_unit", "material_dimension_unit",
        )
    }
    return {
        "mode": mode,
        "prefix": str(prefix or ""),
        "form_action": "",
        "field_ids": {key: prefixed_id(prefix, key) for key in FIELD_KEYS},
        "field_names": {key: prefixed_name(prefix, key) for key in FIELD_KEYS},
        "labels": {
            "box_length_mm": "Internal length",
            "box_width_mm": "Internal width",
            "box_height_mm": "Internal height",
            "product_weight_g": "Product net weight",
            "quantity": "Production quantity",
            "joint_width_mm": "Manufacturer’s joint",
            "sheet_margin_per_edge_mm": "Sheet margin per edge",
            "manual_combined_grammage_g_m2": "Combined grammage",
            "reference_ect_grade_id": "Reference ECT category",
            "ect_override_kn_m": "ECT override",
            "caliper_override_mm": "Actual caliper override",
            "measured_bct_override_n": "Measured BCT override",
            "allowable_supported_force_n": "Maximum supported force above bottom box",
            "allowable_supported_mass_kg": "Maximum supported mass above bottom box",
            "maximum_equivalent_boxes_above": "Equivalent identical packed boxes above",
            "maximum_total_boxes_in_column": "Maximum total boxes in one vertical column",
            "current_boxes_above": "Current boxes above bottom box",
            "current_total_boxes_in_column": "Current total boxes in column",
            "capacity_usage_percent": "Compression-capacity usage",
            "remaining_supported_mass_kg": "Remaining supported mass",
            "remaining_equivalent_boxes": "Remaining equivalent box capacity",
        },
        "unit_selectors": {
            "box_dimensions": build_unit_selector_contract(
                quantity="length",
                label="box and sheet dimension",
                group=f"corrugated-box-dimensions{unit_suffix}",
                hidden_name=unit_names["box_dimension_unit"],
                hidden_id=f"corrugatedBoxDimensionUnit{unit_suffix}",
                menu_id=f"corrugatedBoxDimensionUnitMenu{unit_suffix}",
            ),
            "product_mass": build_unit_selector_contract(
                quantity="mass",
                label="product mass",
                group=f"corrugated-product-mass{unit_suffix}",
                hidden_name=unit_names["product_mass_unit"],
                hidden_id=f"corrugatedProductMassUnit{unit_suffix}",
                menu_id=f"corrugatedProductMassUnitMenu{unit_suffix}",
            ),
            "pallet_dimensions": build_unit_selector_contract(
                quantity="length",
                label="pallet dimension",
                group=f"corrugated-pallet-dimensions{unit_suffix}",
                hidden_name=unit_names["pallet_dimension_unit"],
                hidden_id=f"corrugatedPalletDimensionUnit{unit_suffix}",
                menu_id=f"corrugatedPalletDimensionUnitMenu{unit_suffix}",
            ),
            "pallet_mass": build_unit_selector_contract(
                quantity="mass",
                label="pallet mass",
                group=f"corrugated-pallet-mass{unit_suffix}",
                hidden_name=unit_names["pallet_mass_unit"],
                hidden_id=f"corrugatedPalletMassUnit{unit_suffix}",
                menu_id=f"corrugatedPalletMassUnitMenu{unit_suffix}",
            ),
            "material_dimensions": build_unit_selector_contract(
                quantity="length",
                label="board material dimension",
                group=f"corrugated-material-dimensions{unit_suffix}",
                hidden_name=unit_names["material_dimension_unit"],
                hidden_id=f"corrugatedMaterialDimensionUnit{unit_suffix}",
                menu_id=f"corrugatedMaterialDimensionUnitMenu{unit_suffix}",
            ),
        },
        "help_text": {
            "box_dimensions": "Preliminary geometry uses entered internal dimensions directly; converter allowances are not included.",
            "reference_ect_grade": "Reference ECT categories are industry screening classes. Actual ECT depends on the complete paper construction and manufacturing performance.",
            "strength": "Supplier or measured values take priority over reference data. McKee remains a screening estimate.",
            "capacity": "Equivalent-box capacity is a preliminary compression-strength screening value for one vertical load column, not a recommended physical stack height.",
            "distribution": "The distribution factor is a simplified screening allowance. It is not a detailed humidity, creep or vibration model.",
            "carbon": "Material-based CO₂ screening estimate; not a formal product carbon footprint.",
        },
        "options": {
            "fefco": [("0201", "FEFCO 0201 — regular slotted case")],
            "distribution": list(DISTRIBUTION_CHOICES),
            "patterns": [("COLUMN_ALIGNED", "Column aligned"), ("INTERLOCKED", "Interlocked (same load model)")],
        },
        "defaults": json_safe(dict(DEFAULTS)),
        "visibility": {
            "catalogue_board": True, "manual_board": False,
            "catalogue_pallet": False, "manual_pallet": True,
            "custom_distribution": False, "custom_carbon": False,
        },
        "catalogue": catalogue or {"boards": [], "pallets": []},
    }


# Explicitly named alias for callers following the task brief.
_build_shared_corrugated_material_ui_contract = build_shared_corrugated_material_ui_contract
