from packagingapp.access import visible_packaging_catalogues, visible_product_catalogues, get_visible_packaging_catalogue_or_404, get_visible_product_catalogue_or_404
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from ..forms import ContainerToolForm
from ..models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
from ..tools.transport.export import build_transport_container_pdf
from ..tools.transport.presenter import selected_container_summary
from ..tools.transport.serializers import sanitize_transport_rows_for_session
from ..tools.transport.service import analyze_transport_config, read_product_rows_raw
from ..tools.transport.state import default_product_rows
from ..tools.threejs_snapshot import save_threejs_snapshot_from_request


def _format_number(value, decimals=0):
    if value in (None, "", "None"):
        return "-"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "-"


def _format_dims(l, w, h):
    return f"{_format_number(l, 0)} x {_format_number(w, 0)} x {_format_number(h, 0)} mm"


def _format_optional_weight(value):
    if value in (None, "", "None"):
        return "Not set"
    return f"{_format_number(value, 2)} kg"


def _material_value(material, attr, default="-"):
    if material is None:
        return default
    return getattr(material, attr, default) or default


def _build_transport_export_payload(*, cfg, analysis, selected_material=None):
    if not analysis.get("ok") or not analysis.get("serialized_result"):
        return None

    serialized = analysis.get("serialized_result") or {}
    summary = serialized.get("summary") or {}
    container = analysis.get("container") or {}
    result = analysis.get("result") or {}
    image_rel_paths = result.get("image_rel_paths") or {}

    if selected_material is not None:
        source = "Catalogue"
        part_number = _material_value(selected_material, "part_number")
        description = _material_value(selected_material, "part_description")
        unit_type = _material_value(selected_material, "packaging_type")
        material = _material_value(selected_material, "packaging_materials")
        dimensions = _format_dims(selected_material.part_length, selected_material.part_width, selected_material.part_height)
    else:
        source = "Manual"
        part_number = "Manual transport unit"
        description = "Manual input"
        unit_type = "Manual"
        material = "Manual input"
        dimensions = _format_dims(container.get("L"), container.get("W"), container.get("H"))

    return {
        "report_type": "standalone",
        "generated_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
        "transport_unit": {
            "source": source,
            "part_number": str(part_number),
            "description": str(description),
            "type": str(unit_type),
            "material": str(material),
            "dimensions": dimensions,
            "max_payload": _format_optional_weight(container.get("max_weight")),
            "tare_weight": _format_optional_weight(container.get("tare_weight")),
        },
        "summary": summary,
        "image_rel_path": result.get("image_rel_path") or "",
        "image_rel_paths": image_rel_paths,
    }


def _form_error_messages(form):
    messages = []
    for field_name, errors in form.errors.items():
        if field_name == "__all__":
            label = "Form"
        else:
            label = form.fields.get(field_name).label if field_name in form.fields else field_name
        for error in errors:
            messages.append(f"{label}: {error}")
    return messages


def container_tool(request):
    packaging_catalogues = visible_packaging_catalogues(request.user).order_by("name")
    product_catalogues = visible_product_catalogues(request.user).order_by("name")

    raw_action = request.POST.get("action") if request.method == "POST" else request.GET.get("action", "refresh")
    raw_catalogue_id = request.POST.get("catalogue_id") if request.method == "POST" else request.GET.get("catalogue_id", "")
    raw_container_id = request.POST.get("container_id") if request.method == "POST" else request.GET.get("container_id", "")
    raw_product_catalogue_id = request.POST.get("product_catalogue_id") if request.method == "POST" else request.GET.get("product_catalogue_id", "")
    raw_product_id_to_fill = request.POST.get("product_id_to_fill") if request.method == "POST" else request.GET.get("product_id_to_fill", "")
    raw_selected_row_index = request.POST.get("selected_row_index") if request.method == "POST" else request.GET.get("selected_row_index", "")

    result = None
    threejs_scene = None
    image_url = None
    image_urls = {}
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
            PackagingMaterial.objects.filter(catalogue__in=packaging_catalogues, id=raw_container_id)
            .select_related("catalogue")
            .first()
        )
        if selected_material and not selected_catalogue:
            selected_catalogue = selected_material.catalogue

    if raw_product_catalogue_id:
        selected_product_catalogue = visible_product_catalogues(request.user).filter(id=raw_product_catalogue_id).first()

    if raw_action == "select_product":
        selected_product = Product.objects.filter(catalogue__in=product_catalogues, id=raw_product_id_to_fill or None).first()
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
            PackagingMaterial.objects.filter(catalogue__in=packaging_catalogues, id=raw_container_id or None)
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
                    "tare_weight": selected_material.part_weight,
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
            "tare_weight": form.cleaned_data.get("tare_weight"),
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
                threejs_scene = analysis["threejs_scene"]
                image_url = analysis["image_url"]
                image_urls = analysis.get("image_urls") or {}
                export_payload = _build_transport_export_payload(
                    cfg=cfg,
                    analysis=analysis,
                    selected_material=selected_material,
                )
                if export_payload:
                    request.session["transport_container_last_export"] = export_payload
                    request.session.modified = True

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
                "tare_weight": form.cleaned_data.get("tare_weight"),
            }
        )

        if "catalogue_id" in form.fields:
            form.fields["catalogue_id"].choices = [("", "— Select —")] + [
                (str(c.id), c.name) for c in packaging_catalogues
            ]

    else:
        if request.method == "POST" and raw_action == "run_analysis":
            row_errors = _form_error_messages(form)

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
                    "tare_weight": request.POST.get("tare_weight", "") if request.method == "POST" else (selected_material.part_weight or ""),
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
            "tare_weight": form["tare_weight"].value() if "tare_weight" in form.fields else "",
        },
    )

    materials = PackagingMaterial.objects.filter(catalogue__in=packaging_catalogues).select_related("catalogue").order_by("part_number")
    if selected_catalogue:
        materials = materials.filter(catalogue=selected_catalogue)

    product_items = Product.objects.filter(catalogue__in=product_catalogues).order_by("product_name")
    if selected_product_catalogue:
        product_items = product_items.filter(catalogue=selected_product_catalogue)

    context = {
        "form": form,
        "result": result,
        "threejs_scene": threejs_scene,
        "image_url": image_url,
        "image_urls": image_urls,
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
    }

    return render(request, "container_tool/container_tool.html", context)

def container_tool_export_pdf(request):
    export_payload = request.session.get("transport_container_last_export")

    if not export_payload:
        return HttpResponse(
            "Please run a transport container analysis before exporting a PDF report.",
            status=400,
            content_type="text/plain",
        )

    snapshot_fields = {
        "main": "transport_threejs_snapshot_main",
        "top": "transport_threejs_snapshot_top",
        "opposite": "transport_threejs_snapshot_opposite",
    }
    snapshot_rel_paths = {
        view_name: save_threejs_snapshot_from_request(
            request,
            relative_directory="generated/transport_container/threejs",
            field_name=field_name,
        )
        for view_name, field_name in snapshot_fields.items()
    }
    if not all(snapshot_rel_paths.values()):
        return HttpResponse(
            "The Three.js Main, Top and Opposite side transport views are required for PDF export.",
            status=400,
            content_type="text/plain",
        )

    pdf_payload = dict(export_payload)
    pdf_payload["threejs_snapshot_rel_paths"] = snapshot_rel_paths
    pdf_buffer = build_transport_container_pdf(pdf_payload)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"transport_container_report_{timestamp}.pdf"

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
