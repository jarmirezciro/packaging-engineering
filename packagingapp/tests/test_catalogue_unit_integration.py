from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from packagingapp.forms import ContainerSelectionMode1Form, PackagingMaterialForm, ProductForm
from packagingapp.models import (
    PackagingCatalogue,
    PackagingMaterial,
    Product,
    ProductCatalogue,
    UserSubscription,
)
from packagingapp.tools.container.service import build_container_analysis_report


class CatalogueEntryUnitFormTests(SimpleTestCase):
    def test_product_imperial_input_is_normalized_to_canonical_model_units(self):
        form = ProductForm(data={
            "product_id": "P-IN-1",
            "product_name": "Imperial input",
            "product_length": "12",
            "product_width": "8",
            "product_height": "5",
            "weight": "5",
            "desired_qty": "1",
            "rotation_1": "on",
            "catalogue_length_unit": "in",
            "catalogue_mass_unit": "lb",
        })

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data["product_length"], Decimal("304.800"))
        self.assertEqual(form.cleaned_data["product_width"], Decimal("203.200"))
        self.assertEqual(form.cleaned_data["product_height"], Decimal("127.000"))
        self.assertEqual(form.cleaned_data["weight"], Decimal("2.268"))

    def test_packaging_imperial_input_normalizes_internal_external_thickness_and_weight(self):
        form = PackagingMaterialForm(data={
            "part_number": "BOX-IN-1",
            "part_description": "Imperial box",
            "packaging_type": "BOX",
            "branding": "Brand1",
            "packaging_materials": "Corrugated board",
            "part_length": "12",
            "part_width": "8",
            "part_height": "5",
            "external_length": "12.5",
            "external_width": "8.5",
            "external_height": "5.5",
            "box_thickness_mm": "0.125",
            "part_weight": "1",
            "catalogue_length_unit": "in",
            "catalogue_mass_unit": "lb",
        })

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data["part_length"], Decimal("304.80"))
        self.assertEqual(form.cleaned_data["part_width"], Decimal("203.20"))
        self.assertEqual(form.cleaned_data["part_height"], Decimal("127.00"))
        self.assertEqual(form.cleaned_data["external_length"], Decimal("317.50"))
        self.assertEqual(form.cleaned_data["box_thickness_mm"], Decimal("3.175"))
        self.assertEqual(form.cleaned_data["part_weight"], Decimal("0.454"))

    def test_existing_product_is_presented_in_selected_units_without_changing_instance(self):
        product = Product(
            product_id="P-EDIT-1",
            product_length=Decimal("304.800"),
            product_width=Decimal("203.200"),
            product_height=Decimal("127.000"),
            weight=Decimal("1.250"),
            desired_qty=1,
        )
        form = ProductForm(
            instance=product,
            catalogue_length_unit="in",
            catalogue_mass_unit="lb",
        )

        self.assertEqual(form.initial["product_length"], "12")
        self.assertEqual(form.initial["product_width"], "8")
        self.assertEqual(form.initial["product_height"], "5")
        self.assertEqual(form.initial["weight"], "2.75577828")
        self.assertEqual(product.product_length, Decimal("304.800"))

        unchanged = ProductForm(
            data={
                "product_id": "P-EDIT-1",
                "product_length": "12",
                "product_width": "8",
                "product_height": "5",
                "weight": "2.75577828",
                "desired_qty": "1",
                "rotation_1": "on",
                "catalogue_length_unit": "in",
                "catalogue_mass_unit": "lb",
            },
            instance=product,
            catalogue_length_unit="in",
            catalogue_mass_unit="lb",
        )
        self.assertTrue(unchanged.is_valid(), unchanged.errors.as_json())
        self.assertEqual(unchanged.cleaned_data["product_length"], Decimal("304.800"))
        self.assertEqual(unchanged.cleaned_data["weight"], Decimal("1.250"))

    def test_unsupported_catalogue_unit_is_rejected(self):
        form = ProductForm(data={
            "product_length": "1",
            "product_width": "1",
            "product_height": "1",
            "desired_qty": "1",
            "catalogue_length_unit": "yard",
            "catalogue_mass_unit": "kg",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("Select a valid choice", str(form.errors["catalogue_length_unit"]))


class CatalogueUnitViewTests(TestCase):
    def setUp(self):
        self.catalogue = ProductCatalogue.objects.create(name="Unit Products", is_public=True)
        self.product = Product.objects.create(
            catalogue=self.catalogue,
            product_id="UNIT-P-1",
            product_name="Twelve inch product",
            product_length=Decimal("304.800"),
            product_width=Decimal("203.200"),
            product_height=Decimal("127.000"),
            weight=Decimal("1.250"),
            desired_qty=1,
        )
        self.packaging_catalogue = PackagingCatalogue.objects.create(
            name="Unit Packaging", is_public=True
        )
        self.material = PackagingMaterial.objects.create(
            catalogue=self.packaging_catalogue,
            part_number="UNIT-B-1",
            part_description="Twelve inch box",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Corrugated board",
            part_length=Decimal("304.80"),
            part_width=Decimal("203.20"),
            part_height=Decimal("127.00"),
            external_length=Decimal("317.50"),
            external_width=Decimal("215.90"),
            external_height=Decimal("139.70"),
            box_thickness_mm=Decimal("3.175"),
            part_weight=Decimal("0.450"),
        )

    def test_product_detail_displays_selected_units_and_keeps_storage_canonical(self):
        response = self.client.get(
            reverse("product_catalogue_detail", args=[self.catalogue.pk]),
            {"catalogue_length_unit": "in", "catalogue_mass_unit": "lb"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "L (in)")
        self.assertContains(response, "2.7558")
        self.assertContains(response, "data-unit-selector")
        self.assertContains(response, "js/unit_selector.js")
        self.product.refresh_from_db()
        self.assertEqual(self.product.product_length, Decimal("304.800"))
        self.assertEqual(self.product.weight, Decimal("1.250"))

    def test_packaging_detail_displays_internal_external_thickness_and_weight_units(self):
        response = self.client.get(
            reverse("catalogue_detail", args=[self.packaging_catalogue.pk]),
            {"catalogue_length_unit": "in", "catalogue_mass_unit": "lb"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Int. L (in)")
        self.assertContains(response, "Box thickness (in)")
        self.assertContains(response, "0.9921")
        self.assertContains(response, "data-unit-group=\"catalogue-display-length\"")

    def test_selected_display_units_are_reused_by_canonical_filters(self):
        response = self.client.get(
            reverse("product_catalogue_detail", args=[self.catalogue.pk]),
            {
                "catalogue_length_unit": "in",
                "catalogue_mass_unit": "lb",
                "min_length": "12",
                "max_weight": "2.7558",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [self.product])
        self.assertEqual(self.client.session["catalogue_length_unit"], "in")
        self.assertEqual(self.client.session["catalogue_mass_unit"], "lb")

    def test_product_create_and_packaging_create_save_canonical_values_from_imperial_input(self):
        user = get_user_model().objects.create_user(username="catalogue-owner", password="pass-123")
        UserSubscription.objects.create(user=user, plan=UserSubscription.Plan.PLUS)
        private_products = ProductCatalogue.objects.create(
            name="Private Unit Products", owner=user, is_public=False
        )
        private_packaging = PackagingCatalogue.objects.create(
            name="Private Unit Packaging", owner=user, is_public=False
        )
        self.client.force_login(user)

        add_product_page = self.client.get(
            reverse("add_product", args=[private_products.pk])
            + "?catalogue_length_unit=in&catalogue_mass_unit=lb"
        )
        add_material_page = self.client.get(
            reverse("add_material", args=[private_packaging.pk])
            + "?catalogue_length_unit=in&catalogue_mass_unit=lb"
        )
        self.assertEqual(add_product_page.status_code, 200)
        self.assertEqual(add_material_page.status_code, 200)
        self.assertContains(add_product_page, "data-unit-selector")
        self.assertContains(add_material_page, "data-unit-selector")

        product_response = self.client.post(
            reverse("add_product", args=[private_products.pk])
            + "?catalogue_length_unit=in&catalogue_mass_unit=lb",
            {
                "product_id": "P-POST-IN",
                "product_name": "Posted imperial product",
                "product_length": "12",
                "product_width": "8",
                "product_height": "5",
                "weight": "5",
                "desired_qty": "1",
                "rotation_1": "on",
                "catalogue_length_unit": "in",
                "catalogue_mass_unit": "lb",
            },
        )
        self.assertEqual(product_response.status_code, 302)
        saved_product = Product.objects.get(product_id="P-POST-IN")
        self.assertEqual(saved_product.product_length, Decimal("304.800"))
        self.assertEqual(saved_product.weight, Decimal("2.268"))
        edit_product_page = self.client.get(
            reverse("edit_product", args=[private_products.pk, saved_product.pk])
        )
        self.assertEqual(edit_product_page.status_code, 200)

        packaging_response = self.client.post(
            reverse("add_material", args=[private_packaging.pk])
            + "?catalogue_length_unit=in&catalogue_mass_unit=lb",
            {
                "part_number": "B-POST-IN",
                "part_description": "Posted imperial box",
                "packaging_type": "BOX",
                "branding": "Brand1",
                "packaging_materials": "Corrugated board",
                "part_length": "12",
                "part_width": "8",
                "part_height": "5",
                "box_thickness_mm": "0.125",
                "part_weight": "1",
                "catalogue_length_unit": "in",
                "catalogue_mass_unit": "lb",
            },
        )
        self.assertEqual(packaging_response.status_code, 302)
        saved_material = PackagingMaterial.objects.get(part_number="B-POST-IN")
        self.assertEqual(saved_material.part_length, Decimal("304.80"))
        self.assertEqual(saved_material.box_thickness_mm, Decimal("3.175"))
        self.assertEqual(saved_material.part_weight, Decimal("0.454"))
        edit_material_page = self.client.get(
            reverse("edit_material", args=[private_packaging.pk, saved_material.pk])
        )
        self.assertEqual(edit_material_page.status_code, 200)

    def test_catalogue_display_does_not_change_tool_canonical_mass_boundary(self):
        self.client.get(
            reverse("product_catalogue_detail", args=[self.catalogue.pk]),
            {"catalogue_length_unit": "in", "catalogue_mass_unit": "lb"},
        )
        form = ContainerSelectionMode1Form(data={
            "mode": "single",
            "product_source": "catalogue",
            "product_l": "100",
            "product_w": "80",
            "product_h": "60",
            "desired_qty": "1",
            "r1": "on",
            "container_source": "manual",
            "box_l": "400",
            "box_w": "300",
            "box_h": "250",
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        report = build_container_analysis_report(
            form=form,
            result=type("Result", (), {"max_quantity": 1})(),
            product=(100, 80, 60),
            container=(400, 300, 250),
            desired_qty=1,
            product_source="catalogue",
            selected_product=self.product,
            selected_material=None,
        )

        self.assertEqual(report["product_weight"], 1250.0)
