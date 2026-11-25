import pandas as pd
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField

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

BAG_FILM_COLUMNS = ("bag_film_family", "bag_construction", "bag_film_caliper_mm", "bag_actual_weight_g")

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


def _cell_error(excel_row, column, value, message):
    return ValueError(f"Excel row {excel_row}, column {column} (value {value!r}). {message}")


def _clean_optional_property(row, excel_row, column):
    value = _optional_number(row, column)
    field = PackagingMaterial._meta.get_field(column)
    value_to_clean = value
    if isinstance(field, DecimalField) and pd.api.types.is_float(value):
        # Django parses the string as a decimal without expanding the binary float.
        value_to_clean = str(value)
    elif column == "carton_style" and value is not None:
        value_to_clean = str(value).strip().removesuffix(".0").zfill(4)
    try:
        return field.clean(value_to_clean, None)
    except ValidationError as exc:
        raise _cell_error(excel_row, column, value, " ".join(exc.messages)) from exc


@transaction.atomic
def import_packaging_excel(excel_file, catalogue):
    df = pd.read_excel(excel_file)
    df.columns = _clean_header(df.columns)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in Excel: {missing}. Found: {list(df.columns)}")

    created_count = 0
    updated_count = 0

    for excel_row, (_, row) in enumerate(df.iterrows(), start=2):
        part_number = _normalize_part_number(row["part_number"])

        raw_type = str(row["packaging_type"]).strip()
        packaging_type = PACKAGING_TYPE_MAP.get(raw_type, PACKAGING_TYPE_MAP.get(raw_type.lower()))

        if not packaging_type:
            raise _cell_error(
                excel_row, "packaging_type", row["packaging_type"],
                "Allowed values are BOX, PALLET, CRATE, BAG, CONTAINER, and TRAILER.",
            )

        optional_columns = ("box_thickness_mm", "combined_grammage_g_m2", "carton_style")
        if packaging_type == "BAG":
            optional_columns += BAG_FILM_COLUMNS
        material_properties = {
            column: _clean_optional_property(row, excel_row, column)
            for column in optional_columns
            if column in df.columns
        }
        if "corrugated_construction_code" in df.columns:
            code = _optional_number(row, "corrugated_construction_code")
            construction = None
            if code is not None:
                construction = CorrugatedBoardConstruction.objects.filter(code=str(code).strip()).first()
                if construction is None:
                    raise _cell_error(
                        excel_row, "corrugated_construction_code", code, "Unknown corrugated construction code."
                    )
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
