from django.shortcuts import render

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
        },
        "ids": {
            "root": f"containerSelectionRoot{suffix}",
            "product_catalogue_section": f"productCatalogueSection{suffix}",
            "container_catalogue_section": f"containerCatalogueSection{suffix}",
            "manual_product_fields": f"manualProductFields{suffix}",
            "manual_container_fields": f"manualContainerFields{suffix}",
            "selected_product_id": f"selected_product_id{suffix}",
            "container_id": f"container_id{suffix}",
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


def container_selection_mode1(request):
    packaging_catalogues = get_packaging_catalogues()
    product_catalogues = get_product_catalogues()

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