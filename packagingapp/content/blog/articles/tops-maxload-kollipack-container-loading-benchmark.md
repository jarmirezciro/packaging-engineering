+++
schema_version = 1
status = "published"
title = "From 1,285 to 1,319: Testing a TOPS MaxLoad Case in KolliPack"
slug = "tops-maxload-kollipack-container-loading-benchmark"
subtitle = "A bounded 40-ft high-cube benchmark that tests whether visible unused space can accept more cargo."
excerpt = "We reconstructed a public TOPS MaxLoad high-cube case in KolliPack, matched its 1,285-unit manifest, then tested the remaining geometry with additional cargo."
summary = "A focused container-loading benchmark that reproduces one TOPS MaxLoad high-cube result in KolliPack and tests the residual geometry with two separate quantity probes."
description = "A case-scoped comparison of one public TOPS MaxLoad high-cube load and matched KolliPack calculations, including an exact 1,285-unit reproduction and two additional-cargo probes."
seo_title = "TOPS MaxLoad vs KolliPack: High-Cube Loading Benchmark"
meta_description = "A focused container-loading benchmark reproducing a TOPS MaxLoad high-cube case in KolliPack and testing usable capacity beyond 1,285 load units."
article_type = "demo_case_study"
author = "Alejandro Ramírez"
category = "Transport Loading"
read_time = "9 min read"
published_at = 2026-10-20
updated_at = 2026-10-20
hero_icon = "bi-truck"
featured_image = "img/blog/tops-maxload-kollipack-container-loading-benchmark/thumbnail.webp"
thumbnail = "img/blog/tops-maxload-kollipack-container-loading-benchmark/thumbnail.webp"
thumbnail_alt = "KolliPack high-cube result beside the headline 1,285 units, room still left, and 34 more in this case"
primary_keyword = "TOPS MaxLoad container loading benchmark"
tags = ["TOPS MaxLoad benchmark", "container loading benchmark", "40-ft high-cube", "mixed cargo loading", "KolliPack"]
related_articles = ["container-loading-benchmark-kollipack-br1-br7"]
related_tools = ["transport-container"]
canonical_path = "/blog/tops-maxload-kollipack-container-loading-benchmark/"
og_image = "img/blog/tops-maxload-kollipack-container-loading-benchmark/thumbnail.webp"
takeaways = ["KolliPack reproduced all 1,285 load units in the optimized TOPS manifest.", "A separate Progressive Fill probe loaded 34 additional SKU302473 units, reaching 1,319.", "Another separate probe increased Case 1 from 32 to 40, reaching 1,293.", "The result is specific to this fixture and does not establish universal product superiority or physical load approval."]

[cta]
label = "Try the same high-cube benchmark in KolliPack"
url = "/free-container-loading-calculator/?case=tops-max-load-high-cube-benchmark"
new_tab = true
+++

<section class="blog-content-section" markdown="1">

In a public TOPS MaxLoad example, the optimized 40-ft high-cube load contains **1,285 load units**. KolliPack reproduced that exact manifest and loaded all 1,285. The more useful test came next: instead of treating visible unused space as proof, we added cargo. The tested KolliPack **Progressive Fill** solution accepted another **34 units of SKU302473**, taking this same fixture to **1,319 load units**.

That is about **2.6% more load units in this specific test**. It is not a claim that KolliPack is universally better, that TOPS could not produce another arrangement, or that either result is mathematically optimal.

> **Comparison scope.** This article examines one supplied public TOPS MaxLoad reference case and the stated KolliPack inputs. It is not a complete product evaluation, and the conclusion should not be generalized beyond this fixture. KolliLabs/KolliPack is independent of and not affiliated with TOPS Software Corporation.

</section>

<section class="blog-content-section" markdown="1">

## Why an external reference case is useful

A benchmark designed around our own software can accidentally favor the way that software works. A public case created elsewhere is more demanding: the container, load-unit sizes, quantities, and reference result were not selected to make KolliPack look good.

This fixture also asks a practical question for a distribution or transport-planning team. If several rectangular case types must share one high-cube container, does the calculated arrangement merely look compact, or does it leave space that can accept additional load units? The distinction matters because nominal cargo volume and usable geometric space are not the same thing.

The TOPS source starts with four quantity-level load units. Its interface also displays a separate piece count for some rows, so this article consistently uses **load units**, not consumer pieces.

<div class="blog-table-wrap">
<table class="table blog-result-table">
  <thead><tr><th>ID</th><th>TOPS / KolliPack label</th><th>Dimensions (mm)</th><th>Original qty</th><th>TOPS optimized qty</th></tr></thead>
  <tbody>
    <tr><td>P1</td><td>SKU302473</td><td>457.2 × 279.4 × 317.5</td><td>375</td><td>400</td></tr>
    <tr><td>P2</td><td>SKU503739</td><td>431.8 × 318.77 × 317.5</td><td>405</td><td>405</td></tr>
    <tr><td>P3</td><td>SKU57392 / Case Pack 12</td><td>558.8 × 377.444 × 317.5</td><td>288</td><td>288</td></tr>
    <tr><td>P4</td><td>SKU9876 / Case Pack</td><td>558.8 × 355.6 × 381.0</td><td>160</td><td>160</td></tr>
    <tr><td>P5</td><td>Case 1</td><td>558.8 × 406.4 × 317.5</td><td>—</td><td>32</td></tr>
  </tbody>
</table>
</div>

<figure class="blog-figure">
  <img src="static://img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-kollipack-benchmark-setup.webp" alt="TOPS screenshots showing the four-row 1,228-unit manifest, selected 40-foot high-cube sea van, and Load Front to Back and Space Evenly strategies" loading="lazy">
  <figcaption>Figure 1. The supplied TOPS source establishes the initial 1,228-load-unit manifest, the 40 Ft. H.C. Sea Van, and the two displayed TOPS strategies.</figcaption>
</figure>

</section>

<section class="blog-content-section" markdown="1">

## Reconstructing the original 1,228-unit fixture

TOPS displays a **474 × 93 × 106 in** internal loading space. Those rounded values correspond to approximately **12,039 × 2,362 × 2,692 mm**, which is the metric fixture used for the KolliPack reconstruction. The original four rows total 1,228 load units and approximately **2,271 ft³** of product-envelope volume. The source reports about **84% cube utilization**; the current KolliPack backend calculates **84.008%** from the supplied metric dimensions.

The source shows two TOPS outputs: **Load Front to Back** and **Space Evenly**. KolliPack's current strategies are **Progressive Fill** and **Balanced Spread**. Similar names or visual objectives do not make the algorithms equivalent; they are independent implementations.

The layouts make a central point visible. When the same cargo occupies the same container, the aggregate cargo-volume percentage is essentially fixed. What changes is the arrangement: where product blocks end, how the longitudinal footprint develops, and whether the remaining shapes can accept another load unit.

<figure class="blog-figure">
  <img src="static://img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-kollipack-original-1228-comparison.webp" alt="TOPS Load Front to Back and Space Evenly results above an independent KolliPack Progressive Fill reproduction of the same 1,228-unit manifest" loading="lazy">
  <figcaption>Figure 2. The two TOPS source results and the independent KolliPack reproduction organize the same four-row manifest differently. The labels describe each product's own strategy; they do not imply algorithmic equivalence.</figcaption>
</figure>

</section>

<section class="blog-content-section" markdown="1">

## TOPS pushes its example from 1,228 to 1,285

The published example does not stop at the original manifest. TOPS increases SKU302473 from **375 to 400** and introduces **32 units of Case 1**. The other three quantities stay fixed, producing a five-row manifest of **1,285 load units**.

The source reports approximately **2,388.3 ft³** of cargo cube and **88.3%** cube utilization for this later result. The current KolliPack backend independently calculates 2,388.3 ft³ and 88.347% from the metric fixture. This is the important apples-to-apples control: the later TOPS manifest—not a different quantity mix—becomes the primary benchmark.

<figure class="blog-figure">
  <img src="static://img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-maxload-optimized-1285.webp" alt="TOPS optimized manifest and load showing 1,285 load units, 2,388.3 cubic feet, and 88.3 percent cube utilization" loading="lazy">
  <figcaption>Figure 3. TOPS adds Case 1 and increases SKU302473, creating the 1,285-unit manifest used for the direct KolliPack reproduction.</figcaption>
</figure>

</section>

<section class="blog-content-section" markdown="1">

## The exact TOPS manifest loads in KolliPack

KolliPack then received the same five requested quantities: **400, 405, 288, 160, and 32**. Progressive Fill loaded every row completely, for 1,285 of 1,285 requested units. A secondary backend check also loaded the full manifest with Balanced Spread, although its calculated geometry differed.

<figure class="blog-figure">
  <img src="static://img/blog/tops-maxload-kollipack-container-loading-benchmark/tops-kollipack-same-1285-manifest.webp" alt="TOPS optimized load beside the KolliPack Progressive Fill result with the same quantities 400, 405, 288, 160, and 32" loading="lazy">
  <figcaption>Figure 4. The quantities are held constant. Both displayed results contain the complete 1,285-unit optimized manifest, while their calculated arrangements leave different-looking residual geometry.</figcaption>
</figure>

The visual difference suggests that the KolliPack arrangement may retain usable capacity. But an empty-looking region is not enough evidence. Container utilization measures how much nominal product-envelope volume is present; it does not prove that every remaining cubic metre has the right shape, support, and orientation for another case.

The stronger question is therefore direct: **can another load unit actually be placed?**

</section>

<section class="blog-content-section" markdown="1">

## Two separate tests of the remaining geometry

The first probe keeps the entire 1,285-unit TOPS manifest and increases only SKU302473 from 400 to **434**. Progressive Fill loaded all requested units, reaching **1,319**. The 34 added units contribute about **48.7 ft³** of product-envelope volume, bringing calculated cargo cube to approximately **2,437.0 ft³** and volume utilization to **90.148%**.

The second probe asks a different question. It returns SKU302473 to 400, holds the other TOPS quantities constant, and increases only Case 1 from 32 to **40**. KolliPack loaded all 40 Case 1 units, reaching **1,293** load units. Those eight added cases contribute about **20.4 ft³**, for approximately **2,408.7 ft³** and **89.100%** calculated volume utilization.

These are separate experiments. The extra 34 SKU302473 units and the extra eight Case 1 units were **not** loaded simultaneously.

<div class="blog-table-wrap">
<table class="table blog-result-table">
  <thead><tr><th>Test</th><th>P1</th><th>P2</th><th>P3</th><th>P4</th><th>P5</th><th>Total</th></tr></thead>
  <tbody>
    <tr><td>Original TOPS case</td><td>375</td><td>405</td><td>288</td><td>160</td><td>—</td><td><strong>1,228</strong></td></tr>
    <tr><td>TOPS optimized result</td><td>400</td><td>405</td><td>288</td><td>160</td><td>32</td><td><strong>1,285</strong></td></tr>
    <tr><td>KolliPack exact reproduction</td><td>400</td><td>405</td><td>288</td><td>160</td><td>32</td><td><strong>1,285</strong></td></tr>
    <tr><td>Progressive Fill probe A</td><td>434</td><td>405</td><td>288</td><td>160</td><td>32</td><td><strong>1,319</strong></td></tr>
    <tr><td>Progressive Fill probe B</td><td>400</td><td>405</td><td>288</td><td>160</td><td>40</td><td><strong>1,293</strong></td></tr>
  </tbody>
</table>
</div>

<figure class="blog-figure">
  <img src="static://img/blog/tops-maxload-kollipack-container-loading-benchmark/kollipack-residual-capacity-test.webp" alt="Two separate KolliPack Progressive Fill probes showing 434 SKU302473 units for 1,319 total and 40 Case 1 units for 1,293 total" loading="lazy">
  <figcaption>Figure 5. Probe A adds 34 SKU302473 units; Probe B separately adds eight Case 1 units. Both preserve the other quantities from the 1,285-unit benchmark.</figcaption>
</figure>

### Why two probes are more informative than one

An unused region can be real yet highly product-specific. A narrow strip may accept one case orientation while rejecting another; a shallow top space may contribute nominal cubic volume without providing enough continuous support or height for the next unit. That is why a single cube percentage cannot describe the practical value of every empty region.

Probe A tests the strongest quantity result with SKU302473. It shows that the arrangement can absorb 34 more of that load unit without reducing any quantity from the optimized TOPS manifest. On its own, however, that result could be dismissed as a particularly convenient fit for the smaller P1 envelope.

Probe B provides a different challenge. Case 1 has a larger product-envelope volume than SKU302473, and the test changes only its quantity from 32 to 40. Loading all eight additional units does not prove that the remaining geometry is generally flexible, but it does show that the observed capacity was not limited to inserting more of only one smaller load-unit type.

Together, the probes make the evidence more useful while keeping it bounded: the same 1,285-unit reference manifest supports two independent quantity extensions, but the article does not combine them or extrapolate beyond the tested products and orientations.

For a planner, the business meaning is deliberately modest: under this dimensional fixture, the tested KolliPack arrangement carried more load units in the same container. No shipment volume, freight price, or annual operating data was supplied, so the benchmark does not convert that result into invented cost or sustainability savings.

</section>

<section class="blog-content-section" markdown="1">

## What this benchmark demonstrates—and what it does not

The evidence supports a narrow conclusion: **in this specific published fixture, the tested KolliPack Progressive Fill solution reproduced the complete 1,285-unit TOPS result and then accommodated additional cargo**. The strongest probe reached 1,319 by adding 34 SKU302473 load units. The second probe independently showed that the residual geometry could also accept eight more of the larger-by-volume Case 1 load unit.

The result does not establish universal KolliPack superiority, mathematical global optimality, or the limit of what another TOPS configuration, version, setting, optimization pass, or operator might achieve. It does not compare price, calculation speed, interface design, feature coverage, or commercial value.

The calculated geometry is decision support. It does not certify physical load stability, compression performance, cargo restraint, transport safety, loading ergonomics, handling requirements, regulatory compliance, or a released logistics instruction. Those decisions require the actual load units, transport unit, operating method, and appropriate physical and safety review.

Readers interested in broader algorithm evidence can also review [700 Container-Loading Tests: An Honest Benchmark of KolliPack](/blog/container-loading-benchmark-kollipack-br1-br7/), which asks a different question across a large public benchmark suite.

</section>

<section class="blog-content-section" markdown="1">

## Try the same high-cube fixture

The [prepopulated high-cube benchmark](/free-container-loading-calculator/?case=tops-max-load-high-cube-benchmark) opens the original four-row, 1,228-unit setup. From there, you can change quantities and loading strategy, add the Case 1 row, and observe how the calculated geometry changes.

The exact route is retained so the benchmark can be revisited against the current shared Transport Container engine rather than a separate article-only implementation.

<div class="blog-note"><i class="bi bi-truck me-2"></i><a href="/free-container-loading-calculator/?case=tops-max-load-high-cube-benchmark" target="_blank" rel="noopener">Try the same high-cube benchmark in KolliPack</a> and test the quantities and loading strategy yourself.</div>

</section>

<section class="blog-content-section" markdown="1">

## Evidence and publication note

The TOPS panels are faithful compositions of screenshots supplied from a public TOPS MaxLoad video. The exact video URL, tutorial date, and software version still require source confirmation before publication. The KolliPack values were reproduced on the current repository backend snapshot dated 20 October 2026.

Because this draft names a commercial comparator and reproduces source screenshots, source provenance, screenshot rights, and the final bounded wording require human/legal review before public release.

</section>
