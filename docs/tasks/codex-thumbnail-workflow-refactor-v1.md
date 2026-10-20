# Codex Task — Refactor KolliLabs Thumbnail Skill into an Approved AI Editorial Design System

**Agent:** Codex — Luna Extra High reasoning (or highest available equivalent)  
**Mode:** Repository audit → implementation → tests → two local pilots → approval checkpoint  
**Priority:** Brand repeatability, no regressions, factual integrity, minimal new architecture  
**Date:** 2026-10-20  
**Approval:** Implement and prepare pilot previews; **do not publish / replace live thumbnails without explicit owner approval**.

## 0. Governing documents and style assets

Read these supplied/repository files first:

1. `docs/blog/thumbnail-design-system-v1.md` — the complete agreed functional and visual design contract.
2. `docs/blog/assets/kollilabs-approved-thumbnail-board-v1.png` — **the exact owner-approved nine-tile image, primary visual source of truth**.
3. Existing thumbnail-generation skill instructions and scripts (locate them; do not assume a path).
4. Existing overarching blog/article writing skill, article registry, article-template/schema, editorial style, blog architecture, evidence/research policies, comparative benchmarking/figures guidance, any README and publishing setup. Follow the actual repository variants, not assumptions from this task.
5. Current templates and styling for the blog listing and blog article preview imagery, including image dimensions, responsive behavior, social/OG images, and storage conventions.

**IMPORTANT:** There is already a basic thumbnail skill. The task is to **inspect and refactor it in place**, reusing stable components and respecting other blog skills. Do not discard or replace it with a disconnected second system. The prior thumbnails varied widely: some were presentation-slide collages, some small UI screenshot comparisons, some charts, all with inconsistent layout. Fix the underlying workflow, not merely the wording of a prompt.

### Absolute style requirement

The reference collage has already been explicitly approved by the owner. It depicts a premium dark-teal studio atmosphere; large white and mint message on the left; an appealing, coherent 3D box/pallet/container/product scene on the right; `KOLLILABS / INSIGHTS` top-left; KolliLabs logo at bottom-left; restrained supporting text; cinematic lighting; and exceptionally consistent style across nine subjects.

**Do not:** reinterpret it as a white-background infographic, a screenshot-heavy engineering presentation, a loose family of unrelated generated cards, or a different design. The previous generated secondary “style-guide board” is **not** a replacement for the supplied approved original.

## 1. Desired product behavior

A user asks the existing blog workflow to draft/publish an article. The thumbnail skill automatically extracts a short, fact-grounded visual hook and an illustration plan from approved article content; it creates an AI subject illustration using the fixed art direction; code renders the same branded card every time; validators check it; and the user gets a preview and approval gate. The user never writes image prompts or decides lighting/camera/background from scratch.

Illustrations can be conceptual: **do not require real KolliPack screenshots**. When an exact packing arrangement or quantity is visually asserted, however, require verified evidence; an AI illustration must not be misrepresented as an actual solver result.

## 2. Scope and work order

### Phase A — Inspect and report before edits

Read the relevant code and skills and briefly record:

- Locations of current thumbnail skill, prompt files, render/generation code, article registry and publication interfaces.
- Current flow from article to thumbnail asset, from thumbnail asset to card/OG/social display.
- Current image model/API access, whether real reference images and alpha/transparent backgrounds are supported, API keys/configuration and costs/limits where documented.
- Existing requirements for article schema, naming, front matter, thumbnails, alt text, file sizes, social previews and deployment.
- Root causes of current visual variation **supported by inspection**, separating confirmed behavior from hypotheses.
- The minimal refactor strategy and any conflicts with the proposed file paths or contracts.

Do not stop at a generic audit: proceed to implement within the stated boundaries. If image generation cannot be exercised because credentials/provider integration are unavailable, continue with deterministic renderer and fixtures, report the blocker accurately, and do not fabricate successful end-to-end tests.

### Phase B — Commit the design system

- Use the supplied approved board unchanged under `docs/blog/assets/` or adapt paths only to pre-existing repo convention, with clear docs links.
- Establish versioned design tokens for near-black/deep-teal gradient, white and mint-green text, neutral captions, margins, typography, logo placement and illustration placement.
- Prefer the current verified KolliLabs logo asset; do not create an AI-rendered imitation.
- Document reference asset SHA-256 and the true provider/model limitation on style-reference usage.
- Define exactly one layout skeleton, allowing five **scene** families (`hero`, `comparison`, `improvement`, `benchmark`, `product`) without inventing five unrelated template styles.

### Phase C — Refactor existing skill, schema and prompt assembly

Within existing blog workflow conventions, implement:

1. `thumbnail-brief` schema and validator with:
   - `schema_version`, `article_slug`, `composition`, `hook_primary`, optional `hook_secondary`, `support_line`, `scene_subject`, `image_mode`, `supported_claims`, `screenshots_allowed=false`, `reference_standard`.
   - hook length budgets plus actual renderer text measurement; no hard-coded unjustified article data.
   - explicit evidence support for numeric/benchmark hooks.
2. `illustration-spec` schema and validator with:
   - scene family, allowed subjects, camera, materials, lighting, reserved blank zones, blending/alpha strategy, exclusions and mode.
3. Fixed, versioned base illustration prompt + approved scene-family clauses + validated article-specific variables.
4. Automatically generated complete prompt and metadata; save its revision for provenance.
5. `editorial_illustration` as the default; `evidence_derived` only when the actual visual data has been provided and verified.
6. A clean skill instruction update explaining the normal authoring trigger, direct re-generation action, approvals, limits, and failure paths.

**Do not** write brand words/logos into the AI illustration prompt if they would appear as generated lettering. The final renderer owns all text and logo.

### Phase D — AI illustration adapter

Implement a simple adapter around the currently suitable configured image-generation provider, **without assuming Codex itself has an image-generation endpoint**. Use supported official APIs/conventions already adopted in repo when possible. Must:

- Accept normalized subject specification + reference asset if provider supports visual conditioning.
- Produce the illustration, not the entire finished text-and-logo card.
- Prefer alpha-background source artwork when supported and reliable; otherwise integrate with dark teal studio background/masking and ensure clean seams.
- Record provider/model/revision and actual generation parameters, prompt, reference SHA, request ID if provided, timestamps, count of attempts, error reason, and usage estimates if available.
- Keep keys/config outside source; provide clear setup instructions; do not require internet/API calls in unit tests.
- Bound generation to **one primary + at most two retries** by default, with no unbounded loops.
- Fail loudly, preserve currently approved thumbnails, and report unsupported capabilities without asserting they ran.

Do **not** introduce a new dependency on Django or a customer-facing API to produce internal editorial assets. Use existing content tooling or a small well-scoped module/CLI as fits the repository.

### Phase E — Deterministic renderer

Implement one reusable branded renderer (SVG, existing HTML/CSS/Playwright, Pillow or comparable pre-existing stack—choose based on repo). It owns:

- `1280x720` 16:9 output (or compatible resized derivatives).
- Fixed deep-teal gradient / studio background.
- Text zones: upper-left brand kicker, large white/mint numeric/conceptual hook at left, short secondary text, bottom-left KolliLabs branding.
- Right-side illustrations with consistent scale, perspective positioning and proper feathering/alpha.
- Auto-line breaks and text-fitting; explicit failure on clipping/overflow, no illegible miniscule typography.
- Predictable export and deterministic behavior on a fixed input/environment.
- Ability to render fixture/mock illustrations when the provider is unavailable.

**Priority:** Match the owner-approved image rather than pursuing a substantially different implementation aesthetic. If a fully separate illustration and deterministic background creates visible seams, fix matte/edge blending or composite subject over a studio ground-plane layer; do not quietly switch to full AI-generated thumbnails.

### Phase F — QA, artifact management and fail-closed release

Implement appropriate tests/checks:

- **Hard checks:** schema, file dimensions/format, image existence, logo/font asset availability, margins, text overflow, export size/quality, path naming, output metadata correctness.
- **Fact checks:** numeric claims backed by source evidence; avoid implying exact visual counts from illustrative AI imagery.
- **Image-aware QA:** clean composition, consistent teal/white/mint palette, physical subject and lighting match anchor, no alien UI snippets or illegible text, no humans or clutter; human review required for subjective pass/fail.
- **Publication gates:** `draft → review_required → approved → staged/published` or match existing repository's approval model; no live replacement before owner confirmation.
- **Provenance:** store brief/spec/source prompt/reference SHA, generation parameters actually used, created assets, validation report, approval and release status, rollback target.
- **Rollback:** originals retained and restorable without changes to article content/SEO.

Keep original blog title/description/schema and real article evidence untouched. If there are conflicting current asset conventions, adapt the new workflow to them rather than rewriting unrelated blogging infrastructure.

### Phase G — Tests and proof

Provide automated tests covering at minimum:

1. Scene-family selection and schema validation for all five types.
2. Missing or unsupported numeric evidence causes review or rejection (never silent fabrication).
3. The same fixture inputs generate the same deterministic template layout.
4. Each template size/crop has no text clipping and is legible at reduced card dimensions.
5. A provider failure and reference-image unsupported case are surfaced accurately.
6. Retry cap is enforced, failures are persisted, and publishing remains fail-closed.
7. Existing published asset contracts, article generation, preview pages and SEO front matter are unaffected.
8. Actual output images are compared visually and/or through stable golden fixture checks for composition; do not assert that pixel differences in randomly generated image content are deterministic.

If UI screenshot comparisons are possible, supply before/after sample blog grid for review. Run only relevant safe tests and report exact commands and outcomes.

### Phase H — Two real article pilots — approval checkpoint

Use **existing source articles**, not invented articles:

**Pilot 1: business outcome / improvement**  
Article: the case moving **9,600 → 14,400 products** in the same container (`+50%`).  
Visual: cinematic, realistic loaded container in right zone; hero copy `+50%` / `MORE PRODUCTS` and `Same container. One different box.` or an editorially equivalent supported hook. Exact visible geometry need not replicate KolliPack engine output; do not imply it does.

**Pilot 2: research / benchmark**  
Article: **700 container-loading test cases**, with honest benchmark interpretation.  
Visual: tidy matrix of repeated container-loading motifs, not a generic bar chart. Hook `700` / `TESTS`; support `An honest benchmark of KolliPack.` No claim of a win-rate or superiority unless grounded.

Create both with the **same renderer and design token set**. Produce:

- Full-size individual outputs.
- Small card-width previews.
- Side-by-side contact sheet including the two new thumbnails and at least two nearby crops from the approved board.
- Brief/spec/validation/provenance files and a short checklist explaining where manual approval is required.

**STOP before replacing published thumbnails.** The human owner must approve the *actual generated pilot visuals*, not just the design system prose.

### Phase I — Conditional rollout plan (do not publish in this task)

After pilot approval, document how to migrate each current blog thumbnail to the new standard via dry run, then staged preview, then owner-approved replacement. Keep original images, restore procedure, article IDs, OG image references and cache behavior intact. Once accepted, new blog articles use this pipeline automatically and legacy thumbnail generation cannot silently bypass it.

## 3. Expected repository deliverables

Paths may follow actual established conventions. Document final locations.

```text
docs/blog/thumbnail-design-system-v1.md

docs/blog/assets/kollilabs-approved-thumbnail-board-v1.png

<existing-thumbnail-skill>/SKILL.md         # Updated skill instructions
<existing-blog-tooling>/...               # Structured brief/spec + render/generator/QA integration
<existing-tests>/...                      # Schema, renderer, provider-failure, publishing regression tests

<article-thumbnail-output>/pilot-50pct/
    thumbnail-brief.json
    illustration-spec.json
    illustration-v1.png
    thumbnail-v1.webp (or pipeline-standard format)
    thumbnail-validation.json
    thumbnail-provenance.json

<article-thumbnail-output>/pilot-700-tests/
    ... same deliverables ...

<preview-output>/pilot-contact-sheet.png
<preview-output>/pilot-card-width-previews.png
```

If the image API is unavailable, deliver renderer examples with clearly labeled fixtures and a blocker report; do **not** invent `illustration-v1.png` as a successful AI image output or claim that full pilot generation succeeded.

## 4. Acceptance criteria / definition of done

**Implementation complete** when:

- Existing thumbnail-generation skill is properly integrated into the blog workflow rather than duplicated.
- Approved nine-tile board is used unchanged as the canonical reference.
- Fixed renderer controls the identical positions/background/typography/logo every time.
- AI control is limited to illustration subject, with a stable base style/prompt and approved scene families.
- No manual end-user prompts are needed; article evidence creates the brief.
- The QA/approval gate is real, observable and fail-closed.
- Facts, article content, existing SEO fields and current published thumbnails are preserved.
- Deterministic automated tests pass.
- Two real pilot thumbnails have been generated if actual provider access permits, shown side-by-side at full and card scale, and **explicitly await owner visual approval**.

**Visual standard accepted** only after the owner approves the two pilot images as homogeneous and sufficiently close to the reference. Passing unit tests or successful calls to an image API is not visual approval.

## 5. Constraints / regressions to prevent

- No direct production deployment or unsanctioned DB migrations.
- No change to carton/pallet/container optimization engine logic, business calculations, or solver representations.
- No deletion of old thumbnails; always preserve rollback.
- No needless new Python/Django app or heavyweight UI if existing tooling suffices.
- No breaking article URLs, front matter, SEO tags, JSON contracts, images, or article registry.
- No auto-approving AI output because it meets hard file-size checks.
- No unverified product counts, geometry, optimization performance or claims based on AI-generated scenes.
- No arbitrary visual refresh away from the exact approved collage.
- No oversized back-and-forth iteration: first do the audit, then execute the minimal effective refactor, test and present two thoughtful previews.

## 6. Codex completion response format

Return a concise but detailed engineering handover with:

1. **Audit findings:** exact skill paths, root causes found (distinguish proven vs inferred), integration choices, image-provider limits.
2. **Code changes:** relevant files/modules and rationale, especially how the existing skill was improved.
3. **Tests:** commands run, pass/fail results, skipped steps with honest reasons.
4. **Pilot previews:** actual local image artifact paths and visual contact sheet, or clearly identified fixture-only screenshots if blocked.
5. **Provenance:** applied design/reference versions, image model actually used, reference mode support and generation attempt counts.
6. **Regression protection:** how old thumbnails, articles, SEO and existing pipelines were protected.
7. **Approval request:** explicitly ask for owner approval of the two pilots before existing thumbnails are replaced.
8. **Remaining risks:** visual style drift and generation/provider variability, with realistic mitigations.

**Do not describe as production-complete unless tests and visual owner approval actually occurred.**
