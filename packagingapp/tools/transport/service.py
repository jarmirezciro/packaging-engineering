from django.conf import settings

from .state import default_product_rows
from .serializers import sanitize_transport_rows_for_session, serialize_transport_result
from ...utils.container_tool.engine import run_container_tool


def read_product_rows_raw(post_data):
    names = post_data.getlist("item_name[]")
    lengths = post_data.getlist("item_length[]")
    widths = post_data.getlist("item_width[]")
    heights = post_data.getlist("item_height[]")
    qtys = post_data.getlist("item_qty[]")
    weights = post_data.getlist("item_weight[]")
    seqs = post_data.getlist("item_sequence[]")
    r1_vals = post_data.getlist("item_r1[]")
    r2_vals = post_data.getlist("item_r2[]")
    r3_vals = post_data.getlist("item_r3[]")

    row_count = max(
        len(names),
        len(lengths),
        len(widths),
        len(heights),
        len(qtys),
        len(weights),
        len(seqs),
        len(r1_vals),
        len(r2_vals),
        len(r3_vals),
    )

    rows = []

    def checked(value):
        return str(value).lower() in {"1", "true", "on", "yes"}

    for i in range(row_count):
        name = names[i].strip() if i < len(names) else f"Product {i+1}"
        length_raw = lengths[i].strip() if i < len(lengths) else ""
        width_raw = widths[i].strip() if i < len(widths) else ""
        height_raw = heights[i].strip() if i < len(heights) else ""
        qty_raw = qtys[i].strip() if i < len(qtys) else "1"
        weight_raw = weights[i].strip() if i < len(weights) else "0"
        seq_raw = seqs[i].strip() if i < len(seqs) else "1"

        rows.append(
            {
                "name": name or f"Product {i+1}",
                "length": length_raw,
                "width": width_raw,
                "height": height_raw,
                "qty": qty_raw if qty_raw != "" else 1,
                "weight": weight_raw if weight_raw != "" else 0,
                "sequence": seq_raw if seq_raw != "" else 1,
                "r1": checked(r1_vals[i]) if i < len(r1_vals) else False,
                "r2": checked(r2_vals[i]) if i < len(r2_vals) else False,
                "r3": checked(r3_vals[i]) if i < len(r3_vals) else False,
            }
        )

    return rows


def validate_transport_rows(raw_rows):
    rows = []
    errors = []

    if not raw_rows:
        return rows, ["Please add at least one valid product row."]

    for i, raw in enumerate(raw_rows):
        name = str(raw.get("name", "")).strip() or f"Product {i+1}"

        try:
            length = float(raw.get("length"))
            width = float(raw.get("width"))
            height = float(raw.get("height"))
            qty = int(float(raw.get("qty", 1)))
            weight = float(raw.get("weight", 0) or 0)
            sequence = int(float(raw.get("sequence", 1) or 1))
        except Exception:
            errors.append(f"Row {i+1}: invalid numeric values.")
            continue

        r1 = bool(raw.get("r1"))
        r2 = bool(raw.get("r2"))
        r3 = bool(raw.get("r3"))

        if length <= 0 or width <= 0 or height <= 0:
            errors.append(f"Row {i+1}: dimensions must be greater than 0.")
            continue
        if qty <= 0:
            errors.append(f"Row {i+1}: quantity must be greater than 0.")
            continue
        if weight < 0:
            errors.append(f"Row {i+1}: weight cannot be negative.")
            continue
        if sequence <= 0:
            errors.append(f"Row {i+1}: loading sequence must be greater than 0.")
            continue
        if not (r1 or r2 or r3):
            errors.append(f"Row {i+1}: enable at least one rotation.")
            continue

        rows.append(
            {
                "name": name,
                "length": length,
                "width": width,
                "height": height,
                "qty": qty,
                "weight": weight,
                "sequence": sequence,
                "r1": r1,
                "r2": r2,
                "r3": r3,
            }
        )

    if not rows:
        errors.append("Please add at least one valid product row.")

    return rows, errors


def build_container_from_config(cfg, selected_material=None):
    messages = []

    try:
        max_weight = float(cfg.get("max_weight") or 0)
    except Exception:
        max_weight = None
        messages.append("Please enter a valid max weight.")

    if (cfg.get("container_source") or "manual") == "catalogue":
        if not selected_material:
            messages.append("Please select a packaging item from the catalogue table.")
            return None, messages

        try:
            container = {
                "L": float(selected_material.part_length),
                "W": float(selected_material.part_width),
                "H": float(selected_material.part_height),
                "max_weight": max_weight or 0.0,
            }
        except Exception:
            messages.append("Selected packaging item has invalid dimensions.")
            return None, messages
    else:
        try:
            container = {
                "L": float(cfg.get("container_l")),
                "W": float(cfg.get("container_w")),
                "H": float(cfg.get("container_h")),
                "max_weight": float(cfg.get("max_weight")),
            }
        except Exception:
            messages.append("Please enter all manual container dimensions and max weight.")
            return None, messages

    for label, value in [
        ("length", container["L"]),
        ("width", container["W"]),
        ("height", container["H"]),
        ("max weight", container["max_weight"]),
    ]:
        if value <= 0:
            messages.append(f"Container {label} must be greater than 0.")

    return container, messages


def run_transport_analysis(container, products, media_root=None):
    result = run_container_tool(
        container=container,
        products=products,
        media_root=media_root or settings.MEDIA_ROOT,
    )
    return {
        "result": result,
        "serialized_result": serialize_transport_result(result),
        "image_url": settings.MEDIA_URL + result["image_rel_path"],
    }


def analyze_transport_config(cfg, raw_rows, selected_material=None, media_root=None):
    safe_rows = sanitize_transport_rows_for_session(raw_rows or default_product_rows())
    products, row_errors = validate_transport_rows(safe_rows)
    container, container_errors = build_container_from_config(cfg, selected_material)

    messages = list(row_errors) + list(container_errors)

    if messages:
        return {
            "ok": False,
            "messages": messages,
            "safe_rows": safe_rows,
            "products": products,
            "container": container,
            "result": None,
            "serialized_result": None,
            "image_url": None,
        }

    analysis = run_transport_analysis(
        container=container,
        products=products,
        media_root=media_root,
    )

    return {
        "ok": True,
        "messages": [],
        "safe_rows": safe_rows,
        "products": products,
        "container": container,
        "result": analysis["result"],
        "serialized_result": analysis["serialized_result"],
        "image_url": analysis["image_url"],
    }