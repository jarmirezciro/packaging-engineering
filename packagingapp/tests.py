import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import PackagingCatalogue, PackagingMaterial, Product, ProductCatalogue


class CatalogueAdministrationRightsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="regular", password="password-123")
        self.other_user = User.objects.create_user(username="other", password="password-123")
        self.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password-123",
        )

    def test_regular_user_create_packaging_catalogue_is_forced_private(self):
        self.client.login(username="regular", password="password-123")

        response = self.client.post(
            reverse("create_catalogue"),
            {
                "name": "Regular Packaging",
                "description": "Should stay private",
                "is_public": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        catalogue = PackagingCatalogue.objects.get(name="Regular Packaging")
        self.assertFalse(catalogue.is_public)
        self.assertEqual(catalogue.owner, self.user)

    def test_regular_user_create_product_catalogue_is_forced_private(self):
        self.client.login(username="regular", password="password-123")

        response = self.client.post(
            reverse("create_product_catalogue"),
            {
                "name": "Regular Products",
                "description": "Should stay private",
                "is_public": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        catalogue = ProductCatalogue.objects.get(name="Regular Products")
        self.assertFalse(catalogue.is_public)
        self.assertEqual(catalogue.owner, self.user)

    def test_superuser_can_create_public_packaging_catalogue(self):
        self.client.login(username="admin", password="password-123")

        response = self.client.post(
            reverse("create_catalogue"),
            {
                "name": "Public Packaging",
                "description": "Visible to everyone",
                "is_public": "on",
                "owner": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        catalogue = PackagingCatalogue.objects.get(name="Public Packaging")
        self.assertTrue(catalogue.is_public)
        self.assertIsNone(catalogue.owner)

    def test_superuser_can_create_private_product_catalogue(self):
        self.client.login(username="admin", password="password-123")

        response = self.client.post(
            reverse("create_product_catalogue"),
            {
                "name": "Admin Private Products",
                "description": "Admin-owned private catalogue",
                "owner": str(self.superuser.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        catalogue = ProductCatalogue.objects.get(name="Admin Private Products")
        self.assertFalse(catalogue.is_public)
        self.assertEqual(catalogue.owner, self.superuser)

    def test_superuser_can_see_private_packaging_catalogue_owned_by_another_user(self):
        catalogue = PackagingCatalogue.objects.create(
            name="Other User Private Packaging",
            owner=self.other_user,
            is_public=False,
        )
        self.client.login(username="admin", password="password-123")

        list_response = self.client.get(reverse("catalogue_list"))
        detail_response = self.client.get(reverse("catalogue_detail", args=[catalogue.pk]))

        self.assertContains(list_response, "Other User Private Packaging")
        self.assertEqual(detail_response.status_code, 200)

    def test_superuser_can_see_private_product_catalogue_owned_by_another_user(self):
        catalogue = ProductCatalogue.objects.create(
            name="Other User Private Products",
            owner=self.other_user,
            is_public=False,
        )
        self.client.login(username="admin", password="password-123")

        list_response = self.client.get(reverse("product_catalogues"))
        detail_response = self.client.get(reverse("product_catalogue_detail", args=[catalogue.pk]))

        self.assertContains(list_response, "Other User Private Products")
        self.assertEqual(detail_response.status_code, 200)

    def test_superuser_can_change_product_catalogue_visibility_and_owner(self):
        catalogue = ProductCatalogue.objects.create(
            name="Product Visibility Change",
            owner=self.other_user,
            is_public=False,
        )
        self.client.login(username="admin", password="password-123")

        response = self.client.post(
            reverse("edit_product_catalogue", args=[catalogue.pk]),
            {
                "name": catalogue.name,
                "description": "Now public",
                "is_public": "on",
                "owner": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        catalogue.refresh_from_db()
        self.assertTrue(catalogue.is_public)
        self.assertIsNone(catalogue.owner)


class PackagingMaterialPictureTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="picture-user", password="password-123")
        self.catalogue = PackagingCatalogue.objects.create(
            name="Picture Test Packaging",
            owner=self.user,
            is_public=False,
        )
        self.material = PackagingMaterial.objects.create(
            catalogue=self.catalogue,
            part_number="PKG-100",
            part_description="Picture test box",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Corrugated board",
            part_length=100,
            part_width=80,
            part_height=60,
        )

    def test_packaging_material_picture_can_be_saved(self):
        self.material.picture.save(
            "PKG-100.jpg",
            SimpleUploadedFile("PKG-100.jpg", b"fake-image-content", content_type="image/jpeg"),
            save=True,
        )

        self.material.refresh_from_db()
        self.assertTrue(self.material.picture.name)
        self.assertIn("packaging_material_pictures", self.material.picture.name)

    def test_packaging_material_picture_upload_page_requires_owner_access(self):
        self.client.login(username="picture-user", password="password-123")

        response = self.client.get(reverse("upload_material_images_for_catalogue", args=[self.catalogue.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload Pictures")


class CatalogueRowDeletionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="row-owner", password="password-123")
        self.other_user = User.objects.create_user(username="row-other", password="password-123")

        self.packaging_catalogue = PackagingCatalogue.objects.create(
            name="Row Delete Packaging",
            owner=self.owner,
            is_public=False,
        )
        self.material = PackagingMaterial.objects.create(
            catalogue=self.packaging_catalogue,
            part_number="PKG-DEL-100",
            part_description="Delete test box",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Corrugated board",
            part_length=100,
            part_width=80,
            part_height=60,
        )

        self.product_catalogue = ProductCatalogue.objects.create(
            name="Row Delete Products",
            owner=self.owner,
            is_public=False,
        )
        self.product = Product.objects.create(
            catalogue=self.product_catalogue,
            product_id="PROD-DEL-100",
            product_name="Delete test product",
            product_length=100,
            product_width=80,
            product_height=60,
        )

    def test_owner_can_delete_packaging_material_row(self):
        self.client.login(username="row-owner", password="password-123")

        response = self.client.post(
            reverse("delete_material", args=[self.packaging_catalogue.pk, self.material.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(PackagingMaterial.objects.filter(pk=self.material.pk).exists())

    def test_other_user_cannot_delete_packaging_material_row(self):
        self.client.login(username="row-other", password="password-123")

        response = self.client.post(
            reverse("delete_material", args=[self.packaging_catalogue.pk, self.material.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(PackagingMaterial.objects.filter(pk=self.material.pk).exists())

    def test_owner_can_delete_product_row(self):
        self.client.login(username="row-owner", password="password-123")

        response = self.client.post(
            reverse("delete_product", args=[self.product_catalogue.pk, self.product.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_other_user_cannot_delete_product_row(self):
        self.client.login(username="row-other", password="password-123")

        response = self.client.post(
            reverse("delete_product", args=[self.product_catalogue.pk, self.product.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

class CatalogueRowEditingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="edit-owner", password="password-123")
        self.other_user = User.objects.create_user(username="edit-other", password="password-123")

        self.packaging_catalogue = PackagingCatalogue.objects.create(
            name="Row Edit Packaging",
            owner=self.owner,
            is_public=False,
        )
        self.material = PackagingMaterial.objects.create(
            catalogue=self.packaging_catalogue,
            part_number="PKG-EDIT-100",
            part_description="Original box",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Corrugated board",
            part_length=100,
            part_width=80,
            part_height=60,
        )

        self.product_catalogue = ProductCatalogue.objects.create(
            name="Row Edit Products",
            owner=self.owner,
            is_public=False,
        )
        self.product = Product.objects.create(
            catalogue=self.product_catalogue,
            product_id="PROD-EDIT-100",
            product_name="Original product",
            product_length=100,
            product_width=80,
            product_height=60,
        )

    def test_owner_can_edit_packaging_material_row(self):
        self.client.login(username="edit-owner", password="password-123")

        response = self.client.post(
            reverse("edit_material", args=[self.packaging_catalogue.pk, self.material.pk]),
            {
                "part_number": "PKG-EDIT-100",
                "part_description": "Updated container",
                "packaging_type": "CONTAINER",
                "branding": "Brand2",
                "packaging_materials": "Steel",
                "part_length": "120.00",
                "part_width": "90.00",
                "part_height": "70.00",
                "external_length": "130.00",
                "external_width": "100.00",
                "external_height": "80.00",
                "part_weight": "12.500",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.material.refresh_from_db()
        self.assertEqual(self.material.part_description, "Updated container")
        self.assertEqual(self.material.packaging_type, "CONTAINER")
        self.assertEqual(self.material.branding, "Brand2")

    def test_other_user_cannot_edit_packaging_material_row(self):
        self.client.login(username="edit-other", password="password-123")

        response = self.client.get(
            reverse("edit_material", args=[self.packaging_catalogue.pk, self.material.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_owner_can_edit_product_row(self):
        self.client.login(username="edit-owner", password="password-123")

        response = self.client.post(
            reverse("edit_product", args=[self.product_catalogue.pk, self.product.pk]),
            {
                "product_id": "PROD-EDIT-100",
                "product_name": "Updated product",
                "product_length": "110.000",
                "product_width": "85.000",
                "product_height": "65.000",
                "rotation_1": "on",
                "rotation_2": "on",
                "weight": "2.500",
                "desired_qty": "8",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.product_name, "Updated product")
        self.assertTrue(self.product.rotation_2)
        self.assertEqual(self.product.desired_qty, 8)

    def test_other_user_cannot_edit_product_row(self):
        self.client.login(username="edit-other", password="password-123")

        response = self.client.get(
            reverse("edit_product", args=[self.product_catalogue.pk, self.product.pk])
        )

        self.assertEqual(response.status_code, 404)

class PalletizationSeoExampleTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="kollipack-pallet-test-")

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_seo_calculator_opens_with_live_example_result(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(reverse("palletization_calculator"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_initial_example"])
        self.assertEqual(response.context["pallet_config"]["box_l"], 400)
        self.assertEqual(response.context["pallet_config"]["box_w"], 300)
        self.assertEqual(response.context["pallet_config"]["box_h"], 250)
        self.assertEqual(response.context["pallet_config"]["pallet_l"], 1200)
        self.assertEqual(response.context["pallet_config"]["pallet_w"], 800)
        self.assertEqual(response.context["pallet_config"]["max_stack_height"], 1500)
        self.assertTrue(response.context["results_table"])
        self.assertIsNotNone(response.context["selected_result"])
        self.assertTrue(response.context["result_image_url"])
        self.assertContains(response, "Live example loaded")
        self.assertContains(response, "edit any value to calculate your own pallet")

    def test_standalone_calculator_still_opens_without_example(self):
        response = self.client.get(reverse("palletization_mode1"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pallet_config"]["box_l"], "")
        self.assertEqual(response.context["pallet_config"]["pallet_l"], "")
        self.assertEqual(response.context["results_table"], [])
        self.assertNotContains(response, "Live example loaded")

