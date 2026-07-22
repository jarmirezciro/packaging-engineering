import json

from django.test import TestCase
from django.urls import reverse

from packagingapp.models import PackagingCatalogue, PackagingMaterial, Product, ProductCatalogue


class BagThreeJsMigrationTests(TestCase):
    snapshot = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    single_data = {
        "mode": "single",
        "action": "run_single",
        "product_source": "manual",
        "product_l": "180",
        "product_w": "120",
        "product_h": "40",
        "product_weight": "250",
        "desired_qty": "4",
        "bag_source": "manual",
        "bag_length": "450",
        "bag_width": "330",
        "bag_weight": "18",
        "bag_max_payload": "5000",
    }

    def test_single_uses_json_safe_threejs_scene_without_png(self):
        response = self.client.post(reverse("bag_selection_mode1"), self.single_data)
        self.assertEqual(response.status_code, 200)
        scene = response.context["threejs_scene"]
        self.assertEqual(scene["packageType"], "bag")
        self.assertEqual(scene["mode"], "single")
        self.assertEqual(scene["bag"]["flatLength"], 450)
        self.assertEqual(scene["bag"]["flatWidth"], 330)
        self.assertEqual(scene["bag"]["openingSide"], "width")
        self.assertGreater(len(scene["products"]), 0)
        self.assertIsNone(response.context["image_url"])
        self.assertNotContains(response, '<img src="/media/bag_selection/')
        json.dumps(scene)

    def test_workflow_single_uses_equivalent_scene(self):
        standalone = self.client.post(reverse("bag_selection_mode1"), self.single_data)
        self.client.post(reverse("full_packaging_mode"), {
            "action": "add_step", "step_type": "bag", "after_index": "start",
        })
        workflow_post = {
            "action": "run_step",
            "index": "0",
            **{f"{key}_0": value for key, value in self.single_data.items()},
        }
        workflow_post["action_0"] = "run_single"
        self.client.post(reverse("full_packaging_mode"), workflow_post)
        step = self.client.session["full_packaging_mode_session"]["steps"][0]
        self.assertEqual(step["threejs_scene"], standalone.context["threejs_scene"])
        self.assertEqual(step["pending_result"]["render_data"], standalone.context["threejs_scene"])
        json.dumps(step)

    def test_optimal_selected_candidate_and_pdf_use_threejs_scene(self):
        packaging = PackagingCatalogue.objects.create(name="Optimal bags", is_public=True)
        material = PackagingMaterial.objects.create(
            catalogue=packaging,
            part_number="OPT-BAG-1",
            part_description="Optimal Three.js bag",
            packaging_type="BAG",
            part_length=600,
            part_width=400,
            part_height=1,
        )
        data = {
            **self.single_data,
            "mode": "optimal",
            "action": "select_candidate",
            "bag_source": "catalogue",
            "catalogue_id": str(packaging.pk),
            "bag_id": str(material.pk),
            "desired_qty": "4",
        }
        response = self.client.post(reverse("bag_selection_mode1"), data)
        self.assertEqual(response.status_code, 200)
        scene = response.context["threejs_scene"]
        self.assertEqual(scene["mode"], "optimal")
        self.assertEqual(scene["bag"]["flatLength"], 600)
        self.assertEqual(scene["bag"]["flatWidth"], 400)
        self.assertEqual(response.context["result"]["threejs_scene"], scene)
        pdf = self.client.post(reverse("bag_selection_export_optimal_pdf"), {
            "optimal_export": "1", "threejs_snapshot": self.snapshot,
        })
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_multi_product_bag_uses_shared_threejs_viewer_and_scene(self):
        products = ProductCatalogue.objects.create(name="Bag products", is_public=True)
        product = Product.objects.create(
            catalogue=products,
            product_id="BAG-3D-1",
            product_name="Bag 3D product",
            product_length=100,
            product_width=80,
            product_height=20,
            desired_qty=4,
        )
        packaging = PackagingCatalogue.objects.create(name="Bag materials", is_public=True)
        material = PackagingMaterial.objects.create(
            catalogue=packaging,
            part_number="BAG-3D-MAT",
            part_description="Three.js bag",
            packaging_type="BAG",
            part_length=300,
            part_width=220,
            part_height=1,
        )

        page = self.client.get(reverse("multi_product_bag_selection"))
        self.assertContains(page, "js/container_threejs_viewer.js")
        self.assertContains(page, 'data-container-threejs-view="reset"')
        self.assertNotContains(page, "data.image_url")
        draw = self.client.post(reverse("multi_product_bag_draw"), {
            "product_id": product.pk,
            "bag_id": material.pk,
        })
        self.assertEqual(draw.status_code, 200)
        payload = draw.json()
        self.assertEqual(payload["threejs_scene"]["packageType"], "bag")
        self.assertNotIn("image_url", payload)
        json.dumps(payload)
