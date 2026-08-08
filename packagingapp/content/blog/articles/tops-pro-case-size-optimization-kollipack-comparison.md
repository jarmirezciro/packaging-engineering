+++
schema_version = 1
status = "published"
display_order = 2
title = "Can KolliPack Match TOPS Pro? The 8-Pack vs 16-Pack Case"
slug = "tops-pro-case-size-optimization-kollipack-comparison"
subtitle = "A focused case study on case-pack quantity, pallet yield, and the decision behind the number."
excerpt = "In the supplied TOPS Pro case, 16 products per carton reach 1,232 units per pallet versus 1,152 for the current 8-pack. KolliPack reproduces both results and makes the next decision visible."
summary = "A business-focused comparison of one public TOPS Pro case and a matched KolliPack reproduction, showing why pallet capacity alone does not decide whether a shipping quantity should change."
description = "Can KolliPack match TOPS Pro on a case-pack optimization problem? Follow one 8-pack versus 16-pack pallet case, compare the results, and explore the assumptions in a prepopulated KolliPack case."
seo_title = "KolliPack vs TOPS Pro: 8-Pack vs 16-Pack Pallet Optimization"
meta_description = "Compare the 8-pack and 16-pack results from one public TOPS Pro case with a matched KolliPack reproduction, then test pallet overhang and carton caliper."
article_type = "demo_case_study"
author = "Alejandro Ramírez"
category = "Palletization"
read_time = "6 min read"
published_at = 2026-08-08
updated_at = 2026-08-08
hero_icon = "bi-box-seam"
featured_image = "img/blog/tops-pro-case-size-optimization-kollipack-comparison/thumbnail.webp"
thumbnail = "img/blog/tops-pro-case-size-optimization-kollipack-comparison/thumbnail.webp"
thumbnail_alt = "TOPS Pro and KolliPack case-pack results comparing 8 products and 16 products per carton"
primary_keyword = "KolliPack vs TOPS Pro"
tags = ["KolliPack vs TOPS Pro", "case pack optimization", "pallet yield", "packaging engineering case study"]
related_articles = ["kollipack-vs-tops-pro-palletization-benchmark", "think-beyond-the-box-packaging-flow-case-study"]
related_tools = ["packaging-flow", "palletization"]
canonical_path = "/blog/tops-pro-case-size-optimization-kollipack-comparison/"
og_image = "img/blog/tops-pro-case-size-optimization-kollipack-comparison/thumbnail.webp"
takeaways = ["The supplied TOPS Pro case reports 1,152 units per pallet for the 8-pack and 1,232 for the 16-pack.", "KolliPack reproduces those headline pallet capacities with the stated metric inputs and the updated 127 mm pallet height.", "The 80-unit increase is a case-pack change with commercial and operational consequences, not only a pallet result.", "Changing overhang, carton caliper, or carton geometry may be worth exploring before changing an established shipping quantity."]

[cta]
label = "Open the prepopulated TOPS Pro case in KolliPack"
url = "/full-packaging/case/tops-product-pallet-optimization/?reset=1"
new_tab = true
+++

<section class="blog-content-section" markdown="1">

The supplied TOPS Pro tutorial finds **1,152 products per pallet with an 8-pack carton** and **1,232 products with a 16-pack carton**. KolliPack reproduces those same headline capacities in this case. The difference is **80 products per pallet**, or about **6.9%**.

That result answers one question: can the second tool reach the same pallet yield under the stated inputs? It does. The more useful business question comes next: **does 80 more products per pallet justify changing an established case pack from 8 to 16?**

> **Comparison scope.** TOPS Pro results were reproduced from the [public tutorial used for this case](https://www.youtube.com/watch?v=aAeo0ZSB7vU). KolliPack is not affiliated with or endorsed by TOPS Software Corporation. This article compares one palletization case and does not represent a complete product evaluation.

</section>

<section class="blog-content-section" markdown="1">

## The business question behind the video

The TOPS Pro video presents a generic brand-owner scenario rather than a named company or product. The company is already shipping a product in an **8-unit carton** and wants to know whether a larger case pack would improve pallet utilization. The tool compares **8, 10, 16, 18, and 24 products per carton**, then identifies the 16-pack as the strongest result for the demonstrated pallet case.

The video also uses an illustrative annual volume of **one million products**. At that volume, its presenter explains that moving from 1,152 to just over 1,200 products per pallet would avoid approximately **57 pallets per year**. That is a useful way to frame the opportunity, but it remains an illustration from the tutorial—not a forecast for a particular company.

For a packaging or purchasing manager, the decision is familiar. A higher case pack may improve logistics, but it also changes the shipping specification that customers, warehouses, suppliers, and internal systems use. The calculation is therefore a screening step before a packaging change, not the whole approval decision.

<figure class="blog-figure">
  <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/case-setup-flow.webp" alt="Case-study flow from product dimensions and case-pack quantity to carton geometry, pallet yield, and the packaging decision" loading="lazy">
  <figcaption>The case follows one product requirement through case-pack quantity, carton geometry, and pallet yield to the business decision.</figcaption>
</figure>

</section>

<section class="blog-content-section" markdown="1">

## Setting up the same case in both tools

The product in the tutorial is approximately **153 × 70 × 89 mm** and weighs about **68 g** after conversion from the source value. The brand-owner rules allow two permitted upright orientations, represented by **R1 and R3** in KolliPack.

The unit load is a **1,219 × 1,016 × 127 mm GMA pallet**, with a **1,346 mm maximum total height** and zero permitted overhang. For the KolliPack reproduction, the C-flute assumption is represented as a **4 mm carton caliper**. The source material does not identify a TOPS version, edition, or region, so this is a comparison of the supplied public result and the reproduced case inputs—not a version-controlled software test.

TOPS evaluates the five quantities together and presents a preferred result. KolliPack exposes the quantities as cases to inspect: the user can generate a carton for 8, 10, 16, 18, or 24 products, review the alternatives, and pass a selected carton to palletization. That is a different interaction model, but it leads to the same practical comparison: how does the case-pack decision change the pallet?

<figure class="blog-figure">
  <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/case-setup-comparison.webp" alt="TOPS Pro case setup above KolliPack case setup for the same product orientation, carton, and pallet inputs" loading="lazy">
  <figcaption>The supplied TOPS Pro setup and the matched KolliPack setup describe the same product, permitted orientations, carton assumptions, and pallet limits.</figcaption>
</figure>

</section>

<section class="blog-content-section" markdown="1">

## The result: the same pallet answer in this case

The matched outputs are simple to read:

<div class="blog-table-wrap">
<table class="table blog-result-table">
  <thead><tr><th>Case pack</th><th>TOPS Pro result</th><th>KolliPack result</th><th>Pallet detail</th></tr></thead>
  <tbody>
    <tr><td>8 products/carton</td><td><strong>1,152 products</strong></td><td><strong>1,152 products</strong></td><td>144 cartons; 24 per layer × 6 layers</td></tr>
    <tr><td>16 products/carton</td><td><strong>1,232 products</strong></td><td><strong>1,232 products</strong></td><td>77 cartons; 11 per layer × 7 layers</td></tr>
  </tbody>
</table>
</div>

The KolliPack reproduction uses matched carton dimensions of approximately **314 × 148 × 194 mm** for the 8-pack and **364 × 288 × 169 mm** for the 16-pack. The resulting total palletized heights are **1,291 mm** and **1,310 mm**, both within the stated 1,346 mm limit.

<figure class="blog-figure">
  <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/results-mesh-comparison.webp" alt="Four-panel comparison of TOPS Pro and KolliPack box and pallet results for 8-product and 16-product cartons" loading="lazy">
  <figcaption>Top row: the 8-pack. Bottom row: the 16-pack. Each cell combines the carton result with its pallet result so the case-pack decision can be read from product to unit load.</figcaption>
</figure>

The match is the important result of this case. It shows that KolliPack can reproduce the source tutorial's two headline pallet capacities with the stated assumptions. It does not establish that every feature, ranking convention, or result across either product is identical.

</section>

<section class="blog-content-section" markdown="1">

## More alternatives make the next question visible

The result tables show another difference in the workflow. The supplied TOPS table presents **12 alternatives** for the case comparison. KolliPack generates a broader inspectable list in this case: **20 alternatives for the 8-pack and 30 for the 16-pack**.

The count itself is not a score for either tool. It matters because a packaging team may want to look beyond the first highlighted row. Several 8-pack designs can reach the 1,152-unit pallet result, while the leading 16-pack design reaches 1,232. Carton geometry and pallet pattern still matter after the quantity has been chosen.

<figure class="blog-figure">
  <img src="static://img/blog/tops-pro-case-size-optimization-kollipack-comparison/result-table-comparison-collage.webp" alt="KolliPack ranked result tables for 8-pack and 16-pack cases beside the supplied TOPS Pro result table" loading="lazy">
  <figcaption>The comparison keeps the result matrices visible: KolliPack's 8-pack and 16-pack alternatives are shown beside the supplied TOPS Pro alternatives.</figcaption>
</figure>

</section>

<section class="blog-content-section" markdown="1">

## Should the company change from 8 to 16?

If pallet yield is the only criterion, the 16-pack is attractive. It carries **80 more products per pallet** in this case. But changing the case quantity is a packaging-system decision, not a simple data-entry change.

Moving from 8 to 16 may require review of:

- packaging master data, case labels, and barcodes;
- customer, warehouse, and supplier records that use the case quantity;
- case weight, lifting, opening, counting, and storage practices;
- order quantities, inventory levels, and the amount of product held in each case;
- carton equipment, closing, compression, pallet stability, and physical testing.

A larger case can improve pallet yield while being less convenient for a customer or operator. A smaller case can be easier to handle and replenish while requiring more cartons and pallet positions. The correct answer depends on the real supply chain, not only the highest number in the result table.

</section>

<section class="blog-content-section" markdown="1">

## Explore the assumptions before changing shipping quantities

The prepopulated KolliPack case opens with the 8-pack baseline, the confirmed **127 mm pallet height**, **1,346 mm maximum total height**, zero overhang, R1 and R3 product orientations, and the 4 mm C-flute caliper assumption.

<a href="/full-packaging/case/tops-product-pallet-optimization/?reset=1" target="_blank" rel="noopener"><strong>Open the prepopulated case in KolliPack</strong></a> and change the desired quantity to compare the 8-pack with 10, 16, 18, or 24. Then try the variables that are often fixed too early: pallet overhang, carton caliper, and the carton geometry selected for palletization.

That experiment may show that changing the shipping quantity is not the only way to improve the 8-pack result. It may also show that a larger case is still the better choice. Either way, the team gets more information before changing master data, labels, customer communication, and physical packaging.

The calculation is decision support. The selected carton and pallet pattern still require review against supplier drawings, material specifications, handling requirements, and physical tests before release.

</section>

<section class="blog-content-section" markdown="1">

## Practical takeaway

In this focused case, **KolliPack matches the supplied TOPS Pro pallet results**: 1,152 products per pallet for the 8-pack and 1,232 for the 16-pack.

The more valuable conclusion is not that every company should move to 16. It is that a matched pallet result gives managers a credible starting point for the next decision: compare the case-pack change with the operational cost of keeping the current quantity, and test the assumptions that may improve the existing case before changing it.

<div class="blog-note"><i class="bi bi-box-seam me-2"></i><a href="/full-packaging/case/tops-product-pallet-optimization/?reset=1" target="_blank" rel="noopener">Open the exact KolliPack case</a> and explore the 8-pack, 16-pack, pallet overhang, and carton-caliper assumptions.</div>

</section>
