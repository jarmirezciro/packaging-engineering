from decimal import Decimal

from .carbon import calculate_carbon
from .constants import DEFAULTS
from .flute_profiles import nominal_height_for
from .geometry import BoxGeometryInput, Fefco0201GeometryProvider
from .material import calculate_material
from .pallet import PalletInput, calculate_pallet
from .serializers import serialize_corrugated_result
from .strength import calculate_strength, distribution_factor


def _decimal(value, default=None):
    if value in (None, "", "None"):
        return default
    return Decimal(str(value))


def _construction_metadata(construction):
    if construction is None:
        return {
            "mode": "manual", "code": "MANUAL",
            "name": "Manual one-time board entry",
            "source_type": "ADMIN_ENTERED",
            "source_label": "Entered for this calculation only",
        }
    return {
        "mode": "catalogue", "id": construction.pk,
        "code": construction.code, "name": construction.name,
        "supplier_name": construction.supplier_name,
        "supplier_grade_code": construction.supplier_grade_code,
        "wall_type": construction.wall_type,
        "flute": construction.flute_display,
        "combined_grammage_g_m2": construction.combined_grammage_g_m2,
        "nominal_flute_height_mm": construction.nominal_flute_height_mm,
        "caliper_mm": construction.caliper_mm,
        "ect_kn_m": construction.ect_kn_m,
        "measured_bct_n": construction.measured_bct_n,
        "source_type": construction.source_type,
        "source_label": construction.source_label,
        "source_notes": construction.source_notes,
        "co2_factor_kg_co2e_per_kg": construction.co2_factor_kg_co2e_per_kg,
        "co2_source_label": construction.co2_source_label,
        "co2_boundary": construction.co2_boundary,
    }


def calculate_corrugated_material_strength(inputs, *, construction=None, pallet_material=None):
    """Calculate one JSON-safe standalone or future workflow-safe analysis."""
    data = dict(inputs or {})
    box_length = _decimal(data.get("box_length_mm"), DEFAULTS["box_length_mm"])
    box_width = _decimal(data.get("box_width_mm"), DEFAULTS["box_width_mm"])
    box_height = _decimal(data.get("box_height_mm"), DEFAULTS["box_height_mm"])
    product_weight = _decimal(data.get("product_weight_g"), DEFAULTS["product_weight_g"])
    quantity = int(data.get("quantity") or DEFAULTS["quantity"])
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    joint = _decimal(data.get("joint_width_mm"), DEFAULTS["joint_width_mm"])
    sheet_margin = _decimal(data.get("sheet_margin_per_edge_mm"), DEFAULTS["sheet_margin_per_edge_mm"])

    geometry = Fefco0201GeometryProvider().calculate(BoxGeometryInput(
        length_mm=box_length, width_mm=box_width, height_mm=box_height,
        joint_width_mm=joint, sheet_margin_per_edge_mm=sheet_margin,
    ))

    if construction is None:
        grammage = _decimal(data.get("manual_combined_grammage_g_m2"))
        if grammage is None:
            raise ValueError("Enter a combined grammage for the manual board entry.")
        manual_flute_1 = data.get("manual_flute_1") or ""
        manual_flute_2 = data.get("manual_flute_2") or None
        nominal_height = nominal_height_for(manual_flute_1, manual_flute_2)
        construction_ect = construction_caliper = construction_bct = None
        is_custom_co2 = str(data.get("co2_mode") or "").upper() == "CUSTOM"
        co2_factor = _decimal(data.get("custom_co2_factor_kg_per_kg")) if is_custom_co2 else None
        co2_source = data.get("custom_co2_source") or "Manual one-time factor"
        co2_boundary = data.get("custom_co2_boundary") or "Entered for this calculation only"
    else:
        grammage = construction.combined_grammage_g_m2
        nominal_height = construction.nominal_flute_height_mm
        construction_ect = construction.ect_kn_m
        construction_caliper = construction.caliper_mm
        construction_bct = construction.measured_bct_n
        is_custom_co2 = str(data.get("co2_mode") or "CONSTRUCTION").upper() == "CUSTOM"
        if is_custom_co2:
            co2_factor = _decimal(data.get("custom_co2_factor_kg_per_kg"))
            co2_source = data.get("custom_co2_source") or "Custom factor"
            co2_boundary = data.get("custom_co2_boundary") or "Custom boundary"
        else:
            co2_factor = construction.co2_factor_kg_co2e_per_kg
            co2_source = construction.co2_source_label
            co2_boundary = construction.co2_boundary

    material = calculate_material(geometry, grammage, product_weight)
    pallet_weight = _decimal(data.get("pallet_weight_kg"), DEFAULTS["pallet_weight_kg"])
    if pallet_weight < 0:
        raise ValueError("Pallet weight cannot be negative.")
    pallet = calculate_pallet(PalletInput(
        pallet_length_mm=_decimal(data.get("pallet_length_mm"), DEFAULTS["pallet_length_mm"]),
        pallet_width_mm=_decimal(data.get("pallet_width_mm"), DEFAULTS["pallet_width_mm"]),
        pallet_height_mm=_decimal(data.get("pallet_height_mm"), DEFAULTS["pallet_height_mm"]),
        pallet_weight_kg=pallet_weight,
        max_palletized_height_mm=_decimal(data.get("max_palletized_height_mm"), DEFAULTS["max_palletized_height_mm"]),
        box_length_mm=box_length, box_width_mm=box_width, box_height_mm=box_height,
        gross_packed_box_weight_g=material.gross_packed_box_weight_g,
        stacked_pallets=int(data.get("stacked_pallets") or DEFAULTS["stacked_pallets"]),
        pattern=data.get("pattern") or DEFAULTS["pattern"],
    ))
    pallet["source"] = "Existing pallet catalogue" if pallet_material is not None else "Manual dimensions"
    pallet["code"] = getattr(pallet_material, "part_number", "") if pallet_material is not None else "MANUAL"
    pallet["name"] = getattr(pallet_material, "part_description", "") if pallet_material is not None else "Manual pallet"

    profile = data.get("distribution_profile") or DEFAULTS["distribution_profile"]
    custom_factor = _decimal(data.get("distribution_factor"))
    strength = calculate_strength(
        box_length_mm=box_length, box_width_mm=box_width,
        required_bct_n=pallet["static_load_n"],
        distribution_profile=profile,
        custom_distribution_factor=custom_factor if str(profile).upper() == "CUSTOM" else None,
        construction_ect_kn_m=construction_ect,
        construction_caliper_mm=construction_caliper,
        construction_measured_bct_n=construction_bct,
        ect_override_kn_m=_decimal(data.get("ect_override_kn_m")),
        caliper_override_mm=_decimal(data.get("caliper_override_mm")),
        measured_bct_override_n=_decimal(data.get("measured_bct_override_n")),
    )

    carbon = calculate_carbon(
        factor_kg_co2e_per_kg=co2_factor,
        source_label=co2_source, boundary=co2_boundary,
        finished_box_weight_g=material.finished_box_weight_g,
        cutting_scrap_weight_g=material.cutting_scrap_weight_g,
        production_sheet_weight_g=material.production_sheet_weight_g,
        boxes_per_pallet=pallet["boxes_per_pallet"], quantity=quantity,
    )

    warnings = list(pallet.get("warnings") or [])
    if strength["available_bct_n"] is None:
        if construction is not None and construction.ect_kn_m is None and construction.caliper_mm is None and construction.measured_bct_n is None:
            strength["data_note"] = (
                "This generic construction contains material information but no supplier ECT or finished-board caliper. "
                "Enter ECT and caliper for this calculation or select a material containing strength data."
            )
        warnings.append(
            "Material and CO₂ results are available, but compression strength cannot be estimated from the available data."
        )
    assumptions = [
        "Preliminary geometry uses the entered dimensions directly and does not include converter-specific dimensional allowances.",
        "Slot-cut width is treated as negligible in the first version.",
        "Only geometric cutting scrap is included; startup loss, trimming, printing rejects and general factory waste are excluded.",
        "The distribution factor is a simplified screening allowance. It is not a detailed humidity, creep or vibration model.",
    ]
    if nominal_height is not None:
        assumptions.append("Nominal flute height excludes facings and is not used as finished-board caliper.")

    explanation = [
        f"Blank length = 2 × ({box_length} + {box_width}) + {joint} = {geometry.blank_length_mm} mm",
        f"Blank width = {box_height} + {box_width} = {geometry.blank_width_mm} mm",
        f"Required sheet length = {geometry.blank_length_mm} + 2 × {sheet_margin} = {geometry.production_sheet_length_mm} mm",
        f"Required sheet width = {geometry.blank_width_mm} + 2 × {sheet_margin} = {geometry.production_sheet_width_mm} mm",
        f"Effective finished-box area = {geometry.effective_box_area_m2} m²",
        f"Required BCT = {pallet['static_load_n']} N × {strength['distribution_factor']} = {strength['required_bct_n']} N",
    ]

    result = {
        "box_geometry": {**geometry.__dict__}, "material": {**material.__dict__},
        "pallet": pallet, "strength": strength, "carbon": carbon,
        "assumptions": assumptions, "warnings": warnings,
        "source_metadata": _construction_metadata(construction),
        "explanation": explanation,
        "board": {"combined_grammage_g_m2": grammage, "nominal_flute_height_mm": nominal_height},
    }
    result.update({
        "blank_length_mm": geometry.blank_length_mm,
        "blank_width_mm": geometry.blank_width_mm,
        "blank_bounding_area_m2": geometry.blank_bounding_area_m2,
        "production_sheet_length_mm": geometry.production_sheet_length_mm,
        "production_sheet_width_mm": geometry.production_sheet_width_mm,
        "production_sheet_area_m2": geometry.production_sheet_area_m2,
        "effective_box_area_m2": geometry.effective_box_area_m2,
        "blank_void_area_m2": geometry.blank_void_area_m2,
        "sheet_margin_area_m2": geometry.sheet_margin_area_m2,
        "total_scrap_area_m2": geometry.total_scrap_area_m2,
        "material_utilization_percent": geometry.material_utilization_percent,
        "scrap_percent": geometry.scrap_percent,
        "finished_box_weight_g": material.finished_box_weight_g,
        "blank_bounding_weight_g": material.blank_bounding_weight_g,
        "production_sheet_weight_g": material.production_sheet_weight_g,
        "cutting_scrap_weight_g": material.cutting_scrap_weight_g,
        "gross_packed_box_weight_g": material.gross_packed_box_weight_g,
        "boxes_per_layer": pallet["boxes_per_layer"], "layers": pallet["layers"],
        "boxes_per_pallet": pallet["boxes_per_pallet"],
        "palletized_height_mm": pallet["palletized_height_mm"],
        "selected_orientation": pallet["selected_orientation"],
        "supported_mass_kg": pallet["supported_mass_kg"], "static_load_n": pallet["static_load_n"],
        "distribution_factor": strength["distribution_factor"],
        "required_bct_n": strength["required_bct_n"],
        "available_bct_n": strength["available_bct_n"],
        "strength_source": strength["strength_source"],
        "strength_margin": strength["strength_margin"],
        "strength_status": strength["strength_status"],
        "finished_box_co2_kg": carbon.get("finished_box_co2_kg"),
        "cutting_scrap_co2_kg": carbon.get("cutting_scrap_co2_kg"),
        "required_sheet_co2_kg": carbon.get("required_sheet_co2_kg"),
        "pallet_co2_kg": carbon.get("pallet_co2_kg"),
        "quantity_co2_kg": carbon.get("quantity_co2_kg"),
    })
    return serialize_corrugated_result(result)


calculate = calculate_corrugated_material_strength
