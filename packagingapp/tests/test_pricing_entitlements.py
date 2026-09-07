from __future__ import annotations

from datetime import timedelta
from io import BytesIO
import shutil
import tempfile
from unittest.mock import patch
import zipfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from packagingapp.entitlements import (
    AI_ASSISTANT,
    BATCH_EXCEL_EXPORT,
    PDF_REPORTS,
    PRIVATE_CATALOGUES,
    PLUS_IMAGE_LIMIT_BYTES,
    PREMIUM_IMAGE_LIMIT_BYTES,
    catalogue_image_limit_bytes,
    effective_plan,
    expert_support_hours,
    has_feature,
)
from packagingapp.models import (
    PackagingCatalogue,
    PackagingMaterial,
    ProductCatalogue,
    Product,
    UserSubscription,
)
from packagingapp.services.catalogue_media import (
    MAX_RAW_IMAGE_BYTES,
    CatalogueMediaError,
    catalogue_image_usage_bytes,
    optimize_catalogue_image,
    prepare_catalogue_image,
)
from packagingapp.services.material_image_import import import_material_images_zip


def make_image_bytes(size=(80, 50), image_format="PNG"):
    output = BytesIO()
    Image.new("RGB", size, (34, 139, 94)).save(output, format=image_format)
    return output.getvalue()


class EntitlementPlanResolutionTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def user_with_plan(self, username, plan, **subscription_kwargs):
        user = self.User.objects.create_user(username=username)
        UserSubscription.objects.create(user=user, plan=plan, **subscription_kwargs)
        return user

    def test_effective_plan_resolution_and_feature_matrix(self):
        no_subscription = self.User.objects.create_user(username="no-subscription")
        explicit_free = self.user_with_plan("explicit-free", UserSubscription.Plan.FREE)
        plus = self.user_with_plan("plus", UserSubscription.Plan.PLUS)
        premium = self.user_with_plan("premium", UserSubscription.Plan.PREMIUM)
        expired = self.user_with_plan(
            "expired",
            UserSubscription.Plan.PREMIUM,
            current_period_end=timezone.now() - timedelta(seconds=1),
        )
        inactive = self.user_with_plan(
            "inactive",
            UserSubscription.Plan.PLUS,
            status=UserSubscription.Status.INACTIVE,
        )
        superuser = self.User.objects.create_superuser(username="root", email="root@example.com")

        self.assertEqual(effective_plan(AnonymousUser()), UserSubscription.Plan.FREE)
        self.assertEqual(effective_plan(no_subscription), UserSubscription.Plan.FREE)
        self.assertEqual(effective_plan(explicit_free), UserSubscription.Plan.FREE)
        self.assertEqual(effective_plan(plus), UserSubscription.Plan.PLUS)
        self.assertEqual(effective_plan(premium), UserSubscription.Plan.PREMIUM)
        self.assertEqual(effective_plan(expired), UserSubscription.Plan.FREE)
        self.assertEqual(effective_plan(inactive), UserSubscription.Plan.FREE)
        self.assertEqual(effective_plan(superuser), UserSubscription.Plan.PREMIUM)

        self.assertTrue(has_feature(plus, PRIVATE_CATALOGUES))
        self.assertTrue(has_feature(plus, PDF_REPORTS))
        self.assertTrue(has_feature(plus, AI_ASSISTANT))
        self.assertFalse(has_feature(plus, BATCH_EXCEL_EXPORT))
        self.assertTrue(has_feature(premium, BATCH_EXCEL_EXPORT))
        self.assertTrue(has_feature(superuser, BATCH_EXCEL_EXPORT))

    def test_plan_limits_and_support_hours(self):
        free = self.User.objects.create_user(username="limit-free")
        plus = self.user_with_plan("limit-plus", UserSubscription.Plan.PLUS)
        premium = self.user_with_plan("limit-premium", UserSubscription.Plan.PREMIUM)
        staff = self.User.objects.create_user(username="limit-staff", is_staff=True)

        self.assertEqual(catalogue_image_limit_bytes(free), 0)
        self.assertEqual(catalogue_image_limit_bytes(plus), PLUS_IMAGE_LIMIT_BYTES)
        self.assertEqual(catalogue_image_limit_bytes(premium), PREMIUM_IMAGE_LIMIT_BYTES)
        self.assertIsNone(catalogue_image_limit_bytes(staff))
        self.assertEqual(expert_support_hours(plus), 1)
        self.assertEqual(expert_support_hours(premium), 5)


class CatalogueEntitlementTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.free = User.objects.create_user(username="catalogue-free")
        self.plus = User.objects.create_user(username="catalogue-plus")
        self.premium = User.objects.create_user(username="catalogue-premium")
        self.superuser = User.objects.create_superuser(username="catalogue-admin", email="admin@example.com")
        UserSubscription.objects.create(user=self.plus, plan=UserSubscription.Plan.PLUS)
        UserSubscription.objects.create(user=self.premium, plan=UserSubscription.Plan.PREMIUM)

    def test_private_catalogue_creation_matrix(self):
        cases = (
            (None, False, "anon"),
            (self.free, False, "free"),
            (self.plus, True, "plus"),
            (self.premium, True, "premium"),
            (self.superuser, True, "admin"),
        )
        for user, allowed, suffix in cases:
            with self.subTest(user=suffix, catalogue="packaging"):
                self.client.logout()
                if user:
                    self.client.force_login(user)
                response = self.client.post(reverse("create_catalogue"), {"name": f"Packaging {suffix}"})
                self.assertEqual(PackagingCatalogue.objects.filter(name=f"Packaging {suffix}").exists(), allowed)
                if not allowed:
                    self.assertRedirects(response, f"{reverse('pricing')}?feature=catalogues", fetch_redirect_response=False)

            with self.subTest(user=suffix, catalogue="product"):
                self.client.logout()
                if user:
                    self.client.force_login(user)
                response = self.client.post(reverse("create_product_catalogue"), {"name": f"Products {suffix}"})
                self.assertEqual(ProductCatalogue.objects.filter(name=f"Products {suffix}").exists(), allowed)
                if not allowed:
                    self.assertRedirects(response, f"{reverse('pricing')}?feature=catalogues", fetch_redirect_response=False)

    def test_downgraded_owner_keeps_read_only_visibility_and_all_mutations_are_blocked(self):
        packaging = PackagingCatalogue.objects.create(name="Free Private Packaging", owner=self.free, is_public=False)
        material = PackagingMaterial.objects.create(
            catalogue=packaging,
            part_number="FREE-1",
            part_description="Read only",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Board",
            part_length=100,
            part_width=80,
            part_height=60,
        )
        products = ProductCatalogue.objects.create(name="Free Private Products", owner=self.free, is_public=False)
        product = Product.objects.create(
            catalogue=products,
            product_id="FREE-PRODUCT-1",
            product_name="Read only product",
            product_length=100,
            product_width=80,
            product_height=60,
        )
        self.client.force_login(self.free)

        packaging_detail = self.client.get(reverse("catalogue_detail", args=[packaging.pk]))
        product_detail = self.client.get(reverse("product_catalogue_detail", args=[products.pk]))
        self.assertContains(packaging_detail, "read-only on the Free plan")
        self.assertContains(product_detail, "read-only on the Free plan")

        blocked_routes = (
            ("get", reverse("edit_catalogue", args=[packaging.pk])),
            ("post", reverse("delete_catalogue", args=[packaging.pk])),
            ("get", reverse("add_material", args=[packaging.pk])),
            ("get", reverse("edit_material", args=[packaging.pk, material.pk])),
            ("post", reverse("delete_material", args=[packaging.pk, material.pk])),
            ("get", reverse("upload_excel", args=[packaging.pk])),
            ("get", reverse("download_excel_template", args=[packaging.pk])),
            ("get", reverse("upload_drawings_for_catalogue", args=[packaging.pk])),
            ("get", reverse("upload_material_images_for_catalogue", args=[packaging.pk])),
            ("get", reverse("export_catalogue_excel", args=[packaging.pk])),
            ("get", reverse("edit_product_catalogue", args=[products.pk])),
            ("post", reverse("delete_product_catalogue", args=[products.pk])),
            ("get", reverse("add_product", args=[products.pk])),
            ("get", reverse("edit_product", args=[products.pk, product.pk])),
            ("post", reverse("delete_product", args=[products.pk, product.pk])),
            ("get", reverse("upload_products_excel", args=[products.pk])),
            ("get", reverse("download_product_excel_template", args=[products.pk])),
            ("get", reverse("upload_product_images_zip", args=[products.pk])),
            ("get", reverse("export_product_catalogue_excel", args=[products.pk])),
        )
        for method, url in blocked_routes:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertRedirects(response, f"{reverse('pricing')}?feature=catalogues", fetch_redirect_response=False)

    def test_public_catalogues_remain_visible_to_anonymous_and_free_users(self):
        packaging = PackagingCatalogue.objects.create(name="Platform Packaging", is_public=True)
        products = ProductCatalogue.objects.create(name="Platform Products", is_public=True)
        for user in (None, self.free):
            self.client.logout()
            if user:
                self.client.force_login(user)
            self.assertContains(self.client.get(reverse("catalogue_list")), packaging.name)
            self.assertEqual(self.client.get(reverse("catalogue_detail", args=[packaging.pk])).status_code, 200)
            self.assertContains(self.client.get(reverse("product_catalogues")), products.name)
            self.assertEqual(self.client.get(reverse("product_catalogue_detail", args=[products.pk])).status_code, 200)


class ExportEntitlementTests(TestCase):
    pdf_routes = (
        "container_selection_export_pdf",
        "container_selection_export_optimal_pdf",
        "bag_selection_export_pdf",
        "bag_selection_export_optimal_pdf",
        "palletization_export_pdf",
        "container_tool_export_pdf",
        "corrugated_material_strength_export_pdf",
        "full_packaging_export_pdf",
    )

    def setUp(self):
        User = get_user_model()
        self.free = User.objects.create_user(username="export-free")
        self.plus = User.objects.create_user(username="export-plus")
        self.premium = User.objects.create_user(username="export-premium")
        self.superuser = User.objects.create_superuser(username="export-admin", email="export@example.com")
        UserSubscription.objects.create(user=self.plus, plan=UserSubscription.Plan.PLUS)
        UserSubscription.objects.create(user=self.premium, plan=UserSubscription.Plan.PREMIUM)
        self.product_catalogue = ProductCatalogue.objects.create(name="Batch Products", is_public=True)
        self.packaging_catalogue = PackagingCatalogue.objects.create(name="Batch Packaging", is_public=True)

    def test_every_pdf_endpoint_blocks_anonymous_and_free_but_passes_paid_plans(self):
        for user in (None, self.free):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for route_name in self.pdf_routes:
                with self.subTest(user=getattr(user, "username", "anonymous"), route=route_name):
                    self.assertEqual(self.client.get(reverse(route_name)).status_code, 403)
            self.assertEqual(
                self.client.get(reverse("full_packaging_case_export_pdf", args=["sample-case"])).status_code,
                403,
            )

        fake_pdf = BytesIO(b"%PDF-1.4\n%%EOF")
        with patch("packagingapp.views.full_packaging.build_full_packaging_pdf", return_value=fake_pdf):
            for user in (self.plus, self.premium, self.superuser):
                self.client.force_login(user)
                for route_name in self.pdf_routes:
                    with self.subTest(user=user.username, route=route_name):
                        response = self.client.get(reverse(route_name))
                        self.assertNotEqual(response.status_code, 403)
                        fake_pdf.seek(0)
                response = self.client.get(reverse("full_packaging_case_export_pdf", args=["sample-case"]))
                self.assertNotEqual(response.status_code, 403)
                fake_pdf.seek(0)

    def test_blocked_pdf_does_not_capture_threejs_snapshot(self):
        self.client.force_login(self.free)
        session = self.client.session
        session["palletization_last_export"] = {"result": {}}
        session.save()
        with patch("packagingapp.views.palletization.save_threejs_snapshot_from_request") as snapshot:
            response = self.client.post(reverse("palletization_export_pdf"), {"threejs_snapshot": "ignored"})
        self.assertEqual(response.status_code, 403)
        snapshot.assert_not_called()

    def test_batch_excel_is_premium_only_and_batch_analysis_remains_free(self):
        post_data = {
            "product_catalogue_id": str(self.product_catalogue.pk),
            "packaging_catalogue_id": str(self.packaging_catalogue.pk),
        }
        export_routes = ("multi_product_container_export_excel", "multi_product_bag_export_excel")
        run_routes = ("multi_product_container_run", "multi_product_bag_run")

        for user in (None, self.free, self.plus):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for route_name in export_routes:
                response = self.client.post(reverse(route_name), post_data)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["pricing_url"], f"{reverse('pricing')}?feature=batch_excel")
            for route_name in run_routes:
                response = self.client.post(reverse(route_name), post_data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["ok"])

        for user in (self.premium, self.superuser):
            self.client.force_login(user)
            for route_name in export_routes:
                response = self.client.post(reverse(route_name), post_data)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response["Content-Type"],
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

    def test_plus_can_use_catalogue_excel_while_batch_result_excel_stays_locked(self):
        private_packaging = PackagingCatalogue.objects.create(
            name="Plus Private Packaging",
            owner=self.plus,
            is_public=False,
        )
        private_products = ProductCatalogue.objects.create(
            name="Plus Private Products",
            owner=self.plus,
            is_public=False,
        )
        self.client.force_login(self.plus)
        self.assertEqual(
            self.client.get(reverse("export_catalogue_excel", args=[private_packaging.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("export_product_catalogue_excel", args=[private_products.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                reverse("multi_product_container_export_excel"),
                {
                    "product_catalogue_id": private_products.pk,
                    "packaging_catalogue_id": private_packaging.pk,
                },
            ).status_code,
            403,
        )


class PricingPageTests(TestCase):
    def test_pricing_page_and_contextual_messages_are_public(self):
        response = self.client.get(reverse("pricing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$0")
        self.assertContains(response, "$99")
        self.assertContains(response, "$299")
        for feature, text in (
            ("pdf", "PDF reports are included"),
            ("catalogues", "Private Product and Packaging Catalogues"),
            ("batch_excel", "Premium feature"),
        ):
            contextual = self.client.get(reverse("pricing"), {"feature": feature})
            self.assertContains(contextual, text)
            self.assertContains(contextual, f'data-pricing-feature="{feature}"')

    def test_pricing_is_in_public_and_application_navigation(self):
        self.assertContains(self.client.get(reverse("company_home")), 'href="/pricing/"')
        self.assertContains(self.client.get(reverse("home")), "Pricing &amp; Plans")

    def test_public_result_pages_render_locked_pdf_links_without_active_export_forms(self):
        route_pairs = (
            ("container_selection_calculator", "container_selection_export_pdf"),
            ("bag_selection_calculator", "bag_selection_export_pdf"),
            ("palletization_calculator", "palletization_export_pdf"),
            ("transport_container_calculator", "container_tool_export_pdf"),
        )
        for page_route, export_route in route_pairs:
            with self.subTest(page=page_route):
                response = self.client.get(reverse(page_route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'{reverse("pricing")}?feature=pdf')
                self.assertNotContains(response, f'formaction="{reverse(export_route)}"')

    def test_account_plan_label_and_locked_batch_action_match_effective_plan(self):
        User = get_user_model()
        free = User.objects.create_user(username="nav-free")
        plus = User.objects.create_user(username="nav-plus")
        UserSubscription.objects.create(user=plus, plan=UserSubscription.Plan.PLUS)

        self.client.force_login(free)
        self.assertContains(self.client.get(reverse("home")), "Free · Upgrade")
        batch = self.client.get(reverse("multi_product_container_selection"))
        self.assertContains(batch, "Export to Excel · Premium")
        self.assertNotContains(batch, 'id="exportBtn"')

        self.client.force_login(plus)
        self.assertContains(self.client.get(reverse("home")), ">Plus</span>", html=False)


class CatalogueMediaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="media-plus")
        UserSubscription.objects.create(user=self.user, plan=UserSubscription.Plan.PLUS)
        self.media_root = tempfile.mkdtemp(prefix="kollipack-entitlement-media-")

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_image_is_validated_optimized_and_not_upscaled(self):
        upload = SimpleUploadedFile("small.png", make_image_bytes((40, 20)), content_type="image/png")
        optimized = optimize_catalogue_image(upload)
        self.assertTrue(optimized.name.endswith(".webp"))
        with Image.open(optimized) as image:
            self.assertEqual(image.size, (40, 20))
            self.assertEqual(image.format, "WEBP")

    def test_normal_catalogue_form_upload_uses_shared_optimizer(self):
        self.client.force_login(self.user)
        with self.settings(MEDIA_ROOT=self.media_root):
            response = self.client.post(
                reverse("create_product_catalogue"),
                {
                    "name": "Optimized Cover",
                    "picture": SimpleUploadedFile(
                        "cover.png",
                        make_image_bytes((120, 70)),
                        content_type="image/png",
                    ),
                },
            )
        self.assertEqual(response.status_code, 302)
        catalogue = ProductCatalogue.objects.get(name="Optimized Cover")
        self.assertTrue(catalogue.picture.name.endswith(".webp"))

    def test_oversized_and_quota_crossing_uploads_fail_cleanly(self):
        oversized = SimpleUploadedFile("too-large.png", b"x" * (MAX_RAW_IMAGE_BYTES + 1), content_type="image/png")
        with self.assertRaisesMessage(CatalogueMediaError, "5 MB or smaller"):
            optimize_catalogue_image(oversized)

        upload = SimpleUploadedFile("valid.png", make_image_bytes(), content_type="image/png")
        with patch("packagingapp.services.catalogue_media.catalogue_image_usage_bytes", return_value=PLUS_IMAGE_LIMIT_BYTES):
            with self.assertRaisesMessage(CatalogueMediaError, "exceed your catalogue storage limit"):
                prepare_catalogue_image(upload, self.user)

    def test_usage_follows_current_references_after_replacement_and_deletion(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            catalogue = PackagingCatalogue.objects.create(name="Media Catalogue", owner=self.user, is_public=False)
            catalogue.picture.save("old.png", ContentFile(make_image_bytes((20, 20))), save=True)
            first_usage = catalogue_image_usage_bytes(self.user)
            self.assertGreater(first_usage, 0)

            catalogue.picture.save("new.png", ContentFile(make_image_bytes((30, 30))), save=True)
            current_size = catalogue.picture.size
            self.assertEqual(catalogue_image_usage_bytes(self.user), current_size)

            catalogue.delete()
            self.assertEqual(catalogue_image_usage_bytes(self.user), 0)

    def test_zip_image_import_enforces_quota(self):
        catalogue = PackagingCatalogue.objects.create(name="ZIP Catalogue", owner=self.user, is_public=False)
        PackagingMaterial.objects.create(
            catalogue=catalogue,
            part_number="ZIP-1",
            part_description="ZIP image",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Board",
            part_length=100,
            part_width=80,
            part_height=60,
        )
        archive_bytes = BytesIO()
        with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("images/ZIP-1.png", make_image_bytes())
        archive_bytes.seek(0)

        with patch("packagingapp.services.catalogue_media.catalogue_image_usage_bytes", return_value=PLUS_IMAGE_LIMIT_BYTES):
            with self.assertRaises(CatalogueMediaError):
                import_material_images_zip(archive_bytes, catalogue, acting_user=self.user)
