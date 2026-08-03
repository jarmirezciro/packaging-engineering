from decimal import Decimal


# These are indicative flute properties used only as calculation aids.  The
# nominal height intentionally remains separate from finished-board caliper.
FLUTE_PROFILES = {
    "A": {
        "nominal_height_mm": Decimal("4.8"),
        "flutes_per_m": 110,
        "take_up_min": Decimal("1.50"),
        "take_up_max": Decimal("1.55"),
        "default_take_up": Decimal("1.525"),
        "glue_per_layer_min_gsm": Decimal("4.5"),
        "glue_per_layer_max_gsm": Decimal("5.0"),
        "default_glue_per_layer_gsm": Decimal("4.75"),
    },
    "B": {
        "nominal_height_mm": Decimal("2.4"),
        "flutes_per_m": 150,
        "take_up_min": Decimal("1.30"),
        "take_up_max": Decimal("1.35"),
        "default_take_up": Decimal("1.325"),
        "glue_per_layer_min_gsm": Decimal("5.5"),
        "glue_per_layer_max_gsm": Decimal("6.0"),
        "default_glue_per_layer_gsm": Decimal("5.75"),
    },
    "C": {
        "nominal_height_mm": Decimal("3.6"),
        "flutes_per_m": 130,
        "take_up_min": Decimal("1.40"),
        "take_up_max": Decimal("1.45"),
        "default_take_up": Decimal("1.43"),
        "glue_per_layer_min_gsm": Decimal("5.0"),
        "glue_per_layer_max_gsm": Decimal("5.5"),
        "default_glue_per_layer_gsm": Decimal("5.0"),
    },
    "E": {
        "nominal_height_mm": Decimal("1.2"),
        "flutes_per_m": 290,
        "take_up_min": Decimal("1.20"),
        "take_up_max": Decimal("1.35"),
        "glue_per_layer_min_gsm": Decimal("6.0"),
        "glue_per_layer_max_gsm": Decimal("6.5"),
        "default_take_up": Decimal("1.275"),
        "default_glue_per_layer_gsm": Decimal("6.25"),
    },
}


def nominal_height_for(flute_1, flute_2=None):
    """Return indicative flute height, never a finished-board caliper."""
    if not flute_1 or flute_1 not in FLUTE_PROFILES:
        return None
    height = FLUTE_PROFILES[flute_1]["nominal_height_mm"]
    if flute_2:
        if flute_2 not in FLUTE_PROFILES:
            return None
        height += FLUTE_PROFILES[flute_2]["nominal_height_mm"]
    return height
