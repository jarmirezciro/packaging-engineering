# Graphic Contract — Consistent identity, flexible figures

The two full-resolution, owner-approved source figures under `assets/` are the canonical editorial style reference. Compare *actual generated images* against them; a written prompt is not a substitute.

## Fixed identity
- Soft near-white / very light cool-grey canvas, no decorative gradients or dark dashboard surfaces.
- Top-left short green accent rule; large navy bold headline; grey one-line subtitle.
- White large cards with very light blue-grey stroke, generous whitespace and moderately rounded corners.
- Pale mint rounded step-number badge and dark navy card title.
- Clear large subject art in center: realistic-but-editorial packaging objects, soft isometric/three-quarter perspective, neutral studio light, subtle ground contact shadow, tan cardboard/wood and recognizable products.
- Green arrows only when an actual directional/causal chain exists.
- Light gray concise parameter strips at bottom of cards, center aligned when useful.
- Optional full-width pale mint takeaway with dark navy sentence and restrained green emphasis. No oversized decorative icons.
- Never use competitor logos, manufactured UI, fake labels or unverified exact packing geometry in concept art.

## Adjustable elements
- Number of cards 1–5; orientation and order; presence of connectors and takeaway; exact physical subjects; compact strips with confirmed units; concept vs. trade-off vs. summary.
- A 2-column design is usually preferable for longer explanations; four and five items wrap into multiple rows instead of shrinking to illegible cards.
- For non-packaging concepts, illustrations may be machinery, a process, a data-flow object, or an engineering schematic, but the same clean studio treatment and card system remain.

## Non-negotiable evidence boundary
- Editorial figure: conceptual, illustrative, clearly captioned. Do not assert exact 3D coordinates or counts from it.
- Evidence comparison: authentic screenshots/verified engine exports, with truthful source labels and no rebuilt vendor UI. Follow the comparative skill.
- If source is not trustworthy, do not hide the conflict with a concept figure.

## Typography and sizes
The composer reads actual values from `assets/design-tokens.json`; this document is qualitative. The shipped renderer never bundles fonts. Prefer installed Inter when available and a system sans-serif fallback.

## Reproducibility statement
The **layout, text, proportions, colors and badges** can be reproduced deterministically from a frozen input JSON, assets and tokens. **AI-generated object illustrations may vary between runs**; ship source artwork and a provenance record to reproduce an *approved complete figure* precisely. Do not claim pixel-level reproducibility when artwork is regenerated.
