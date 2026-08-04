from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from decimal import Decimal
import uuid

from .tools.corrugated_material_strength.constants import (
    CO2_FACTOR_BASES,
    CO2_SOURCE_TYPES,
    CALIPER_BASIS_CHOICES,
    ECT_LB_IN_TO_KN_M,
    FLUTE_CHOICES,
    REFERENCE_FLUTE_FAMILY_CHOICES,
    PAPER_TYPES,
    SOURCE_TYPES,
    WALL_DOUBLE,
    WALL_SINGLE,
)
from .tools.corrugated_material_strength.flute_profiles import nominal_height_for


# Create your models here.

###
# Packaging Catalogue Data Model
###

class PackagingCatalogue(models.Model):
    name = models.CharField(max_length=100, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="packaging_catalogues",
        blank=True,
        null=True,
    )
    is_public = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    picture = models.ImageField(
        upload_to="catalogue_pictures/",
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def is_platform_catalogue(self):
        return self.owner_id is None and self.is_public


def packaging_material_picture_upload_path(instance, filename):
    return f"packaging_material_pictures/{instance.catalogue_id}/{filename}"


def blog_image_upload_path(instance, filename):
    """Compatibility upload path for blog image migrations.

    The current first blog version uses static in-code articles, but some local
    branches may still contain the earlier BlogImage migration. Keeping this
    small helper here allows Django to import that migration safely.
    """
    slug = getattr(instance, "slug", None) or getattr(getattr(instance, "post", None), "slug", None) or "blog"
    return f"blog_images/{slug}/{filename}"


class PackagingMaterial(models.Model):

    PACKAGING_TYPES = [
    ('BOX', 'BOX'),
    ('PALLET', 'PALLET'),
    ('CRATE', 'CRATE'),
    ('BAG', 'BAG'),
    ('CONTAINER', 'CONTAINER'),
    ('TRAILER', 'TRAILER'),
    ]

    BRANDS = [
        ('Brand1', 'Brand1'),
        ('Brand2', 'Brand2'),
        ('Brand3', 'Brand3'),
    ]

    catalogue = models.ForeignKey(
        PackagingCatalogue,
        on_delete=models.CASCADE,
        related_name="materials"
    )

    part_number = models.CharField(max_length=50)
    part_description = models.CharField(max_length=255)

    packaging_type = models.CharField(max_length=20, choices=PACKAGING_TYPES)
    branding = models.CharField(max_length=20, choices=BRANDS)

    packaging_materials = models.CharField(max_length=255)

    # Internal dimensions (mm)
    part_length = models.DecimalField(max_digits=10, decimal_places=2)
    part_width = models.DecimalField(max_digits=10, decimal_places=2)
    part_height = models.DecimalField(max_digits=10, decimal_places=2)

    # External dimensions (mm)
    external_length = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    external_width = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    external_height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    # Weight (kg)
    part_weight = models.DecimalField(max_digits=12, decimal_places=3, blank=True, null=True)

    part_volume = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)

    drawing = models.FileField(
        upload_to='drawings/',
        blank=True,
        null=True
    )

    picture = models.ImageField(
        upload_to=packaging_material_picture_upload_path,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("catalogue", "part_number")

    def save(self, *args, **kwargs):
        self.part_volume = self.part_length * self.part_width * self.part_height
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.part_number} ({self.catalogue.name})"


###
# Product Catalogue Data Model
###


def product_catalogue_picture_upload_path(instance, filename):
    return f"product_catalogue_pictures/{filename}"


def product_image_upload_path(instance, filename):
    return f"products/{instance.catalogue_id}/{filename}"


class ProductCatalogue(models.Model):
    name = models.CharField(max_length=120, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="product_catalogues",
        blank=True,
        null=True,
    )
    is_public = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    picture = models.ImageField(
        upload_to=product_catalogue_picture_upload_path,
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    catalogue = models.ForeignKey(ProductCatalogue, on_delete=models.CASCADE, related_name="products")

    product_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    product_name = models.CharField(max_length=255, blank=True, null=True)

    product_length = models.DecimalField(max_digits=12, decimal_places=3)
    product_width = models.DecimalField(max_digits=12, decimal_places=3)
    product_height = models.DecimalField(max_digits=12, decimal_places=3)

    rotation_1 = models.BooleanField(default=True)
    rotation_2 = models.BooleanField(default=False)
    rotation_3 = models.BooleanField(default=False)

    weight = models.DecimalField(max_digits=12, decimal_places=3, blank=True, null=True)
    desired_qty = models.PositiveIntegerField(default=1)
    product_volume = models.DecimalField(max_digits=18, decimal_places=3, blank=True, null=True)

    product_picture = models.ImageField(upload_to=product_image_upload_path, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("catalogue", "product_id")
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.product_id:
            self.product_id = f"P-{uuid.uuid4().hex[:10].upper()}"

        self.product_volume = self.product_length * self.product_width * self.product_height
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_id} - {self.product_name or ''}".strip()


class CorrugatedECTReferenceGrade(models.Model):
    """Admin-managed reference ECT category, separate from board construction."""

    SOURCE_TYPE_CHOICES = (
        ("INDUSTRY_REFERENCE", "Industry reference"),
        ("MANUFACTURER_EXAMPLE", "Manufacturer example"),
        ("ADMIN_ENTERED", "Admin entered"),
    )
    FLUTE_FAMILY_CHOICES = REFERENCE_FLUTE_FAMILY_CHOICES
    REFERENCE_FLUTE_FAMILY_CHOICES = FLUTE_FAMILY_CHOICES
    CALIPER_BASIS_CHOICES = CALIPER_BASIS_CHOICES

    code = models.CharField(max_length=64, unique=True)
    flute_family = models.CharField(max_length=2, choices=FLUTE_FAMILY_CHOICES)
    wall_type = models.CharField(
        max_length=20,
        choices=((WALL_SINGLE, "Single wall"), (WALL_DOUBLE, "Double wall")),
    )
    ect_lb_in = models.DecimalField(max_digits=8, decimal_places=3)
    ect_kn_m = models.DecimalField(max_digits=12, decimal_places=9, editable=False)
    reference_caliper_mm = models.DecimalField(max_digits=8, decimal_places=3)
    caliper_basis = models.CharField(max_length=40, choices=CALIPER_BASIS_CHOICES)
    ect_source_label = models.CharField(max_length=255)
    ect_source_url = models.URLField(max_length=500)
    caliper_source_url = models.URLField(max_length=500)
    source_accessed_date = models.DateField(blank=True, null=True)
    calculation_notes = models.TextField(blank=True)

    # Legacy source columns remain for compatibility with the original Luna
    # migration and are kept synchronized by the seed/admin workflow.
    source_type = models.CharField(max_length=32, choices=SOURCE_TYPE_CHOICES, blank=True, default="INDUSTRY_REFERENCE")
    source_label = models.CharField(max_length=255, blank=True, default="")
    source_notes = models.TextField(blank=True)
    caliper_source_label = models.CharField(max_length=255)
    caliper_source_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["wall_type", "flute_family", "sort_order", "ect_lb_in"]
        constraints = [
            models.UniqueConstraint(
                fields=("flute_family", "ect_lb_in"),
                name="corrugated_ect_grade_family_ect_unique",
            ),
        ]
        verbose_name = "corrugated ECT reference grade"
        verbose_name_plural = "corrugated ECT reference grades"

    @property
    def calculated_ect_kn_m(self):
        return self.ect_lb_in * ECT_LB_IN_TO_KN_M

    def clean(self):
        errors = {}
        if self.ect_lb_in is not None and self.ect_lb_in <= 0:
            errors["ect_lb_in"] = "ECT must be greater than zero."
        if self.ect_lb_in is not None and self.ect_kn_m is not None:
            if abs(self.ect_kn_m - self.calculated_ect_kn_m) > Decimal("0.000000001"):
                errors["ect_kn_m"] = "Metric ECT must match the calculated imperial conversion."
        if self.reference_caliper_mm is None:
            errors["reference_caliper_mm"] = "Reference caliper is required for every reference grade."
        elif self.reference_caliper_mm <= 0:
            errors["reference_caliper_mm"] = "Reference caliper must be greater than zero."
        if not self.ect_source_label:
            errors["ect_source_label"] = "ECT source label is required."
        if not self.ect_source_url:
            errors["ect_source_url"] = "ECT source URL is required."
        if not self.caliper_source_label:
            errors["caliper_source_label"] = "Caliper source label is required."
        if not self.caliper_source_url:
            errors["caliper_source_url"] = "Caliper source URL is required."
        if self.flute_family in {"A", "B", "C", "E", "F", "N"} and self.wall_type != WALL_SINGLE:
            errors["wall_type"] = "A, B, C, E, F and N reference grades must be single wall."
        if self.flute_family in {"EB", "BC"} and self.wall_type != WALL_DOUBLE:
            errors["wall_type"] = "EB and BC reference grades must be double wall."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.ect_kn_m = self.calculated_ect_kn_m
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.flute_family} flute - {self.ect_lb_in:g} ECT"


class CorrugatedBoardConstruction(models.Model):
    """Admin-managed corrugated construction catalogue record.

    ``flute_1`` is the first/inner medium in the selected design order and
    ``flute_2`` is the second medium for double wall.  Nominal flute height
    excludes facings and is never used as finished-board caliper.
    """

    WALL_TYPE_CHOICES = (
        (WALL_SINGLE, "Single wall"),
        (WALL_DOUBLE, "Double wall"),
    )

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    supplier_name = models.CharField(max_length=255, blank=True)
    supplier_grade_code = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    source_type = models.CharField(max_length=32, choices=SOURCE_TYPES)
    source_label = models.CharField(max_length=255)
    source_notes = models.TextField(blank=True)
    source_document = models.FileField(upload_to="corrugated_board_documents/", blank=True, null=True)
    source_document_date = models.DateField(blank=True, null=True)

    wall_type = models.CharField(max_length=20, choices=WALL_TYPE_CHOICES)
    flute_1 = models.CharField(max_length=1, choices=FLUTE_CHOICES, blank=True, default="")
    flute_2 = models.CharField(max_length=1, choices=FLUTE_CHOICES, blank=True, default="")
    outer_liner_type = models.CharField(max_length=40, choices=PAPER_TYPES, blank=True, default="")
    outer_liner_gsm = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    medium_1_type = models.CharField(max_length=40, choices=PAPER_TYPES, blank=True, default="")
    medium_1_gsm = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    middle_liner_type = models.CharField(max_length=40, choices=PAPER_TYPES, blank=True, default="")
    middle_liner_gsm = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    medium_2_type = models.CharField(max_length=40, choices=PAPER_TYPES, blank=True, default="")
    medium_2_gsm = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    inner_liner_type = models.CharField(max_length=40, choices=PAPER_TYPES, blank=True, default="")
    inner_liner_gsm = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    take_up_factor_1 = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    take_up_factor_2 = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    glue_per_layer_1_gsm = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    glue_per_layer_2_gsm = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    combined_grammage_g_m2 = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True)
    nominal_flute_height_mm = models.DecimalField(max_digits=8, decimal_places=3, blank=True, null=True)
    caliper_mm = models.DecimalField(max_digits=8, decimal_places=3, blank=True, null=True)
    ect_kn_m = models.DecimalField(max_digits=8, decimal_places=3, blank=True, null=True)
    measured_bct_n = models.DecimalField(max_digits=12, decimal_places=3, blank=True, null=True)
    bct_test_method = models.CharField(max_length=120, blank=True)

    co2_factor_kg_co2e_per_kg = models.DecimalField(max_digits=8, decimal_places=5, blank=True, null=True)
    co2_boundary = models.CharField(max_length=255, blank=True)
    co2_geography = models.CharField(max_length=120, blank=True)
    co2_data_year = models.PositiveIntegerField(blank=True, null=True)
    co2_source_label = models.CharField(max_length=255, blank=True)
    co2_source_type = models.CharField(max_length=40, choices=CO2_SOURCE_TYPES, blank=True)
    co2_factor_basis = models.CharField(max_length=40, choices=CO2_FACTOR_BASES, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "wall_type", "flute_1", "flute_2", "name"]
        verbose_name = "corrugated board construction"
        verbose_name_plural = "corrugated board constructions"

    @property
    def flute_display(self):
        return f"{self.flute_1}{self.flute_2}" if self.wall_type == WALL_DOUBLE else self.flute_1

    @property
    def calculated_combined_grammage(self):
        values = (
            self.outer_liner_gsm, self.medium_1_gsm, self.inner_liner_gsm,
            self.take_up_factor_1, self.glue_per_layer_1_gsm,
        )
        if any(value is None for value in values):
            return None
        total = (
            self.outer_liner_gsm
            + self.medium_1_gsm * self.take_up_factor_1
            + self.inner_liner_gsm
            + Decimal("2") * self.glue_per_layer_1_gsm
        )
        if self.wall_type == WALL_DOUBLE:
            values_2 = (self.middle_liner_gsm, self.medium_2_gsm, self.take_up_factor_2, self.glue_per_layer_2_gsm)
            if any(value is None for value in values_2):
                return None
            total += (
                self.middle_liner_gsm
                + self.medium_2_gsm * self.take_up_factor_2
                + Decimal("2") * self.glue_per_layer_2_gsm
            )
        return total

    def clean(self):
        errors = {}

        def required(field_names, message="This field is required for this wall type."):
            for field_name in field_names:
                if getattr(self, field_name, None) in (None, ""):
                    errors[field_name] = message

        if self.wall_type == WALL_SINGLE:
            required(("flute_1", "outer_liner_gsm", "medium_1_gsm", "inner_liner_gsm", "take_up_factor_1", "glue_per_layer_1_gsm"))
            for field_name in ("flute_2", "middle_liner_gsm", "medium_2_gsm", "take_up_factor_2", "glue_per_layer_2_gsm"):
                if getattr(self, field_name, None) not in (None, ""):
                    errors[field_name] = "This field must be blank for a single-wall construction."
        elif self.wall_type == WALL_DOUBLE:
            required(("flute_1", "flute_2", "outer_liner_gsm", "medium_1_gsm", "middle_liner_gsm", "medium_2_gsm", "inner_liner_gsm", "take_up_factor_1", "take_up_factor_2", "glue_per_layer_1_gsm", "glue_per_layer_2_gsm"))
        elif self.wall_type:
            errors["wall_type"] = "Select a supported wall type."

        positive_fields = (
            "outer_liner_gsm", "medium_1_gsm", "middle_liner_gsm", "medium_2_gsm", "inner_liner_gsm",
            "take_up_factor_1", "take_up_factor_2", "glue_per_layer_1_gsm", "glue_per_layer_2_gsm",
            "combined_grammage_g_m2", "nominal_flute_height_mm", "caliper_mm", "ect_kn_m", "measured_bct_n",
        )
        for field_name in positive_fields:
            value = getattr(self, field_name, None)
            if value is not None and value <= 0:
                errors[field_name] = "Value must be greater than zero."

        calculated = self.calculated_combined_grammage
        if calculated is not None:
            if self.combined_grammage_g_m2 is not None and abs(self.combined_grammage_g_m2 - calculated) > Decimal("0.0001"):
                errors["combined_grammage_g_m2"] = "Combined grammage must match the layer calculation."
            self.combined_grammage_g_m2 = calculated
            height = nominal_height_for(self.flute_1, self.flute_2 or None)
            if height is not None:
                self.nominal_flute_height_mm = height

        if self.co2_factor_kg_co2e_per_kg is not None:
            if self.co2_factor_kg_co2e_per_kg < 0:
                errors["co2_factor_kg_co2e_per_kg"] = "CO₂ factor cannot be negative."
            for field_name in ("co2_boundary", "co2_source_label", "co2_factor_basis"):
                if not getattr(self, field_name, None):
                    errors[field_name] = "This field is required when a CO₂ factor exists."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        calculated = self.calculated_combined_grammage
        if calculated is not None:
            self.combined_grammage_g_m2 = calculated
            self.nominal_flute_height_mm = nominal_height_for(self.flute_1, self.flute_2 or None)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} — {self.name}"
