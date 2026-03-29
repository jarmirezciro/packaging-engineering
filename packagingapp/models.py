from django.db import models
import uuid


# Create your models here.

###
# Packaging Catalogue Data Model
###

class PackagingCatalogue(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    picture = models.ImageField(
        upload_to="catalogue_pictures/",
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class PackagingMaterial(models.Model):

    PACKAGING_TYPES = [
        ('BOX', 'BOX'),
        ('PALLET', 'PALLET'),
        ('CRATE', 'CRATE'),
        ('BAG', 'BAG'),
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