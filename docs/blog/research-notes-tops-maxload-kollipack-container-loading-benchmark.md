# Research Notes — From 1,285 to 1,319: Testing a TOPS MaxLoad Case in KolliPack

## Brief

- Mode: research / new article creation from supplied evidence
- Article profile: demo_case_study
- Editorial treatment: comparative engineering benchmark
- Intended reader: packaging engineers, logistics engineers, transport planners, and operations managers
- Primary question: When the optimized 1,285-unit TOPS MaxLoad manifest is reconstructed in KolliPack, can the remaining geometry accept additional cargo?
- Search intent: informational / comparative; understand one high-cube loading benchmark and why tested residual capacity is stronger evidence than visible empty space
- Primary keyword: TOPS MaxLoad container loading benchmark
- Article promise: reproduce the published reference manifest exactly, then test the apparent residual geometry with two separate additional-cargo probes
- Proposed CTA: Try the same high-cube benchmark in KolliPack → /free-container-loading-calculator/?case=tops-max-load-high-cube-benchmark
- Research date: 2026-10-20
- Repository snapshot: production at 92d0f80b22a4c32a0693866196245ad92a2e531c

## Editorial contract

- Primary audience: logistics / operations managers and technical packaging readers evaluating container-loading approaches.
- Business decision: determine whether a calculated high-cube arrangement leaves geometrically usable capacity for more load units.
- Business consequence in the opening: 34 additional SKU302473 load units fit in the same dimensional fixture, increasing the tested total from 1,285 to 1,319.
- Approved workflow scope: rectangular load units → 40-ft high-cube container geometry → calculated placement and loaded quantity.
- Excluded scope: product review, price, usability, speed, feature parity, payload comparison, physical safety, stability, restraint, compliance, global optimality, and downstream packaging stages.
- First-block result: exact 1,285-unit manifest reproduced; separate Progressive Fill probe A loads 1,319.
- Comparison claim: in this specific fixture, the tested KolliPack Progressive Fill solution accommodated more cargo than the TOPS result shown in the supplied public-source screenshots.
- Figure plan: five deterministic editorial composites plus one thumbnail; TOPS source output and KolliPack reproduction visibly distinguished.
- CTA action: open the original 1,228-unit preset, change quantities or mode, and add the Case 1 row to reproduce the later tests.

## Story angle

- Reader problem: cube utilization alone does not show whether the remaining volume is shaped usefully.
- Apparent answer: the 1,285-unit KolliPack arrangement appears to leave space.
- Surprising result: the apparent space accepts 34 more SKU302473 units in one probe and eight more Case 1 units in another separate probe.
- Business consequence: more load units fit in the same container geometry under this fixture.
- Remaining decision: physical stability, restraint, handling, compliance, and actual operating approval remain outside the geometric calculation.
- Article promise: move from visual impression to a quantity-tested, case-scoped conclusion.

## Title laboratory

Scores are on a 1–5 scale for clarity, specificity, curiosity, business relevance, SEO naturalness, and credibility.

| Angle | Candidate | Score | Decision |
|---|---|---:|---|
| Result-led | From 1,285 to 1,319: Testing a TOPS MaxLoad Case in KolliPack | 29/30 | Selected visible title |
| Engineering-led | Same Container, Same Manifest: Testing Usable Space Beyond 1,285 Units | 27/30 | Strong, but comparator less visible |
| Curiosity-led | The Empty Space That Accepted 34 More Load Units | 25/30 | Memorable, but less precise |
| Benchmark-led | Reproducing a TOPS MaxLoad High-Cube Case in KolliPack | 27/30 | Accurate, but hides the result |
| SEO-led | TOPS MaxLoad vs KolliPack: 40-ft High-Cube Container Loading Benchmark | 28/30 | Selected SEO direction |
| Business-led | How Much More Cargo Can the Same High-Cube Geometry Accept? | 24/30 | Useful question, but too generic |
| Restraint-led | One Published Load, Two Additional-Cargo Tests | 24/30 | Credible, but weak search signal |

- Final visible title: From 1,285 to 1,319: Testing a TOPS MaxLoad Case in KolliPack
- SEO title: TOPS MaxLoad vs KolliPack: High-Cube Loading Benchmark
- Thumbnail headline: 1,285 UNITS / ROOM STILL LEFT / +34 MORE / IN THIS SPECIFIC CASE
- Slug: tops-maxload-kollipack-container-loading-benchmark

## Source ledger

| Source | Claim supported | Source type | Accessed | Article use |
|---|---|---|---|---|
| Supplied TOPS screenshots in C:/Users/jaram/Desktop/transport_container_tool | Original and optimized manifests, vehicle, algorithms, visible arrangements, 1,228 and 1,285 totals | Supplied public-source evidence | 2026-10-20 | Figures 1–4 and fixture values |
| Supplied KolliPack screenshots in C:/Users/jaram/Desktop/transport_container_tool | Original reproduction, exact 1,285 reproduction, probes A and B | Supplied application evidence | 2026-10-20 | Figures 2, 4, and 5 |
| https://topseng.com/maxload-smart-loading-algorithms/ | Official vendor description of MaxLoad loading-algorithm context | Vendor website | 2026-10-20 | Comparator context only; not treated as the fixture source |
| https://topseng.com/download-center/ | Current vendor download center and current-production MaxLoad Pro release listing | Vendor website | 2026-10-20 | Version caution only; does not identify the video version |
| packagingapp/tools/transport/case_presets.py | Exact public preset dimensions, rows, quantities, and route slug | Current repository | 2026-10-20 | CTA verification |
| packagingapp/tools/transport/modes.py | Current public labels: Progressive Fill and Balanced Spread | Current repository | 2026-10-20 | Visible terminology |
| packagingapp/tools/transport/service.py:analyze_transport_capacity | Shared no-render transport backend entry point | Current repository | 2026-10-20 | Focused reproduction |
| packagingapp/utils/container_tool/engine.py | Current packing engine and existing physical geometry validator | Current repository | 2026-10-20 | Counts, volumes, utilization, geometry validation |

## Comparator record

- Comparator: MaxLoad / TOPS Software Corporation.
- Evidence: supplied screenshots said to originate from a public YouTube example.
- Exact YouTube URL: TODO — not present in the supplied files or repository and not found in a bounded web search.
- Video title/tutorial date: TODO.
- Source software version/edition: unknown; do not infer from the current TOPS download page.
- Capture date: unknown for the original source screenshots; supplied for this article on 2026-10-20.
- Region: not applicable to the dimensional fixture; source UI uses inches and pounds.
- Unit conversion: 474 × 93 × 106 in corresponds to approximately 12039.6 × 2362.2 × 2692.4 mm; KolliPack uses 12039 × 2362 × 2692 mm.
- Comparison scope: load-unit dimensions, requested/loaded quantities, product-envelope volume, calculated arrangement, and tested additional capacity.
- Omitted scope: weight comparison, payload, product features, price, speed, usability, safety, and commercial value.
- Rights status: supplied screenshots require provenance and reuse-rights confirmation before public release.
- Affiliation disclosure: KolliLabs/KolliPack is independent of and not affiliated with TOPS Software Corporation.
- Review status: human/legal review required before publication because a named commercial comparator and its screenshots are used.

## Backend reproduction

Entry point: packagingapp.tools.transport.service.analyze_transport_capacity

Current public name: Progressive Fill.

Canonical backend mode: front_to_back.

Container: 12039 × 2362 × 2692 mm.

All rows are stackable, R1 only, one effective sequence group, and have no positive payload limit.

| Fixture | Requested | Loaded | Total | Cargo cube | Volume utilization | Geometry |
|---|---|---|---:|---:|---:|---|
| Original Progressive Fill | 375 / 405 / 288 / 160 | 375 / 405 / 288 / 160 | 1,228 | 2,271.0 ft³ | 84.008% | Valid |
| Exact optimized Progressive Fill | 400 / 405 / 288 / 160 / 32 | 400 / 405 / 288 / 160 / 32 | 1,285 | 2,388.3 ft³ | 88.347% | Valid |
| Progressive Fill probe A | 434 / 405 / 288 / 160 / 32 | 434 / 405 / 288 / 160 / 32 | 1,319 | 2,437.0 ft³ | 90.148% | Valid |
| Progressive Fill probe B | 400 / 405 / 288 / 160 / 40 | 400 / 405 / 288 / 160 / 40 | 1,293 | 2,408.7 ft³ | 89.100% | Valid |
| Exact optimized Balanced Spread | 400 / 405 / 288 / 160 / 32 | 400 / 405 / 288 / 160 / 32 | 1,285 | 2,388.3 ft³ | 88.347% | Valid |

Geometry validation used the current engine's existing final-placement validator for bounds, positive-volume overlap, and full-base union support. Every central fixture passed.

Derived checked values:

- Probe A additional cargo cube: approximately 48.7 ft³.
- Probe B additional cargo cube: approximately 20.4 ft³.
- Probe A unit-count change: 34 / 1,285 = approximately 2.65%; article rounds to about 2.6% more load units in this test.

## Evidence discrepancies and treatment

### Current mode name

The supplied brief and historical screenshot filenames say Progressive Spread. The checked-out mode registry, public template tests, engine documentation, and UI use Progressive Fill.

Treatment: visible article text, metadata, captions, and editorial labels use Progressive Fill. No application wording was changed.

### Optional Balanced Spread screenshot

The supplied optional screenshot shows 375 / 405 / 288 / 160 / 48 loaded for 1,276 total. The current Balanced Spread backend loads 370 / 405 / 288 / 160 / 48 for 1,271 total, leaving five SKU302473 units unplaced.

Treatment: omit this optional result and screenshot. Do not use it in the benchmark table or public claim. The discrepancy does not affect the exact 1,285 reproduction or either Progressive Fill probe.

### Exact public video source

The exact YouTube URL, video title, tutorial date, and video software version were not present in the repository or supplied evidence and were not identified in a bounded search.

Treatment: keep the article in draft, state the source-metadata gap in the draft, and block publication until the URL and reuse rights are confirmed.

### Preset scope

The named public preset opens the original four-row 1,228-unit fixture, not the later five-row 1,285-unit manifest.

Treatment: CTA wording says “same high-cube benchmark,” and the article explains that readers can change quantities and add Case 1. Do not label the CTA as a preloaded 1,285-unit case.

### Brand asset

No standalone official logo image exists in the checked-out repository. The canonical public/app brand uses text plus Bootstrap icons in templates.

Treatment: the thumbnail uses the canonical KolliLabs / KolliPack wording and theme colors without drawing or generating a logo.

## Figure plan and source map

| Figure | Message | Source screenshots | Output |
|---|---|---|---|
| Figure 1 | Establish the initial reference case | top_original_loading_list (1).png; tops_container_selection.png; tops_algorithms.png | static/img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-kollipack-benchmark-setup.webp |
| Figure 2 | The same 1,228-unit cargo can be organized differently | tops_original_loading_list_front_to_back.png; tops_space_evenly.png; kollipack_progressive_spread.png | static/img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-kollipack-original-1228-comparison.webp |
| Figure 3 | TOPS extends the case to 1,285 | tops_optimizaed_load_list.png; tops_load_optimized_front_to_back.png | static/img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-maxload-optimized-1285.webp |
| Figure 4 | Same optimized manifest in both systems | tops_load_optimized_front_to_back.png; kollipack_front_to_back_optimized_same_tops.png | static/img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-kollipack-same-1285-manifest.webp |
| Figure 5 | Two separate probes prove the residual geometry is usable | kollipack_progressive_spread_optimized_v1.png; kollipack_progressive_spread_optimized_v2.png | static/img/blog/tops-maxload-kollipack-container-loading-benchmark/kollipack-residual-capacity-test.webp |
| Thumbnail | One visual tension: 1,285 units, room still left, +34 more | kollipack_progressive_spread_optimized_v1.png | static/img/blog/tops-maxload-kollipack-container-loading-benchmark/thumbnail.webp |

Composition script: .agents/skills/blog-article/scripts/generate_tops_maxload_benchmark_assets.py

All source screenshots remain visually faithful. Labels and result cards sit outside the screenshot panels.

## Fresh-Eyes review

Persona: logistics / operations manager who understands container utilization but not packing-engine internals.

Required comprehension:

1. Original TOPS case: four rows and 1,228 load units.
2. TOPS optimization: P1 rises to 400 and P5 Case 1 adds 32, totaling 1,285.
3. Exact KolliPack reproduction: 400 / 405 / 288 / 160 / 32, all loaded.
4. Main result: separate probe A reaches 1,319 by adding 34 SKU302473 units.
5. Stronger-than-visual evidence: additional real load units were placed; empty-looking space was not treated as proof.
6. Scope: one fixture, no universal superiority or physical certification.
7. Reader action: open the exact preset route, change quantities or mode, and add Case 1.

Planned/reviewed revisions:

- Lead with 1,285 → 1,319 within the first 100 words.
- Explain “load unit” and product-envelope volume once.
- State explicitly that probes A and B are separate.
- Keep implementation terms and private engine architecture out of the article.
- Align CTA language with the original 1,228-unit preset rather than implying that 1,285 is preloaded.
- Consolidate comparison and engineering limitations into one late section.

Outcome: passes the seven comprehension questions after revision.

## SEO review

- The existing broad primary keyword “container loading benchmark” belongs to the published BR1–BR7 article.
- The public tool page owns the transactional term “container loading calculator.”
- This article uses the narrower “TOPS MaxLoad container loading benchmark” to avoid material keyword cannibalization.
- Visible title is result-led; SEO title is comparator and fixture led; thumbnail is short and numerical.
- Exact prepopulated-case route is present in front matter, body context, and article-specific footer CTA.
- One directly relevant internal article link is used; unrelated packaging tools are omitted.

## Publication gates

- Keep status = draft.
- Confirm the exact public YouTube URL, title, tutorial date, and source version when available.
- Confirm permission/rights basis for the TOPS screenshots.
- Complete human/legal review of comparator naming, screenshot use, and bounded claims.
- Recheck the public preset and current backend immediately before publication if the engine changes.
