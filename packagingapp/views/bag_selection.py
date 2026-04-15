from django.shortcuts import render

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
        "desired_qty": source.get("desired_qty", cfg["desired_qty"]),
        "bag_source": source.get("bag_source", cfg["bag_source"]),
        "catalogue_id": source.get("catalogue_id", cfg["catalogue_id"]),
        "bag_id": source.get("bag_id", cfg["bag_id"]),
        "bag_length": source.get("bag_length", cfg["bag_length"]),
        "bag_width": source.get("bag_width", cfg["bag_width"]),
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
            "desired_qty": f"desired_qty{suffix}",
            "bag_source": f"bag_source{suffix}",
            "catalogue_id": f"catalogue_id{suffix}",
            "bag_id": f"bag_id{suffix}",
            "bag_length": f"bag_length{suffix}",
            "bag_width": f"bag_width{suffix}",
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
