from django.shortcuts import render  # ✅ FIX: this was missing
from django.conf import settings

from ..models import PackagingCatalogue, PackagingMaterial
from ..forms import BagSelectionForm
from ..utils.bag_selection.engine import (
    build_required_bag_options,
    best_usage_for_bag,
    run_bag_mode1_and_render,
)


def bag_selection_mode1(request):
    result = None
    image_url = None

    materials = PackagingMaterial.objects.none()
    selected_material = None
    top5 = []

    if request.method == "POST":
        form = BagSelectionForm(request.POST)
    else:
        form = BagSelectionForm(initial={"mode": "single"})

    # Populate catalogue dropdown
    catalogues = PackagingCatalogue.objects.all().order_by("name")
    form.fields["catalogue_id"].choices = [("", "— Select —")] + [(str(c.id), c.name) for c in catalogues]

    selected_catalogue_id = request.GET.get("catalogue_id") or ""
    selected_bag_id = request.GET.get("bag_id") or ""

    # Load BAG materials if catalogue already selected (GET)
    if request.method == "GET" and selected_catalogue_id:
        materials = (
            PackagingMaterial.objects
            .filter(catalogue_id=selected_catalogue_id, packaging_type="BAG")
            .order_by("part_number")
        )

    if request.method == "POST" and form.is_valid():
        mode = form.cleaned_data.get("mode") or "single"
        action = form.cleaned_data.get("action") or ""

        selected_catalogue_id = form.cleaned_data.get("catalogue_id") or ""
        selected_bag_id = form.cleaned_data.get("bag_id") or ""

        # Load BAG materials for selected catalogue (POST)
        if selected_catalogue_id:
            materials = (
                PackagingMaterial.objects
                .filter(catalogue_id=selected_catalogue_id, packaging_type="BAG")
                .order_by("part_number")
            )
        else:
            materials = PackagingMaterial.objects.none()

        product = (
            float(form.cleaned_data["product_l"]),
            float(form.cleaned_data["product_w"]),
            float(form.cleaned_data["product_h"]),
        )
        desired_qty = int(form.cleaned_data.get("desired_qty") or 1)

        # Engine required options
        req = build_required_bag_options(product[0], product[1], product[2], desired_qty)
        required_bags = req["required"]

        # -------------------------
        # SINGLE MODE
        # -------------------------
        if mode == "single":
            source = form.cleaned_data.get("bag_source") or "manual"
            bag = None  # (len, width)

            if source == "manual":
                bl = form.cleaned_data.get("bag_length")
                bw = form.cleaned_data.get("bag_width")
                if bl is None or bw is None:
                    form.add_error(None, "Please enter manual bag length and width.")
                else:
                    bag = (float(bl), float(bw))
            else:
                if not selected_bag_id:
                    form.add_error(None, "Please select a bag from the table below.")
                else:
                    selected_material = PackagingMaterial.objects.get(id=selected_bag_id)
                    # BAG mapping rule:
                    # Length = part_length, Width = part_height (ignore part_width)
                    bag = (float(selected_material.part_length), float(selected_material.part_width))

            if not form.errors and bag is not None:
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

                # 3D render if fits
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


        # -------------------------
        # OPTIMAL MODE
        # -------------------------
        if mode == "optimal":
            if not selected_catalogue_id:
                form.add_error(None, "Please select a packaging catalogue.")
            else:
                # Build Top 5 list (Length=part_length, Width=part_width)
                scored = []
                for m in materials:
                    bag_len = float(m.part_length or 0)
                    bag_w = float(m.part_width or 0)

                    # skip invalid
                    if bag_len <= 0 or bag_w <= 0:
                        continue

                    best = best_usage_for_bag(bag_len, bag_w, required_bags)
                    if best is not None:
                        scored.append({
                            "material": m,
                            "bag_len": bag_len,
                            "bag_w": bag_w,
                            "usage": best["usage"],
                            "best_required": (best["req_len"], best["req_w"]),
                            "bag_area": best["bag_area"],
                        })

                # Sort: highest usage first, then smaller bag area
                scored.sort(key=lambda x: (-x["usage"], x["bag_area"]))
                top5 = scored[:5]

                # When user selects one of the Top 5 candidates
                if action == "select_candidate":
                    if not selected_bag_id:
                        form.add_error(None, "Please select one of the Top 5 bags.")
                    else:
                        selected_material = PackagingMaterial.objects.get(id=selected_bag_id)

                        bag_len = float(selected_material.part_length or 0)
                        bag_w = float(selected_material.part_width or 0)

                        best = best_usage_for_bag(bag_len, bag_w, required_bags)
                        result = {
                            "desired_qty": desired_qty,
                            "smooth_qty": req["smooth_qty"],
                            "fits": best is not None,
                            "bag_len": bag_len,
                            "bag_w": bag_w,
                            "best_required": (best["req_len"], best["req_w"]) if best else None,
                            "usage": best["usage"] if best else 0.0,
                            "required_bags": required_bags,
                        }

                        if best is not None:
                            render_res = run_bag_mode1_and_render(
                                product=product,
                                selected_bag=(bag_len, bag_w),
                                desired_qty=desired_qty,
                                solutions=req["solutions"],
                                media_root=settings.MEDIA_ROOT,
                                draw_limit=desired_qty,
                            )
                            image_url = settings.MEDIA_URL + render_res.image_rel_path

    return render(request, "bag_selection/bag_selection_mode1.html", {
        "form": form,
        "result": result,
        "image_url": image_url,
        "materials": materials,
        "selected_material": selected_material,
        "top5": top5,
    })