+++
schema_version = 1
status = "published"
display_order = 2
title = "Eight or Sixteen? The Case-Pack Decision Behind One Pallet Benchmark"
slug = "tops-pro-case-size-optimization-kollipack-comparison"
subtitle = "A focused TOPS Pro and KolliPack comparison of 8- and 16-product cartons on one 48 × 40 pallet."
excerpt = "In one supplied tutorial case, the 16-pack raises calculated pallet yield from 1,152 to 1,232 units. The harder question is whether 80 more units justify changing the case pack."
summary = "A bounded case-size optimization benchmark comparing the source-reported TOPS Pro result with a current KolliPack reproduction using rounded metric inputs."
description = "A practical TOPS Pro case-size optimization comparison showing how an 8-pack versus 16-pack changes pallet yield, carton geometry, and the business decision around packaging master data."
seo_title = "TOPS Pro Case Size Optimization: 8-Pack vs 16-Pack Benchmark"
meta_description = "Compare an 8-pack and 16-pack in one TOPS Pro case-size optimization benchmark, then inspect the matched KolliPack pallet results and trade-offs."
article_type = "demo_case_study"
author = "Alejandro Ramírez"
category = "Palletization"
read_time = "8 min read"
published_at = 2026-08-08
updated_at = 2026-08-08
hero_icon = "bi-box-seam"
featured_image = "img/blog/tops-pro-case-size-optimization-kollipack-comparison/thumbnail.webp"
thumbnail = "img/blog/tops-pro-case-size-optimization-kollipack-comparison/thumbnail.webp"
thumbnail_alt = "TOPS Pro and KolliPack pallet results framing an 8-pack versus 16-pack case-size decision"
primary_keyword = "TOPS Pro case size optimization"
tags = ["TOPS Pro case size optimization", "case pack optimization comparison", "8-pack versus 16-pack pallet optimization", "packaging optimization software benchmark"]
related_articles = ["kollipack-vs-tops-pro-palletization-benchmark", "think-beyond-the-box-packaging-flow-case-study"]
related_tools = ["packaging-flow", "container-selection", "palletization"]
canonical_path = "/blog/tops-pro-case-size-optimization-kollipack-comparison/"
og_image = "img/blog/tops-pro-case-size-optimization-kollipack-comparison/thumbnail.webp"
takeaways = ["The supplied TOPS Pro tutorial reports 1,152 units per pallet for the 8-pack and 1,232 for the 16-pack.", "The current KolliPack backend reproduces those two unit counts with the stated rounded metric inputs.", "The 80-unit increase is a packaging change, not just a pallet result: master data, barcodes, documentation, handling, and qualification may all need review.", "The benchmark supports a focused comparison, not a complete evaluation of either product."]

[cta]
label = "Open the 8-pack benchmark in KolliPack"
url = "/full-packaging/case/tops-product-pallet-optimization/?reset=1"
new_tab = true
+++

<section class="blog-content-section" markdown="1">

The supplied TOPS Pro tutorial reports a move from **1,152 units per pallet with an 8-product carton** to **1,232 units with a 16-product carton**. That is **80 more units per pallet**, or approximately **6.9%**, in this one case.

The calculation is straightforward. The decision is not. Moving from 8 to 16 products per carton changes the case itself, the way people handle it, the records that describe it, and the work required to qualify the new packaging. This article uses the case to compare a source-reported TOPS Pro result with a current KolliPack reproduction, then asks what the extra pallet capacity does—and does not—tell a packaging team.

> **Benchmark scope.** TOPS Pro results come from the supplied public tutorial and source material. KolliLabs/KolliPack is independent of and not affiliated with TOPS Software Corporation. This is one focused benchmark case, not a complete product evaluation. Results depend on inputs, conversions, assumptions, versions, and settings. Calculated geometry is not physical stability, compression validation, transport approval, compliance, or customer approval. Supplier specifications, physical testing, and operational approval remain separate decisions.

<figure class="blog-figure">
  <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/case-summary.webp" alt="Benchmark summary showing the shared product and pallet inputs, five tested case quantities, and matching 8-pack and 16-pack pallet capacities" loading="lazy">
  <figcaption>The comparison is bounded to one product, one pallet, five candidate quantities, and the stated carton assumptions.</figcaption>
</figure>

</section>

<section class="blog-content-section" markdown="1">

## The case: one product, five carton quantities

In packaging, a **case-pack quantity** is the number of retail or base products placed in one shipping carton. It is the “8” or “16” in an 8-pack or 16-pack. Changing it changes the carton geometry, not merely the number printed in a planning spreadsheet.

The supplied TOPS screenshots test five quantities: **8, 10, 16, 18, and 24 products per carton**. The tutorial presents the 16-pack as its preferred result. The source package identifies the following fixture:

<div class="blog-table-wrap">
<table class="table blog-result-table">
  <thead><tr><th>Input</th><th>Benchmark value</th><th>Evidence note</th></tr></thead>
  <tbody>
    <tr><td>Product</td><td>153 × 70 × 89 mm</td><td>Rounded metric counterpart of the supplied TOPS inputs</td></tr>
    <tr><td>Allowed orientations</td><td>R1 and R3</td><td>Shown in the KolliPack restrictions screenshot</td></tr>
    <tr><td>Pallet</td><td>1,219 × 1,016 × 127 mm</td><td>48 × 40 × 5 in in the TOPS source; 127 mm used in the updated KolliPack case</td></tr>
    <tr><td>Maximum total height</td><td>1,346 mm</td><td>53 in in TOPS, rounded to metric</td></tr>
    <tr><td>Overhang</td><td>0 × 0 mm</td><td>Zero overhang in both benchmark inputs</td></tr>
    <tr><td>Carton caliper</td><td>4 mm</td><td>KolliPack assumption; the supplied TOPS 0.018 in value is intentionally not used as a like-for-like caliper</td></tr>
  </tbody>
</table>
</div>

The metric product and pallet values are rounded or converted values, not evidence that the two applications used identical internal representations. That distinction matters when comparing the last millimetre of a carton or the last layer on a pallet.

<figure class="blog-figure">
  <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/packaging-flow-summary-8.webp" alt="KolliPack Packaging Flow summary showing eight base products per box, 144 boxes per pallet, and 1,152 base products per pallet" loading="lazy">
  <figcaption>The prepopulated KolliPack case starts from the 8-pack baseline: 144 cartons times 8 products equals 1,152 base products per pallet.</figcaption>
</figure>

</section>

<section class="blog-content-section" markdown="1">

## What the two result sets show

The most useful comparison is not whether the interfaces look alike. It is whether the same case-pack decisions lead to comparable calculated pallet capacities under the stated assumptions.

<div class="blog-table-wrap">
<table class="table blog-result-table">
  <thead><tr><th>Case pack</th><th>TOPS Pro source result</th><th>KolliPack backend reproduction</th><th>Difference from 8-pack</th></tr></thead>
  <tbody>
    <tr><td>8 products/carton</td><td>1,152 units; 144 cases</td><td>1,152 units; 144 cartons; 6 layers of 24</td><td>Baseline</td></tr>
    <tr><td>16 products/carton</td><td>1,232 units; 77 cases</td><td>1,232 units; 77 cartons; 7 layers of 11</td><td>+80 units; approximately +6.9%</td></tr>
  </tbody>
</table>
</div>

The current shared KolliPack backend was run with the matched carton dimensions shown in the source package: approximately **314 × 148 × 194 mm** for the 8-pack and **364 × 288 × 169 mm** for the 16-pack. With the updated **127 mm pallet** input, the reproduced total palletized heights are **1,291 mm** and **1,310 mm**.

<figure class="blog-figure">
  <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/capacity-comparison.webp" alt="Bar chart comparing 1,152 and 1,232 base products per pallet in TOPS Pro source results and KolliPack backend results" loading="lazy">
  <figcaption>The headline capacity is aligned in this fixture: both result sets show 1,152 units for the 8-pack and 1,232 for the 16-pack.</figcaption>
</figure>

<div class="blog-figure-grid">
  <figure class="blog-figure">
    <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/tops-result-8.webp" alt="TOPS Pro source screenshot showing the selected 8-product carton with 1,152 units per unit load" loading="lazy">
    <figcaption>TOPS Pro source result for the 8-pack: 1,152 units and 144 cases per unit load.</figcaption>
  </figure>
  <figure class="blog-figure">
    <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/tops-result-16.webp" alt="TOPS Pro source screenshot showing the selected 16-product carton with 1,232 units per unit load" loading="lazy">
    <figcaption>TOPS Pro source result for the 16-pack: 1,232 units and 77 cases per unit load.</figcaption>
  </figure>
</div>

</section>

<section class="blog-content-section" markdown="1">

## Same capacity question, different interaction styles

In the supplied tutorial, TOPS Pro evaluates the tested quantities and presents a preferred row. KolliPack takes a more inspectable path in this workflow: the user can enter a desired quantity, generate designs, review ranked alternatives, and then run the selected carton through palletization.

That is a difference in interaction philosophy, not proof that one calculation engine is universally better. A team may want an automatically highlighted answer when speed is the priority. It may also want to see how the 8-pack, 10-pack, 16-pack, 18-pack, and 24-pack behave before changing an approved packaging specification.

The KolliPack alternatives show why the second view can matter. For the 8-pack, several candidate designs reach 1,152 base units per pallet. For the 16-pack, the leading visible candidate reaches 1,232, while other candidates fall back to 1,152 or lower. The pack quantity is therefore only one part of the result; carton geometry and pallet arrangement still decide the outcome.

<div class="blog-figure-grid">
  <figure class="blog-figure">
    <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/kollipack-alternatives-8.webp" alt="KolliPack ranked container alternatives for the 8-product case pack, with multiple rows reaching 1,152 base units per pallet" loading="lazy">
    <figcaption>KolliPack exposes multiple 8-pack alternatives instead of reducing the case to one unexplained geometry.</figcaption>
  </figure>
  <figure class="blog-figure">
    <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/kollipack-alternatives-16.webp" alt="KolliPack ranked container alternatives for the 16-product case pack, led by a 1,232-unit pallet result" loading="lazy">
    <figcaption>The 16-pack list contains a 1,232-unit leader alongside lower-capacity alternatives.</figcaption>
  </figure>
</div>

<div class="blog-figure-grid">
  <figure class="blog-figure">
    <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/kollipack-result-8.webp" alt="KolliPack palletization result showing 144 cartons, 6 layers, 24 cartons per layer, and 1,291 millimetres stack height" loading="lazy">
    <figcaption>KolliPack reproduction of the matched 8-pack pallet: 144 cartons, 6 layers, and 1,291 mm total height.</figcaption>
  </figure>
  <figure class="blog-figure">
    <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/kollipack-result-16.webp" alt="KolliPack palletization result showing 77 cartons, 7 layers, 11 cartons per layer, and 1,310 millimetres stack height" loading="lazy">
    <figcaption>KolliPack reproduction of the matched 16-pack pallet: 77 cartons, 7 layers, and 1,310 mm total height.</figcaption>
  </figure>
</div>

</section>

<section class="blog-content-section" markdown="1">

## Why 80 more units may not be the best business answer

The 16-pack looks attractive if the only score is base products per pallet. But packaging teams rarely approve a case by looking at one pallet number.

Changing from 8 to 16 products per carton can require work in:

- packaging and product master data;
- barcode or identifier creation and verification;
- drawings, specifications, work instructions, and customer documentation;
- warehouse locations, picking rules, and inventory quantities;
- customer receiving, opening, replenishment, and handling routines;
- supplier tooling, samples, line trials, and qualification records.

The new carton may also change the physical handling experience. A larger or heavier case can be harder to lift, open, count, store, or return, even when its pallet utilization is better. Conversely, a smaller case can be easier to handle but require more cartons, more labels, or more pallet positions. Those are decision considerations, not measured outcomes from this benchmark.

The right question is therefore not “Which row has the largest number?” It is closer to: **Does the extra pallet capacity justify the specification change for this supply chain?** The answer depends on approved case dimensions, handling limits, customer requirements, order quantities, supplier capability, and physical test results that are outside the supplied calculation.

</section>

<section class="blog-content-section" markdown="1">

## Open the case and inspect the alternatives

The exact KolliPack case is prepopulated with the confirmed 8-pack starting point: a 153 × 70 × 89 mm product, 68 g product weight, R1 and R3 allowed, a 314 × 148 × 194 mm matched carton, a 1,219 × 1,016 × 127 mm pallet, a 1,346 mm maximum stack height, zero overhang, and a 4 mm carton-caliper assumption.

<div class="blog-note"><i class="bi bi-box-seam me-2"></i><a href="/full-packaging/case/tops-product-pallet-optimization/?reset=1" target="_blank" rel="noopener">Open the prepopulated 8-pack benchmark in KolliPack</a> and change the desired quantity, carton dimensions, caliper, or pallet assumptions to see which parts of the result move together.</div>

The value of the case is not that it tells every team to choose 8 or 16. It gives the team a reproducible starting point for asking a better question: what changes when the case-pack decision is followed through carton design and palletization?

</section>

<section class="blog-content-section" markdown="1">

## What this benchmark does not establish

The comparator source is the public [TOPS tutorial supplied for this case](https://www.youtube.com/watch?v=aAeo0ZSB7vU). The package does not identify a TOPS Pro version, edition, region, or capture date, so this article makes no claim about current or universal TOPS Pro functionality. It reports what is visible in the supplied tutorial screenshots and notes.

The comparison also uses different presentation units and an explicit assumption: TOPS is shown in inches with a C-flute and 0.018 in caliper field, while KolliPack uses rounded metric product inputs and a manually entered 4 mm caliper. The 4 mm value is the agreed KolliPack assumption for this benchmark; the 0.018 in field is not treated as an equivalent input.

Finally, calculated carton and pallet geometry is a screening result. It does not certify compression strength, load stability, forklift handling, transport safety, regulatory compliance, supplier approval, or customer acceptance. Those decisions require the relevant specifications, engineering review, samples, and physical testing.

This draft should receive human and legal review before publication because it names and compares a third-party product. The wording is intentionally limited to the supplied fixture and evidence.

</section>

<section class="blog-content-section" markdown="1">

## The practical conclusion

In this focused case, KolliPack reproduces the same headline capacities reported in the TOPS Pro tutorial: **1,152 base units per pallet for the 8-pack and 1,232 for the 16-pack**. That supports the narrower hypothesis that the two tools can produce comparable pallet-capacity results under this fixture.

The more important lesson is what happens after the match. The 16-pack offers a calculated 80-unit pallet increase, but adopting it may create a wider packaging change. A useful optimizer helps quantify the geometry; a sound packaging decision still weighs the operational and commercial consequences around that geometry.

</section>
