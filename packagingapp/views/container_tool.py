# packagingapp/views/container_tool.py

from django.conf import settings
from django.shortcuts import render

from ..forms import ContainerToolForm
from ..utils.container_tool.engine import run_container_tool


def _parse_product_rows(post_data):
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
        len(names), len(lengths), len(widths), len(heights),
        len(qtys), len(weights), len(seqs)
    )

    rows = []
    errors = []

    def checked(value):
        return str(value).lower() in {"1", "true", "on", "yes"}

    for i in range(row_count):
        name = names[i].strip() if i < len(names) else f"Product {i+1}"
        length_raw = lengths[i].strip() if i < len(lengths) else ""
        width_raw = widths[i].strip() if i < len(widths) else ""
        height_raw = heights[i].strip() if i < len(heights) else ""
        qty_raw = qtys[i].strip() if i < len(qtys) else ""
        weight_raw = weights[i].strip() if i < len(weights) else ""
        seq_raw = seqs[i].strip() if i < len(seqs) else ""

        r1 = checked(r1_vals[i]) if i < len(r1_vals) else False
        r2 = checked(r2_vals[i]) if i < len(r2_vals) else False
        r3 = checked(r3_vals[i]) if i < len(r3_vals) else False

        # skip fully empty row
        if not any([name, length_raw, width_raw, height_raw, qty_raw, weight_raw, seq_raw, r1, r2, r3]):
            continue

        try:
            length = float(length_raw)
            width = float(width_raw)
            height = float(height_raw)
            qty = int(float(qty_raw))
            weight = float(weight_raw) if weight_raw != "" else 0.0
            sequence = int(float(seq_raw)) if seq_raw != "" else 1
        except ValueError:
            errors.append(f"Row {i+1}: invalid numeric values.")
            continue

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

        rows.append({
            "name": name or f"Product {i+1}",
            "length": length,
            "width": width,
            "height": height,
            "qty": qty,
            "weight": weight,
            "sequence": sequence,
            "r1": r1,
            "r2": r2,
            "r3": r3,
        })

    if not rows:
        errors.append("Please add at least one valid product row.")

    return rows, errors


def container_tool(request):
    result = None
    image_url = None
    row_errors = []

    if request.method == "POST":
        form = ContainerToolForm(request.POST)
    else:
        form = ContainerToolForm(
            initial={
                "container_l": 12032,
                "container_w": 2352,
                "container_h": 2698,
                "max_weight": 26000,
            }
        )

    product_rows = []

    if request.method == "POST" and form.is_valid():
        product_rows, row_errors = _parse_product_rows(request.POST)

        if not row_errors:
            container = {
                "L": float(form.cleaned_data["container_l"]),
                "W": float(form.cleaned_data["container_w"]),
                "H": float(form.cleaned_data["container_h"]),
                "max_weight": float(form.cleaned_data["max_weight"]),
            }

            result = run_container_tool(
                container=container,
                products=product_rows,
                media_root=settings.MEDIA_ROOT,
            )
            image_url = settings.MEDIA_URL + result["image_rel_path"]

    elif request.method == "POST":
        # preserve rows even when form is invalid
        product_rows, row_errors = _parse_product_rows(request.POST)

    if request.method == "GET" and not product_rows:
        product_rows = [
            {
                "name": "Product 1",
                "length": "",
                "width": "",
                "height": "",
                "qty": 1,
                "weight": 0,
                "sequence": 1,
                "r1": True,
                "r2": False,
                "r3": False,
            }
        ]

    return render(
        request,
        "container_tool/container_tool.html",
        {
            "form": form,
            "result": result,
            "image_url": image_url,
            "product_rows": product_rows,
            "row_errors": row_errors,
        }
    )