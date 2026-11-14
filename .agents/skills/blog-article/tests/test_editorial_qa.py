from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_editorial as qa


THUMBNAIL = "img/blog/qa-fixture/thumbnail.webp"
CASE_ROUTE = "/free-box-size-calculator/"
CASE = f"{CASE_ROUTE}?case=product-orientation-capacity"
PIPE_TABLE = """| Dimension (mm) | Quantity |
| --- | --- |
| 200 | 4 |
"""
HTML_TABLE = """<table class="blog-result-table">
<thead><tr><th>Dimension (mm)</th><th>Quantity</th></tr></thead>
<tbody><tr><td>200</td><td>4</td></tr></tbody>
</table>"""


class EditorialAuditTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.article = self.root / "qa-fixture.md"
        self.asset = self.root / "static" / THUMBNAIL
        self.asset.parent.mkdir(parents=True)
        self.asset.write_bytes(b"approved fixture bytes")
        self.enterContext(patch.object(qa, "REPO_ROOT", self.root))
        # Reuse validate() with the temporary repository as its asset root.
        self.enterContext(patch.object(qa.validate_article, "__file__", str(
            self.root / ".agents/skills/blog-article/scripts/validate_article.py"
        )))

    def write_article(self, body, *, article_type="engineering_deep_dive", cta="", title="Packaging QA"):
        self.article.write_text(
            f"""+++
schema_version = 1
status = "draft"
title = "{title}"
slug = "qa-fixture"
excerpt = "A short packaging experiment."
seo_title = "Packaging QA"
meta_description = "A test case for the editorial audit."
article_type = "{article_type}"
author = "KolliLabs"
published_at = 2026-10-01
updated_at = 2026-10-01
thumbnail = "{THUMBNAIL}"
thumbnail_alt = "Packages in a box"
primary_keyword = "box packing"

[cta]
url = "{cta}"
+++
{body}
""",
            encoding="utf-8",
        )

    def check(self, rule, status, *, kind="automated", **options):
        found = [f for f in qa.audit(self.article, **options) if f.rule == rule and f.kind == kind]
        self.assertTrue(any(f.status == status for f in found), found)
        return found

    def figure(self, caption):
        return f'<figure class="blog-figure"><img src="static://{THUMBNAIL}" alt="A box"><figcaption>{caption}</figcaption></figure>'

    def test_valid_article_and_case_pass_automated_checks(self):
        self.write_article(
            f"See Figure 1. [Open this case]({CASE}).\n\n"
            f"{self.figure('Figure 1. Pack layout')}\n\n{HTML_TABLE}",
            article_type="demo_case_study", cta=CASE,
        )
        findings = qa.audit(self.article)
        self.assertFalse([f for f in findings if f.kind == "automated" and f.status in {"WARNING", "FAIL", "REVIEW_REQUIRED"}])
        checks = {(f.rule, f.status) for f in findings if f.kind == "automated"}
        self.assertTrue({(rule, "PASS") for rule in ("SCHEMA", "ASSETS", "EDR-07", "EDR-08", "EDR-11")} <= checks)
        self.assertEqual({f.rule for f in findings if f.rule.startswith("EDR-")}, {f"EDR-{i:02d}" for i in range(1, 13)})

    def test_markdown_table_wrappers_use_production_rendering(self):
        for wrapper, expected in (("<div>", "FAIL"), ('<div markdown="1">', "PASS")):
            with self.subTest(wrapper=wrapper):
                self.write_article(f"{wrapper}\n\n{PIPE_TABLE}\n</div>")
                self.check("EDR-07", expected)

    def test_code_sample_table_is_not_counted_as_a_rendering_failure(self):
        self.write_article(f"```md\n{PIPE_TABLE}```")
        self.check("EDR-07", "NOT_APPLICABLE")

    def test_missing_headers_and_explicit_unit_conflicts(self):
        self.write_article("<table><tr><td>Value</td></tr></table>")
        self.check("EDR-07", "FAIL")
        self.write_article(HTML_TABLE.replace("<td>200</td>", "<td>200 kg</td>"))
        self.check("EDR-07", "WARNING")

    def test_single_column_pipe_table_can_leak(self):
        self.write_article("<div>\n\n| Dimension |\n| --- |\n| 200 |\n\n</div>")
        self.check("EDR-07", "FAIL")

    def test_detects_numbering_defects_and_dangling_references(self):
        for first, second in (
            ("Pack layout", "Figure 2. Results"),
            ("Figure 1. Layout", "Figure 1. Results"),
            ("Figure 1. Layout", "Figure 3. Results"),
            ("Figure 2. Layout", "Figure 1. Results"),
        ):
            with self.subTest(captions=(first, second)):
                self.write_article(f"{self.figure(first)}\n\n{self.figure(second)}")
                self.check("EDR-08", "FAIL")
        self.write_article(f"See Figure 3.\n\n{self.figure('Figure 1. Layout')}")
        self.check("EDR-08", "FAIL")

    def test_decorative_image_does_not_require_a_figure_number(self):
        self.write_article(f'<figure class="blog-figure" role="presentation"><img src="static://{THUMBNAIL}" alt=""></figure>')
        self.check("EDR-08", "NOT_APPLICABLE")

    def test_mixed_numbering_also_detected_without_article_css_class(self):
        body = f"{self.figure('Figure 1. Layout')}\n\n{self.figure('Results')}"
        self.write_article(body.replace(' class="blog-figure"', ""))
        self.check("EDR-08", "FAIL")

    def test_missing_and_unsafe_local_images(self):
        self.write_article('![Box](/static/img/blog/qa-fixture/missing.webp)')
        self.check("ASSETS", "FAIL")
        self.write_article('![Box](/static/img/%2E%2E/missing.webp)')
        self.check("ASSETS", "FAIL")
        self.write_article(f'<img src="static://{THUMBNAIL}">')
        self.check("ASSETS", "FAIL")

    def test_reuses_existing_structural_errors(self):
        self.write_article("A demo.", article_type="unsupported")
        findings = self.check("SCHEMA", "FAIL")
        self.assertIn("article_type", findings[0].message)

    def test_bad_demo_cta_and_conflicting_body_case(self):
        for url in (CASE_ROUTE, f"{CASE_ROUTE}?case=unknown", f"{CASE}&case=duplicate"):
            with self.subTest(url=url):
                self.write_article(f"[Try]({url})", article_type="demo_case_study", cta=url)
                self.check("EDR-11", "FAIL")
        self.write_article(f"[Different case]({CASE_ROUTE}?case=unknown)", cta=CASE)
        self.check("EDR-11", "WARNING")
        self.check("EDR-11", "REVIEW_REQUIRED", kind="review")

    def test_runnable_benchmark_scope_does_not_depend_on_article_type(self):
        self.write_article("We compare two datasets.", title="Loading Benchmark", cta=CASE_ROUTE)
        self.check("EDR-11", "NOT_APPLICABLE")
        self.check("EDR-11", "FAIL", require_case=True)

    def test_packaging_flow_case_uses_the_path_parameter(self):
        url = "/full-packaging/case/capepack-bottle-20/?reset=1"
        self.write_article(f"[Try]({url})", article_type="demo_case_study", cta=url)
        self.check("EDR-11", "PASS")

    def test_external_reference_does_not_imply_an_archive(self):
        self.write_article("See the [comparison source](https://example.org/study?case=cargo).", title="Packaging Benchmark")
        findings = self.check("EDR-10", "WARNING")
        self.assertIn("archival was not verified", findings[0].message)
        self.check("EDR-10", "REVIEW_REQUIRED", kind="review")
        self.check("EDR-11", "NOT_APPLICABLE")
        self.write_article("We compare these with vendor claims.", title="Packaging Benchmark")
        self.check("EDR-10", "FAIL")

    def test_visual_checks_require_review(self):
        self.write_article(f"{self.figure('Figure 1. Layout')}\n\n{HTML_TABLE}")
        visual = {f.rule: f.status for f in qa.audit(self.article) if f.kind == "visual"}
        self.assertEqual(visual, {f"EDR-{i:02d}": "REVIEW_REQUIRED" for i in range(4, 10)})
        self.check("EDR-12", "REVIEW_REQUIRED", kind="review")

    def test_old_approved_thumbnail_in_metadata_does_not_approve_a_new_thumbnail(self):
        self.write_article("A demo.")
        replacement = self.asset.with_name("replacement.webp")
        replacement.write_bytes(b"replacement")
        source = self.article.read_text(encoding="utf-8")
        self.article.write_text(
            source.replace(f'thumbnail = "{THUMBNAIL}"', f'thumbnail = "img/blog/qa-fixture/{replacement.name}"\nog_image = "{THUMBNAIL}"'),
            encoding="utf-8",
        )
        known = {THUMBNAIL: sha256(self.asset.read_bytes()).hexdigest()}
        with patch("packagingapp.tests.test_blog_editorial_metadata.APPROVED_THUMBNAIL_HASHES", known):
            self.check("EDR-12", "FAIL")

    def test_asset_preservation_detects_changed_bytes_and_path_without_writes(self):
        self.write_article("A demo.")
        approval = self.root / "approval.json"
        original = self.asset.read_bytes()
        approval.write_text(json.dumps({
            "article_slug": "qa-fixture",
            "assets": {THUMBNAIL: sha256(original).hexdigest()},
        }), encoding="utf-8")
        before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in (self.article, self.asset, approval)]
        self.check("EDR-12", "PASS", approval_record=approval)
        self.assertEqual(before, [(path.read_bytes(), path.stat().st_mtime_ns) for path in (self.article, self.asset, approval)])
        self.asset.write_bytes(b"changed")
        self.check("EDR-12", "FAIL", approval_record=approval)
        self.asset.write_bytes(original)
        self.article.write_text(self.article.read_text(encoding="utf-8").replace(THUMBNAIL, "img/replacement.webp"), encoding="utf-8")
        self.check("EDR-12", "FAIL", approval_record=approval)


if __name__ == "__main__":
    unittest.main()
