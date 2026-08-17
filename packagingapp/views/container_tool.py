import json

from packagingapp.access import visible_packaging_catalogues, visible_product_catalogues
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from ..forms import ContainerToolForm
from ..models import PackagingMaterial, Product
from ..tools.transport.export import build_transport_container_pdf
from ..tools.transport.presenter import selected_container_summary
from ..tools.transport.serializers import sanitize_transport_rows_for_session
from ..tools.transport.service import analyze_transport_config, read_product_rows_raw
from ..tools.transport.state import default_product_rows
from ..tools.transport.case_presets import get_transport_container_case_preset
from ..tools.transport.modes import (
    DEFAULT_TRANSPORT_PACKING_MODE,
    TRANSPORT_PACKING_MODE_OPTIONS,
    normalize_transport_packing_mode,
    transport_sequence_is_locked,
)
from ..tools.threejs_snapshot import save_threejs_snapshot_from_request


SEO_TRANSPORT_EXAMPLE_CONFIG = {
    "container_source": "manual",
    "container_l": 12032,
    "container_w": 2352,
    "container_h": 2395,
    "max_weight": 26500,
    "tare_weight": 3750,
    "packing_mode": DEFAULT_TRANSPORT_PACKING_MODE,
}

SEO_TRANSPORT_EXAMPLE_ROWS = [
    {
        "name": "EUR palletized load",
        "length": 1200,
        "width": 800,
        "height": 1100,
        "qty": 20,
        "max_qty": False,
        "weight": 900,
        "sequence": 1,
        "r1": True,
        "r2": False,
        "r3": False,
    }
]


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
        "product_legend": list(
            (analysis.get("threejs_scene") or {}).get("products") or []
        ),
        "packing_mode": normalize_transport_packing_mode(
            result.get("packing_mode"),
            default=DEFAULT_TRANSPORT_PACKING_MODE,
        ),
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


def _build_transport_page_context(
    request,
    *,
    mode,
    initial_config=None,
    initial_rows=None,
    run_initial_analysis=False,
):
    """Build the shared standalone-style Transport page context.

    The KolliPack screen and public SEO calculator both use this orchestration.
    Packaging Flow consumes the same service and shared partials through its
    prefixed workflow adapter.
    """
    initial_config = dict(initial_config or {})
    initial_config["packing_mode"] = normalize_transport_packing_mode(
        initial_config.get("packing_mode"),
        default=DEFAULT_TRANSPORT_PACKING_MODE,
    )
    packaging_catalogues = visible_packaging_catalogues(request.user).order_by("name")
    product_catalogues = visible_product_catalogues(request.user).order_by("name")

    raw_action = request.POST.get("action") if request.method == "POST" else request.GET.get(
        "action", "run_analysis" if run_initial_analysis else "refresh"
    )
    raw_catalogue_id = request.POST.get("catalogue_id") if request.method == "POST" else request.GET.get(
        "catalogue_id", initial_config.get("catalogue_id", "")
    )
    raw_container_id = request.POST.get("container_id") if request.method == "POST" else request.GET.get(
        "container_id", initial_config.get("container_id", "")
    )
    raw_product_catalogue_id = request.POST.get("product_catalogue_id") if request.method == "POST" else request.GET.get(
        "product_catalogue_id", initial_config.get("product_catalogue_id", "")
    )
    raw_product_id_to_fill = request.POST.get("product_id_to_fill") if request.method == "POST" else request.GET.get(
        "product_id_to_fill", initial_config.get("product_id_to_fill", "")
    )
    raw_selected_row_index = request.POST.get("selected_row_index") if request.method == "POST" else request.GET.get(
        "selected_row_index", initial_config.get("selected_row_index", "")
    )

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
        product_rows = sanitize_transport_rows_for_session(
            initial_rows if initial_rows is not None else default_product_rows()
        )

    current_container_source = (
        request.POST.get("container_source")
        if request.method == "POST"
        else request.GET.get(
            "container_source",
            initial_config.get("container_source", "manual"),
        )
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
            row.setdefault("stackable", True)
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
            "container_source": current_container_source,
            "packing_mode": initial_config.get(
                "packing_mode", DEFAULT_TRANSPORT_PACKING_MODE
            ),
            "catalogue_id": raw_catalogue_id,
            "container_id": raw_container_id,
            "container_l": initial_config.get("container_l", ""),
            "container_w": initial_config.get("container_w", ""),
            "container_h": initial_config.get("container_h", ""),
            "max_weight": initial_config.get("max_weight", ""),
            "tare_weight": initial_config.get("tare_weight", ""),
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
            "packing_mode": form.cleaned_data.get(
                "packing_mode"
            ) or DEFAULT_TRANSPORT_PACKING_MODE,
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
                "packing_mode": form.cleaned_data.get(
                    "packing_mode"
                ) or DEFAULT_TRANSPORT_PACKING_MODE,
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
                    "packing_mode": normalize_transport_packing_mode(
                        request.POST.get(
                            "packing_mode", DEFAULT_TRANSPORT_PACKING_MODE
                        )
                        if request.method == "POST"
                        else initial_config.get(
                            "packing_mode", DEFAULT_TRANSPORT_PACKING_MODE
                        )
                    ),
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

    if request.method == "GET" and run_initial_analysis:
        cfg = {
            "container_source": current_container_source,
            "packing_mode": (
                form["packing_mode"].value()
                if "packing_mode" in form.fields
                else DEFAULT_TRANSPORT_PACKING_MODE
            ),
            "container_l": form["container_l"].value() if "container_l" in form.fields else "",
            "container_w": form["container_w"].value() if "container_w" in form.fields else "",
            "container_h": form["container_h"].value() if "container_h" in form.fields else "",
            "max_weight": form["max_weight"].value() if "max_weight" in form.fields else "",
            "tare_weight": form["tare_weight"].value() if "tare_weight" in form.fields else "",
            "catalogue_id": raw_catalogue_id,
            "container_id": raw_container_id,
            "product_catalogue_id": raw_product_catalogue_id,
            "selected_row_index": raw_selected_row_index,
            "product_id_to_fill": raw_product_id_to_fill,
        }
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
        "mode": mode,
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
        "transport_packing_modes": TRANSPORT_PACKING_MODE_OPTIONS,
        "transport_sequence_locked": transport_sequence_is_locked(
            form["packing_mode"].value()
            if "packing_mode" in form.fields
            else DEFAULT_TRANSPORT_PACKING_MODE
        ),
    }

    return context


def _build_transport_seo_schema(request):
    canonical_url = request.build_absolute_uri(reverse("transport_container_calculator"))
    company_url = request.build_absolute_uri(reverse("company_home"))
    app_url = request.build_absolute_uri(reverse("container_tool"))
    flow_url = request.build_absolute_uri(reverse("full_packaging_mode"))

    faq_items = [
        (
            "What does a container loading calculator calculate?",
            "It estimates how many rectangular load units the selected transport unit can place, then reports unplaced quantity, volume use, loaded weight, payload use, occupied dimensions, and remaining dimensions.",
        ),
        (
            "Which dimensions should I enter?",
            "Use usable internal dimensions for the transport unit and external length, width, and height for each packaged product, carton, pallet, crate, or other load unit.",
        ),
        (
            "What does Max qty do?",
            "Max qty asks the shared Transport engine to find the largest quantity the current packing heuristic can load while respecting the other entered rows, rotations, available space, and payload.",
        ),
        (
            "Does the calculator check container payload?",
            "Yes. Enter a maximum payload and load-unit weight to compare cargo weight with that payload. Tare is reported separately and is added only to the gross loaded weight summary.",
        ),
        (
            "Does the result replace a physical and legal transport check?",
            "No. Confirm door-aperture access, loading sequence, load securing, stacking strength, axle and centre-of-gravity limits, airflow, dangerous-goods rules, and route-specific legal requirements separately.",
        ),
    ]

    schema = [
        {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "KolliPack Container Loading Calculator",
            "applicationCategory": "BusinessApplication",
            "applicationSubCategory": "Packaging transport optimization calculator",
            "operatingSystem": "Any web browser",
            "url": canonical_url,
            "description": (
                "Calculate shipping-container and truck capacity, loaded quantity, volume use, "
                "weight, payload use, occupied dimensions, and remaining space."
            ),
            "provider": {
                "@type": "Organization",
                "name": "KolliLabs",
                "url": company_url,
            },
            "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock",
            },
            "isAccessibleForFree": True,
            "browserRequirements": "Requires JavaScript and a modern web browser",
            "featureList": [
                "Shipping container and truck loading capacity",
                "Requested quantity and automatic maximum quantity",
                "Volume and payload utilization",
                "Rotation restrictions and mixed load-unit rows",
                "Interactive Three.js loading visualization",
                "Fixed-view PDF engineering report snapshots",
            ],
            "potentialAction": {"@type": "UseAction", "target": canonical_url},
            "sameAs": [app_url, flow_url],
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
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "KolliLabs",
                    "item": company_url,
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": "Container Loading Calculator",
                    "item": canonical_url,
                },
            ],
        },
    ]
    return canonical_url, faq_items, json.dumps(schema, ensure_ascii=False)


def container_tool(request):
    return render(
        request,
        "container_tool/container_tool.html",
        _build_transport_page_context(request, mode="standalone"),
    )


def transport_container_calculator(request):
    case_slug = (request.GET.get("case") or "").strip() if request.method == "GET" else ""
    case_preset = get_transport_container_case_preset(case_slug)
    is_initial_example = request.method == "GET" and not request.GET
    is_case_example = request.method == "GET" and case_preset is not None
    context = _build_transport_page_context(
        request,
        mode="seo",
        initial_config=(
            case_preset["config"]
            if is_case_example
            else SEO_TRANSPORT_EXAMPLE_CONFIG if is_initial_example else None
        ),
        initial_rows=(
            case_preset["rows"]
            if is_case_example
            else SEO_TRANSPORT_EXAMPLE_ROWS if is_initial_example else None
        ),
        run_initial_analysis=is_initial_example or is_case_example,
    )
    canonical_url, faq_items, schema_json = _build_transport_seo_schema(request)
    context.update(
        {
            "canonical_url": canonical_url,
            "faq_items": faq_items,
            "seo_schema_json": schema_json,
            "is_initial_example": is_initial_example,
            "is_case_example": is_case_example,
            "case_preset": case_preset,
            "example_transport_dimensions": "12032 x 2352 x 2395 mm",
            "example_load_dimensions": "1200 x 800 x 1100 mm",
            "example_quantity": 20,
            "example_load_weight": "900 kg",
            "example_payload": "26500 kg",
        }
    )
    return render(request, "marketing/transport_container_calculator.html", context)


def container_tool_export_pdf(request):
    export_payload = request.session.get("transport_container_last_export")

    if not export_payload:
        return HttpResponse(
            "Please run a transport container analysis before exporting a PDF report.",
            status=400,
            content_type="text/plain",
        )

    snapshot_fields = {
        "loading": "transport_threejs_snapshot_loading",
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
            "The Three.js Loading, Opposite Side and Top transport views are required for PDF export.",
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
