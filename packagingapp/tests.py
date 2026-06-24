from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import PackagingCatalogue, ProductCatalogue


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
