# packagingapp/views_product_catalogue.py
import io
import zipfile
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.core.files.base import ContentFile

from openpyxl import load_workbook

from ..models import ProductCatalogue, Product
from ..forms import (
    ProductCatalogueForm,
    ProductForm,
    ProductExcelUploadForm,
    ProductImagesZipUploadForm,
)


def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "y"}:
        return True
    if s in {"0", "false", "no", "n"}:
        return False
    return default


def _to_decimal(value, field_name):
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing required numeric field: {field_name}")
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"Invalid number for {field_name}: {value}")


# 1) Catalogue list (tiles)
def product_catalogues(request):
    catalogues = ProductCatalogue.objects.all().order_by("-created_at")
    return render(request, "product_catalogue/catalogues.html", {"catalogues": catalogues})


# 2) Create catalogue
def create_product_catalogue(request):
    if request.method == "POST":
        form = ProductCatalogueForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Product catalogue created.")
            return redirect("product_catalogues")
    else:
        form = ProductCatalogueForm()
    return render(request, "product_catalogue/create_catalogue.html", {"form": form})


# 3) Delete catalogue
def delete_product_catalogue(request, catalogue_id):
    catalogue = get_object_or_404(ProductCatalogue, id=catalogue_id)
    if request.method == "POST":
        catalogue.delete()
        messages.success(request, "Product catalogue deleted.")
        return redirect("product_catalogues")
    return render(request, "product_catalogue/confirm_delete_catalogue.html", {"catalogue": catalogue})


# 4) Catalogue detail (table of products)
def product_catalogue_detail(request, catalogue_id):
    catalogue = get_object_or_404(ProductCatalogue, id=catalogue_id)
    products = catalogue.products.all()
    return render(
        request,
        "product_catalogue/catalogue_detail.html",
        {"catalogue": catalogue, "products": products},
    )


# 5) Add product manually
def add_product(request, catalogue_id):
    catalogue = get_object_or_404(ProductCatalogue, id=catalogue_id)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.catalogue = catalogue
            product.save()
            messages.success(request, "Product added.")
            return redirect("product_catalogue_detail", catalogue_id=catalogue.id)
    else:
        form = ProductForm()
    return render(
        request,
        "product_catalogue/add_product.html",
        {"catalogue": catalogue, "form": form},
    )


# 6) Mass upload via Excel
def upload_products_excel(request, catalogue_id):
    catalogue = get_object_or_404(ProductCatalogue, id=catalogue_id)

    if request.method == "POST":
        form = ProductExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["file"]
            try:
                wb = load_workbook(filename=f, data_only=True)
                ws = wb.active
            except Exception:
                messages.error(request, "Could not read the Excel file. Please upload a valid .xlsx.")
                return redirect("upload_products_excel", catalogue_id=catalogue.id)

            # Expect headers on row 1
            headers = {}
            for idx, cell in enumerate(ws[1], start=1):
                if cell.value:
                    headers[str(cell.value).strip()] = idx

            required = ["product_length", "product_width", "product_height"]
            for col in required:
                if col not in headers:
                    messages.error(request, f"Missing required column: {col}")
                    return redirect("upload_products_excel", catalogue_id=catalogue.id)

            created = 0
            updated = 0
            errors = 0

            with transaction.atomic():
                for row in range(2, ws.max_row + 1):
                    # skip fully empty rows
                    if all(ws.cell(row=row, column=c).value in (None, "") for c in range(1, ws.max_column + 1)):
                        continue

                    def get(col, default=None):
                        if col not in headers:
                            return default
                        return ws.cell(row=row, column=headers[col]).value

                    try:
                        pid = get("product_id")
                        pname = get("product_name")
                        length = _to_decimal(get("product_length"), "product_length")
                        width = _to_decimal(get("product_width"), "product_width")
                        height = _to_decimal(get("product_height"), "product_height")

                        r1 = _to_bool(get("rotation_1"), True)
                        r2 = _to_bool(get("rotation_2"), False)
                        r3 = _to_bool(get("rotation_3"), False)

                        weight_val = get("weight")
                        weight = None
                        if weight_val not in (None, ""):
                            weight = _to_decimal(weight_val, "weight")

                        picture_name = get("product_picture")

                        obj, was_created = Product.objects.get_or_create(
                            catalogue=catalogue,
                            product_id=str(pid).strip() if pid not in (None, "") else None,
                            defaults={
                                "product_name": str(pname).strip() if pname not in (None, "") else None,
                                "product_length": length,
                                "product_width": width,
                                "product_height": height,
                                "rotation_1": r1,
                                "rotation_2": r2,
                                "rotation_3": r3,
                                "weight": weight,
                            },
                        )

                        if not was_created:
                            obj.product_name = str(pname).strip() if pname not in (None, "") else obj.product_name
                            obj.product_length = length
                            obj.product_width = width
                            obj.product_height = height
                            obj.rotation_1 = r1
                            obj.rotation_2 = r2
                            obj.rotation_3 = r3
                            obj.weight = weight
                            obj.save()
                            updated += 1
                        else:
                            created += 1

                        # picture_name is just stored as "pending filename" unless already set
                        # (actual image can be uploaded via ZIP in a separate step)
                        if picture_name and not obj.product_picture:
                            # store filename in name field temporarily if you want,
                            # or simply ignore here and rely on ZIP upload later
                            pass

                    except Exception:
                        errors += 1

            messages.success(
                request,
                f"Excel processed. Created: {created}, Updated: {updated}, Errors: {errors}",
            )
            return redirect("product_catalogue_detail", catalogue_id=catalogue.id)

    else:
        form = ProductExcelUploadForm()

    return render(
        request,
        "product_catalogue/upload_excel.html",
        {"catalogue": catalogue, "form": form},
    )


# 7) Upload product images ZIP (optional but useful for product_picture at scale)
def upload_product_images_zip(request, catalogue_id):
    catalogue = get_object_or_404(ProductCatalogue, id=catalogue_id)

    if request.method == "POST":
        form = ProductImagesZipUploadForm(request.POST, request.FILES)
        if form.is_valid():
            zf = form.cleaned_data["file"]
            try:
                with zipfile.ZipFile(zf) as z:
                    # index by lowercase filename
                    zip_names = {name.lower(): name for name in z.namelist() if not name.endswith("/")}

                    matched = 0
                    for p in catalogue.products.all():
                        if p.product_picture:
                            continue

                        # Match on product_id.ext OR product_name.ext OR any known filename convention
                        candidates = []
                        if p.product_id:
                            candidates += [f"{p.product_id}.png", f"{p.product_id}.jpg", f"{p.product_id}.jpeg", f"{p.product_id}.webp"]
                        if p.product_name:
                            safe = str(p.product_name).strip()
                            candidates += [f"{safe}.png", f"{safe}.jpg", f"{safe}.jpeg", f"{safe}.webp"]

                        found_key = None
                        for c in candidates:
                            if c.lower() in zip_names:
                                found_key = zip_names[c.lower()]
                                break

                        if not found_key:
                            continue

                        data = z.read(found_key)
                        p.product_picture.save(found_key.split("/")[-1], ContentFile(data), save=True)
                        matched += 1

                messages.success(request, f"ZIP processed. Images matched and saved: {matched}")
            except zipfile.BadZipFile:
                messages.error(request, "Invalid ZIP file.")
            return redirect("product_catalogue_detail", catalogue_id=catalogue.id)

    else:
        form = ProductImagesZipUploadForm()

    return render(
        request,
        "product_catalogue/upload_images_zip.html",
        {"catalogue": catalogue, "form": form},
    )