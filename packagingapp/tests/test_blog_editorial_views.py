from __future__ import annotations

import json

from django.test import SimpleTestCase
from django.urls import reverse

from .test_blog_editorial_metadata import EXPECTED_ARTICLES, load_metadata


class BlogEditorialViewTests(SimpleTestCase):
    def test_listing_renders_all_editorial_titles_and_metadata_alt_text(self):
        response = self.client.get(reverse("blog_list"))

        self.assertEqual(response.status_code, 200)
        for slug, expected in EXPECTED_ARTICLES.items():
            with self.subTest(slug=slug):
                metadata = load_metadata(slug)
                self.assertContains(response, expected["title"], count=1)
                self.assertContains(response, f'href="{reverse("blog_detail", kwargs={"slug": slug})}"')
                self.assertContains(response, f'alt="{metadata["thumbnail_alt"]}"')

    def test_detail_pages_keep_h1_seo_canonical_og_and_schema_contracts(self):
        for slug, expected in EXPECTED_ARTICLES.items():
            with self.subTest(slug=slug):
                response = self.client.get(reverse("blog_detail", kwargs={"slug": slug}))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'<h1 class="app-title marketing-title">{expected["title"]}</h1>', html=True)
                self.assertContains(response, f"<title>{expected['seo_title']}</title>", html=True)
                self.assertContains(
                    response,
                    f'<link rel="canonical" href="http://testserver/blog/{slug}/">',
                    html=True,
                )
                self.assertContains(response, f"/static/{expected['thumbnail']}")

                schema = json.loads(response.context["post"]["article_schema_json"])
                self.assertEqual(schema["headline"], expected["title"])
                self.assertEqual(schema["mainEntityOfPage"], f"http://testserver/blog/{slug}/")
                self.assertEqual(schema["image"], [f"http://testserver/static/{expected['thumbnail']}"])
