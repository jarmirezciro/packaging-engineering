from django.test import SimpleTestCase
from django.urls import reverse

from packagingapp.forms import ContactForm


class KolliLabsHomepageTests(SimpleTestCase):
    def test_company_home_uses_approved_positioning_and_accessible_structure(self):
        response = self.client.get(reverse("company_home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "marketing/about.html")
        self.assertContains(
            response,
            "<title>KolliLabs | Packaging, Logistics and Transport Tools</title>",
            html=True,
        )
        self.assertContains(
            response,
            "Practical software, consultancy and education for packaging, palletization, transport utilization and logistics operations.",
            count=1,
        )
        self.assertContains(
            response,
            "<h1>From packaging to transport, make every load count.</h1>",
            html=True,
        )
        self.assertContains(response, "<h1", count=1)
        self.assertContains(response, "Available now", count=2)
        self.assertContains(response, "A broader KolliLabs toolkit")
        self.assertContains(response, "Let’s improve the next load.")
        self.assertNotContains(response, "Main software product")

    def test_navigation_and_homepage_anchors_keep_their_destinations(self):
        response = self.client.get(reverse("company_home"))

        for anchor in ("why", "software", "consultancy", "education", "contact"):
            self.assertContains(response, f'id="{anchor}"')

        for view_name in (
            "pricing",
            "blog_list",
            "palletization_calculator",
            "bag_selection_calculator",
            "container_selection_calculator",
            "transport_container_calculator",
            "home",
        ):
            self.assertContains(response, f'href="{reverse(view_name)}"')

    def test_about_alias_preserves_the_canonical_homepage(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "marketing/about.html")
        self.assertContains(response, "From packaging to transport, make every load count.")
        self.assertContains(
            response,
            f'<link rel="canonical" href="http://testserver{reverse("company_home")}">',
            html=True,
        )

    def test_contact_form_keeps_behavior_with_revised_interest_choices(self):
        expected_choices = [
            ("KolliPack app", "KolliPack app"),
            ("Packaging and logistics consultancy", "Packaging and logistics consultancy"),
            ("Palletization and transport utilization", "Palletization and transport utilization"),
            ("Training and education", "Training and education"),
            ("Software idea or partnership", "Software idea or partnership"),
            ("Other", "Other"),
        ]

        self.assertEqual(ContactForm.AREA_CHOICES, expected_choices)
        response = self.client.get(reverse("company_home"))
        for field_name in ("name", "email", "company", "area_of_interest", "message", "consent"):
            self.assertContains(response, f'for="id_{field_name}"')
            self.assertContains(response, f'name="{field_name}"')

        valid_form = ContactForm(
            data={
                "name": "Test User",
                "email": "test@example.com",
                "company": "Example Company",
                "area_of_interest": "Palletization and transport utilization",
                "message": "Please contact me about a packaging analysis.",
                "consent": True,
                "website": "",
            }
        )
        self.assertTrue(valid_form.is_valid(), valid_form.errors)

        honeypot_form = ContactForm(data={**valid_form.data, "website": "spam"})
        self.assertFalse(honeypot_form.is_valid())
        self.assertIn("website", honeypot_form.errors)

    def test_kollipack_remains_a_separate_application_surface(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")
        self.assertNotContains(response, "From packaging to transport, make every load count.")
