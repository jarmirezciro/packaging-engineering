from django.conf import settings
from django.shortcuts import render
from ..models import PackagingCatalogue, PackagingMaterial
from ..forms import PalletizationForm
from ..utils.palletization.engine import run_palletization_analysis, render_selected_result


def palletization_mode1(request):
    materials = PackagingMaterial.objects.none()
    selected_material = None
    results_table = []
    selected_result = None
    result_image_url = None

    if request.method == "POST":
        form = PalletizationForm(request.POST)
    else:
        form = PalletizationForm(initial={
            "pallet_source": "manual",
            "max_width_stickout": 0,
            "max_length_stickout": 0,
        })

    catalogues = PackagingCatalogue.objects.all().order_by("name")
    form.fields["catalogue_id"].choices = [("", "— Select —")] + [
        (str(c.id), c.name) for c in catalogues
    ]

    selected_catalogue_id = request.POST.get("catalogue_id") or request.GET.get("catalogue_id") or ""
    selected_pallet_id = request.POST.get("pallet_id") or request.GET.get("pallet_id") or ""

    if selected_catalogue_id:
        materials = PackagingMaterial.objects.filter(
            catalogue_id=selected_catalogue_id,
            packaging_type="PALLET"
        ).order_by("part_number")

    if request.method == "POST":
        if form.is_valid():
            action = form.cleaned_data.get("action") or "run_analysis"
            source = form.cleaned_data.get("pallet_source") or "manual"

            selected_catalogue_id = form.cleaned_data.get("catalogue_id") or ""
            selected_pallet_id = form.cleaned_data.get("pallet_id") or ""

            if selected_catalogue_id:
                materials = PackagingMaterial.objects.filter(
                    catalogue_id=selected_catalogue_id,
                    packaging_type="PALLET"
                ).order_by("part_number")
            else:
                materials = PackagingMaterial.objects.none()

            # Box inputs
            box_l = float(form.cleaned_data["box_l"])
            box_w = float(form.cleaned_data["box_w"])
            box_h = float(form.cleaned_data["box_h"])
            box_weight = form.cleaned_data.get("box_weight")
            max_weight_on_bottom_box = form.cleaned_data.get("max_weight_on_bottom_box")

            if box_weight is not None:
                box_weight = float(box_weight)
            if max_weight_on_bottom_box is not None:
                max_weight_on_bottom_box = float(max_weight_on_bottom_box)

            # Constraints
            max_stack_height = float(form.cleaned_data["max_stack_height"])
            max_width_stickout = float(form.cleaned_data.get("max_width_stickout") or 0)
            max_length_stickout = float(form.cleaned_data.get("max_length_stickout") or 0)

            # Pallet source
            if source == "manual":
                pallet_l = float(form.cleaned_data["pallet_l"])
                pallet_w = float(form.cleaned_data["pallet_w"])
            else:
                selected_material = PackagingMaterial.objects.get(
                    id=selected_pallet_id,
                    packaging_type="PALLET"
                )
                pallet_l = float(selected_material.part_length)
                pallet_w = float(selected_material.part_width)

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

        else:
            # Keep catalogue table populated on invalid POST too
            if selected_catalogue_id:
                materials = PackagingMaterial.objects.filter(
                    catalogue_id=selected_catalogue_id,
                    packaging_type="PALLET"
                ).order_by("part_number")

    return render(request, "palletization/palletization_mode1.html", {
        "form": form,
        "materials": materials,
        "selected_material": selected_material,
        "results_table": results_table,
        "selected_result": selected_result,
        "result_image_url": result_image_url,
    })