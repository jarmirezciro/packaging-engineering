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
- Candidate pilots and dry runs stay outside the release tree until the applicable release gate. An isolated preview may use the intended static paths for validation.

The implementation extends the existing `blog-article` skill and keeps `.agents/skills/blog-article/scripts/compose_thumbnail.py` as the stable entry point. Historical invocations without a subcommand retain the old generic composer behavior.

## Normal authoring trigger

When an article is drafted, refreshed, rewritten, or prepared for publication:

1. Read only approved article text/evidence and create `thumbnail-brief.json`.
2. Create `illustration-spec.json` with one of `hero`, `comparison`, `improvement`, `benchmark`, or `product`.
3. Validate both files and the canonical reference SHA.
4. Build the complete locked prompt. The author does not write a low-level image prompt.
5. Generate a subject-only illustration. No brand words, logo, headline, number, label, interface, or screenshot belongs in generated art.
6. Visually review the raw illustration against the approved board before rendering. Retry a clear failure within the cumulative three-attempt budget; do not present a failed candidate.
7. Render the final 1280×720 card with the deterministic renderer.
8. Inspect the full card and its 360×203 blog-card preview, then generate the validation report, provenance record, and comparison sheet.
9. Leave a passing candidate `review_required` pending owner approval, subject to the first-release policy below.

`editorial_illustration` is the default. Use `evidence_derived` only when the illustration is intended to show exact geometry/counts and verified source assets are supplied.

### First release of a new article

The [production workflow](production-workflow-v2.md#publication-intent-and-decision) permits a narrow exception to the individual owner-approval step. An explicit `direct_publish` request for a new article covers its newly generated first thumbnail. The full-size and 360×203 candidate must be inspected, deterministic checks must pass, and the final article and assets must pass Visual Editorial review. Complete the evidence, rights and any applicable human/legal checks before release.

Record the owner's publication request, the reviewer and actual inspection outcome, the validation and provenance references, and the selected path and SHA-256. This records the release authorization and the reviewed bytes. Keep the tool's approval fields and the existing `can_publish` owner-approval path intact. A `review_required` tool record supplies candidate evidence and must never be edited to simulate owner approval. Codex makes the first-release decision in the article workflow, based on the documented review and explicit authorization.

Failed or uninspected candidates remain blocked. This exception applies only to a new article's first release. `publish_approved`, staged replacements, changes to an existing approved thumbnail and requests that explicitly require review retain the normal owner-approval process. The canonical board, design standards and retry limits still apply.

## Commands

From the repository root, with a Python environment containing Pillow:

```powershell
python .agents/skills/blog-article/scripts/compose_thumbnail.py validate `
  --brief <candidate>/thumbnail-brief.json `
  --spec <candidate>/illustration-spec.json

python .agents/skills/blog-article/scripts/compose_thumbnail.py prompt `
  --brief <candidate>/thumbnail-brief.json `
  --spec <candidate>/illustration-spec.json `
  --output <candidate>/illustration-prompt.json

python .agents/skills/blog-article/scripts/compose_thumbnail.py generate `
  --brief <candidate>/thumbnail-brief.json `
  --spec <candidate>/illustration-spec.json `
  --output <candidate>/illustration-v1.png `
  --attempts-report <candidate>/illustration-attempts.json `
  --prompt-record <candidate>/illustration-prompt.json `
  --max-attempts 3

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
  --generation-report <candidate>/illustration-attempts.json `
  --prompt-record <candidate>/illustration-prompt.json

python .agents/skills/blog-article/scripts/compose_thumbnail.py gallery `
  --item "Article label=<candidate>/thumbnail-v1.webp" `
  --item "Second label=<other-candidate>/thumbnail-v1.webp" `
  --output <preview-dir>/thumbnail-contact-sheet.png `
  --columns 3
```

The gallery command renders every supplied thumbnail at the real 360×203 blog-card review size and adds labels outside the card artwork. Use it for rollout-wide consistency review; it never stages or publishes an asset.

When a generation tool needs a tool-specific addendum, save it with `--append-instruction` before generation and pass that exact record to both `generate` and `render` with `--prompt-record`. This keeps provenance tied to the actual complete prompt rather than only the locked base template.

### Required pre-presentation visual review

Before rendering or presenting the candidate, inspect the raw illustration at full size beside the approved nine-thumbnail board. Check photorealistic commercial 3D quality; believable corrugated-cardboard fibre/flutes, wood grain, plastic thickness/finish, and other relevant materials; physical geometry and scale; perspective; lighting, contact shadows, and depth; the right-side subject/left-side negative-space composition; clutter; and family consistency. Compare the complete rendered card to the board again at 1280×720 and at the actual 360×203 blog-card size. At card size, the topic and subject must still read clearly, and the headline must remain legible.

Use `static/img/blog/capepack-kollipack-bottle-case-pallet-benchmark/thumbnail-approved.png` as a qualitative realism regression example for bottle, cardboard, pallet, surface, scale, and lighting quality. The nine-thumbnail board remains the authority for thumbnail-family composition, palette, and brand treatment; do not copy the CapePack example's text, layout, or claims.

Fail the illustration only for a clear issue such as flat/cartoon/clip-art rendering, generic smooth materials, implausible geometry or scale, weak or inconsistent lighting, a tiny/poorly placed subject, clutter, generated lettering/branding, or a visual implication that is not supported by the brief. Record a concise finding in the attempt report using `--review-rejected --review-note`. Keep the failed illustration and prompt record, make one targeted prompt addendum, and generate the next version to a new filename. The same `illustration-attempts.json` tracks all calls across visual retries; `--max-attempts 3` is a total cap, including provider errors and visually rejected generations. If all three attempts fail review, stop and report that outcome without presenting it as a candidate for approval.

For example, after rejecting v1 for smooth cardboard, create `illustration-prompt-v2.json` with the same locked prompt plus a narrow correction, then run:

```powershell
python .agents/skills/blog-article/scripts/compose_thumbnail.py prompt `
  --brief <candidate>/thumbnail-brief.json `
  --spec <candidate>/illustration-spec.json `
  --output <candidate>/illustration-prompt-v2.json `
  --append-instruction "Make the corrugated cardboard visibly fibrous with clear folded edges and believable flute detail; preserve the established scene and camera."

python .agents/skills/blog-article/scripts/compose_thumbnail.py generate `
  --brief <candidate>/thumbnail-brief.json `
  --spec <candidate>/illustration-spec.json `
  --prompt-record <candidate>/illustration-prompt-v2.json `
  --output <candidate>/illustration-v2.png `
  --attempts-report <candidate>/illustration-attempts.json `
  --max-attempts 3 `
  --review-rejected `
  --review-note "Cardboard read as smooth plastic at full size."
```

Do not use the review as a request to add text, logos, labels, graphics, or other layout content to generated art. The renderer remains responsible for the complete background, typography, logo, and card layout.

If the final card-size review exposes an illustration problem—such as an unreadable or undersized subject, weak material detail, poor contact shadows, or clutter—reject that illustration through the same cumulative attempt report and generate the next version. If the issue is headline fitting, contrast, or deterministic placement, correct the relevant editorial/renderer inputs; do not ask the image model to solve layout or typography.

Direct regeneration uses the same brief/spec unless the evidence or intended message changed. Keep prior illustration and thumbnail versions; write `illustration-v2.png`/`thumbnail-v2.webp` rather than overwriting an approved candidate. After a visual rejection, reuse the same attempt report and set `--review-rejected --review-note "<specific observed issue>"`; save a targeted revised prompt record and write to the next illustration version.
For a typography-only rerender that reuses an approved illustration, record zero generation attempts, `generation_performed: false`, and `illustration_reused: true`; do not imply that an image-provider call occurred.

## Optional official Images API adapter

The `generate` subcommand is an optional local adapter around the official OpenAI Images API. It uses `OPENAI_API_KEY`, defaults to the pinned `gpt-image-2.5-sunburst-2026-09-08` model, automatically resolves the immutable approved board, submits it as the `image` file input to `images.edit`, requests a transparent PNG, and persists every attempt. Reference conditioning is marked `used` only after the edit request returns an image payload. The attempt report and rendered provenance record the reference status, supplied-image SHA-256, request ID, usage (when returned), and cumulative attempt count. The budget is one primary plus at most two retries across provider failures and visual rejections. Keys are never written to assets or provenance.

The official Python SDK exposes edited-image inputs as uploaded files through the `image` argument to `images.edit`; the adapter uses that request shape ([SDK method](https://github.com/openai/openai-python/blob/main/src/openai/resources/images.py)). Model/account availability, organization verification, quotas, and cost remain account-specific. Record actual response usage and request ID when returned. Never claim reference conditioning, alpha, model identity, cost, or a successful request unless the provider response established it.

Offline tests use fake providers and make no API calls. The normal Codex image-generation tool may be used for an editorial pilot, but its provenance must state any undisclosed provider/model/request fields as undisclosed or null.

## Fail-closed behavior

- Missing/changed approved reference: reject.
- Invalid brief/spec or unsupported numeric hook: reject.
- A provider that cannot accept references must report `not_supported`/`false`; it must never claim reference-conditioned generation. Apply the pinned visual prompt and enhanced visual review if text-only generation is available.
- Provider/alpha capability failure: persist the limitation and stop that generation path.
- Three total attempts, counting provider failures and visual rejections: stop; do not retry again automatically.
- Text overflow, missing font, invalid size/format, missing illustration, or bad path: reject.
- Subjective visual match requires actual inspection. Use the owner-approval route by default and the first-release exception only under the conditions above.
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
