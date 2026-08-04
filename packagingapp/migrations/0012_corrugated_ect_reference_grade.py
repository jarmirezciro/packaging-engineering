from decimal import Decimal

from django.db import migrations, models


WALL_TYPES = [
    ("SINGLE_WALL", "Single wall"),
    ("DOUBLE_WALL", "Double wall"),
]
FLUTE_FAMILIES = [(code, code) for code in ("A", "B", "C", "E", "EB", "BC")]
SOURCE_TYPES = [
    ("INDUSTRY_REFERENCE", "Industry reference"),
    ("MANUFACTURER_EXAMPLE", "Manufacturer example"),
    ("ADMIN_ENTERED", "Admin entered"),
]


def seed_reference_grades(apps, schema_editor):
    ReferenceGrade = apps.get_model("packagingapp", "CorrugatedECTReferenceGrade")
    source_label = "FBA-hosted corrugated board strength reference table"
    source_notes = (
        "Reference ECT strength class. This does not assert that every board construction "
        "within the selected flute family achieves this value. Replace with supplier or "
        "measured data when available."
    )
    caliper_source_label = "FBA-hosted target caliper table mapped through the corresponding board grade"
    caliper_source_notes = "Target reference caliper, not supplier-measured finished-board thickness."
    single = {
        "A": {32: "5.15", 40: "5.31", 44: "5.46", 55: "5.72"},
        "B": {32: "3.10", 40: "3.26", 44: "3.41", 55: "3.67"},
        "C": {32: "4.08", 40: "4.23", 44: "4.38", 55: "4.64"},
        "E": {32: None, 40: None, 44: None, 55: None},
    }
    double = {
        "EB": {42: None, 48: None, 51: None, 61: None, 71: None, 82: None},
        "BC": {42: "6.62", 48: "6.77", 51: "7.03", 61: None, 71: "7.54", 82: "7.90"},
    }
    for flute_family, grades in {**single, **double}.items():
        wall_type = "DOUBLE_WALL" if flute_family in double else "SINGLE_WALL"
        for ect_lb_in, caliper in grades.items():
            defaults = {
                "flute_family": flute_family,
                "wall_type": wall_type,
                "ect_lb_in": Decimal(str(ect_lb_in)),
                "ect_kn_m": Decimal(str(ect_lb_in)) * Decimal("0.175126835"),
                "reference_caliper_mm": Decimal(caliper) if caliper is not None else None,
                "source_type": "INDUSTRY_REFERENCE",
                "source_label": source_label,
                "source_notes": source_notes,
                "caliper_source_label": caliper_source_label if caliper is not None else "",
                "caliper_source_notes": caliper_source_notes if caliper is not None else "",
                "is_active": True,
                "sort_order": ect_lb_in,
            }
            ReferenceGrade.objects.update_or_create(code=f"REF_{flute_family}_{ect_lb_in}", defaults=defaults)


class Migration(migrations.Migration):
    dependencies = [("packagingapp", "0011_corrugated_board_construction")]

    operations = [
        migrations.CreateModel(
            name="CorrugatedECTReferenceGrade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("flute_family", models.CharField(choices=FLUTE_FAMILIES, max_length=2)),
                ("wall_type", models.CharField(choices=WALL_TYPES, max_length=20)),
                ("ect_lb_in", models.DecimalField(decimal_places=3, max_digits=8)),
                ("ect_kn_m", models.DecimalField(decimal_places=9, max_digits=12)),
                ("reference_caliper_mm", models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True)),
                ("source_type", models.CharField(choices=SOURCE_TYPES, max_length=32)),
                ("source_label", models.CharField(max_length=255)),
                ("source_notes", models.TextField(blank=True)),
                ("caliper_source_label", models.CharField(blank=True, max_length=255)),
                ("caliper_source_notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "corrugated ECT reference grade",
                "verbose_name_plural": "corrugated ECT reference grades",
                "ordering": ["wall_type", "flute_family", "sort_order", "ect_lb_in"],
            },
        ),
        migrations.AddConstraint(
            model_name="corrugatedectreferencegrade",
            constraint=models.UniqueConstraint(
                fields=("flute_family", "ect_lb_in"),
                name="corrugated_ect_grade_family_ect_unique",
            ),
        ),
        migrations.RunPython(seed_reference_grades, migrations.RunPython.noop),
    ]
