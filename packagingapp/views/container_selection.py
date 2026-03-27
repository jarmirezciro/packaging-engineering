# packagingapp/views/container_selection.py
from django.conf import settings
from django.shortcuts import render
from ..models import PackagingCatalogue, PackagingMaterial
from ..forms import ContainerSelectionMode1Form
from ..utils.box_selection.engine import run_mode1_and_render, compute_max_quantity_only


def container_selection_mode1(request):
    result = None
    image_url = None

    materials = PackagingMaterial.objects.none()
    selected_material = None
    top5 = []

    # Build form
    if request.method == "POST":
        form = ContainerSelectionMode1Form(request.POST)
    else:
        form = ContainerSelectionMode1Form(initial={"mode": "single"})

    # Populate catalogue dropdown (always)
    catalogues = PackagingCatalogue.objects.all().order_by("name")
    form.fields["catalogue_id"].choices = [("", "— Select —")] + [(str(c.id), c.name) for c in catalogues]

    selected_catalogue_id = request.GET.get("catalogue_id") or ""
    selected_container_id = request.GET.get("container_id") or ""

    if request.method == "POST" and form.is_valid():
        mode = form.cleaned_data.get("mode") or "single"
        action = form.cleaned_data.get("action") or ""

        selected_catalogue_id = form.cleaned_data.get("catalogue_id") or request.POST.get("catalogue_id") or ""
        selected_container_id = form.cleaned_data.get("container_id") or request.POST.get("container_id") or ""

        # Load materials for chosen catalogue
        if selected_catalogue_id:
            materials = PackagingMaterial.objects.filter(catalogue_id=selected_catalogue_id).order_by("part_number")
        else:
            materials = PackagingMaterial.objects.none()

        product = (
            float(form.cleaned_data["product_l"]),
            float(form.cleaned_data["product_w"]),
            float(form.cleaned_data["product_h"]),
        )
        desired_qty = int(form.cleaned_data.get("desired_qty") or 1)

        r1 = 1 if form.cleaned_data.get("r1") else 0
        r2 = 1 if form.cleaned_data.get("r2") else 0
        r3 = 1 if form.cleaned_data.get("r3") else 0

        if r1 == 0 and r2 == 0 and r3 == 0:
            form.add_error(None, "Please enable at least one rotation option.")

        # MODE: SINGLE
        if mode == "single" and not form.errors:
            source = form.cleaned_data.get("container_source") or "manual"
            container = None

            if source == "manual":
                bl = form.cleaned_data.get("box_l")
                bw = form.cleaned_data.get("box_w")
                bh = form.cleaned_data.get("box_h")
                if bl is None or bw is None or bh is None:
                    form.add_error(None, "Please enter all manual container dimensions (L/W/H).")
                else:
                    container = (float(bl), float(bw), float(bh))
            else:
                if not selected_container_id:
                    form.add_error(None, "Please select a container from the table below.")
                else:
                    selected_material = PackagingMaterial.objects.get(id=selected_container_id)
                    container = (
                        float(selected_material.part_length),
                        float(selected_material.part_width),
                        float(selected_material.part_height),
                    )

            if not form.errors and container is not None:
                result = run_mode1_and_render(product, container, r1, r2, r3, settings.MEDIA_ROOT)
                image_url = settings.MEDIA_URL + result.image_rel_path

        # MODE: OPTIMAL
        if mode == "optimal" and not form.errors:
            if not selected_catalogue_id:
                form.add_error(None, "Please select a packaging catalogue.")
            else:
                product_vol = product[0] * product[1] * product[2]
                scored = []

                for m in materials:
                    container = (float(m.part_length), float(m.part_width), float(m.part_height))
                    max_qty = compute_max_quantity_only(product, container, r1, r2, r3)

                    if max_qty >= desired_qty:
                        container_vol = float(m.part_volume) if m.part_volume is not None else (container[0] * container[1] * container[2])
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
                    if not selected_container_id:
                        form.add_error(None, "Please select one of the Top 5 containers.")
                    else:
                        selected_material = PackagingMaterial.objects.get(id=selected_container_id)
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

    else:
        if selected_catalogue_id:
            materials = PackagingMaterial.objects.filter(catalogue_id=selected_catalogue_id).order_by("part_number")

    return render(request, "container_selection/container_selection_mode1.html", {
        "form": form,
        "result": result,
        "image_url": image_url,
        "materials": materials,
        "selected_material": selected_material,
        "top5": top5,
    })