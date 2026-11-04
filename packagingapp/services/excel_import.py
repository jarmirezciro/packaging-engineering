import pandas as pd
from django.db import transaction
from packagingapp.models import CorrugatedBoardConstruction, PackagingMaterial

REQUIRED_COLUMNS = [
    "part_number",
    "part_description",
    "packaging_type",
    "branding",
    "packaging_materials",
    "part_length",
    "part_width",
    "part_height",
    "external_length",
    "external_width",
    "external_height",
    "part_weight",
]

OPTIONAL_COLUMNS = ["box_thickness_mm", "corrugated_construction_code", "combined_grammage_g_m2", "carton_style"]

PACKAGING_TYPE_MAP = {
    "box": "BOX",
    "pallet": "PALLET",
    "crate": "CRATE",
    "bag": "BAG",
    "container": "CONTAINER",
    "trailer": "TRAILER",
    "BOX": "BOX",
    "PALLET": "PALLET",
    "CRATE": "CRATE",
    "BAG": "BAG",
    "CONTAINER": "CONTAINER",
    "TRAILER": "TRAILER",
}

def _clean_header(columns):
    return [str(c).strip() for c in columns]

def _normalize_part_number(value):
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _optional_number(row, column):
    if column not in row.index or pd.isna(row[column]):
        return None
    return row[column]

@transaction.atomic
def import_packaging_excel(excel_file, catalogue):
    df = pd.read_excel(excel_file)
    df.columns = _clean_header(df.columns)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in Excel: {missing}. Found: {list(df.columns)}")

    created_count = 0
    updated_count = 0

    for _, row in df.iterrows():
        part_number = _normalize_part_number(row["part_number"])

        raw_type = str(row["packaging_type"]).strip()
        packaging_type = PACKAGING_TYPE_MAP.get(raw_type, PACKAGING_TYPE_MAP.get(raw_type.lower()))

        if not packaging_type:
            raise ValueError(
                f"Invalid packaging_type '{raw_type}'. Allowed values: BOX, PALLET, CRATE, BAG, CONTAINER, TRAILER."
            )

        material_properties = {}
        for column in ("box_thickness_mm", "combined_grammage_g_m2", "carton_style"):
            if column in df.columns:
                value = _optional_number(row, column)
                if column == "carton_style" and value is not None:
                    value = str(value).strip().removesuffix(".0").zfill(4)
                material_properties[column] = PackagingMaterial._meta.get_field(column).clean(value, None)
        if "corrugated_construction_code" in df.columns:
            code = _optional_number(row, "corrugated_construction_code")
            construction = None
            if code is not None:
                construction = CorrugatedBoardConstruction.objects.filter(code=str(code).strip()).first()
                if construction is None:
                    raise ValueError(f"Unknown corrugated construction code: {code}")
            material_properties["corrugated_construction"] = construction

        _, created = PackagingMaterial.objects.update_or_create(
            catalogue=catalogue,
            part_number=part_number,
            defaults={
                "part_description": str(row["part_description"]).strip(),
                "packaging_type": packaging_type,
                "branding": str(row["branding"]).strip(),
                "packaging_materials": str(row["packaging_materials"]).strip(),
                "part_length": row["part_length"],
                "part_width": row["part_width"],
                "part_height": row["part_height"],
                "external_length": _optional_number(row, "external_length"),
                "external_width": _optional_number(row, "external_width"),
                "external_height": _optional_number(row, "external_height"),
                "part_weight": _optional_number(row, "part_weight"),
                **material_properties,
            }
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    return created_count, updated_count
