"""Canonical Transport Container packing-mode names and compatibility aliases."""

SPACE_EVENLY_MODE = "space_evenly"
FRONT_TO_BACK_MODE = "front_to_back"
SPACE_EVENLY_INFILL_MODE = "space_evenly_infill"
FRONT_TO_BACK_INFILL_MODE = "front_to_back_infill"

DEFAULT_TRANSPORT_PACKING_MODE = FRONT_TO_BACK_MODE

TRANSPORT_PACKING_MODE_OPTIONS = (
    {
        "value": SPACE_EVENLY_MODE,
        "label": "Space Evenly",
        "help": (
            "Creates strong product blocks and distributes cargo using the "
            "Space Evenly loading strategy."
        ),
    },
    {
        "value": FRONT_TO_BACK_MODE,
        "label": "Load Front-to-Back",
        "help": (
            "Creates strong product blocks and fills the load progressively "
            "from the back toward the doors."
        ),
    },
    {
        "value": SPACE_EVENLY_INFILL_MODE,
        "label": "Space Evenly – Mixed Cargo Infill",
        "help": (
            "Uses Space Evenly as the main loading strategy and fills bounded "
            "side residuals with compatible remaining products. Explicit "
            "sequence groups are respected."
        ),
    },
    {
        "value": FRONT_TO_BACK_INFILL_MODE,
        "label": "Load Front-to-Back – Mixed Cargo Infill",
        "help": (
            "Uses Load Front-to-Back as the main strategy and fills compatible "
            "side residuals while preserving the active loading frontier. "
            "Explicit sequence groups are respected."
        ),
    },
)

TRANSPORT_PACKING_MODE_CHOICES = tuple(
    (option["value"], option["label"])
    for option in TRANSPORT_PACKING_MODE_OPTIONS
)

_MODE_ALIASES = {
    SPACE_EVENLY_MODE: SPACE_EVENLY_MODE,
    "evenly_spaced": SPACE_EVENLY_MODE,
    "spread_evenly": SPACE_EVENLY_MODE,
    FRONT_TO_BACK_MODE: FRONT_TO_BACK_MODE,
    "front_to_back_blocks": FRONT_TO_BACK_MODE,
    "load_front_to_back": FRONT_TO_BACK_MODE,
    "maximum_utilization": FRONT_TO_BACK_MODE,
    "maximum_utilization_floor_first": FRONT_TO_BACK_MODE,
    SPACE_EVENLY_INFILL_MODE: SPACE_EVENLY_INFILL_MODE,
    "space_evenly_mixed_cargo_infill": SPACE_EVENLY_INFILL_MODE,
    FRONT_TO_BACK_INFILL_MODE: FRONT_TO_BACK_INFILL_MODE,
    "load_front_to_back_infill": FRONT_TO_BACK_INFILL_MODE,
    "front_to_back_mixed_cargo_infill": FRONT_TO_BACK_INFILL_MODE,
}

_MODE_LABELS = {
    option["value"]: option["label"]
    for option in TRANSPORT_PACKING_MODE_OPTIONS
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
    """Approved baseline modes intentionally use one common sequence group."""
    return normalize_transport_packing_mode(value) in {
        SPACE_EVENLY_MODE,
        FRONT_TO_BACK_MODE,
    }
