from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("packagingapp", "0014_packagingmaterial_box_thickness_mm"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plan", models.CharField(choices=[("FREE", "Free"), ("PLUS", "Plus"), ("PREMIUM", "Premium")], default="FREE", max_length=16)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive"), ("CANCELLED", "Cancelled")], default="ACTIVE", max_length=16)),
                ("starts_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("is_founder", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="subscription", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("user__username",)},
        ),
    ]
