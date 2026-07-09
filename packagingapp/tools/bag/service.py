from django.conf import settings

from ...access import visible_packaging_catalogues, visible_product_catalogues
from ...forms import BagSelectionForm
from ...models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
from ...utils.bag_selection.engine import (
    build_required_bag_options,
    best_usage_for_bag,
    compute_max_quantity_for_bag,
    run_bag_mode1_and_render,
)

from .serializers import sanitize_bag_config_for_session


BAG_DRAW_LIMIT = 250


def _to_float(value):
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value, default=1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _round_or_none(value, digits=2):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _round_int_or_none(value):
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _format_percent(value):
    if value is None:
        return "Not available"
    try:
        return f"{float(value):.0f}%"
    except (TypeError, ValueError):
        return "Not available"


def _format_weight(value):
    if value in (None, "", "None"):
        return "Not available"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "Not available"
    if abs(numeric) >= 1000:
        return f"{numeric / 1000:.2f} kg"
    return f"{numeric:.0f} g"


def _first_available_numeric_attr(obj, names):
    if obj is None:
        return None
    for name in names:
        if not hasattr(obj, name):
            continue
        numeric = _to_float(getattr(obj, name, None))
        if numeric is not None:
            return numeric
    return None


def get_packaging_catalogues(user=None):
    return visible_packaging_catalogues(user).order_by("name")


def get_product_catalogues(user=None):
    return visible_product_catalogues(user).order_by("name")


def get_products_for_catalogue(config):
    product_catalogue_id = (config or {}).get("product_catalogue_id")
    if not product_catalogue_id:
        return Product.objects.none()
    return Product.objects.filter(catalogue_id=product_catalogue_id).select_related("catalogue").order_by("-created_at")


def get_materials_for_catalogue(config):
    catalogue_id = (config or {}).get("catalogue_id")
    if not catalogue_id:
        return PackagingMaterial.objects.none()
    return PackagingMaterial.objects.filter(catalogue_id=catalogue_id, packaging_type="BAG").select_related("catalogue").order_by("part_number")


def get_selected_product(config):
    selected_product_id = (config or {}).get("selected_product_id")
    if not selected_product_id:
        return None
    return Product.objects.filter(id=selected_product_id).select_related("catalogue").first()


def get_selected_material(config):
    bag_id = (config or {}).get("bag_id")
    if not bag_id:
        return None
    return PackagingMaterial.objects.filter(id=bag_id, packaging_type="BAG").select_related("catalogue").first()


def build_hydrated_post_data(raw_post, config, selected_product=None, selected_material=None):
    post_data = raw_post.copy()

    if config.get("product_source") == "catalogue" and selected_product is not None:
        post_data["product_l"] = "" if selected_product.product_length is None else str(selected_product.product_length)
        post_data["product_w"] = "" if selected_product.product_width is None else str(selected_product.product_width)
        post_data["product_h"] = "" if selected_product.product_height is None else str(selected_product.product_height)
        if post_data.get("product_weight") in (None, "", "None") and getattr(selected_product, "weight", None) is not None:
            post_data["product_weight"] = str(selected_product.weight)
        if config.get("mode") == "optimal" and getattr(selected_product, "desired_qty", None) not in (None, "", "None"):
            post_data["desired_qty"] = str(selected_product.desired_qty)

    if config.get("bag_source") == "catalogue" and selected_material is not None:
        post_data["bag_length"] = "" if selected_material.part_length is None else str(selected_material.part_length)
        post_data["bag_width"] = "" if selected_material.part_width is None else str(selected_material.part_width)
        if post_data.get("bag_weight") in (None, "", "None") and getattr(selected_material, "part_weight", None) is not None:
            post_data["bag_weight"] = str(selected_material.part_weight)
        payload = _resolve_payload_capacity_from_material(selected_material)
        if post_data.get("bag_max_payload") in (None, "", "None") and payload is not None:
            post_data["bag_max_payload"] = str(payload)

    return post_data


def build_initial_data(config, selected_product=None, selected_material=None):
    initial_data = dict(config)

    if config.get("product_source") == "catalogue" and selected_product is not None:
        initial_data.update({
            "product_l": selected_product.product_length,
            "product_w": selected_product.product_width,
            "product_h": selected_product.product_height,
            "product_weight": getattr(selected_product, "weight", None),
        })
        if config.get("mode") == "optimal":
            initial_data["desired_qty"] = getattr(selected_product, "desired_qty", None) or initial_data.get("desired_qty")

    if config.get("bag_source") == "catalogue" and selected_material is not None:
        initial_data.update({
            "bag_length": selected_material.part_length,
            "bag_width": selected_material.part_width,
            "bag_weight": getattr(selected_material, "part_weight", None),
            "bag_max_payload": _resolve_payload_capacity_from_material(selected_material),
        })

    return initial_data


def build_bag_form(request, config, selected_product=None, selected_material=None):
    if request.method == "POST":
        hydrated_post = build_hydrated_post_data(
            raw_post=request.POST,
            config=config,
            selected_product=selected_product,
            selected_material=selected_material,
        )
        form = BagSelectionForm(hydrated_post)
    else:
        form = BagSelectionForm(initial=build_initial_data(config, selected_product, selected_material))
    return form


def apply_catalogue_choices(form, packaging_catalogues, product_catalogues):
    form.fields["catalogue_id"].choices = [("", "— Select —")] + [(str(c.id), c.name) for c in packaging_catalogues]
    form.fields["product_catalogue_id"].choices = [("", "— Select —")] + [(str(c.id), c.name) for c in product_catalogues]


def resolve_product_tuple(config, selected_product=None):
    product_source = (config or {}).get("product_source") or "manual"
    if product_source == "catalogue":
        if selected_product is None:
            return None
        return (
            float(selected_product.product_length),
            float(selected_product.product_width),
            float(selected_product.product_height),
        )

    product_l = _to_float((config or {}).get("product_l"))
    product_w = _to_float((config or {}).get("product_w"))
    product_h = _to_float((config or {}).get("product_h"))
    if None in (product_l, product_w, product_h):
        return None
    return (product_l, product_w, product_h)


def _resolve_product_weight(config, selected_product=None):
    if (config or {}).get("product_source") == "catalogue" and selected_product is not None:
        return _to_float(getattr(selected_product, "weight", None))
    return _to_float((config or {}).get("product_weight"))


def _resolve_bag_weight(config, selected_material=None):
    if (config or {}).get("bag_source") == "catalogue" and selected_material is not None:
        return _to_float(getattr(selected_material, "part_weight", None))
    return _to_float((config or {}).get("bag_weight"))


def _resolve_payload_capacity_from_material(selected_material):
    return _first_available_numeric_attr(
        selected_material,
        [
            "max_payload",
            "payload_capacity",
            "max_payload_kg",
            "max_load",
            "max_load_kg",
            "max_weight",
            "max_weight_kg",
        ],
    )


def _resolve_payload_capacity(config, selected_material=None):
    if (config or {}).get("bag_source") == "catalogue" and selected_material is not None:
        return _resolve_payload_capacity_from_material(selected_material)
    return _to_float((config or {}).get("bag_max_payload"))


def _resolve_visual_bag_box(selected_bag, inner_box):
    bag_len, bag_w = selected_bag
    body_length, body_width, body_height = inner_box

    tolerance = 2.0
    sealing_area = 10.0

    # Bag L and W are physical dimensions. Length carries the sealing allowance;
    # width is the opening side and only carries tolerance. They should not be
    # swapped here. The engine already chooses the correct product-arrangement
    # orientation before returning inner_box.
    bag_box_length = bag_len - tolerance - sealing_area - body_height
    bag_box_width = bag_w - tolerance - body_height

    if bag_box_length <= 0 or bag_box_width <= 0:
        return None

    bag_box_length = max(float(bag_box_length), float(body_length))
    bag_box_width = max(float(bag_box_width), float(body_width))

    return (round(bag_box_length, 2), round(bag_box_width, 2), round(float(body_height), 2))


def build_bag_analysis_report(
    *,
    config,
    result,
    product,
    quantity,
    selected_product=None,
    selected_material=None,
):
    if result is None or product is None:
        return None

    current_quantity = int(quantity or result.get("desired_qty") or result.get("max_quantity") or 0)

    product_volume = float(product[0]) * float(product[1]) * float(product[2])
    bag_len = _to_float(result.get("bag_len")) or 0
    bag_w = _to_float(result.get("bag_w")) or 0
    bag_area = bag_len * bag_w

    best_required_current = result.get("best_required")
    required_area_current = None
    bag_usage_current_pct = None
    if best_required_current:
        required_area_current = float(best_required_current[0]) * float(best_required_current[1])
        if bag_area > 0:
            bag_usage_current_pct = (required_area_current / bag_area) * 100
    elif result.get("usage") is not None:
        bag_usage_current_pct = float(result.get("usage") or 0) * 100

    max_quantity = int(result.get("max_quantity") or 0)
    bag_usage_max_pct = None
    max_required_area = None
    max_search_capped = bool(result.get("search_capped"))

    if bag_len > 0 and bag_w > 0:
        max_info = compute_max_quantity_for_bag(product[0], product[1], product[2], bag_len, bag_w)
        max_quantity = int(max_info.get("max_quantity") or max_quantity or 0)
        max_best = max_info.get("best")
        max_search_capped = bool(max_info.get("capped")) or max_search_capped
        if max_best:
            max_required_area = float(max_best["req_len"]) * float(max_best["req_w"])
            bag_usage_max_pct = float(max_best.get("usage") or 0) * 100

    if bag_usage_max_pct is None:
        bag_usage_max_pct = bag_usage_current_pct

    remaining_capacity = None
    if max_quantity is not None:
        remaining_capacity = max(max_quantity - current_quantity, 0)

    product_weight = _resolve_product_weight(config, selected_product)
    bag_weight = _resolve_bag_weight(config, selected_material)
    payload_capacity = _resolve_payload_capacity(config, selected_material)

    net_weight = None
    total_weight = None
    payload_usage_pct = None

    if product_weight is not None:
        net_weight = product_weight * current_quantity
        if bag_weight is not None:
            total_weight = net_weight + bag_weight
        if payload_capacity and payload_capacity > 0:
            payload_usage_pct = (net_weight / payload_capacity) * 100

    return {
        "current_quantity": current_quantity,
        "requested_qty": current_quantity,
        "max_quantity": max_quantity,
        "remaining_capacity": remaining_capacity,
        "fits": bool(result.get("fits")),
        "bag_area": _round_or_none(bag_area, 2),
        "required_area": _round_or_none(required_area_current, 2),
        "required_area_current": _round_or_none(required_area_current, 2),
        "required_area_max": _round_or_none(max_required_area, 2),
        "bag_usage_current_pct": _round_int_or_none(bag_usage_current_pct),
        "bag_usage_max_pct": _round_int_or_none(bag_usage_max_pct),
        "area_usage_pct": _round_int_or_none(bag_usage_current_pct),
        "bag_usage_current_display": _format_percent(bag_usage_current_pct),
        "bag_usage_max_display": _format_percent(bag_usage_max_pct),
        "area_usage_display": _format_percent(bag_usage_current_pct),
        "product_volume": _round_or_none(product_volume, 2),
        "total_product_volume": _round_or_none(product_volume * current_quantity, 2),
        "product_weight": _round_or_none(product_weight, 3),
        "bag_weight": _round_or_none(bag_weight, 3),
        "payload_capacity": _round_or_none(payload_capacity, 3),
        "net_weight": _round_or_none(net_weight, 3),
        "total_weight": _round_or_none(total_weight, 3),
        "payload_usage_pct": _round_int_or_none(payload_usage_pct),
        "product_weight_display": _format_weight(product_weight),
        "bag_weight_display": _format_weight(bag_weight),
        "payload_capacity_display": _format_weight(payload_capacity),
        "net_weight_display": _format_weight(net_weight),
        "total_weight_display": _format_weight(total_weight),
        "payload_usage_display": _format_percent(payload_usage_pct),
        "has_product_weight": product_weight is not None,
        "has_bag_weight": bag_weight is not None,
        "has_payload_capacity": payload_capacity is not None,
        "has_total_weight": total_weight is not None,
        "has_payload_usage": payload_usage_pct is not None,
        "search_capped": max_search_capped,
        "calculation_note": "Bag dimensions and product dimensions are treated as millimetres. Sealing allowance is included in the bag formula.",
    }


def _build_pending_result(label, selected_bag, render_res, quantity):
    bag_box = _resolve_visual_bag_box(selected_bag, render_res.inner_box)
    if bag_box:
        length, width, height = bag_box
    else:
        length, width, height = (
            round(render_res.inner_box[0], 2),
            round(render_res.inner_box[1], 2),
            round(render_res.inner_box[2], 2),
        )
    return {
        "label": label,
        "length": length,
        "width": width,
        "height": height,
        "units_per_parent": int(quantity or 1),
        "total_base_units": int(quantity or 1),
    }


def analyze_bag_config(config, action, selected_product=None, selected_material=None, materials=None, media_root=None):
    cfg = sanitize_bag_config_for_session(config)
    mode = cfg.get("mode") or "single"
    product_source = cfg.get("product_source") or "manual"
    bag_source = cfg.get("bag_source") or "manual"

    result = None
    image_url = None
    top5 = []
    pending_result = None
    analysis_report = None
    messages = []

    product = resolve_product_tuple(cfg, selected_product)

    if mode == "optimal" and product_source == "catalogue" and selected_product is not None:
        desired_qty = int(selected_product.desired_qty or 1)
    else:
        desired_qty = _to_int(cfg.get("desired_qty"), 1) or 1

    if mode == "single" and action in ("run_single", "select_bag"):
        bag = None
        if product_source == "catalogue" and not selected_product:
            messages.append("Please select a product from the product catalogue.")
        elif product_source == "manual" and (not product or None in product):
            messages.append("Please enter product dimensions in mm.")

        if not messages:
            if bag_source == "manual":
                bag_l = _to_float(cfg.get("bag_length"))
                bag_w = _to_float(cfg.get("bag_width"))
                if bag_l is None or bag_w is None:
                    messages.append("Please enter bag length and width in mm.")
                else:
                    bag = (bag_l, bag_w)
            else:
                if not selected_material:
                    messages.append("Please select a bag from the packaging catalogue.")
                else:
                    bag = (float(selected_material.part_length), float(selected_material.part_width))

        if not messages and bag is not None and product is not None:
            max_info = compute_max_quantity_for_bag(product[0], product[1], product[2], bag[0], bag[1])
            max_qty = int(max_info.get("max_quantity") or 0)
            best = max_info.get("best")
            result = {
                "kind": "bag",
                "max_quantity": max_qty,
                "desired_qty": max_qty,
                "smooth_qty": int(max_info.get("smooth_qty") or 0),
                "fits": best is not None and max_qty > 0,
                "bag_len": bag[0],
                "bag_w": bag[1],
                "best_required": (best["req_len"], best["req_w"]) if best else None,
                "usage": best["usage"] if best else 0.0,
                "required_bags": max_info.get("required_bags") or [],
                "usage_pct": round((best["usage"] if best else 0.0) * 100, 2),
                "search_capped": bool(max_info.get("capped")),
            }
            analysis_report = build_bag_analysis_report(
                config=cfg,
                result=result,
                product=product,
                quantity=max_qty,
                selected_product=selected_product,
                selected_material=selected_material,
            )
            if best is not None and max_qty > 0:
                render_res = run_bag_mode1_and_render(
                    product=product,
                    selected_bag=(bag[0], bag[1]),
                    desired_qty=max_qty,
                    solutions=max_info["solutions"],
                    media_root=media_root or settings.MEDIA_ROOT,
                    draw_limit=min(max_qty, BAG_DRAW_LIMIT),
                    selected_required_bag=result.get("best_required"),
                )
                result["image_rel_path"] = render_res.image_rel_path
                image_url = settings.MEDIA_URL + render_res.image_rel_path
                label = selected_material.part_number if selected_material else "Manual Bag"
                pending_result = _build_pending_result(label, (bag[0], bag[1]), render_res, max_qty)

    if mode == "optimal" and action in ("find_top5", "select_candidate"):
        if product_source == "catalogue" and not selected_product:
            messages.append("Please select a product from the product catalogue.")
        elif product_source == "manual" and (not product or None in product):
            messages.append("Please enter product dimensions in mm.")
        elif not cfg.get("catalogue_id"):
            messages.append("Please select a packaging catalogue.")

        if not messages:
            req = build_required_bag_options(product[0], product[1], product[2], desired_qty)
            required_bags = req["required"]
            scored = []
            for m in (materials or []):
                bag_len = float(m.part_length or 0)
                bag_w = float(m.part_width or 0)
                if bag_len <= 0 or bag_w <= 0:
                    continue
                best = best_usage_for_bag(bag_len, bag_w, required_bags)
                if best is None:
                    continue
                scored.append({
                    "id": str(m.id),
                    "part_number": m.part_number,
                    "description": m.part_description,
                    "branding": m.branding,
                    "bag_len": round(bag_len, 2),
                    "bag_w": round(bag_w, 2),
                    "usage": best["usage"],
                    "usage_pct": round(best["usage"] * 100, 2),
                    "best_required": (best["req_len"], best["req_w"]),
                    "bag_area": bag_len * bag_w,
                })
            scored.sort(key=lambda x: (-x["usage"], x["bag_area"]))
            top5 = scored[:5]

            if action == "select_candidate":
                if not selected_material:
                    messages.append("Please select one of the Top 5 bags.")
                else:
                    bag = (float(selected_material.part_length), float(selected_material.part_width))
                    best = best_usage_for_bag(bag[0], bag[1], required_bags)
                    result = {
                        "kind": "bag",
                        "max_quantity": None,
                        "desired_qty": desired_qty,
                        "smooth_qty": req["smooth_qty"],
                        "fits": best is not None,
                        "bag_len": bag[0],
                        "bag_w": bag[1],
                        "best_required": (best["req_len"], best["req_w"]) if best else None,
                        "usage": best["usage"] if best else 0.0,
                        "required_bags": required_bags,
                        "usage_pct": round((best["usage"] if best else 0.0) * 100, 2),
                    }
                    analysis_report = build_bag_analysis_report(
                        config=cfg,
                        result=result,
                        product=product,
                        quantity=desired_qty,
                        selected_product=selected_product,
                        selected_material=selected_material,
                    )
                    if best is not None:
                        render_res = run_bag_mode1_and_render(
                            product=product,
                            selected_bag=(bag[0], bag[1]),
                            desired_qty=desired_qty,
                            solutions=req["solutions"],
                            media_root=media_root or settings.MEDIA_ROOT,
                            draw_limit=min(desired_qty, BAG_DRAW_LIMIT),
                            selected_required_bag=result.get("best_required"),
                        )
                        result["image_rel_path"] = render_res.image_rel_path
                        image_url = settings.MEDIA_URL + render_res.image_rel_path
                        pending_result = _build_pending_result(selected_material.part_number, (bag[0], bag[1]), render_res, desired_qty)

    return {
        "messages": messages,
        "result": result,
        "image_url": image_url,
        "top5": top5,
        "pending_result": pending_result,
        "analysis_report": analysis_report,
    }
