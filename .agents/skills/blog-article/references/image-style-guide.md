# Image and Thumbnail Style Guide

## Brand principle

KolliLabs images should feel modern, practical, technical, and clean. Packaging objects and comparisons must remain understandable at mobile and thumbnail size.

## Evidence principle

When an article discusses a KolliPack result, use real KolliPack screenshots or renders.

Do not:

- Create fake UI screenshots.
- Change numerical values visible in screenshots.
- Invent arrangements.
- Generate a logo.
- Use decorative imagery where real evidence is required.

## Method selection

| Need | Method |
|---|---|
| Numerical chart | Matplotlib |
| Geometric comparison | Matplotlib or deterministic SVG/drawing |
| Screenshot comparison | Deterministic composition with Pillow/SVG |
| Packaging arrangement diagram | Deterministic drawing or Matplotlib |
| Conceptual editorial scene | OpenAI image generation when appropriate |
| Thumbnail from real case | Deterministic composition from KolliPack renders |
| Logo/title/brand frame | Deterministic composition script |

Honor the method requested by the author.

## Figure planning

Each figure must communicate one main idea.

Common demo figures:

- Case setup.
- Alternative comparison.
- Capacity comparison.
- Pallet consequence.
- Transport result.
- Detailed final result.
- Same capacity, different practical decisions.

A normal business article usually needs three to six figures.

Keep relevant approved images. When several screenshots communicate one comparison, combine them into one compact figure rather than displaying each as a large image.

For reusable multi-tool layouts—setup collages, render matrices, result-table matrices, and
scope-limited setup flows—follow `comparative-figure-workflow.md`. The layout should follow the
approved editorial question, not the order in which screenshots happen to appear in a folder.

## Screenshot treatment

- Preserve raw screenshots as evidence.
- Crop irrelevant browser or interface clutter.
- Keep key metrics readable.
- Use consistent margins and labels.
- Do not cover or rewrite original result values.
- Use clear figure labels when comparing alternatives.
- Optimize final figures to WebP.
- Retain source images when useful.

Treat raw screenshots as evidence sources. Treat the integrated figure as an editorial explanation:
crop, align, label, and caption it without changing the underlying result.

## Thumbnail workflow

1. Identify the single most important visual tension.
2. Select one or two real KolliPack renders or comparison objects.
3. Use one short headline.
4. Use one important number or contrast when useful.
5. Use the canonical official logo.
6. Use the actual project brand colors.
7. Compose deterministically using the existing script or equivalent project method.
8. Export at the approved social-preview size.
9. Check readability at small size.
10. Optimize to WebP.

The thumbnail should not be a miniature screenshot collage.

Examples:

```text
15 → 18
SAME BOX
20% MORE PRODUCTS
```

```text
9,600 → 14,400
THINK BEYOND THE BOX
```

## Generated imagery

When a conceptual image is genuinely useful:

- Use one clear packaging concept.
- Keep object count limited.
- Leave space for deterministic title and logo.
- Do not generate fake technical text.
- Do not generate fake KolliPack interfaces.
- Do not generate the brand logo.

## Accessibility

Alt text explains the information contributed by the image.

Captions explain the interpretation.

Do not duplicate the full caption in the alt text.
