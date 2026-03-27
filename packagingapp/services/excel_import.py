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
]

def import_packaging_excel(excel_file, catalogue):
    df = pd.read_excel(excel_file)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in Excel: {missing}")

    for _, row in df.iterrows():
        PackagingMaterial.objects.update_or_create(
            catalogue=catalogue,
            part_number=str(row["part_number"]).strip(),
            defaults={
                "part_description": str(row["part_description"]).strip(),
                "packaging_type": str(row["packaging_type"]).strip(),
                "branding": str(row["branding"]).strip(),
                "packaging_materials": str(row["packaging_materials"]).strip(),
                "part_length": row["part_length"],
                "part_width": row["part_width"],
                "part_height": row["part_height"],
            }
        )