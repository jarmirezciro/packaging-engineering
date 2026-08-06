# Article Schema

Articles use TOML front matter between `+++` delimiters, followed by Markdown.

## Required example

```markdown
+++
schema_version = 1
status = "published"
title = "How Box Selection Becomes a 3D Bin-Packing Problem"
slug = "box-selection-3d-bin-packing-problem"
excerpt = "A practical explanation of why product orientation and box geometry matter."
seo_title = "3D Bin Packing for Packaging Box Selection | KolliLabs"
meta_description = "Learn how 3D bin-packing logic improves packaging box selection, utilization, and engineering decisions."
article_type = "engineering_deep_dive"
author = "Alejandro Ramírez"
published_at = 2026-07-06
updated_at = 2026-07-06
thumbnail = "img/blog/box-selection-3d-bin-packing-problem/thumbnail.webp"
thumbnail_alt = "Products arranged inside a shipping box using optimized orientations"
primary_keyword = "3D bin packing box selection"
math = true
tags = ["box selection", "packaging optimization", "3D bin packing"]
related_articles = []
related_tools = ["box-selection-tool"]
canonical_path = "/blog/box-selection-3d-bin-packing-problem/"
og_image = "img/blog/box-selection-3d-bin-packing-problem/thumbnail.webp"

[cta]
label = "Try the KolliPack box selection tool"
url = "/tools/box-selection/"
+++

# Article introduction

Article body...
```

## Required fields

| Field | Rule |
|---|---|
| `schema_version` | Integer; currently `1` |
| `status` | `draft` or `published` |
| `title` | Human-facing article title |
| `slug` | Lowercase kebab-case; matches filename |
| `excerpt` | Blog listing summary |
| `seo_title` | Search-result title; keep concise |
| `meta_description` | Search-result description |
| `article_type` | One approved type |
| `author` | Current author display name |
| `published_at` | TOML date |
| `updated_at` | TOML date; not earlier than published date |
| `thumbnail` | Static-relative asset path |
| `thumbnail_alt` | Meaningful visual description |
| `primary_keyword` | Main search topic |

## Selectable mathematics

Set the optional TOML field below only when an article contains TeX delimiters that require browser typesetting:

```toml
math = true
```

Math-enabled articles may use `\(...\)` for inline equations and `\[...\]` for display equations. The blog detail template loads the shared math renderer only for opted-in articles. Keep equations as text in the Markdown source; do not replace them with raster images. Code blocks are excluded from math processing.

## Approved article types

- `demo_case_study`
- `engineering_deep_dive`
- `business_case`
- `practical_guide`
- `kollipack_update`
- `sustainability`

## Optional fields

- `hero_image`
- `hero_image_alt`
- `math`
- `tags`
- `related_articles`
- `related_tools`
- `canonical_path`
- `og_image`
- `cta.label`
- `cta.url`

## Rules

- Filename must equal `<slug>.md`.
- Published slugs are stable.
- `updated_at` changes only for substantive updates.
- Drafts are excluded from public pages.
- Related article values are slugs, not titles.
- Asset paths omit `/static/`; the repository resolves them.
- Body image references use `static://`.
