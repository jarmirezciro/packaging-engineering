import json

from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse
from django.urls import reverse
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


SEO_CONTAINER_SELECTION_EXAMPLE_CONFIG = {
    "mode": "single",
    "action": "run_single",
    "product_source": "manual",
    "product_l": 180,
    "product_w": 120,
    "product_h": 80,
    "product_weight": 450,
    "desired_qty": 24,
    "r1": True,
    "r2": True,
    "r3": True,
    "container_source": "manual",
    "box_l": 600,
    "box_w": 400,
    "box_h": 320,
    "box_weight": 950,
    "box_max_payload": 20000,
}


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _read_raw_container_config(request, *, initial_config=None):
    cfg = default_container_config()
    if initial_config:
        cfg.update(initial_config)

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

def _build_container_selection_page_context(
    request,
    *,
    mode,
    initial_config=None,
    run_initial_analysis=False,
):
    """Build the shared Container Selection view model for standalone and SEO pages."""
    # SEO catalogue access is public-only, including for signed-in visitors.
    catalogue_user = None if mode == "seo" else request.user
    packaging_catalogues = get_packaging_catalogues(catalogue_user)
    product_catalogues = get_product_catalogues(catalogue_user)

    config = _read_raw_container_config(request, initial_config=initial_config)

    selected_product = get_selected_product(config, user=catalogue_user)
    selected_material = get_selected_material(config, user=catalogue_user)

    products = get_products_for_catalogue(config, user=catalogue_user)
    materials = get_materials_for_catalogue(config, user=catalogue_user)

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

    analysis_form = form
    form_is_valid = form.is_valid() if request.method == "POST" else True
    if run_initial_analysis and request.method != "POST":
        analysis_form = form.__class__(config)
        apply_catalogue_choices(analysis_form, packaging_catalogues, product_catalogues)
        form_is_valid = analysis_form.is_valid()

    if (request.method == "POST" or run_initial_analysis) and form_is_valid:
        analysis = analyze_container_form(
            form=analysis_form,
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

        current_form_mode = analysis_form.cleaned_data.get("mode") or "single"

        if (
            analysis.get("ok")
            and current_form_mode == "single"
            and analysis_report
            and result
        ):
            export_payload = _build_single_export_payload(
                form=analysis_form,
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
                form=analysis_form,
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

        "mode": mode,
        "prefix": "",
        "container_ui": _build_shared_container_ui_contract(prefix=""),
        "container_values": config,
    }

    return context


def _build_container_selection_seo_schema(request):
    canonical_url = request.build_absolute_uri(reverse("container_selection_calculator"))
    company_url = request.build_absolute_uri(reverse("company_home"))
    app_url = request.build_absolute_uri(reverse("container_selection_mode1"))

    faq_items = [
        (
            "How many products fit in a box?",
            "Enter the product and usable internal box dimensions, then select every permitted vertical orientation. The calculator evaluates the shared KolliPack packing engine and reports maximum capacity.",
        ),
        (
            "Which box dimensions should I use?",
            "Use usable internal length, width, and height in millimetres. External dimensions are relevant later for palletization and transport but do not describe the product space inside the box.",
        ),
        (
            "What do R1, R2, and R3 mean?",
            "R1 permits the original product length to be vertical, R2 permits width to be vertical, and R3 permits height to be vertical. Disable any orientation that handling or product rules prohibit.",
        ),
        (
            "What is volumetric efficiency?",
            "It compares the volume occupied by the packed products with the usable internal container volume. Weight and payload are evaluated separately because a geometric fit can still exceed a safe load limit.",
        ),
        (
            "Does the result replace a packaging trial?",
            "No. Confirm clearances, material strength, cushioning, compression, handling, closure, and product protection with the real product and packaging.",
        ),
    ]

    schema = [
        {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "KolliPack Box Size and Container Selection Calculator",
            "applicationCategory": "BusinessApplication",
            "applicationSubCategory": "Packaging engineering calculator",
            "operatingSystem": "Any web browser",
            "url": canonical_url,
            "description": (
                "Calculate how many products fit in a box, compare current and maximum volumetric "
                "efficiency, and check packed weight, payload usage, and remaining capacity."
            ),
            "provider": {"@type": "Organization", "name": "KolliLabs", "url": company_url},
            "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock",
            },
            "isAccessibleForFree": True,
            "browserRequirements": "Requires JavaScript and a modern web browser",
            "featureList": [
                "Maximum product quantity per box",
                "R1, R2 and R3 orientation restrictions",
                "Current and maximum volumetric efficiency",
                "Product, packaging and payload weight checks",
                "Interactive 3D RSC box visualization",
                "Top 5 public catalogue alternatives",
                "PDF engineering report with 3D snapshot",
            ],
            "potentialAction": {"@type": "UseAction", "target": canonical_url},
            "sameAs": [app_url],
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {"@type": "Answer", "text": answer},
                }
                for question, answer in faq_items
            ],
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "KolliLabs", "item": company_url},
                {"@type": "ListItem", "position": 2, "name": "Box Size Calculator", "item": canonical_url},
            ],
        },
    ]
    return canonical_url, faq_items, json.dumps(schema, ensure_ascii=False)


def container_selection_mode1(request):
    return render(
        request,
        "container_selection/container_selection_mode1.html",
        _build_container_selection_page_context(request, mode="standalone"),
    )


def container_selection_calculator(request):
    is_initial_example = request.method == "GET" and not request.GET
    context = _build_container_selection_page_context(
        request,
        mode="seo",
        initial_config=SEO_CONTAINER_SELECTION_EXAMPLE_CONFIG if is_initial_example else None,
        run_initial_analysis=is_initial_example,
    )
    canonical_url, faq_items, schema_json = _build_container_selection_seo_schema(request)
    context.update(
        {
            "canonical_url": canonical_url,
            "faq_items": faq_items,
            "seo_schema_json": schema_json,
            "is_initial_example": is_initial_example,
            "example_product_dimensions": "180 × 120 × 80 mm",
            "example_container_dimensions": "600 × 400 × 320 mm",
        }
    )
    return render(request, "marketing/container_selection_calculator.html", context)

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
