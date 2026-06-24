# Generated for packaging material pictures.

from django.db import migrations, models
import packagingapp.models


class Migration(migrations.Migration):

    dependencies = [
        ("packagingapp", "0008_catalogue_access_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="packagingmaterial",
            name="picture",
            field=models.ImageField(
                upload_to=packagingapp.models.packaging_material_picture_upload_path,
                blank=True,
                null=True,
            ),
        ),
    ]
