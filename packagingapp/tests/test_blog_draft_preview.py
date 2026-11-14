from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase

from packagingapp.services import blog_repository


DRAFT_LIST = "/blog/drafts/"
DRAFT_PREVIEW = "/blog/preview/preview-fixture/"
PUBLISHED_DETAIL = "/blog/published-fixture/"

ARTICLE_BODY = r"""
## Shared article body

Inline math: \(L=H\).

\[
\frac{A}{2}=\frac{V}{B}
\]

<figure class="blog-figure">
    <img src="static://img/blog/preview-fixture.png" alt="A packaging figure">
    <figcaption>Figure 1. A packaging figure.</figcaption>
</figure>

| Dimension | Value |
| --- | --- |
| Length | 200 mm |
"""


class BlogDraftPreviewTests(SimpleTestCase):
    def setUp(self):
        directory = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.object(blog_repository, "ARTICLE_DIRECTORY", directory))
        self.write_article(directory, "preview-fixture", "Private draft title", 'status = "draft"')
        self.write_article(directory, "second-draft", "Second draft title", 'status = "draft"')
        self.write_article(directory, "published-fixture", "Published fixture title", 'status = "published"')
        self.write_article(directory, "legacy-fixture", "Legacy published title", "")

    def write_article(self, directory, slug, title, status):
        subtitle = '' if status == 'status = "draft"' else 'subtitle = "Published article subtitle"'
        (directory / f"{slug}.md").write_text(
            f"""+++
slug = "{slug}"
{status}
title = "{title}"
seo_title = "{title} | KolliLabs"
{subtitle}
article_type = "engineering_deep_dive"
published_at = 2026-01-01
math = true

[cta]
url = "/free-box-size-calculator/"
label = "Try this calculation"
new_tab = true
+++
{ARTICLE_BODY}
""",
            encoding="utf-8",
        )

    def assert_private_response(self, response):
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def assert_preview_denied(self):
        with (
            patch("packagingapp.views.marketing.get_draft_articles") as get_drafts,
            patch("packagingapp.views.marketing.get_draft_article") as get_draft,
        ):
            for path in (DRAFT_LIST, DRAFT_PREVIEW, "/blog/preview/unknown/"):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertNotContains(response, "Private draft title", status_code=404)
                    self.assert_private_response(response)
            get_drafts.assert_not_called()
            get_draft.assert_not_called()

    def test_anonymous_visitors_are_denied(self):
        self.assert_preview_denied()

    def test_non_superusers_are_denied(self):
        for is_staff in (False, True):
            with self.subTest(is_staff=is_staff):
                user = User(is_active=True, is_staff=is_staff, is_superuser=False)
                with patch("django.contrib.auth.middleware.get_user", return_value=user):
                    self.assert_preview_denied()

    def test_inactive_superuser_is_denied_even_if_authenticated(self):
        # Exercise the view's active check independently of auth backend filtering.
        user = User(is_active=False, is_staff=True, is_superuser=True)
        with patch("django.contrib.auth.middleware.get_user", return_value=user):
            self.assert_preview_denied()

    def test_active_superuser_lists_drafts_and_renders_the_shared_article(self):
        user = User(is_active=True, is_superuser=True)
        with patch("django.contrib.auth.middleware.get_user", return_value=user):
            listing = self.client.get(DRAFT_LIST)
            self.assert_private_response(listing)
            self.assertContains(listing, '<meta name="robots" content="noindex, nofollow, noarchive">', html=True)
            self.assertContains(listing, "Engineering deep dive")
            self.assertContains(listing, f'href="{DRAFT_PREVIEW}"')
            self.assertContains(listing, "Private draft title")
            self.assertContains(listing, "Second draft title")
            self.assertNotContains(listing, "Published fixture title")
            self.assertNotContains(listing, "Legacy published title")
            self.assertNotContains(listing, "Shared article body")

            preview = self.client.get(DRAFT_PREVIEW)
            self.assertTemplateUsed(preview, "marketing/blog_detail.html")
            self.assert_private_response(preview)
            self.assertContains(preview, '<meta name="robots" content="noindex, nofollow, noarchive">', html=True)
            self.assertContains(preview, '<div class="alert alert-warning fw-bold">DRAFT PREVIEW</div>', html=True)
            self.assertContains(preview, "Private draft title")
            self.assertContains(preview, f'href="{DRAFT_LIST}"')
            self.assertNotContains(preview, 'rel="canonical"')
            self.assertNotContains(preview, 'property="og:url"')
            self.assertNotContains(preview, 'type="application/ld+json"')
            self.assertNotContains(preview, "Published 2026-01-01")
            self.assertContains(preview, r"\(L=H\)")
            self.assertContains(preview, r"\frac{A}{2}=\frac{V}{B}")
            self.assertContains(preview, "tex-chtml.js")
            self.assertContains(preview, "/static/img/blog/preview-fixture.png")
            self.assertContains(preview, "Figure 1. A packaging figure.")
            self.assertContains(preview, "<th>Dimension</th>", html=True)
            self.assertContains(preview, "Alejandro Ramírez")
            self.assertContains(preview, "Try this calculation")
            self.assertContains(preview, 'href="/free-box-size-calculator/"')

            published = self.client.get(PUBLISHED_DETAIL)
            self.assertEqual(preview.context["post"]["content_html"], published.context["post"]["content_html"])

    def test_active_superuser_cannot_preview_published_or_unknown_articles(self):
        user = User(is_active=True, is_superuser=True)
        with patch("django.contrib.auth.middleware.get_user", return_value=user):
            for slug in ("published-fixture", "legacy-fixture", "unknown"):
                with self.subTest(slug=slug):
                    response = self.client.get(f"/blog/preview/{slug}/")
                    self.assertEqual(response.status_code, 404)
                    self.assert_private_response(response)

    def test_public_blog_and_sitemap_remain_published_only(self):
        listing = self.client.get("/blog/")
        self.assertContains(listing, "Published fixture title")
        self.assertContains(listing, "Legacy published title")
        self.assertNotContains(listing, "Private draft title")
        self.assertNotContains(listing, DRAFT_LIST)
        self.assertEqual(self.client.get("/blog/preview-fixture/").status_code, 404)

        published = self.client.get(PUBLISHED_DETAIL)
        self.assertContains(published, f'<link rel="canonical" href="http://testserver{PUBLISHED_DETAIL}">', html=True)
        self.assertContains(published, '<meta name="robots" content="index,follow,max-image-preview:large">', html=True)
        self.assertContains(published, '"@type": "BlogPosting"')
        self.assertNotContains(published, "DRAFT PREVIEW")
        self.assertFalse(published.has_header("X-Robots-Tag"))
        self.assertNotIn("no-store", published.get("Cache-Control", ""))

        sitemap = self.client.get("/sitemap.xml")
        self.assertContains(sitemap, f"<loc>https://testserver{PUBLISHED_DETAIL}</loc>")
        self.assertContains(sitemap, "<loc>https://testserver/blog/legacy-fixture/</loc>")
        self.assertNotContains(sitemap, "preview-fixture")
        self.assertNotContains(sitemap, "/blog/preview/")
        self.assertNotContains(sitemap, DRAFT_LIST)
