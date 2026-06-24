# Generated manually for the catalogue packaging type expansion.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("packagingapp", "0009_packagingmaterial_picture"),
    ]

    operations = [
        migrations.AlterField(
            model_name="packagingmaterial",
            name="packaging_type",
            field=models.CharField(
                choices=[
                    ("BOX", "BOX"),
                    ("PALLET", "PALLET"),
                    ("CRATE", "CRATE"),
                    ("BAG", "BAG"),
                    ("CONTAINER", "CONTAINER"),
                    ("TRAILER", "TRAILER"),
                ],
                max_length=20,
            ),
        ),
    ]
