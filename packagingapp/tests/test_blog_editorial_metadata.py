from __future__ import annotations

import hashlib
from pathlib import Path
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 fallback
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTICLE_DIR = REPO_ROOT / "packagingapp" / "content" / "blog" / "articles"
STATIC_ROOT = REPO_ROOT / "static"
FRONT_MATTER = re.compile(r"\A\+\+\+\s*\n(?P<meta>.*?)\n\+\+\+", re.DOTALL)

EXPECTED_ARTICLES = {
    "box-selection-3d-bin-packing-problem": {
        "title": "The Box Fits. So Why Might It Still Be the Wrong Choice?",
        "seo_title": "3D Bin Packing for Better Box Selection | KolliLabs",
        "thumbnail": "img/blog/box-selection-3d-bin-packing-problem/thumbnail-v1.webp",
    },
    "kollipack-vs-tops-pro-palletization-benchmark": {
        "title": "KolliPack vs TOPS Pro: Same Pallet Capacity, Different Approaches",
        "seo_title": "KolliPack vs TOPS Pro Palletization: A 48 × 40 Pallet Benchmark",
        "thumbnail": "img/blog/kollipack-vs-tops-pro-palletization-benchmark/thumbnail-v1.webp",
    },
    "tops-pro-case-size-optimization-kollipack-comparison": {
        "title": "KolliPack vs TOPS Pro: Is a Bigger Case Pack Really Better?",
        "seo_title": "KolliPack vs TOPS Pro: 8-Pack vs 16-Pack Pallet Optimization",
        "thumbnail": "img/blog/tops-pro-case-size-optimization-kollipack-comparison/thumbnail-v1.webp",
    },
    "think-beyond-the-box-packaging-flow-case-study": {
        "title": "How Changing the Box Increased Container Capacity by 50%",
        "seo_title": "How Box Design Affects Pallet and Container Capacity | KolliPack",
        "thumbnail": "img/blog/think-beyond-the-box-packaging-flow-case-study/thumbnail-v2.webp",
    },
    "rsc-material-optimization": {
        "title": "Same Volume, Different Cardboard: Why Box Shape Matters",
        "seo_title": "Box Geometry, Corrugated Material, Cost and Carbon | KolliPack",
        "thumbnail": "img/blog/rsc-material-optimization/thumbnail-v1.webp",
    },
    "how-many-products-fit-in-a-box-orientation-case-study": {
        "title": "How We Fit 20% More Products Without Changing the Box",
        "seo_title": "How Many Products Fit in a Box? Orientation Case Study | KolliPack",
        "thumbnail": "img/blog/how-many-products-fit-in-a-box-orientation-case-study/thumbnail-v1.webp",
    },
    "container-loading-benchmark-kollipack-br1-br7": {
        "title": "How Good Is KolliPack at Container Loading? An Honest Benchmark",
        "seo_title": "Container Loading Benchmark: KolliPack on 700 BR Cases",
        "thumbnail": "img/blog/container-loading-benchmark-kollipack-br1-br7/thumbnail-v2.webp",
    },
    "ask-kollipack-ai-assistant-packaging-logistics": {
        "title": "Ask KolliPack: What Happens When AI Meets Logistics Software?",
        "seo_title": "KolliPack AI Assistant for Packaging & Logistics Software | KolliLabs",
        "thumbnail": "img/blog/ask-kollipack-ai-assistant-packaging-logistics/thumbnail-v1.webp",
    },
    "tops-maxload-kollipack-container-loading-benchmark": {
        "title": "KolliPack vs TOPS MaxLoad: Can a Different Loading Strategy Fit More?",
        "seo_title": "TOPS MaxLoad vs KolliPack: High-Cube Loading Benchmark",
        "thumbnail": "img/blog/tops-maxload-kollipack-container-loading-benchmark/thumbnail-v1.webp",
    },
}

APPROVED_THUMBNAIL_HASHES = {
    "img/blog/box-selection-3d-bin-packing-problem/thumbnail-v1.webp": (
        "d07a00c50fd80cc0e2f6a4ce039d73cc814420f59fbe9a4ee67d85214a6303f0"
    ),
    "img/blog/kollipack-vs-tops-pro-palletization-benchmark/thumbnail-v1.webp": (
        "7550e6757035452409637a4bd171745567bdcc248b8c5dff972a0e5a0ca88cb8"
    ),
    "img/blog/tops-pro-case-size-optimization-kollipack-comparison/thumbnail-v1.webp": (
        "1d68a6dea59efa75a4f42fdd2a12c5b20a1c08c293980bf4220db6e98e2e4528"
    ),
    "img/blog/think-beyond-the-box-packaging-flow-case-study/thumbnail-v2.webp": (
        "687413900fbb7bb39e1204ce231659ef33f35592186e763cc3e1ecbfbdbb858a"
    ),
    "img/blog/container-loading-benchmark-kollipack-br1-br7/thumbnail-v2.webp": (
        "419f27815b598074923d9456fd86ec57c64001ed6a994ce3e153b7dd9c2d61a7"
    ),
    "img/blog/rsc-material-optimization/thumbnail-v1.webp": (
        "ceb3bc5823cfd1a2a6104766f461f8ef72276e8e0e4eede7f03dddc57b9ea116"
    ),
    "img/blog/how-many-products-fit-in-a-box-orientation-case-study/thumbnail-v1.webp": (
        "ebeda4f9ddddde4b5359394b6f8e741864b79d4f6b86d34e8fbd961ed5ea1d54"
    ),
    "img/blog/ask-kollipack-ai-assistant-packaging-logistics/thumbnail-v1.webp": (
        "32c559ee13ba15bb70ee48f1be7d980f94d0fac34042bfc233eff992e1c85ea5"
    ),
    "img/blog/tops-maxload-kollipack-container-loading-benchmark/thumbnail-v1.webp": (
        "7c6044e209564e6c9014933bcf33a5400afb1e278166387cadc0572b110e4f0b"
    ),
}

ROLLBACK_ASSETS = {
    "box-selection-3d-bin-packing-problem": "blog1_thumbnail_kollipack_box_selection.png",
    "kollipack-vs-tops-pro-palletization-benchmark": "thumbnail.webp",
    "tops-pro-case-size-optimization-kollipack-comparison": "thumbnail.webp",
    "think-beyond-the-box-packaging-flow-case-study": "thumbnail-v1.webp",
    "rsc-material-optimization": "thumbnail.webp",
    "how-many-products-fit-in-a-box-orientation-case-study": "thumbnail.webp",
    "container-loading-benchmark-kollipack-br1-br7": "thumbnail-v1.webp",
    "ask-kollipack-ai-assistant-packaging-logistics": "thumbnail.webp",
    "tops-maxload-kollipack-container-loading-benchmark": "thumbnail.webp",
}


def load_metadata(slug: str) -> dict:
    path = ARTICLE_DIR / f"{slug}.md"
    source = path.read_text(encoding="utf-8")
    match = FRONT_MATTER.match(source)
    if not match:
        raise AssertionError(f"Missing TOML front matter: {path}")
    return tomllib.loads(match.group("meta"))


class BlogEditorialMetadataTests(unittest.TestCase):
    def test_all_nine_editorial_titles_and_seo_titles_are_canonical(self):
        article_files = {path.stem for path in ARTICLE_DIR.glob("*.md")}
        self.assertEqual(len(EXPECTED_ARTICLES), 9)
        self.assertTrue(set(EXPECTED_ARTICLES).issubset(article_files))

        for slug, expected in EXPECTED_ARTICLES.items():
            with self.subTest(slug=slug):
                metadata = load_metadata(slug)
                self.assertEqual(metadata["slug"], slug)
                self.assertEqual(metadata["title"], expected["title"])
                self.assertEqual(metadata["seo_title"], expected["seo_title"])
                self.assertEqual(metadata["canonical_path"], f"/blog/{slug}/")
                self.assertEqual(metadata["featured_image"], expected["thumbnail"])
                self.assertEqual(metadata["thumbnail"], expected["thumbnail"])
                self.assertEqual(metadata["og_image"], expected["thumbnail"])
                self.assertTrue(metadata["thumbnail_alt"].strip())
                self.assertTrue((STATIC_ROOT / expected["thumbnail"]).is_file())

    def test_approved_thumbnail_assets_match_reviewed_bytes_and_keep_rollback_files(self):
        for relative_path, expected_hash in APPROVED_THUMBNAIL_HASHES.items():
            with self.subTest(relative_path=relative_path):
                asset = STATIC_ROOT / relative_path
                self.assertEqual(hashlib.sha256(asset.read_bytes()).hexdigest(), expected_hash)
                slug = asset.parent.name
                self.assertTrue((asset.parent / ROLLBACK_ASSETS[slug]).is_file())

    def test_blog_listing_uses_thumbnail_alt_metadata(self):
        template = (
            REPO_ROOT / "packagingapp" / "templates" / "marketing" / "blog_list.html"
        ).read_text(encoding="utf-8")
        self.assertIn("post.thumbnail_alt|default:post.title", template)


if __name__ == "__main__":
    unittest.main()
