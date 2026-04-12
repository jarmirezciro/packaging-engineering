from django.conf import settings

from ...forms import BagSelectionForm
from ...models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
from ...utils.bag_selection.engine import (
    build_required_bag_options,
    best_usage_for_bag,
    run_bag_mode1_and_render,
)

from .serializers import sanitize_bag_config_for_session


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


def get_packaging_catalogues():
    return PackagingCatalogue.objects.all().order_by("name")


def get_product_catalogues():
    return ProductCatalogue.objects.all().order_by("name")


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
    return PackagingMaterial.objects.filter(id=bag_id).select_related("catalogue").first()


def build_hydrated_post_data(raw_post, config, selected_product=None, selected_material=None):
    post_data = raw_post.copy()

    if config.get("product_source") == "catalogue" and selected_product is not None:
        post_data["product_l"] = "" if selected_product.product_length is None else str(selected_product.product_length)
        post_data["product_w"] = "" if selected_product.product_width is None else str(selected_product.product_width)
        post_data["product_h"] = "" if selected_product.product_height is None else str(selected_product.product_height)
        if config.get("mode") == "optimal" and getattr(selected_product, "desired_qty", None) not in (None, "", "None"):
            post_data["desired_qty"] = str(selected_product.desired_qty)

    if config.get("bag_source") == "catalogue" and selected_material is not None:
        post_data["bag_length"] = "" if selected_material.part_length is None else str(selected_material.part_length)
        post_data["bag_width"] = "" if selected_material.part_width is None else str(selected_material.part_width)

    return post_data


def build_initial_data(config, selected_product=None, selected_material=None):
    initial_data = dict(config)

    if config.get("product_source") == "catalogue" and selected_product is not None:
        initial_data.update({
            "product_l": selected_product.product_length,
            "product_w": selected_product.product_width,
            "product_h": selected_product.product_height,
        })
        if config.get("mode") == "optimal":
            initial_data["desired_qty"] = getattr(selected_product, "desired_qty", None) or initial_data.get("desired_qty")

    if config.get("bag_source") == "catalogue" and selected_material is not None:
        initial_data.update({
            "bag_length": selected_material.part_length,
            "bag_width": selected_material.part_width,
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


def _resolve_visual_bag_box(selected_bag, inner_box):
    bag_len, bag_w = selected_bag
    bl, bw, bh = inner_box

    tolerance = 20.0
    sealing_area = 50.0

    candidates = []

    box_length_a = bag_len - tolerance - bh
    box_width_a = bag_w - tolerance - sealing_area - bh
    if box_length_a > 0 and box_width_a > 0:
        candidates.append((box_length_a, box_width_a))

    box_length_b = bag_w - tolerance - bh
    box_width_b = bag_len - tolerance - sealing_area - bh
    if box_length_b > 0 and box_width_b > 0:
        candidates.append((box_length_b, box_width_b))

    if not candidates:
        return None

    valid_candidates = [
        (l, w) for l, w in candidates
        if l + 1e-9 >= bl and w + 1e-9 >= bw
    ]

    if valid_candidates:
        bag_box_length, bag_box_width = min(valid_candidates, key=lambda t: (t[0] * t[1], t[0] + t[1]))
    else:
        bag_box_length, bag_box_width = min(candidates, key=lambda t: (t[0] * t[1], t[0] + t[1]))

    return (round(bag_box_length, 2), round(bag_box_width, 2), round(bh, 2))


def analyze_bag_config(config, action, selected_product=None, selected_material=None, materials=None, media_root=None):
    cfg = sanitize_bag_config_for_session(config)
    mode = cfg.get("mode") or "single"
    product_source = cfg.get("product_source") or "manual"
    bag_source = cfg.get("bag_source") or "manual"

    result = None
    image_url = None
    top5 = []
    pending_result = None
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
            messages.append("Please enter product dimensions.")

        if not messages:
            if bag_source == "manual":
                bag_l = _to_float(cfg.get("bag_length"))
                bag_w = _to_float(cfg.get("bag_width"))
                if bag_l is None or bag_w is None:
                    messages.append("Please enter bag length and width.")
                else:
                    bag = (bag_l, bag_w)
            else:
                if not selected_material:
                    messages.append("Please select a bag from the packaging catalogue.")
                else:
                    bag = (float(selected_material.part_length), float(selected_material.part_width))

        if not messages and bag is not None and product is not None:
            req = build_required_bag_options(product[0], product[1], product[2], desired_qty)
            required_bags = req["required"]
            best = best_usage_for_bag(bag[0], bag[1], required_bags)
            result = {
                "kind": "bag",
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
            if best is not None:
                render_res = run_bag_mode1_and_render(
                    product=product,
                    selected_bag=(bag[0], bag[1]),
                    desired_qty=desired_qty,
                    solutions=req["solutions"],
                    media_root=media_root or settings.MEDIA_ROOT,
                    draw_limit=desired_qty,
                )
                image_url = settings.MEDIA_URL + render_res.image_rel_path
                bag_box = _resolve_visual_bag_box((bag[0], bag[1]), render_res.inner_box)
                if bag_box:
                    length, width, height = bag_box
                else:
                    length, width, height = (
                        round(render_res.inner_box[0], 2),
                        round(render_res.inner_box[1], 2),
                        round(render_res.inner_box[2], 2),
                    )
                label = selected_material.part_number if selected_material else "Manual Bag"
                pending_result = {
                    "label": label,
                    "length": length,
                    "width": width,
                    "height": height,
                    "units_per_parent": desired_qty,
                    "total_base_units": desired_qty,
                }

    if mode == "optimal" and action in ("find_top5", "select_candidate"):
        if product_source == "catalogue" and not selected_product:
            messages.append("Please select a product from the product catalogue.")
        elif product_source == "manual" and (not product or None in product):
            messages.append("Please enter product dimensions.")
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
                    "material": m,
                    "bag_len": round(bag_len, 2),
                    "bag_w": round(bag_w, 2),
                    "usage": best["usage"],
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
                    if best is not None:
                        render_res = run_bag_mode1_and_render(
                            product=product,
                            selected_bag=(bag[0], bag[1]),
                            desired_qty=desired_qty,
                            solutions=req["solutions"],
                            media_root=media_root or settings.MEDIA_ROOT,
                            draw_limit=desired_qty,
                        )
                        image_url = settings.MEDIA_URL + render_res.image_rel_path
                        bag_box = _resolve_visual_bag_box((bag[0], bag[1]), render_res.inner_box)
                        if bag_box:
                            length, width, height = bag_box
                        else:
                            length, width, height = (
                                round(render_res.inner_box[0], 2),
                                round(render_res.inner_box[1], 2),
                                round(render_res.inner_box[2], 2),
                            )
                        pending_result = {
                            "label": selected_material.part_number,
                            "length": length,
                            "width": width,
                            "height": height,
                            "units_per_parent": desired_qty,
                            "total_base_units": desired_qty,
                        }

    return {
        "messages": messages,
        "result": result,
        "image_url": image_url,
        "top5": top5,
        "pending_result": pending_result,
    }
