import json

from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from ..tools.bag.presenter import selected_bag_summary, selected_product_summary
from ..tools.bag.serializers import sanitize_bag_config_for_session
from ..tools.bag.service import (
    analyze_bag_config,
    apply_catalogue_choices,
    build_bag_form,
    get_materials_for_catalogue,
    get_packaging_catalogues,
    get_product_catalogues,
    get_products_for_catalogue,
    get_selected_material,
    get_selected_product,
)
from ..tools.bag.state import default_bag_config
from ..tools.selection_mode import normalize_selection_mode
from ..tools.bag.export import build_bag_selection_pdf
from ..utils.bag_selection.engine import SEALING_AREA, TOLERANCE
from ..tools.threejs_snapshot import save_threejs_snapshot_from_request


SEO_BAG_SELECTION_EXAMPLE_CONFIG = {
    "mode": "single",
    "action": "run_single",
    "product_source": "manual",
    "product_l": 180,
    "product_w": 120,
    "product_h": 40,
    "product_weight": 250,
    "desired_qty": 4,
    "bag_source": "manual",
    "bag_length": 450,
    "bag_width": 330,
    "bag_weight": 18,
    "bag_max_payload": 5000,
}


def _read_raw_bag_config(request, *, initial_config=None):
    cfg = default_bag_config()
    if initial_config:
        cfg.update(initial_config)

    if request.method == "POST":
        source = request.POST
    else:
        source = request.GET

    has_explicit_rotation_submission = (
        request.method == "POST"
        and bool(source.get("rotation_permissions_present"))
        and source.get("action") in ("run_design", "select_design_candidate")
    )

    cfg.update({
        "mode": normalize_selection_mode({
            "mode": source.get("mode", normalize_selection_mode(cfg)),
            "tool_mode": source.get("tool_mode", ""),
        }),
        "action": source.get("action", cfg["action"]),
        "product_source": source.get("product_source", cfg["product_source"]),
        "product_catalogue_id": source.get("product_catalogue_id", cfg["product_catalogue_id"]),
        "selected_product_id": source.get("selected_product_id", cfg["selected_product_id"]),
        "product_l": source.get("product_l", cfg["product_l"]),
        "product_w": source.get("product_w", cfg["product_w"]),
        "product_h": source.get("product_h", cfg["product_h"]),
        "product_weight": source.get("product_weight", cfg["product_weight"]),
        "desired_qty": source.get("desired_qty", cfg["desired_qty"]),
        "r1": source.get("r1") is not None if has_explicit_rotation_submission else cfg["r1"],
        "r2": source.get("r2") is not None if has_explicit_rotation_submission else cfg["r2"],
        "r3": source.get("r3") is not None if has_explicit_rotation_submission else cfg["r3"],
        "bag_source": source.get("bag_source", cfg["bag_source"]),
        "catalogue_id": source.get("catalogue_id", cfg["catalogue_id"]),
        "bag_id": source.get("bag_id", cfg["bag_id"]),
        "bag_length": source.get("bag_length", cfg["bag_length"]),
        "bag_width": source.get("bag_width", cfg["bag_width"]),
        "bag_weight": source.get("bag_weight", cfg["bag_weight"]),
        "bag_max_payload": source.get("bag_max_payload", cfg["bag_max_payload"]),
        "selected_design_candidate_id": source.get("selected_design_candidate_id", cfg["selected_design_candidate_id"]),
    })

    return sanitize_bag_config_for_session(cfg)


def _build_shared_bag_ui_contract(prefix="", action_field_name=None, action_field_id=None, render_action_hidden=True):
    suffix = f"_{prefix}" if prefix else ""
    action_name = action_field_name or f"action{suffix}"
    action_id = action_field_id or action_name

    return {
        "prefix": prefix,
        "render_action_hidden": render_action_hidden,
        "assumptions": {
            "tolerance_mm": TOLERANCE,
            "sealing_allowance_mm": SEALING_AREA,
        },
        "names": {
            "action": action_name,
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
            "rotation_permissions_present": f"rotation_permissions_present{suffix}",
            "bag_source": f"bag_source{suffix}",
            "catalogue_id": f"catalogue_id{suffix}",
            "bag_id": f"bag_id{suffix}",
            "bag_length": f"bag_length{suffix}",
            "bag_width": f"bag_width{suffix}",
            "bag_weight": f"bag_weight{suffix}",
            "bag_max_payload": f"bag_max_payload{suffix}",
            "selected_design_candidate_id": f"selected_design_candidate_id{suffix}",
        },
        "ids": {
            "root": f"bagSelectionRoot{suffix}",
            "action": action_id,
            "selected_product_id": f"selected_product_id{suffix}",
            "bag_id": f"bag_id{suffix}",
            "selected_design_candidate_id": f"selected_design_candidate_id{suffix}",
            "product_catalogue_chooser": f"productCatalogueChooser{suffix}" if prefix else "productCatalogueChooser",
            "manual_product_fields": f"manualProductFields{suffix}" if prefix else "manualProductFields",
            "manual_desired_qty_wrap": f"manualDesiredQtyWrap{suffix}" if prefix else "manualDesiredQtyWrap",
            "rotation_fields": f"bagRotationFields{suffix}" if prefix else "bagRotationFields",
            "global_catalogue_chooser": f"globalCatalogueChooser{suffix}" if prefix else "globalCatalogueChooser",
            "single_bag_controls": f"singleBagControls{suffix}" if prefix else "singleBagControls",
            "optimal_bag_controls": f"optimalBagControls{suffix}" if prefix else "optimalBagControls",
            "manual_bag_fields": f"manualBagFields{suffix}" if prefix else "manualBagFields",
            "design_packaging_fields": f"designPackagingFields{suffix}" if prefix else "designPackagingFields",
            "selection_package_controls": f"selectionPackageControls{suffix}" if prefix else "selectionPackageControls",
            "threejs_viewer": f"bagThreeJsViewer{suffix}",
            "threejs_scene": f"bagThreeJsScene{suffix}",
        },
    }

def _format_dims(length, width, height):
    return f"{length} × {width} × {height} mm"


def _format_bag_dims(length, width):
    return f"{length} × {width} mm"


def _format_optional_weight(value, default="Not available"):
    if value in (None, "", "None"):
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if abs(numeric) >= 1000:
        return f"{numeric / 1000:.2f} kg"
    return f"{numeric:.0f} g"


def _format_usage(value):
    if value in (None, "", "None"):
        return "Not available"
    try:
        return f"{float(value):.0f}%"
    except (TypeError, ValueError):
        return "Not available"


def _catalogue_name_from_choice(form, field_name):
    value = str(form.cleaned_data.get(field_name) or "")
    for option_value, label in form.fields[field_name].choices:
        if str(option_value) == value:
            return str(label)
    return "Selected catalogue"


def _product_payload(*, form, selected_product):
    product_source = form.cleaned_data.get("product_source") or "manual"

    if product_source == "catalogue" and selected_product is not None:
        product_id = selected_product.product_id
        product_name = selected_product.product_name
        product_l = selected_product.product_length
        product_w = selected_product.product_width
        product_h = selected_product.product_height
        product_weight = getattr(selected_product, "weight", None)
    else:
        product_id = "Manual product"
        product_name = "Manual input"
        product_l = form.cleaned_data.get("product_l")
        product_w = form.cleaned_data.get("product_w")
        product_h = form.cleaned_data.get("product_h")
        product_weight = form.cleaned_data.get("product_weight")

    desired_qty = form.cleaned_data.get("desired_qty") or 1

    return {
        "source": "Catalogue" if product_source == "catalogue" else "Manual",
        "id": product_id,
        "name": product_name or "—",
        "dimensions": _format_dims(product_l, product_w, product_h),
        "weight": _format_optional_weight(product_weight),
        "desired_qty": f"{desired_qty} pcs",
        "orientation": "Fixed product orientation; bag opening is on the width side.",
    }


def _bag_payload(*, form, selected_material, analysis_report):
    bag_source = form.cleaned_data.get("bag_source") or "manual"

    if bag_source == "catalogue" and selected_material is not None:
        part_number = selected_material.part_number
        description = selected_material.part_description
        brand = selected_material.branding
        material = selected_material.packaging_materials
        bag_length = selected_material.part_length
        bag_width = selected_material.part_width
        bag_weight = getattr(selected_material, "part_weight", None)
    else:
        part_number = "Manual bag"
        description = "Manual input"
        brand = "Manual"
        material = "Manual input"
        bag_length = form.cleaned_data.get("bag_length")
        bag_width = form.cleaned_data.get("bag_width")
        bag_weight = form.cleaned_data.get("bag_weight")

    payload_display = (analysis_report or {}).get("payload_capacity_display") or _format_optional_weight(form.cleaned_data.get("bag_max_payload"))

    return {
        "source": "Catalogue" if bag_source == "catalogue" else "Manual",
        "part_number": part_number or "—",
        "description": description or "—",
        "brand": brand or "—",
        "material": material or "—",
        "dimensions": _format_bag_dims(bag_length, bag_width),
        "weight": _format_optional_weight(bag_weight),
        "payload_capacity": payload_display,
    }


def _build_single_export_payload(*, form, analysis, selected_product, selected_material):
    analysis_report = analysis.get("analysis_report") or {}
    result = analysis.get("result") or {}

    if not analysis_report or not result:
        return None

    return {
        "report_type": "single",
        "generated_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
        "product": _product_payload(form=form, selected_product=selected_product),
        "bag": _bag_payload(form=form, selected_material=selected_material, analysis_report=analysis_report),
        "analysis_report": analysis_report,
        "image_rel_path": result.get("image_rel_path", ""),
    }


def _top5_export_rows(top5):
    rows = []
    for idx, row in enumerate(top5 or [], start=1):
        best_required = row.get("best_required") or (None, None)
        if len(best_required) < 2:
            best_required_display = "-"
        else:
            best_required_display = f"{best_required[0]} × {best_required[1]} mm"

        rows.append({
            "rank": idx,
            "part_number": row.get("part_number"),
            "description": row.get("description"),
            "brand": row.get("branding"),
            "bag_length": f"{row.get('bag_len', '-')} mm",
            "bag_width": f"{row.get('bag_w', '-')} mm",
            "usage_display": f"{row.get('usage_pct')}%" if row.get("usage_pct") not in (None, "") else _format_usage(row.get("usage")),
            "best_required": best_required_display,
        })

    return rows


def _selected_candidate_payload(selected_material):
    if selected_material is None:
        return None
    return {
        "part_number": selected_material.part_number,
        "description": selected_material.part_description,
        "brand": selected_material.branding,
        "dimensions": _format_bag_dims(selected_material.part_length, selected_material.part_width),
    }


def _build_optimal_export_payload(*, form, analysis, top5, selected_product, selected_material):
    analysis_report = analysis.get("analysis_report") or {}
    result = analysis.get("result") or {}

    if not analysis_report or not result:
        return None

    return {
        "report_type": "optimal",
        "generated_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
        "catalogue_name": _catalogue_name_from_choice(form, "catalogue_id"),
        "product": _product_payload(form=form, selected_product=selected_product),
        "selected_candidate": _selected_candidate_payload(selected_material),
        "analysis_report": analysis_report,
        "image_rel_path": result.get("image_rel_path", ""),
        "top5": _top5_export_rows(top5),
    }


def _build_design_export_payload(*, form, analysis, selected_product):
    selected = analysis.get("result") or {}
    report = analysis.get("analysis_report") or {}
    if not selected or not report:
        return None
    analysis_payload = dict(report)
    analysis_payload.update({
        "current_quantity": selected["desired_quantity"],
        "max_quantity": selected["design_quantity"],
        "remaining_capacity": selected["additional_capacity"],
        "bag_usage_current_display": f"{selected['bag_usage'] * 100:.0f}%",
        "bag_usage_max_display": f"{selected['bag_usage'] * 100:.0f}%",
        "calculation_note": "Design Mode dimensions use the shared smooth-quantity and bag formula contracts.",
        "design_mode": True,
    })
    return {
        "report_type": "design",
        "generated_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
        "product": _product_payload(form=form, selected_product=selected_product),
        "bag": {
            "source": "Designed",
            "part_number": selected["candidate_id"],
            "description": f"Arrangement {selected['arrangement']} · {selected['product_orientation']}",
            "brand": "KolliPack Design Mode",
            "material": "To be specified",
            "dimensions": _format_bag_dims(selected["bag_length"], selected["bag_width"]),
        },
        "analysis_report": analysis_payload,
        "selected_candidate": selected,
    }



def _build_bag_selection_page_context(
    request,
    *,
    mode,
    initial_config=None,
    run_initial_analysis=False,
):
    """Build the shared Bag Selection view model for standalone and SEO pages."""
    packaging_catalogues = get_packaging_catalogues(request.user)
    product_catalogues = get_product_catalogues(request.user)

    config = _read_raw_bag_config(request, initial_config=initial_config)

    selected_product = get_selected_product(config)
    selected_material = get_selected_material(config)

    products = get_products_for_catalogue(config)
    materials = get_materials_for_catalogue(config)

    form = build_bag_form(
        request=request,
        config=config,
        selected_product=selected_product,
        selected_material=selected_material,
    )
    apply_catalogue_choices(form, packaging_catalogues, product_catalogues)

    result = None
    image_url = None
    top5 = []
    pending_result = None
    analysis_report = None
    threejs_scene = None
    design_candidates = []
    selected_design_candidate_id = config.get("selected_design_candidate_id") or ""
    notices = []

    form_is_valid = form.is_valid() if request.method == "POST" else True
    should_analyze = run_initial_analysis or request.method == "POST"

    if should_analyze and form_is_valid:
        analysis = analyze_bag_config(
            config=config,
            action=config.get("action") or ("run_single" if run_initial_analysis else ""),
            selected_product=selected_product,
            selected_material=selected_material,
            materials=materials,
            media_root=settings.MEDIA_ROOT,
        )
        result = analysis["result"]
        image_url = analysis["image_url"]
        top5 = analysis["top5"]
        pending_result = analysis["pending_result"]
        analysis_report = analysis.get("analysis_report")
        threejs_scene = analysis.get("threejs_scene")
        design_candidates = analysis.get("design_candidates") or []
        selected_design_candidate_id = analysis.get("selected_design_candidate_id") or selected_design_candidate_id
        notices = analysis.get("notices") or []

        current_form_mode = (
            form.cleaned_data.get("mode")
            if request.method == "POST"
            else config.get("mode")
        ) or "single"
        current_action = config.get("action") or ""

        if result and analysis_report and current_form_mode == "single":
            export_form = form
            if request.method != "POST":
                export_form = form.__class__(config)
                apply_catalogue_choices(export_form, packaging_catalogues, product_catalogues)
                if not export_form.is_valid():
                    export_form = None

            export_payload = _build_single_export_payload(
                form=export_form,
                analysis=analysis,
                selected_product=selected_product,
                selected_material=selected_material,
            ) if export_form is not None else None
            if export_payload:
                request.session["bag_selection_last_export"] = export_payload
                request.session["bag_selection_single_export"] = export_payload
                request.session.modified = True

        if result and analysis_report and current_form_mode == "optimal" and current_action == "select_candidate":
            optimal_export_payload = _build_optimal_export_payload(
                form=form,
                analysis=analysis,
                top5=top5,
                selected_product=selected_product,
                selected_material=selected_material,
            )
            if optimal_export_payload:
                request.session["bag_selection_optimal_export"] = optimal_export_payload
                request.session.modified = True

        for message in analysis["messages"]:
            form.add_error(None, message)

        if result and analysis_report and current_form_mode == "design":
            design_export = _build_design_export_payload(form=form, analysis=analysis, selected_product=selected_product)
            if design_export:
                request.session["bag_selection_design_export"] = design_export
                request.session.modified = True

    product_summary = selected_product_summary(
        selected_product=selected_product,
        data=form if request.method == "POST" else config,
        mode=config.get("mode") or "single",
    )
    bag_summary = selected_bag_summary(
        selected_material=selected_material,
        data=form if request.method == "POST" else config,
    )

    return {
        "form": form,
        "bag_form": form,
        "bag_config": config,
        "bag_values": config,
        "result": result,
        "image_url": image_url,
        "top5": top5,
        "pending_result": pending_result,
        "analysis_report": analysis_report,
        "threejs_scene": threejs_scene,
        "design_candidates": design_candidates,
        "selected_design_candidate_id": selected_design_candidate_id,
        "notices": notices,
        "materials": materials,
        "products": products,
        "selected_material": selected_material,
        "selected_product": selected_product,
        "selected_product_summary": product_summary,
        "selected_bag_summary": bag_summary,
        "current_mode": config.get("mode") or "single",
        "current_product_source": config.get("product_source") or "manual",
        "current_bag_source": config.get("bag_source") or "manual",
        "mode": mode,
        "prefix": "",
        "bag_ui": _build_shared_bag_ui_contract(prefix=""),
        "bag_assumptions": {
            "tolerance_mm": TOLERANCE,
            "sealing_allowance_mm": SEALING_AREA,
        },
        "allow_product_catalogue": True,
    }


def _build_bag_selection_seo_schema(request):
    canonical_url = request.build_absolute_uri(reverse("bag_selection_calculator"))
    company_url = request.build_absolute_uri(reverse("company_home"))
    app_url = request.build_absolute_uri(reverse("bag_selection_mode1"))

    faq_items = [
        (
            "How does the bag size calculator determine the required bag size?",
            "It evaluates supported product arrangements with the shared KolliPack Bag Selection engine, then applies the current fit tolerance and reserves sealing space along bag length.",
        ),
        (
            "Which bag dimensions should I enter?",
            "Enter the flat bag length and width in millimetres. Bag length includes the reserved sealing allowance; bag width is the opening span and receives the fit tolerance defined by the engine.",
        ),
        (
            "What does bag usage mean?",
            "Bag usage compares the calculated required flat bag area with the selected bag area for the current or maximum feasible quantity.",
        ),
        (
            "Does the calculator check payload?",
            "Yes. When product weight and maximum payload are supplied, the result shows net product weight, total weight, payload usage, and remaining quantity capacity.",
        ),
        (
            "Does this result replace a packaging trial?",
            "No. Flexible materials, seals, product shape, handling, protection, and manufacturing tolerances should still be validated with the actual bag and product.",
        ),
    ]

    schema = [
        {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "KolliPack Bag Size Calculator",
            "applicationCategory": "BusinessApplication",
            "applicationSubCategory": "Packaging engineering calculator",
            "operatingSystem": "Any web browser",
            "url": canonical_url,
            "description": (
                "Calculate product-to-bag fit, maximum quantity, bag usage, weight, "
                "payload usage, and remaining capacity with a flexible packaging calculator."
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
                "Maximum product quantity per bag",
                "Current and maximum bag usage",
                "Net product and total packed weight",
                "Payload usage and remaining capacity",
                "Bag orientation visualization",
                "PDF engineering report",
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
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "KolliLabs",
                    "item": company_url,
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": "Bag Size Calculator",
                    "item": canonical_url,
                },
            ],
        },
    ]
    return canonical_url, faq_items, json.dumps(schema, ensure_ascii=False)


def bag_selection_mode1(request):
    return render(
        request,
        "bag_selection/bag_selection_mode1.html",
        _build_bag_selection_page_context(request, mode="standalone"),
    )


def bag_selection_calculator(request):
    is_initial_example = request.method == "GET" and not request.GET
    context = _build_bag_selection_page_context(
        request,
        mode="seo",
        initial_config=SEO_BAG_SELECTION_EXAMPLE_CONFIG if is_initial_example else None,
        run_initial_analysis=is_initial_example,
    )
    canonical_url, faq_items, schema_json = _build_bag_selection_seo_schema(request)
    context.update(
        {
            "canonical_url": canonical_url,
            "faq_items": faq_items,
            "seo_schema_json": schema_json,
            "is_initial_example": is_initial_example,
            "example_product_dimensions": "180 x 120 x 40 mm",
            "example_bag_dimensions": "450 x 330 mm",
        }
    )
    return render(request, "marketing/bag_selection_calculator.html", context)


def bag_selection_export_pdf(request):
    if request.POST.get("design_export"):
        export_payload = request.session.get("bag_selection_design_export")
        if export_payload:
            snapshot = save_threejs_snapshot_from_request(request, relative_directory="bag_exports/threejs")
            if not snapshot:
                return HttpResponse("The Three.js snapshot was not received. Wait for the viewer to load and try again.", status=400, content_type="text/plain")
            export_payload = dict(export_payload)
            export_payload["threejs_snapshot_rel_path"] = snapshot
    else:
        export_payload = request.session.get("bag_selection_single_export") or request.session.get("bag_selection_last_export")
        if export_payload and request.method == "POST":
            snapshot = save_threejs_snapshot_from_request(request, relative_directory="bag_exports/threejs")
            if not snapshot:
                return HttpResponse("The Three.js snapshot was not received. Wait for the viewer to load and try again.", status=400, content_type="text/plain")
            export_payload = dict(export_payload)
            export_payload["threejs_snapshot_rel_path"] = snapshot

    if not export_payload:
        return HttpResponse(
            "Please run a Single bag analysis before exporting a PDF report.",
            status=400,
            content_type="text/plain",
        )

    export_payload["report_type"] = "single"
    pdf_buffer = build_bag_selection_pdf(export_payload)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"bag_selection_single_report_{timestamp}.pdf"

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def bag_selection_export_optimal_pdf(request):
    export_payload = request.session.get("bag_selection_optimal_export")

    if not export_payload:
        return HttpResponse(
            "Please select a Top 5 bag candidate before exporting an Optimal PDF report.",
            status=400,
            content_type="text/plain",
        )

    if request.method == "POST":
        snapshot = save_threejs_snapshot_from_request(request, relative_directory="bag_exports/threejs")
        if not snapshot:
            return HttpResponse("The Three.js snapshot was not received. Wait for the viewer to load and try again.", status=400, content_type="text/plain")
        export_payload = dict(export_payload)
        export_payload["threejs_snapshot_rel_path"] = snapshot

    export_payload["report_type"] = "optimal"
    pdf_buffer = build_bag_selection_pdf(export_payload)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"bag_selection_optimal_report_{timestamp}.pdf"

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
