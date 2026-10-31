from pathlib import Path
import re
from tempfile import TemporaryDirectory

from django.conf import settings
from django.test import SimpleTestCase

from packagingapp.services.blog_repository import _load_article, get_published_articles


class BlogMathRenderingTests(SimpleTestCase):
    def _write_article(self, directory: str, *, math: bool) -> Path:
        path = Path(directory) / "math-contract.md"
        math_field = "math = true\n" if math else ""
        path.write_text(
            "+++\n"
            'slug = "math-contract"\n'
            'status = "draft"\n'
            f"{math_field}"
            "+++\n"
            "Display:\n\n"
            "\\[\n"
            "\\frac{A}{2}=\\frac{V}{B}\n"
            "\\]\n\n"
            "Inline: \\(L=H\\)\n\n"
            "```text\n"
            "\\[code sample\\]\n"
            "```\n",
            encoding="utf-8",
        )
        return path

    def test_opted_in_article_preserves_math_delimiters(self):
        with TemporaryDirectory() as directory:
            article = _load_article(self._write_article(directory, math=True))

        self.assertIn(r"\[", article["content_html"])
        self.assertIn(r"\]", article["content_html"])
        self.assertIn(r"\(", article["content_html"])
        self.assertIn(r"\)", article["content_html"])
        self.assertIn(r"\frac{A}{2}", article["content_html"])
        self.assertIn(r'code class="language-text">\[code sample\]', article["content_html"])

    def test_non_math_article_keeps_existing_markdown_behavior(self):
        with TemporaryDirectory() as directory:
            article = _load_article(self._write_article(directory, math=False))

        self.assertIn("<p>[\n", article["content_html"])
        self.assertIn("\n]</p>", article["content_html"])
        self.assertIn("<p>Inline: (L=H)</p>", article["content_html"])


class BlogPublishingContractTests(SimpleTestCase):
    def test_published_articles_have_resolvable_image_assets(self):
        static_root = Path(settings.BASE_DIR) / "static"
        static_prefix = str(settings.STATIC_URL).rstrip("/") + "/"
        registry = Path(settings.BASE_DIR) / "docs" / "blog" / "article-registry.md"
        registry_status = {}
        if registry.is_file():
            for line in registry.read_text(encoding="utf-8").splitlines():
                if line.startswith("| ") and not line.startswith("|---"):
                    columns = [column.strip() for column in line.strip("|").split("|")]
                    if len(columns) >= 3 and columns[0] != "Slug":
                        registry_status[columns[0]] = columns[2]

        for article in get_published_articles():
            with self.subTest(slug=article["slug"]):
                self.assertEqual(registry_status.get(article["slug"]), article["status"])
                for field in ("thumbnail", "featured_image", "og_image"):
                    asset = article.get(field)
                    if asset:
                        self.assertTrue(
                            (static_root / str(asset).lstrip("/")).is_file(),
                            f"{field} is missing for {article['slug']}: {asset}",
                        )

                body_sources = re.findall(
                    r'<img\b[^>]*\bsrc=["\']([^"\']+)',
                    article["content_html"],
                )
                for source in body_sources:
                    if source.startswith(static_prefix):
                        asset = source[len(static_prefix) :]
                        self.assertTrue(
                            (static_root / asset).is_file(),
                            f"body image is missing for {article['slug']}: {asset}",
                        )
