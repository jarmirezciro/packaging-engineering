import json
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
        self.assertIsNone(response.context["result_image_url"])
        self.assertTrue(response.context["threejs_scene"])
        self.assertContains(response, "data-palletization-threejs-viewer")
        self.assertContains(response, "js/palletization_threejs_viewer.js")
        self.assertContains(response, "Live example loaded")
        self.assertContains(response, "edit any value to calculate your own pallet")

    def test_standalone_calculator_still_opens_without_example(self):
        response = self.client.get(reverse("palletization_mode1"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pallet_config"]["box_l"], "")
        self.assertEqual(response.context["pallet_config"]["pallet_l"], "")
        self.assertEqual(response.context["results_table"], [])
        self.assertNotContains(response, "Live example loaded")


class PalletizationThreeJsAndPdfTests(TestCase):
    # Valid 1x1 PNG used only to exercise the server-side snapshot contract.
    PNG_DATA_URL = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="kollipack-pallet-threejs-test-")
        self.analysis_data = {
            "action": "run_analysis",
            "box_source": "manual",
            "box_l": "400",
            "box_w": "300",
            "box_h": "250",
            "box_weight": "",
            "max_weight_on_bottom_box": "",
            "pallet_source": "manual",
            "pallet_l": "1200",
            "pallet_w": "800",
            "max_stack_height": "1500",
            "max_width_stickout": "0",
            "max_length_stickout": "0",
        }

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_scene_uses_engine_placements_and_is_json_safe(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.post(
                reverse("palletization_mode1"),
                self.analysis_data,
            )

        self.assertEqual(response.status_code, 200)
        scene = response.context["threejs_scene"]
        selected = response.context["selected_result"]
        self.assertEqual(scene["total_cases"], selected["total_boxes"])
        self.assertEqual(len(scene["placements"]), selected["total_boxes"])
        self.assertEqual(scene["layers"], selected["layers"])
        self.assertEqual(scene["pallet"]["length"], 1200.0)
        self.assertEqual(scene["pallet"]["width"], 800.0)
        self.assertTrue(
            all(
                placement["z"] >= scene["pallet"]["height"]
                for placement in scene["placements"]
            )
        )
        json.dumps(scene)

    def test_pdf_requires_snapshot_and_uses_posted_browser_view(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            analysis_response = self.client.post(
                reverse("palletization_mode1"),
                self.analysis_data,
            )
            self.assertEqual(analysis_response.status_code, 200)

            missing_response = self.client.get(reverse("palletization_export_pdf"))
            self.assertEqual(missing_response.status_code, 400)
            self.assertIn(b"current Three.js pallet view was not captured", missing_response.content)

            pdf_response = self.client.post(
                reverse("palletization_export_pdf"),
                {
                    "threejs_snapshot": self.PNG_DATA_URL,
                    "threejs_view_label": "Current interactive 3D view - top view",
                },
            )

        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))
        self.assertGreater(len(pdf_response.content), 1000)

    def test_workflow_scene_contract_is_prefixed_and_json_safe(self):
        add_response = self.client.post(
            reverse("full_packaging_mode"),
            {
                "action": "add_step",
                "after_index": "start",
                "step_type": "pallet",
            },
        )
        self.assertEqual(add_response.status_code, 302)

        workflow_data = {
            "action": "run_step",
            "index": "0",
            "step_action_0": "run_analysis",
            **{
                f"{key}_0": value
                for key, value in self.analysis_data.items()
                if key != "action"
            },
        }
        with self.settings(MEDIA_ROOT=self.media_root):
            run_response = self.client.post(
                reverse("full_packaging_mode"),
                workflow_data,
            )
            self.assertEqual(run_response.status_code, 302)
            page_response = self.client.get(reverse("full_packaging_mode"))

        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, 'id="palletizationThreeJsViewer_0"', count=1)
        self.assertContains(page_response, 'id="palletizationThreeJsScene_0"', count=1)
        self.assertTrue(page_response.context["steps"][0]["threejs_scene"])
        json.dumps(self.client.session["full_packaging_mode_session"])


class ToolScrollPreservationTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="kollipack-scroll-test-")

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_standalone_and_seo_tools_render_scoped_scroll_markers(self):
        expected_markers = {
            "palletization_mode1": "palletization-standalone",
            "container_selection_mode1": "container-selection-standalone",
            "bag_selection_mode1": "bag-selection-standalone",
            "container_tool": "transport-standalone",
            "palletization_calculator": "palletization-seo",
        }

        for url_name, marker in expected_markers.items():
            with self.subTest(url_name=url_name):
                with self.settings(MEDIA_ROOT=self.media_root):
                    response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    f'data-preserve-tool-scroll="{marker}"',
                    count=1,
                )
                self.assertContains(response, "js/tool_scroll_preservation.js")

    def test_packaging_flow_gives_each_repeated_tool_instance_a_unique_marker(self):
        for _ in range(2):
            response = self.client.post(
                reverse("full_packaging_mode"),
                {
                    "action": "add_step",
                    "after_index": "start",
                    "step_type": "container",
                },
            )
            self.assertEqual(response.status_code, 302)

        response = self.client.get(reverse("full_packaging_mode"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'data-preserve-tool-scroll="packaging-flow"',
            count=1,
        )
        self.assertContains(
            response,
            'data-preserve-tool-scroll="workflow-step-0"',
            count=1,
        )
        self.assertContains(
            response,
            'data-preserve-tool-scroll="workflow-step-1"',
            count=1,
        )

    def test_multi_product_tools_remain_non_navigating_ajax_surfaces(self):
        for url_name in (
            "multi_product_container_selection",
            "multi_product_bag_selection",
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="runBtn" type="button"', count=1)
                self.assertContains(response, "fetch(")

    def test_transport_no_longer_renders_delayed_forced_scroll_logic(self):
        response = self.client.get(reverse("container_tool"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "scroll_target")
        self.assertNotContains(response, "setTimeout(function ()")
        self.assertNotContains(response, "scrollIntoView({ behavior: 'smooth'")

