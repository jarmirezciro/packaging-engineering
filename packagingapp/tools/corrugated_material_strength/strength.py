import math
from decimal import Decimal

from .constants import DISTRIBUTION_FACTORS, GRAVITY_M_S2


ECT_LB_IN_TO_KN_M = Decimal("0.175126835")
SCREENING_NOTE = (
    "This is a screening estimate. Confirm final box performance with supplier "
    "data and representative testing."
)
REFERENCE_WARNING = (
    "This McKee result uses one or more reference values. It is an illustrative "
    "screening estimate, not supplier-confirmed board performance."
)


def _decimal(value):
    return None if value is None else Decimal(str(value))


def predict_bct_mckee_metric(ect_kn_m, caliper_mm, perimeter_cm):
    """Return McKee BCT in N from ECT in kN/m, caliper in mm, perimeter in cm."""
    ect = Decimal(str(ect_kn_m))
    caliper = Decimal(str(caliper_mm))
    perimeter = Decimal(str(perimeter_cm))
    if ect <= 0 or caliper <= 0 or perimeter <= 0:
        raise ValueError("ECT, caliper and perimeter must be greater than zero.")
    # Keep the established KolliPack screening equation and units unchanged.
    kgf = (
        Decimal("1.82")
        * ect
        * Decimal("1.0194")
        * Decimal(str(math.pow(float(caliper), 0.508)))
        * Decimal(str(math.pow(float(perimeter), 0.492)))
    )
    return kgf * GRAVITY_M_S2


def distribution_factor(profile, custom_factor=None):
    profile = str(profile or "NORMAL").upper()
    if profile == "CUSTOM":
        if custom_factor is None or Decimal(str(custom_factor)) <= 0:
            raise ValueError("Custom distribution factor must be greater than zero.")
        return Decimal(str(custom_factor))
    return DISTRIBUTION_FACTORS.get(profile, DISTRIBUTION_FACTORS["NORMAL"])


def calculate_strength(
    *, box_length_mm, box_width_mm, required_bct_n, distribution_profile,
    custom_distribution_factor=None, construction_ect_kn_m=None,
    construction_caliper_mm=None, construction_measured_bct_n=None,
    ect_override_kn_m=None, caliper_override_mm=None,
    measured_bct_override_n=None, reference_grade=None,
    effective_caliper_mm=None, caliper_source_type=None,
    caliper_source_label=None, caliper_is_reference=False,
):
    factor = distribution_factor(distribution_profile, custom_distribution_factor)
    required = None if required_bct_n is None else Decimal(str(required_bct_n)) * factor
    if required is not None and required <= 0:
        raise ValueError("Required BCT must be greater than zero.")
    for value in (
        construction_ect_kn_m, construction_caliper_mm, construction_measured_bct_n,
        ect_override_kn_m, caliper_override_mm, measured_bct_override_n,
        effective_caliper_mm,
    ):
        if value is not None and Decimal(str(value)) <= 0:
            raise ValueError("Entered strength values must be greater than zero.")

    # This intentionally preserves the existing internal-perimeter McKee
    # convention; external dimensions are used only for palletization here.
    perimeter_cm = Decimal("2") * (Decimal(str(box_length_mm)) + Decimal(str(box_width_mm))) / Decimal("10")

    reference_ect = _decimal(getattr(reference_grade, "ect_kn_m", None))
    reference_lb_in = _decimal(getattr(reference_grade, "ect_lb_in", None))
    reference_code = getattr(reference_grade, "code", None)

    ect_used = None
    ect_source_type = None
    ect_source_label = None
    ect_is_reference = False
    if ect_override_kn_m is not None and caliper_override_mm is not None:
        ect_used = _decimal(ect_override_kn_m)
        ect_source_type = "ONE_TIME_ACTUAL"
        ect_source_label = "One-time actual ECT override"
    elif construction_ect_kn_m is not None and construction_caliper_mm is not None:
        ect_used = _decimal(construction_ect_kn_m)
        ect_source_type = "CONSTRUCTION"
        ect_source_label = "Board-construction ECT"
    elif reference_ect is not None:
        ect_used = reference_ect
        ect_source_type = "REFERENCE_CATEGORY"
        ect_source_label = "KolliPack reference category"
        ect_is_reference = True

    caliper_used = None
    if effective_caliper_mm is not None:
        caliper_used = _decimal(effective_caliper_mm)
    elif caliper_override_mm is not None:
        caliper_used = _decimal(caliper_override_mm)
        caliper_source_type = "ONE_TIME_ACTUAL"
        caliper_source_label = "One-time actual caliper override"
        caliper_is_reference = False
    elif construction_caliper_mm is not None:
        caliper_used = _decimal(construction_caliper_mm)
        caliper_source_type = "CONSTRUCTION"
        caliper_source_label = "Board-construction caliper"
        caliper_is_reference = False
    elif getattr(reference_grade, "reference_caliper_mm", None) is not None:
        caliper_used = _decimal(reference_grade.reference_caliper_mm)
        caliper_source_type = "REFERENCE_TARGET"
        caliper_source_label = "Reference target caliper"
        caliper_is_reference = True

    available = None
    source = None
    bct_is_reference_based = False
    if measured_bct_override_n is not None:
        available = _decimal(measured_bct_override_n)
        source = "Measured BCT override"
    elif construction_measured_bct_n is not None:
        available = _decimal(construction_measured_bct_n)
        source = "Measured BCT"
    elif ect_used is not None and caliper_used is not None:
        available = predict_bct_mckee_metric(ect_used, caliper_used, perimeter_cm)
        if ect_source_type == "ONE_TIME_ACTUAL":
            source = "Predicted BCT - McKee estimate (overrides)"
        elif ect_source_type == "CONSTRUCTION":
            source = "Predicted BCT - McKee estimate"
        else:
            source = "Predicted BCT - McKee screening estimate using reference data"
        bct_is_reference_based = bool(ect_is_reference or caliper_is_reference)

    margin = available / required if available is not None and required else None
    if available is None:
        status = "Strength unavailable"
        interpretation = status
    elif required is None:
        status = "Available BCT calculated; pallet requirement unavailable"
        interpretation = status
    else:
        status = "Exceeds preliminary requirement" if margin >= 1 else "Below preliminary requirement"
        interpretation = status

    return {
        "distribution_profile": str(distribution_profile or "NORMAL").upper(),
        "distribution_factor": factor,
        "required_bct_n": required,
        "available_bct_n": available,
        "strength_source": source,
        "strength_margin": margin,
        "strength_status": status,
        "interpretation": interpretation,
        "warning": REFERENCE_WARNING if bct_is_reference_based else SCREENING_NOTE,
        "ect_used_kn_m": ect_used,
        "ect_used_lb_in": reference_lb_in if ect_is_reference else (ect_used / ECT_LB_IN_TO_KN_M if ect_used is not None else None),
        "ect_source_type": ect_source_type,
        "ect_source_label": ect_source_label,
        "ect_is_reference": ect_is_reference,
        "reference_ect_code": reference_code,
        "caliper_used_mm": caliper_used,
        "caliper_source_type": caliper_source_type,
        "caliper_source_label": caliper_source_label,
        "caliper_is_reference": bool(caliper_is_reference),
        "bct_is_reference_based": bct_is_reference_based,
    }
