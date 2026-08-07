from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("packagingapp", "0013_corrugated_reference_database"),
    ]

    operations = [
        migrations.AddField(
            model_name="packagingmaterial",
            name="box_thickness_mm",
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                max_digits=8,
                null=True,
                validators=[MinValueValidator(Decimal("0.001"))],
            ),
        ),
    ]
