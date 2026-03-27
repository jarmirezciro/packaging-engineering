# packagingapp/views/packaging_catalogue.py
from django import forms
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from ..models import PackagingCatalogue, PackagingMaterial
from ..forms import (
    PackagingMaterialFilterForm,
    PackagingMaterialForm,
    ExcelUploadForm,
    DrawingUploadForm,
)
from ..services.excel_import import import_packaging_excel
from ..services.drawing_import import import_drawings_zip


# -------------------------
# Forms (Catalogue)
# -------------------------
class PackagingCatalogueForm(forms.ModelForm):
    class Meta:
        model = PackagingCatalogue
        fields = ["name", "description"]


# -------------------------
# Catalogue Views
# -------------------------
def catalogue_list(request):
    catalogues = PackagingCatalogue.objects.all().order_by("-created_at")
    return render(request, "packaging_catalogue/catalogue_list.html", {"catalogues": catalogues})


def create_catalogue(request):
    if request.method == "POST":
        form = PackagingCatalogueForm(request.POST)
        if form.is_valid():
            catalogue = form.save()
            # keep your current behavior; you can redirect to detail or list
            return redirect("catalogue_detail", pk=catalogue.pk)
    else:
        form = PackagingCatalogueForm()

    return render(request, "packaging_catalogue/create_catalogue.html", {"form": form})


@require_POST
def delete_catalogue(request, pk):
    catalogue = get_object_or_404(PackagingCatalogue, pk=pk)
    catalogue.delete()
    return redirect("catalogue_list")


def catalogue_detail(request, pk):
    catalogue = get_object_or_404(PackagingCatalogue, pk=pk)
    materials = catalogue.materials.all()

    form = PackagingMaterialFilterForm(request.GET or None)
    if form.is_valid():
        cd = form.cleaned_data

        if cd.get("part_number"):
            materials = materials.filter(part_number__icontains=cd["part_number"])
        if cd.get("part_description"):
            materials = materials.filter(part_description__icontains=cd["part_description"])
        if cd.get("packaging_type"):
            materials = materials.filter(packaging_type__icontains=cd["packaging_type"])
        if cd.get("branding"):
            materials = materials.filter(branding__icontains=cd["branding"])

        if cd.get("min_length"):
            materials = materials.filter(part_length__gte=cd["min_length"])
        if cd.get("max_length"):
            materials = materials.filter(part_length__lte=cd["max_length"])
        if cd.get("min_width"):
            materials = materials.filter(part_width__gte=cd["min_width"])
        if cd.get("max_width"):
            materials = materials.filter(part_width__lte=cd["max_width"])
        if cd.get("min_height"):
            materials = materials.filter(part_height__gte=cd["min_height"])
        if cd.get("max_height"):
            materials = materials.filter(part_height__lte=cd["max_height"])

        if cd.get("min_volume"):
            materials = materials.filter(part_volume__gte=cd["min_volume"])
        if cd.get("max_volume"):
            materials = materials.filter(part_volume__lte=cd["max_volume"])

    paginator = Paginator(materials, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "packaging_catalogue/catalogue_detail.html",
        {"catalogue": catalogue, "form": form, "page_obj": page_obj},
    )


# -------------------------
# Materials
# -------------------------
def add_material(request, pk):
    catalogue = get_object_or_404(PackagingCatalogue, pk=pk)

    if request.method == "POST":
        form = PackagingMaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.catalogue = catalogue
            material.save()
            return redirect("catalogue_detail", pk=catalogue.pk)
    else:
        form = PackagingMaterialForm()

    return render(
        request,
        "packaging_catalogue/add_material.html",
        {"catalogue": catalogue, "form": form},
    )


# -------------------------
# Excel Upload
# -------------------------
def upload_excel(request, pk):
    catalogue = get_object_or_404(PackagingCatalogue, pk=pk)

    if request.method == "POST":
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                import_packaging_excel(request.FILES["file"], catalogue)
                return redirect("catalogue_detail", pk=catalogue.pk)
            except Exception as e:
                return render(
                    request,
                    "packaging_catalogue/upload_excel.html",
                    {"form": form, "catalogue": catalogue, "error": str(e)},
                )
    else:
        form = ExcelUploadForm()

    return render(request, "packaging_catalogue/upload_excel.html", {"form": form, "catalogue": catalogue})


# -------------------------
# Drawings ZIP Upload
# -------------------------
def upload_drawings_for_catalogue(request, pk):
    catalogue = get_object_or_404(PackagingCatalogue, pk=pk)

    if request.method == "POST":
        form = DrawingUploadForm(request.POST, request.FILES)
        if form.is_valid():
            imported, not_matched, skipped = import_drawings_zip(
                request.FILES["zip_file"],
                catalogue,
            )
            return render(
                request,
                "packaging_catalogue/upload_drawings.html",
                {
                    "form": DrawingUploadForm(),
                    "catalogue": catalogue,
                    "success": f"Done. Imported: {imported}. Not matched: {not_matched}. Skipped: {skipped}.",
                },
            )
    else:
        form = DrawingUploadForm()

    return render(request, "packaging_catalogue/upload_drawings.html", {"form": form, "catalogue": catalogue})