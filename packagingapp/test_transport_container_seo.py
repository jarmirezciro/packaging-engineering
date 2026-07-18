import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import PackagingCatalogue, PackagingMaterial


class TransportContainerSeoCalculatorTests(TestCase):
    PNG_DATA_URL = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    valid_data = {
        "action": "run_analysis",
        "container_source": "manual",
        "catalogue_id": "",
        "container_id": "",
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

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="kollipack-transport-seo-test-")

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_public_get_renders_prefilled_live_result_metadata_and_shared_viewer(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(reverse("transport_container_calculator"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_initial_example"])
        self.assertEqual(response.context["form"]["container_l"].value(), 12032)
        self.assertEqual(response.context["form"]["container_w"].value(), 2352)
        self.assertEqual(response.context["form"]["container_h"].value(), 2395)
        self.assertEqual(response.context["form"]["max_weight"].value(), 26500)
        self.assertEqual(response.context["form"]["tare_weight"].value(), 3750)
        self.assertEqual(response.context["product_rows"][0]["qty"], 20)
        self.assertEqual(response.context["product_rows"][0]["weight"], 900)
        self.assertIsNotNone(response.context["result"])
        self.assertTrue(response.context["threejs_scene"])
        self.assertGreater(response.context["result"]["summary"]["placed_units"], 0)
        self.assertContains(response, "Live example loaded")
        self.assertContains(response, 'data-preserve-tool-scroll="transport-seo"', count=1)
        self.assertContains(response, 'data-transport-threejs-viewer', count=1)
        self.assertContains(response, "js/transport_container_threejs_viewer.js")
        self.assertContains(response, 'data-transport-threejs-view="reset"')
        self.assertContains(response, 'data-transport-threejs-view="top"')
        self.assertContains(response, 'data-transport-threejs-view="front"')
        self.assertContains(response, 'data-transport-threejs-view="side"')
        self.assertContains(response, 'data-transport-threejs-pdf-button')
        self.assertContains(
            response,
            '<link rel="canonical" href="http://testserver/tools/container-loading-calculator/">',
            html=True,
        )
        self.assertContains(response, 'property="og:title"')
        self.assertContains(response, 'type="application/ld+json"')

    def test_seo_and_standalone_posts_return_equivalent_shared_outputs(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            standalone = self.client.post(reverse("container_tool"), self.valid_data)
            seo = self.client.post(reverse("transport_container_calculator"), self.valid_data)

        self.assertEqual(standalone.status_code, 200)
        self.assertEqual(seo.status_code, 200)
        self.assertEqual(seo.context["result"], standalone.context["result"])
        self.assertEqual(seo.context["threejs_scene"], standalone.context["threejs_scene"])

    def test_max_qty_uses_shared_service_and_remains_visible(self):
        max_data = {
            **self.valid_data,
            "item_qty[]": ["1"],
            "item_max_qty[]": ["1"],
            "item_max_qty_checked[]": ["0"],
        }
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.post(reverse("transport_container_calculator"), max_data)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["result"])
        self.assertTrue(response.context["product_rows"][0]["max_qty"])
        self.assertGreater(response.context["product_rows"][0]["qty"], 1)
        self.assertTrue(response.context["result"]["summary"]["product_rows"][0]["max_qty"])
        self.assertContains(response, "Max qty?")

    def test_shared_validation_handles_container_load_quantity_weight_and_payload(self):
        invalid_container = {
            **self.valid_data,
            "container_l": "-1",
            "max_weight": "-5",
        }
        invalid_row = {
            **self.valid_data,
            "item_length[]": ["0"],
            "item_qty[]": ["0"],
            "item_weight[]": ["-1"],
        }

        for url_name in ("container_tool", "transport_container_calculator"):
            with self.subTest(url_name=url_name, validation="container"):
                response = self.client.post(reverse(url_name), invalid_container)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.context["result"])
                self.assertIn("container_l", response.context["form"].errors)
                self.assertIn("max_weight", response.context["form"].errors)
                self.assertContains(response, "data-tool-validation-errors")

            with self.subTest(url_name=url_name, validation="load-row"):
                response = self.client.post(reverse(url_name), invalid_row)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.context["result"])
                self.assertTrue(response.context["row_errors"])
                self.assertContains(response, "dimensions must be greater than 0")

    def test_anonymous_catalogue_context_exposes_only_public_records(self):
        owner = get_user_model().objects.create_user(username="private-owner", password="secret")
        public_catalogue = PackagingCatalogue.objects.create(name="Public transport units", is_public=True)
        private_catalogue = PackagingCatalogue.objects.create(
            name="Private customer transport units",
            is_public=False,
            owner=owner,
        )
        public_material = PackagingMaterial.objects.create(
            catalogue=public_catalogue,
            part_number="PUBLIC-40FT",
            part_description="Public 40 foot reference",
            packaging_type="CONTAINER",
            branding="Brand1",
            packaging_materials="Steel",
            part_length=12032,
            part_width=2352,
            part_height=2395,
            part_weight=3750,
        )
        private_material = PackagingMaterial.objects.create(
            catalogue=private_catalogue,
            part_number="PRIVATE-CUSTOMER-UNIT",
            part_description="Private customer transport unit",
            packaging_type="TRAILER",
            branding="Brand2",
            packaging_materials="Steel",
            part_length=13620,
            part_width=2480,
            part_height=2700,
            part_weight=7000,
        )

        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(reverse("transport_container_calculator"))

        visible_catalogue_ids = set(response.context["packaging_catalogues"].values_list("id", flat=True))
        visible_material_ids = set(response.context["materials"].values_list("id", flat=True))
        self.assertIn(public_catalogue.id, visible_catalogue_ids)
        self.assertIn(public_material.id, visible_material_ids)
        self.assertNotIn(private_catalogue.id, visible_catalogue_ids)
        self.assertNotIn(private_material.id, visible_material_ids)
        self.assertNotContains(response, "Private customer transport units")
        self.assertNotContains(response, "PRIVATE-CUSTOMER-UNIT")

    def test_initial_pdf_export_uses_shared_threejs_snapshot_contract(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            initial = self.client.get(reverse("transport_container_calculator"))
            missing = self.client.get(reverse("container_tool_export_pdf"))
            pdf = self.client.post(
                reverse("container_tool_export_pdf"),
                {
                    "transport_threejs_snapshot_main": self.PNG_DATA_URL,
                    "transport_threejs_snapshot_top": self.PNG_DATA_URL,
                    "transport_threejs_snapshot_opposite": self.PNG_DATA_URL,
                },
            )

        self.assertEqual(initial.status_code, 200)
        self.assertEqual(missing.status_code, 400)
        self.assertIn(b"Main, Top and Opposite side", missing.content)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_sitemap_navigation_and_packaging_flow_transport_consumer_render(self):
        sitemap = self.client.get(reverse("sitemap"))
        page = self.client.get(reverse("transport_container_calculator"))
        add_step = self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "transport"},
        )
        workflow = self.client.get(reverse("full_packaging_mode"))

        self.assertEqual(sitemap.status_code, 200)
        self.assertContains(sitemap, "/tools/container-loading-calculator/")
        self.assertContains(page, reverse("palletization_calculator"))
        self.assertContains(page, reverse("full_packaging_mode"))
        self.assertEqual(add_step.status_code, 302)
        self.assertEqual(workflow.status_code, 200)
        self.assertContains(workflow, "data-transport-tool-root")
        self.assertContains(workflow, "js/transport_container_threejs_viewer.js")
