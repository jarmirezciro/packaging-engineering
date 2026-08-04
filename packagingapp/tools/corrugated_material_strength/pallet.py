from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR

from .constants import GRAVITY_M_S2


def _floor(value):
    return int(Decimal(value).to_integral_value(rounding=ROUND_FLOOR))


@dataclass(frozen=True)
class PalletInput:
    pallet_length_mm: Decimal
    pallet_width_mm: Decimal
    pallet_height_mm: Decimal
    pallet_weight_kg: Decimal
    max_palletized_height_mm: Decimal
    box_length_mm: Decimal
    box_width_mm: Decimal
    box_height_mm: Decimal
    gross_packed_box_weight_g: Decimal
    stacked_pallets: int = 1
    pattern: str = "COLUMN_ALIGNED"


def unavailable_pallet_result(reason):
    """Return a structured partial-result state without an internal fallback."""
    return {
        "available": False,
        "status": "External dimensions unavailable",
        "reason": reason,
        "dimension_basis": "EXTERNAL",
        "box_length_used_mm": None,
        "box_width_used_mm": None,
        "box_height_used_mm": None,
        "boxes_per_layer": None,
        "layers": None,
        "boxes_per_pallet": None,
        "palletized_height_mm": None,
        "supported_mass_kg": None,
        "static_load_n": None,
        "warnings": [],
    }


def calculate_pallet(inputs: PalletInput):
    values = (
        inputs.pallet_length_mm,
        inputs.pallet_width_mm,
        inputs.pallet_height_mm,
        inputs.max_palletized_height_mm,
        inputs.box_length_mm,
        inputs.box_width_mm,
        inputs.box_height_mm,
    )
    if any(value <= 0 for value in values[:2] + values[4:]):
        raise ValueError("Pallet and box dimensions must be greater than zero.")
    if inputs.pallet_height_mm < 0:
        raise ValueError("Pallet height cannot be negative.")
    if inputs.max_palletized_height_mm <= inputs.pallet_height_mm:
        raise ValueError("The maximum palletized height does not allow one complete box layer.")
    if inputs.stacked_pallets < 1:
        raise ValueError("Stacked pallets must be at least one.")

    n1_length = _floor(inputs.pallet_length_mm / inputs.box_length_mm)
    n1_width = _floor(inputs.pallet_width_mm / inputs.box_width_mm)
    n1 = n1_length * n1_width
    n2_length = _floor(inputs.pallet_length_mm / inputs.box_width_mm)
    n2_width = _floor(inputs.pallet_width_mm / inputs.box_length_mm)
    n2 = n2_length * n2_width
    if n1 >= n2:
        boxes_per_layer = n1
        orientation = "L along pallet length"
        layer_length = n1_length
        layer_width = n1_width
    else:
        boxes_per_layer = n2
        orientation = "W along pallet length"
        layer_length = n2_length
        layer_width = n2_width
    if boxes_per_layer < 1:
        raise ValueError("The box footprint does not fit on the selected pallet.")

    available_height = inputs.max_palletized_height_mm - inputs.pallet_height_mm
    layers = _floor(available_height / inputs.box_height_mm)
    if layers < 1:
        raise ValueError("The maximum palletized height does not allow one complete box layer.")

    boxes_per_pallet = boxes_per_layer * layers
    palletized_height = inputs.pallet_height_mm + layers * inputs.box_height_mm
    gross_kg = inputs.gross_packed_box_weight_g / Decimal("1000")
    supported_mass = Decimal(max(layers - 1, 0)) * gross_kg
    if inputs.stacked_pallets > 1:
        upper_pallet_mass = Decimal(boxes_per_pallet) * gross_kg + inputs.pallet_weight_kg
        upper_pallets = Decimal(inputs.stacked_pallets - 1)
        upper_per_box = upper_pallets * upper_pallet_mass / Decimal(boxes_per_layer)
    else:
        upper_per_box = Decimal("0")
    supported_total = supported_mass + upper_per_box
    static_load = supported_total * GRAVITY_M_S2

    warnings = []
    if str(inputs.pattern).upper() == "INTERLOCKED":
        warnings.append(
            "Interlocked stacking can reduce real box-compression performance. "
            "This simplified version does not apply an interlock reduction."
        )
    if inputs.stacked_pallets > 1:
        warnings.append(
            "Upper pallet load is assumed to be distributed evenly across the bottom pallet’s boxes."
        )

    return {
        "available": True,
        "status": "Available",
        "dimension_basis": "EXTERNAL",
        "box_length_used_mm": inputs.box_length_mm,
        "box_width_used_mm": inputs.box_width_mm,
        "box_height_used_mm": inputs.box_height_mm,
        "pallet_length_mm": inputs.pallet_length_mm,
        "pallet_width_mm": inputs.pallet_width_mm,
        "pallet_height_mm": inputs.pallet_height_mm,
        "pallet_weight_kg": inputs.pallet_weight_kg,
        "max_palletized_height_mm": inputs.max_palletized_height_mm,
        "selected_orientation": orientation,
        "boxes_per_layer": boxes_per_layer,
        "layer_footprint_length": layer_length,
        "layer_footprint_width": layer_width,
        "layers": layers,
        "boxes_per_pallet": boxes_per_pallet,
        "palletized_height_mm": palletized_height,
        "supported_mass_kg": supported_total,
        "static_load_n": static_load,
        "pattern": str(inputs.pattern).upper(),
        "stacked_pallets": inputs.stacked_pallets,
        "warnings": warnings,
    }
