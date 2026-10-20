# Thumbnail Workflow v1

Use this workflow for every new or regenerated KolliLabs blog thumbnail. The owner-approved visual source of truth is:

```text
docs/blog/assets/kollilabs-approved-thumbnail-board-v1.png
SHA-256 8cbfd1f852273f4a6b20c7e47abb25ffdbd675607fa88c03fa4dd48e46bb547b
```

The board is a style reference, not calculation evidence. The specific design contract is `docs/blog/thumbnail-design-system-v1.md` and overrides the older light-background figure guidance for thumbnails only. Article figures keep their existing light editorial system.

## Existing integration boundary

- `packagingapp/content/blog/articles/<slug>.md` remains the article registry.
- `thumbnail`/`featured_image` remain static-relative paths; `og_image` may reuse the same asset.
- `packagingapp/services/blog_repository.py`, the marketing views, and the blog templates remain consumers. They do not generate thumbnails.
- Production assets remain under `static/img/blog/<slug>/`.
- Candidate pilots and dry runs stay outside that production tree until owner approval.

The implementation extends the existing `blog-article` skill and keeps `.agents/skills/blog-article/scripts/compose_thumbnail.py` as the stable entry point. Historical invocations without a subcommand retain the old generic composer behavior.

## Normal authoring trigger

When an article is drafted, refreshed, rewritten, or prepared for publication:

1. Read only approved article text/evidence and create `thumbnail-brief.json`.
2. Create `illustration-spec.json` with one of `hero`, `comparison`, `improvement`, `benchmark`, or `product`.
3. Validate both files and the canonical reference SHA.
4. Build the complete locked prompt. The author does not write a low-level image prompt.
5. Generate a subject-only illustration. No brand words, logo, headline, number, label, interface, or screenshot belongs in generated art.
6. Render the final 1280×720 card with the deterministic renderer.
7. Generate a 360×203 preview, validation report, provenance record, and comparison sheet.
8. Leave the candidate `review_required`. Only explicit owner approval may advance it to staging or replace the published asset.

`editorial_illustration` is the default. Use `evidence_derived` only when the illustration is intended to show exact geometry/counts and verified source assets are supplied.

## Commands

From the repository root, with a Python environment containing Pillow:

```powershell
python .agents/skills/blog-article/scripts/compose_thumbnail.py validate `
  --brief <candidate>/thumbnail-brief.json `
  --spec <candidate>/illustration-spec.json

python .agents/skills/blog-article/scripts/compose_thumbnail.py prompt `
  --brief <candidate>/thumbnail-brief.json `
  --spec <candidate>/illustration-spec.json `
  --output <candidate>/illustration-prompt.json `
  --append-instruction <exact-tool-specific-instruction-if-used>

python .agents/skills/blog-article/scripts/compose_thumbnail.py render `
  --brief <candidate>/thumbnail-brief.json `
  --spec <candidate>/illustration-spec.json `
  --illustration <candidate>/illustration-v1.png `
  --output <candidate>/thumbnail-v1.webp `
  --validation <candidate>/thumbnail-validation.json `
  --provenance <candidate>/thumbnail-provenance.json `
  --provider <actual-provider> `
  --model <actual-model-or-undisclosed-by-tool> `
  --reference-mode <actual-reference-mode> `
  --attempts <actual-attempt-count> `
  --prompt-record <candidate>/illustration-prompt.json

python .agents/skills/blog-article/scripts/compose_thumbnail.py gallery `
  --item "Article label=<candidate>/thumbnail-v1.webp" `
  --item "Second label=<other-candidate>/thumbnail-v1.webp" `
  --output <preview-dir>/thumbnail-contact-sheet.png `
  --columns 3
```

The gallery command renders every supplied thumbnail at the real 360×203 blog-card review size and adds labels outside the card artwork. Use it for rollout-wide consistency review; it never stages or publishes an asset.

When a generation tool needs a tool-specific addendum, save it with `--append-instruction` before generation and pass that exact record back to `render` with `--prompt-record`. This keeps provenance tied to the actual complete prompt rather than only the locked base template.

Direct regeneration uses the same brief/spec unless the evidence or intended message changed. Keep prior illustration and thumbnail versions; write `illustration-v2.png`/`thumbnail-v2.webp` rather than overwriting an approved candidate.
For a typography-only rerender that reuses an approved illustration, record zero generation attempts, `generation_performed: false`, and `illustration_reused: true`; do not imply that an image-provider call occurred.

## Optional official Images API adapter

The `generate` subcommand is an optional local adapter around the official OpenAI Images API. It uses `OPENAI_API_KEY`, defaults to the pinned `gpt-image-2.5-sunburst-2026-09-08` model, submits the approved board through the image-edit/reference path, requests a transparent PNG, and persists every attempt. The default budget is one primary plus at most two retries. Keys are never written to assets or provenance.

As documented by OpenAI on 2026-10-20, current GPT Image 2.5 models accept reference images through the image-edit endpoint and support transparent PNG/WebP output. Model/account availability, organization verification, quotas, and cost remain account-specific. Record actual response usage and request ID when returned. Never claim reference conditioning, alpha, model identity, cost, or a successful request unless the provider response established it.

Offline tests use fake providers and make no API calls. The normal Codex image-generation tool may be used for an editorial pilot, but its provenance must state any undisclosed provider/model/request fields as undisclosed or null.

## Fail-closed behavior

- Missing/changed approved reference: reject.
- Invalid brief/spec or unsupported numeric hook: reject.
- Provider/reference/alpha capability missing: persist failure and stop.
- Three failed attempts: stop; do not retry again automatically.
- Text overflow, missing font, invalid size/format, missing illustration, or bad path: reject.
- Subjective visual match: always `review_required` until a human approves it.
- Provider success or hard-check success never means publication approval.
- Existing published article metadata and assets remain untouched on every failure.

## Logo and font limitation

The repository currently has no standalone canonical KolliLabs logo/wordmark file. The public header composes a Bootstrap icon and text in HTML/CSS. For v1 pilots, the renderer extracts the already owner-approved lower-left lockup from the canonical board without asking the image model to recreate it. This is an explicit interim dependency. Replace it only when the owner supplies and approves a canonical logo asset; bump the renderer version and re-run the contact sheet.

The renderer uses the existing Windows/Pillow sans-serif candidates recorded in the versioned token file and fails if none are available.

## Conditional rollout after pilot approval

1. Inventory article slug, existing `thumbnail`/`featured_image`/`og_image`, current asset SHA, and cache-visible URL.
2. Generate a versioned candidate outside the production path.
3. Validate and show the article card/detail/social preview in a dry run.
   The current blog grid adds an article-type chip at the image's upper-left;
   check it against the thumbnail kicker and change that shared template only
   as part of an owner-approved staged rollout, not during pilot generation.
4. Obtain owner approval for the actual image.
5. Copy the approved candidate to a new versioned production filename; retain the original file.
6. Update only the approved article image fields together, stage, and verify static-cache behavior.
7. Roll back by restoring the prior front-matter paths. Article content, SEO copy, dates, slugs, routes, and calculation evidence do not change.

Legacy article-specific thumbnail functions must not be used silently for future thumbnails. Keep them only to reproduce historical assets until each article receives an approved migration.
