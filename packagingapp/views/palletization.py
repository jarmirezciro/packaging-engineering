from django.conf import settings
from django.shortcuts import render

from ..models import PackagingCatalogue, PackagingMaterial
from ..forms import PalletizationForm
from ..utils.palletization.engine import run_palletization_analysis, render_selected_result


def _dims_from_material(material, prefer_external=False):
    if prefer_external:
        l = material.external_length if material.external_length is not None else material.part_length
        w = material.external_width if material.external_width is not None else material.part_width
        h = material.external_height if material.external_height is not None else material.part_height
    else:
        l = material.part_length
        w = material.part_width
        h = material.part_height
    return float(l), float(w), float(h)


def palletization_mode1(request):
    results_table = []
    selected_result = None
    result_image_url = None

    box_materials = PackagingMaterial.objects.none()
    pallet_materials = PackagingMaterial.objects.none()

    selected_box_material = None
    selected_pallet_material = None

    if request.method == "POST":
        form = PalletizationForm(request.POST)
    else:
        form = PalletizationForm(initial={
            "box_source": "manual",
            "pallet_source": "manual",
            "max_width_stickout": 0,
            "max_length_stickout": 0,
        })

    packaging_catalogues = PackagingCatalogue.objects.all().order_by("name")

    form.fields["box_catalogue_id"].choices = [("", "— Select —")] + [
        (str(c.id), c.name) for c in packaging_catalogues
    ]
    form.fields["pallet_catalogue_id"].choices = [("", "— Select —")] + [
        (str(c.id), c.name) for c in packaging_catalogues
    ]

    raw_box_source = request.POST.get("box_source") or request.GET.get("box_source") or "manual"
    raw_pallet_source = request.POST.get("pallet_source") or request.GET.get("pallet_source") or "manual"

    raw_box_catalogue_id = request.POST.get("box_catalogue_id") or request.GET.get("box_catalogue_id") or ""
    raw_selected_box_id = request.POST.get("selected_box_id") or request.GET.get("selected_box_id") or ""

    raw_pallet_catalogue_id = request.POST.get("pallet_catalogue_id") or request.GET.get("pallet_catalogue_id") or ""
    raw_pallet_id = request.POST.get("pallet_id") or request.GET.get("pallet_id") or ""

    if raw_box_catalogue_id:
        box_materials = PackagingMaterial.objects.filter(
            catalogue_id=raw_box_catalogue_id,
            packaging_type__in=["BOX", "CRATE"]
        ).select_related("catalogue").order_by("part_number")

    if raw_pallet_catalogue_id:
        pallet_materials = PackagingMaterial.objects.filter(
            catalogue_id=raw_pallet_catalogue_id,
            packaging_type="PALLET"
        ).select_related("catalogue").order_by("part_number")

    if raw_selected_box_id:
        selected_box_material = PackagingMaterial.objects.filter(
            id=raw_selected_box_id,
            packaging_type__in=["BOX", "CRATE"]
        ).select_related("catalogue").first()

    if raw_pallet_id:
        selected_pallet_material = PackagingMaterial.objects.filter(
            id=raw_pallet_id,
            packaging_type="PALLET"
        ).select_related("catalogue").first()

    if request.method == "POST":
        action = request.POST.get("action") or "refresh"

        if action in ("run_analysis", "select_result"):
            if form.is_valid():
                current_box_source = form.cleaned_data.get("box_source") or "manual"
                current_pallet_source = form.cleaned_data.get("pallet_source") or "manual"

                raw_box_catalogue_id = form.cleaned_data.get("box_catalogue_id") or raw_box_catalogue_id
                raw_selected_box_id = form.cleaned_data.get("selected_box_id") or raw_selected_box_id
                raw_pallet_catalogue_id = form.cleaned_data.get("pallet_catalogue_id") or raw_pallet_catalogue_id
                raw_pallet_id = form.cleaned_data.get("pallet_id") or raw_pallet_id

                if raw_box_catalogue_id:
                    box_materials = PackagingMaterial.objects.filter(
                        catalogue_id=raw_box_catalogue_id,
                        packaging_type__in=["BOX", "CRATE"]
                    ).select_related("catalogue").order_by("part_number")
                else:
                    box_materials = PackagingMaterial.objects.none()

                if raw_pallet_catalogue_id:
                    pallet_materials = PackagingMaterial.objects.filter(
                        catalogue_id=raw_pallet_catalogue_id,
                        packaging_type="PALLET"
                    ).select_related("catalogue").order_by("part_number")
                else:
                    pallet_materials = PackagingMaterial.objects.none()

                selected_box_material = (
                    PackagingMaterial.objects.filter(
                        id=raw_selected_box_id,
                        packaging_type__in=["BOX", "CRATE"]
                    ).select_related("catalogue").first()
                    if raw_selected_box_id else None
                )

                selected_pallet_material = (
                    PackagingMaterial.objects.filter(
                        id=raw_pallet_id,
                        packaging_type="PALLET"
                    ).select_related("catalogue").first()
                    if raw_pallet_id else None
                )

                if current_box_source == "catalogue":
                    box_l, box_w, box_h = _dims_from_material(selected_box_material, prefer_external=True)
                    box_weight = (
                        float(selected_box_material.part_weight)
                        if selected_box_material and selected_box_material.part_weight is not None
                        else None
                    )
                    manual_box_weight = form.cleaned_data.get("box_weight")
                    if manual_box_weight is not None:
                        box_weight = float(manual_box_weight)
                else:
                    box_l = float(form.cleaned_data["box_l"])
                    box_w = float(form.cleaned_data["box_w"])
                    box_h = float(form.cleaned_data["box_h"])
                    box_weight = form.cleaned_data.get("box_weight")
                    if box_weight is not None:
                        box_weight = float(box_weight)

                if current_pallet_source == "catalogue":
                    pallet_l, pallet_w, _ = _dims_from_material(selected_pallet_material, prefer_external=True)
                else:
                    pallet_l = float(form.cleaned_data["pallet_l"])
                    pallet_w = float(form.cleaned_data["pallet_w"])

                max_weight_on_bottom_box = form.cleaned_data.get("max_weight_on_bottom_box")
                if max_weight_on_bottom_box is not None:
                    max_weight_on_bottom_box = float(max_weight_on_bottom_box)

                max_stack_height = float(form.cleaned_data["max_stack_height"])
                max_width_stickout = float(form.cleaned_data.get("max_width_stickout") or 0)
                max_length_stickout = float(form.cleaned_data.get("max_length_stickout") or 0)

                results_table = run_palletization_analysis(
                    box_l=box_l,
                    box_w=box_w,
                    box_h=box_h,
                    pallet_l=pallet_l,
                    pallet_w=pallet_w,
                    max_stack_height=max_stack_height,
                    max_width_stickout=max_width_stickout,
                    max_length_stickout=max_length_stickout,
                    box_weight=box_weight,
                    max_weight_on_bottom_box=max_weight_on_bottom_box,
                )

                selected_result_key = request.POST.get("selected_result_key") or ""

                if results_table:
                    if action == "select_result" and selected_result_key:
                        for row in results_table:
                            row_key = f'{row["pattern"]}__{row["stacking"]}'
                            if row_key == selected_result_key:
                                selected_result = row
                                break

                    if selected_result is None:
                        selected_result = results_table[0]

                    render_res = render_selected_result(
                        selected_result=selected_result,
                        pallet_l=pallet_l,
                        pallet_w=pallet_w,
                        max_stack_height=max_stack_height,
                        media_root=settings.MEDIA_ROOT,
                    )
                    result_image_url = settings.MEDIA_URL + render_res.image_rel_path

    return render(request, "palletization/palletization_mode1.html", {
        "form": form,
        "box_materials": box_materials,
        "pallet_materials": pallet_materials,
        "selected_box_material": selected_box_material,
        "selected_pallet_material": selected_pallet_material,
        "results_table": results_table,
        "selected_result": selected_result,
        "result_image_url": result_image_url,
        "current_box_source": raw_box_source,
        "current_pallet_source": raw_pallet_source,
    })