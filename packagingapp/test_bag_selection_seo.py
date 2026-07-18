import shutil
import tempfile

from django.test import TestCase
from django.urls import reverse


class BagSelectionSeoCalculatorTests(TestCase):
    valid_data = {
        "mode": "single",
        "action": "run_single",
        "product_source": "manual",
        "product_catalogue_id": "",
        "selected_product_id": "",
        "product_l": "180",
        "product_w": "120",
        "product_h": "40",
        "product_weight": "250",
        "desired_qty": "4",
        "bag_source": "manual",
        "catalogue_id": "",
        "bag_id": "",
        "bag_length": "450",
        "bag_width": "330",
        "bag_weight": "18",
        "bag_max_payload": "5000",
    }

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="kollipack-bag-seo-test-")

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_public_get_renders_prefilled_live_engine_result_and_metadata(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(reverse("bag_selection_calculator"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_initial_example"])
        self.assertEqual(response.context["bag_config"]["product_l"], "180")
        self.assertEqual(response.context["bag_config"]["product_w"], "120")
        self.assertEqual(response.context["bag_config"]["product_h"], "40")
        self.assertEqual(response.context["bag_config"]["desired_qty"], "4")
        self.assertEqual(response.context["bag_config"]["bag_length"], "450")
        self.assertEqual(response.context["bag_config"]["bag_width"], "330")
        self.assertEqual(response.context["bag_config"]["product_weight"], "250")
        self.assertEqual(response.context["bag_config"]["bag_weight"], "18")
        self.assertEqual(response.context["bag_config"]["bag_max_payload"], "5000")
        self.assertIsNotNone(response.context["result"])
        self.assertIsNotNone(response.context["analysis_report"])
        self.assertGreater(response.context["analysis_report"]["max_quantity"], 0)
        self.assertTrue(response.context["image_url"])
        self.assertContains(response, "Live example loaded")
        self.assertContains(response, 'data-bag-sealing-allowance')
        self.assertContains(response, 'data-bag-fit-tolerance')
        self.assertContains(response, 'data-preserve-tool-scroll="bag-selection-seo"', count=1)
        self.assertContains(response, "Download PDF report")
        self.assertContains(response, '<link rel="canonical" href="http://testserver/tools/bag-size-calculator/">', html=True)
        self.assertContains(response, 'property="og:title"')
        self.assertContains(response, 'type="application/ld+json"')

    def test_seo_and_standalone_post_return_equivalent_shared_results(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            standalone = self.client.post(reverse("bag_selection_mode1"), self.valid_data)
            seo = self.client.post(reverse("bag_selection_calculator"), self.valid_data)

        self.assertEqual(standalone.status_code, 200)
        self.assertEqual(seo.status_code, 200)
        standalone_result = {**standalone.context["result"]}
        seo_result = {**seo.context["result"]}
        standalone_result.pop("image_rel_path", None)
        seo_result.pop("image_rel_path", None)
        self.assertEqual(seo_result, standalone_result)
        self.assertEqual(seo.context["analysis_report"], standalone.context["analysis_report"])

    def test_invalid_dimensions_and_weights_use_shared_form_validation(self):
        invalid_data = {
            **self.valid_data,
            "product_l": "-1",
            "product_weight": "-5",
            "bag_max_payload": "-10",
        }

        for url_name in ("bag_selection_mode1", "bag_selection_calculator"):
            with self.subTest(url_name=url_name):
                response = self.client.post(reverse(url_name), invalid_data)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.context["result"])
                self.assertIn("product_l", response.context["form"].errors)
                self.assertIn("product_weight", response.context["form"].errors)
                self.assertIn("bag_max_payload", response.context["form"].errors)
                self.assertContains(response, "data-tool-validation-errors")

    def test_initial_shared_pdf_export_remains_available(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            initial = self.client.get(reverse("bag_selection_calculator"))
            response = self.client.get(reverse("bag_selection_export_pdf"))

        self.assertEqual(initial.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_public_sitemap_and_navigation_include_both_calculators(self):
        sitemap = self.client.get(reverse("sitemap"))
        page = self.client.get(reverse("bag_selection_calculator"))

        self.assertEqual(sitemap.status_code, 200)
        self.assertContains(sitemap, "/tools/palletization-calculator/")
        self.assertContains(sitemap, "/tools/bag-size-calculator/")
        self.assertContains(page, reverse("palletization_calculator"))
        self.assertContains(page, reverse("bag_selection_calculator"))

    def test_workflow_and_multi_product_bag_consumers_still_render(self):
        add_step = self.client.post(
            reverse("full_packaging_mode"),
            {"action": "add_step", "after_index": "start", "step_type": "bag"},
        )
        workflow = self.client.get(reverse("full_packaging_mode"))
        multi_product = self.client.get(reverse("multi_product_bag_selection"))

        self.assertEqual(add_step.status_code, 302)
        self.assertEqual(workflow.status_code, 200)
        self.assertContains(workflow, "data-bag-tool-root")
        self.assertContains(workflow, "data-bag-sealing-allowance")
        self.assertContains(workflow, "data-bag-fit-tolerance")
        self.assertEqual(multi_product.status_code, 200)
        self.assertContains(multi_product, "Multiple Product Bag Selection")
