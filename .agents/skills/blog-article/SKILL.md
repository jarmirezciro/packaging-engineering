---
name: blog-article
description: Create, polish, research, refresh, illustrate, validate, and integrate KolliLabs/KolliPack blog articles using the repository's file-based article architecture.
---

# KolliLabs Blog Article Skill

Use this skill when creating a new KolliLabs article, polishing a draft, elaborating ideas into an article, or refreshing an existing article.

## Supported modes

- `polish`: improve a substantially complete user-authored draft.
- `research`: turn notes, questions, or ideas into a researched article.
- `refresh`: update an existing published article while preserving its slug and identity.

## Required inputs

Resolve from the task or source document:

- Mode.
- Source text or idea notes.
- Intended audience, when stated.
- Requested images and their specified method.
- Any required CTA or linked KolliPack tool.

Do not ask unnecessary questions. When information is not specified, infer conservative defaults from the existing article library and document the assumption in the final report.

## Repository rules

1. Read `references/blog-architecture.md` before editing.
2. Inspect existing articles and the generated registry before choosing a topic or slug.
3. Create or edit article files in the configured article-content directory.
4. Store production article images under `static/img/blog/<slug>/`.
5. Do not add article content to `marketing.py`.
6. Do not change routes, templates, loaders, or schema during normal article creation.
7. Do not regenerate or redraw the official logo.
8. Do not commit, push, merge, or deploy unless explicitly requested.

## Editorial workflow

### 1. Establish the article brief

Determine:

- Reader problem.
- Primary search intent.
- Primary keyword.
- One-sentence promise.
- Article type.
- Proposed CTA.
- Needed evidence.
- Image plan.

Check for topic overlap with existing articles.

### 2. Handle the input mode

#### Polish mode

- Preserve the author's technical meaning and personal voice.
- Correct grammar, spelling, transitions, and cohesion.
- Reorganize only when it materially improves understanding.
- Flag unsupported claims rather than inventing support.
- Avoid generic AI-marketing language.

#### Research mode

- Create research notes from authoritative sources.
- Separate verified facts from KolliLabs engineering judgment.
- Build a clear outline before drafting.
- Never invent sources, quotations, results, statistics, or calculations.
- Paraphrase sources and keep quotations minimal.

#### Refresh mode

- Preserve the existing slug unless a redirect is explicitly part of the task.
- Verify links, facts, dates, screenshots, recommendations, and figures.
- Update `updated_at` only when substantive content changes.
- Report exactly what changed.

### 3. Write the article

Follow `references/editorial-style.md`, `references/article-schema.md`, and `references/seo-rules.md`.

Use readable Markdown. Limited trusted HTML may be used for figures, captions, tables, or callouts where Markdown is insufficient.

### 4. Create images

Follow explicit method instructions embedded in the draft.

- Use Matplotlib/deterministic graphics for quantitative charts, geometry, comparisons, and engineering diagrams.
- Use the available OpenAI image-generation capability for conceptual/editorial images and thumbnail backgrounds.
- Never substitute one requested method for another without reporting it.
- Use the approved brand style in `references/image-style-guide.md`.
- Generate the creative thumbnail background without logo or final title.
- Compose the official logo, title, and branded treatment using `scripts/compose_thumbnail.py`.
- Optimize production images using `scripts/optimize_blog_images.py`.

When image generation is unavailable in the active environment, create a final, production-ready image request file and report the blocked step. Do not silently use an unrelated image.

### 5. Integrate

- Create/update the article Markdown file.
- Add production images to the article asset directory.
- Ensure image filenames, alt text, and captions are descriptive.
- Add contextually useful internal links.
- Add one relevant CTA.
- Add related articles only when genuinely relevant.
- Do not edit Python views for a normal article.

### 6. Validate

Run the repository equivalents of:

```bash
python manage.py validate_blog_content
python .agents/skills/blog-article/scripts/validate_article.py <article-file>
python .agents/skills/blog-article/scripts/validate_internal_links.py
python .agents/skills/blog-article/scripts/generate_registry.py
python manage.py check
```

Run relevant blog tests and visually inspect the article list and detail page.

Perform one focused correction pass if validation fails. If errors remain, stop and report them rather than entering an endless loop.

## Final report

Report:

- Mode.
- Title and slug.
- Primary keyword and search intent.
- Article file.
- Images created and method used for each.
- Thumbnail output.
- Internal links and CTA.
- Research notes/sources, when applicable.
- Validation and tests run.
- Pages visually inspected.
- Exact changed/generated files.
- Remaining warnings.
