from html.parser import HTMLParser
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

from packagingapp.services.blog_repository import get_published_articles


class _PublicExpertParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.form_depth = 0
        self.expert_form_depths = []
        self.scopes = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "form":
            self.form_depth += 1
        if "data-kollipack-public-expert" in attributes:
            self.expert_form_depths.append(self.form_depth)
            self.scopes.append(attributes.get("data-public-expert-scope"))

    def handle_endtag(self, tag):
        if tag == "form":
            self.form_depth -= 1


@override_settings(AI_PUBLIC_EXPERT_ENABLED=True)
class PublicExpertUiTests(TestCase):
    def test_supported_public_pages_render_one_scoped_component_outside_tool_forms(self):
        pages = {
            "company_home": "global",
            "about": "global",
            "home": "global",
            "blog_list": "global",
            "container_selection_calculator": "container_selection",
            "bag_selection_calculator": "bag_selection",
            "palletization_calculator": "palletization",
            "transport_container_calculator": "transport",
        }
        for name, scope in pages.items():
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                parser = _PublicExpertParser()
                parser.feed(response.content.decode("utf-8"))
                self.assertEqual(parser.expert_form_depths, [0])
                self.assertEqual(parser.scopes, [scope])
                self.assertContains(response, "js/kollipack_public_expert.js", count=1)
                self.assertContains(response, "data-public-expert-open", count=1)
                self.assertContains(response, "aria-live=\"polite\"", count=1)
                self.assertContains(response, "Uses an external AI service", count=1)
                self.assertContains(
                    response,
                    "Questions that KolliPack cannot answer may be stored",
                    count=1,
                )
                self.assertContains(
                    response,
                    "Do not include confidential or personal information.",
                    count=1,
                )

    def test_every_published_blog_article_renders_global_public_expert(self):
        articles = get_published_articles()
        self.assertTrue(articles)

        for article in articles:
            with self.subTest(slug=article["slug"]):
                response = self.client.get(
                    reverse("blog_detail", kwargs={"slug": article["slug"]})
                )
                self.assertEqual(response.status_code, 200)
                parser = _PublicExpertParser()
                parser.feed(response.content.decode("utf-8"))
                self.assertEqual(parser.expert_form_depths, [0])
                self.assertEqual(parser.scopes, ["global"])
                self.assertContains(response, "js/kollipack_public_expert.js", count=1)

    def test_unrelated_public_pages_do_not_render_expert(self):
        for name in (
            "pricing",
            "container_selection_mode1",
            "catalogue_list",
            "product_catalogues",
        ):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertNotContains(response, "data-kollipack-public-expert")
                self.assertNotContains(response, "js/kollipack_public_expert.js")

    def test_markup_exposes_no_provider_or_engineering_state(self):
        response = self.client.get(reverse("container_selection_calculator"))
        expert_markup = response.content.decode("utf-8").split(
            '<div class="kpe-root"', 1
        )[1].split("</aside>", 1)[0]
        for forbidden in (
            "data-assistant-state",
            "data-public-expert-provider",
            "openai_api_key",
            "reasoning_effort",
            "threejs_scene",
            "selected_product_id",
            "tool_context",
        ):
            self.assertNotIn(forbidden, expert_markup.lower())

    def test_controller_uses_text_content_focus_trap_escape_and_exact_request_shape(self):
        script = (
            Path(__file__).resolve().parents[2]
            / "static"
            / "js"
            / "kollipack_public_expert.js"
        ).read_text(encoding="utf-8")
        self.assertIn("responseNode.textContent = response.message", script)
        self.assertNotIn("responseNode.innerHTML", script)
        self.assertIn('event.key === "Escape"', script)
        self.assertIn('event.key !== "Tab"', script)
        self.assertIn("restoreFocus.focus()", script)
        self.assertIn("{message: String(message).trim(), knowledge_scope: knowledgeScope}", script)
        for forbidden in (
            "localStorage",
            "sessionStorage",
            "querySelectorAll(\"input\")",
            "FormData",
            "threejs",
        ):
            self.assertNotIn(forbidden, script)
