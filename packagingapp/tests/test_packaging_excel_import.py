from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from packagingapp.models import PackagingCatalogue
from packagingapp.services.excel_import import BAG_FILM_COLUMNS, REQUIRED_COLUMNS, import_packaging_excel


class PackagingExcelImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catalogue = PackagingCatalogue.objects.create(name="Packaging Excel import")

    def workbook(self, *rows):
        defaults = {
            "part_description": "Catalogue material",
            "packaging_type": "BAG",
            "branding": "Brand1",
            "packaging_materials": "Polyethylene",
            "part_length": 127,
            "part_width": 87,
            "part_height": 0,
        }
        columns = list(dict.fromkeys([*REQUIRED_COLUMNS, *(key for row in rows for key in row)]))
        workbook = Workbook()
        workbook.active.append(columns)
        for row in rows:
            values = {**defaults, **row}
            workbook.active.append([values.get(column) for column in columns])
        stream = BytesIO()
        workbook.save(stream)
        stream.seek(0)
        return stream

    def test_bag_imports_with_fractional_grammage_and_either_caliper(self):
        for index, expected_caliper in enumerate(("0.03048", "0.0305"), start=1):
            with self.subTest(caliper=expected_caliper):
                part_number = f"BAG-{index}"
                stream = self.workbook({
                    "part_number": part_number,
                    "combined_grammage_g_m2": 28.04,
                    "bag_film_caliper_mm": float(expected_caliper),
                    "bag_actual_weight_g": 0.620123,
                    "bag_film_family": "ldpe",
                    "bag_construction": "two_wall",
                })
                self.assertEqual(import_packaging_excel(stream, self.catalogue), (1, 0))
                material = self.catalogue.materials.get(part_number=part_number)
                self.assertEqual(material.combined_grammage_g_m2, Decimal("28.04"))
                self.assertEqual(material.bag_film_caliper_mm, Decimal(expected_caliper))
                self.assertEqual(material.bag_actual_weight_g, Decimal("0.620123"))
                self.assertEqual(material.bag_film_family, "ldpe")
                self.assertEqual(material.bag_construction, "two_wall")

    def test_bag_imports_with_optional_columns_omitted_or_blank(self):
        optional_columns = (*BAG_FILM_COLUMNS, "combined_grammage_g_m2")
        rows = (
            {"part_number": "BAG-OMITTED"},
            {"part_number": "BAG-BLANK", **dict.fromkeys(optional_columns)},
        )
        for row in rows:
            with self.subTest(part_number=row["part_number"]):
                self.assertEqual(import_packaging_excel(self.workbook(row), self.catalogue), (1, 0))
                material = self.catalogue.materials.get(part_number=row["part_number"])
                for column in optional_columns:
                    self.assertIsNone(getattr(material, column))

    def test_box_import_preserves_fractional_corrugated_properties(self):
        stream = self.workbook({
            "part_number": "BOX-1",
            "packaging_type": "BOX",
            "packaging_materials": "Corrugated board",
            "part_height": 75,
            "combined_grammage_g_m2": 560.2,
            "box_thickness_mm": 4.127,
            "carton_style": "0201",
        })
        self.assertEqual(import_packaging_excel(stream, self.catalogue), (1, 0))
        material = self.catalogue.materials.get(part_number="BOX-1")
        self.assertEqual(material.combined_grammage_g_m2, Decimal("560.2"))
        self.assertEqual(material.box_thickness_mm, Decimal("4.127"))
        self.assertEqual(material.carton_style, "0201")

    def test_eight_bags_are_updated_in_place_on_reimport(self):
        rows = [
            {
                "part_number": f"BAG-{index}",
                "combined_grammage_g_m2": 28.04,
                "bag_film_caliper_mm": 0.03048,
            }
            for index in range(1, 9)
        ]
        self.assertEqual(import_packaging_excel(self.workbook(*rows), self.catalogue), (8, 0))
        materials = self.catalogue.materials.filter(packaging_type="BAG")
        material_ids = dict(materials.values_list("part_number", "pk"))
        self.assertEqual(set(material_ids), {row["part_number"] for row in rows})

        rows[-1]["bag_film_caliper_mm"] = 0.0305
        self.assertEqual(import_packaging_excel(self.workbook(*rows), self.catalogue), (0, 8))
        self.assertEqual(self.catalogue.materials.count(), 8)
        self.assertEqual(dict(materials.values_list("part_number", "pk")), material_ids)
        self.assertEqual(materials.get(part_number="BAG-8").bag_film_caliper_mm, Decimal("0.0305"))

    def test_upload_reports_invalid_precision_and_rolls_back_all_rows(self):
        staff = get_user_model().objects.create_user(username="import-staff", is_staff=True)
        self.client.force_login(staff)
        url = reverse("upload_excel", args=[self.catalogue.pk])
        cases = (
            ("combined_grammage_g_m2", 28.04001, 4),
            ("bag_film_caliper_mm", 0.03048001, 7),
            ("bag_actual_weight_g", 0.6201234, 6),
            ("box_thickness_mm", 4.1271, 3),
        )
        for column, value, decimal_places in cases:
            with self.subTest(column=column):
                stream = self.workbook(
                    {"part_number": "BAG-1"},
                    {"part_number": "BAG-2", column: value},
                )
                upload = SimpleUploadedFile("catalogue.xlsx", stream.getvalue())
                response = self.client.post(url, {"file": upload})
                self.assertContains(
                    response,
                    f"Excel row 3, column {column} (value {value}). "
                    f"Ensure that there are no more than {decimal_places} decimal places.",
                )
                self.assertFalse(self.catalogue.materials.exists())
