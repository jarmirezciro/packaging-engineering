# KolliPack product vision and scope

## Product vision

KolliPack is a packaging-engineering platform that connects decisions that are often handled in separate tools:

```text
Product
  → primary/secondary packaging selection
  → carton or container packing
  → palletization
  → transport loading
  → material/logistics/sustainability analysis
```

The core differentiation is not only a single algorithm. It is the combination of deterministic engineering tools, shared catalogues, visual explanation, reports, and an integrated Packaging Flow.

## Current and discussed modules

- Product Catalogue
- Packaging Catalogue
- Container Selection Tool
- Container Multi-product Selection Tool
- Bag Selection Tool
- Bag Multi-product Selection Tool
- Palletization Tool
- Transport Container Tool
- Packaging Flow / Full Packaging Mode
- Branding and packaging-related prediction tools from earlier project generations
- Public SEO calculators and technical blog

Roadmap ideas discussed include box-strength/load optimization, packaging life-cycle/CO2 comparison, artwork management, and AI-assisted explanation or rendering.

## Product principles

1. **Deterministic engineering first.** AI may explain, parse, or assist, but it must not silently replace auditable geometry and constraint engines.
2. **One result, multiple explanations.** Results should be understandable in cards, detailed analysis, visualizations, and reports.
3. **Shared catalogues reduce re-entry.** Users should be able to load products and packaging from catalogues or work manually.
4. **Standalone tools remain useful.** Packaging Flow adds chaining without making individual tools dependent on it.
5. **Improvements propagate.** Shared logic and UI contracts must prevent the Flow and SEO calculators from becoming outdated copies.
6. **Assumptions are visible.** Units, tolerances, orientation restrictions, payload, stack height, overhang, and omitted real-world constraints must be explained.

## Public-site separation

- `/` is the KolliLabs public/company entry point.
- `/kollipack/` is the KolliPack application dashboard/entry point.
- Public calculators, SEO pages, and blog content should lead users toward KolliPack while preserving the application’s existing authenticated/product experience.
