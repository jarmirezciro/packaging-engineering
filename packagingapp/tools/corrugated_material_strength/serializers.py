import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal


INPUT_KEYS = (
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

RESULT_KEYS = (
    "reference_grade_code", "reference_flute_family", "reference_ect_lb_in",
    "reference_ect_kn_m", "reference_caliper_mm", "reference_caliper_basis",
    "reference_source_label", "reference_source_url", "reference_data_used",
    "allowable_supported_force_n", "allowable_supported_mass_kg",
    "maximum_equivalent_boxes_above", "maximum_total_boxes_in_column",
    "current_boxes_above", "current_total_boxes_in_column",
    "current_equivalent_boxes_above", "remaining_supported_force_n",
    "remaining_supported_mass_kg", "remaining_equivalent_boxes",
    "capacity_usage_percent", "is_overloaded", "overload_force_n",
    "overload_mass_kg", "overload_equivalent_boxes", "capacity_basis",
    "capacity_is_reference_based",
)


def json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if is_dataclass(value):
        return {key: json_safe(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def serialize_corrugated_inputs(cleaned_data):
    payload = {key: cleaned_data.get(key) for key in INPUT_KEYS}
    return json_safe(payload)


def serialize_corrugated_result(result):
    payload = json_safe(result)
    json.dumps(payload)
    return payload
