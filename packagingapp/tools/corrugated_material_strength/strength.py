import math
from decimal import Decimal, ROUND_FLOOR

from .constants import DISTRIBUTION_FACTORS, ECT_LB_IN_TO_KN_M, GRAVITY_M_S2


SCREENING_NOTE = (
    "Preliminary engineering screening estimate. Confirm the final construction "
    "and stacking performance with the corrugated supplier and representative testing."
)
REFERENCE_WARNING = (
    "This result uses reference ECT and/or reference caliper. Replace with "
    "supplier-documented or measured values when available."
)
CAPACITY_WARNING = (
    "The equivalent box capacity is a compression-strength screening result for one "
    "vertical load column. It is not a recommended physical stack height."
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
    # Preserve the established metric McKee equation and perimeter convention.
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


def _pair_source(
    *, ect_override_kn_m, caliper_override_mm, construction_ect_kn_m,
    construction_caliper_mm, reference_ect, reference_caliper,
    construction_source_type, construction_source_label,
):
    if ect_override_kn_m is not None and caliper_override_mm is not None:
        return (
            _decimal(ect_override_kn_m), _decimal(caliper_override_mm),
            "ONE_TIME_ACTUAL", "One-time actual ECT and caliper overrides", False, False,
        )
    if construction_ect_kn_m is not None and construction_caliper_mm is not None:
        return (
            _decimal(construction_ect_kn_m), _decimal(construction_caliper_mm),
            construction_source_type or "CONSTRUCTION",
            construction_source_label or "Board-construction ECT and caliper", False, False,
        )
    if reference_ect is not None and reference_caliper is not None:
        return (
            _decimal(reference_ect), _decimal(reference_caliper),
            "REFERENCE_CATEGORY", "KolliPack reference ECT and caliper", True, True,
        )
    return None, None, None, None, False, False


def _capacity_basis(source, *, reference_based, construction_source_type=None, ect_source_type=None):
    if reference_based:
        return "McKee screening estimate using KolliPack reference ECT and caliper"
    if source == "Measured BCT override" or source == "Measured BCT":
        return "Measured BCT"
    if source == "ONE_TIME_ACTUAL" or ect_source_type == "ONE_TIME_ACTUAL":
        return "McKee prediction using one-time ECT and caliper values"
    if source:
        if construction_source_type == "SUPPLIER_DOCUMENTED":
            return "McKee prediction using supplier-documented ECT and caliper"
        if construction_source_type == "COMPANY_MEASURED":
            return "McKee prediction using company-measured ECT and caliper"
        return "McKee screening estimate using board-construction ECT and caliper"
    return None


def calculate_compression_capacity(
    *, available_bct_n, distribution_factor, gross_box_weight_kg,
    current_static_load_n=None, current_supported_mass_kg=None,
    current_boxes_above=None, basis=None, capacity_is_reference_based=False,
):
    """Translate available BCT into preliminary load-column capacity.

    This function deliberately accepts pallet-derived current load values rather
    than recomputing pallet layers or stacked-pallet load in the strength layer.
    """
    bct = _decimal(available_bct_n)
    factor = _decimal(distribution_factor)
    gross = _decimal(gross_box_weight_kg)
    current_force = _decimal(current_static_load_n)
    current_mass = _decimal(current_supported_mass_kg)
    if current_force is None and current_mass is not None:
        current_force = current_mass * GRAVITY_M_S2
    current_above = None if current_boxes_above is None else int(current_boxes_above)
    current_total = None if current_above is None else current_above + 1

    maximum_force = None
    maximum_mass = None
    maximum_equivalent = None
    maximum_total = None
    warnings = [CAPACITY_WARNING]
    if bct is None or factor is None or factor <= 0:
        warnings.insert(0, "Maximum supported load unavailable because no measured or predicted BCT is available.")
    elif bct <= 0:
        warnings.insert(0, "Maximum supported load unavailable because available BCT is not positive.")
    else:
        maximum_force = bct / factor
        maximum_mass = maximum_force / GRAVITY_M_S2
        if gross is not None and gross > 0:
            maximum_equivalent = int((maximum_mass / gross).to_integral_value(rounding=ROUND_FLOOR))
            maximum_total = maximum_equivalent + 1
        else:
            warnings.insert(0, "Equivalent box capacity unavailable because gross packed-box weight is unavailable.")

    if current_force is None:
        warnings.append("Current pallet load is unavailable; current usage and remaining capacity cannot be calculated.")

    current_equivalent = None
    if current_mass is not None and gross is not None and gross > 0:
        current_equivalent = current_mass / gross

    remaining_force = None
    remaining_mass = None
    remaining_equivalent = None
    usage = None
    overloaded = None
    overload_force = None
    overload_mass = None
    overload_equivalent = None
    if maximum_force is not None and current_force is not None:
        usage = current_force / maximum_force * Decimal("100")
        overloaded = current_force > maximum_force
        remaining_force = max(Decimal("0"), maximum_force - current_force)
        remaining_mass = remaining_force / GRAVITY_M_S2
        if gross is not None and gross > 0:
            remaining_equivalent = int((remaining_mass / gross).to_integral_value(rounding=ROUND_FLOOR))
        if overloaded:
            overload_force = current_force - maximum_force
            overload_mass = overload_force / GRAVITY_M_S2
            if gross is not None and gross > 0:
                overload_equivalent = overload_mass / gross

    return {
        "available": maximum_force is not None,
        "allowable_supported_force_n": maximum_force,
        "allowable_supported_mass_kg": maximum_mass,
        "maximum_equivalent_boxes_above": maximum_equivalent,
        "maximum_total_boxes_in_column": maximum_total,
        "current_boxes_above": current_above,
        "current_total_boxes_in_column": current_total,
        "current_equivalent_boxes_above": current_equivalent,
        "current_equivalent_supported_load": current_equivalent,
        "current_supported_force_n": current_force,
        "current_supported_mass_kg": current_mass,
        "remaining_supported_force_n": remaining_force,
        "remaining_supported_mass_kg": remaining_mass,
        "remaining_equivalent_boxes": remaining_equivalent,
        "capacity_usage_percent": usage,
        "is_overloaded": overloaded,
        "overload_force_n": overload_force,
        "overload_mass_kg": overload_mass,
        "overload_equivalent_boxes": overload_equivalent,
        "basis": basis,
        "capacity_basis": basis,
        "capacity_is_reference_based": bool(capacity_is_reference_based),
        "gross_box_weight_kg": gross,
        "warnings": warnings,
    }


def calculate_strength(
    *, box_length_mm, box_width_mm, required_bct_n, distribution_profile,
    custom_distribution_factor=None, construction_ect_kn_m=None,
    construction_caliper_mm=None, construction_measured_bct_n=None,
    ect_override_kn_m=None, caliper_override_mm=None,
    measured_bct_override_n=None, reference_grade=None,
    effective_caliper_mm=None, caliper_source_type=None,
    caliper_source_label=None, caliper_is_reference=False,
    construction_source_type=None, construction_source_label=None,
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

    perimeter_cm = Decimal("2") * (Decimal(str(box_length_mm)) + Decimal(str(box_width_mm))) / Decimal("10")
    reference_ect = _decimal(getattr(reference_grade, "ect_kn_m", None))
    reference_lb_in = _decimal(getattr(reference_grade, "ect_lb_in", None))
    reference_caliper = _decimal(getattr(reference_grade, "reference_caliper_mm", None))
    reference_code = getattr(reference_grade, "code", None)
    reference_family = getattr(reference_grade, "flute_family", None)
    reference_basis = getattr(reference_grade, "caliper_basis", None)

    ect_used, caliper_from_pair, ect_source_type, ect_source_label, ect_is_reference, pair_is_reference = _pair_source(
        ect_override_kn_m=ect_override_kn_m,
        caliper_override_mm=caliper_override_mm,
        construction_ect_kn_m=construction_ect_kn_m,
        construction_caliper_mm=construction_caliper_mm,
        reference_ect=reference_ect,
        reference_caliper=reference_caliper,
        construction_source_type=construction_source_type,
        construction_source_label=construction_source_label,
    )
    caliper_used = caliper_from_pair
    if caliper_used is None and effective_caliper_mm is not None:
        caliper_used = _decimal(effective_caliper_mm)
    if caliper_used is None and caliper_override_mm is not None:
        caliper_used = _decimal(caliper_override_mm)
        caliper_source_type = "ONE_TIME_ACTUAL"
        caliper_source_label = "One-time actual caliper override"
        caliper_is_reference = False
    elif caliper_used is not None and ect_source_type == "ONE_TIME_ACTUAL":
        caliper_source_type = "ONE_TIME_ACTUAL"
        caliper_source_label = "One-time actual caliper override"
        caliper_is_reference = False
    elif caliper_used is not None and ect_source_type == "REFERENCE_CATEGORY":
        caliper_source_type = "REFERENCE_TARGET"
        caliper_source_label = "KolliPack reference caliper"
        caliper_is_reference = True
    elif caliper_used is not None and caliper_source_type is None:
        caliper_source_type = construction_source_type or "CONSTRUCTION"
        caliper_source_label = construction_source_label or "Board-construction caliper"

    available = None
    source = None
    if measured_bct_override_n is not None:
        available = _decimal(measured_bct_override_n)
        source = "Measured BCT override"
    elif construction_measured_bct_n is not None:
        available = _decimal(construction_measured_bct_n)
        source = "Measured BCT"
    elif ect_used is not None and caliper_used is not None:
        available = predict_bct_mckee_metric(ect_used, caliper_used, perimeter_cm)
        source = "Predicted BCT - McKee screening estimate" if pair_is_reference else "Predicted BCT - McKee estimate"

    bct_is_reference_based = bool(
        pair_is_reference and source not in {"Measured BCT override", "Measured BCT"}
    )
    capacity_basis = _capacity_basis(
        source,
        reference_based=bct_is_reference_based,
        construction_source_type=construction_source_type,
        ect_source_type=ect_source_type,
    )
    margin = available / required if available is not None and required else None
    if available is None:
        status = "Strength unavailable"
    elif required is None:
        status = "Available BCT calculated; pallet requirement unavailable"
    else:
        status = "Exceeds preliminary requirement" if margin >= 1 else "Below preliminary requirement"

    return {
        "distribution_profile": str(distribution_profile or "NORMAL").upper(),
        "distribution_factor": factor,
        "required_bct_n": required,
        "available_bct_n": available,
        "available_bct_source": source,
        "strength_source": source,
        "strength_margin": margin,
        "strength_status": status,
        "interpretation": status,
        "warning": REFERENCE_WARNING if bct_is_reference_based else SCREENING_NOTE,
        "ect_used_kn_m": ect_used,
        "ect_used_lb_in": reference_lb_in if ect_is_reference else (ect_used / ECT_LB_IN_TO_KN_M if ect_used is not None else None),
        "ect_source_type": ect_source_type,
        "ect_source_label": ect_source_label,
        "ect_is_reference": ect_is_reference,
        "reference_grade_code": reference_code,
        "reference_flute_family": reference_family,
        "reference_caliper_basis": reference_basis,
        "caliper_used_mm": caliper_used,
        "caliper_source_type": caliper_source_type,
        "caliper_source_label": caliper_source_label,
        "caliper_is_reference": bool(caliper_is_reference),
        "bct_is_reference_based": bct_is_reference_based,
        "capacity_basis": capacity_basis,
    }
