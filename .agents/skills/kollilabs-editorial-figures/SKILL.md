---
name: kollilabs-editorial-figures
description: Create, validate, and reproducibly compose KolliLabs conceptual editorial figures for case setups, engineering concepts, trade-offs, comparisons, and summaries, using the two owner-approved visual references. Keep factual evidence figures separate.
---

# KolliLabs Editorial Figures — Production Skill v1.0

## Goal
Create **recognizably consistent** KolliLabs blog illustrations across different subjects and layouts. **Do not reproduce a figure's case-specific facts just because it is the style reference.** Reproduce the graphical language, not the benchmark itself.

## Canonical references — mandatory
- `assets/approved-bottle-case-pallet-setup.png` — physical workflow visual language (owner-approved example).
- `assets/approved-allowance-overhang-concept.png` — engineering concept visual language (owner-approved example).
- `assets/design-tokens.json` — deterministic graphic styling.

Inspect both reference images before producing any new figure. Use their **off-white backgrounds, large navy title, modest muted subtitle, large complete warm-toned isometric objects, quiet white rounded cards, green numbered badges and arrows, concise soft-gray input strips, and restrained pale-green takeaway band**. Preserve their fidelity; do not regenerate or edit these references.

## Scope and figure selection
This skill covers *editorial explanations*, not numeric benchmark proofs:

| Need | Pattern | Typical structure |
|---|---|---|
| Packaging Scenario Setup | `setup_flow` | product → case → pallet, or product → packaging catalogue → selected case |
| Engineering mechanism | `concept_flow` | parameter → mechanism → consequence |
| Decision trade-off | `tradeoff` | option/benefit → drawback/check; two or three cards |
| Alternatives | `comparison` | two to four side-by-side alternatives, no invented metrics |
| Key lessons | `summary` | one hero or two-to-five concise findings |
| Single concept | `single_explainer` | one central image plus one explanation card |

Choose **one central message** and the **smallest honest layout**. Three cards are *not* mandatory. Do not force arrows between nonsequential alternatives, a bottom banner without a real takeaway, or a transport stage if the study ends at palletization.

## Core production workflow
1. **Evidence + figure brief.** Read actual scenario, approved article scope, source values, and source status. Write a JSON figure specification according to `schema/figure-spec.schema.json` and `references/figure-specification.md`. If facts conflict, do not invent or silently reconcile them.
2. **Select visual roles.** For conceptual mechanisms, use conceptual, count-agnostic editorial illustrations. For results, direct readers to the established `blog-article/references/comparative-figure-workflow.md` using authentic tool screenshots/verified backend geometry. Never pass an AI drawing as calculated outcome.
3. **Illustrate subjects only.** For new objects, produce independent PNG/WebP illustrations with no captions, labels, logos, UI, numbers or graphic cards. Use `references/illustration-direction.md` and the actual approved style images as visual references when supported. If reference conditioning is unavailable, record that limitation, and rely on visual QA; do not falsely claim exact matching.
4. **Compose deterministically.** Use the supplied `scripts/render_figure.py` with `assets/design-tokens.json` and the figure spec. The renderer owns **all text**, cards, badge numbers, arrows, margins, colors, and takeaway placement. Do not rely on an image generator for embedded text or exact numeric labels.
5. **Review final visible output.** Inspect at native resolution, at ~900px article width, and ~360px mobile width. Apply `references/visual-qa.md`; fix at most one focused pass, or return the asset as `REVISE`/`NOT REVIEWED`. Separate evidence verification and owner approval are still required.
6. **Publish only on explicit authorization.** Create candidate files outside existing published article assets. Blog article integration follows the existing blog skill; this skill never silently updates slugs, thumbnails, content, or the repository.

## Minimum specification contract
- `purpose`, `headline`, `subtitle`, `layout`, `role` (`conceptual` or `evidence_derived`), `cards`, `takeaway`, `caption`, `alt_text`.
- Per card: `title`, `illustration` (file path), `detail_lines` (0–3 concise lines), optional `tag`/`subheading`.
- `source_notes`: where numeric facts came from; **required for evidence-derived figures**.
- No invented values, fake vendor screens, false counts, or surrogate copyrighted logos.
- If the image visibly depicts countable bottles/cases that conflict with a named exact quantity, correct or remove the implied claim.

## Layout renderer
- Requires Pillow (already used in project scripts; install dependency only if absent). Does not bundle or redistribute fonts.
- Supports 1–5 cards in rows; nonsequential layouts omit arrows. A fifth card wraps rather than forcing tiny five-column cards.
- Test a bundled example: `python .agents/skills/kollilabs-editorial-figures/scripts/render_figure.py --spec .agents/skills/kollilabs-editorial-figures/examples/01_case_setup.json --out /tmp/kollilabs-case-setup.webp --preview /tmp/kollilabs-case-setup-preview.webp --report /tmp/kollilabs-case-setup-qa.json`
- Runtime validation is **structural**, not proof of physical accuracy or visual approval.

## Integration with existing blog guidance
- `../blog-article/references/packaging-scenario-setup.md` defines **which physical stages or engineering decision steps** to include.
- `../blog-article/references/comparative-figure-workflow.md` defines how to compose **real screenshots and actual results**.
- `../blog-article/references/image-style-guide.md` and `../blog-article/references/visual-editorial-critic.md` remain authoritative for blog-wide branding/evidence/quality gates.
- This skill adds a **reproducible visual system**, not a replacement for those editorial/evidence policies.

## Generalization principle
**Generalization does not mean adding complexity for hypothetical future requirements.** Standardize reusable design and clear boundaries; adapt stage count, card content and illustrations to the real case. Do not build new software frameworks or universal 3D engines to make a blog figure.

## Output and handoff
Provide (1) complete edited figure, (2) reflowed 720px retina mobile artwork for a 360px CSS-wide display, (3) source JSON spec and artwork/provenance, (4) concise visual/evidence QA report with PASS/REVISE/FAIL/NOT REVIEWED, (5) intended caption and alt text. Artwork and final figure remain drafts until approved.
