from decimal import Decimal

from django.db import migrations, models


SOURCE_TYPES = [
    ("OFFICIAL_REFERENCE", "Official reference"),
    ("ILLUSTRATIVE_DERIVED", "Illustrative derived"),
    ("ADMIN_ENTERED", "Admin entered"),
    ("SUPPLIER_DOCUMENTED", "Supplier documented"),
    ("COMPANY_MEASURED", "Company measured"),
]
WALL_TYPES = [("SINGLE_WALL", "Single wall"), ("DOUBLE_WALL", "Double wall")]
FLUTES = [(code, code) for code in ("A", "B", "C", "E")]
PAPER_TYPES = [
    ("KRAFTLINER", "Kraftliner"), ("TESTLINER", "Testliner"),
    ("HIGH_PERFORMANCE_RECYCLED_LINER", "High-performance recycled liner"),
    ("KRAFT_TOP_LINER", "Kraft-top liner"), ("WHITE_TOP_TESTLINER", "White-top testliner"),
    ("SEMI_CHEMICAL_FLUTING", "Semi-chemical fluting"), ("RECYCLED_FLUTING", "Recycled fluting"),
    ("LIGHTWEIGHT_RECYCLED_MEDIUM", "Lightweight recycled medium"),
    ("DUAL_PURPOSE", "Dual-purpose paper"), ("UNSPECIFIED_LINER", "Unspecified liner"),
    ("UNSPECIFIED_MEDIUM", "Unspecified medium"),
]
CO2_SOURCE_TYPES = [
    ("GENERIC_INDUSTRY_SCREENING", "Generic industry screening"),
    ("SUPPLIER_SCREENING", "Supplier screening"), ("COMPANY_MEASURED", "Company measured"),
    ("OTHER", "Other"),
]
CO2_BASES = [
    ("FINISHED_CORRUGATED_MASS", "Finished corrugated mass"),
    ("REQUIRED_SHEET_MASS", "Required sheet mass"), ("SUPPLIER_DEFINED", "Supplier defined"),
]


def _grammage(data):
    total = Decimal(str(data["outer_liner_gsm"])) + Decimal(str(data["medium_1_gsm"])) * Decimal(str(data["take_up_factor_1"])) + Decimal(str(data["inner_liner_gsm"])) + Decimal("2") * Decimal(str(data["glue_per_layer_1_gsm"]))
    if data["wall_type"] == "DOUBLE_WALL":
        total += Decimal(str(data["middle_liner_gsm"])) + Decimal(str(data["medium_2_gsm"])) * Decimal(str(data["take_up_factor_2"])) + Decimal("2") * Decimal(str(data["glue_per_layer_2_gsm"]))
    return total


def seed_corrugated_constructions(apps, schema_editor):
    Model = apps.get_model("packagingapp", "CorrugatedBoardConstruction")
    common = {
        "is_active": True, "supplier_name": "", "supplier_grade_code": "",
        "source_document": None, "source_document_date": None,
        "co2_factor_kg_co2e_per_kg": Decimal("0.491"),
        "co2_boundary": "cradle-to-grave screening", "co2_geography": "Europe",
        "co2_data_year": None,
        "co2_source_label": "FEFCO generic corrugated industry carbon impact",
        "co2_source_type": "GENERIC_INDUSTRY_SCREENING",
        "co2_factor_basis": "REQUIRED_SHEET_MASS",
        "caliper_mm": None, "ect_kn_m": None, "measured_bct_n": None,
        "bct_test_method": "",
    }
    records = [
        dict(code="GEN_E_125_90_125", name="Generic lightweight E flute — 125/90/125", source_type="ILLUSTRATIVE_DERIVED", wall_type="SINGLE_WALL", flute_1="E", outer_liner_type="TESTLINER", outer_liner_gsm=125, medium_1_type="LIGHTWEIGHT_RECYCLED_MEDIUM", medium_1_gsm=90, inner_liner_type="TESTLINER", inner_liner_gsm=125, take_up_factor_1="1.275", glue_per_layer_1_gsm="6.25", nominal_flute_height_mm="1.2", sort_order=10, source_label="Illustrative construction derived from published ranges", source_notes="Illustrative derived construction; not a commercial grade."),
        dict(code="GEN_E_150_100_150", name="Generic E flute — 150/100/150", source_type="ILLUSTRATIVE_DERIVED", wall_type="SINGLE_WALL", flute_1="E", outer_liner_type="TESTLINER", outer_liner_gsm=150, medium_1_type="RECYCLED_FLUTING", medium_1_gsm=100, inner_liner_type="TESTLINER", inner_liner_gsm=150, take_up_factor_1="1.275", glue_per_layer_1_gsm="6.25", nominal_flute_height_mm="1.2", sort_order=11, source_label="Illustrative construction derived from published ranges", source_notes="Illustrative derived construction; not a commercial grade."),
        dict(code="GEN_B_125_100_125", name="Generic lightweight B flute — 125/100/125", source_type="ILLUSTRATIVE_DERIVED", wall_type="SINGLE_WALL", flute_1="B", outer_liner_type="TESTLINER", outer_liner_gsm=125, medium_1_type="RECYCLED_FLUTING", medium_1_gsm=100, inner_liner_type="TESTLINER", inner_liner_gsm=125, take_up_factor_1="1.325", glue_per_layer_1_gsm="5.75", nominal_flute_height_mm="2.4", sort_order=20, source_label="Illustrative construction derived from published ranges", source_notes="Illustrative derived construction; not a commercial grade."),
        dict(code="GEN_B_150_120_150", name="Generic B flute — 150/120/150", source_type="ILLUSTRATIVE_DERIVED", wall_type="SINGLE_WALL", flute_1="B", outer_liner_type="TESTLINER", outer_liner_gsm=150, medium_1_type="RECYCLED_FLUTING", medium_1_gsm=120, inner_liner_type="TESTLINER", inner_liner_gsm=150, take_up_factor_1="1.325", glue_per_layer_1_gsm="5.75", nominal_flute_height_mm="2.4", sort_order=21, source_label="Illustrative construction derived from published ranges", source_notes="Illustrative derived construction; not a commercial grade."),
        dict(code="GEN_C_150_120_150", name="Generic lightweight C flute — 150/120/150", source_type="ILLUSTRATIVE_DERIVED", wall_type="SINGLE_WALL", flute_1="C", outer_liner_type="TESTLINER", outer_liner_gsm=150, medium_1_type="RECYCLED_FLUTING", medium_1_gsm=120, inner_liner_type="TESTLINER", inner_liner_gsm=150, take_up_factor_1="1.43", glue_per_layer_1_gsm="5.0", nominal_flute_height_mm="3.6", sort_order=30, source_label="Illustrative construction derived from published ranges", source_notes="Illustrative derived construction; not a commercial grade."),
        dict(code="FEFCO_C_175_140_175", name="FEFCO C-flute reference — KL175/RF140/TL175", source_type="OFFICIAL_REFERENCE", wall_type="SINGLE_WALL", flute_1="C", outer_liner_type="KRAFTLINER", outer_liner_gsm=175, medium_1_type="RECYCLED_FLUTING", medium_1_gsm=140, inner_liner_type="TESTLINER", inner_liner_gsm=175, take_up_factor_1="1.43", glue_per_layer_1_gsm="5.0", nominal_flute_height_mm="3.6", sort_order=31, source_label="FEFCO C-flute worked example", source_notes="Only seed whose exact paper combination follows the FEFCO worked example; displayed grammage rounds to 560 g/m²."),
        dict(code="GEN_A_175_140_175", name="Generic A flute — 175/140/175", source_type="ILLUSTRATIVE_DERIVED", wall_type="SINGLE_WALL", flute_1="A", outer_liner_type="KRAFTLINER", outer_liner_gsm=175, medium_1_type="RECYCLED_FLUTING", medium_1_gsm=140, inner_liner_type="TESTLINER", inner_liner_gsm=175, take_up_factor_1="1.525", glue_per_layer_1_gsm="4.75", nominal_flute_height_mm="4.8", sort_order=40, source_label="Illustrative construction derived from published ranges", source_notes="Illustrative derived construction; not a commercial grade."),
        dict(code="GEN_EB_150_100_125_120_150", name="Generic EB double wall — 150/100/125/120/150", source_type="ILLUSTRATIVE_DERIVED", wall_type="DOUBLE_WALL", flute_1="E", flute_2="B", outer_liner_type="TESTLINER", outer_liner_gsm=150, medium_1_type="RECYCLED_FLUTING", medium_1_gsm=100, take_up_factor_1="1.275", glue_per_layer_1_gsm="6.25", middle_liner_type="TESTLINER", middle_liner_gsm=125, medium_2_type="RECYCLED_FLUTING", medium_2_gsm=120, take_up_factor_2="1.325", glue_per_layer_2_gsm="5.75", inner_liner_type="TESTLINER", inner_liner_gsm=150, nominal_flute_height_mm="3.6", sort_order=50, source_label="Illustrative construction derived from published ranges", source_notes="Nominal combined flute height excludes facings and is not finished-board caliper."),
        dict(code="GEN_BC_175_120_150_140_175", name="Generic BC double wall — 175/120/150/140/175", source_type="ILLUSTRATIVE_DERIVED", wall_type="DOUBLE_WALL", flute_1="B", flute_2="C", outer_liner_type="KRAFTLINER", outer_liner_gsm=175, medium_1_type="RECYCLED_FLUTING", medium_1_gsm=120, take_up_factor_1="1.325", glue_per_layer_1_gsm="5.75", middle_liner_type="TESTLINER", middle_liner_gsm=150, medium_2_type="RECYCLED_FLUTING", medium_2_gsm=140, take_up_factor_2="1.43", glue_per_layer_2_gsm="5.0", inner_liner_type="TESTLINER", inner_liner_gsm=175, nominal_flute_height_mm="6.0", sort_order=60, source_label="Illustrative construction derived from published ranges", source_notes="Nominal combined flute height excludes facings and is not finished-board caliper."),
    ]
    for record in records:
        record = {**common, **record}
        record["combined_grammage_g_m2"] = _grammage(record)
        Model.objects.update_or_create(code=record.pop("code"), defaults=record)


class Migration(migrations.Migration):
    dependencies = [("packagingapp", "0010_alter_packagingmaterial_packaging_type")]
    operations = [
        migrations.CreateModel(
            name="CorrugatedBoardConstruction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("supplier_name", models.CharField(blank=True, max_length=255)),
                ("supplier_grade_code", models.CharField(blank=True, max_length=120)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("source_type", models.CharField(choices=SOURCE_TYPES, max_length=32)),
                ("source_label", models.CharField(max_length=255)),
                ("source_notes", models.TextField(blank=True)),
                ("source_document", models.FileField(blank=True, null=True, upload_to="corrugated_board_documents/")),
                ("source_document_date", models.DateField(blank=True, null=True)),
                ("wall_type", models.CharField(choices=WALL_TYPES, max_length=20)),
                ("flute_1", models.CharField(blank=True, choices=FLUTES, default="", max_length=1)),
                ("flute_2", models.CharField(blank=True, choices=FLUTES, default="", max_length=1)),
                ("outer_liner_type", models.CharField(blank=True, choices=PAPER_TYPES, default="", max_length=40)),
                ("outer_liner_gsm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("medium_1_type", models.CharField(blank=True, choices=PAPER_TYPES, default="", max_length=40)),
                ("medium_1_gsm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("middle_liner_type", models.CharField(blank=True, choices=PAPER_TYPES, default="", max_length=40)),
                ("middle_liner_gsm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("medium_2_type", models.CharField(blank=True, choices=PAPER_TYPES, default="", max_length=40)),
                ("medium_2_gsm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("inner_liner_type", models.CharField(blank=True, choices=PAPER_TYPES, default="", max_length=40)),
                ("inner_liner_gsm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("take_up_factor_1", models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True)),
                ("take_up_factor_2", models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True)),
                ("glue_per_layer_1_gsm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("glue_per_layer_2_gsm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("combined_grammage_g_m2", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("nominal_flute_height_mm", models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True)),
                ("caliper_mm", models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True)),
                ("ect_kn_m", models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True)),
                ("measured_bct_n", models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ("bct_test_method", models.CharField(blank=True, max_length=120)),
                ("co2_factor_kg_co2e_per_kg", models.DecimalField(blank=True, decimal_places=5, max_digits=8, null=True)),
                ("co2_boundary", models.CharField(blank=True, max_length=255)),
                ("co2_geography", models.CharField(blank=True, max_length=120)),
                ("co2_data_year", models.PositiveIntegerField(blank=True, null=True)),
                ("co2_source_label", models.CharField(blank=True, max_length=255)),
                ("co2_source_type", models.CharField(blank=True, choices=CO2_SOURCE_TYPES, max_length=40)),
                ("co2_factor_basis", models.CharField(blank=True, choices=CO2_BASES, max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["sort_order", "wall_type", "flute_1", "flute_2", "name"], "verbose_name": "corrugated board construction", "verbose_name_plural": "corrugated board constructions"},
        ),
        migrations.RunPython(seed_corrugated_constructions, migrations.RunPython.noop),
    ]
