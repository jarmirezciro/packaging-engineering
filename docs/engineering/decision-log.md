# Durable decision log

This is a compact log of decisions that repeatedly affect implementation.

## Product and site

- KolliLabs is the company; KolliPack is the application.
- The project is independent/commercial, not a previous employer’s internal tool.
- Public root is for KolliLabs; KolliPack has its own application entry.
- Blog and public calculators support SEO, education, credibility, and conversion.

## Architecture

- Standalone tools remain independent.
- Packaging Flow chains selected outputs and is a thin orchestration adapter.
- Shared engines, services, wrappers, partials, and prefix-safe JS are the target.
- Session state must remain JSON-safe.
- A tool improvement must propagate to all consumers. Container changes include standalone, Flow, and Multi-product Container Selection. Bag changes include standalone, Flow, and Multi-product Bag Selection. Palletization also includes its SEO page.

## Frontend

- Existing Bootstrap/app theme is the source of truth.
- Container Selection is the primary reference standard.
- Include instructions, clarified units, images, clean result cards, clean visualization, and concise PDF.
- Remove redundant Select buttons where row selection exists.
- Preserve vertical page position through interactions.
- Do not redesign the stable Packaging Flow shell.

## Domain

- Bag sealing space belongs to length; width receives tolerance only.
- Container rotation restrictions apply to recursive leftovers as well as the main region.
- Pallet pattern terminology uses mosaic, P1/P2, block/filler language, column/interlock.
- Pinwheel and interlock require conservative geometric validation.
- Transport payload and tare may be optional; volumes display in m³; doors and multi-view render are part of the approved result.

## Reports and 3D

- Customer views have no matplotlib axes/mesh/debug overlays.
- Detailed results and PDFs should include a base product render with original L/W/H where relevant.
- PDF uses the selected result.
- Browser interactive 3D controls are compact and placed beside the title.

## Process and safety

- Inspect latest repository/ZIP before coding.
- Explain root cause first.
- Work in small safe but coherent batches.
- Avoid duplicate HTML/JS/business logic.
- Do not touch production/Railway without explicit request.
- Do not claim completion while another required layer remains pending.

## Transport Container mode boundaries

- Maximum Utilization has no operational accessibility frontier; sequence is processing priority only.
- Accessible Sequence Loading may use supported, door-visible transition residuals and its dedicated backward/forward compaction behavior.
- Strict Sequence Loading creates a full-width frontier after **each product row** and does not reuse side/top/deep residuals behind it, even when adjacent rows share the same numeric sequence value.
- Transport mode semantics must remain isolated; mode-specific behavior should not be smuggled through shared helpers without cross-mode regression proof.
- `Space evenly` is an independent mode. V3 selects at most one complete
  homogeneous cuboid per product sequentially, then calls the existing greedy
  helper once in a translated full-width door-side sub-container. It has no
  artificial-ceiling search or beam/global combinatorial search.
- `Maximum utilization floor first` is an isolated comparison mode. It keeps
  Maximum Utilization's physical rules and sequence ordering, then selects a
  homogeneous main block using the bounded transverse `ny × nz` candidate
  math shared with Space Evenly. It subtracts that block from real free-space
  geometry and packs its residual units adjacently in x-strip -> z-layer ->
  y-row order, including available side spaces. It does not use Space Evenly's
  orchestration or final door-side residual zone. The unchanged Maximum result
  is retained only when this candidate would lose capacity.
