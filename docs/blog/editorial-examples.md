# KolliLabs editorial examples

The source edition is production at `3d18f4a2fc80c617ecb5024996b9c7aae16059f6`. The linked Markdown files contain the published copy, captions, metadata and CTA definitions. The linked images are the production assets. Use the [regression register](editorial-regressions.md) to check future work against the examples.

| Editorial profile | What readers come to learn | Production examples |
| --- | --- | --- |
| Engineering Deep Dive | How an engineering principle works and what decision it changes | [Box Selection](#001-box-selection), [RSC Material Optimization](#004-rsc-material-optimization) |
| Comparative Benchmark | What the same or explicitly qualified fixture reveals about different methods or results | [CapePack](#002-capepack-bottle-benchmark), [TOPS MaxLoad](#003-tops-maxload-benchmark), [BR1–BR7](#005-br1br7-container-benchmark) |
| Practical Demo | How to reproduce one packaging decision and interpret its result | [Product Orientation](#006-product-orientation-demo) |

These profiles describe the editorial job. The article schema still controls metadata. **Approved** denotes either direct owner approval or an example of a treatment endorsed in production guidance. Each entry identifies the basis and limits of that judgment. **Negative** records a concrete defect or mismatch. **Improvement needed** describes a proposed change awaiting review.

## 001 Box Selection

Engineering Deep Dive · `engineering_deep_dive` · [Production article][box]

| ID | Status | Element and location | Finding and reusable lesson |
| --- | --- | --- | --- |
| BOX-01 | Approved | Narrative, “Why a simple box decision becomes an optimization problem” through “KolliPack goes beyond the obvious packing patterns” | The owner valued the sequence from a familiar fit question to rotations, leftover spaces and catalogue decisions. Introduce the practical problem before naming the optimization technique. |
| BOX-02 | Approved | Rendered components, green `blog-note` in “Why box selection matters,” pull quote in “The goal is not always to pack more products,” and front-matter `takeaways` | The owner singled out the concise insight, the question marking a change of objective, and the takeaways grounded in the text. Place callouts where a reader's decision changes. |
| BOX-03 | Approved | Results table, “Best uniform packing versus KolliPack optimization” | The approved treatment keeps the 84- and 102-product rows aligned and highlights the calculated improvement. Preserve the comparator and units when emphasizing the gain. |
| BOX-04 | Approved | Mathematical figure content, [uniform orientations][box1], [subbox family][box2], [developed mosaic][box3] and [best uniform versus mosaic][box4] | Deterministic diagrams show actual geometric alternatives. Retain the mathematical treatment, labels and counts when developing new versions. |
| BOX-05 | Improvement needed | Visual presentation of BOX-04 | The owner identified the plain chart backgrounds and color treatment as outside the light article figure family. Apply the existing visual system while preserving the distinctions among main blocks and leftover zones. |
| BOX-06 | Negative | Printed and captioned numbers on [subbox family][box2], [developed mosaic][box3] and [uniform versus mosaic][box4] | Production inspection found printed numbers 2B, 2 and 3 against captions 2, 3 and 4. Verify the visible artwork and the article's references together. |

## 002 CapePack Bottle Benchmark

Comparative Benchmark · `demo_case_study` · [Production article][cape]

| ID | Status | Element and location | Finding and reusable lesson |
| --- | --- | --- | --- |
| CAPE-01 | Approved | Concept figures [1 physical setup][cape1] and [7 allowance and overhang][cape7] | The owner approved the recognizable bottle, RSC and pallet sequence and the explanation of allowable space versus load extension. Use a physical chain and explain the mechanism before presenting exact results. Both figures are conceptual. |
| CAPE-02 | Approved | Results figures [3 24 bottles][cape3], [4 15 bottles][cape4] and [5 20 bottles][cape5] | Repeated carton and pallet panels show authentic KolliPack results and place the derived capacity in a consistent reading position. Keep geometry, layer count and units connected across variations. |
| CAPE-03 | Approved | [Figure 6 design approaches][cape6] and the progression from setup to results and discussion | Parallel branches explain the two design questions, adjustable bottle dimensions and fixed-product carton alternatives. Keep the contrast scoped to the workflows shown. |
| CAPE-04 | Negative | [Figure 2 original reference][cape2] | The owner flagged a small capture isolated within a wide white card. Use available space for readable source evidence. The surrounding article can carry context and values that would crowd the capture. |
| CAPE-05 | Improvement needed | Owner's Figure 2 mockup, `media/image5.png` in the CapePack DOCX | The four-panel proposal separates bottle, case, pallet and result data. Treat it as an external review attachment requiring future archival. No production equivalent or final approval was identified. |
| CAPE-06 | Negative | Tables under “What went into the calculations?” and “Three matching pallet quantities” | The owner capture shows the result as a table without the standard results styling. Compare the rendered treatment with BOX-03 or TOPS-02. |
| CAPE-07 | Improvement needed | [Current thumbnail][capet] versus the [canonical board](assets/kollilabs-approved-thumbnail-board-v1.png) | The owner flagged the family mismatch. The production thumbnail workflow cites this exact image for material and lighting realism. Use the board for layout and branding, including the lower-left lockup and headline treatment. |
| CAPE-08 | Negative | Figure 2 caption, source and independence note, and repeated settings caveats in the opening and conclusion | Publication instructions appear in reader-facing text, and several mismatches recur. Resolve the identity and use of the original frame in the evidence record. State material limits and independence concisely in the article. The exact source video and frame permissions are unresolved in the production record. |
| CAPE-09 | Improvement needed | Title, opening, and transition into “Different approaches to packaging optimization” | The owner prefers “bottle configurations” and a direct statement that the article reproduces a public demonstration. A short bridge can connect the results to design approach, product development and overhang. Use a callout only if it adds emphasis to a specific decision. |
| CAPE-10 | Negative | Front-matter `cta.url` | The production link is the generic `/full-packaging/` entry. The demo policy and owner review call for an article-specific preset that opens the relevant bottle-to-pallet inputs. |

![Bottle, shipping carton and pallet as a conceptual setup][cape1]

## 003 TOPS MaxLoad Benchmark

Comparative Benchmark · `demo_case_study` · [Production article][tops] · [Research notes](research-notes-tops-maxload-kollipack-container-loading-benchmark.md)

| ID | Status | Element and location | Finding and reusable lesson |
| --- | --- | --- | --- |
| TOPS-01 | Approved | [Figure 1 source fixture][tops1] and [Figure 3 optimized TOPS manifest][tops3] | The owner praised the consistent composition of genuine source crops. Keep source boundaries and labels visible. Figure 1 identifies the manifest, vehicle and modes independently of KolliPack output. The suggested green accent is a preference. |
| TOPS-02 | Approved | Tables in “Why an external reference case is useful” and “Two separate tests of the remaining geometry” | The owner praised the table style. The manifest puts dimensions and quantities next to the row ID, and the probe table gives each change its own row. |
| TOPS-03 | Negative | [Figures 2][tops2], [4][tops4] and [5][tops5] | Embedded KolliPack tables and UI margins leave the container smaller than its role warrants. Keep the container prominent when the point is the arrangement. Use an adjacent article table for detailed comparison values. |
| TOPS-04 | Negative | Opening and “Reconstructing the original 1,228-unit fixture” | A SKU appears before readers know what it represents, and the software collage does not show the physical setup. Introduce the high-cube mixed load and group manifest, dimensions and restrictions before software settings. |
| TOPS-05 | Improvement needed | “Why an external reference case is useful” and “Why two probes are more informative than one” | The owner wants the narrative to proceed from setup through tools and modes to results and engineering decisions. Describe why the probe changes matter to this load. Keep the 1,285-unit reproduction distinct from each independent quantity increase. |

The CTA and [published fixture description][tops] identify the original 1,228-unit preset. It gives readers a starting point for recreating the 1,285-unit manifest and probe runs. The [source ledger](research-notes-tops-maxload-kollipack-container-loading-benchmark.md#comparator-record) records the video, observed software evidence and reproduction boundary.

## 004 RSC Material Optimization

Engineering Deep Dive · `engineering_deep_dive` · [Production article][rsc]

| ID | Status | Element and location | Finding and reusable lesson |
| --- | --- | --- | --- |
| RSC-01 | Approved | “Deriving the FEFCO 0201 material minimum” and [Figure 3][rsc3] | The owner praised the progression from blank area and fixed volume to the 2:1:2 result. Let the diagram summarize the reasoning and keep equations selectable in the article. |
| RSC-02 | Approved | [Figure 5 equal internal dimensions][rsc5] and “From board area to material, purchasing cost and carbon impact” | The owner found the blank drawings clear. Flap shapes explain the different retained board areas. Connect the idealized result to purchasing while keeping the supplier and physical validation boundary. |
| RSC-03 | Negative | Erected cartons in [Figures 1][rsc1], [2][rsc2] and [4][rsc4] | The owner found the presentation visually consistent and the plain cuboids insufficient to communicate slotted corrugated construction. Depict the identifying seam, flap or closure when that feature matters. |
| RSC-04 | Negative | Pipe tables in “Controlled comparison: three 100-litre RSCs” and “Same internal dimensions, different construction” | The owner reports visible Markdown delimiters. Production source places the pipe tables inside wrapper divs without `markdown="1"`. Verify the rendered table rather than judging from the Markdown alone. |
| RSC-05 | Improvement needed | Heading pair “The two ways geometry changes material consumption” and “Same construction, different proportions”; “How KolliPack supports the decision” | Review the visual distinction between the heading levels. The owner also proposed an insight callout and a verified downstream case to connect the mathematics with practice. Scope those additions to the supporting evidence. |

![Diagram summarizing the FEFCO 0201 derivation][rsc3]

## 005 BR1–BR7 Container Benchmark

Comparative Benchmark · `engineering_deep_dive` · [Production article][br] · [Research notes](research-notes-container-loading-benchmark-kollipack-br1-br7.md)

The owner's editorial approval covers the visible `thumbnail-v2.webp` selected by the published article, all four technical figures and the tables. The repository's separate file-specific approval record covers the `thumbnail-v1.webp` pilot.

| ID | Status | Element and location | Finding and reusable lesson |
| --- | --- | --- | --- |
| BR-01 | Approved | Thumbnail family, [recorded v1 pilot][brv1] and its [implementation record](thumbnail-design-system-v1.md#repository-implementation-record-2026-10-20) | The recorded pilot applies the dark studio visual family to a benchmark. Refer to the approved board for current layout rules. |
| BR-02 | Approved | [Published v2 thumbnail][brv2] selected by the article front matter | The owner approved the visible “700 tests” thumbnail. Its representative container grid works as a benchmark motif. Keep 700 fixtures and 2,800 mode-specific solves distinct in the article. |
| BR-03 | Improvement needed | Opening sequence through “How KolliPack was tested” | The lead reports the frozen result directly. Two setup sections and later methodology revisit the purpose of benchmarking. A tighter passage could introduce the physical fixture and mode purposes together while retaining the approved figures and reproducibility detail. |
| BR-04 | Approved | [Figure 1 utilization][br1], [Figure 2 heterogeneity][br2], [Figure 3 commercial classes][br3], [Figure 4 engineering loop][br4] and the published tables from “What the Bischoff–Ratcliff BR1–BR7 suite is” through “Why the gap exists” | The owner approved all four figures and the tables. Keep KolliPack means, CLTRS full-support values and vendor-reported LoadingMCP classes identifiable. Preserve the technical figures and tables when tightening the narrative. |

## 006 Product Orientation Demo

Practical Demo · `demo_case_study` · [Production article][orientation] · [Production demo lessons][demo-lessons]

The owner explicitly approved Figures 2 and 3, the results table and the concise demonstration structure. The introduction, Figure 1 and sequential figure numbering remain open improvements.

| ID | Status | Element and location | Finding and reusable lesson |
| --- | --- | --- | --- |
| ORI-01 | Approved | Concise demonstration structure, [Figure 2 orientation comparison][ori2] and the results table under “Why the obvious arrangement was not the best one” | The owner approved the compact progression from the same-box 15-to-18 comparison to its operational consequence. Keep the result readable in the figure and table. The production demo lessons also endorse the exact-case link. |
| ORI-02 | Approved | [Figure 3 maximum result analysis][ori3] in “Geometry wins here, not payload” | The owner approved the figure showing why geometry limits the count before payload does. Show the controlling constraint and keep illustrative order quantities clearly labeled in the prose. |
| ORI-03 | Improvement needed | [Figure 1 case setup][ori1] in “A realistic export-box decision” | The input screenshot and cube summarize the settings. Use a recognizable product-to-shipping-box illustration to establish the physical case before software controls. Keep the verified orientation permissions. |
| ORI-04 | Negative | The three `figcaption` entries | Each caption explains its figure. Add sequential labels 1–3 and check them against article order and references. |
| ORI-05 | Improvement needed | Opening before “A realistic export-box decision” | State the objective up front: maximize carton utilization by combining permitted product orientations. Keep the same-box 15-to-18 result and the concise demonstration structure. |

## Original review locators

The article figures and all six published thumbnail files were opened from the production checkout. The 17 embedded images in the four supplied DOCX files were opened separately and compared with the production assets or article sections. This review used the production source and owner page captures for page-level findings. The Box callouts, takeaways and table and the CapePack table are rendered components with no standalone repository snapshot identified. The RSC table-rendering finding comes from the owner's prose, alongside corroborating source markup. The CapePack proposal is a review-only image. Durable archive status for these owner files is pending.

| Original DOCX filename | Useful locators |
| --- | --- |
| `box-selection-3d-bin-packing-problem.docx` | `media/image.png`, `image2.png`, `image3.png`, `image4.png` show insight, question, takeaways and table. `image5.png` shows Figure 1 in context. |
| `capepack-kollipack-bottle-case-pallet-benchmark.docx` | `media/image.png`, `image2.png` and `image3.png` show Figures 1, 3 and 6. `image4.png` shows published Figure 2 and `image5.png` its proposed arrangement. `image6.png` shows the table and `image7.png` the thumbnail. `image8.png` and `image9.png` refer back to Box Selection's components. |
| `tops-maxload-kollipack-container-loading-benchmark.docx` | `media/image.png` and `image2.png` show Figures 1 and 2. Remarks on Figures 4 and 5 appear in review prose. |
| `rsc-material-optimization.docx` | `media/image.png` reproduces the Box Selection insight pattern as a suggestion. Judgments on the five RSC figures and table display are in review prose. |

[box]: ../../packagingapp/content/blog/articles/box-selection-3d-bin-packing-problem.md
[box1]: ../../static/img/blog/box-selection-3d-bin-packing-problem/figure_1_six_uniform_base_ways.png
[box2]: ../../static/img/blog/box-selection-3d-bin-packing-problem/figure_2b_rectangular_subbox_family_all_base_mosaics.png
[box3]: ../../static/img/blog/box-selection-3d-bin-packing-problem/figure_2_developed_mosaic_layout.png
[box4]: ../../static/img/blog/box-selection-3d-bin-packing-problem/figure_3_best_uniform_vs_kollipack.png
[cape]: ../../packagingapp/content/blog/articles/capepack-kollipack-bottle-case-pallet-benchmark.md
[cape1]: ../../static/img/blog/capepack-kollipack-bottle-case-pallet-benchmark/01_packaging_scenario_setup_revised.webp
[cape2]: ../../static/img/blog/capepack-kollipack-bottle-case-pallet-benchmark/02_capepack_single_reference.webp
[cape3]: ../../static/img/blog/capepack-kollipack-bottle-case-pallet-benchmark/03_kollipack_24_bottles.webp
[cape4]: ../../static/img/blog/capepack-kollipack-bottle-case-pallet-benchmark/04_kollipack_15_bottles.webp
[cape5]: ../../static/img/blog/capepack-kollipack-bottle-case-pallet-benchmark/05_kollipack_20_bottles.webp
[cape6]: ../../static/img/blog/capepack-kollipack-bottle-case-pallet-benchmark/06_optimization_approaches.webp
[cape7]: ../../static/img/blog/capepack-kollipack-bottle-case-pallet-benchmark/08_allowance_and_pallet_overhang_explained.png
[capet]: ../../static/img/blog/capepack-kollipack-bottle-case-pallet-benchmark/thumbnail-approved.png
[tops]: ../../packagingapp/content/blog/articles/tops-maxload-kollipack-container-loading-benchmark.md
[tops1]: ../../static/img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-kollipack-benchmark-setup.webp
[tops2]: ../../static/img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-kollipack-original-1228-comparison.webp
[tops3]: ../../static/img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-maxload-optimized-1285.webp
[tops4]: ../../static/img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-kollipack-same-1285-manifest.webp
[tops5]: ../../static/img/blog/tops-maxload-kollipack-container-loading-benchmark/kollipack-residual-capacity-test.webp
[rsc]: ../../packagingapp/content/blog/articles/rsc-material-optimization.md
[rsc1]: ../../static/img/blog/rsc-material-optimization/figure-1-geometry-material-demand.webp
[rsc2]: ../../static/img/blog/rsc-material-optimization/figure-2-fefco-0201-blank-geometry.webp
[rsc3]: ../../static/img/blog/rsc-material-optimization/figure-3-mathematical-result.webp
[rsc4]: ../../static/img/blog/rsc-material-optimization/figure-4-equal-volume-comparison.webp
[rsc5]: ../../static/img/blog/rsc-material-optimization/figure-5-same-dimensions-construction.webp
[br]: ../../packagingapp/content/blog/articles/container-loading-benchmark-kollipack-br1-br7.md
[br1]: ../../static/img/blog/container-loading-benchmark-kollipack-br1-br7/figure-1-700-case-utilization.webp
[br2]: ../../static/img/blog/container-loading-benchmark-kollipack-br1-br7/figure-2-heterogeneity-curve.webp
[br3]: ../../static/img/blog/container-loading-benchmark-kollipack-br1-br7/figure-3-commercial-reference.webp
[br4]: ../../static/img/blog/container-loading-benchmark-kollipack-br1-br7/figure-4-engineering-improvement-loop.webp
[brv1]: ../../static/img/blog/container-loading-benchmark-kollipack-br1-br7/thumbnail-v1.webp
[brv2]: ../../static/img/blog/container-loading-benchmark-kollipack-br1-br7/thumbnail-v2.webp
[orientation]: ../../packagingapp/content/blog/articles/how-many-products-fit-in-a-box-orientation-case-study.md
[ori1]: ../../static/img/blog/how-many-products-fit-in-a-box-orientation-case-study/case-setup.webp
[ori2]: ../../static/img/blog/how-many-products-fit-in-a-box-orientation-case-study/orientation-capacity-comparison.webp
[ori3]: ../../static/img/blog/how-many-products-fit-in-a-box-orientation-case-study/maximum-result-analysis.webp
[demo-lessons]: ../../.agents/skills/blog-article/references/demo-case-study-lessons.md#container-selection-orientation-case
