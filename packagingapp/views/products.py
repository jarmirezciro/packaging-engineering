from io import BytesIO
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from openpyxl import Workbook
from django.views.decorators.http import require_POST

from packagingapp.access import (
    can_manage_product_catalogue,
    get_manageable_product_catalogue_or_404,
    get_visible_product_catalogue_or_404,
    user_can_administer_catalogues,
    visible_product_catalogues,
)
from packagingapp.entitlements import PRIVATE_CATALOGUES, feature_required
from packagingapp.forms import (
    ProductCatalogueForm,
    ProductForm,
    ProductExcelUploadForm,
    ProductImagesZipUploadForm,
    ProductFilterForm,
)
from packagingapp.models import Product
from packagingapp.services.catalogue_media import CatalogueMediaError, catalogue_storage_summary
from packagingapp.services.product_excel_import import import_product_excel
from packagingapp.services.product_image_import import import_product_images_zip
from packagingapp.catalogue_units import (
    catalogue_display_selectors,
    catalogue_unit_selectors,
    catalogue_units_from_request,
    convert_catalogue_filter,
    remember_catalogue_units,
    format_catalogue_value,
)


def product_catalogues(request):
    catalogues = list(visible_product_catalogues(request.user).order_by("is_public", "-created_at"))
    for catalogue in catalogues:
        catalogue.can_manage_by_user = can_manage_product_catalogue(request.user, catalogue)
    return render(
        request,
        "product_catalogue/catalogues.html",
        {
            "catalogues": catalogues,
            "can_administer_catalogues": user_can_administer_catalogues(request.user),
        },
    )


@feature_required(PRIVATE_CATALOGUES, "catalogues", redirect_to_pricing=True)
@login_required
def create_product_catalogue(request):
    can_administer_catalogues = user_can_administer_catalogues(request.user)

    if request.method == "POST":
        form = ProductCatalogueForm(
            request.POST,
            request.FILES,
            user=request.user,
            allow_public_management=can_administer_catalogues,
        )
        if form.is_valid():
            catalogue = form.save(commit=False)

            if not can_administer_catalogues:
                catalogue.owner = request.user
                catalogue.is_public = False
            elif not catalogue.is_public and catalogue.owner_id is None:
                catalogue.owner = request.user

            catalogue.save()
            messages.success(request, "Product catalogue created successfully.")
            return redirect("product_catalogue_detail", catalogue_id=catalogue.pk)
    else:
        form = ProductCatalogueForm(user=request.user, allow_public_management=can_administer_catalogues)

    return render(
        request,
        "product_catalogue/create_catalogue.html",
        {
            "form": form,
            "can_administer_catalogues": can_administer_catalogues,
        },
    )


@feature_required(PRIVATE_CATALOGUES, "catalogues", redirect_to_pricing=True)
@login_required
def edit_product_catalogue(request, catalogue_id):
    catalogue = get_manageable_product_catalogue_or_404(request.user, pk=catalogue_id)
    can_administer_catalogues = user_can_administer_catalogues(request.user)

    if request.method == "POST":
        form = ProductCatalogueForm(
            request.POST,
            request.FILES,
            instance=catalogue,
            user=request.user,
            allow_public_management=can_administer_catalogues,
        )
        if form.is_valid():
            updated = form.save(commit=False)

            if not can_administer_catalogues:
                updated.owner = catalogue.owner
                updated.is_public = catalogue.is_public
            elif not updated.is_public and updated.owner_id is None:
                updated.owner = request.user

            updated.save()
            messages.success(request, "Product catalogue updated successfully.")
            return redirect("product_catalogue_detail", catalogue_id=catalogue.pk)
    else:
        form = ProductCatalogueForm(
            instance=catalogue,
            user=request.user,
            allow_public_management=can_administer_catalogues,
        )

    return render(
        request,
        "product_catalogue/edit_catalogue.html",
        {
            "catalogue": catalogue,
            "form": form,
            "can_administer_catalogues": can_administer_catalogues,
        },
    )


@feature_required(PRIVATE_CATALOGUES, "catalogues", redirect_to_pricing=True)
@login_required
def delete_product_catalogue(request, catalogue_id):
    catalogue = get_manageable_product_catalogue_or_404(request.user, pk=catalogue_id)
    if request.method == "POST":
        catalogue.delete()
        messages.success(request, "Product catalogue deleted successfully.")
        return redirect("product_catalogues")
    return redirect("product_catalogues")



def product_catalogue_detail(request, catalogue_id):
    catalogue = get_visible_product_catalogue_or_404(request.user, pk=catalogue_id)
    catalogue_units, unit_error = catalogue_units_from_request(request)
    if unit_error:
        return unit_error
    products = catalogue.products.all().order_by("product_id")

    form = ProductFilterForm(
        request.GET or None,
        initial={
            "catalogue_length_unit": catalogue_units["length"],
            "catalogue_mass_unit": catalogue_units["mass"],
        },
    )

    if form.is_valid():
        cd = form.cleaned_data

        if cd.get("product_id"):
            products = products.filter(product_id__icontains=cd["product_id"])

        if cd.get("product_name"):
            products = products.filter(product_name__icontains=cd["product_name"])

        length_unit = cd.get("catalogue_length_unit") or catalogue_units["length"]
        mass_unit = cd.get("catalogue_mass_unit") or catalogue_units["mass"]

        for field_name, lookup, model_field in (
            ("min_length", "gte", "product_length"),
            ("max_length", "lte", "product_length"),
            ("min_width", "gte", "product_width"),
            ("max_width", "lte", "product_width"),
            ("min_height", "gte", "product_height"),
            ("max_height", "lte", "product_height"),
        ):
            if cd.get(field_name) is not None:
                products = products.filter(**{
                    f"{model_field}__{lookup}": convert_catalogue_filter(
                        cd[field_name], quantity="length", display_unit=length_unit
                    )
                })

        for field_name, lookup in (("min_weight", "gte"), ("max_weight", "lte")):
            if cd.get(field_name) is not None:
                products = products.filter(**{
                    f"weight__{lookup}": convert_catalogue_filter(
                        cd[field_name], quantity="mass", display_unit=mass_unit
                    )
                })

        if cd.get("min_desired_qty"):
            products = products.filter(desired_qty__gte=cd["min_desired_qty"])
        if cd.get("max_desired_qty"):
            products = products.filter(desired_qty__lte=cd["max_desired_qty"])

        if cd.get("min_volume"):
            products = products.filter(product_volume__gte=cd["min_volume"])
        if cd.get("max_volume"):
            products = products.filter(product_volume__lte=cd["max_volume"])

    paginator = Paginator(products, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    for product in page_obj.object_list:
        product.catalogue_display_length = format_catalogue_value(
            product.product_length, quantity="length", display_unit=catalogue_units["length"]
        )
        product.catalogue_display_width = format_catalogue_value(
            product.product_width, quantity="length", display_unit=catalogue_units["length"]
        )
        product.catalogue_display_height = format_catalogue_value(
            product.product_height, quantity="length", display_unit=catalogue_units["length"]
        )
        product.catalogue_display_weight = format_catalogue_value(
            product.weight, quantity="mass", display_unit=catalogue_units["mass"]
        )
    can_manage = can_manage_product_catalogue(request.user, catalogue)

    return render(
        request,
        "product_catalogue/catalogue_detail.html",
        {
            "catalogue": catalogue,
            "form": form,
            "page_obj": page_obj,
            "can_manage_catalogue": can_manage,
            "is_read_only_private_catalogue": bool(
                not catalogue.is_public
                and getattr(request.user, "is_authenticated", False)
                and catalogue.owner_id == request.user.id
                and not can_manage
            ),
            "catalogue_storage": catalogue_storage_summary(request.user) if can_manage else None,
            "catalogue_length_unit": catalogue_units["length"],
            "catalogue_mass_unit": catalogue_units["mass"],
            "catalogue_display_selectors": catalogue_display_selectors(
                length_unit=catalogue_units["length"], mass_unit=catalogue_units["mass"]
            ),
        },
    )


@feature_required(PRIVATE_CATALOGUES, "catalogues", redirect_to_pricing=True)
@login_required
def add_product(request, catalogue_id):
    catalogue = get_manageable_product_catalogue_or_404(request.user, pk=catalogue_id)
    catalogue_units, unit_error = catalogue_units_from_request(request)
    if unit_error:
        return unit_error

    if request.method == "POST":
        form = ProductForm(
            request.POST,
            request.FILES,
            user=request.user,
            catalogue_length_unit=catalogue_units["length"],
            catalogue_mass_unit=catalogue_units["mass"],
        )
        if form.is_valid():
            product = form.save(commit=False)
            product.catalogue = catalogue
            product.save()
            remember_catalogue_units(
                request,
                length_unit=form.cleaned_data.get("catalogue_length_unit"),
                mass_unit=form.cleaned_data.get("catalogue_mass_unit"),
            )
            messages.success(request, "Product added successfully.")
            return redirect("product_catalogue_detail", catalogue_id=catalogue.id)
    else:
        form = ProductForm(
            user=request.user,
            catalogue_length_unit=catalogue_units["length"],
            catalogue_mass_unit=catalogue_units["mass"],
        )

    return render(
        request,
        "product_catalogue/add_product.html",
        {
            "catalogue": catalogue,
            "form": form,
            "catalogue_length_unit": catalogue_units["length"],
            "catalogue_mass_unit": catalogue_units["mass"],
            "catalogue_unit_selectors": catalogue_unit_selectors(
                length_unit=catalogue_units["length"], mass_unit=catalogue_units["mass"]
            ),
        },
    )


@feature_required(PRIVATE_CATALOGUES, "catalogues", redirect_to_pricing=True)
@login_required
def edit_product(request, catalogue_id, product_id):
    catalogue = get_manageable_product_catalogue_or_404(request.user, pk=catalogue_id)
    product = get_object_or_404(Product, pk=product_id, catalogue=catalogue)
    catalogue_units, unit_error = catalogue_units_from_request(request)
    if unit_error:
        return unit_error

    if request.method == "POST":
        form = ProductForm(
            request.POST,
            request.FILES,
            instance=product,
            user=request.user,
            catalogue_length_unit=catalogue_units["length"],
            catalogue_mass_unit=catalogue_units["mass"],
        )
        if form.is_valid():
            form.save()
            remember_catalogue_units(
                request,
                length_unit=form.cleaned_data.get("catalogue_length_unit"),
                mass_unit=form.cleaned_data.get("catalogue_mass_unit"),
            )
            messages.success(request, "Product updated successfully.")
            return redirect("product_catalogue_detail", catalogue_id=catalogue.pk)
    else:
        form = ProductForm(
            instance=product,
            user=request.user,
            catalogue_length_unit=catalogue_units["length"],
            catalogue_mass_unit=catalogue_units["mass"],
        )

    return render(
        request,
        "product_catalogue/edit_product.html",
        {
            "catalogue": catalogue,
            "product": product,
            "form": form,
            "catalogue_length_unit": catalogue_units["length"],
            "catalogue_mass_unit": catalogue_units["mass"],
            "catalogue_unit_selectors": catalogue_unit_selectors(
                length_unit=catalogue_units["length"], mass_unit=catalogue_units["mass"]
            ),
        },
    )


@feature_required(PRIVATE_CATALOGUES, "catalogues", redirect_to_pricing=True)
@login_required
@require_POST
def delete_product(request, catalogue_id, product_id):
    catalogue = get_manageable_product_catalogue_or_404(request.user, pk=catalogue_id)
    product = get_object_or_404(Product, pk=product_id, catalogue=catalogue)
    product_label = product.product_id or product.product_name or str(product.pk)

    product.delete()

    messages.success(request, f"Product '{product_label}' deleted successfully.")
    return redirect("product_catalogue_detail", catalogue_id=catalogue.pk)


@feature_required(PRIVATE_CATALOGUES, "catalogues", redirect_to_pricing=True)
@login_required
def upload_products_excel(request, catalogue_id):
    catalogue = get_manageable_product_catalogue_or_404(request.user, pk=catalogue_id)

    if request.method == "POST":
        form = ProductExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                created_count, updated_count = import_product_excel(request.FILES["file"], catalogue)
                return render(
                    request,
                    "product_catalogue/upload_excel.html",
                    {
                        "form": ProductExcelUploadForm(),
                        "catalogue": catalogue,
                        "success": f"Upload completed. Created: {created_count}. Updated: {updated_count}.",
                    },
                )
            except Exception as e:
                return render(
                    request,
                    "product_catalogue/upload_excel.html",
                    {"form": form, "catalogue": catalogue, "error": str(e)},
                )
    else:
        form = ProductExcelUploadForm()

    return render(
        request,
        "product_catalogue/upload_excel.html",
        {"catalogue": catalogue, "form": form},
    )



@feature_required(PRIVATE_CATALOGUES, "catalogues", redirect_to_pricing=True)
def download_product_excel_template(request, catalogue_id):
    catalogue = get_manageable_product_catalogue_or_404(request.user, pk=catalogue_id)

    wb = Workbook()

    ws = wb.active
    ws.title = "Template"
    ws.append([
        "product_id",
        "product_name",
        "product_length",
        "product_width",
        "product_height",
        "rotation_1",
        "rotation_2",
        "rotation_3",
        "weight",
        "desired_qty",
    ])
    ws.append([
        "P-100001",
        "Sample Product",
        300,
        200,
        150,
        True,
        False,
        False,
        1.250,
        12,
    ])

    info = wb.create_sheet(title="Instructions")
    info["A1"] = "Product Catalogue Upload Template"
    info["A2"] = "Units"
    info["B2"] = "Metric only"
    info["A3"] = "Dimensions"
    info["B3"] = "product_length, product_width, product_height in mm"
    info["A4"] = "Weight"
    info["B4"] = "weight in kg"
    info["A5"] = "Desired quantity"
    info["B5"] = "desired_qty is units needed per packaging analysis"
    info["A6"] = "Rotations"
    info["B6"] = "Use TRUE/FALSE, 1/0, YES/NO"
    info["A7"] = "Catalogue"
    info["B7"] = catalogue.name

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"product_catalogue_template_{catalogue.pk}.xlsx"

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response



@feature_required(PRIVATE_CATALOGUES, "catalogues", redirect_to_pricing=True)
def export_product_catalogue_excel(request, catalogue_id):
    catalogue = get_manageable_product_catalogue_or_404(request.user, pk=catalogue_id)
    products = catalogue.products.all().order_by("product_id")

    wb = Workbook()
    ws = wb.active
    ws.title = "Product Catalogue Export"

    ws.append([
        "product_id",
        "product_name",
        "product_length",
        "product_width",
        "product_height",
        "rotation_1",
        "rotation_2",
        "rotation_3",
        "weight",
        "desired_qty",
        "product_volume",
        "product_picture",
    ])

    for p in products:
        ws.append([
            p.product_id,
            p.product_name,
            float(p.product_length) if p.product_length is not None else None,
            float(p.product_width) if p.product_width is not None else None,
            float(p.product_height) if p.product_height is not None else None,
            p.rotation_1,
            p.rotation_2,
            p.rotation_3,
            float(p.weight) if p.weight is not None else None,
            p.desired_qty,
            float(p.product_volume) if p.product_volume is not None else None,
            p.product_picture.url if p.product_picture else "",
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"product_catalogue_export_{catalogue.pk}.xlsx"

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@feature_required(PRIVATE_CATALOGUES, "catalogues", redirect_to_pricing=True)
@login_required
def upload_product_images_zip(request, catalogue_id):
    catalogue = get_manageable_product_catalogue_or_404(request.user, pk=catalogue_id)

    if request.method == "POST":
        form = ProductImagesZipUploadForm(request.POST, request.FILES)
        if form.is_valid():
            zf = form.cleaned_data["file"]
            try:
                matched, skipped = import_product_images_zip(
                    zf,
                    catalogue,
                    acting_user=request.user,
                )

                return render(
                    request,
                    "product_catalogue/upload_images_zip.html",
                    {
                        "form": ProductImagesZipUploadForm(),
                        "catalogue": catalogue,
                        "success": f"ZIP processed successfully. Images matched and saved: {matched}. Skipped: {skipped}.",
                    },
                )
            except zipfile.BadZipFile:
                return render(
                    request,
                    "product_catalogue/upload_images_zip.html",
                    {
                        "form": form,
                        "catalogue": catalogue,
                        "error": "Invalid ZIP file.",
                    },
                )
            except CatalogueMediaError as exc:
                return render(
                    request,
                    "product_catalogue/upload_images_zip.html",
                    {"form": form, "catalogue": catalogue, "error": str(exc)},
                )
    else:
        form = ProductImagesZipUploadForm()

    return render(
        request,
        "product_catalogue/upload_images_zip.html",
        {"catalogue": catalogue, "form": form},
    )
