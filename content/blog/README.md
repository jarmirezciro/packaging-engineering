# KolliLabs blog workflow

The current Django blog is rendered from `packagingapp/views/marketing.py`.
The Markdown files in this folder are source copies for drafting, SEO review, and future migration to a database or Markdown renderer.

## Article types

Use `article_type` in the article metadata to control the badge and positioning.

| article_type | Label | Use when |
|---|---|---|
| `engineering_deep_dive` | Engineering deep dive / Nerd article | The article is technical, algorithmic, visual, or calculation-heavy. |
| `business_case` | Business case / Business article | The article is about savings, management decisions, cost, CO₂, or process improvement. |
| `practical_guide` | Practical guide / How-to guide | The article teaches a repeatable method or checklist. |
| `kollipack_update` | KolliPack update / Product update | The article explains a feature, workflow, release, or app example. |
| `sustainability` | Sustainability | The article focuses on material reduction, emissions, or environmental impact. |

## Suggested first content mix

A healthy KolliLabs blog should mix:

- technical depth to build credibility,
- business articles to reach managers and buyers,
- practical guides to help packaging/logistics teams,
- product updates to explain KolliPack workflows,
- sustainability articles to connect optimization with CO₂ and material reduction.
