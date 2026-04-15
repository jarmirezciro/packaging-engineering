from django.contrib import admin

from .models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product


class PackagingMaterialInline(admin.TabularInline):
    model = PackagingMaterial
    extra = 0


@admin.register(PackagingCatalogue)
class PackagingCatalogueAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_public", "created_at")
    list_filter = ("is_public", "created_at")
    search_fields = ("name", "description")
    inlines = [PackagingMaterialInline]


@admin.register(PackagingMaterial)
class PackagingMaterialAdmin(admin.ModelAdmin):
    list_display = ("part_number", "part_description", "catalogue", "packaging_type", "branding")
    list_filter = ("packaging_type", "branding", "catalogue")
    search_fields = ("part_number", "part_description")


class ProductInline(admin.TabularInline):
    model = Product
    extra = 0


@admin.register(ProductCatalogue)
class ProductCatalogueAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_public", "created_at")
    list_filter = ("is_public", "created_at")
    search_fields = ("name", "description")
    inlines = [ProductInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("product_id", "product_name", "catalogue", "desired_qty", "created_at")
    list_filter = ("catalogue", "created_at")
    search_fields = ("product_id", "product_name")
