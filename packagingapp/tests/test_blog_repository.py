from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from packagingapp.services.blog_repository import _load_article


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
