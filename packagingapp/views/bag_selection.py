from django.conf import settings
from django.shortcuts import render

from ..models import (
    PackagingCatalogue,
    PackagingMaterial,
    ProductCatalogue,
    Product,
)
from ..forms import BagSelectionForm
from ..utils.bag_selection.engine import (
    build_required_bag_options,
    best_usage_for_bag,
    run_bag_mode1_and_render,
)


def bag_selection_mode1(request):
    result = None
    image_url = None
    top5 = []

    materials = PackagingMaterial.objects.none()
    products = Product.objects.none()

    selected_material = None
    selected_product = None

    if request.method == "POST":
        form = BagSelectionForm(request.POST)
    else:
        form = BagSelectionForm(initial={
            "mode": "single",
            "product_source": "manual",
            "bag_source": "manual",
        })

    # Populate dropdowns
    packaging_catalogues = PackagingCatalogue.objects.all().order_by("name")
    product_catalogues = ProductCatalogue.objects.all().order_by("name")

    form.fields["catalogue_id"].choices = [("", "— Select —")] + [
        (str(c.id), c.name) for c in packaging_catalogues
    ]
    form.fields["product_catalogue_id"].choices = [("", "— Select —")] + [
        (str(c.id), c.name) for c in product_catalogues
    ]

    raw_mode = request.POST.get("mode") or request.GET.get("mode") or "single"
    raw_product_source = request.POST.get("product_source") or request.GET.get("product_source") or "manual"
    raw_bag_source = request.POST.get("bag_source") or request.GET.get("bag_source") or "manual"

    raw_product_catalogue_id = request.POST.get("product_catalogue_id") or request.GET.get("product_catalogue_id") or ""
    raw_selected_product_id = request.POST.get("selected_product_id") or request.GET.get("selected_product_id") or ""

    raw_catalogue_id = request.POST.get("catalogue_id") or request.GET.get("catalogue_id") or ""
    raw_bag_id = request.POST.get("bag_id") or request.GET.get("bag_id") or ""

    if raw_product_catalogue_id:
        products = Product.objects.filter(
            catalogue_id=raw_product_catalogue_id
        ).select_related("catalogue").order_by("-created_at")

    if raw_catalogue_id:
        materials = PackagingMaterial.objects.filter(
            catalogue_id=raw_catalogue_id,
            packaging_type="BAG",
        ).select_related("catalogue").order_by("part_number")

    if raw_selected_product_id:
        selected_product = Product.objects.filter(id=raw_selected_product_id).select_related("catalogue").first()

    if raw_bag_id:
        selected_material = PackagingMaterial.objects.filter(id=raw_bag_id).select_related("catalogue").first()

    if request.method == "POST" and form.is_valid():
        mode = form.cleaned_data.get("mode") or "single"
        action = form.cleaned_data.get("action") or ""

        product_source = form.cleaned_data.get("product_source") or "manual"
        bag_source = form.cleaned_data.get("bag_source") or "manual"

        selected_product_catalogue_id = form.cleaned_data.get("product_catalogue_id") or raw_product_catalogue_id
        selected_product_id = form.cleaned_data.get("selected_product_id") or raw_selected_product_id

        selected_catalogue_id = form.cleaned_data.get("catalogue_id") or raw_catalogue_id
        selected_bag_id = form.cleaned_data.get("bag_id") or raw_bag_id

        if selected_product_catalogue_id:
            products = Product.objects.filter(
                catalogue_id=selected_product_catalogue_id
            ).select_related("catalogue").order_by("-created_at")
        else:
            products = Product.objects.none()

        if selected_catalogue_id:
            materials = PackagingMaterial.objects.filter(
                catalogue_id=selected_catalogue_id,
                packaging_type="BAG",
            ).select_related("catalogue").order_by("part_number")
        else:
            materials = PackagingMaterial.objects.none()

        selected_product = (
            Product.objects.filter(id=selected_product_id).select_related("catalogue").first()
            if selected_product_id else None
        )

        selected_material = (
            PackagingMaterial.objects.filter(id=selected_bag_id).select_related("catalogue").first()
            if selected_bag_id else None
        )

        # Resolve product
        product = None

        if product_source == "catalogue":
            if selected_product:
                product = (
                    float(selected_product.product_length),
                    float(selected_product.product_width),
                    float(selected_product.product_height),
                )
            else:
                product = None
        else:
            if (
                form.cleaned_data.get("product_l") is not None
                and form.cleaned_data.get("product_w") is not None
                and form.cleaned_data.get("product_h") is not None
            ):
                product = (
                    float(form.cleaned_data["product_l"]),
                    float(form.cleaned_data["product_w"]),
                    float(form.cleaned_data["product_h"]),
                )

        desired_qty = int(form.cleaned_data.get("desired_qty") or 1)
        if product_source == "catalogue" and selected_product and mode == "optimal":
            desired_qty = int(selected_product.desired_qty or 1)

        # ---------- SINGLE MODE ----------
        if mode == "single" and not form.errors:
            should_run_single = action in ("run_single", "select_bag")

            if should_run_single:
                bag = None

                if product_source == "catalogue" and not selected_product:
                    form.add_error(None, "Please select a product from the product catalogue.")
                elif product_source == "manual" and product is None:
                    form.add_error(None, "Please enter product dimensions.")

                if not form.errors:
                    if bag_source == "manual":
                        bag_l = form.cleaned_data.get("bag_length")
                        bag_w = form.cleaned_data.get("bag_width")
                        if bag_l is None or bag_w is None:
                            form.add_error(None, "Please enter bag length and width.")
                        else:
                            bag = (float(bag_l), float(bag_w))
                    else:
                        if not selected_material:
                            form.add_error(None, "Please select a bag from the packaging catalogue.")
                        else:
                            bag = (
                                float(selected_material.part_length),
                                float(selected_material.part_width),
                            )

                if not form.errors and bag is not None and product is not None:
                    req = build_required_bag_options(product[0], product[1], product[2], desired_qty)
                    required_bags = req["required"]

                    best = best_usage_for_bag(bag[0], bag[1], required_bags)

                    result = {
                        "desired_qty": desired_qty,
                        "smooth_qty": req["smooth_qty"],
                        "fits": best is not None,
                        "bag_len": bag[0],
                        "bag_w": bag[1],
                        "best_required": (best["req_len"], best["req_w"]) if best else None,
                        "usage": best["usage"] if best else 0.0,
                        "required_bags": required_bags,
                    }

                    if best is not None:
                        render_res = run_bag_mode1_and_render(
                            product=product,
                            selected_bag=(bag[0], bag[1]),
                            desired_qty=desired_qty,
                            solutions=req["solutions"],
                            media_root=settings.MEDIA_ROOT,
                            draw_limit=desired_qty,
                        )
                        image_url = settings.MEDIA_URL + render_res.image_rel_path

        # ---------- OPTIMAL MODE ----------
        if mode == "optimal" and not form.errors:
            if action in ("find_top5", "select_candidate"):
                if product_source == "catalogue" and not selected_product:
                    form.add_error(None, "Please select a product from the product catalogue.")
                elif product_source == "manual" and product is None:
                    form.add_error(None, "Please enter product dimensions.")
                elif not selected_catalogue_id:
                    form.add_error(None, "Please select a packaging catalogue.")

                if not form.errors:
                    req = build_required_bag_options(product[0], product[1], product[2], desired_qty)
                    required_bags = req["required"]
                    scored = []

                    for m in materials:
                        bag_len = float(m.part_length or 0)
                        bag_w = float(m.part_width or 0)

                        if bag_len <= 0 or bag_w <= 0:
                            continue

                        best = best_usage_for_bag(bag_len, bag_w, required_bags)
                        if best is not None:
                            bag_area = bag_len * bag_w
                            scored.append({
                                "material": m,
                                "bag_len": bag_len,
                                "bag_w": bag_w,
                                "usage": best["usage"],
                                "best_required": (best["req_len"], best["req_w"]),
                                "bag_area": bag_area,
                            })

                    scored.sort(key=lambda x: (-x["usage"], x["bag_area"]))
                    top5 = scored[:5]

                    if action == "select_candidate":
                        if not selected_material:
                            form.add_error(None, "Please select one of the Top 5 candidates.")
                        else:
                            bag = (
                                float(selected_material.part_length),
                                float(selected_material.part_width),
                            )

                            best = best_usage_for_bag(bag[0], bag[1], required_bags)

                            result = {
                                "desired_qty": desired_qty,
                                "smooth_qty": req["smooth_qty"],
                                "fits": best is not None,
                                "bag_len": bag[0],
                                "bag_w": bag[1],
                                "best_required": (best["req_len"], best["req_w"]) if best else None,
                                "usage": best["usage"] if best else 0.0,
                                "required_bags": required_bags,
                            }

                            if best is not None:
                                render_res = run_bag_mode1_and_render(
                                    product=product,
                                    selected_bag=(bag[0], bag[1]),
                                    desired_qty=desired_qty,
                                    solutions=req["solutions"],
                                    media_root=settings.MEDIA_ROOT,
                                    draw_limit=desired_qty,
                                )
                                image_url = settings.MEDIA_URL + render_res.image_rel_path

    context = {
        "form": form,
        "result": result,
        "image_url": image_url,
        "top5": top5,
        "materials": materials,
        "products": products,
        "selected_material": selected_material,
        "selected_product": selected_product,
        "current_mode": raw_mode,
        "current_product_source": raw_product_source,
        "current_bag_source": raw_bag_source,
    }
    return render(request, "bag_selection/bag_selection_mode1.html", context)