from django.contrib import admin
from .models import PackagingCatalogue, PackagingMaterial


@admin.register(PackagingCatalogue)
class PackagingCatalogueAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(PackagingMaterial)
class PackagingMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "part_number",
        "catalogue",
        "packaging_type",
        "branding",
        "part_volume",
    )
    list_filter = ("catalogue", "packaging_type", "branding")
    search_fields = ("part_number", "part_description")

