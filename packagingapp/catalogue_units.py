"""Shared unit state and presentation helpers for catalogue surfaces.

Catalogue records remain canonical metric.  This module is deliberately a
presentation/input boundary: it converts display values to and from the
model units without changing any catalogue or tool contracts.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.http import HttpResponseBadRequest

from .units import (
    LENGTH_UNITS,
    MASS_UNITS,
    UnsupportedUnitError,
    convert_length,
    convert_mass,
    normalize_unit,
)
from .units.ui import build_unit_selector_contract
from .user_preferences import unit_defaults_for_user


CATALOGUE_LENGTH_SESSION_KEY = "catalogue_length_unit"
CATALOGUE_MASS_SESSION_KEY = "catalogue_mass_unit"
DEFAULT_CATALOGUE_LENGTH_UNIT = "mm"
DEFAULT_CATALOGUE_MASS_UNIT = "kg"

CATALOGUE_LENGTH_GROUP = "catalogue-length"
CATALOGUE_MASS_GROUP = "catalogue-mass"
CATALOGUE_DISPLAY_LENGTH_GROUP = "catalogue-display-length"
CATALOGUE_DISPLAY_MASS_GROUP = "catalogue-display-mass"
CATALOGUE_ENTRY_LENGTH_GROUP = f"catalogue-entry-{CATALOGUE_LENGTH_GROUP}"
CATALOGUE_ENTRY_MASS_GROUP = f"catalogue-entry-{CATALOGUE_MASS_GROUP}"


def _unit_from_request(request, *, query_key, session_key, definitions, default):
    raw = request.GET.get(query_key)
    if raw in (None, ""):
        raw = request.session.get(session_key, default)
    return normalize_unit(raw, definitions, default)


def catalogue_units_from_request(request):
    """Resolve and remember catalogue display units for a GET request.

    The query parameters are useful for links and pagination; the session is
    a lightweight page-to-page fallback.  Invalid explicit tokens are
    rejected instead of being silently interpreted as metric.
    """
    user_defaults = unit_defaults_for_user(getattr(request, "user", None))
    try:
        length_unit = _unit_from_request(
            request,
            query_key=CATALOGUE_LENGTH_SESSION_KEY,
            session_key=CATALOGUE_LENGTH_SESSION_KEY,
            definitions=LENGTH_UNITS,
            default=user_defaults["length"],
        )
        mass_unit = _unit_from_request(
            request,
            query_key=CATALOGUE_MASS_SESSION_KEY,
            session_key=CATALOGUE_MASS_SESSION_KEY,
            definitions=MASS_UNITS,
            default=user_defaults["small_mass"],
        )
    except UnsupportedUnitError as exc:
        return None, HttpResponseBadRequest(str(exc))

    if request.GET.get(CATALOGUE_LENGTH_SESSION_KEY) not in (None, ""):
        request.session[CATALOGUE_LENGTH_SESSION_KEY] = length_unit
    if request.GET.get(CATALOGUE_MASS_SESSION_KEY) not in (None, ""):
        request.session[CATALOGUE_MASS_SESSION_KEY] = mass_unit
    if request.GET.get(CATALOGUE_LENGTH_SESSION_KEY) or request.GET.get(CATALOGUE_MASS_SESSION_KEY):
        request.session.modified = True

    return {"length": length_unit, "mass": mass_unit}, None


def remember_catalogue_units(request, *, length_unit=None, mass_unit=None):
    """Persist validated catalogue units after a form submission."""
    try:
        if length_unit not in (None, ""):
            request.session[CATALOGUE_LENGTH_SESSION_KEY] = normalize_unit(
                length_unit, LENGTH_UNITS, DEFAULT_CATALOGUE_LENGTH_UNIT
            )
        if mass_unit not in (None, ""):
            request.session[CATALOGUE_MASS_SESSION_KEY] = normalize_unit(
                mass_unit, MASS_UNITS, DEFAULT_CATALOGUE_MASS_UNIT
            )
    except UnsupportedUnitError:
        # Form ChoiceFields reject unsupported tokens before a successful save.
        # Keep this helper defensive for callers that pass external values.
        return
    request.session.modified = True


def catalogue_unit_selectors(*, length_unit, mass_unit, group_prefix="catalogue-entry"):
    """Build selector contracts shared by detail tables and entry forms."""
    return {
        "length": build_unit_selector_contract(
            quantity="length",
            label="catalogue length",
            group=f"{group_prefix}-{CATALOGUE_LENGTH_GROUP}",
            hidden_name=CATALOGUE_LENGTH_SESSION_KEY,
            hidden_id=f"{group_prefix}-catalogue-length",
            menu_id=f"{group_prefix}-catalogue-length-menu",
            storage_key=CATALOGUE_LENGTH_SESSION_KEY,
            url_param=CATALOGUE_LENGTH_SESSION_KEY,
        ),
        "mass": build_unit_selector_contract(
            quantity="mass",
            label="catalogue mass",
            group=f"{group_prefix}-{CATALOGUE_MASS_GROUP}",
            hidden_name=CATALOGUE_MASS_SESSION_KEY,
            hidden_id=f"{group_prefix}-catalogue-mass",
            menu_id=f"{group_prefix}-catalogue-mass-menu",
            storage_key=CATALOGUE_MASS_SESSION_KEY,
            url_param=CATALOGUE_MASS_SESSION_KEY,
        ),
    }


def catalogue_display_selectors(*, length_unit, mass_unit):
    selectors = catalogue_unit_selectors(
        length_unit=length_unit,
        mass_unit=mass_unit,
        group_prefix="catalogue-display",
    )
    selectors["length"]["group"] = CATALOGUE_DISPLAY_LENGTH_GROUP
    selectors["mass"]["group"] = CATALOGUE_DISPLAY_MASS_GROUP
    return selectors


def _as_decimal(value):
    if value in (None, ""):
        return None
    try:
        numeric = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Catalogue physical values must be numeric.") from exc
    if not numeric.is_finite():
        raise ValueError("Catalogue physical values must be finite.")
    return numeric


def quantize_canonical(value, decimal_places):
    """Apply the model field precision after conversion, not before it."""
    numeric = _as_decimal(value)
    if numeric is None:
        return None
    quantum = Decimal("1").scaleb(-decimal_places)
    return numeric.quantize(quantum, rounding=ROUND_HALF_UP)


def convert_catalogue_input(value, *, quantity, from_unit, decimal_places):
    """Convert one submitted display value into canonical catalogue units."""
    numeric = _as_decimal(value)
    if numeric is None:
        return None
    converter = convert_length if quantity == "length" else convert_mass
    canonical_unit = "mm" if quantity == "length" else "kg"
    return quantize_canonical(
        converter(numeric, from_unit, canonical_unit),
        decimal_places,
    )


def convert_catalogue_filter(value, *, quantity, display_unit):
    """Convert a filter threshold exactly for a canonical ORM lookup."""
    numeric = _as_decimal(value)
    if numeric is None:
        return None
    converter = convert_length if quantity == "length" else convert_mass
    canonical_unit = "mm" if quantity == "length" else "kg"
    return converter(numeric, display_unit, canonical_unit)


def format_catalogue_value(value, *, quantity, display_unit, max_decimal_places=4):
    """Convert a canonical value for readable catalogue presentation."""
    numeric = _as_decimal(value)
    if numeric is None:
        return "—"
    converter = convert_length if quantity == "length" else convert_mass
    canonical_unit = "mm" if quantity == "length" else "kg"
    converted = converter(numeric, canonical_unit, display_unit)
    quantum = Decimal("1").scaleb(-max_decimal_places)
    rounded = converted.quantize(quantum, rounding=ROUND_HALF_UP)
    text = format(rounded, "f").rstrip("0").rstrip(".")
    return text or "0"


def annotate_product_picker_rows(records, *, length_unit, mass_unit):
    """Attach display-only values for an in-tool Product Catalogue picker.

    The records remain ordinary model instances and their canonical fields are
    never replaced.  The transient attributes are consumed by picker
    templates while ``data-unit-canonical`` keeps the browser conversion
    source tied to the stored mm/kg values.
    """
    for product in records or ():
        for axis in ("length", "width", "height"):
            field_name = f"product_{axis}"
            setattr(
                product,
                f"picker_display_{axis}",
                format_catalogue_value(
                    getattr(product, field_name, None),
                    quantity="length",
                    display_unit=length_unit,
                ),
            )
        setattr(
            product,
            "picker_display_weight",
            format_catalogue_value(
                getattr(product, "weight", None),
                quantity="mass",
                display_unit=mass_unit,
            ),
        )
    return records


def annotate_packaging_picker_rows(
    records, *, length_unit, mass_unit, external_fallback=False
):
    """Attach display-only values for an in-tool Packaging Catalogue picker.

    ``external_fallback`` matches Palletization's established selection
    contract: external dimensions are preferred and the canonical internal
    ``part_*`` dimensions are used only when an external value is absent.
    """
    for material in records or ():
        for axis in ("length", "width", "height"):
            part_field = f"part_{axis}"
            external_field = f"external_{axis}"
            part_value = getattr(material, part_field, None)
            external_value = getattr(material, external_field, None)
            setattr(
                material,
                f"picker_display_part_{axis}",
                format_catalogue_value(
                    part_value,
                    quantity="length",
                    display_unit=length_unit,
                ),
            )
            if external_fallback:
                display_value = external_value or part_value
                setattr(material, f"picker_external_{axis}", display_value)
                setattr(
                    material,
                    f"picker_display_external_{axis}",
                    format_catalogue_value(
                        display_value,
                        quantity="length",
                        display_unit=length_unit,
                    ),
                )
            elif external_value not in (None, ""):
                setattr(
                    material,
                    f"picker_display_external_{axis}",
                    format_catalogue_value(
                        external_value,
                        quantity="length",
                        display_unit=length_unit,
                    ),
                )
        setattr(
            material,
            "picker_display_weight",
            format_catalogue_value(
                getattr(material, "part_weight", None),
                quantity="mass",
                display_unit=mass_unit,
            ),
        )
    return records


def catalogue_entry_state(*, length_unit, mass_unit):
    """Return JSON-safe state for catalogue forms and templates."""
    return {
        "length": normalize_unit(length_unit, LENGTH_UNITS, DEFAULT_CATALOGUE_LENGTH_UNIT),
        "mass": normalize_unit(mass_unit, MASS_UNITS, DEFAULT_CATALOGUE_MASS_UNIT),
    }
