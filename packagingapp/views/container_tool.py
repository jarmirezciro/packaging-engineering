# packagingapp/views/container_tool.py

from django.conf import settings
from django.shortcuts import render

from ..forms import ContainerToolForm
from ..models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
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


def _read_product_rows_raw(post_data):
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
        len(qtys), len(weights), len(seqs),
        len(r1_vals), len(r2_vals), len(r3_vals)
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

        r1 = checked(r1_vals[i]) if i < len(r1_vals) else False
        r2 = checked(r2_vals[i]) if i < len(r2_vals) else False
        r3 = checked(r3_vals[i]) if i < len(r3_vals) else False

        rows.append({
            "name": name or f"Product {i+1}",
            "length": length_raw,
            "width": width_raw,
            "height": height_raw,
            "qty": qty_raw if qty_raw != "" else 1,
            "weight": weight_raw if weight_raw != "" else 0,
            "sequence": seq_raw if seq_raw != "" else 1,
            "r1": r1,
            "r2": r2,
            "r3": r3,
        })

    return rows


def _default_product_rows():
    return [
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


def _selected_container_summary(selected_material, form):
    if selected_material:
        return {
            "title": f"{selected_material.part_number} — {selected_material.part_description}",
            "dims": f"{selected_material.part_length} × {selected_material.part_width} × {selected_material.part_height}",
            "meta": f"{selected_material.packaging_type} | {selected_material.branding}",
            "max_weight": form["max_weight"].value() or "",
        }

    return {
        "title": "Manual container",
        "dims": f'{form["container_l"].value() or ""} × {form["container_w"].value() or ""} × {form["container_h"].value() or ""}',
        "meta": "Manual dimensions",
        "max_weight": form["max_weight"].value() or "",
    }


def container_tool(request):
    result = None
    image_url = None
    row_errors = []

    packaging_materials = PackagingMaterial.objects.none()
    selected_material = None

    product_items = Product.objects.none()
    selected_row_index = request.POST.get("selected_row_index") or request.GET.get("selected_row_index") or ""
    product_catalogue_id = request.POST.get("product_catalogue_id") or request.GET.get("product_catalogue_id") or ""
    product_id_to_fill = request.POST.get("product_id_to_fill") or request.GET.get("product_id_to_fill") or ""
    scroll_target = request.POST.get("scroll_target") or request.GET.get("scroll_target") or ""

    auto_hide_product_catalogue = False

    if request.method == "POST":
        form = ContainerToolForm(request.POST)
    else:
        form = ContainerToolForm(
            initial={
                "container_source": "manual",
                "container_l": 12032,
                "container_w": 2352,
                "container_h": 2698,
                "max_weight": 26000,
            }
        )

    packaging_catalogues = PackagingCatalogue.objects.all().order_by("name")
    product_catalogues = ProductCatalogue.objects.all().order_by("name")

    form.fields["catalogue_id"].choices = [("", "— Select —")] + [
        (str(c.id), c.name) for c in packaging_catalogues
    ]

    raw_container_source = request.POST.get("container_source") or request.GET.get("container_source") or "manual"
    raw_catalogue_id = request.POST.get("catalogue_id") or request.GET.get("catalogue_id") or ""
    raw_container_id = request.POST.get("container_id") or request.GET.get("container_id") or ""
    raw_action = request.POST.get("action") or ""

    if raw_catalogue_id:
        packaging_materials = PackagingMaterial.objects.filter(
            catalogue_id=raw_catalogue_id
        ).select_related("catalogue").order_by("part_number")

    if raw_container_id:
        selected_material = PackagingMaterial.objects.filter(
            id=raw_container_id
        ).select_related("catalogue").first()

    if product_catalogue_id:
        product_items = Product.objects.filter(
            catalogue_id=product_catalogue_id
        ).select_related("catalogue").order_by("product_id", "product_name")

    if request.method == "POST":
        if raw_action == "run_analysis":
            product_rows, row_errors = _parse_product_rows(request.POST)
            if not product_rows:
                product_rows = _default_product_rows()
        else:
            product_rows = _read_product_rows_raw(request.POST)
            if not product_rows:
                product_rows = _default_product_rows()
            row_errors = []
    else:
        product_rows = _default_product_rows()

    if raw_action == "select_product" and product_id_to_fill and selected_row_index != "":
        selected_product = Product.objects.filter(id=product_id_to_fill).first()

        try:
            idx = int(selected_row_index)
        except Exception:
            idx = None

        if selected_product is not None and idx is not None and 0 <= idx < len(product_rows):
            product_rows[idx]["name"] = selected_product.product_name or selected_product.product_id or f"Product {idx + 1}"
            product_rows[idx]["length"] = selected_product.product_length
            product_rows[idx]["width"] = selected_product.product_width
            product_rows[idx]["height"] = selected_product.product_height
            product_rows[idx]["weight"] = selected_product.weight or 0
            product_rows[idx]["r1"] = bool(selected_product.rotation_1)
            product_rows[idx]["r2"] = bool(selected_product.rotation_2)
            product_rows[idx]["r3"] = bool(selected_product.rotation_3)

            auto_hide_product_catalogue = True
            selected_row_index = ""
            scroll_target = ""

    if request.method == "POST" and form.is_valid():
        container_source = form.cleaned_data.get("container_source") or "manual"

        container_l = float(form.cleaned_data["container_l"])
        container_w = float(form.cleaned_data["container_w"])
        container_h = float(form.cleaned_data["container_h"])
        max_weight = float(form.cleaned_data["max_weight"])

        if container_source == "catalogue" and selected_material:
            container_l = float(selected_material.part_length)
            container_w = float(selected_material.part_width)
            container_h = float(selected_material.part_height)

        if raw_action == "run_analysis" and not row_errors:
            container = {
                "L": container_l,
                "W": container_w,
                "H": container_h,
                "max_weight": max_weight,
            }

            result = run_container_tool(
                container=container,
                products=product_rows,
                media_root=settings.MEDIA_ROOT,
            )
            image_url = settings.MEDIA_URL + result["image_rel_path"]

        form = ContainerToolForm(
            initial={
                "container_source": container_source,
                "catalogue_id": raw_catalogue_id,
                "container_id": raw_container_id,
                "container_l": container_l,
                "container_w": container_w,
                "container_h": container_h,
                "max_weight": max_weight,
            }
        )
        form.fields["catalogue_id"].choices = [("", "— Select —")] + [
            (str(c.id), c.name) for c in packaging_catalogues
        ]

    container_summary = _selected_container_summary(selected_material, form)

    return render(
        request,
        "container_tool/container_tool.html",
        {
            "form": form,
            "result": result,
            "image_url": image_url,
            "product_rows": product_rows,
            "row_errors": row_errors,
            "materials": packaging_materials,
            "selected_material": selected_material,
            "current_container_source": raw_container_source,
            "current_catalogue_id": raw_catalogue_id,
            "container_summary": container_summary,
            "product_catalogues": product_catalogues,
            "product_items": product_items,
            "product_catalogue_id": product_catalogue_id,
            "selected_row_index": selected_row_index,
            "auto_hide_product_catalogue": auto_hide_product_catalogue,
            "scroll_target": scroll_target,
        }
    )