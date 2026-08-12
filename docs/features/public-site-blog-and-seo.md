# Public site, blog, and SEO calculators

## Site roles

- `/` — KolliLabs public/company page.
- `/kollipack/` — KolliPack application entry/dashboard.
- Public pages explain the company, product value, consultancy, education, and blog.
- The application layout should not be casually redesigned when changing public routing.

Historical early routes included `/company/`, `/blog/`, and `/blog/<slug>/`; verify the current URL configuration because the later root-site architecture may supersede them.

## Company page

The public company/About page should:

- explain why KolliLabs exists;
- sell the value of packaging engineering without exaggeration;
- present software, consultancy, and education;
- include founder context and a real approved photo asset;
- use larger, premium sections/cards rather than an overly compact layout;
- link clearly to KolliPack and relevant blog/tool pages;
- preserve the established colors and theme.

## Blog purpose

The blog is a packaging-engineering knowledge base that supports:

- SEO and discoverability;
- technical credibility;
- education;
- links to relevant KolliPack tools;
- consultancy and software conversion.

Approved article types:

- `engineering_deep_dive` (“nerd” article);
- `business_case`;
- `practical_guide`;
- `kollipack_update`;
- `sustainability`.

## Blog content model

Historical implementation discussed:

- `BlogPost` with cover image, draft/published status, SEO fields;
- `BlogImage` for multiple inline diagrams/images;
- author area with Alejandro Ramírez, role, publication date, and reading time;
- insertion syntax similar to `{{ image:box-fill-rate }}`.

Verify the current model and rendering syntax.

## Visual assets

- Use repeatable SVG/PNG logo assets for “KolliPack Smart Packaging Optimization”; do not depend on an AI model regenerating the same logo.
- Store article figures with descriptive stable filenames.
- Thumbnail direction: green KolliPack theme, simple high-contrast packaging concept, readable at small size.
- Technical figures should be generated from reproducible scripts where possible.

A blog example used a 130×70×30 product in a 500×300×200 box and compared six uniform orientations with a mosaic result. Historical illustrative figures reported 84 products for the best uniform orientation and 102 for the KolliPack-style mosaic (+18 / +21.4%). Treat this as a documented article fixture, not a universal performance claim.

## SEO calculator architecture

Public calculators must not be independent copies of the engine.

For the Palletization Calculator, the agreed architecture is:

```text
shared engine/service/UI contract
  ├── standalone tool
  ├── Packaging Flow
  └── public SEO page
```

The public page may have prefilled demo values and a visible initial result. Demo defaults belong to the SEO page only.

The Bag Size Calculator follows the same contract at
`/free-bag-size-calculator/`. It consumes the shared Bag Selection page
context, form, service, engine, renderer, result partials, and PDF export.
Its public demo values are injected only by the SEO view. The engine's fixed
fit tolerance and sealing allowance are displayed as read-only assumptions;
they are not parallel SEO inputs or calculations.

The Container Loading Calculator follows the same contract at
`/free-container-loading-calculator/`. It consumes the shared Transport
Container form orchestration, service, engine, result partials, Three.js scene
and viewer, public catalogue visibility rules, and snapshot-backed PDF export.
Its demonstration transport unit and load row are injected only by the SEO
view; standalone and Packaging Flow defaults are unchanged. Named public case
links use the `?case=<slug>` query parameter. The current TOPS high-cube
benchmark is available at
`/free-container-loading-calculator/?case=tops-max-load-high-cube-benchmark`;
it loads the manual 12039 × 2362 × 2692 mm fixture, four requested load-unit
rows, and Maximum utilization floor first.

The Box Size Calculator follows the Container Selection shared contract at
`/free-box-size-calculator/`. Its public demo uses manual product and box
values, the shared R1/R2/R3 restrictions, Container engine, result metrics,
Three.js RSC viewer, public-only catalogue visibility, and snapshot-backed PDF
path. SEO defaults and marketing content do not alter standalone, Packaging
Flow, or Multi-product Container Selection state.

## SEO content rules

Each calculator page should include:

- clear H1 matching search intent;
- concise problem explanation;
- working calculator near the top;
- units and assumptions;
- example result;
- explanation of how to interpret the result;
- internal links to the relevant article and KolliPack application;
- unique title/meta description/canonical URL;
- no unsupported “best/optimal” claims.

A shared tool change must be checked on its SEO page to avoid front-end or JavaScript drift.
