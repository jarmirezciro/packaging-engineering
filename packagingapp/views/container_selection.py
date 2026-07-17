from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse
from django.utils import timezone

from ..tools.container.presenter import (
    selected_container_summary,
    selected_product_summary,
)
from ..tools.container.serializers import sanitize_container_config_for_session
from ..tools.container.service import (
    analyze_container_form,
    apply_catalogue_choices,
    build_container_form,
    get_materials_for_catalogue,
    get_packaging_catalogues,
    get_product_catalogues,
    get_products_for_catalogue,
    get_selected_material,
    get_selected_product,
)
from ..tools.container.state import default_container_config
from ..tools.container.export import build_container_selection_pdf
from ..tools.threejs_snapshot import save_threejs_snapshot_from_request


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _read_raw_container_config(request):
    cfg = default_container_config()

    if request.method == "POST":
        source = request.POST
    else:
        source = request.GET

    cfg.update({
        "mode": source.get("mode", cfg["mode"]),
        "action": source.get("action", cfg["action"]),

        "product_source": source.get("product_source", cfg["product_source"]),
        "product_catalogue_id": source.get("product_catalogue_id", cfg["product_catalogue_id"]),
        "selected_product_id": source.get("selected_product_id", cfg["selected_product_id"]),
        "product_l": source.get("product_l", cfg["product_l"]),
        "product_w": source.get("product_w", cfg["product_w"]),
        "product_h": source.get("product_h", cfg["product_h"]),
        "product_weight": source.get("product_weight", cfg["product_weight"]),
        "desired_qty": source.get("desired_qty", cfg["desired_qty"]),
        "r1": _as_bool(source.get("r1", cfg["r1"])),
        "r2": _as_bool(source.get("r2", cfg["r2"])),
        "r3": _as_bool(source.get("r3", cfg["r3"])),

        "container_source": source.get("container_source", cfg["container_source"]),
        "catalogue_id": source.get("catalogue_id", cfg["catalogue_id"]),
        "container_id": source.get("container_id", cfg["container_id"]),
        "box_l": source.get("box_l", cfg["box_l"]),
        "box_w": source.get("box_w", cfg["box_w"]),
        "box_h": source.get("box_h", cfg["box_h"]),
        "box_weight": source.get("box_weight", cfg["box_weight"]),
        "box_max_payload": source.get("box_max_payload", cfg["box_max_payload"]),
    })

    return sanitize_container_config_for_session(cfg)


def _build_shared_container_ui_contract(prefix=""):
    suffix = f"_{prefix}" if prefix else ""

    return {
        "prefix": prefix,
        "names": {
            "action": f"action{suffix}",
            "mode": f"mode{suffix}",
            "product_source": f"product_source{suffix}",
            "product_catalogue_id": f"product_catalogue_id{suffix}",
            "selected_product_id": f"selected_product_id{suffix}",
            "product_l": f"product_l{suffix}",
            "product_w": f"product_w{suffix}",
            "product_h": f"product_h{suffix}",
            "product_weight": f"product_weight{suffix}",
            "desired_qty": f"desired_qty{suffix}",
            "r1": f"r1{suffix}",
            "r2": f"r2{suffix}",
            "r3": f"r3{suffix}",
            "container_source": f"container_source{suffix}",
            "catalogue_id": f"catalogue_id{suffix}",
            "container_id": f"container_id{suffix}",
            "box_l": f"box_l{suffix}",
            "box_w": f"box_w{suffix}",
            "box_h": f"box_h{suffix}",
            "box_weight": f"box_weight{suffix}",
            "box_max_payload": f"box_max_payload{suffix}",
        },
        "ids": {
            "root": f"containerSelectionRoot{suffix}",
            "product_catalogue_section": f"productCatalogueSection{suffix}",
            "container_catalogue_section": f"containerCatalogueSection{suffix}",
            "manual_product_fields": f"manualProductFields{suffix}",
            "manual_container_fields": f"manualContainerFields{suffix}",
            "selected_product_id": f"selected_product_id{suffix}",
            "container_id": f"container_id{suffix}",
            "threejs_viewer": f"containerThreeJsViewer{suffix}",
            "threejs_scene": f"containerThreeJsScene{suffix}",
        },
        "actions": {
            "refresh": "containerSelectionRefresh",
            "run_single": "containerSelectionRunSingle",
            "find_top5": "containerSelectionFindTop5",
            "select_product": "containerSelectionSelectProduct",
            "select_container": "containerSelectionSelectContainer",
            "select_candidate": "containerSelectionSelectCandidate",
        },
    }



def _format_dims(length, width, height):
    return f"{length} × {width} × {height} mm"


def _format_optional_weight(value, default="Not available"):
    if value in (None, "", "None"):
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if abs(numeric) >= 1000:
        return f"{int(round(numeric / 1000))} kg"
    return f"{int(round(numeric))} g"


def _rotation_display(r1, r2, r3):
    rotations = []
    if r1:
        rotations.append("R1 — Length vertical")
    if r2:
        rotations.append("R2 — Width vertical")
    if r3:
        rotations.append("R3 — Height vertical")
    return ", ".join(rotations) if rotations else "None"


def _build_single_export_payload(*, form, analysis, selected_product, selected_material):
    analysis_report = analysis.get("analysis_report")
    result = analysis.get("result")

    if not analysis_report or not result:
        return None

    product_source = form.cleaned_data.get("product_source") or "manual"
    container_source = form.cleaned_data.get("container_source") or "manual"

    if selected_product:
        product_id = selected_product.product_id
        product_name = selected_product.product_name
        product_l = selected_product.product_length
        product_w = selected_product.product_width
        product_h = selected_product.product_height
        product_weight = getattr(selected_product, "weight", None)
        r1 = bool(getattr(selected_product, "rotation_1", False))
        r2 = bool(getattr(selected_product, "rotation_2", False))
        r3 = bool(getattr(selected_product, "rotation_3", False))
    else:
        product_id = "Manual product"
        product_name = "Manual input"
        product_l = form.cleaned_data.get("product_l")
        product_w = form.cleaned_data.get("product_w")
        product_h = form.cleaned_data.get("product_h")
        product_weight = form.cleaned_data.get("product_weight")
        r1 = bool(form.cleaned_data.get("r1"))
        r2 = bool(form.cleaned_data.get("r2"))
        r3 = bool(form.cleaned_data.get("r3"))

    if selected_material:
        container_part_number = selected_material.part_number
        container_description = selected_material.part_description
        container_type = selected_material.packaging_type
        container_material = selected_material.packaging_materials
        container_l = selected_material.part_length
        container_w = selected_material.part_width
        container_h = selected_material.part_height
        container_tare = getattr(selected_material, "part_weight", None)
        payload_capacity = analysis_report.get("payload_capacity")
    else:
        container_part_number = "Manual packaging"
        container_description = "Manual input"
        container_type = "Manual"
        container_material = "Manual input"
        container_l = form.cleaned_data.get("box_l")
        container_w = form.cleaned_data.get("box_w")
        container_h = form.cleaned_data.get("box_h")
        container_tare = form.cleaned_data.get("box_weight")
        payload_capacity = form.cleaned_data.get("box_max_payload")

    return {
        "report_type": "single",
        "generated_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
        "product": {
            "source": "Catalogue" if product_source == "catalogue" else "Manual",
            "id": product_id,
            "name": product_name or "—",
            "dimensions": _format_dims(product_l, product_w, product_h),
            "weight": _format_optional_weight(product_weight),
            "desired_qty": f"{form.cleaned_data.get('desired_qty') or 1} pcs",
            "rotations": _rotation_display(r1, r2, r3),
        },
        "container": {
            "source": "Catalogue" if container_source == "catalogue" else "Manual",
            "part_number": container_part_number,
            "description": container_description or "—",
            "type": container_type or "—",
            "material": container_material or "—",
            "dimensions": _format_dims(container_l, container_w, container_h),
            "tare": _format_optional_weight(container_tare),
            "payload_capacity": _format_optional_weight(payload_capacity),
        },
        "analysis_report": analysis_report,
        "image_rel_path": getattr(result, "image_rel_path", ""),
        "product_base_image_rel_path": analysis.get("product_base_image_rel_path", ""),
    }


def _format_usage(value):
    if value in (None, "", "None"):
        return "Not available"
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "Not available"


def _format_part_volume(value):
    if value in (None, "", "None"):
        return "-"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{int(round(numeric))} mm3"


def _catalogue_name_from_choice(form, field_name):
    value = str(form.cleaned_data.get(field_name) or "")
    for option_value, label in form.fields[field_name].choices:
        if str(option_value) == value:
            return str(label)
    return "Selected catalogue"


def _top5_export_rows(top5):
    rows = []
    for idx, row in enumerate(top5 or [], start=1):
        material = row.get("material")
        if material is None:
            continue

        rows.append({
            "rank": idx,
            "part_number": material.part_number,
            "description": material.part_description,
            "type": material.packaging_type,
            "brand": material.branding,
            "material": material.packaging_materials,
            "dimensions": _format_dims(material.part_length, material.part_width, material.part_height),
            "weight": _format_optional_weight(getattr(material, "part_weight", None)),
            "volume": _format_part_volume(getattr(material, "part_volume", None)),
            "max_qty": row.get("max_qty"),
            "usage_display": _format_usage(row.get("usage")),
        })

    return rows


def _build_optimal_export_payload(*, form, top5, selected_product, analysis=None, selected_material=None):
    if not top5:
        return None

    product_source = form.cleaned_data.get("product_source") or "manual"

    if selected_product:
        product_id = selected_product.product_id
        product_name = selected_product.product_name
        product_l = selected_product.product_length
        product_w = selected_product.product_width
        product_h = selected_product.product_height
        product_weight = getattr(selected_product, "weight", None)
        r1 = bool(getattr(selected_product, "rotation_1", False))
        r2 = bool(getattr(selected_product, "rotation_2", False))
        r3 = bool(getattr(selected_product, "rotation_3", False))
    else:
        product_id = "Manual product"
        product_name = "Manual input"
        product_l = form.cleaned_data.get("product_l")
        product_w = form.cleaned_data.get("product_w")
        product_h = form.cleaned_data.get("product_h")
        product_weight = form.cleaned_data.get("product_weight")
        r1 = bool(form.cleaned_data.get("r1"))
        r2 = bool(form.cleaned_data.get("r2"))
        r3 = bool(form.cleaned_data.get("r3"))

    desired_qty = form.cleaned_data.get("desired_qty") or 1

    result = (analysis or {}).get("result")
    analysis_report = (analysis or {}).get("analysis_report") or {}

    selected_candidate = None
    if selected_material is not None:
        selected_candidate = {
            "part_number": selected_material.part_number,
            "description": selected_material.part_description,
            "type": selected_material.packaging_type,
            "dimensions": _format_dims(selected_material.part_length, selected_material.part_width, selected_material.part_height),
        }

    return {
        "report_type": "optimal",
        "generated_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
        "catalogue_name": _catalogue_name_from_choice(form, "catalogue_id"),
        "image_rel_path": getattr(result, "image_rel_path", "") if result else "",
        "selected_candidate": selected_candidate,
        "analysis_report": analysis_report,
        "product_base_image_rel_path": (analysis or {}).get("product_base_image_rel_path", ""),
        "product": {
            "source": "Catalogue" if product_source == "catalogue" else "Manual",
            "id": product_id,
            "name": product_name or "-",
            "dimensions": _format_dims(product_l, product_w, product_h),
            "weight": _format_optional_weight(product_weight),
            "desired_qty": f"{desired_qty} pcs",
            "rotations": _rotation_display(r1, r2, r3),
        },
        "top5": _top5_export_rows(top5),
    }


def _save_threejs_snapshot_from_request(request):
    return save_threejs_snapshot_from_request(
        request,
        relative_directory="container_exports/threejs",
    )


def _attach_threejs_snapshot(export_payload, request):
    payload = dict(export_payload or {})
    snapshot_rel_path = _save_threejs_snapshot_from_request(request)
    if snapshot_rel_path:
        payload["threejs_snapshot_rel_path"] = snapshot_rel_path
        payload["threejs_view_label"] = request.POST.get("threejs_view_label") or "Current interactive 3D view"
    return payload


def _missing_threejs_snapshot_response():
    return HttpResponse(
        "The Three.js snapshot was not received by the server. Please hard-refresh the page with Ctrl+F5, wait until the interactive 3D viewer is visible, and try the PDF export again.",
        status=400,
        content_type="text/plain",
    )

def container_selection_mode1(request):
    packaging_catalogues = get_packaging_catalogues(request.user)
    product_catalogues = get_product_catalogues(request.user)

    config = _read_raw_container_config(request)

    selected_product = get_selected_product(config)
    selected_material = get_selected_material(config)

    products = get_products_for_catalogue(config)
    materials = get_materials_for_catalogue(config)

    form = build_container_form(
        request=request,
        config=config,
        selected_product=selected_product,
        selected_material=selected_material,
    )
    apply_catalogue_choices(form, packaging_catalogues, product_catalogues)

    result = None
    image_url = None
    top5 = []
    analysis_report = None
    threejs_scene = None
    product_base_image_url = None

    if request.method == "POST" and form.is_valid():
        analysis = analyze_container_form(
            form=form,
            config=config,
            selected_product=selected_product,
            selected_material=selected_material,
            materials=materials,
        )

        result = analysis["result"]
        image_url = analysis["image_url"]
        top5 = analysis["top5"]
        analysis_report = analysis.get("analysis_report")
        threejs_scene = analysis.get("threejs_scene")
        product_base_image_url = analysis.get("product_base_image_url")

        current_form_mode = form.cleaned_data.get("mode") or "single"

        if (
            analysis.get("ok")
            and current_form_mode == "single"
            and analysis_report
            and result
        ):
            export_payload = _build_single_export_payload(
                form=form,
                analysis=analysis,
                selected_product=selected_product,
                selected_material=selected_material,
            )
            if export_payload:
                request.session["container_selection_last_export"] = export_payload
                request.session["container_selection_single_export"] = export_payload
                request.session.modified = True

        if analysis.get("ok") and current_form_mode == "optimal" and top5:
            optimal_export_payload = _build_optimal_export_payload(
                form=form,
                top5=top5,
                selected_product=selected_product,
                analysis=analysis,
                selected_material=selected_material,
            )
            if optimal_export_payload:
                request.session["container_selection_optimal_export"] = optimal_export_payload
                request.session.modified = True

        for message in analysis["messages"]:
            form.add_error(None, message)

    product_summary = selected_product_summary(
        selected_product=selected_product,
        data=form if request.method == "POST" else config,
        mode=config.get("mode") or "single",
    )
    container_summary = selected_container_summary(
        selected_material=selected_material,
        data=form if request.method == "POST" else config,
    )

    context = {
        "form": form,
        "container_form": form,
        "container_config": config,

        "result": result,
        "image_url": image_url,
        "threejs_scene": threejs_scene,
        "analysis_report": analysis_report,
        "product_base_image_url": product_base_image_url,
        "top5": top5,

        "products": products,
        "materials": materials,
        "selected_product": selected_product,
        "selected_material": selected_material,

        "selected_product_summary": product_summary,
        "selected_container_summary": container_summary,

        "current_mode": config.get("mode") or "single",
        "current_product_source": config.get("product_source") or "manual",
        "current_container_source": config.get("container_source") or "manual",

        "mode": "standalone",
        "prefix": "",
        "container_ui": _build_shared_container_ui_contract(prefix=""),
        "container_values": config,
    }

    return render(
        request,
        "container_selection/container_selection_mode1.html",
        context,
    )

def container_selection_export_pdf(request):
    export_payload = (
        request.session.get("container_selection_single_export")
        or request.session.get("container_selection_last_export")
    )

    if not export_payload:
        return HttpResponse(
            "Please run a Single container analysis before exporting a PDF report.",
            status=400,
            content_type="text/plain",
        )

    export_payload = _attach_threejs_snapshot(export_payload, request)
    if not export_payload.get("threejs_snapshot_rel_path"):
        return _missing_threejs_snapshot_response()
    export_payload["report_type"] = "single"
    pdf_buffer = build_container_selection_pdf(export_payload)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"container_selection_single_report_{timestamp}.pdf"

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def container_selection_export_optimal_pdf(request):
    export_payload = request.session.get("container_selection_optimal_export")

    if not export_payload:
        return HttpResponse(
            "Please run an Optimal container search before exporting a PDF report.",
            status=400,
            content_type="text/plain",
        )

    export_payload = _attach_threejs_snapshot(export_payload, request)
    if not export_payload.get("threejs_snapshot_rel_path"):
        return _missing_threejs_snapshot_response()
    export_payload["report_type"] = "optimal"
    pdf_buffer = build_container_selection_pdf(export_payload)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"container_selection_optimal_report_{timestamp}.pdf"

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
