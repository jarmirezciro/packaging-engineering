from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def mark_existing_catalogues_public(apps, schema_editor):
    PackagingCatalogue = apps.get_model("packagingapp", "PackagingCatalogue")
    ProductCatalogue = apps.get_model("packagingapp", "ProductCatalogue")
    PackagingCatalogue.objects.filter(is_public=False).update(is_public=True)
    ProductCatalogue.objects.filter(is_public=False).update(is_public=True)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("packagingapp", "0007_product_product_volume_productcatalogue_description_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="packagingcatalogue",
            name="is_public",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="packagingcatalogue",
            name="owner",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="packaging_catalogues", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="productcatalogue",
            name="is_public",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="productcatalogue",
            name="owner",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="product_catalogues", to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(mark_existing_catalogues_public, migrations.RunPython.noop),
    ]
