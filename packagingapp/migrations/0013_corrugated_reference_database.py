from datetime import date
from decimal import Decimal

from django.db import migrations, models


FLUTES = [(code, code) for code in ("A", "B", "C", "E", "F", "N")]
REFERENCE_FLUTES = [
    ("A", "A flute"), ("B", "B flute"), ("C", "C flute"),
    ("E", "E flute"), ("F", "F flute"), ("N", "N flute"),
    ("EB", "EB double wall"), ("BC", "BC double wall"),
]
WALL_TYPES = [("SINGLE_WALL", "Single wall"), ("DOUBLE_WALL", "Double wall")]
CALIPER_BASES = [
    ("GRADE_SPECIFIC_TARGET", "Grade-specific target caliper"),
    ("FLUTE_FAMILY_REFERENCE", "Flute-family reference caliper"),
    ("PUBLISHED_RANGE_MIDPOINT", "Midpoint of published range"),
    ("LINEAR_INTERPOLATION", "Linear interpolation between published grades"),
    ("ADMIN_ENTERED", "Admin-entered reference"),
]

ECT_CONVERSION = Decimal("0.175126835")
ACCESSED = date(2026, 8, 4)
FBA_LABEL = "FBA-hosted Corrugated Board Specifications"
FBA_URL = "https://www.fibrebox.org/assets/2025/09/Walmart_Corrugated-Board_Specifications_Automation_Packaging_Standards.pdf"
FEFCO_LABEL = "FEFCO European Database for Corrugated Board Life Cycle Studies 2023"
FEFCO_URL = "https://www.fefco.org/download/file/fid/3353"
NETPAK_LABEL = "Netpak Micro-Flute Packaging - E, F and N Flute Guide"
NETPAK_URL = "https://www.netpak.com/en/packaging-resources/industry-articles/micro-flute-packaging-e-f-n-flute/"
UNICO_LABEL = "Unico Packing EE/BE Flute Corrugated Board Reference"
UNICO_URL = "https://unicopacking.com/en/new/EE-flute-corrugated-box.html"


def _grammage(outer, medium, inner, take_up, glue):
    return (
        Decimal(str(outer))
        + Decimal(str(medium)) * Decimal(str(take_up))
        + Decimal(str(inner))
        + Decimal("2") * Decimal(str(glue))
    )


def _seed_flute_constructions(apps, schema_editor):
    Construction = apps.get_model("packagingapp", "CorrugatedBoardConstruction")
    common = {
        "is_active": True,
        "supplier_name": "",
        "supplier_grade_code": "",
        "description": "",
        "source_document": None,
        "source_document_date": None,
        "co2_factor_kg_co2e_per_kg": Decimal("0.491"),
        "co2_boundary": "cradle-to-grave screening",
        "co2_geography": "Europe",
        "co2_data_year": None,
        "co2_source_label": "FEFCO generic corrugated industry carbon impact",
        "co2_source_type": "GENERIC_INDUSTRY_SCREENING",
        "co2_factor_basis": "REQUIRED_SHEET_MASS",
        "caliper_mm": None,
        "ect_kn_m": None,
        "measured_bct_n": None,
        "bct_test_method": "",
    }
    records = [
        {
            "code": "GEN_F_125_90_125",
            "name": "Generic F flute - 125/90/125",
            "source_type": "ILLUSTRATIVE_DERIVED",
            "wall_type": "SINGLE_WALL",
            "flute_1": "F",
            "outer_liner_type": "TESTLINER",
            "outer_liner_gsm": 125,
            "medium_1_type": "LIGHTWEIGHT_RECYCLED_MEDIUM",
            "medium_1_gsm": 90,
            "inner_liner_type": "TESTLINER",
            "inner_liner_gsm": 125,
            "take_up_factor_1": Decimal("1.20"),
            "glue_per_layer_1_gsm": Decimal("10.0"),
            "combined_grammage_g_m2": _grammage(125, 90, 125, "1.20", "10.0"),
            "nominal_flute_height_mm": Decimal("0.8"),
            "sort_order": 12,
            "source_label": "FEFCO F/G/N indicative profile range",
            "source_notes": "Illustrative microflute construction using representative take-up and glue values within the published F/G/N ranges. It is not a supplier grade.",
        },
        {
            "code": "GEN_N_125_90_125",
            "name": "Generic N flute - 125/90/125",
            "source_type": "ILLUSTRATIVE_DERIVED",
            "wall_type": "SINGLE_WALL",
            "flute_1": "N",
            "outer_liner_type": "TESTLINER",
            "outer_liner_gsm": 125,
            "medium_1_type": "LIGHTWEIGHT_RECYCLED_MEDIUM",
            "medium_1_gsm": 90,
            "inner_liner_type": "TESTLINER",
            "inner_liner_gsm": 125,
            "take_up_factor_1": Decimal("1.20"),
            "glue_per_layer_1_gsm": Decimal("10.0"),
            "combined_grammage_g_m2": _grammage(125, 90, 125, "1.20", "10.0"),
            "nominal_flute_height_mm": Decimal("0.5"),
            "sort_order": 13,
            "source_label": "FEFCO F/G/N indicative profile range",
            "source_notes": "Illustrative microflute construction using representative take-up and glue values within the published F/G/N ranges. It is not a supplier grade.",
        },
    ]
    for record in records:
        code = record.pop("code")
        Construction.objects.update_or_create(code=code, defaults={**common, **record})


def _seed_reference_grades(apps, schema_editor):
    ReferenceGrade = apps.get_model("packagingapp", "CorrugatedECTReferenceGrade")
    single_calipers = {
        "A": {32: "5.15", 40: "5.31", 44: "5.46", 55: "5.72"},
        "B": {32: "3.10", 40: "3.26", 44: "3.41", 55: "3.67"},
        "C": {32: "4.08", 40: "4.23", 44: "4.38", 55: "4.64"},
        "E": {32: "1.60", 40: "1.60", 44: "1.60", 55: "1.60"},
        "F": {32: "0.80", 40: "0.80", 44: "0.80", 55: "0.80"},
        "N": {32: "0.50", 40: "0.50", 44: "0.50", 55: "0.50"},
    }
    double_calipers = {
        "EB": {42: "4.90", 48: "4.90", 51: "4.90", 61: "4.90", 71: "4.90", 82: "4.90"},
        "BC": {42: "6.62", 48: "6.77", 51: "7.03", 61: "7.20", 71: "7.54", 82: "7.90"},
    }
    family_caliper_source = {
        "E": (NETPAK_LABEL, NETPAK_URL),
        "F": (NETPAK_LABEL, NETPAK_URL),
        "N": (NETPAK_LABEL, NETPAK_URL),
    }
    for flute_family, grades in {**single_calipers, **double_calipers}.items():
        for ect_lb_in, caliper in grades.items():
            if flute_family in {"A", "B", "C", "BC"}:
                caliper_basis = "LINEAR_INTERPOLATION" if flute_family == "BC" and ect_lb_in == 61 else "GRADE_SPECIFIC_TARGET"
                caliper_label, caliper_url = FBA_LABEL, FBA_URL
                if flute_family == "BC" and ect_lb_in == 61:
                    calculation_notes = "BC 61 ECT is linearly interpolated from the direct 350# -> 7.03 mm and 500# -> 7.54 mm target-caliper rows: 7.03 + (400-350)/(500-350) x (7.54-7.03) = 7.20 mm."
                else:
                    calculation_notes = "Direct target-caliper value mapped from the published board-grade reference table."
            elif flute_family in family_caliper_source:
                caliper_basis = "FLUTE_FAMILY_REFERENCE"
                caliper_label, caliper_url = family_caliper_source[flute_family]
                calculation_notes = "Family-level approximate finished-board thickness; the source does not provide grade-specific caliper rows."
            else:
                caliper_basis = "PUBLISHED_RANGE_MIDPOINT"
                caliper_label, caliper_url = UNICO_LABEL, UNICO_URL
                calculation_notes = "Reference caliper is the arithmetic midpoint of the published 4.8-5.0 mm BE/EB finished-board range: (4.8 + 5.0) / 2 = 4.90 mm."
            source_notes = "Reference performance class. This does not assert that every paper construction in the flute family achieves this ECT. Replace with supplier-documented or measured values when available."
            defaults = {
                "flute_family": flute_family,
                "wall_type": "DOUBLE_WALL" if flute_family in {"EB", "BC"} else "SINGLE_WALL",
                "ect_lb_in": Decimal(str(ect_lb_in)),
                "ect_kn_m": Decimal(str(ect_lb_in)) * ECT_CONVERSION,
                "reference_caliper_mm": Decimal(caliper),
                "caliper_basis": caliper_basis,
                "ect_source_label": FBA_LABEL,
                "ect_source_url": FBA_URL,
                "caliper_source_label": caliper_label,
                "caliper_source_url": caliper_url,
                "source_accessed_date": ACCESSED,
                "source_notes": source_notes,
                "calculation_notes": calculation_notes,
                "source_type": "INDUSTRY_REFERENCE",
                "source_label": FBA_LABEL,
                "caliper_source_notes": calculation_notes,
                "is_active": True,
                "sort_order": ect_lb_in,
            }
            ReferenceGrade.objects.update_or_create(code=f"REF_{flute_family}_{ect_lb_in}", defaults=defaults)


def seed_reference_database(apps, schema_editor):
    _seed_flute_constructions(apps, schema_editor)
    _seed_reference_grades(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [("packagingapp", "0012_corrugated_ect_reference_grade")]

    operations = [
        migrations.AlterField(
            model_name="corrugatedboardconstruction",
            name="flute_1",
            field=models.CharField(blank=True, choices=FLUTES, default="", max_length=1),
        ),
        migrations.AlterField(
            model_name="corrugatedboardconstruction",
            name="flute_2",
            field=models.CharField(blank=True, choices=FLUTES, default="", max_length=1),
        ),
        migrations.AlterField(
            model_name="corrugatedectreferencegrade",
            name="flute_family",
            field=models.CharField(choices=REFERENCE_FLUTES, max_length=2),
        ),
        migrations.AlterField(
            model_name="corrugatedectreferencegrade",
            name="ect_kn_m",
            field=models.DecimalField(decimal_places=9, editable=False, max_digits=12),
        ),
        migrations.AlterField(
            model_name="corrugatedectreferencegrade",
            name="source_type",
            field=models.CharField(blank=True, choices=[
                ("INDUSTRY_REFERENCE", "Industry reference"),
                ("MANUFACTURER_EXAMPLE", "Manufacturer example"),
                ("ADMIN_ENTERED", "Admin entered"),
            ], default="INDUSTRY_REFERENCE", max_length=32),
        ),
        migrations.AlterField(
            model_name="corrugatedectreferencegrade",
            name="source_label",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="corrugatedectreferencegrade",
            name="caliper_basis",
            field=models.CharField(choices=CALIPER_BASES, default="ADMIN_ENTERED", max_length=40),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="corrugatedectreferencegrade",
            name="ect_source_label",
            field=models.CharField(default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="corrugatedectreferencegrade",
            name="ect_source_url",
            field=models.URLField(default=FBA_URL, max_length=500),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="corrugatedectreferencegrade",
            name="caliper_source_url",
            field=models.URLField(default=FBA_URL, max_length=500),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="corrugatedectreferencegrade",
            name="source_accessed_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="corrugatedectreferencegrade",
            name="calculation_notes",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.RunPython(seed_reference_database, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="corrugatedectreferencegrade",
            name="reference_caliper_mm",
            field=models.DecimalField(decimal_places=3, max_digits=8),
        ),
        migrations.AlterField(
            model_name="corrugatedectreferencegrade",
            name="caliper_basis",
            field=models.CharField(choices=CALIPER_BASES, max_length=40),
        ),
        migrations.AlterField(
            model_name="corrugatedectreferencegrade",
            name="caliper_source_label",
            field=models.CharField(max_length=255),
        ),
    ]
