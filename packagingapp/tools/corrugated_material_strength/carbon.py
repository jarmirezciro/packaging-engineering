from decimal import Decimal


def calculate_carbon(
    *, factor_kg_co2e_per_kg, source_label, boundary,
    finished_box_weight_g, cutting_scrap_weight_g, production_sheet_weight_g,
    boxes_per_pallet, quantity,
):
    if factor_kg_co2e_per_kg is None:
        return {
            "available": False, "factor_kg_co2e_per_kg": None,
            "source_label": source_label, "boundary": boundary,
            "finished_box_co2_kg": None, "cutting_scrap_co2_kg": None,
            "required_sheet_co2_kg": None, "pallet_co2_kg": None,
            "quantity_co2_kg": None,
        }
    factor = Decimal(str(factor_kg_co2e_per_kg))
    if factor < 0:
        raise ValueError("CO₂ factor cannot be negative.")
    finished = Decimal(str(finished_box_weight_g)) / Decimal("1000") * factor
    scrap = Decimal(str(cutting_scrap_weight_g)) / Decimal("1000") * factor
    sheet = Decimal(str(production_sheet_weight_g)) / Decimal("1000") * factor
    pallet_co2 = None if boxes_per_pallet is None else sheet * Decimal(str(boxes_per_pallet))
    return {
        "available": True, "factor_kg_co2e_per_kg": factor,
        "source_label": source_label, "boundary": boundary,
        "finished_box_co2_kg": finished, "cutting_scrap_co2_kg": scrap,
        "required_sheet_co2_kg": sheet,
        "pallet_co2_kg": pallet_co2,
        "quantity_co2_kg": sheet * Decimal(str(quantity)),
        "label": "Material-based CO₂ screening estimate",
        "note": (
            "This is not a formal product carbon footprint. It applies a selected "
            "mass-based factor to the calculated corrugated material."
        ),
    }
