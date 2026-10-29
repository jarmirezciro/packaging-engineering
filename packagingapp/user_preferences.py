"""Account unit defaults and initialization rules.

These helpers are intentionally limited to presentation-state initialization.
They never alter canonical catalogue, workflow, service, engine, or report
values.
"""

from .models import UserPreferences
from .units import LENGTH_UNITS, MASS_UNITS, normalize_unit


LEGACY_UNIT_DEFAULTS = {
    "length": "mm",
    "small_mass": "g",
    "large_mass": "kg",
}

PREFERENCE_FIELD_DEFAULTS = {
    "default_length_unit": (LENGTH_UNITS, "mm"),
    "default_small_mass_unit": (MASS_UNITS, "g"),
    "default_large_mass_unit": (MASS_UNITS, "kg"),
}

TOOL_UNIT_FIELDS = {
    "container": {
        "length": ("product_dimension_unit", "container_dimension_unit"),
        "small_mass": ("product_mass_unit", "container_mass_unit"),
    },
    "bag": {
        "length": ("product_dimension_unit", "bag_dimension_unit"),
        "small_mass": ("product_mass_unit", "bag_mass_unit"),
    },
    "palletization": {
        "length": ("box_dimension_unit", "pallet_dimension_unit"),
        "small_mass": ("mass_unit",),
    },
    "transport": {
        "length": ("load_unit_dimension_unit", "transport_dimension_unit"),
        "large_mass": ("load_unit_mass_unit", "transport_mass_unit"),
    },
    "corrugated": {
        "length": (
            "box_dimension_unit",
            "pallet_dimension_unit",
            "material_dimension_unit",
        ),
        "small_mass": ("product_mass_unit",),
        "large_mass": ("pallet_mass_unit",),
    },
}


def _is_authenticated(user):
    return bool(user is not None and getattr(user, "is_authenticated", False))


def unit_defaults_for_user(user):
    """Return validated unit defaults, with safe legacy fallback."""
    defaults = dict(LEGACY_UNIT_DEFAULTS)
    if not _is_authenticated(user):
        return defaults

    preferences = UserPreferences.objects.filter(user=user).first()
    if preferences is None:
        return defaults

    for field_name, (definitions, fallback) in PREFERENCE_FIELD_DEFAULTS.items():
        key = {
            "default_length_unit": "length",
            "default_small_mass_unit": "small_mass",
            "default_large_mass_unit": "large_mass",
        }[field_name]
        try:
            defaults[key] = normalize_unit(
                getattr(preferences, field_name, None), definitions, fallback
            )
        except (TypeError, ValueError):
            # Invalid legacy/tampered rows must not break public tools or a
            # user's account.  The settings form still rejects invalid input.
            defaults[key] = fallback
    return defaults


def apply_user_unit_defaults(config, user, tool, *, replace_legacy=False):
    """Initialize missing unit state without overwriting explicit state.

    ``replace_legacy`` is used only when a brand-new config is being built from
    a historical metric template.  Existing posted/session/workflow state uses
    the normal missing-only behavior and therefore always wins.
    """
    if not isinstance(config, dict) or not _is_authenticated(user):
        return config

    defaults = unit_defaults_for_user(user)
    fields = TOOL_UNIT_FIELDS.get(tool, {})
    for preference_key, field_names in fields.items():
        legacy_value = LEGACY_UNIT_DEFAULTS[preference_key]
        for field_name in field_names:
            current = config.get(field_name)
            if current in (None, "") or (replace_legacy and current == legacy_value):
                config[field_name] = defaults[preference_key]
    return config
