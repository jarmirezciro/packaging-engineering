# Mixed-cargo loading draft evidence

- Profile: Engineering Deep Dive. The original research draft was refined in place using `refine_article`. The reusable review lessons were handled separately in `calibrate_from_feedback`. The owner’s six-page PDF served as the visual baseline.
- Reader: a transport planner evaluating a rear-unload, two-stop route. Products stay anonymized as A–G.
- Search intent: how delivery sequence changes mixed-cargo loading decisions. Primary keyword: “mixed-cargo loading and delivery sequence.”
- Case: `48ft-semitrailer-two-stop-mixed-cargo`, registered in the existing Transport Container preset registry. [Open the prepopulated calculator](/free-container-loading-calculator/?case=48ft-semitrailer-two-stop-mixed-cargo)

## Evidence and reproduction

The brief supplied a KolliPack input capture (attachment 2), requested and loaded counts plus a 3D loading view (attachment 3), and a result summary (attachments 1 and 5, byte-identical). Attachment 4 shows the EasyCargo reference. Capture dates and software build identifiers are unavailable. The public EasyCargo post is dated 3 February 2026 and was checked 15 November 2026. Its loading illustration inspired a separately configured KolliPack case. The draft attributes the source and uses no EasyCargo outputs as performance evidence. [EasyCargo article](https://www.easycargo3d.com/sv/blog/ssme-logistics-optimize-cargo-transport/)

The new preset uses the existing imperial 566.9 × 98.5 × 108 in trailer with blank payload and tare. The directly supplied reference illustration shows those interior dimensions. The current KolliPack result reproduces the attachment’s trailer volume and axis clearances. The seven load rows, exact displayed decimal dimensions, fixed quantities, weights, permissions and group identifiers come from attachments 2 and 3. The separate existing three-stop benchmark and all-rotations support-bed preset use different inputs.

Reproduced against checkout `3d18f4a` with the existing working tree on 15 November 2026. The entry point was `packagingapp.tools.transport.service.analyze_transport_capacity`, which validates and converts the imperial inputs before running the shared `pack_container` and `summarize` functions.

| Configuration | Placed | Unplaced | Volume utilization |
|---|---:|---:|---:|
| Progressive Fill – Mixed Cargo Infill, screenshot permissions | 133 | 0 | 85.62% |
| Progressive Fill | 67 | 66 | 52.62% |
| Balanced Spread | 55 | 78 | 50.15% |
| Balanced Spread – Mixed Cargo Infill | 133 | 0 | 85.62% |
| Progressive Fill – Mixed Cargo Infill, A upright-only (R3) | 115 | 18 D | 78.66% |
| Progressive Fill – Mixed Cargo Infill, A 15.70 × 55.10 × 63 in | 127 | 6 D | 83.19% |

Headline result also matches 84.619 m³ loaded, 98.825 m³ interior, 48,181.53 lb cargo, 559.25 × 94.50 × 102.40 in occupied and 7.65 × 4.00 × 5.60 in axis clearances. Payload utilization is unset. Placements were inspected directly. The two groups occupy adjacent sections separated at 311.15 in from the nose. A is upright in every placement and supports all 17 B units. Three D layers support all 14 E units. The 0.15 in difference between A’s deck length and the B layer shows why the exact roof arrangement is sensitive. Each sensitivity run changes one input setting as listed. It establishes a different result for this solver and case.

## Article refinement and visual review

Figure 1 explains the physical setup of seven cargo types, two stops and one rear-unloading semitrailer. Figure 2 diagrams allowable resting faces, supported versus clear tops, and the intended unload order. Both are conceptual illustrations made with the established editorial figure renderer and its approved light design tokens. Their illustrations and editable specifications are in [the figure source package](../../artifacts/mixed-cargo-loading-draft). The numbered badges identify panels within an illustration. The article captions carry the figure numbers.

Figure 3 reflows the seven original legend tiles and retains the 768 × 392 loading-view crop byte for byte. The [retained KolliPack source capture](../../artifacts/mixed-cargo-loading-draft/loading-view-source.png) is the supplied 08:35:03 recording, SHA-256 `0f2050b05af057923619baa1c9fd1a77089dc738726b80121797c89039ad122e`. Each tile retains its P number, product letter, dimensions in inches, and loaded/planned counts. The summary line `133 of 133 units loaded` comes from the verified calculation.

| Asset | Inspected | Self-review |
|---|---|---|
| Figure 1, physical setup | 1,680 px source, 901 px desktop and 279 px reflowed mobile display | Pass after restoring roof clearance in the source drawing. The three in-scope elements and complete trailer are visible. |
| Figure 2, engineering constraints | 1,680 px source, 901 px desktop and 279 px reflowed mobile display | Pass. Orientation, support and door-side order read independently. The trailer diagram shows group position schematically. |
| Figure 3, authentic result | Original source capture and result, 901 px desktop and 279 px mobile display | Pass. P1–P7, dimensions and requested/loaded pairs are visible above the complete original geometry. |
| Article in the private Django preview template | 1,440 px desktop and 390 px mobile | Pass. Captions run 1–3, the manifest scrolls within its container and the strategy table fits the content column. |
| Existing thumbnail candidate | 1,280 × 720 and 360 × 203 as previously reviewed | The owner approved the review package on 15 November 2026. The reviewed thumbnail was copied byte for byte to its static path. |

Fresh-Eyes self-review used logistics and purchasing perspectives. The route explains what comes out first, the calculations demonstrate input sensitivity, and the software section names what to measure against implementation costs. The conclusion reports 133 units and connects the choice of strategy to the stop order. All four strategy outputs and both sensitivity results were rerun and matched.

## EDR-08 and validation handoff

The baseline used `<figure class="blog-figure">` and an unnumbered `<figcaption>`. The original handoff ran the schema validator, which checks required metadata and assets. Its production checkout was behind the upstream revision containing the existing editorial audit and did not have `audit_editorial.py`. Running the upstream auditor against the original Markdown detected the figure and returned EDR-08 FAIL. The finding was applicable and there was no prior audit disposition to override. The unchanged auditor reports EDR-08 PASS on the refined Markdown, and visual review confirmed the caption order and the Figure 2 prose reference. The skill now executes that audit alongside schema validation and records each outcome during draft handoff.

Schema validation passed. The initial audit confirmed the named case and surfaced missing thumbnail and Open Graph paths. Both now resolve to the approved thumbnail. It also records an external source archival warning. The source illustration was checked for the visible grouping only. The private preview and calculator CTA returned 200 with the intended draft and case, respectively. Anonymous requests to the private preview and unpublished public article returned 404. The approved package is integrated as a draft.

## Calibration checks on existing articles

| Situation | Reference checked | Guidance outcome |
|---|---|---|
| Practical Engineering Deep Dive | [RSC material optimization](../../packagingapp/content/blog/articles/rsc-material-optimization.md) | Its derivation supports the material decision. Keep useful mathematics and connect the result to board area and purchasing. |
| Independent case inspired by an external example | [Mixed-cargo loading](../../packagingapp/content/blog/articles/mixed-cargo-loading-delivery-sequence.md) | Attribute the illustration, teach the constraints and compare the four supported local methods. |
| Competitive benchmark | [CapePack bottle benchmark](../../packagingapp/content/blog/articles/capepack-kollipack-bottle-case-pallet-benchmark.md) | Preserve matching conditions, genuine outputs and bounded conclusions where the actual question concerns both tools. |
| Business-oriented packaging decision | [Think Beyond the Box](../../packagingapp/content/blog/articles/think-beyond-the-box-packaging-flow-case-study.md) | Use case, pallet and transport results to identify a practical shortlist. A software purchasing section adds no decision value here. |

## Refined files

- Draft and evidence: `packagingapp/content/blog/articles/mixed-cargo-loading-delivery-sequence.md`, these notes, six new WebP compositions in `static/img/blog/mixed-cargo-loading-delivery-sequence/`, and the corresponding source capture, drawing script, subject art, specifications and render reports in `artifacts/mixed-cargo-loading-draft/`.
- Calibration: `.agents/skills/blog-article/SKILL.md` and its `editorial-style.md`, `business-context-and-product-selection.md`, `fresh-eyes-business-reader.md`, `visual-editorial-critic.md` and `quality-checklist.md` references. The existing `docs/blog/editorial-regressions.md` and `docs/blog/editorial-examples.md` were brought into this checkout from `origin/production` and updated for the observed findings. The canonical `.agents/skills/blog-article/scripts/audit_editorial.py` was brought over byte for byte.
- Local review: refreshed the existing authenticated preview copy at `/blog/preview/mixed-cargo-loading-delivery-sequence/` on port 8001. Its two CTA links point to the existing local calculator case on port 8000.

## Missing screenshots and technical information

- A KolliPack trailer-input screenshot or the original POST/export would independently confirm the exact interior setup and the source build. The rounded result agrees with the reconstructed inputs.
- The supplied 3D capture includes the loading view only. A top view and opposite-side view would document the group boundary and obscured placements visually. The current backend coordinates support the claims in the draft.
- Screenshots are unavailable for the baseline strategies, alternative infill mode and sensitivity runs. Their figures come from the current backend.
- The EasyCargo example’s exact rotation settings and software build are unconfirmed. The source’s group arrangement is separate from the two-stop adaptation.
- No trailer tare, payload rating, axle-load data, package compression limits, securing plan, or physical unloading trial was supplied. Payload, strength and handling certification remain outside the case.

## Title review

Scores run from 1 to 5 for clarity, specificity, reader relevance, and evidence fidelity, in that order.

| Approach | Candidate | Scores |
|---|---|---|
| Result | 133 Units in One Trailer, Ready for Two Stops | 5/5/4/3 |
| Problem | How Orientation, Stacking and Stop Order Shape a Mixed-Cargo Load | 5/5/5/5 |
| Business | Plan the Trailer Around the First Unload | 5/4/5/5 |
| Curiosity | When Two Loading Plans Use the Same Space | 4/4/5/4 |
| Search | Mixed-Cargo Loading and Delivery Sequence | 5/4/5/5 |
| Geometry | How a Fraction of an Inch Changed a Trailer Load | 5/5/4/5 |

The problem-led title carries the requested engineering scope. The search-led wording supplies the SEO title.

## Publication approval

The owner authorized publication on 15 November 2026. The approved article changes only its publication status. The eight approved asset hashes match the retained checksum manifest. The external-link archival warning is recorded for the attributed EasyCargo illustration, which is cited as inspiration. The published article uses the independently reproduced KolliPack results and original KolliPack visuals.
