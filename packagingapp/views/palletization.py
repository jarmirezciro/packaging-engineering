from packagingapp.access import visible_packaging_catalogues, visible_product_catalogues, get_visible_packaging_catalogue_or_404, get_visible_product_catalogue_or_404
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from ..forms import PalletizationForm
from ..models import PackagingCatalogue
from ..tools.palletization.export import build_palletization_pdf
from ..tools.palletization.serializers import sanitize_palletization_config_for_session
from ..tools.palletization.service import (
    analyze_palletization_config,
    get_box_materials,
    get_pallet_materials,
    get_selected_box_material,
    get_selected_pallet_material,
)
from ..tools.palletization.state import default_palletization_config


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _read_raw_palletization_config(request):
    cfg = default_palletization_config()

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
            box_l = selected_box_material.external_length
            box_w = selected_box_material.external_width
            box_h = selected_box_material.external_height

            if box_l is None:
                box_l = selected_box_material.part_length
            if box_w is None:
                box_w = selected_box_material.part_width
            if box_h is None:
                box_h = selected_box_material.part_height

            post_data["box_l"] = "" if box_l is None else str(box_l)
            post_data["box_w"] = "" if box_w is None else str(box_w)
            post_data["box_h"] = "" if box_h is None else str(box_h)

            if (
                (post_data.get("box_weight") in (None, "", "None"))
                and getattr(selected_box_material, "part_weight", None) is not None
            ):
                post_data["box_weight"] = str(selected_box_material.part_weight)

        if config.get("pallet_source") == "catalogue" and selected_pallet_material is not None:
            pallet_l = selected_pallet_material.external_length
            pallet_w = selected_pallet_material.external_width

            if pallet_l is None:
                pallet_l = selected_pallet_material.part_length
            if pallet_w is None:
                pallet_w = selected_pallet_material.part_width

            post_data["pallet_l"] = "" if pallet_l is None else str(pallet_l)
            post_data["pallet_w"] = "" if pallet_w is None else str(pallet_w)

        form = PalletizationForm(post_data)
    else:
        initial_data = dict(config)

        if config.get("box_source") == "catalogue" and selected_box_material is not None:
            box_l = selected_box_material.external_length
            box_w = selected_box_material.external_width
            box_h = selected_box_material.external_height

            if box_l is None:
                box_l = selected_box_material.part_length
            if box_w is None:
                box_w = selected_box_material.part_width
            if box_h is None:
                box_h = selected_box_material.part_height

            initial_data["box_l"] = "" if box_l is None else box_l
            initial_data["box_w"] = "" if box_w is None else box_w
            initial_data["box_h"] = "" if box_h is None else box_h

            if (
                initial_data.get("box_weight") in (None, "", "None")
                and getattr(selected_box_material, "part_weight", None) is not None
            ):
                initial_data["box_weight"] = selected_box_material.part_weight

        if config.get("pallet_source") == "catalogue" and selected_pallet_material is not None:
            pallet_l = selected_pallet_material.external_length
            pallet_w = selected_pallet_material.external_width

            if pallet_l is None:
                pallet_l = selected_pallet_material.part_length
            if pallet_w is None:
                pallet_w = selected_pallet_material.part_width

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
        "image_rel_path": serialized.get("image_rel_path") or "",
    }

def _build_shared_pallet_ui_contract(prefix=""):
    suffix = f"_{prefix}" if prefix else ""

    return {
        "prefix": prefix,
        "names": {
            "action": f"action{suffix}",
            "selected_box_id": f"selected_box_id{suffix}",
            "pallet_id": f"pallet_id{suffix}",
            "selected_result_key": f"selected_result_key{suffix}",
            "show_advanced": f"show_advanced{suffix}",
            "box_source": f"box_source{suffix}",
            "box_catalogue_id": f"box_catalogue_id{suffix}",
            "box_l": f"box_l{suffix}",
            "box_w": f"box_w{suffix}",
            "box_h": f"box_h{suffix}",
            "box_weight": f"box_weight{suffix}",
            "max_weight_on_bottom_box": f"max_weight_on_bottom_box{suffix}",
            "pallet_source": f"pallet_source{suffix}",
            "pallet_catalogue_id": f"pallet_catalogue_id{suffix}",
            "pallet_l": f"pallet_l{suffix}",
            "pallet_w": f"pallet_w{suffix}",
            "max_stack_height": f"max_stack_height{suffix}",
            "max_width_stickout": f"max_width_stickout{suffix}",
            "max_length_stickout": f"max_length_stickout{suffix}",
        },
        "ids": {
            "root": f"palletizationToolRoot{suffix}",
            "box_catalogue_chooser": f"boxCatalogueChooser{suffix}",
            "manual_box_fields": f"manualBoxFields{suffix}",
            "pallet_catalogue_chooser": f"palletCatalogueChooser{suffix}",
            "manual_pallet_fields": f"manualPalletFields{suffix}",
            "catalogue_pallet_main_fields": f"cataloguePalletMainFields{suffix}",
            "stacking_constraints_section": f"stackingConstraintsSection{suffix}",
            "toggle_constraints_text": f"toggleConstraintsText{suffix}",
            "toggle_constraints_icon": f"toggleConstraintsIcon{suffix}",
            "selected_result_key": f"selected_result_key{suffix}",
            "show_advanced": f"show_advanced{suffix}",
        },
        "actions": {
            "browse_box": "palletToolBrowseBoxCatalogue",
            "clear_box": "palletToolClearSelectedBox",
            "select_box": "palletToolSelectBox",
            "browse_pallet": "palletToolBrowsePalletCatalogue",
            "clear_pallet": "palletToolClearSelectedPallet",
            "select_pallet": "palletToolSelectPallet",
            "toggle_advanced": "palletToolToggleConstraints",
            "run_analysis": "palletToolRunAnalysis",
            "select_result": "palletToolSelectResult",
        },
    }

def palletization_mode1(request):
    packaging_catalogues = visible_packaging_catalogues(request.user).order_by("name")

    config = _read_raw_palletization_config(request)

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
    active_selected_result_key = ""

    if request.method == "POST":
        action = request.POST.get("action") or "refresh"
        selected_result_key = request.POST.get("selected_result_key") or ""

        if action in ("run_analysis", "select_result"):
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

    return render(
        request,
        "palletization/palletization_mode1.html",
        {
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
            "current_box_source": config.get("box_source") or "manual",
            "current_pallet_source": config.get("pallet_source") or "manual",
            "show_advanced": bool(config.get("show_advanced", False)),
            "mode": "standalone",
            "prefix": "",
            "packaging_catalogues": packaging_catalogues,
            "pallet_values": {
                **{
                    k: config.get(k)
                    for k in default_palletization_config().keys()
                },
                "selected_result_key": active_selected_result_key,
            },
            "pallet_ui": _build_shared_pallet_ui_contract(prefix=""),
            "pallet_debug": settings.DEBUG,
        },
    )


def palletization_export_pdf(request):
    export_payload = request.session.get("palletization_last_export")

    if not export_payload:
        return HttpResponse(
            "Please run a palletization analysis before exporting a PDF report.",
            status=400,
            content_type="text/plain",
        )

    pdf_buffer = build_palletization_pdf(export_payload)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    filename = f"palletization_report_{timestamp}.pdf"

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
