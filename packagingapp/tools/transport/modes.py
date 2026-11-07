"""Canonical Transport Container packing-mode names and compatibility aliases."""

SPACE_EVENLY_MODE = "space_evenly"
FRONT_TO_BACK_MODE = "front_to_back"
SPACE_EVENLY_INFILL_MODE = "space_evenly_infill"
FRONT_TO_BACK_INFILL_MODE = "front_to_back_infill"

DEFAULT_TRANSPORT_PACKING_MODE = FRONT_TO_BACK_MODE

TRANSPORT_PACKING_MODE_OPTIONS = (
    {
        "value": SPACE_EVENLY_MODE,
        "label": "Balanced Spread",
        "sequence_locked": True,
        "help": (
            "Distributes products using geometry-based ordering and efficient "
            "product blocks. Loading sequence groups are ignored."
        ),
    },
    {
        "value": FRONT_TO_BACK_MODE,
        "label": "Progressive Fill",
        "sequence_locked": False,
        "help": (
            "Loads products progressively through the container, respecting "
            "loading sequence groups and prioritizing compact product blocks "
            "and efficient residual-space utilization."
        ),
    },
    {
        "value": SPACE_EVENLY_INFILL_MODE,
        "label": "Balanced Spread – Mixed Cargo Infill",
        "sequence_locked": True,
        "help": (
            "Extends Balanced Spread by filling available side and supported-top "
            "spaces with compatible remaining products. Loading sequence groups "
            "are ignored."
        ),
    },
    {
        "value": FRONT_TO_BACK_INFILL_MODE,
        "label": "Progressive Fill – Mixed Cargo Infill",
        "sequence_locked": False,
        "help": (
            "Extends Progressive Fill by filling available side and supported-top "
            "spaces with compatible products while respecting loading sequence "
            "groups and the progressive loading frontier."
        ),
    },
)

TRANSPORT_PACKING_MODE_CHOICES = tuple(
    (option["value"], option["label"])
    for option in TRANSPORT_PACKING_MODE_OPTIONS
)

_MODE_ALIASES = {
    SPACE_EVENLY_MODE: SPACE_EVENLY_MODE,
    "balanced_spread": SPACE_EVENLY_MODE,
    "evenly_spaced": SPACE_EVENLY_MODE,
    "spread_evenly": SPACE_EVENLY_MODE,
    FRONT_TO_BACK_MODE: FRONT_TO_BACK_MODE,
    "progressive_fill": FRONT_TO_BACK_MODE,
    "front_to_back_blocks": FRONT_TO_BACK_MODE,
    "load_front_to_back": FRONT_TO_BACK_MODE,
    "maximum_utilization": FRONT_TO_BACK_MODE,
    "maximum_utilization_floor_first": FRONT_TO_BACK_MODE,
    SPACE_EVENLY_INFILL_MODE: SPACE_EVENLY_INFILL_MODE,
    "balanced_spread_infill": SPACE_EVENLY_INFILL_MODE,
    "balanced_spread_mixed_cargo_infill": SPACE_EVENLY_INFILL_MODE,
    "space_evenly_mixed_cargo_infill": SPACE_EVENLY_INFILL_MODE,
    FRONT_TO_BACK_INFILL_MODE: FRONT_TO_BACK_INFILL_MODE,
    "progressive_fill_infill": FRONT_TO_BACK_INFILL_MODE,
    "progressive_fill_mixed_cargo_infill": FRONT_TO_BACK_INFILL_MODE,
    "load_front_to_back_infill": FRONT_TO_BACK_INFILL_MODE,
    "front_to_back_mixed_cargo_infill": FRONT_TO_BACK_INFILL_MODE,
}

_MODE_LABELS = {
    option["value"]: option["label"]
    for option in TRANSPORT_PACKING_MODE_OPTIONS
}
_SEQUENCE_LOCKED_MODES = {
    option["value"] for option in TRANSPORT_PACKING_MODE_OPTIONS if option["sequence_locked"]
}


def normalize_transport_packing_mode(value, *, default=DEFAULT_TRANSPORT_PACKING_MODE):
    """Return a canonical value while retaining unknown values for diagnostics."""
    if value is None or str(value).strip() == "":
        return default
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return _MODE_ALIASES.get(normalized, normalized)


def transport_packing_mode_label(value):
    canonical = normalize_transport_packing_mode(value)
    return _MODE_LABELS.get(canonical, str(value or canonical))


def transport_sequence_is_locked(value):
    """Return whether this mode uses one common loading sequence group."""
    return normalize_transport_packing_mode(value) in _SEQUENCE_LOCKED_MODES
