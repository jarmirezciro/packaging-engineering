import json
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import PackagingCatalogue, PackagingMaterial, Product, ProductCatalogue
from .utils.box_selection.engine import compute_max_quantity_only


class ContainerSelectionSeoCalculatorTests(TestCase):
    PNG_DATA_URL = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    valid_data = {
        "mode": "single",
        "action": "run_single",
        "product_source": "manual",
        "product_catalogue_id": "",
        "selected_product_id": "",
        "product_l": "180",
        "product_w": "120",
        "product_h": "80",
        "product_weight": "450",
        "desired_qty": "24",
        "r1": "on",
        "r2": "on",
        "r3": "on",
        "container_source": "manual",
        "catalogue_id": "",
        "container_id": "",
        "box_l": "600",
        "box_w": "400",
        "box_h": "320",
        "box_weight": "950",
        "box_max_payload": "20000",
    }

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="kollipack-container-seo-test-")

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_public_get_renders_prefilled_live_engine_result_metrics_and_metadata(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(reverse("container_selection_calculator"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_initial_example"])
        expected_values = {
            "product_l": "180",
            "product_w": "120",
            "product_h": "80",
            "product_weight": "450",
            "desired_qty": "24",
            "box_l": "600",
            "box_w": "400",
            "box_h": "320",
            "box_weight": "950",
            "box_max_payload": "20000",
        }
        for key, value in expected_values.items():
            self.assertEqual(response.context["container_config"][key], value)

        self.assertIsNotNone(response.context["result"])
        self.assertIsNotNone(response.context["analysis_report"])
        self.assertGreater(response.context["result"].max_quantity, 0)
        self.assertEqual(
            response.context["analysis_report"]["max_quantity"],
            response.context["result"].max_quantity,
        )
        self.assertTrue(response.context["threejs_scene"])
        json.dumps(response.context["threejs_scene"])
        self.assertContains(response, "Live example loaded")
        self.assertContains(response, 'data-preserve-tool-scroll="container-selection-seo"', count=1)
        self.assertContains(response, "Volumetric efficiency")
        self.assertContains(response, "Net weight")
        self.assertContains(response, "Payload usage")
        self.assertContains(response, "Remaining capacity")
        self.assertContains(response, "pcs")
        self.assertContains(response, "kg")
        self.assertContains(
            response,
            '<link rel="canonical" href="http://testserver/tools/box-size-calculator/">',
            html=True,
        )
        self.assertContains(response, 'property="og:title"')
        self.assertContains(response, 'type="application/ld+json"')
        self.assertEqual(response.content.count(b"<h1"), 1)

    def test_seo_and_standalone_posts_return_equivalent_shared_results(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            standalone = self.client.post(reverse("container_selection_mode1"), self.valid_data)
            seo = self.client.post(reverse("container_selection_calculator"), self.valid_data)

        self.assertEqual(standalone.status_code, 200)
        self.assertEqual(seo.status_code, 200)
        self.assertEqual(seo.context["result"].max_quantity, standalone.context["result"].max_quantity)
        self.assertEqual(seo.context["analysis_report"], standalone.context["analysis_report"])
        self.assertEqual(seo.context["threejs_scene"], standalone.context["threejs_scene"])

    def test_each_rotation_restriction_uses_the_shared_engine_rules(self):
        product = (180.0, 120.0, 80.0)
        container = (600.0, 400.0, 320.0)

        for enabled_field, flags in (
            ("r1", (1, 0, 0)),
            ("r2", (0, 1, 0)),
            ("r3", (0, 0, 1)),
        ):
            data = {key: value for key, value in self.valid_data.items() if key not in ("r1", "r2", "r3")}
            data[enabled_field] = "on"
            with self.subTest(enabled_field=enabled_field), self.settings(MEDIA_ROOT=self.media_root):
                response = self.client.post(reverse("container_selection_calculator"), data)
                self.assertEqual(response.status_code, 200)
                self.assertIsNotNone(response.context["result"])
                self.assertEqual(
                    response.context["result"].max_quantity,
                    compute_max_quantity_only(product, container, *flags),
                )

    def test_manual_container_dimensions_and_shared_validation_work(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            valid = self.client.post(reverse("container_selection_calculator"), self.valid_data)
            invalid = self.client.post(
                reverse("container_selection_calculator"),
                {**self.valid_data, "box_l": "-1", "product_weight": "-5"},
            )

        self.assertIsNotNone(valid.context["result"])
        self.assertEqual(valid.context["threejs_scene"]["container"]["length"], 600.0)
        self.assertIsNone(invalid.context["result"])
        self.assertIn("box_l", invalid.context["form"].errors)
        self.assertIn("product_weight", invalid.context["form"].errors)
        self.assertContains(invalid, "data-tool-validation-errors")

    def test_seo_catalogues_are_public_only_even_for_authenticated_owner(self):
        owner = get_user_model().objects.create_user(username="private-owner", password="secret")
        public_product_catalogue = ProductCatalogue.objects.create(name="Public products", is_public=True)
        private_product_catalogue = ProductCatalogue.objects.create(
            name="Private customer products", is_public=False, owner=owner
        )
        public_product = Product.objects.create(
            catalogue=public_product_catalogue,
            product_id="PUBLIC-PRODUCT",
            product_length=100,
            product_width=80,
            product_height=50,
        )
        private_product = Product.objects.create(
            catalogue=private_product_catalogue,
            product_id="PRIVATE-PRODUCT",
            product_length=90,
            product_width=70,
            product_height=40,
        )
        public_packaging_catalogue = PackagingCatalogue.objects.create(name="Public boxes", is_public=True)
        private_packaging_catalogue = PackagingCatalogue.objects.create(
            name="Private customer boxes", is_public=False, owner=owner
        )
        public_box = PackagingMaterial.objects.create(
            catalogue=public_packaging_catalogue,
            part_number="PUBLIC-BOX",
            part_description="Public RSC box",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Corrugated board",
            part_length=600,
            part_width=400,
            part_height=300,
        )
        private_box = PackagingMaterial.objects.create(
            catalogue=private_packaging_catalogue,
            part_number="PRIVATE-BOX",
            part_description="Private customer box",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Corrugated board",
            part_length=500,
            part_width=300,
            part_height=250,
        )

        self.client.force_login(owner)
        query = {
            "mode": "single",
            "action": "refresh",
            "product_source": "catalogue",
            "product_catalogue_id": str(public_product_catalogue.pk),
            "container_source": "catalogue",
            "catalogue_id": str(public_packaging_catalogue.pk),
        }
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(reverse("container_selection_calculator"), query)
            crafted = self.client.get(
                reverse("container_selection_calculator"),
                {
                    **query,
                    "product_catalogue_id": str(private_product_catalogue.pk),
                    "selected_product_id": str(private_product.pk),
                    "catalogue_id": str(private_packaging_catalogue.pk),
                    "container_id": str(private_box.pk),
                },
            )

        self.assertEqual(set(response.context["products"]), {public_product})
        self.assertEqual(set(response.context["materials"]), {public_box})
        self.assertNotContains(response, "Private customer products")
        self.assertNotContains(response, "PRIVATE-PRODUCT")
        self.assertNotContains(response, "Private customer boxes")
        self.assertNotContains(response, "PRIVATE-BOX")
        self.assertIsNone(crafted.context["selected_product"])
        self.assertIsNone(crafted.context["selected_material"])
        self.assertFalse(crafted.context["products"].exists())
        self.assertFalse(crafted.context["materials"].exists())

    def test_threejs_rsc_controls_and_snapshot_pdf_path_remain_shared(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            initial = self.client.get(reverse("container_selection_calculator"))
            missing = self.client.get(reverse("container_selection_export_pdf"))
            pdf = self.client.post(
                reverse("container_selection_export_pdf"),
                {
                    "threejs_snapshot": self.PNG_DATA_URL,
                    "threejs_view_label": "Current interactive 3D view - top view",
                },
            )

        scene = initial.context["threejs_scene"]
        self.assertTrue(scene["rsc"]["enabled"])
        self.assertEqual(scene["rsc"]["openingAngleDeg"], 130)
        self.assertContains(initial, "js/container_threejs_viewer.js")
        for view_name in ("reset", "top", "front", "side"):
            self.assertContains(initial, f'data-container-threejs-view="{view_name}"')
        self.assertContains(initial, 'data-container-threejs-toggle="container"')
        self.assertContains(initial, "data-container-threejs-pdf-button")
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_sitemap_internal_links_and_other_container_consumers_render(self):
        sitemap = self.client.get(reverse("sitemap"))
        page = self.client.get(reverse("container_selection_calculator"))
        add_step = self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "container"},
        )
        workflow = self.client.get(reverse("full_packaging_mode"))
        multi_product = self.client.get(reverse("multi_product_container_selection"))

        self.assertEqual(sitemap.status_code, 200)
        self.assertContains(sitemap, "/tools/box-size-calculator/")
        for url_name in (
            "home",
            "full_packaging_mode",
            "palletization_calculator",
            "bag_selection_calculator",
            "transport_container_calculator",
        ):
            self.assertContains(page, reverse(url_name))
        self.assertEqual(add_step.status_code, 302)
        self.assertEqual(workflow.status_code, 200)
        self.assertContains(workflow, "data-container-tool-root")
        self.assertEqual(multi_product.status_code, 200)
        self.assertContains(multi_product, "js/container_threejs_viewer.js")
        self.assertContains(multi_product, 'data-container-threejs-toggle="container"')
