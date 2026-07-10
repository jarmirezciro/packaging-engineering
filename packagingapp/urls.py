# packagingapp/urls.py
from django.urls import path

from .views import packaging_catalogue, container_selection
from .views import products
from .views import bag_selection
from .views import palletization
from .views import container_tool
from .views.home import home
from .views.marketing import about, blog_detail, blog_list

from .views.multi_product_bag import (
    multi_product_bag_selection,
    multi_product_bag_run,
    multi_product_bag_draw,
    multi_product_bag_export_excel,
)

from packagingapp.views.multi_product_container import (
    multi_product_container_selection,
    multi_product_container_run,
    multi_product_container_draw,
    multi_product_container_export_excel,
)

from packagingapp.views.full_packaging import full_packaging_mode, full_packaging_export_pdf

urlpatterns = [
    # Public KolliLabs website
    path("", about, name="company_home"),
    path("about/", about, name="about"),
    path("blog/", blog_list, name="blog_list"),

    # KolliPack application
    path("kollipack/", home, name="home"),
    path("blog/<slug:slug>/", blog_detail, name="blog_detail"),


# Packaging Catalogue
    path("catalogues/", packaging_catalogue.catalogue_list, name="catalogue_list"),
    path("catalogues/create/", packaging_catalogue.create_catalogue, name="create_catalogue"),
    path("catalogues/<int:pk>/", packaging_catalogue.catalogue_detail, name="catalogue_detail"),
    path("catalogues/<int:pk>/delete/", packaging_catalogue.delete_catalogue, name="delete_catalogue"),
    path("catalogues/<int:pk>/add-material/", packaging_catalogue.add_material, name="add_material"),
    path("catalogues/<int:pk>/materials/<int:material_id>/edit/", packaging_catalogue.edit_material, name="edit_material"),
    path("catalogues/<int:pk>/materials/<int:material_id>/delete/", packaging_catalogue.delete_material, name="delete_material"),
    path("catalogues/<int:pk>/upload-excel/", packaging_catalogue.upload_excel, name="upload_excel"),
    path("catalogues/<int:pk>/download-excel-template/", packaging_catalogue.download_excel_template, name="download_excel_template"),
    path(
        "catalogues/<int:pk>/upload-drawings/",
        packaging_catalogue.upload_drawings_for_catalogue,
        name="upload_drawings_for_catalogue",
    ),
    path(
        "catalogues/<int:pk>/upload-images/",
        packaging_catalogue.upload_material_images_for_catalogue,
        name="upload_material_images_for_catalogue",
    ),
    path("catalogues/<int:pk>/edit/", packaging_catalogue.edit_catalogue, name="edit_catalogue"),

    # Container Selection
    path(
        "container-selection/mode1/",
        container_selection.container_selection_mode1,
        name="container_selection_mode1",
    ),

    path(
        "container-selection/mode1/export/pdf/",
        container_selection.container_selection_export_pdf,
        name="container_selection_export_pdf",
    ),

    path("catalogues/<int:pk>/export-excel/", packaging_catalogue.export_catalogue_excel, name="export_catalogue_excel"),


    # Product Catalogue
    path("product-catalogues/", products.product_catalogues, name="product_catalogues"),
    path("product-catalogues/create/", products.create_product_catalogue, name="create_product_catalogue"),
    path("product-catalogues/<int:catalogue_id>/", products.product_catalogue_detail, name="product_catalogue_detail"),
    path("product-catalogues/<int:catalogue_id>/delete/", products.delete_product_catalogue, name="delete_product_catalogue"),
    path("product-catalogues/<int:catalogue_id>/add/", products.add_product, name="add_product"),
    path("product-catalogues/<int:catalogue_id>/products/<int:product_id>/edit/", products.edit_product, name="edit_product"),
    path("product-catalogues/<int:catalogue_id>/products/<int:product_id>/delete/", products.delete_product, name="delete_product"),
    path("product-catalogues/<int:catalogue_id>/upload-excel/", products.upload_products_excel, name="upload_products_excel"),
    path("product-catalogues/<int:catalogue_id>/download-excel-template/", products.download_product_excel_template, name="download_product_excel_template"),
    path("product-catalogues/<int:catalogue_id>/upload-images-zip/", products.upload_product_images_zip, name="upload_product_images_zip"),
    path("product-catalogues/<int:catalogue_id>/edit/", products.edit_product_catalogue, name="edit_product_catalogue"),
    path("product-catalogues/<int:catalogue_id>/export-excel/", products.export_product_catalogue_excel, name="export_product_catalogue_excel"),

    # Multi Product Container
    path("multi-product-container/", multi_product_container_selection, name="multi_product_container_selection"),
    path("multi-product-container/run/", multi_product_container_run, name="multi_product_container_run"),
    path("multi-product-container/draw/", multi_product_container_draw, name="multi_product_container_draw"),
    path("multi-product-container/export/", multi_product_container_export_excel, name="multi_product_container_export_excel"),

    # Bag Selection
    path("bag-selection/", bag_selection.bag_selection_mode1, name="bag_selection"),
    path("bag-selection/mode1/", bag_selection.bag_selection_mode1, name="bag_selection_mode1"),
    path(
        "bag-selection/mode1/export/pdf/",
        bag_selection.bag_selection_export_pdf,
        name="bag_selection_export_pdf",
    ),
    path(
        "bag-selection/mode1/export/optimal/pdf/",
        bag_selection.bag_selection_export_optimal_pdf,
        name="bag_selection_export_optimal_pdf",
    ),

    # Multi Product Bag
    path("multi-product-bag/", multi_product_bag_selection, name="multi_product_bag_selection"),
    path("multi-product-bag/run/", multi_product_bag_run, name="multi_product_bag_run"),
    path("multi-product-bag/draw/", multi_product_bag_draw, name="multi_product_bag_draw"),
    path("multi-product-bag/export/", multi_product_bag_export_excel, name="multi_product_bag_export_excel"),

    # Palletization Tool
    path("palletization/mode1/", palletization.palletization_mode1, name="palletization_mode1"),
    path(
        "palletization/mode1/export/pdf/",
        palletization.palletization_export_pdf,
        name="palletization_export_pdf",
    ),

    # Transport Container Tool
    path("container-tool/", container_tool.container_tool, name="container_tool"),
    path(
        "container-tool/export/pdf/",
        container_tool.container_tool_export_pdf,
        name="container_tool_export_pdf",
    ),

    # Full Packaging Module
    path("full-packaging/", full_packaging_mode, name="full_packaging_mode"),
    path("full-packaging/export/pdf/", full_packaging_export_pdf, name="full_packaging_export_pdf"),
]