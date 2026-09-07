from django.contrib import admin

from .models import (
    CorrugatedBoardConstruction,
    CorrugatedECTReferenceGrade,
    PackagingCatalogue,
    PackagingMaterial,
    ProductCatalogue,
    Product,
    UserSubscription,
)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "status",
        "is_founder",
        "starts_at",
        "current_period_end",
        "updated_at",
    )
    list_filter = ("plan", "status", "is_founder", "starts_at", "current_period_end")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


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


@admin.register(CorrugatedBoardConstruction)
class CorrugatedBoardConstructionAdmin(admin.ModelAdmin):
    list_display = (
        "code", "name", "supplier_name", "supplier_grade_code", "wall_type",
        "flute_display", "combined_grammage_g_m2", "caliper_mm", "ect_kn_m",
        "measured_bct_n", "source_type", "is_active", "updated_at",
    )
    list_filter = ("is_active", "wall_type", "flute_1", "flute_2", "source_type", "co2_source_type")
    search_fields = ("code", "name", "supplier_name", "supplier_grade_code", "source_label", "source_notes")
    readonly_fields = ("combined_grammage_g_m2", "nominal_flute_height_mm", "created_at", "updated_at")
    fieldsets = (
        ("Identification", {"fields": ("code", "name", "supplier_name", "supplier_grade_code", "description")}),
        ("Construction", {"fields": ("wall_type", "flute_1", "flute_2", "combined_grammage_g_m2", "nominal_flute_height_mm")}),
        ("Layer papers", {"fields": ("outer_liner_type", "outer_liner_gsm", "medium_1_type", "medium_1_gsm", "take_up_factor_1", "glue_per_layer_1_gsm", "middle_liner_type", "middle_liner_gsm", "medium_2_type", "medium_2_gsm", "take_up_factor_2", "glue_per_layer_2_gsm", "inner_liner_type", "inner_liner_gsm")}),
        ("Strength", {"fields": ("caliper_mm", "ect_kn_m", "measured_bct_n", "bct_test_method")}),
        ("Sustainability", {"fields": ("co2_factor_kg_co2e_per_kg", "co2_boundary", "co2_geography", "co2_data_year", "co2_source_label", "co2_source_type", "co2_factor_basis")}),
        ("Source and documentation", {"fields": ("source_type", "source_label", "source_notes", "source_document", "source_document_date")}),
        ("Status and timestamps", {"fields": ("is_active", "sort_order", "created_at", "updated_at")}),
    )
    save_as = True

    @admin.display(description="Flute")
    def flute_display(self, obj):
        return obj.flute_display


@admin.register(CorrugatedECTReferenceGrade)
class CorrugatedECTReferenceGradeAdmin(admin.ModelAdmin):
    list_display = (
        "code", "flute_family", "wall_type", "ect_lb_in", "ect_kn_m",
        "reference_caliper_mm", "caliper_basis", "is_active", "sort_order", "updated_at",
    )
    list_filter = ("is_active", "wall_type", "flute_family", "caliper_basis")
    search_fields = ("code", "ect_source_label", "caliper_source_label", "source_notes", "calculation_notes")
    readonly_fields = ("ect_kn_m", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {
            "fields": ("code", "flute_family", "wall_type"),
            "description": "Reference grades are screening categories. Supplier-documented or measured construction values take priority.",
        } ),
        ("Strength category", {"fields": ("ect_lb_in", "ect_kn_m")} ),
        ("Reference caliper", {"fields": ("reference_caliper_mm", "caliper_basis")} ),
        ("Source traceability", {"fields": (
            "ect_source_label", "ect_source_url", "caliper_source_label", "caliper_source_url",
            "source_accessed_date", "source_notes",
        )} ),
        ("Calculations and limitations", {"fields": ("calculation_notes",)}),
        ("Status and ordering", {"fields": ("is_active", "sort_order", "created_at", "updated_at")} ),
    )
    save_on_top = True
