import math
from decimal import Decimal

from .constants import DISTRIBUTION_FACTORS, GRAVITY_M_S2


SCREENING_NOTE = (
    "This is a screening estimate. Confirm final box performance with supplier "
    "data and representative testing."
)


def predict_bct_mckee_metric(ect_kn_m, caliper_mm, perimeter_cm):
    """Return McKee BCT in N from ECT in kN/m, caliper in mm, perimeter in cm."""
    ect = Decimal(str(ect_kn_m))
    caliper = Decimal(str(caliper_mm))
    perimeter = Decimal(str(perimeter_cm))
    if ect <= 0 or caliper <= 0 or perimeter <= 0:
        raise ValueError("ECT, caliper and perimeter must be greater than zero.")
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
    measured_bct_override_n=None,
):
    factor = distribution_factor(distribution_profile, custom_distribution_factor)
    required = Decimal(str(required_bct_n)) * factor
    if required <= 0:
        raise ValueError("Required BCT must be greater than zero.")
    for value in (
        construction_ect_kn_m, construction_caliper_mm, construction_measured_bct_n,
        ect_override_kn_m, caliper_override_mm, measured_bct_override_n,
    ):
        if value is not None and Decimal(str(value)) <= 0:
            raise ValueError("Entered strength values must be greater than zero.")
    perimeter_cm = Decimal("2") * (Decimal(str(box_length_mm)) + Decimal(str(box_width_mm))) / Decimal("10")

    available = None
    source = None
    if measured_bct_override_n is not None:
        available = Decimal(str(measured_bct_override_n))
        source = "Measured BCT override"
    elif construction_measured_bct_n is not None:
        available = Decimal(str(construction_measured_bct_n))
        source = "Measured BCT"
    elif ect_override_kn_m is not None and caliper_override_mm is not None:
        available = predict_bct_mckee_metric(ect_override_kn_m, caliper_override_mm, perimeter_cm)
        source = "Predicted BCT — McKee estimate (overrides)"
    elif construction_ect_kn_m is not None and construction_caliper_mm is not None:
        available = predict_bct_mckee_metric(construction_ect_kn_m, construction_caliper_mm, perimeter_cm)
        source = "Predicted BCT — McKee estimate"

    if available is None:
        return {
            "distribution_profile": str(distribution_profile or "NORMAL").upper(),
            "distribution_factor": factor,
            "required_bct_n": required,
            "available_bct_n": None,
            "strength_source": None,
            "strength_margin": None,
            "strength_status": "Strength unavailable",
            "interpretation": "Strength unavailable",
            "warning": SCREENING_NOTE,
        }

    margin = available / required if required else None
    status = "Exceeds preliminary requirement" if margin is not None and margin >= 1 else "Below preliminary requirement"
    return {
        "distribution_profile": str(distribution_profile or "NORMAL").upper(),
        "distribution_factor": factor,
        "required_bct_n": required,
        "available_bct_n": available,
        "strength_source": source,
        "strength_margin": margin,
        "strength_status": status,
        "interpretation": status,
        "warning": SCREENING_NOTE,
    }
