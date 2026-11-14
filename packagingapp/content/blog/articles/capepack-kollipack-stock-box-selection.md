+++
schema_version = 1
status = "published"
title = "CapePack and KolliPack: Choosing a Stock Box for 20 Units"
slug = "capepack-kollipack-stock-box-selection"
excerpt = "A stock-box case study shows how target quantity and upright orientation change the shortlist, even when several boxes can hold the order."
subtitle = "How target quantity and upright orientation change which catalogue box makes the shortlist."
seo_title = "Stock Box Selection with CapePack and KolliPack"
meta_description = "Compare CapePack Case Fills and KolliPack Container Selection, then see how an upright 20-unit or 16-unit order changes the stock-box shortlist."
article_type = "demo_case_study"
category = "Box selection"
author = "Alejandro Ramírez"
published_at = 2026-11-14
updated_at = 2026-11-14
thumbnail = "img/blog/capepack-kollipack-stock-box-selection/thumbnail-v2.webp"
thumbnail_alt = "Two kraft shipping boxes of different sizes beside a blank retail carton"
og_image = "img/blog/capepack-kollipack-stock-box-selection/thumbnail-v2.webp"
canonical_path = "/blog/capepack-kollipack-stock-box-selection/"
primary_keyword = "stock box selection"
tags = ["stock box selection", "packaging catalogues", "case filling", "CapePack"]
related_articles = ["box-selection-3d-bin-packing-problem"]
related_tools = ["container-selection"]
takeaways = [
  "Set the order quantity and permitted product orientation before ranking stock boxes.",
  "Compare how much of each box the order fills. A box with spare capacity can still be a poor fit for that order.",
  "Trial-pack the shortlisted box with the actual product and protective materials before ordering stock."
]

[explore]
text = "To compare your own stock boxes, enter your product dimensions and order quantity in"
label = "KolliPack Container Selection"
url = "/container-selection/mode1/"

[[flow_steps]]
icon = "bi-bounding-box"
label = "Packaged product"

[[flow_steps]]
icon = "bi-boxes"
label = "Packaging catalogue"

[[flow_steps]]
icon = "bi-box"
label = "Selected case"

[cta]
label = "Run the 20-unit stock-box case"
url = "/container-selection/mode1/?case=capepack-stock-box-20"
new_tab = true
+++

When a company already stocks a range of shipping boxes, the packaging team has to choose which size suits the product and order quantity. Inspired by Esko’s CapePack Case Fills demonstration, we used its stock-box dimensions to reproduce individual examples and investigate that decision in KolliPack. [Cape Pack Advanced demo, Case Fills](https://www.youtube.com/watch?v=9be4hp7gRf4&t=1310s)

Both tools fit 20 upright units in the reference stock box at about 77.6% fill. For 16 units, we reproduced CapePack’s 75.9% result in the corresponding case. KolliPack also identified a different box among the 17 catalogue records we examined that fit the 16 units at 84.4% fill. KolliLabs develops KolliPack independently and has no affiliation with Esko.

## Case Setup

Imagine a buyer selecting a shipping carton for boxed replacement parts. The test product measures **6 × 4 × 6 in** and weighs **2.2 lb** per packaged unit. The original height stays vertical. Each unit can turn on its base, so a layer can mix 6 × 4 in and 4 × 6 in footprints while remaining 6 in high.

<figure class="blog-figure">
  <picture>
    <source media="(max-width: 575px)" srcset="static://img/blog/capepack-kollipack-stock-box-selection/stock-box-setup-mobile.webp">
    <img src="static://img/blog/capepack-kollipack-stock-box-selection/stock-box-setup.webp" alt="A 6 by 4 by 6 inch upright product, a catalogue of stock shipping boxes, and the selected case for a 20-unit order." loading="lazy">
  </picture>
  <figcaption>Figure 1. Conceptual stock-box selection. Use the product’s outside dimensions and the case’s inside dimensions to evaluate catalogue alternatives.</figcaption>
</figure>

### CapePack Packaging Catalogue

The five stock-box records below come from the CapePack demonstration and are among the 17 records we reconstructed for the KolliPack comparison. The number in each CAPECASE reference matches the original CapePack record number.

<div class="blog-table-wrap">
  <table class="table table-sm blog-result-table" aria-label="Selected CapePack stock-box inputs">
    <thead>
      <tr><th scope="col">Case reference</th><th scope="col">Inside dimensions (in)</th></tr>
    </thead>
    <tbody>
      <tr><th scope="row" class="text-nowrap">CAPECASE-005</th><td>19.875 × 14.5 × 12.875</td></tr>
      <tr><th scope="row" class="text-nowrap">CAPECASE-006</th><td>20.512 × 14.528 × 22.008</td></tr>
      <tr><th scope="row" class="text-nowrap">CAPECASE-009</th><td>16.5 × 16.5 × 16.5</td></tr>
      <tr><th scope="row" class="text-nowrap">CAPECASE-014</th><td>15.5 × 14.5 × 13.5</td></tr>
      <tr><th scope="row" class="text-nowrap">CAPECASE-015</th><td class="text-body fw-normal">15 × 14 × 13</td></tr>
    </tbody>
  </table>
</div>

CapePack lists CAPECASE-006 as 521 × 369 × 559 mm. The table shows the inch conversion rounded to three decimal places.

## How the two workflows choose which boxes to test

CapePack’s Fill Restrictions screen lets the operator nominate several stock-case records from the database. The demonstration shows records 1, 5, 7 and 9 entered together. In KolliPack, we selected the packaging catalogue and entered the required quantity. KolliPack evaluated which boxes could hold the order and ranked those cases by the share of inside volume the order would occupy.

<figure class="blog-figure">
  <picture>
    <source media="(max-width: 575px)" srcset="static://img/blog/capepack-kollipack-stock-box-selection/catalogue-selection-comparison-mobile.webp">
    <img src="static://img/blog/capepack-kollipack-stock-box-selection/catalogue-selection-comparison.webp" alt="CapePack Fill Restrictions with several case records entered, alongside the KolliPack Capecatalogue selector." loading="lazy">
  </picture>
  <figcaption>Figure 2. In the CapePack demonstration, several database records are entered for evaluation. In KolliPack, we selected the reconstructed catalogue.</figcaption>
</figure>

## Which stock box fits 20 upright units?

The order takes up 2,880 in³ before any allowance for protective material. For each box that can fit the order, divide that volume by the box’s inside volume. The resulting percentage is the **volume used by the order**. The Units column shows calculated capacity. In the result tables, case IDs omit the CAPECASE- prefix.

<div class="blog-table-wrap">
  <table class="table table-sm blog-result-table" aria-label="Stock boxes ranked by fill">
    <thead>
      <tr><th scope="col">Case ID</th><th scope="col">Inside size (in)</th><th scope="col">Units</th><th scope="col">Fill</th></tr>
    </thead>
    <tbody>
      <tr class="fw-bold"><th scope="row">005</th><td>19.875 × 14.5 × 12.875</td><td>20</td><td>77.6%</td></tr>
      <tr><th scope="row">009</th><td>16.5 × 16.5 × 16.5</td><td>20</td><td>64.1%</td></tr>
      <tr><th scope="row">006</th><td>20.512 × 14.528 × 22.008</td><td>33</td><td>43.9%</td></tr>
    </tbody>
  </table>
</div>

CapePack shows the corresponding Box record at 20 units and 77.6% cube used. [CapePack Box result](https://www.youtube.com/watch?v=9be4hp7gRf4&t=1513s)

CAPECASE-005 uses about **17% less inside volume** than CAPECASE-009 for the same 20-unit order. CAPECASE-006 offers the most spare capacity in this shortlist. It makes sense to keep it in consideration if the order quantity regularly grows beyond 20.

<figure class="blog-figure">
  <picture>
    <source media="(max-width: 575px)" srcset="static://img/blog/capepack-kollipack-stock-box-selection/twenty-unit-packing-mobile.webp">
    <img src="static://img/blog/capepack-kollipack-stock-box-selection/twenty-unit-packing.webp" alt="CapePack and KolliPack views of the stock box that holds 20 upright units. Both runs use 77.6 percent of its inside volume." loading="lazy">
  </picture>
  <figcaption>Figure 3. Two layers of ten upright units in CapePack’s Box record and the corresponding CAPECASE-005 in KolliPack. The KolliPack capture shows a whole-percent result.</figcaption>
</figure>

[Run the 20-unit stock-box case](/container-selection/mode1/?case=capepack-stock-box-20) to check CAPECASE-005 on its own. The case opens with the product and box dimensions in inches and allows only the original height to stay vertical. Change the dimensions or permitted orientations and recalculate to see what fits.

## What changes when the order drops to 16?

At 16 units, two smaller cases enter the shortlist under the same upright constraint. CapePack’s case2 demonstration shows 16 units at 75.9% fill in CAPECASE-014, a result we reproduced in KolliPack. Our KolliPack catalogue run also found CAPECASE-015, which fits the same quantity into a smaller box at 84.4% fill. The larger 014 may still be worth trial-packing if the product needs extra clearance or protection. [CapePack case2 result](https://www.youtube.com/watch?v=9be4hp7gRf4&t=1446s)

<div class="blog-table-wrap">
  <table class="table table-sm blog-result-table" aria-label="Stock boxes ranked by fill">
    <thead>
      <tr><th scope="col">Case ID</th><th scope="col">Inside size (in)</th><th scope="col">Units</th><th scope="col">Fill</th></tr>
    </thead>
    <tbody>
      <tr class="fw-bold"><th scope="row">015</th><td>15 × 14 × 13</td><td>16</td><td>84.4%</td></tr>
      <tr><th scope="row">014</th><td>15.5 × 14.5 × 13.5</td><td>16</td><td>75.9%</td></tr>
      <tr><th scope="row">005</th><td>19.875 × 14.5 × 12.875</td><td>20</td><td>62.1%</td></tr>
    </tbody>
  </table>
</div>

<figure class="blog-figure">
  <picture>
    <source media="(max-width: 575px)" srcset="static://img/blog/capepack-kollipack-stock-box-selection/sixteen-unit-case-comparison-mobile.webp">
    <img src="static://img/blog/capepack-kollipack-stock-box-selection/sixteen-unit-case-comparison.webp" alt="CapePack shows 16 units in CAPECASE-014 at 75.9 percent fill. KolliPack shows 16 units in the smaller CAPECASE-015 at 84.4 percent fill." loading="lazy">
  </picture>
  <figcaption>Figure 4. CapePack’s demonstrated 16-unit case and the smaller alternative we found in KolliPack. The KolliPack capture displays 84% after rounding.</figcaption>
</figure>

If 16-unit orders are occasional, CAPECASE-005 can serve both order sizes. If 16 is a regular order size, trial-pack CAPECASE-015 and compare the cost of stocking a second box size with the benefit of a more compact case. A supplier’s actual inside dimensions, manufacturing tolerances, room for protection and measured packed weight can all affect that decision.
