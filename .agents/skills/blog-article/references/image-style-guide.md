# Image and Thumbnail Style Guide

## Brand principle

KolliLabs images should feel modern, practical, technical, and clean. Packaging objects should be easy to understand at thumbnail size.

## Method selection

| Need | Method |
|---|---|
| Numerical chart | Matplotlib |
| Geometric comparison | Matplotlib or deterministic SVG/drawing |
| Packaging arrangement diagram | Deterministic drawing or Matplotlib |
| Conceptual editorial scene | OpenAI image generation |
| Thumbnail background | OpenAI image generation |
| Logo/title/brand frame | Deterministic composition script |

Honor the method requested by the article author.

## Generated thumbnail workflow

1. Read the article and identify one visual idea.
2. Generate a clean background without logos, wordmarks, or long text.
3. Use the canonical official logo from the repository.
4. Use `compose_thumbnail.py` to add the logo and title consistently.
5. Use the real project brand green, sourced from CSS/configuration.
6. Export at the project's approved social-preview size; use 1200×630 only when that matches the approved implementation.
7. Optimize to WebP while retaining a source image when useful.

## Image-generation prompt principles

- One clear packaging concept.
- Limited object count.
- Strong silhouette and composition.
- Space reserved for deterministic title/logo overlay.
- Clean green-accented KolliLabs visual language.
- No generated brand logo.
- No generated small technical text.
- No fake UI screenshots.

## Matplotlib rules

- Label axes and units.
- Use engineering-meaningful scales.
- Avoid decorative 3D charts unless geometry itself is being explained.
- Export at sufficient resolution.
- Keep labels readable on mobile.
- Match the repository's approved brand colors only after reading the actual CSS values.

## Accessibility

Alt text explains what the image contributes. Captions explain interpretation when needed. Do not duplicate the full caption in alt text.
