from decimal import Decimal, InvalidOperation

from ...units import LENGTH_UNITS, convert_length
from ...units.input import validate_unit
from ...utils.bag_selection.engine import DEFAULT_BAG_SIZING


BAG_ALLOWANCE_DEFAULTS_MM = {
    "sealing_allowance": DEFAULT_BAG_SIZING.sealing_allowance_mm,
    "fit_tolerance": DEFAULT_BAG_SIZING.fit_tolerance_mm,
}


def default_bag_config(bag_dimension_unit="mm"):
    return {
        "mode": "single",
        "action": "",
        "product_source": "manual",
        "product_catalogue_id": "",
        "selected_product_id": "",
        "product_l": "",
        "product_w": "",
        "product_h": "",
        "product_dimension_unit": "mm",
        "product_allowance_l": "0",
        "product_allowance_w": "0",
        "product_allowance_h": "0",
        "product_weight": "",
        "product_mass_unit": "g",
        "desired_qty": "1",
        "product_shape": "cuboid",
        "bag_source": "manual",
        "catalogue_id": "",
        "bag_id": "",
        "bag_length": "",
        "bag_width": "",
        "bag_dimension_unit": bag_dimension_unit,
        **{
            key: format(convert_length(Decimal(str(value)), "mm", bag_dimension_unit).normalize(), "f")
            for key, value in BAG_ALLOWANCE_DEFAULTS_MM.items()
        },
        "bag_weight": "",
        "bag_max_payload": "",
        "bag_mass_unit": "g",
        "selected_design_candidate_id": "",
    }


def read_bag_allowances(source, previous, bag_dimension_unit, *, suffix=""):
    """Read sent values and carry forward omitted fields in the new display unit."""
    previous = previous or {}
    previous_unit = previous.get("bag_dimension_unit")
    values = {}
    for key in BAG_ALLOWANCE_DEFAULTS_MM:
        name = f"{key}{suffix}"
        if name in source:
            values[key] = source[name]
        elif key in previous:
            value = previous[key]
            if bag_dimension_unit != previous_unit:
                try:
                    from_unit = validate_unit(previous_unit, LENGTH_UNITS, "mm", "bag dimension")
                    to_unit = validate_unit(bag_dimension_unit, LENGTH_UNITS, "mm", "bag dimension")
                    value = convert_length(Decimal(str(value)), from_unit, to_unit)
                except (InvalidOperation, TypeError, ValueError, OverflowError):
                    # Retain invalid saved input so the normal validation can flag it.
                    pass
            values[key] = value
    return values
