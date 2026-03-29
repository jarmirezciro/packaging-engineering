import pandas as pd
from packagingapp.models import Product


REQUIRED_COLUMNS = [
    "product_id",
    "product_name",
    "product_length",
    "product_width",
    "product_height",
    "rotation_1",
    "rotation_2",
    "rotation_3",
    "weight",
    "desired_qty",
]


def _clean_header(columns):
    return [str(c).strip() for c in columns]


def _normalize_product_id(value):
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _to_bool(value, default=False):
    if pd.isna(value):
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "y"}:
        return True
    if s in {"0", "false", "no", "n"}:
        return False
    return default


def import_product_excel(excel_file, catalogue):
    df = pd.read_excel(excel_file)
    df.columns = _clean_header(df.columns)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in Excel: {missing}. Found: {list(df.columns)}")

    created_count = 0
    updated_count = 0

    for _, row in df.iterrows():
        product_id = _normalize_product_id(row["product_id"])

        defaults = {
            "product_name": None if pd.isna(row["product_name"]) else str(row["product_name"]).strip(),
            "product_length": row["product_length"],
            "product_width": row["product_width"],
            "product_height": row["product_height"],
            "rotation_1": _to_bool(row["rotation_1"], True),
            "rotation_2": _to_bool(row["rotation_2"], False),
            "rotation_3": _to_bool(row["rotation_3"], False),
            "weight": None if pd.isna(row["weight"]) else row["weight"],
            "desired_qty": 1 if pd.isna(row["desired_qty"]) else int(row["desired_qty"]),
        }

        if product_id:
            _, created = Product.objects.update_or_create(
                catalogue=catalogue,
                product_id=product_id,
                defaults=defaults,
            )
        else:
            obj = Product.objects.create(
                catalogue=catalogue,
                **defaults,
            )
            created = True

        if created:
            created_count += 1
        else:
            updated_count += 1

    return created_count, updated_count