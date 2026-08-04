from decimal import Decimal


# These are indicative flute properties used only as calculation aids. The
# nominal height intentionally remains separate from finished-board caliper.
#
# F and N are representative KolliPack selections within the FEFCO-published
# F/G/N profile range. Their profile height excludes facings and is not
# automatically treated as finished-board caliper. Finished-board reference
# caliper is stored separately on each reference-grade record.
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
    "F": {
        "nominal_height_mm": Decimal("0.8"),
        "flutes_per_m": 420,
        "take_up_min": Decimal("1.15"),
        "take_up_max": Decimal("1.25"),
        "default_take_up": Decimal("1.20"),
        "glue_per_layer_min_gsm": Decimal("9.0"),
        "glue_per_layer_max_gsm": Decimal("11.0"),
        "default_glue_per_layer_gsm": Decimal("10.0"),
    },
    "N": {
        "nominal_height_mm": Decimal("0.5"),
        "flutes_per_m": 550,
        "take_up_min": Decimal("1.15"),
        "take_up_max": Decimal("1.25"),
        "default_take_up": Decimal("1.20"),
        "glue_per_layer_min_gsm": Decimal("9.0"),
        "glue_per_layer_max_gsm": Decimal("11.0"),
        "default_glue_per_layer_gsm": Decimal("10.0"),
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


def resolve_reference_flute_family(*, wall_type, flute_1, flute_2=None):
    """Return the supported reference family for a selected construction."""
    if wall_type == "SINGLE_WALL" and flute_1 in {"A", "B", "C", "E", "F", "N"}:
        return flute_1
    if wall_type == "DOUBLE_WALL" and f"{flute_1 or ''}{flute_2 or ''}" in {"EB", "BC"}:
        return f"{flute_1}{flute_2}"
    return None
