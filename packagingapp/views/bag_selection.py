from django.shortcuts import render
from django.http import HttpResponse
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
from ..tools.bag.export import build_bag_selection_pdf


def _read_raw_bag_config(request):
    cfg = default_bag_config()

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
        "bag_source": source.get("bag_source", cfg["bag_source"]),
        "catalogue_id": source.get("catalogue_id", cfg["catalogue_id"]),
        "bag_id": source.get("bag_id", cfg["bag_id"]),
        "bag_length": source.get("bag_length", cfg["bag_length"]),
        "bag_width": source.get("bag_width", cfg["bag_width"]),
        "bag_weight": source.get("bag_weight", cfg["bag_weight"]),
        "bag_max_payload": source.get("bag_max_payload", cfg["bag_max_payload"]),
    })

    return sanitize_bag_config_for_session(cfg)


def _build_shared_bag_ui_contract(prefix="", action_field_name=None, action_field_id=None, render_action_hidden=True):
    suffix = f"_{prefix}" if prefix else ""
    action_name = action_field_name or f"action{suffix}"
    action_id = action_field_id or action_name

    return {
        "prefix": prefix,
        "render_action_hidden": render_action_hidden,
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
            "bag_source": f"bag_source{suffix}",
            "catalogue_id": f"catalogue_id{suffix}",
            "bag_id": f"bag_id{suffix}",
            "bag_length": f"bag_length{suffix}",
            "bag_width": f"bag_width{suffix}",
            "bag_weight": f"bag_weight{suffix}",
            "bag_max_payload": f"bag_max_payload{suffix}",
        },
        "ids": {
            "root": f"bagSelectionRoot{suffix}",
            "action": action_id,
            "selected_product_id": f"selected_product_id{suffix}",
            "bag_id": f"bag_id{suffix}",
            "product_catalogue_chooser": f"productCatalogueChooser{suffix}" if prefix else "productCatalogueChooser",
            "manual_product_fields": f"manualProductFields{suffix}" if prefix else "manualProductFields",
            "manual_desired_qty_wrap": f"manualDesiredQtyWrap{suffix}" if prefix else "manualDesiredQtyWrap",
            "global_catalogue_chooser": f"globalCatalogueChooser{suffix}" if prefix else "globalCatalogueChooser",
            "single_bag_controls": f"singleBagControls{suffix}" if prefix else "singleBagControls",
            "optimal_bag_controls": f"optimalBagControls{suffix}" if prefix else "optimalBagControls",
            "manual_bag_fields": f"manualBagFields{suffix}" if prefix else "manualBagFields",
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



def bag_selection_mode1(request):
    packaging_catalogues = get_packaging_catalogues(request.user)
    product_catalogues = get_product_catalogues(request.user)

    config = _read_raw_bag_config(request)

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

    if request.method == "POST" and form.is_valid():
        analysis = analyze_bag_config(
            config=config,
            action=config.get("action") or "",
            selected_product=selected_product,
            selected_material=selected_material,
            materials=materials,
        )
        result = analysis["result"]
        image_url = analysis["image_url"]
        top5 = analysis["top5"]
        pending_result = analysis["pending_result"]
        analysis_report = analysis.get("analysis_report")

        current_form_mode = form.cleaned_data.get("mode") or "single"
        current_action = config.get("action") or ""

        if result and analysis_report and current_form_mode == "single":
            export_payload = _build_single_export_payload(
                form=form,
                analysis=analysis,
                selected_product=selected_product,
                selected_material=selected_material,
            )
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

    product_summary = selected_product_summary(
        selected_product=selected_product,
        data=form if request.method == "POST" else config,
        mode=config.get("mode") or "single",
    )
    bag_summary = selected_bag_summary(
        selected_material=selected_material,
        data=form if request.method == "POST" else config,
    )

    context = {
        "form": form,
        "bag_form": form,
        "bag_config": config,
        "bag_values": config,
        "result": result,
        "image_url": image_url,
        "top5": top5,
        "pending_result": pending_result,
        "analysis_report": analysis_report,
        "materials": materials,
        "products": products,
        "selected_material": selected_material,
        "selected_product": selected_product,
        "selected_product_summary": product_summary,
        "selected_bag_summary": bag_summary,
        "current_mode": config.get("mode") or "single",
        "current_product_source": config.get("product_source") or "manual",
        "current_bag_source": config.get("bag_source") or "manual",
        "mode": "standalone",
        "prefix": "",
        "bag_ui": _build_shared_bag_ui_contract(prefix=""),
        "allow_product_catalogue": True,
    }
    return render(request, "bag_selection/bag_selection_mode1.html", context)


def bag_selection_export_pdf(request):
    export_payload = (
        request.session.get("bag_selection_single_export")
        or request.session.get("bag_selection_last_export")
    )

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

    export_payload["report_type"] = "optimal"
    pdf_buffer = build_bag_selection_pdf(export_payload)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"bag_selection_optimal_report_{timestamp}.pdf"

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
