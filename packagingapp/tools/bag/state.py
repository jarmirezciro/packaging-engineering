from decimal import Decimal, InvalidOperation

from ...units import LENGTH_UNITS, convert_length
from ...units.input import validate_unit
from ...utils.bag_selection.engine import DEFAULT_BAG_SIZING
from .film import DEFAULT_FILM_PRESET, catalogue_bag_mode, film_flag


BAG_ALLOWANCE_DEFAULTS_MM = {
    "sealing_allowance": DEFAULT_BAG_SIZING.sealing_allowance_mm,
    "fit_tolerance": DEFAULT_BAG_SIZING.fit_tolerance_mm,
}

BAG_ROTATION_KEYS = ("r1", "r2", "r3")
BAG_PRODUCT_ADVANCED_DEFAULTS = {
    **dict.fromkeys(BAG_ROTATION_KEYS, True),
    "product_advanced_open": False,
}

BAG_FILM_DEFAULTS = {
    "film_preset": DEFAULT_FILM_PRESET,
    "film_preset_override": "0",
    "film_caliper": "",
    "film_caliper_unit": "mil",
    "film_caliper_override": "0",
    "film_grammage": "",
    "film_grammage_override": "0",
    "bag_weight_override": "",
    "bag_advanced_open": "",
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
        **BAG_PRODUCT_ADVANCED_DEFAULTS,
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
        **BAG_FILM_DEFAULTS,
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


def read_bag_film(source, config, *, suffix=""):
    film = {key: source.get(f"{key}{suffix}", config[key]) for key in BAG_FILM_DEFAULTS}
    custom = film["film_preset"] == "custom" and (
        not catalogue_bag_mode(config) or film_flag(film["film_preset_override"])
    )
    for field in ("film_caliper", "film_grammage"):
        if not custom and not film_flag(film[f"{field}_override"]):
            film[field] = ""
    if film["bag_weight_override"] == "0":
        film["bag_weight"] = ""
    return film


def _checked(value):
    return str(value).strip().lower() in {"1", "true", "on", "yes"}


def read_bag_product_advanced(source, config, *, suffix=""):
    """Distinguish a submitted unchecked box from omitted manual permissions."""
    submitted = f"rotation_fields_present{suffix}" in source
    state = {}
    for key, default in BAG_PRODUCT_ADVANCED_DEFAULTS.items():
        saved = config.get(key, default)
        if submitted and key in BAG_ROTATION_KEYS:
            saved = False
        state[key] = _checked(source.get(f"{key}{suffix}", saved))
    return state


def resolve_bag_design_rotations(config, selected_product=None):
    if config.get("product_source") == "catalogue" and selected_product is not None:
        return selected_product.rotation_1, selected_product.rotation_2, selected_product.rotation_3
    return tuple(_checked(config.get(key, True)) for key in BAG_ROTATION_KEYS)
