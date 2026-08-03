from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MaterialResult:
    combined_grammage_g_m2: Decimal
    finished_box_weight_g: Decimal
    blank_bounding_weight_g: Decimal
    production_sheet_weight_g: Decimal
    cutting_scrap_weight_g: Decimal
    gross_packed_box_weight_g: Decimal


def calculate_material(geometry, combined_grammage_g_m2, product_weight_g):
    grammage = Decimal(str(combined_grammage_g_m2))
    product_weight = Decimal(str(product_weight_g))
    if grammage <= 0:
        raise ValueError("Combined grammage must be greater than zero.")
    if product_weight < 0:
        raise ValueError("Product weight cannot be negative.")
    finished = geometry.effective_box_area_m2 * grammage
    blank = geometry.blank_bounding_area_m2 * grammage
    sheet = geometry.production_sheet_area_m2 * grammage
    scrap = sheet - finished
    return MaterialResult(
        combined_grammage_g_m2=grammage,
        finished_box_weight_g=finished,
        blank_bounding_weight_g=blank,
        production_sheet_weight_g=sheet,
        cutting_scrap_weight_g=scrap,
        gross_packed_box_weight_g=product_weight + finished,
    )
