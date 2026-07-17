import json

from packagingapp.access import visible_packaging_catalogues, visible_product_catalogues, get_visible_packaging_catalogue_or_404, get_visible_product_catalogue_or_404
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from ..forms import PalletizationForm
from ..models import PackagingCatalogue
from ..tools.palletization.export import build_palletization_pdf
from ..tools.palletization.presenter import build_pallet_ui_contract
from ..tools.palletization.serializers import sanitize_palletization_config_for_session
from ..tools.palletization.service import (
    analyze_palletization_config,
    get_box_materials,
    get_pallet_materials,
    get_selected_box_material,
    get_selected_pallet_material,
)
from ..tools.palletization.state import default_palletization_config
from ..tools.threejs_snapshot import save_threejs_snapshot_from_request


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _to_float(value, default=None):
    try:
        if value in (None, "", "None"):
            return default
        return float(value)
    except Exception:
        return default


def _catalogue_dimension(material, external_attr, part_attr):
    """Prefer a positive external dimension, then a positive part dimension.

    Some catalogue imports keep external_* as 0 even when part_* contains the
    usable dimension. Treat 0 as missing for fallback purposes.
    """
    if material is None:
        return ""

    first_raw = ""
    for attr in (external_attr, part_attr):
        raw_value = getattr(material, attr, None)
        numeric_value = _to_float(raw_value, None)
        if raw_value not in (None, "", "None") and first_raw == "":
            first_raw = raw_value
        if numeric_value is not None and numeric_value > 0:
            return raw_value

    return first_raw


SEO_PALLETIZATION_EXAMPLE_CONFIG = {
    "box_source": "manual",
    "box_l": 400,
    "box_w": 300,
    "box_h": 250,
    "box_weight": "",
    "max_weight_on_bottom_box": "",
    "pallet_source": "manual",
    "pallet_l": 1200,
    "pallet_w": 800,
    "max_stack_height": 1500,
    "max_width_stickout": 0,
    "max_length_stickout": 0,
    "show_advanced": False,
}


def _read_raw_palletization_config(request, *, initial_config=None):
    cfg = default_palletization_config()
    if initial_config:
        cfg.update(initial_config)

    if request.method == "POST":
        source = request.POST
    else:
        source = request.GET

    cfg.update({
        "box_source": source.get("box_source", cfg["box_source"]),
        "box_catalogue_id": source.get("box_catalogue_id", cfg["box_catalogue_id"]),
        "selected_box_id": source.get("selected_box_id", cfg["selected_box_id"]),
        "box_l": source.get("box_l", cfg["box_l"]),
        "box_w": source.get("box_w", cfg["box_w"]),
        "box_h": source.get("box_h", cfg["box_h"]),
        "box_weight": source.get("box_weight", cfg["box_weight"]),
        "max_weight_on_bottom_box": source.get(
            "max_weight_on_bottom_box",
            cfg["max_weight_on_bottom_box"],
        ),
        "pallet_source": source.get("pallet_source", cfg["pallet_source"]),
        "pallet_catalogue_id": source.get("pallet_catalogue_id", cfg["pallet_catalogue_id"]),
        "pallet_id": source.get("pallet_id", cfg["pallet_id"]),
        "pallet_l": source.get("pallet_l", cfg["pallet_l"]),
        "pallet_w": source.get("pallet_w", cfg["pallet_w"]),
        "max_stack_height": source.get("max_stack_height", cfg["max_stack_height"]),
        "max_width_stickout": source.get("max_width_stickout", cfg["max_width_stickout"]),
        "max_length_stickout": source.get("max_length_stickout", cfg["max_length_stickout"]),
        "show_advanced": _as_bool(source.get("show_advanced", cfg["show_advanced"])),
    })

    return sanitize_palletization_config_for_session(cfg)


def _build_hydrated_form(request, config, selected_box_material=None, selected_pallet_material=None):
    if request.method == "POST":
        post_data = request.POST.copy()

        if config.get("box_source") == "catalogue" and selected_box_material is not None:
            box_l = _catalogue_dimension(selected_box_material, "external_length", "part_length")
            box_w = _catalogue_dimension(selected_box_material, "external_width", "part_width")
            box_h = _catalogue_dimension(selected_box_material, "external_height", "part_height")

            post_data["box_l"] = "" if box_l is None else str(box_l)
            post_data["box_w"] = "" if box_w is None else str(box_w)
            post_data["box_h"] = "" if box_h is None else str(box_h)

            if (
                (post_data.get("box_weight") in (None, "", "None"))
                and getattr(selected_box_material, "part_weight", None) is not None
            ):
                post_data["box_weight"] = str(selected_box_material.part_weight)

        if config.get("pallet_source") == "catalogue" and selected_pallet_material is not None:
            pallet_l = _catalogue_dimension(selected_pallet_material, "external_length", "part_length")
            pallet_w = _catalogue_dimension(selected_pallet_material, "external_width", "part_width")

            post_data["pallet_l"] = "" if pallet_l is None else str(pallet_l)
            post_data["pallet_w"] = "" if pallet_w is None else str(pallet_w)

        form = PalletizationForm(post_data)
    else:
        initial_data = dict(config)

        if config.get("box_source") == "catalogue" and selected_box_material is not None:
            box_l = _catalogue_dimension(selected_box_material, "external_length", "part_length")
            box_w = _catalogue_dimension(selected_box_material, "external_width", "part_width")
            box_h = _catalogue_dimension(selected_box_material, "external_height", "part_height")

            initial_data["box_l"] = "" if box_l is None else box_l
            initial_data["box_w"] = "" if box_w is None else box_w
            initial_data["box_h"] = "" if box_h is None else box_h

            if (
                initial_data.get("box_weight") in (None, "", "None")
                and getattr(selected_box_material, "part_weight", None) is not None
            ):
                initial_data["box_weight"] = selected_box_material.part_weight

        if config.get("pallet_source") == "catalogue" and selected_pallet_material is not None:
            pallet_l = _catalogue_dimension(selected_pallet_material, "external_length", "part_length")
            pallet_w = _catalogue_dimension(selected_pallet_material, "external_width", "part_width")

            initial_data["pallet_l"] = "" if pallet_l is None else pallet_l
            initial_data["pallet_w"] = "" if pallet_w is None else pallet_w

        form = PalletizationForm(initial=initial_data)

    return form


def _apply_catalogue_choices(form, packaging_catalogues):
    choices = [("", "— Select —")] + [(str(c.id), c.name) for c in packaging_catalogues]
    form.fields["box_catalogue_id"].choices = choices
    form.fields["pallet_catalogue_id"].choices = choices




def _clean_display(value, default="-"):
    if value in (None, "", "None"):
        return default
    return str(value)


def _format_number(value, decimals=0):
    if value in (None, "", "None"):
        return "-"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimals == 0:
        return str(int(round(value)))
    return f"{value:.{decimals}f}".rstrip("0").rstrip(".")


def _format_dims(length, width, height=None):
    parts = [_format_number(length), _format_number(width)]
    if height not in (None, "", "None"):
        parts.append(_format_number(height))
    if any(part == "-" for part in parts):
        return "-"
    return " x ".join(parts) + " mm"


def _format_weight(value):
    if value in (None, "", "None"):
        return "Not provided"
    return f"{_format_number(value, 2)} g"


def _material_payload(material, fallback_part_number):
    if material is None:
        return {
            "part_number": fallback_part_number,
            "description": "Manual input",
            "material": "Manual input",
            "brand": "Manual",
            "picture": "",
        }

    picture = ""
    if getattr(material, "picture", None):
        try:
            picture = material.picture.name or ""
        except ValueError:
            picture = ""

    return {
        "part_number": _clean_display(getattr(material, "part_number", None)),
        "description": _clean_display(getattr(material, "part_description", None)),
        "material": _clean_display(getattr(material, "packaging_materials", None)),
        "brand": _clean_display(getattr(material, "branding", None)),
        "picture": picture,
    }


def _build_palletization_export_payload(*, config, analysis, selected_box_material=None, selected_pallet_material=None):
    serialized = analysis.get("serialized_result") or {}
    selected_result = serialized.get("selected_result") or {}
    effective_config = analysis.get("effective_config") or {}

    if not selected_result:
        return None

    box_base = _material_payload(selected_box_material, "Manual carton")
    pallet_base = _material_payload(selected_pallet_material, "Manual pallet")

    box_source = "Catalogue" if (config.get("box_source") == "catalogue" and selected_box_material is not None) else "Manual"
    pallet_source = "Catalogue" if (config.get("pallet_source") == "catalogue" and selected_pallet_material is not None) else "Manual"

    return {
        "report_type": "standalone",
        "generated_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
        "box": {
            **box_base,
            "source": box_source,
            "dimensions": _format_dims(
                effective_config.get("box_l"),
                effective_config.get("box_w"),
                effective_config.get("box_h"),
            ),
            "weight": _format_weight(effective_config.get("box_weight")),
            "bottom_load_limit": _format_weight(effective_config.get("max_weight_on_bottom_box")),
        },
        "pallet": {
            **pallet_base,
            "source": pallet_source,
            "dimensions": _format_dims(
                effective_config.get("pallet_l"),
                effective_config.get("pallet_w"),
            ),
            "max_stack_height": f"{_format_number(effective_config.get('max_stack_height'))} mm",
            "overhang": (
                f"{_format_number(effective_config.get('max_width_stickout'))} mm width / "
                f"{_format_number(effective_config.get('max_length_stickout'))} mm length"
            ),
        },
        "analysis_report": selected_result,
        "ranking": (serialized.get("results_table") or [])[:5],
    }

def _build_palletization_page_context(
    request,
    *,
    mode,
    initial_config=None,
    run_initial_analysis=False,
):
    """Build one shared view model for every standalone pallet calculator page.

    Both the KolliPack application screen and the public SEO calculator call
    this function, so request parsing, catalogue hydration, engine execution,
    selected-result rendering, and PDF state cannot diverge between them.
    Packaging Flow uses the same service layer and shared templates with a
    prefixed UI contract.
    """
    packaging_catalogues = visible_packaging_catalogues(request.user).order_by("name")

    config = _read_raw_palletization_config(request, initial_config=initial_config)

    selected_box_material = get_selected_box_material(config)
    selected_pallet_material = get_selected_pallet_material(config)

    box_materials = get_box_materials(config)
    pallet_materials = get_pallet_materials(config)

    form = _build_hydrated_form(
        request=request,
        config=config,
        selected_box_material=selected_box_material,
        selected_pallet_material=selected_pallet_material,
    )
    _apply_catalogue_choices(form, packaging_catalogues)

    results_table = []
    selected_result = None
    result_image_url = None
    threejs_scene = None
    active_selected_result_key = ""

    should_run_analysis = run_initial_analysis
    selected_result_key = ""

    if request.method == "POST":
        action = request.POST.get("action") or "refresh"
        selected_result_key = request.POST.get("selected_result_key") or ""
        should_run_analysis = action in ("run_analysis", "select_result")

    if should_run_analysis:
        analysis = analyze_palletization_config(
            config=config,
            selected_result_key=selected_result_key,
            selected_box_material=selected_box_material,
            selected_pallet_material=selected_pallet_material,
            media_root=settings.MEDIA_ROOT,
        )

        if analysis["ok"]:
            serialized = analysis["serialized_result"] or {}
            results_table = serialized.get("results_table") or []
            selected_result = serialized.get("selected_result")
            active_selected_result_key = serialized.get("selected_result_key") or ""
            threejs_scene = serialized.get("threejs_scene")
            image_rel_path = serialized.get("image_rel_path")

            if image_rel_path:
                result_image_url = settings.MEDIA_URL + image_rel_path

            export_payload = _build_palletization_export_payload(
                config=config,
                analysis=analysis,
                selected_box_material=selected_box_material,
                selected_pallet_material=selected_pallet_material,
            )
            if export_payload:
                request.session["palletization_last_export"] = export_payload
                request.session.modified = True
        else:
            for message in analysis["messages"]:
                form.add_error(None, message)

    return {
        "form": form,
        "pallet_form": form,
        "pallet_config": config,
        "box_materials": box_materials,
        "pallet_materials": pallet_materials,
        "selected_box_material": selected_box_material,
        "selected_pallet_material": selected_pallet_material,
        "results_table": results_table,
        "selected_result": selected_result,
        "result_image_url": result_image_url,
        "threejs_scene": threejs_scene,
        "current_box_source": config.get("box_source") or "manual",
        "current_pallet_source": config.get("pallet_source") or "manual",
        "show_advanced": bool(config.get("show_advanced", False)),
        "show_pdf_export": True,
        "mode": mode,
        "prefix": "",
        "packaging_catalogues": packaging_catalogues,
        "pallet_values": {
            **{
                key: config.get(key)
                for key in default_palletization_config().keys()
            },
            "selected_result_key": active_selected_result_key,
        },
        "pallet_ui": build_pallet_ui_contract(prefix=""),
        "pallet_debug": settings.DEBUG,
    }


def _build_palletization_seo_schema(request):
    canonical_url = request.build_absolute_uri(reverse("palletization_calculator"))
    company_url = request.build_absolute_uri(reverse("company_home"))
    app_url = request.build_absolute_uri(reverse("palletization_mode1"))

    faq_items = [
        (
            "What does a palletization calculator calculate?",
            "It estimates cartons per layer, number of layers, total cartons, pallet floor usage, stack volume usage, and available alternative layer patterns from carton and pallet dimensions.",
        ),
        (
            "Is the KolliPack palletization calculator free?",
            "Yes. The public calculator can be used without creating an account during the KolliPack early launch.",
        ),
        (
            "Which carton dimensions should I use?",
            "Use the external length, width, and height of the packed carton because those dimensions occupy space on the pallet.",
        ),
        (
            "Can the calculator evaluate pallet overhang?",
            "Yes. Optional maximum overhang values can be entered for the pallet length and width directions, but overhang should only be used when handling and transport rules allow it.",
        ),
        (
            "Does the result replace physical pallet testing?",
            "No. The result is an engineering estimate. Final approval should still consider carton compression strength, load stability, wrapping, handling, vibration, and customer requirements.",
        ),
    ]

    schema = [
        {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "KolliPack Free Palletization Calculator",
            "applicationCategory": "BusinessApplication",
            "applicationSubCategory": "Packaging engineering calculator",
            "operatingSystem": "Any web browser",
            "url": canonical_url,
            "description": (
                "Calculate pallet patterns, cartons per layer, total cartons, stack height, "
                "pallet floor usage, and stack volume usage with a free online palletization tool."
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
                "Ranked pallet patterns",
                "Main and alternate layer layouts",
                "Cartons per layer and total cartons",
                "Pallet floor and stack volume utilization",
                "Optional overhang and bottom-carton load checks",
                "3D pallet visualization",
                "PDF engineering report",
            ],
            "potentialAction": {
                "@type": "UseAction",
                "target": canonical_url,
            },
            "sameAs": [app_url],
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": answer,
                    },
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
                    "name": "Free Palletization Calculator",
                    "item": canonical_url,
                },
            ],
        },
    ]

    return canonical_url, faq_items, json.dumps(schema, ensure_ascii=False)


def palletization_mode1(request):
    return render(
        request,
        "palletization/palletization_mode1.html",
        _build_palletization_page_context(request, mode="standalone"),
    )


def palletization_calculator(request):
    is_initial_example = request.method == "GET" and not request.GET
    context = _build_palletization_page_context(
        request,
        mode="seo",
        initial_config=SEO_PALLETIZATION_EXAMPLE_CONFIG if is_initial_example else None,
        run_initial_analysis=is_initial_example,
    )
    canonical_url, faq_items, schema_json = _build_palletization_seo_schema(request)
    context.update(
        {
            "canonical_url": canonical_url,
            "faq_items": faq_items,
            "seo_schema_json": schema_json,
            "is_initial_example": is_initial_example,
            "example_carton_dimensions": "400 × 300 × 250 mm",
            "example_pallet_dimensions": "1200 × 800 mm",
            "example_stack_height": "1500 mm",
        }
    )
    return render(request, "marketing/palletization_calculator.html", context)

def palletization_export_pdf(request):
    export_payload = request.session.get("palletization_last_export")

    if not export_payload:
        return HttpResponse(
            "Please run a palletization analysis before exporting a PDF report.",
            status=400,
            content_type="text/plain",
        )

    snapshot_rel_path = save_threejs_snapshot_from_request(
        request,
        relative_directory="palletization_exports/threejs",
    )
    if not snapshot_rel_path:
        return HttpResponse(
            "The current Three.js pallet view was not captured. Wait until the interactive 3D viewer is visible, then use its PDF export button and try again.",
            status=400,
            content_type="text/plain",
        )

    allowed_view_labels = {
        "Current interactive 3D view - reset/corner view",
        "Current interactive 3D view - top view",
        "Current interactive 3D view - front view",
        "Current interactive 3D view - side view",
    }
    view_label = request.POST.get("threejs_view_label") or ""
    if view_label not in allowed_view_labels:
        view_label = "Current interactive 3D view"

    report_payload = dict(export_payload)
    report_payload["threejs_snapshot_rel_path"] = snapshot_rel_path
    report_payload["threejs_view_label"] = view_label

    pdf_buffer = build_palletization_pdf(report_payload)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"palletization_report_{timestamp}.pdf"

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
