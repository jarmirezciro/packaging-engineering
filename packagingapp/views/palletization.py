from packagingapp.access import visible_packaging_catalogues, visible_product_catalogues, get_visible_packaging_catalogue_or_404, get_visible_product_catalogue_or_404
from django.conf import settings
from django.shortcuts import render

from ..forms import PalletizationForm
from ..models import PackagingCatalogue
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
                image_rel_path = serialized.get("image_rel_path")

                if image_rel_path:
                    result_image_url = settings.MEDIA_URL + image_rel_path
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
                k: config.get(k)
                for k in default_palletization_config().keys()
            },
            "pallet_ui": _build_shared_pallet_ui_contract(prefix=""),
        },
    )