from packagingapp.access import visible_packaging_catalogues, visible_product_catalogues, get_visible_packaging_catalogue_or_404, get_visible_product_catalogue_or_404
from django.conf import settings
from django.shortcuts import render

from ..forms import ContainerToolForm
from ..models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
from ..tools.transport.presenter import selected_container_summary
from ..tools.transport.serializers import sanitize_transport_rows_for_session
from ..tools.transport.service import analyze_transport_config, read_product_rows_raw
from ..tools.transport.state import default_product_rows


def container_tool(request):
    packaging_catalogues = visible_packaging_catalogues(request.user).order_by("name")
    product_catalogues = visible_product_catalogues(request.user).order_by("name")

    raw_action = request.POST.get("action") if request.method == "POST" else request.GET.get("action", "refresh")
    raw_catalogue_id = request.POST.get("catalogue_id") if request.method == "POST" else request.GET.get("catalogue_id", "")
    raw_container_id = request.POST.get("container_id") if request.method == "POST" else request.GET.get("container_id", "")
    raw_product_catalogue_id = request.POST.get("product_catalogue_id") if request.method == "POST" else request.GET.get("product_catalogue_id", "")
    raw_product_id_to_fill = request.POST.get("product_id_to_fill") if request.method == "POST" else request.GET.get("product_id_to_fill", "")
    raw_selected_row_index = request.POST.get("selected_row_index") if request.method == "POST" else request.GET.get("selected_row_index", "")
    raw_scroll_target = request.POST.get("scroll_target") if request.method == "POST" else request.GET.get("scroll_target", "")

    result = None
    image_url = None
    row_errors = []
    auto_hide_product_catalogue = False

    if request.method == "POST":
        product_rows = read_product_rows_raw(request.POST)
        if not product_rows:
            product_rows = default_product_rows()
    else:
        product_rows = default_product_rows()

    current_container_source = (
        request.POST.get("container_source")
        if request.method == "POST"
        else "manual"
    ) or "manual"

    selected_catalogue = None
    selected_material = None
    selected_product_catalogue = None

    if raw_catalogue_id:
        selected_catalogue = visible_packaging_catalogues(request.user).filter(id=raw_catalogue_id).first()

    if raw_container_id:
        selected_material = (
            PackagingMaterial.objects.filter(id=raw_container_id)
            .select_related("catalogue")
            .first()
        )
        if selected_material and not selected_catalogue:
            selected_catalogue = selected_material.catalogue

    if raw_product_catalogue_id:
        selected_product_catalogue = visible_product_catalogues(request.user).filter(id=raw_product_catalogue_id).first()

    if raw_action == "select_product":
        selected_product = Product.objects.filter(id=raw_product_id_to_fill or None).first()
        try:
            row_idx = int(raw_selected_row_index)
        except Exception:
            row_idx = None

        if selected_product is not None and row_idx is not None and 0 <= row_idx < len(product_rows):
            row = product_rows[row_idx]
            row["name"] = selected_product.product_name or selected_product.product_id or f"Product {row_idx + 1}"
            row["length"] = float(selected_product.product_length)
            row["width"] = float(selected_product.product_width)
            row["height"] = float(selected_product.product_height)
            row["weight"] = float(getattr(selected_product, "weight", 0) or 0)
            row["r1"] = bool(getattr(selected_product, "rotation_1", False))
            row["r2"] = bool(getattr(selected_product, "rotation_2", False))
            row["r3"] = bool(getattr(selected_product, "rotation_3", False))

            product_rows = sanitize_transport_rows_for_session(product_rows)
            raw_selected_row_index = ""
            raw_product_id_to_fill = ""
            auto_hide_product_catalogue = True

    if raw_action == "select_container":
        selected_material = (
            PackagingMaterial.objects.filter(id=raw_container_id or None)
            .select_related("catalogue")
            .first()
        )
        if selected_material is not None:
            raw_container_id = str(selected_material.id)
            if not selected_catalogue:
                selected_catalogue = selected_material.catalogue
            current_container_source = "catalogue"

    if current_container_source != "catalogue":
        raw_container_id = ""
        selected_material = None

    #
    # IMPORTANT FIX:
    # hydrate POST with selected material dimensions BEFORE binding the form
    #
    if request.method == "POST":
        post_data = request.POST.copy()

        if current_container_source == "catalogue" and selected_material is not None:
            post_data["container_l"] = str(selected_material.part_length or "")
            post_data["container_w"] = str(selected_material.part_width or "")
            post_data["container_h"] = str(selected_material.part_height or "")

        form = ContainerToolForm(post_data)
    else:
        initial_data = {
            "container_source": "manual",
        }

        if selected_material is not None and current_container_source == "catalogue":
            initial_data.update(
                {
                    "catalogue_id": raw_catalogue_id,
                    "container_id": raw_container_id,
                    "container_l": selected_material.part_length,
                    "container_w": selected_material.part_width,
                    "container_h": selected_material.part_height,
                }
            )

        form = ContainerToolForm(initial=initial_data)

    if "catalogue_id" in form.fields:
        form.fields["catalogue_id"].choices = [("", "— Select —")] + [
            (str(c.id), c.name) for c in packaging_catalogues
        ]

    if request.method == "POST" and form.is_valid():
        current_container_source = form.cleaned_data.get("container_source") or "manual"

        cfg = {
            "container_source": current_container_source,
            "container_l": form.cleaned_data.get("container_l"),
            "container_w": form.cleaned_data.get("container_w"),
            "container_h": form.cleaned_data.get("container_h"),
            "max_weight": form.cleaned_data.get("max_weight"),
            "catalogue_id": raw_catalogue_id,
            "container_id": raw_container_id,
            "product_catalogue_id": raw_product_catalogue_id,
            "selected_row_index": raw_selected_row_index,
            "product_id_to_fill": raw_product_id_to_fill,
        }

        if raw_action == "run_analysis":
            analysis = analyze_transport_config(
                cfg,
                product_rows,
                selected_material=selected_material,
                media_root=settings.MEDIA_ROOT,
            )
            product_rows = analysis["safe_rows"]
            row_errors = analysis["messages"]

            if analysis["ok"]:
                result = analysis["serialized_result"]
                image_url = analysis["image_url"]

        if selected_material is not None and current_container_source == "catalogue":
            container_l_value = selected_material.part_length
            container_w_value = selected_material.part_width
            container_h_value = selected_material.part_height
        else:
            container_l_value = form.cleaned_data.get("container_l")
            container_w_value = form.cleaned_data.get("container_w")
            container_h_value = form.cleaned_data.get("container_h")

        form = ContainerToolForm(
            initial={
                "container_source": current_container_source,
                "catalogue_id": raw_catalogue_id,
                "container_id": raw_container_id,
                "container_l": container_l_value,
                "container_w": container_w_value,
                "container_h": container_h_value,
                "max_weight": form.cleaned_data.get("max_weight"),
            }
        )

        if "catalogue_id" in form.fields:
            form.fields["catalogue_id"].choices = [("", "— Select —")] + [
                (str(c.id), c.name) for c in packaging_catalogues
            ]

    else:
        if selected_material is not None and current_container_source == "catalogue":
            form = ContainerToolForm(
                initial={
                    "container_source": current_container_source,
                    "catalogue_id": raw_catalogue_id,
                    "container_id": raw_container_id,
                    "container_l": selected_material.part_length,
                    "container_w": selected_material.part_width,
                    "container_h": selected_material.part_height,
                    "max_weight": request.POST.get("max_weight", "") if request.method == "POST" else "",
                }
            )

            if "catalogue_id" in form.fields:
                form.fields["catalogue_id"].choices = [("", "— Select —")] + [
                    (str(c.id), c.name) for c in packaging_catalogues
                ]

    container_summary = selected_container_summary(
        selected_material,
        {
            "container_source": current_container_source,
            "container_l": form["container_l"].value() if "container_l" in form.fields else "",
            "container_w": form["container_w"].value() if "container_w" in form.fields else "",
            "container_h": form["container_h"].value() if "container_h" in form.fields else "",
            "max_weight": form["max_weight"].value() if "max_weight" in form.fields else "",
        },
    )

    materials = PackagingMaterial.objects.all().select_related("catalogue").order_by("part_number")
    if selected_catalogue:
        materials = materials.filter(catalogue=selected_catalogue)

    product_items = Product.objects.all().order_by("product_name")
    if selected_product_catalogue:
        product_items = product_items.filter(catalogue=selected_product_catalogue)

    context = {
        "form": form,
        "result": result,
        "image_url": image_url,
        "row_errors": row_errors,
        "product_rows": product_rows,
        "packaging_catalogues": packaging_catalogues,
        "product_catalogues": product_catalogues,
        "current_container_source": current_container_source,
        "current_catalogue_id": raw_catalogue_id,
        "materials": materials,
        "selected_material": selected_material,
        "container_summary": container_summary,
        "product_catalogue_id": raw_product_catalogue_id,
        "product_items": product_items,
        "selected_row_index": raw_selected_row_index,
        "auto_hide_product_catalogue": auto_hide_product_catalogue,
        "scroll_target": raw_scroll_target,
    }

    return render(request, "container_tool/container_tool.html", context)