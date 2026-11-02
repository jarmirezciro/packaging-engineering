"""Shared corrugated-board presentation and caliper resolution helpers."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ...units import convert_length


# Area density is not a mass conversion.  One MSF is 1,000 square feet, so
# this factor is kept here instead of being routed through convert_mass().
LB_MSF_TO_GSM = Decimal("4.8824276")
DEFAULT_CORRUGATED_DIMENSION_UNIT = "mm"
DEFAULT_CORRUGATED_DENSITY_UNIT = "g/m²"
DEFAULT_MANUAL_RSC_MATERIAL_CODE = "FEFCO_C_175_140_175"
DEFAULT_MANUAL_RSC_CALIPER_MM = Decimal("4.08")


@dataclass(frozen=True)
class CorrugatedCaliper:
    value_mm: Decimal | None
    source: str
    source_label: str
    reference_grade_code: str = ""


def _positive_decimal(value):
    if value in (None, "", "None"):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number <= 0:
        return None
    return number


def gsm_to_lb_msf(value):
    """Convert areal density from canonical g/m² to lb/MSF."""
    number = _positive_decimal(value)
    return None if number is None else number / LB_MSF_TO_GSM


def lb_msf_to_gsm(value):
    """Convert areal density from lb/MSF to canonical g/m²."""
    number = _positive_decimal(value)
    return None if number is None else number * LB_MSF_TO_GSM


def _construction_flute_family(construction):
    flute_display = getattr(construction, "flute_display", "") or ""
    if callable(flute_display):
        flute_display = flute_display()
    if flute_display in {"EB", "BC"}:
        return flute_display
    return str(getattr(construction, "flute_1", "") or flute_display or "").strip()


def resolve_corrugated_caliper(construction, reference_grades=()):
    """Resolve actual, reference, or unavailable finished-board caliper.

    Reference grades are supplied by the caller so this helper remains pure
    and can be reused by services and focused tests without hidden queries.
    The lowest valid ECT category is the deterministic family baseline.
    """
    actual = _positive_decimal(getattr(construction, "caliper_mm", None))
    if actual is not None:
        return CorrugatedCaliper(actual, "actual", "Actual caliper")

    family = _construction_flute_family(construction)
    candidates = []
    for grade in reference_grades or ():
        if not getattr(grade, "is_active", True):
            continue
        if str(getattr(grade, "flute_family", "") or "") != family:
            continue
        caliper = _positive_decimal(getattr(grade, "reference_caliper_mm", None))
        ect = _positive_decimal(getattr(grade, "ect_lb_in", None))
        if caliper is None or ect is None:
            continue
        candidates.append((ect, str(getattr(grade, "code", "") or ""), caliper, grade))

    if not candidates:
        return CorrugatedCaliper(None, "unavailable", "Caliper unavailable")

    _, code, caliper, _ = min(candidates, key=lambda item: (item[0], item[1]))
    return CorrugatedCaliper(caliper, "reference", "Reference caliper", code)


def _number_text(value, places):
    number = _positive_decimal(value)
    if number is None:
        return "—"
    text = f"{number:.{places}f}".rstrip("0").rstrip(".")
    return text or "0"


def corrugated_material_option(construction, caliper, *, dimension_unit="mm"):
    """Build the JSON/template-safe option data for one board construction."""
    dimension_unit = str(dimension_unit or DEFAULT_CORRUGATED_DIMENSION_UNIT).lower()
    imperial = dimension_unit in {"in", "ft"}
    grammage_gsm = _positive_decimal(
        getattr(construction, "combined_grammage_g_m2", None)
    )
    density_value = gsm_to_lb_msf(grammage_gsm) if imperial else grammage_gsm
    density_unit = "lb/MSF" if imperial else DEFAULT_CORRUGATED_DENSITY_UNIT
    caliper_value = caliper.value_mm
    if caliper_value is not None:
        caliper_display = convert_length(
            caliper_value, "mm", "in" if imperial else "mm"
        )
        caliper_text = _number_text(caliper_display, 4 if imperial else 2)
    else:
        caliper_text = "Caliper unavailable"
    caliper_unit = "in" if imperial else "mm"
    source_suffix = " (reference)" if caliper.source == "reference" else ""
    name = str(getattr(construction, "name", "") or "Corrugated board")
    wall = (
        construction.get_wall_type_display()
        if hasattr(construction, "get_wall_type_display")
        else str(getattr(construction, "wall_type", "") or "").replace("_", " ").title()
    )
    flute = str(getattr(construction, "flute_display", "") or "—")
    label = (
        f"{name} — {wall}, {flute}-flute — "
        f"{_number_text(density_value, 1)} {density_unit} — "
        f"{caliper_text}{(' ' + caliper_unit) if caliper_value is not None else ''}{source_suffix}"
    )
    return {
        "id": str(getattr(construction, "pk", getattr(construction, "id", "")) or ""),
        "code": str(getattr(construction, "code", "") or ""),
        "construction": construction,
        "name": name,
        "wall": wall,
        "flute": flute,
        "grammage_g_m2": grammage_gsm,
        "grammage_lb_msf": gsm_to_lb_msf(grammage_gsm),
        "caliper_mm": caliper_value,
        "caliper_source": caliper.source,
        "caliper_source_label": caliper.source_label,
        "reference_grade_code": caliper.reference_grade_code,
        "label": label,
    }


def build_corrugated_material_options(constructions, reference_grades=(), *, dimension_unit="mm"):
    """Return one presentation option per construction without extra queries."""
    grades = tuple(reference_grades or ())
    return [
        corrugated_material_option(
            construction,
            resolve_corrugated_caliper(construction, grades),
            dimension_unit=dimension_unit,
        )
        for construction in constructions or ()
    ]
