import json
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

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


class TransportThreeJsAndPdfTests(TestCase):
    PNG_DATA_URL = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="kollipack-transport-threejs-test-")
        self.analysis_data = {
            "action": "run_analysis",
            "container_source": "manual",
            "packing_mode": "maximum_utilization",
            "container_l": "2400",
            "container_w": "1200",
            "container_h": "1200",
            "max_weight": "1000",
            "tare_weight": "200",
            "item_name[]": ["Pallet A"],
            "item_length[]": ["1200"],
            "item_width[]": ["800"],
            "item_height[]": ["1000"],
            "item_qty[]": ["2"],
            "item_max_qty[]": ["0"],
            "item_weight[]": ["100"],
            "item_sequence[]": ["1"],
            "item_r1[]": ["1"],
            "item_r2[]": ["0"],
            "item_r3[]": ["0"],
        }

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def _run_pallet_to_transport_flow(self, *, container_l=2400, container_w=1600, qty=2):
        self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "pallet"},
        )
        pallet_data = {
            "action": "run_step",
            "index": "0",
            "step_action_0": "run_analysis",
            "box_source_0": "manual",
            "box_l_0": "400",
            "box_w_0": "400",
            "box_h_0": "250",
            "box_weight_0": "5",
            "max_weight_on_bottom_box_0": "",
            "pallet_source_0": "manual",
            "pallet_l_0": "1200",
            "pallet_w_0": "800",
            "max_stack_height_0": "750",
            "max_width_stickout_0": "0",
            "max_length_stickout_0": "0",
        }
        with self.settings(MEDIA_ROOT=self.media_root):
            self.client.post(reverse("full_packaging_mode"), pallet_data)

        pallet_step = self.client.session["full_packaging_mode_session"]["steps"][0]
        self.assertEqual(pallet_step["pending_result"]["source_type"], "palletization_result")
        self.assertNotIn("pallet_visualization", pallet_step["pending_result"])
        self.assertTrue(pallet_step["threejs_scene"])

        self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "0", "step_type": "transport"},
        )
        transport_data = {
            "action": "run_step",
            "index": "1",
            "step_action_1": "run_analysis",
            "container_source_1": "manual",
            "container_l_1": str(container_l),
            "container_w_1": str(container_w),
            "container_h_1": "1000",
            "max_weight_1": "5000",
            "tare_weight_1": "500",
            "item_name[]": ["Inherited pallet"],
            "item_length[]": ["1200"],
            "item_width[]": ["800"],
            "item_height[]": ["850"],
            "item_qty[]": [str(qty)],
            "item_max_qty[]": ["0"],
            "item_weight[]": ["100"],
            "item_sequence[]": ["1"],
            "item_r1[]": ["1"],
            "item_r2[]": ["0"],
            "item_r3[]": ["0"],
        }
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.post(reverse("full_packaging_mode"), transport_data)
            self.assertEqual(response.status_code, 302)
            page = self.client.get(reverse("full_packaging_mode"))
        return page, page.context["steps"][1]

    def test_standalone_scene_uses_engine_placements_and_pdf_requires_three_views(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            analysis_response = self.client.post(
                reverse("container_tool"),
                self.analysis_data,
            )

            self.assertEqual(analysis_response.status_code, 200)
            scene = analysis_response.context["threejs_scene"]
            result = analysis_response.context["result"]
            self.assertEqual(scene["metadata"]["total_items"], result["summary"]["placed_units"])
            self.assertEqual(len(scene["items"]), result["summary"]["placed_units"])
            self.assertEqual(scene["transport_unit"]["length"], 2400.0)
            self.assertEqual(scene["transport_unit"]["width"], 1200.0)
            self.assertEqual(scene["transport_unit"]["height"], 1200.0)
            self.assertTrue(all(item["kind"] == "load_unit" for item in scene["items"]))
            self.assertTrue(all(item["product_id"] == "P1" for item in scene["items"]))
            self.assertEqual(scene["products"][0]["product_id"], "P1")
            self.assertEqual(scene["products"][0]["qty_loaded"], 2)
            self.assertEqual(scene["products"][0]["qty_requested"], 2)
            self.assertTrue(all(
                item["color"] == scene["products"][0]["color"]
                for item in scene["items"]
            ))
            self.assertNotIn("workflow_visualizations", scene)
            json.dumps(scene)

            self.assertContains(analysis_response, 'id="transportThreeJsViewer_0"', count=1)
            self.assertContains(analysis_response, 'id="transportThreeJsScene_0"', count=1)
            self.assertContains(analysis_response, "js/transport_container_threejs_viewer.js")
            self.assertContains(analysis_response, 'data-transport-threejs-view="loading"')
            self.assertContains(analysis_response, 'data-transport-threejs-view="opposite"')
            self.assertContains(analysis_response, 'data-transport-threejs-view="top"')
            self.assertNotContains(analysis_response, 'data-transport-threejs-view="reset"')
            self.assertNotContains(analysis_response, 'data-transport-threejs-view="front"')
            self.assertNotContains(analysis_response, 'data-transport-threejs-view="side"')
            self.assertEqual(
                analysis_response.content.count(b"data-transport-threejs-view="),
                3,
            )
            self.assertContains(analysis_response, "Loading View")
            self.assertContains(analysis_response, "Opposite Side")
            self.assertContains(analysis_response, "Top View")
            self.assertContains(analysis_response, "data-transport-product-legend")
            self.assertNotContains(analysis_response, "transportRenderImage_")

            export_payload = self.client.session["transport_container_last_export"]
            self.assertEqual(export_payload["product_legend"], scene["products"])

            missing_response = self.client.get(reverse("container_tool_export_pdf"))
            self.assertEqual(missing_response.status_code, 400)
            self.assertIn(b"Loading, Opposite Side and Top", missing_response.content)

            pdf_response = self.client.post(
                reverse("container_tool_export_pdf"),
                {
                    "transport_threejs_snapshot_loading": self.PNG_DATA_URL,
                    "transport_threejs_snapshot_top": self.PNG_DATA_URL,
                    "transport_threejs_snapshot_opposite": self.PNG_DATA_URL,
                },
            )

        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))
        self.assertGreater(len(pdf_response.content), 1000)

    def test_product_ids_and_colors_are_stable_by_original_row_index(self):
        from .tools.transport.serializers import serialize_transport_threejs_scene

        summary = {
            "placed_units": 3,
            "product_rows": [
                {"name": "Main pallet load", "length": 1200, "width": 800, "height": 1225, "qty_requested": 1},
                {"name": "Secondary carton", "length": 500, "width": 700, "height": 300, "qty_requested": 1},
                {"name": "Small carton", "length": 400, "width": 350, "height": 300, "qty_requested": 1},
            ],
        }
        placements = [
            SimpleNamespace(product_name="Small carton", row_index=2, x=1700, y=0, z=0, l=400, w=350, h=300),
            SimpleNamespace(product_name="Main pallet load", row_index=0, x=0, y=0, z=0, l=1200, w=800, h=1225),
            SimpleNamespace(product_name="Secondary carton", row_index=1, x=1200, y=0, z=0, l=500, w=700, h=300),
        ]
        container = {"L": 5900, "W": 2352, "H": 2395}

        first = serialize_transport_threejs_scene(container, placements, summary)
        second = serialize_transport_threejs_scene(container, list(reversed(placements)), summary)
        first_colors = {
            item["product_id"]: item["color"]
            for item in first["items"]
        }
        second_colors = {
            item["product_id"]: item["color"]
            for item in second["items"]
        }

        self.assertEqual([product["product_id"] for product in first["products"]], ["P1", "P2", "P3"])
        self.assertEqual(first_colors, second_colors)
        self.assertEqual(
            {product["product_id"]: product["color"] for product in first["products"]},
            first_colors,
        )

    def test_workflow_transport_scene_is_prefixed_and_session_safe(self):
        add_response = self.client.post(
            reverse("full_packaging_mode"),
            {
                "action": "add_step",
                "after_index": "start",
                "step_type": "transport",
            },
        )
        self.assertEqual(add_response.status_code, 302)

        workflow_data = dict(self.analysis_data)
        workflow_data.update({
            "action": "run_step",
            "index": "0",
            "step_action_0": "run_analysis",
            "container_source_0": "manual",
            "container_l_0": "2400",
            "container_w_0": "1200",
            "container_h_0": "1200",
            "max_weight_0": "1000",
            "tare_weight_0": "200",
        })

        with self.settings(MEDIA_ROOT=self.media_root):
            run_response = self.client.post(
                reverse("full_packaging_mode"),
                workflow_data,
            )
            self.assertEqual(run_response.status_code, 302)
            page_response = self.client.get(reverse("full_packaging_mode"))

        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, 'id="transportThreeJsViewer_0"', count=1)
        self.assertContains(page_response, 'id="transportThreeJsScene_0"', count=1)
        self.assertEqual(
            page_response.content.count(b"data-transport-threejs-view="),
            3,
        )
        self.assertContains(page_response, "data-transport-product-legend")
        self.assertTrue(page_response.context["steps"][0]["threejs_scene"])
        self.assertNotIn(
            "workflow_visualizations",
            page_response.context["steps"][0]["threejs_scene"],
        )
        json.dumps(self.client.session["full_packaging_mode_session"])

    def test_direct_pallet_flow_decorates_every_authoritative_transport_placement(self):
        page, transport_step = self._run_pallet_to_transport_flow()

        scene = transport_step["threejs_scene"]
        generic_scene = transport_step["result"]["threejs_scene"]
        visualization = scene["workflow_visualizations"]["palletized_load"]

        self.assertEqual(len(scene["items"]), 2)
        self.assertEqual(scene["metadata"]["detailed_pallet_items"], 2)
        self.assertEqual(
            scene["metadata"]["total_items"],
            transport_step["result"]["summary"]["placed_units"],
        )
        self.assertTrue(all(item["source_type"] == "palletization_result" for item in scene["items"]))
        self.assertTrue(all(item["visualization_ref"] == "palletized_load" for item in scene["items"]))
        self.assertTrue(all(item["pallet_orientation"] == "lwh" for item in scene["items"]))
        self.assertEqual(
            [tuple(item[key] for key in ("x", "y", "z", "dx", "dy", "dz")) for item in scene["items"]],
            [tuple(item[key] for key in ("x", "y", "z", "dx", "dy", "dz")) for item in generic_scene["items"]],
        )
        self.assertEqual(visualization["bounds"], {"length": 1200.0, "width": 800.0, "height": 850.0})
        self.assertEqual(visualization["scene"]["pallet"]["height"], 100.0)
        self.assertEqual(visualization["scene"]["layers"], 3)
        self.assertEqual(
            len(visualization["scene"]["placements"]),
            visualization["scene"]["total_cases"],
        )
        self.assertContains(page, "palletization_result")
        with self.settings(MEDIA_ROOT=self.media_root):
            report = self.client.get(reverse("full_packaging_export_pdf"))
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report["Content-Type"], "application/pdf")
        self.assertTrue(report.content.startswith(b"%PDF"))
        json.dumps(self.client.session["full_packaging_mode_session"])

    def test_direct_pallet_flow_maps_rotated_engine_cuboid_to_one_parent_orientation(self):
        _page, transport_step = self._run_pallet_to_transport_flow(
            container_l=900,
            container_w=1300,
            qty=1,
        )

        scene = transport_step["threejs_scene"]
        self.assertEqual(len(scene["items"]), 1)
        self.assertEqual(scene["items"][0]["pallet_orientation"], "wlh")
        self.assertEqual(
            (scene["items"][0]["dx"], scene["items"][0]["dy"], scene["items"][0]["dz"]),
            (800.0, 1200.0, 850.0),
        )

    def test_detailed_scene_requires_explicit_source_and_in_bounds_geometry(self):
        from .views.full_packaging import _decorate_transport_scene_with_pallet_visualization

        def transport_scene():
            return {
                "items": [{"x": 0, "y": 0, "z": 0, "dx": 1200, "dy": 800, "dz": 850}],
                "metadata": {"total_items": 1},
            }

        valid_pallet_scene = {
            "pallet": {"length": 1200, "width": 800, "height": 108, "deck_thickness": 18},
            "placements": [{"x": 0, "y": 0, "z": 108, "dx": 400, "dy": 400, "dz": 750}],
        }
        out_of_bounds_pallet_scene = {
            "pallet": {"length": 1200, "width": 800, "height": 108, "deck_thickness": 18},
            "placements": [{"x": 1100, "y": 0, "z": 108, "dx": 200, "dy": 400, "dz": 750}],
        }
        wrong_source = {
            "source_type": "container_result",
            "length": 1200,
            "width": 800,
            "height": 850,
            "pallet_visualization": valid_pallet_scene,
        }
        wrong_source_result = _decorate_transport_scene_with_pallet_visualization(
            transport_scene(),
            wrong_source,
        )
        self.assertNotIn("workflow_visualizations", wrong_source_result)

        out_of_bounds = dict(wrong_source)
        out_of_bounds["source_type"] = "palletization_result"
        out_of_bounds["pallet_visualization"] = out_of_bounds_pallet_scene
        out_of_bounds_result = _decorate_transport_scene_with_pallet_visualization(
            transport_scene(),
            out_of_bounds,
        )
        self.assertNotIn("workflow_visualizations", out_of_bounds_result)


class MultiProductContainerThreeJsTests(TestCase):
    def setUp(self):
        self.product_catalogue = ProductCatalogue.objects.create(
            name="Multi Product Three.js Products",
            is_public=True,
        )
        self.product = Product.objects.create(
            catalogue=self.product_catalogue,
            product_id="MP-THREE-1",
            product_name="Three.js test product",
            product_length=100,
            product_width=80,
            product_height=50,
            desired_qty=3,
        )
        self.packaging_catalogue = PackagingCatalogue.objects.create(
            name="Multi Product Three.js Packaging",
            is_public=True,
        )
        self.material = PackagingMaterial.objects.create(
            catalogue=self.packaging_catalogue,
            part_number="MP-BOX-1",
            part_description="Three.js test box",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Corrugated board",
            part_length=600,
            part_width=400,
            part_height=300,
        )

    def test_page_loads_shared_threejs_viewer_and_controls_without_png_preview(self):
        response = self.client.get(reverse("multi_product_container_selection"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/container_threejs_viewer.js")
        self.assertContains(response, 'data-container-threejs-view="reset"')
        self.assertContains(response, 'data-container-threejs-view="top"')
        self.assertContains(response, 'data-container-threejs-view="front"')
        self.assertContains(response, 'data-container-threejs-view="side"')
        self.assertNotContains(response, "data.image_url")
        self.assertNotContains(response, "Generating image")

    @patch("packagingapp.views.multi_product_container.run_mode1_and_render")
    def test_draw_returns_engine_scene_as_json_safe_payload(self, render_mock):
        scene = {
            "version": 1,
            "units": "mm",
            "container": {"length": 600.0, "width": 400.0, "height": 300.0},
            "products": [
                {
                    "kind": "product",
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "dx": 100.0,
                    "dy": 80.0,
                    "dz": 50.0,
                    "color": "#f59e0b",
                    "opacity": 1.0,
                }
            ],
            "subboxes": [],
        }
        render_mock.return_value = SimpleNamespace(
            max_quantity=24,
            image_rel_path="box_selection/unused.png",
            threejs_scene=scene,
        )

        response = self.client.post(
            reverse("multi_product_container_draw"),
            {"product_id": self.product.pk, "container_id": self.material.pk},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["max_quantity"], 24)
        self.assertEqual(payload["desired_qty"], 3)
        self.assertEqual(payload["threejs_scene"], scene)
        self.assertNotIn("image_url", payload)
        json.dumps(payload)
        self.assertEqual(render_mock.call_args.kwargs["draw_limit"], 3)


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
            "container_selection_calculator": "container-selection-seo",
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
