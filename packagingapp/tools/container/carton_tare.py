"""Shared finished-carton tare calculation for eligible RSC cartons.

The Container Selection tool only needs the finished material mass.  Keep that
small adapter here so material selection, FEFCO geometry, and workflow weight
inheritance remain separate concerns while reusing the corrugated tool's
authoritative geometry and material calculations.
"""

from dataclasses import dataclass
from decimal import Decimal

from ..corrugated_material_strength.constants import DEFAULTS
from ..corrugated_material_strength.geometry import (
    BoxGeometryInput,
    Fefco0201GeometryProvider,
)
from ..corrugated_material_strength.material import calculate_material


@dataclass(frozen=True)
class CartonTareResult:
    """JSON-safe values are produced by the caller from this calculation."""

    combined_grammage_g_m2: Decimal
    effective_box_area_m2: Decimal
    finished_box_weight_g: Decimal


def _decimal(value):
    if value in (None, "", "None"):
        return None
    return Decimal(str(value))


def calculate_rsc_carton_tare(
    length_mm,
    width_mm,
    height_mm,
    combined_grammage_g_m2,
):
    """Calculate the finished material mass for one FEFCO 0201 carton.

    Dimensions are internal carton dimensions in millimetres.  Joint width and
    sheet margin use the existing corrugated-tool defaults, preserving the
    established FEFCO 0201 geometry contract.  ``calculate_material`` is
    intentionally called with zero product mass because this helper returns
    tare only; its finished-box area/mass equations remain authoritative.
    """

    dimensions = tuple(_decimal(value) for value in (length_mm, width_mm, height_mm))
    grammage = _decimal(combined_grammage_g_m2)
    if any(value is None for value in dimensions) or grammage is None:
        raise ValueError("Carton dimensions and combined grammage are required.")
    if any(not value.is_finite() for value in dimensions) or not grammage.is_finite():
        raise ValueError("Carton dimensions and combined grammage must be finite.")
    if any(value <= 0 for value in dimensions):
        raise ValueError("Carton dimensions must be greater than zero.")
    if grammage <= 0:
        raise ValueError("Combined grammage must be greater than zero.")

    geometry = Fefco0201GeometryProvider().calculate(
        BoxGeometryInput(
            length_mm=dimensions[0],
            width_mm=dimensions[1],
            height_mm=dimensions[2],
            joint_width_mm=DEFAULTS["joint_width_mm"],
            sheet_margin_per_edge_mm=DEFAULTS["sheet_margin_per_edge_mm"],
        )
    )
    material = calculate_material(geometry, grammage, Decimal("0"))
    return CartonTareResult(
        combined_grammage_g_m2=material.combined_grammage_g_m2,
        effective_box_area_m2=geometry.effective_box_area_m2,
        finished_box_weight_g=material.finished_box_weight_g,
    )


def attach_carton_weight_metadata(payload, report, *, upstream=None):
    """Attach only complete gross mass to the workflow's weight_kg contract."""
    from ...units import g_to_kg

    gross = report.get("gross_carton_weight_g", report.get("gross_carton_weight", report.get("total_weight_current")))
    net = report.get("net_weight", report.get("net_content_weight_g", report.get("net_content_weight")))
    tare = report.get("carton_tare_g")
    incomplete_upstream = (upstream or {}).get("weight_status") in {"net_only", "unknown", "incomplete"}
    if incomplete_upstream:
        gross = None
    payload.pop("weight_kg", None)
    payload.pop("weight_g", None)
    payload["gross_carton_weight_g"] = float(gross) if gross is not None else None
    payload["net_content_weight_g"] = float(net) if net is not None else None
    payload["carton_tare_g"] = float(tare) if tare is not None else None
    source = report.get("carton_tare_source") or "unavailable"
    payload["carton_tare_source"] = source
    payload["carton_tare_source_display"] = report.get("carton_tare_source_display") or "Unavailable"
    if gross is not None:
        payload["weight_g"] = float(gross)
        payload["weight_kg"] = float(g_to_kg(gross))
        payload["weight_status"] = "gross_estimated" if source == "estimated_material" or (upstream or {}).get("weight_status") == "gross_estimated" else "gross_known"
    else:
        payload["weight_status"] = "net_only" if net is not None else "unknown"
    for key in ("container_tare", "weight_source", "weight_source_display", "carton_tare_estimated",
                "combined_grammage_g_m2", "caliper_mm", "caliper_source", "caliper_source_display",
                "grammage_source", "grammage_source_display", "grammage_display",
                "corrugated_material_id", "corrugated_material_name", "effective_box_area_m2", "fefco_code"):
        if key in report:
            payload[key] = report[key]
    return payload
