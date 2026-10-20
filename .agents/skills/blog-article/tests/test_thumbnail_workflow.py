from __future__ import annotations

import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = REPO_ROOT / ".agents" / "skills" / "blog-article" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from thumbnail_workflow import (  # noqa: E402
    ProviderCapabilities,
    ProviderUnavailableError,
    SchemaValidationError,
    UnsupportedReferenceError,
    can_publish,
    create_card_preview,
    create_preview_sheets,
    create_thumbnail_gallery,
    generate_with_retries,
    load_tokens,
    render_thumbnail,
    sha256_file,
    sha256_text,
    validate_illustration_spec,
    validate_rendered_thumbnail,
    validate_thumbnail_brief,
)
from compose_thumbnail import legacy_main, workflow_main  # noqa: E402


def valid_brief(scene_family: str = "hero") -> dict:
    return {
        "schema_version": "1.0",
        "article_slug": f"fixture-{scene_family}",
        "composition": scene_family,
        "hook_primary": "RIGHT FIT",
        "hook_secondary": "CLEAR DECISION",
        "support_line": "One concise, article-grounded message.",
        "scene_subject": "one physically plausible packaging subject with a clean silhouette",
        "image_mode": "editorial_illustration",
        "supported_claims": [],
        "screenshots_allowed": False,
        "reference_standard": "thumbnail-design-system-v1",
    }


def valid_spec(scene_family: str = "hero") -> dict:
    return {
        "schema_version": "1.0",
        "article_slug": f"fixture-{scene_family}",
        "scene_family": scene_family,
        "subjects": ["corrugated_box"],
        "camera": "three-quarter product-studio view",
        "materials": "natural corrugated board with restrained industrial detail",
        "lighting": "cinematic teal studio key and controlled contact shadow",
        "reserved_blank_zones": ["left_text_zone", "lower_left_brand_zone"],
        "blending_strategy": "transparent_alpha",
        "exclusions": ["text", "logos", "people", "screenshots", "watermarks"],
        "image_mode": "editorial_illustration",
    }


def fixture_illustration(path: Path) -> None:
    image = Image.new("RGBA", (720, 620), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((90, 120, 620, 535), radius=36, fill=(174, 105, 55, 255), outline=(230, 171, 112, 255), width=8)
    draw.polygon([(90, 120), (260, 42), (670, 104), (620, 185)], fill=(208, 139, 78, 255))
    draw.line((310, 84, 310, 520), fill=(117, 71, 42, 255), width=7)
    image.save(path, format="PNG")


class ThumbnailSchemaTests(unittest.TestCase):
    def test_all_five_scene_families_validate(self):
        for family in ("hero", "comparison", "improvement", "benchmark", "product"):
            with self.subTest(family=family):
                brief = valid_brief(family)
                spec = valid_spec(family)
                self.assertEqual(validate_thumbnail_brief(brief), [])
                validate_illustration_spec(spec, brief=brief)

    def test_numeric_hook_without_evidence_is_rejected(self):
        brief = valid_brief("improvement")
        brief["hook_primary"] = "+50%"
        with self.assertRaisesRegex(SchemaValidationError, "no matching supported_claims"):
            validate_thumbnail_brief(brief)

    def test_evidence_derived_mode_requires_assets(self):
        brief = valid_brief()
        brief["image_mode"] = "evidence_derived"
        with self.assertRaisesRegex(SchemaValidationError, "evidence_asset_paths"):
            validate_thumbnail_brief(brief)

    def test_prompt_cli_records_tool_instruction_in_exact_prompt_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief_path = root / "brief.json"
            spec_path = root / "spec.json"
            output_path = root / "prompt.json"
            brief_path.write_text(json.dumps(valid_brief()), encoding="utf-8")
            spec_path.write_text(json.dumps(valid_spec()), encoding="utf-8")

            result = workflow_main(
                [
                    "prompt",
                    "--brief",
                    str(brief_path),
                    "--spec",
                    str(spec_path),
                    "--output",
                    str(output_path),
                    "--append-instruction",
                    "Use the attached approved board only as a style reference.",
                ]
            )

            record = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertTrue(record["prompt"].endswith("Use the attached approved board only as a style reference."))
            self.assertEqual(record["prompt_sha256"], sha256_text(record["prompt"]))


class ThumbnailRendererTests(unittest.TestCase):
    def test_same_fixture_produces_same_layout_and_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            illustration = root / "fixture.png"
            first = root / "first.png"
            second = root / "second.png"
            fixture_illustration(illustration)
            brief = valid_brief("hero")
            spec = valid_spec("hero")
            first_report = render_thumbnail(brief, spec, illustration, first)
            second_report = render_thumbnail(brief, spec, illustration, second)
            self.assertEqual(first_report["layout"], second_report["layout"])
            self.assertEqual(sha256_file(first), sha256_file(second))

    def test_all_families_render_without_clipping_at_full_and_card_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            illustration = root / "fixture.png"
            fixture_illustration(illustration)
            for family in ("hero", "comparison", "improvement", "benchmark", "product"):
                with self.subTest(family=family):
                    family_dir = root / family
                    full = family_dir / "thumbnail-v1.webp"
                    card = family_dir / "thumbnail-card-360.webp"
                    report = render_thumbnail(valid_brief(family), valid_spec(family), illustration, full)
                    validation = validate_rendered_thumbnail(full, report)
                    self.assertEqual(validation["hard_status"], "pass")
                    self.assertEqual(validation["visual_status"], "review_required")
                    self.assertGreaterEqual(
                        report["layout"]["font_sizes"]["support"],
                        load_tokens()["layout"]["support_size_min"],
                    )
                    create_card_preview(full, card)
                    with Image.open(card) as image:
                        self.assertEqual(image.size, (360, 203))

    def test_layout_matches_stable_golden_fixture(self):
        expected_path = Path(__file__).parent / "fixtures" / "thumbnail-layout-golden-v1.json"
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            illustration = root / "fixture.png"
            output = root / "golden.png"
            fixture_illustration(illustration)
            report = render_thumbnail(valid_brief("hero"), valid_spec("hero"), illustration, output)
            actual = {
                "canvas": report["layout"]["canvas"],
                "text_zone": report["layout"]["text_zone"],
                "illustration_zone": report["layout"]["illustration_zone"],
                "primary_box": report["layout"]["primary_box"],
                "secondary_boxes": report["layout"]["secondary_boxes"],
                "support_boxes": report["layout"]["support_boxes"],
                "font_sizes": report["layout"]["font_sizes"],
                "logo_box": report["layout"]["logo_box"],
                "illustration_placed_box": report["layout"]["illustration"]["placed_box"],
            }
            self.assertEqual(actual, expected)

    def test_preview_regeneration_keeps_versioned_card_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "pilot-50pct" / "thumbnail-v2.webp"
            second = root / "pilot-700-tests" / "thumbnail-v2.webp"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            Image.new("RGB", (1280, 720), "#063c39").save(first, format="WEBP")
            Image.new("RGB", (1280, 720), "#063c39").save(second, format="WEBP")

            outputs = create_preview_sheets(first, second, root / "previews-v2")

            self.assertTrue(Path(outputs["first_card_preview"]).name.endswith("-v2.webp"))
            self.assertTrue(Path(outputs["second_card_preview"]).name.endswith("-v2.webp"))
            self.assertTrue(Path(outputs["first_card_preview"]).is_file())
            self.assertTrue(Path(outputs["second_card_preview"]).is_file())

    def test_gallery_renders_a_labeled_card_grid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            items = []
            for index in range(4):
                thumbnail = root / f"thumbnail-{index}.webp"
                Image.new("RGB", (1280, 720), (3 + index, 59, 56)).save(thumbnail, format="WEBP")
                items.append((f"Card {index + 1}", thumbnail))

            output = root / "gallery.png"
            create_thumbnail_gallery(items, output, columns=2)

            with Image.open(output) as image:
                self.assertEqual(image.width, 796)
                self.assertGreater(image.height, 500)


class FailingProvider:
    name = "fixture-failure"
    model = "fixture-model"
    capabilities = ProviderCapabilities(True, True)

    def __init__(self):
        self.calls = 0

    def generate(self, **kwargs):
        self.calls += 1
        raise RuntimeError("fixture provider failure")


class UnsupportedReferenceProvider:
    name = "fixture-no-reference"
    model = "fixture-model"
    capabilities = ProviderCapabilities(False, True)

    def generate(self, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("generate must not be called")


class ThumbnailProviderTests(unittest.TestCase):
    def test_retry_cap_persists_failures_and_publish_stays_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempts = root / "attempts.json"
            provider = FailingProvider()
            with self.assertRaises(ProviderUnavailableError):
                generate_with_retries(
                    provider,
                    prompt="fixture",
                    reference_path=None,
                    output_path=root / "output.png",
                    attempts_path=attempts,
                    max_attempts=3,
                )
            report = json.loads(attempts.read_text(encoding="utf-8"))
            self.assertEqual(provider.calls, 3)
            self.assertEqual(len(report["attempts"]), 3)
            self.assertEqual(report["approval_status"], "review_required")
            self.assertFalse(can_publish({"hard_status": "pass", "visual_status": "review_required"}, report))

    def test_unsupported_reference_is_reported_without_calling_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempts = root / "attempts.json"
            reference = REPO_ROOT / "docs" / "blog" / "assets" / "kollilabs-approved-thumbnail-board-v1.png"
            with self.assertRaises(UnsupportedReferenceError):
                generate_with_retries(
                    UnsupportedReferenceProvider(),
                    prompt="fixture",
                    reference_path=reference,
                    output_path=root / "output.png",
                    attempts_path=attempts,
                )
            report = json.loads(attempts.read_text(encoding="utf-8"))
            self.assertEqual(report["error_reason"], "reference_images_unsupported")


class PublishedBlogRegressionTests(unittest.TestCase):
    def test_legacy_composer_interface_still_writes_original_default_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            background = root / "background.png"
            logo = root / "logo.png"
            output = root / "legacy.webp"
            Image.new("RGB", (1400, 800), (12, 48, 50)).save(background)
            Image.new("RGBA", (180, 48), (255, 255, 255, 255)).save(logo)
            result = legacy_main(
                [
                    "--background",
                    str(background),
                    "--logo",
                    str(logo),
                    "--title",
                    "Legacy fixture",
                    "--output",
                    str(output),
                    "--accent",
                    "#10a37f",
                ]
            )
            self.assertEqual(result, 0)
            with Image.open(output) as image:
                self.assertEqual(image.size, (1200, 630))

    def test_published_articles_keep_versioned_asset_contract(self):
        article_dir = REPO_ROOT / "packagingapp" / "content" / "blog" / "articles"
        pilot_expectations = {
            "think-beyond-the-box-packaging-flow-case-study": "img/blog/think-beyond-the-box-packaging-flow-case-study/thumbnail-v2.webp",
            "container-loading-benchmark-kollipack-br1-br7": "img/blog/container-loading-benchmark-kollipack-br1-br7/thumbnail-v2.webp",
        }
        found = set()
        for article_path in article_dir.glob("*.md"):
            text = article_path.read_text(encoding="utf-8")
            front_matter = text.split("+++", 2)[1]
            metadata = tomllib.loads(front_matter)
            if metadata.get("status") != "published":
                continue
            slug = metadata["slug"]
            thumbnail = metadata["thumbnail"]
            self.assertNotIn("pilot", thumbnail)
            self.assertTrue((REPO_ROOT / "static" / thumbnail).is_file(), thumbnail)
            self.assertEqual(metadata.get("featured_image", thumbnail), thumbnail)
            self.assertEqual(metadata.get("og_image", thumbnail), thumbnail)
            if slug in pilot_expectations:
                found.add(slug)
                self.assertEqual(thumbnail, pilot_expectations[slug])
        self.assertEqual(found, set(pilot_expectations))


if __name__ == "__main__":
    unittest.main()
