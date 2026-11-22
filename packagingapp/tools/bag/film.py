"""Single-ply film properties and finished-bag tare for lay-flat stock."""

from dataclasses import dataclass
from decimal import Decimal, DecimalException
from math import isfinite
from types import MappingProxyType

from ...units import FILM_THICKNESS_UNIT_OPTIONS, MASS_UNITS, convert_film_thickness, convert_mass
from ...units.input import validate_unit


FILM_FAMILIES = (("ldpe", "LDPE"), ("pp", "Polypropylene (PP)"), ("custom", "Custom film"))
BAG_CONSTRUCTIONS = (("two_wall", "Simple non-gusseted two-wall bag"), ("other", "Other construction"))
DEFAULT_FILM_PRESET = "ldpe_1_2"
FILM_DENSITIES = {"ldpe": Decimal("0.920"), "pp": Decimal("0.900")}
FILM_UNITS = {option["value"]: option["symbol"] for option in FILM_THICKNESS_UNIT_OPTIONS}
FILM_SOURCES = {
    "preset": "Material preset",
    "calculated": "Calculated from caliper × density",
    "catalogue_property": "Catalogue specification",
    "user_property": "User specified",
    "manual_override": "Manual override",
    "catalogue_actual": "Actual catalogue weight",
    "estimated_catalogue": "Estimated from catalogue film",
    "estimated_material": "Estimated from film properties",
    "unavailable": "Unavailable",
}


@dataclass(frozen=True)
class FilmPreset:
    family: str
    caliper: str
    unit: str

    @property
    def label(self):
        return f"{self.family.upper()} — {self.caliper} {FILM_UNITS[self.unit]}"

    @property
    def caliper_mm(self):
        return convert_film_thickness(Decimal(self.caliper), self.unit, "mm")


FILM_PRESETS = MappingProxyType({
    "ldpe_1": FilmPreset("ldpe", "1.0", "mil"),
    "ldpe_1_2": FilmPreset("ldpe", "1.2", "mil"),
    "ldpe_1_5": FilmPreset("ldpe", "1.5", "mil"),
    "ldpe_2": FilmPreset("ldpe", "2.0", "mil"),
    "ldpe_3": FilmPreset("ldpe", "3.0", "mil"),
    **{f"pp_{size}": FilmPreset("pp", str(size), "um") for size in (20, 25, 30, 40, 50)},
})
FILM_PRESET_CHOICES = (
    *((key, preset.label) for key, preset in FILM_PRESETS.items()),
    ("custom", "Custom film properties"),
    ("legacy", "Film properties unavailable"),
)


def film_flag(value):
    return str(value).lower() in {"1", "true", "on"}


def catalogue_bag_mode(config):
    mode = config.get("mode")
    return mode == "optimal" or (mode != "design" and config.get("bag_source") == "catalogue")


def bag_weight_overridden(config):
    explicit = config.get("bag_weight_override")
    if explicit not in ("", None):
        return film_flag(explicit)
    # Before the checkbox existed, entering a manual tare was the override.
    return not catalogue_bag_mode(config) and config.get("bag_weight") not in (None, "", "None")


def _positive_decimal(value, label, *, required=False):
    if value in (None, "", "None") and not required:
        return None
    try:
        number = Decimal(str(value))
        numeric = float(number)
        if number.is_finite() and isfinite(numeric) and numeric > 0:
            return number
    except (DecimalException, ValueError, TypeError, OverflowError):
        pass
    if required:
        raise ValueError(f"{label} must be a finite number greater than zero.")
    return None


def _attribute(material, field, label):
    return _positive_decimal(getattr(material, field, None), label)


def _validate_result(value):
    if value is not None and (not isfinite(float(value)) or float(value) <= 0):
        raise ValueError("Calculated film properties are outside the supported numeric range.")
    return float(value) if value is not None else None


def catalogue_bag_weight_g(material):
    tare = _attribute(material, "bag_actual_weight_g", "Actual bag weight")
    legacy_weight = _attribute(material, "part_weight", "Actual bag weight")
    if tare is None and legacy_weight is not None:
        return convert_mass(legacy_weight, "kg", "g")
    return tare


def resolve_bag_film(config, flat_dimensions=None, material=None):
    """Resolve validated film and tare data as JSON-safe values in mm, m² and g."""
    catalogue = catalogue_bag_mode(config)
    preset_id = config.get("film_preset", DEFAULT_FILM_PRESET)
    preset = FILM_PRESETS.get(preset_id)
    if preset is None and preset_id not in ("custom", "legacy"):
        raise ValueError("Select a supported film material.")
    unit = validate_unit(config.get("film_caliper_unit"), FILM_UNITS, "mil", "film caliper")
    use_catalogue = catalogue and not film_flag(config.get("film_preset_override"))
    construction = getattr(material, "bag_construction", None) if catalogue else "two_wall"
    simple = construction == "two_wall" or (catalogue and not use_catalogue and not construction)
    caliper = grammage = density = None
    family = ""
    caliper_source = grammage_source = "unavailable"

    if use_catalogue:
        family = getattr(material, "bag_film_family", None) or ""
        caliper = _attribute(material, "bag_film_caliper_mm", "Catalogue film caliper")
        has_carton_spec = getattr(material, "carton_style", None) or getattr(material, "corrugated_construction_id", None)
        # An explicitly confirmed bag with no carton specification can reuse
        # legacy values entered when the catalogue had only a generic caliper.
        if simple and not has_carton_spec:
            legacy_caliper = _attribute(material, "box_thickness_mm", "Catalogue film caliper")
            caliper = caliper or legacy_caliper
        if not has_carton_spec:
            grammage = _attribute(material, "combined_grammage_g_m2", "Catalogue film grammage")
        caliper_source = "catalogue_property" if caliper is not None else "unavailable"
        grammage_source = "catalogue_property" if grammage is not None else "unavailable"
    elif preset:
        family = preset.family
        density = FILM_DENSITIES[family]
        caliper = preset.caliper_mm
        caliper_source = "preset"
    elif preset_id == "custom":
        family = "custom"

    custom = preset_id == "custom" and not use_catalogue
    if custom or film_flag(config.get("film_caliper_override")):
        caliper = convert_film_thickness(
            _positive_decimal(config.get("film_caliper"), "Film caliper", required=True), unit, "mm"
        )
        caliper_source = "user_property" if custom else "manual_override"
    if custom or (use_catalogue and film_flag(config.get("film_grammage_override"))):
        grammage = _positive_decimal(config.get("film_grammage"), "Film grammage", required=True)
        grammage_source = "user_property" if custom else "manual_override"
    elif caliper is not None:
        if use_catalogue and (grammage is None or caliper_source == "manual_override"):
            density = FILM_DENSITIES.get(family)
        if density is not None:
            grammage = convert_film_thickness(caliper, "mm", "um") * density
            grammage_source = "calculated"

    area = None
    if simple and flat_dimensions:
        length, width = (_positive_decimal(value, "Flat bag dimension") for value in flat_dimensions)
        if length is not None and width is not None:
            area = length * width * Decimal("0.000002")

    tare = None
    tare_source = "unavailable"
    if bag_weight_overridden(config):
        weight = _positive_decimal(config.get("bag_weight"), "Packaging weight", required=True)
        mass_unit = validate_unit(config.get("bag_mass_unit"), MASS_UNITS, "g", "bag mass")
        tare = convert_mass(weight, mass_unit, "g")
        tare_source = "manual_override"
    elif catalogue:
        tare = catalogue_bag_weight_g(material)
        if tare is not None:
            tare_source = "catalogue_actual"

    if tare is None and area is not None and grammage is not None:
        tare = area * grammage
        tare_source = (
            "estimated_catalogue"
            if use_catalogue and caliper_source != "manual_override" and grammage_source != "manual_override"
            else "estimated_material"
        )

    return {
        "film_material_family": family,
        "film_caliper_mm": _validate_result(caliper),
        "film_caliper_source": caliper_source,
        "film_grammage_g_m2": _validate_result(grammage),
        "film_grammage_source": grammage_source,
        "film_density_g_cm3": _validate_result(density),
        "film_area_m2": _validate_result(area),
        "film_two_wall": simple,
        "bag_tare_g": _validate_result(tare),
        "bag_tare_source": tare_source,
        "bag_tare_source_display": FILM_SOURCES[tare_source],
        "bag_tare_display": f"{tare:.3f} g" if tare is not None else "Unavailable",
    }
