# packagingapp/views/container_tool.py

from django.conf import settings
from django.shortcuts import render

from ..forms import ContainerToolForm
from ..models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
from ..tools.transport.presenter import selected_container_summary
from ..tools.transport.service import analyze_transport_config, read_product_rows_raw
from ..tools.transport.state import default_product_rows

from django.conf import settings
from django.shortcuts import render

from ..forms import ContainerToolForm
from ..models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
from ..tools.transport.presenter import selected_container_summary
from ..tools.transport.service import analyze_transport_config, read_product_rows_raw
from ..tools.transport.state import default_product_rows


def container_tool(request):
    packaging_catalogues = PackagingCatalogue.objects.all().order_by("name")
    product_catalogues = ProductCatalogue.objects.all().order_by("name")

    raw_action = request.POST.get("action") if request.method == "POST" else request.GET.get("action", "")
    raw_catalogue_id = request.POST.get("catalogue_id") if request.method == "POST" else request.GET.get("catalogue_id", "")
    raw_container_id = request.POST.get("container_id") if request.method == "POST" else request.GET.get("container_id", "")
    raw_product_catalogue_id = request.POST.get("product_catalogue_id") if request.method == "POST" else request.GET.get("product_catalogue_id", "")

    selected_catalogue = None
    selected_material = None
    selected_product_catalogue = None
    selected_product = None

    result = None
    image_url = None
    row_errors = []

    if request.method == "POST":
        product_rows = read_product_rows_raw(request.POST)
        if not product_rows:
            product_rows = default_product_rows()
    else:
        product_rows = default_product_rows()

    # Create the form BEFORE using it anywhere
    if request.method == "POST":
        form = ContainerToolForm(request.POST)
    else:
        form = ContainerToolForm(
            initial={
                "container_source": "manual",
            }
        )

    form.fields["catalogue_id"].choices = [("", "— Select —")] + [
        (str(c.id), c.name) for c in packaging_catalogues
    ]

    # Resolve selected catalogue/material after raw ids are known
    if raw_catalogue_id:
        selected_catalogue = PackagingCatalogue.objects.filter(id=raw_catalogue_id).first()

    if raw_container_id:
        selected_material = PackagingMaterial.objects.filter(id=raw_container_id).select_related("catalogue").first()
        if selected_material and not selected_catalogue:
            selected_catalogue = selected_material.catalogue

    if raw_product_catalogue_id:
        selected_product_catalogue = ProductCatalogue.objects.filter(id=raw_product_catalogue_id).first()

    if request.method == "POST" and form.is_valid():
        container_source = form.cleaned_data.get("container_source") or "manual"

        cfg = {
            "container_source": container_source,
            "container_l": form.cleaned_data.get("container_l"),
            "container_w": form.cleaned_data.get("container_w"),
            "container_h": form.cleaned_data.get("container_h"),
            "max_weight": form.cleaned_data.get("max_weight"),
        }

        if raw_action == "run_analysis":
            analysis = analyze_transport_config(
                cfg,
                product_rows,
                selected_material=selected_material,
                media_root=settings.MEDIA_ROOT,
            )
            product_rows = analysis["safe_rows"]
            row_errors = analysis["messages"]

            if analysis["ok"]:
                result = analysis["serialized_result"]
                image_url = analysis["image_url"]

        # Rebuild form with stable values for rendering
        form = ContainerToolForm(
            initial={
                "container_source": container_source,
                "catalogue_id": raw_catalogue_id,
                "container_id": raw_container_id,
                "container_l": cfg.get("container_l"),
                "container_w": cfg.get("container_w"),
                "container_h": cfg.get("container_h"),
                "max_weight": cfg.get("max_weight"),
            }
        )
        form.fields["catalogue_id"].choices = [("", "— Select —")] + [
            (str(c.id), c.name) for c in packaging_catalogues
        ]

    container_summary = selected_container_summary(selected_material, form)

    packaging_materials = PackagingMaterial.objects.all().select_related("catalogue").order_by("part_number")
    if selected_catalogue:
        packaging_materials = packaging_materials.filter(catalogue=selected_catalogue)

    products = Product.objects.all().order_by("product_name")
    if selected_product_catalogue:
        products = products.filter(catalogue=selected_product_catalogue)

    context = {
        "form": form,
        "result": result,
        "image_url": image_url,
        "row_errors": row_errors,
        "product_rows": product_rows,
        "packaging_catalogues": packaging_catalogues,
        "selected_catalogue": selected_catalogue,
        "selected_material": selected_material,
        "packaging_materials": packaging_materials,
        "product_catalogues": product_catalogues,
        "selected_product_catalogue": selected_product_catalogue,
        "products": products,
        "selected_product": selected_product,
        "container_summary": container_summary,
    }

    return render(request, "container_tool/container_tool.html", context)