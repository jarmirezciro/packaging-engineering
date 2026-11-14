---
name: blog-article
description: Research, reproduce engineering cases, write, illustrate, audit, refine, and integrate KolliLabs/KolliPack blog articles. Use for evidence-led benchmarks, engineering articles, practical demos, approved-artifact integration, and calibration from owner feedback.
---

# KolliLabs Blog Article Skill

Use this skill to create a new KolliLabs article, rewrite or polish a draft, refresh an existing article, or turn a KolliPack calculation case into a business-oriented demo article.

## Supported modes

Start with the [production workflow](references/production-workflow-v2.md). It routes the mode and editorial profile, hands evidence through writing, figures and QA, and determines whether the result can be integrated or published.

- `benchmark_from_evidence`: investigate a comparator result using supplied source evidence and a bounded KolliPack reproduction when possible.
- `research_deep_dive`: research and explain an engineering principle or decision.
- `demo_from_case`: produce a concise practical demo from a reproducible KolliPack case.
- `refine_article`: make a scoped correction while preserving unrelated approved material.
- `calibrate_from_feedback`: turn owner feedback into traceable examples, regression coverage and review guidance.

The existing modes remain available:

- `polish`: improve a substantially complete author draft.
- `research`: turn notes or questions into a sourced article.
- `refresh`: substantively update an existing article while preserving its identity.
- `rewrite`: rebuild an existing article's title, hook, narrative, clarity, visuals, and SEO while preserving approved evidence and slug.

<!-- BEGIN KOLLILABS_BLOG_SKILL_UPDATE_V1:mode -->
- `publish_approved`: integrate owner-approved text and image files unchanged (apart from required metadata/path integration), verify the linked case and publish only with explicit authorization. Follow `references/publish-approved-artifact.md`. Skip the normal rewrite, title-lab, image generation and backend redesign steps unless the owner separately requests them.
<!-- END KOLLILABS_BLOG_SKILL_UPDATE_V1:mode -->

## Article profiles

Choose the editorial profile before drafting and map it to existing metadata using the production workflow and `references/article-schema.md`.

- `demo_case_study`: a reproducible KolliPack case using real inputs, outputs, figures, and a prepopulated tool link.
- `engineering_deep_dive`: formulas, geometry, algorithms, standards, or detailed packaging principles.
- `practical_guide`: step-by-step packaging guidance.
- `business_insight`: a business decision, trade-off, or operational lesson.
- `kollipack_update`: a product capability or release explanation.
- `sustainability`: material, transport, waste, or environmental analysis.

Read `references/demo-case-study-profile.md` whenever the selected profile is `demo_case_study`.
When a demo case names or compares another tool or vendor, also read
`references/comparative-benchmarking.md` and `docs/research/benchmarks.md`.

## Required inputs

Resolve from the task, source package, or current repository:

- Mode and article profile.
- Source text, brief, or `discussion.txt`.
- Intended audience.
- Relevant KolliPack tool.
- Exact case inputs when the article is a demo.
- Existing screenshots and figures.
- Figure source groups and intended comparison layout.
- Required CTA and prepopulated case URL.
- Requested image method.
- Latest project version when backend reproduction is required.
- Source link, capture date, version, and comparison assumptions when another tool or vendor is named.

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
10. Use the production workflow's publication intent and preserve the live edition when preparing a revision for review.
11. Treat competitor comparisons as bounded technical benchmarks, not complete product evaluations or legal opinions.

# Editorial workflow

Use the sequence and handoffs in the production workflow. Apply the steps below where relevant to the mode. A targeted correction starts at the affected component. Feedback calibration routes through the regression register and existing review guidance.

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

Before drafting, create a short editorial contract containing the primary audience, business
decision, business consequence, approved workflow scope, first-block result, comparison claim,
figure plan, and CTA action. Treat explicit author scope as binding. Do not infer downstream
workflow stages from a tool URL, application name, or available implementation.

Check for topic overlap and keyword cannibalization.

When another tool or vendor is named, establish the comparison scope, source provenance,
capture date, version or plan, and required affiliation/disclosure language before drafting.
Use `references/comparative-benchmarking.md` for the comparison review.

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
- Public comparator source, screenshots, recording date, product/version details, and any supplied comparison notes.

Create an internal evidence map. Do not begin drafting before the evidence map and story angle are clear.

If the evidence is incoherent, incomplete, or contradictory, stop drafting. Identify the exact
conflict and ask the author for corrected evidence or clarification. Never select the value,
screenshot, or interpretation that makes the better story.

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

For external-tool comparisons:

- Scope every conclusion to the stated fixture, inputs, versions, settings, and source date.
- Distinguish matched outputs from claims about usability, coverage, or product capability.
- State that KolliPack is independent of the named vendor and does not imply endorsement.
- Avoid unsupported claims of superiority, equivalence, accuracy, savings, or universal optimality.
- Include a compact comparison limitation block and flag the article for human/legal review when the reference requires it.

## 8. Create or revise figures

<!-- BEGIN KOLLILABS_BLOG_SKILL_UPDATE_V1:figure-contract -->
### Required figure-pattern selection and approved-content preservation

Before drawing figures, determine whether the article needs a **Packaging Scenario Setup**: the physical chain appropriate to its actual scope, which can be Product → Bag, Product → Case, Case → Pallet, Pallet → Transport, Product → Case → Pallet → Transport, mixed loads, or branches. Follow `references/packaging-scenario-setup.md`. The approved reference at `assets/approved-packaging-scenario-setup-reference.webp` specifies *visual quality and style*, not fixed inputs, stages or geometry. Do not add unavailable or out-of-scope stages.

Keep **physical scenario illustrations** distinct from **software input comparisons** and **evidence-based result renders**. A conceptual illustration can be attractive but must not assert unverified geometry or quantities. In comparator articles, real results remain sourced from real screenshots/backend data; neither invented vendor UI nor decorative cubes count as result evidence.

If the request is to integrate finished owner-approved copy and figures, use `publish_approved` and `references/publish-approved-artifact.md`. In other modes preserve each approved artifact outside the authorized change.

Before integrating any new figure, inspect the rendered image at its native resolution and actual article/mobile display size and apply `references/visual-editorial-critic.md`. Never pass a result solely because its code produced a valid PNG/WebP.
<!-- END KOLLILABS_BLOG_SKILL_UPDATE_V1:figure-contract -->


Follow `references/image-style-guide.md`.
For multi-tool or multi-result comparisons, also follow
`references/comparative-figure-workflow.md`.

For every new or regenerated blog thumbnail, also read and follow
`references/thumbnail-workflow.md`. The owner-approved thumbnail board and
`docs/blog/thumbnail-design-system-v1.md` are authoritative for thumbnails;
the older light editorial figure style remains authoritative for non-thumbnail
article figures. Use its validated brief/spec, subject-only art and deterministic
composition. Apply the [thumbnail release rules](references/thumbnail-workflow.md#first-release-of-a-new-article)
when the owner explicitly requests direct publication of a new article. A
regeneration writes a versioned candidate while preserving the approved asset.

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
- Let raw screenshots determine the article structure; compose them around the approved reader
  decision and case scope.

## 9. Run the Fresh-Eyes Business Reader review

Follow `references/fresh-eyes-business-reader.md`.

Temporarily ignore the source brief and backend notes. Review only:

- Title.
- Article body.
- Figures.
- Captions.
- CTA.

Choose the most relevant non-expert persona. Apply the recommended revisions before continuing.


<!-- BEGIN KOLLILABS_BLOG_SKILL_UPDATE_V1:visual-gate -->
## 9A. Run the Visual Editorial Critic (hard gate)

Follow `references/visual-editorial-critic.md` **after figures are rendered**. Review each finished figure and the actual rendered article at realistic desktop and mobile widths. A narrow preview/render inspection is authorized by this gate; it is not permission for broad browser regression testing or engine modifications. This is additional to Fresh-Eyes Business Reader, not a replacement. Prefer a review isolated from the creator; if an independent review is unavailable, disclose self-review. A figure with cropped geometry, tiny unreadable results, unsupported packaging counts, confusing scale or unused out-of-scope stages fails. Block publication if Visual QA is `FAIL`, `REVISE` or `NOT REVIEWED`.

For `publish_approved`, visual QA checks that the approved assets remain complete and legible **without redesigning them**. Any proposed change to approved content must be returned to the owner for approval.
<!-- END KOLLILABS_BLOG_SKILL_UPDATE_V1:visual-gate -->

## 10. Perform the SEO pass

Follow `references/seo-rules.md`.

For demo articles:

- The tool landing page owns broad transactional keywords.
- The article should target a specific informational question or case.
- Link naturally to the relevant tool page.
- Include the exact prepopulated case CTA.
- Do not keyword-stuff.

## 11. Prepare integration

- Prepare article Markdown and assets for the production paths using the workflow's candidate review and integration sequence.
- Preserve stable slugs.
- Use descriptive image filenames, alt text, and captions.
- Add useful internal links.
- Add related articles only when genuinely relevant.
- Preserve the working case URL.
- Preserve current publication status when preparing a revision for review.

## 12. Validate

Run the Iteration 2 auditor and complete the applicable evidence, editorial, visual and
preservation checks using the [quality checklist](references/quality-checklist.md). Follow the
[publication decision](references/production-workflow-v2.md#publication-intent-and-decision)
before integrating a published version, then verify the final artifact. A focused
correction reruns affected and dependent checks. Report any remaining blocker.

# Final report

<!-- BEGIN KOLLILABS_BLOG_SKILL_UPDATE_V1:final-report -->
- Visual QA results for each image and the complete page, including whether the review was independent or a self-review.
- Packaging Scenario Setup stages and whether the image is conceptual or evidence-derived.
- In `publish_approved` mode, file checksums and any authorized changes to supplied text/assets.
<!-- END KOLLILABS_BLOG_SKILL_UPDATE_V1:final-report -->


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
- Comparator, source date/version, comparison scope, disclosure, and review status when applicable.
- Minimal validation run.
- Publication intent, readiness, authorization, and actual repository or live publication state.
- Exact files changed.
- Remaining warnings.

<!-- BEGIN KOLLILABS-EDITORIAL-FIGURES-V1 -->
## KolliLabs Editorial Concept Figure System

For conceptual **case setups, engineering concepts, trade-offs, illustration-led summaries and explanatory schemas**, read `../kollilabs-editorial-figures/SKILL.md` and use its owner-approved visual references, JSON figure specification, design tokens, and deterministic composition renderer. The blog-article skill remains authoritative for editorial evidence, source fidelity, publication and visual approval. For real application comparison results continue to use `references/comparative-figure-workflow.md`; AI conceptual graphics must never replace screenshots or verified geometry.
<!-- END KOLLILABS-EDITORIAL-FIGURES-V1 -->
