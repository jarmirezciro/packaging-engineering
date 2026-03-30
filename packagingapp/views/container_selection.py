from django.conf import settings
from django.shortcuts import render

from ..models import (
    PackagingCatalogue,
    PackagingMaterial,
    ProductCatalogue,
    Product,
)
from ..forms import ContainerSelectionMode1Form
from ..utils.box_selection.engine import run_mode1_and_render, compute_max_quantity_only


def container_selection_mode1(request):
    result = None
    image_url = None
    top5 = []

    materials = PackagingMaterial.objects.none()
    products = Product.objects.none()

    selected_material = None
    selected_product = None

    if request.method == "POST":
        form = ContainerSelectionMode1Form(request.POST)
    else:
        form = ContainerSelectionMode1Form(initial={
            "mode": "single",
            "product_source": "manual",
            "container_source": "manual",
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
    raw_container_source = request.POST.get("container_source") or request.GET.get("container_source") or "manual"

    raw_product_catalogue_id = request.POST.get("product_catalogue_id") or request.GET.get("product_catalogue_id") or ""
    raw_selected_product_id = request.POST.get("selected_product_id") or request.GET.get("selected_product_id") or ""

    raw_catalogue_id = request.POST.get("catalogue_id") or request.GET.get("catalogue_id") or ""
    raw_container_id = request.POST.get("container_id") or request.GET.get("container_id") or ""

    if raw_product_catalogue_id:
        products = Product.objects.filter(
            catalogue_id=raw_product_catalogue_id
        ).select_related("catalogue").order_by("-created_at")

    if raw_catalogue_id:
        materials = PackagingMaterial.objects.filter(
            catalogue_id=raw_catalogue_id
        ).select_related("catalogue").order_by("part_number")

    if raw_selected_product_id:
        selected_product = Product.objects.filter(id=raw_selected_product_id).select_related("catalogue").first()

    if raw_container_id:
        selected_material = PackagingMaterial.objects.filter(id=raw_container_id).select_related("catalogue").first()

    if request.method == "POST" and form.is_valid():
        mode = form.cleaned_data.get("mode") or "single"
        action = form.cleaned_data.get("action") or ""

        product_source = form.cleaned_data.get("product_source") or "manual"
        container_source = form.cleaned_data.get("container_source") or "manual"

        selected_product_catalogue_id = form.cleaned_data.get("product_catalogue_id") or raw_product_catalogue_id
        selected_product_id = form.cleaned_data.get("selected_product_id") or raw_selected_product_id

        selected_catalogue_id = form.cleaned_data.get("catalogue_id") or raw_catalogue_id
        selected_container_id = form.cleaned_data.get("container_id") or raw_container_id

        if selected_product_catalogue_id:
            products = Product.objects.filter(
                catalogue_id=selected_product_catalogue_id
            ).select_related("catalogue").order_by("-created_at")
        else:
            products = Product.objects.none()

        if selected_catalogue_id:
            materials = PackagingMaterial.objects.filter(
                catalogue_id=selected_catalogue_id
            ).select_related("catalogue").order_by("part_number")
        else:
            materials = PackagingMaterial.objects.none()

        selected_product = (
            Product.objects.filter(id=selected_product_id).select_related("catalogue").first()
            if selected_product_id else None
        )

        selected_material = (
            PackagingMaterial.objects.filter(id=selected_container_id).select_related("catalogue").first()
            if selected_container_id else None
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
                r1 = 1 if selected_product.rotation_1 else 0
                r2 = 1 if selected_product.rotation_2 else 0
                r3 = 1 if selected_product.rotation_3 else 0
            else:
                r1 = 1 if form.cleaned_data.get("r1") else 0
                r2 = 1 if form.cleaned_data.get("r2") else 0
                r3 = 1 if form.cleaned_data.get("r3") else 0
        else:
            r1 = 1 if form.cleaned_data.get("r1") else 0
            r2 = 1 if form.cleaned_data.get("r2") else 0
            r3 = 1 if form.cleaned_data.get("r3") else 0

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

        if r1 == 0 and r2 == 0 and r3 == 0:
            form.add_error(None, "Please enable at least one rotation option.")

        desired_qty = int(form.cleaned_data.get("desired_qty") or 1)
        if product_source == "catalogue" and selected_product and mode == "optimal":
            desired_qty = int(selected_product.desired_qty or 1)

        # ---------- SINGLE MODE ----------
        if mode == "single" and not form.errors:
            should_run_single = action in ("run_single", "select_container")

            if should_run_single:
                container = None

                if product_source == "catalogue" and not selected_product:
                    form.add_error(None, "Please select a product from the product catalogue.")
                elif product_source == "manual" and product is None:
                    form.add_error(None, "Please enter product dimensions.")

                if not form.errors:
                    if container_source == "manual":
                        bl = form.cleaned_data.get("box_l")
                        bw = form.cleaned_data.get("box_w")
                        bh = form.cleaned_data.get("box_h")
                        if bl is None or bw is None or bh is None:
                            form.add_error(None, "Please enter all manual container dimensions (L/W/H).")
                        else:
                            container = (float(bl), float(bw), float(bh))
                    else:
                        if not selected_material:
                            form.add_error(None, "Please select a packaging item from the catalogue table.")
                        else:
                            container = (
                                float(selected_material.part_length),
                                float(selected_material.part_width),
                                float(selected_material.part_height),
                            )

                if not form.errors and container is not None and product is not None:
                    result = run_mode1_and_render(
                        product,
                        container,
                        r1, r2, r3,
                        settings.MEDIA_ROOT
                    )
                    image_url = settings.MEDIA_URL + result.image_rel_path

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
                    product_vol = product[0] * product[1] * product[2]
                    scored = []

                    for m in materials:
                        container = (
                            float(m.part_length),
                            float(m.part_width),
                            float(m.part_height),
                        )
                        max_qty = compute_max_quantity_only(product, container, r1, r2, r3)

                        if max_qty >= desired_qty:
                            container_vol = (
                                float(m.part_volume)
                                if m.part_volume is not None
                                else (container[0] * container[1] * container[2])
                            )
                            usage = (desired_qty * product_vol) / container_vol if container_vol > 0 else 0.0

                            scored.append({
                                "material": m,
                                "max_qty": max_qty,
                                "usage": usage,
                                "container_vol": container_vol,
                            })

                    scored.sort(key=lambda x: (-x["usage"], x["container_vol"]))
                    top5 = scored[:5]

                    if action == "select_candidate":
                        if not selected_material:
                            form.add_error(None, "Please select one of the Top 5 containers.")
                        else:
                            container = (
                                float(selected_material.part_length),
                                float(selected_material.part_width),
                                float(selected_material.part_height),
                            )
                            result = run_mode1_and_render(
                                product,
                                container,
                                r1, r2, r3,
                                settings.MEDIA_ROOT,
                                draw_limit=desired_qty,
                            )
                            image_url = settings.MEDIA_URL + result.image_rel_path

    current_mode = request.POST.get("mode") or request.GET.get("mode") or form.initial.get("mode", "single")
    current_product_source = request.POST.get("product_source") or request.GET.get("product_source") or form.initial.get("product_source", "manual")
    current_container_source = request.POST.get("container_source") or request.GET.get("container_source") or form.initial.get("container_source", "manual")

    context = {
        "form": form,
        "result": result,
        "image_url": image_url,
        "products": products,
        "materials": materials,
        "selected_product": selected_product,
        "selected_material": selected_material,
        "top5": top5,
        "current_mode": current_mode,
        "current_product_source": current_product_source,
        "current_container_source": current_container_source,
    }
    return render(request, "container_selection/container_selection_mode1.html", context)