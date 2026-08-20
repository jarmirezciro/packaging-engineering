import pandas as pd
from packagingapp.models import PackagingMaterial

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

OPTIONAL_COLUMNS = ["box_thickness_mm"]

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

def import_packaging_excel(excel_file, catalogue):
    df = pd.read_excel(excel_file)
    df.columns = _clean_header(df.columns)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in Excel: {missing}. Found: {list(df.columns)}")
    for column in OPTIONAL_COLUMNS:
        if column not in df.columns:
            df[column] = None

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
                "external_length": row["external_length"],
                "external_width": row["external_width"],
                "external_height": row["external_height"],
                "box_thickness_mm": _optional_number(row, "box_thickness_mm"),
                "part_weight": row["part_weight"],
            }
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    return created_count, updated_count
