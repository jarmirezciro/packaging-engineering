from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("packagingapp", "0016_aiknowledgegap"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserPreferences",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("default_length_unit", models.CharField(choices=[("mm", "Millimetres (mm)"), ("cm", "Centimetres (cm)"), ("m", "Metres (m)"), ("in", "Inches (in)"), ("ft", "Feet (ft)")], default="mm", max_length=4)),
                ("default_small_mass_unit", models.CharField(choices=[("g", "Grams (g)"), ("kg", "Kilograms (kg)"), ("t", "Metric tonnes (t)"), ("oz", "Ounces (oz)"), ("lb", "Pounds (lb)")], default="g", max_length=3)),
                ("default_large_mass_unit", models.CharField(choices=[("g", "Grams (g)"), ("kg", "Kilograms (kg)"), ("t", "Metric tonnes (t)"), ("oz", "Ounces (oz)"), ("lb", "Pounds (lb)")], default="kg", max_length=3)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="unit_preferences", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "user preference",
                "verbose_name_plural": "user preferences",
            },
        ),
    ]
