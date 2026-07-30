---
name: blog-article
description: Create, rewrite, research, refresh, illustrate, validate, and integrate KolliLabs/KolliPack blog articles using the repository's file-based article architecture and current KolliPack evidence.
---

# KolliLabs Blog Article Skill

Use this skill to create a new KolliLabs article, rewrite or polish a draft, refresh an existing article, or turn a KolliPack calculation case into a business-oriented demo article.

## Supported modes

- `polish`: improve a substantially complete author draft.
- `research`: turn notes or questions into a sourced article.
- `refresh`: substantively update an existing article while preserving its identity.
- `rewrite`: rebuild an existing article's title, hook, narrative, clarity, visuals, and SEO while preserving approved evidence and slug.

## Article profiles

Choose the article profile before drafting.

- `demo_case_study`: a reproducible KolliPack case using real inputs, outputs, figures, and a prepopulated tool link.
- `engineering_deep_dive`: formulas, geometry, algorithms, standards, or detailed packaging principles.
- `practical_guide`: step-by-step packaging guidance.
- `business_insight`: a business decision, trade-off, or operational lesson.
- `kollipack_update`: a product capability or release explanation.
- `sustainability`: material, transport, waste, or environmental analysis.

Read `references/demo-case-study-profile.md` whenever the selected profile is `demo_case_study`.

## Required inputs

Resolve from the task, source package, or current repository:

- Mode and article profile.
- Source text, brief, or `discussion.txt`.
- Intended audience.
- Relevant KolliPack tool.
- Exact case inputs when the article is a demo.
- Existing screenshots and figures.
- Required CTA and prepopulated case URL.
- Requested image method.
- Latest project version when backend reproduction is required.

Do not ask unnecessary questions. Infer conservative defaults from the article library and report material assumptions.

## Repository rules

1. Read `references/blog-architecture.md` before editing.
2. Inspect existing article metadata before choosing a topic, keyword, or slug.
3. Store article Markdown in the configured article-content directory.
4. Store production images under `static/img/blog/<slug>/`.
5. Do not add article bodies to Python view files.
6. Do not change routes, templates, loaders, schema, presets, UI, or engines during normal article creation.
7. Do not regenerate or redraw the official logo.
8. Do not commit, push, merge, deploy, or publish unless explicitly requested.
9. Preserve existing working prepopulated case routes.
10. Keep rewritten articles in `draft` unless publication is explicitly requested.

# Editorial workflow

## 1. Classify and establish the brief

Determine:

- Mode.
- Article profile.
- Reader problem.
- Primary audience.
- Search intent.
- Primary keyword.
- One-sentence promise.
- Relevant tool or workflow.
- Required evidence.
- Business-context need.
- Figure plan.
- CTA and prepopulated URL.

Check for topic overlap and keyword cannibalization.

## 2. Inspect the case package

For a supplied ZIP or folder, follow `references/case-package-contract.md`.

Read:

- `discussion.txt` or brief.
- Existing article, when present.
- Input screenshots.
- Result screenshots.
- Existing figures and thumbnail.
- Structured result files.
- Current prepopulated case link.

Create an internal evidence map. Do not begin drafting before the evidence map and story angle are clear.

## 3. Reproduce demo cases through the backend

For `demo_case_study`, follow `references/backend-evidence-policy.md`.

Run the current shared KolliPack backend once with the supplied inputs.

Use the backend run to:

- Verify numerical claims.
- Check screenshots and author observations.
- Find relevant alternatives or result details.
- Enrich the discussion.

Do not:

- Duplicate engine formulas.
- Change backend code.
- Run broad regression tests.
- Start browser automation.
- Take screenshots.
- Turn the article task into engine debugging.

When evidence conflicts, report the discrepancy. Never silently select a convenient value.

## 4. Develop the business context

Follow `references/business-context-and-product-selection.md`.

Use the author's `discussion.txt` as the primary source of intent. Make the case concrete through a representative, plausible product and supply-chain setting.

Prefer a representative product category over an invented real customer.

Never fabricate:

- Contracts.
- Customer names.
- Shipment volumes presented as facts.
- Costs.
- Damage rates.
- Supplier results.
- Proven sustainability savings.
- Retail or operational requirements not supplied by the author.

## 5. Find the editorial angle

Before writing, define:

- Reader problem.
- Apparent or initially attractive answer.
- Surprising result.
- Business consequence.
- Remaining decision or uncertainty.
- One-sentence article promise.

Use `references/title-and-story-rubric.md`.

The strongest verified numerical or operational contrast should usually guide the article.

## 6. Run the title laboratory

Generate and score at least six candidates across:

- Result-led.
- Problem-led.
- Business-led.
- Curiosity-led.
- SEO-led.

Select separate values for:

- Visible article title.
- SEO title.
- Thumbnail headline.

Do not force an awkward keyword into the visible title.

## 7. Draft the article

Follow:

- `references/editorial-style.md`
- `references/article-schema.md`
- `references/seo-rules.md`
- The selected article profile

For demo articles:

- Put the strongest result within the first 100 words.
- Explain why it matters commercially.
- Use one continuous decision story.
- Explain technical terms once in plain language.
- Distinguish calculated output from physical validation.
- Avoid interface documentation unless an interaction is central to the lesson.
- Avoid repeated disclaimers and repeated numbers.

## 8. Create or revise figures

Follow `references/image-style-guide.md`.

Use the supplied real KolliPack screenshots and renders when claims depend on tool results.

Prefer deterministic composition for:

- Cropping.
- Comparison figures.
- Labels.
- Captions.
- Thumbnail layout.
- WebP optimization.

Do not:

- Create fake UI screenshots.
- Change numerical values visible in screenshots.
- Remove relevant approved images merely to shorten the article.
- Make every screenshot a separate oversized figure.

## 9. Run the Fresh-Eyes Business Reader review

Follow `references/fresh-eyes-business-reader.md`.

Temporarily ignore the source brief and backend notes. Review only:

- Title.
- Article body.
- Figures.
- Captions.
- CTA.

Choose the most relevant non-expert persona. Apply the recommended revisions before continuing.

## 10. Perform the SEO pass

Follow `references/seo-rules.md`.

For demo articles:

- The tool landing page owns broad transactional keywords.
- The article should target a specific informational question or case.
- Link naturally to the relevant tool page.
- Include the exact prepopulated case CTA.
- Do not keyword-stuff.

## 11. Integrate

- Create or update the article Markdown.
- Add or update article assets.
- Preserve stable slugs.
- Use descriptive image filenames, alt text, and captions.
- Add useful internal links.
- Add related articles only when genuinely relevant.
- Preserve the working case URL.
- Keep the article in draft.
- Regenerate the registry when required.

## 12. Validate

Use the validation level appropriate to the task.

For editorial demo-article rewrites with focused backend reproduction, run only:

```bash
python .agents/skills/blog-article/scripts/validate_article.py <article-file>
```

Also confirm:

- Referenced image files exist.
- CTA strings match the approved prepopulated URLs.
- WebP files open and have expected dimensions.
- Registry is regenerated when required.

Do not run broad Django, browser, screenshot, deployment, or engine tests unless explicitly requested.

Perform one focused correction pass. Stop and report remaining problems instead of entering repeated loops.

# Final report

Report:

- Mode and article profile.
- Final visible title, SEO title, and thumbnail headline.
- Slug and article file.
- Backend entry points called.
- Inputs reproduced.
- Headline outputs and discrepancies.
- Business context chosen.
- Fresh-Eyes persona used.
- Images and figures revised.
- CTA and prepopulated URL.
- Primary keyword and search intent.
- Minimal validation run.
- Exact files changed.
- Remaining warnings.
