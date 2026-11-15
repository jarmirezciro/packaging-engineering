+++
schema_version = 1
status = "published"
title = "One Container, 878 Units: Recreating an EasyCargo Loading Example"
slug = "easycargo-40hc-mixed-cargo-case-study"
subtitle = "Seven cargo types, three loading groups and two layouts for the same 40-ft high-cube manifest."
excerpt = "We reproduced a published EasyCargo shipment in KolliPack to see how handling restrictions and loading groups shaped two plans for the same cargo."
summary = "A case study of a mixed 40-ft high-cube shipment comparing two calculated layouts, their handling constraints and the Madrid–Paris loading boundary."
seo_title = "EasyCargo 40-ft High-Cube Loading Case Study | KolliPack"
meta_description = "See how KolliPack loaded all 878 units from an EasyCargo example and what orientation, stacking and loading groups meant for the layout."
article_type = "demo_case_study"
author = "Alejandro Ramírez"
category = "Transport Loading"
published_at = 2026-11-15
updated_at = 2026-11-15
hero_icon = "bi-truck"
thumbnail = "img/blog/easycargo-40hc-mixed-cargo-case-study/thumbnail-v1.webp"
thumbnail_alt = "Illustrated high-cube container with cartons at its doors and the headline 878 units, one container"
primary_keyword = "EasyCargo 40-ft high-cube loading case study"
tags = ["mixed cargo loading", "40-ft high-cube", "loading groups"]
related_articles = ["tops-maxload-kollipack-container-loading-benchmark"]
related_tools = ["transport-container"]
canonical_path = "/blog/easycargo-40hc-mixed-cargo-case-study/"
og_image = "img/blog/easycargo-40hc-mixed-cargo-case-study/thumbnail-v1.webp"
flow_steps = [{icon = "bi-box-seam", label = "Mixed load units"}, {icon = "bi-geo-alt", label = "3 destinations"}, {icon = "bi-truck", label = "40-ft high-cube container"}]
takeaways = ["Plan the full manifest with its handling rules and delivery groups in place. KolliPack accommodated all seven cargo types in one calculation.", "Compare layouts as well as loaded counts. When two plans fit the same shipment, use the layouts to assess access at each stop.", "Use KolliPack to compare feasible orientations, stackability settings and loading sequences while keeping the shipment’s actual handling requirements in force."]

[cta]
label = "Open the 878-unit case in KolliPack"
url = "/free-container-loading-calculator/?case=easycargo-40hc-mixed-cargo-benchmark"
new_tab = true

[explore]
text = "To plan a mixed shipment with your own dimensions, cargo restrictions and unloading order,"
label = "explore the KolliPack Container Loading Calculator"
url = "/free-container-loading-calculator/"
+++

<section class="blog-content-section" markdown="1">

## The challenge

EasyCargo’s article *How to Optimize Pallet Loading* includes a container report with seven cargo types and three loading groups. The shipment combines long pipes and compact appliance cartons in one 40-ft high-cube container, with restrictions on which units can tilt, turn or support other cargo. [EasyCargo’s published example](https://www.easycargo3d.com/en/blog/how-to-optimize-pallet-loading/)

We wanted to see whether KolliPack could accommodate the same manifest and how its progressive loading approach would arrange the three groups. We compared EasyCargo’s published Report 003, accessed on 14 November 2026, with an independent KolliPack calculation. KolliLabs and EasyCargo are independent, and the comparison implies no affiliation or endorsement.

</section>

<section class="blog-content-section" markdown="1">

## Case setup

The report specifies a **40-ft high-cube container** with internal dimensions of **12,117 × 2,388 × 2,694 mm** and **878 units** across seven cargo types.

<figure class="blog-figure">
  <picture>
    <source media="(max-width: 600px)" srcset="static://img/blog/easycargo-40hc-mixed-cargo-case-study/mixed-cargo-destinations-setup-mobile.webp">
    <img src="static://img/blog/easycargo-40hc-mixed-cargo-case-study/mixed-cargo-destinations-setup.webp" alt="Mixed cargo is grouped for Berlin, Madrid and Paris before loading into one 40-ft high-cube container." loading="lazy">
  </picture>
  <figcaption>Figure 1. Conceptual setup showing how cargo of different shapes is grouped by destination before loading into one shared container.</figcaption>
</figure>

Table 1 lists the cargo in loading-group order. A dash indicates that EasyCargo’s report shows no handling restriction for that row.

- **Load from the closed end toward the doors.** Group 1 · Berlin → Group 2 · Madrid → Group 3 · Paris.
- **Unload in the intended reverse order.** Paris → Madrid → Berlin.

Dimensions are length × width × height, converted from centimetres. We divided each row’s reported mass by its quantity to get the unit mass and entered all seven quantities as fixed counts.

<p id="easycargo-manifest-scroll" class="d-lg-none small text-secondary mb-0">Scroll the table sideways to see all columns.</p>

<div class="blog-table-wrap" tabindex="0" role="region" aria-labelledby="easycargo-manifest" aria-describedby="easycargo-manifest-scroll">
<table class="table table-sm table-striped mb-0">
  <caption id="easycargo-manifest" class="caption-top fw-bold text-dark"><span class="d-block" style="max-width: 75vw">Table 1. Shipment manifest and handling requirements</span></caption>
  <thead class="table-light text-nowrap"><tr><th scope="col">Load unit</th><th scope="col">Group</th><th scope="col">Restrictions</th><th scope="col">Size (mm)</th><th scope="col" class="text-end">Units</th><th scope="col" class="text-end">kg each</th></tr></thead>
  <tbody class="text-nowrap">
    <tr><th scope="row" class="fw-normal">Microwave WH352</th><td>1 · Berlin</td><td>—</td><td>414 × 503 × 400</td><td class="text-end">220</td><td class="text-end">9.3</td></tr>
    <tr><th scope="row" class="fw-normal">Breather pipe 15A</th><td>1 · Berlin</td><td>No tilt or rotation</td><td>2,500 × 150 × 150</td><td class="text-end">130</td><td class="text-end">2.4</td></tr>
    <tr><th scope="row" class="fw-normal">Microwave WD102</th><td>2 · Madrid</td><td>—</td><td>380 × 420 × 370</td><td class="text-end">193</td><td class="text-end">7.0</td></tr>
    <tr><th scope="row" class="fw-normal">Fridge Alhambra R3</th><td>2 · Madrid</td><td>No tilt</td><td>570 × 576 × 500</td><td class="text-end">58</td><td class="text-end">58.0</td></tr>
    <tr><th scope="row" class="fw-normal">Ceramic stove 45-LOC-13</th><td>3 · Paris</td><td>No stacking above</td><td>350 × 360 × 80</td><td class="text-end">26</td><td class="text-end">2.9</td></tr>
    <tr><th scope="row" class="fw-normal">Microwave RW 230</th><td>3 · Paris</td><td>—</td><td>380 × 420 × 370</td><td class="text-end">193</td><td class="text-end">7.0</td></tr>
    <tr><th scope="row" class="fw-normal">Freezer BD53V</th><td>3 · Paris</td><td>—</td><td>570 × 300 × 200</td><td class="text-end">58</td><td class="text-end">58.0</td></tr>
  </tbody>
</table>
</div>

</section>

<section class="blog-content-section" markdown="1">

## Translating loading requirements

### EasyCargo’s published setup

Report 003 shows a single loaded container, item quantities and restriction icons. EasyCargo distinguishes keeping the height vertical (**do not tilt**), keeping the stated length along the container (**do not rotate**) and keeping an item’s top clear (**do not stack on this item**). EasyCargo also offers several ways to separate priority groups. The published report does not identify which option was selected or show the weight-check settings. [EasyCargo item restrictions](https://help.easycargo3d.com/article/53/inserting-items) · [EasyCargo priority-group settings](https://help.easycargo3d.com/article/97/advanced-priority-groups-settings-)

### KolliPack’s handling inputs

**Orientation.** Each checked box permits one of the original dimensions to stand vertically. **R1** permits the length, **R2** the width and **R3** the height. We enabled only R3 for the pipes and fridges and all three permissions for the other five types.

R3 alone keeps the original height vertical. It still permits a 90-degree turn on the floor if the unit fits, while EasyCargo’s **Do not rotate** keeps the specified length along the container. Here the 2,500 mm pipes exceed the 2,388 mm internal width, so KolliPack can place them only lengthwise.

**Stackable.** A checked box lets the unit serve as support for cargo above it. We cleared it for the ceramic stoves to keep their tops clear. A stove can still rest on the floor or on another load unit that provides suitable support.

**Loading sequence.** We assigned **1** to Berlin, **2** to Madrid and **3** to Paris. Progressive Fill works through those groups from the closed end toward the doors. This puts the first intended delivery, Paris, toward the doors, with some use of space across adjacent group boundaries.

<figure class="blog-figure">
  <div class="bg-light border rounded-3 p-2 p-md-3">
    <p class="text-secondary small fw-semibold text-center mb-2">Selected rows from the KolliPack manifest</p>
    <picture>
      <source media="(max-width: 600px)" srcset="static://img/blog/easycargo-40hc-mixed-cargo-case-study/kollipack-handling-inputs-mobile.webp">
      <img class="w-auto mx-auto border rounded-2" src="static://img/blog/easycargo-40hc-mixed-cargo-case-study/kollipack-handling-inputs.webp" alt="KolliPack controls showing R3 alone for the pipe and fridge, Stackable cleared for the stove, and loading sequences 1, 2 and 3 for the three rows." loading="lazy">
    </picture>
  </div>
  <figcaption>Figure 2. KolliPack’s orientation, stackability and loading-sequence controls for the pipe, fridge and stove. <a href="static://img/blog/easycargo-40hc-mixed-cargo-case-study/kollipack-handling-inputs.webp" target="_blank" rel="noopener">View the full-size crop</a>.</figcaption>
</figure>

</section>

<section class="blog-content-section" markdown="1">

## KolliPack’s progressive loading approach

We selected **Progressive Fill – Mixed Cargo Infill** and used the same internal container dimensions, quantities and unit masses. The KolliPack screenshot in Figure 3 uses a 28,935 kg payload limit. The runnable case leaves the payload limit and tare blank and gives the same loaded count and occupied dimensions as that capture.

Progressive Fill builds blocks of cargo from the closed end toward the doors. Mixed Cargo Infill can use compatible gaps alongside those blocks and supported space above them. Group numbers guide the progression through the load. Adjacent groups can meet within a bounded transition, so the plan can use space near the boundary without putting every group in a separate compartment.

</section>

<section class="blog-content-section" markdown="1">

## Comparative results

Both plans accommodated all **878 units**. Table 2 compares the loaded quantities and the volume and mass they represent.

<div class="blog-table-wrap" tabindex="0" role="region" aria-labelledby="easycargo-results">
<table class="table table-sm table-striped mb-0">
  <caption id="easycargo-results" class="caption-top fw-bold text-dark">Table 2. Calculated and reported loading results</caption>
  <thead><tr><th scope="col">Measure</th><th scope="col">EasyCargo Report 003</th><th scope="col">KolliPack case</th></tr></thead>
  <tbody>
    <tr><th scope="row">Units loaded</th><td>878 (sum of report rows)</td><td>878 of 878</td></tr>
    <tr><th scope="row">Cargo volume (m³)</th><td>60.20</td><td>60.20</td></tr>
    <tr><th scope="row">Cargo mass (kg)</th><td>11,863.4</td><td>11,863.4</td></tr>
    <tr><th scope="row">Volume utilization</th><td>78% (reported)</td><td>77.23%</td></tr>
  </tbody>
</table>
</div>

The matching volume and mass follow from loading the same units. KolliPack divides the cargo volume (60.20 m³) by the internal container volume (77.95 m³), using the unrounded values to calculate 77.23%. The EasyCargo report gives a whole percentage and does not expose the denominator or rounding convention, so the two displayed percentages do not establish a difference in efficiency.

<figure class="blog-figure">
  <div class="row g-3 align-items-start">
    <div class="col-12 col-lg-6">
      <p class="fw-bold mb-1"><a href="static://img/blog/easycargo-40hc-mixed-cargo-case-study/easycargo-report-003-loading-view.webp" target="_blank" rel="noopener" aria-label="Open the full-size EasyCargo · Report 003 view">EasyCargo · Report 003</a></p>
      <img src="static://img/blog/easycargo-40hc-mixed-cargo-case-study/easycargo-report-003-loading-view.webp" alt="EasyCargo report crop with red microwave and green pipe blocks at the left end and differently arranged Madrid and Paris cargo toward the right." loading="lazy">
    </div>
    <div class="col-12 col-lg-6">
      <p class="fw-bold mb-1"><a href="static://img/blog/easycargo-40hc-mixed-cargo-case-study/kollipack-mixed-orientation-loading-view.webp" target="_blank" rel="noopener" aria-label="Open the full-size KolliPack · Mixed Cargo Infill view">KolliPack · Mixed Cargo Infill</a></p>
      <img src="static://img/blog/easycargo-40hc-mixed-cargo-case-study/kollipack-mixed-orientation-loading-view.webp" alt="KolliPack loading-view crop with Berlin labels P1 and P2 at the closed end, Madrid labels P3 and P4 in the middle, and Paris labels P5 to P7 toward the open doors." loading="lazy">
    </div>
  </div>
  <figcaption>Figure 3. Two application views of the 878-unit shipment. In the EasyCargo view, the red WH352 cartons and green pipes identify Berlin at the left end. In the KolliPack view, labels P1–P2 identify Berlin, P3–P4 Madrid and P5–P7 Paris. The views use different camera angles, scales and cargo colours.</figcaption>
</figure>

</section>

<section class="blog-content-section" markdown="1">

## Discussion

Figure 3 shows how the same types can be distributed differently. In the EasyCargo report, green pipe cargo appears in two visible concentrations around the red WH352 microwave blocks. The KolliPack view shows blue pipes visible in a concentrated band alongside the orange WH352 block at the closed end. Toward the doors, the KolliPack view shows the purple stove units using several positions near and above the green RW 230 microwave block.

The KolliPack placements give a closer look at the boundary between Madrid and Paris. The Madrid WD102 microwaves extend to **8.66 m** from the closed end. The Paris BD53V freezers begin at **8.29 m**. The groups therefore share **0.37 m of container length**, with units at different lateral positions or heights. That shared span is compatible with bounded infill at a group transition. The placements share lengthwise coordinates while remaining separate in three dimensions.

<figure class="blog-figure">
  <picture>
    <source media="(max-width: 600px)" srcset="static://img/blog/easycargo-40hc-mixed-cargo-case-study/kollipack-loading-groups-mobile.webp">
    <img src="static://img/blog/easycargo-40hc-mixed-cargo-case-study/kollipack-loading-groups.webp" alt="KolliPack top view and lengthwise group spans, showing Madrid ending at 8.66 metres and Paris beginning at 8.29 metres." loading="lazy">
  </picture>
  <figcaption>Figure 4. Group extents measured from the closed end using the KolliPack placements. The bars measure lengthwise ranges across all positions and heights in each group.</figcaption>
</figure>

For the first stop, the shared span tells the team where to check whether the Paris freezers can be removed without moving Madrid cargo. That depends on the approach through the doors, available handling equipment and access to each unit. The two captured views cannot establish the unloading path or compare handling effort.

</section>

<section class="blog-content-section" markdown="1">

## Conclusion

Different loading approaches accommodated this same mixed-cargo shipment in one high-cube container and produced different spatial arrangements. The experiment establishes a matched loaded manifest and a distinct KolliPack geometry under the stated inputs. It leaves the precise EasyCargo settings and practical unloading, stack strength, weight distribution and securing for separate verification.

<a href="/free-container-loading-calculator/?case=easycargo-40hc-mixed-cargo-benchmark" target="_blank" rel="noopener">Open the prefilled case in KolliPack</a> to rotate the result and inspect the Madrid–Paris transition. To explore the effect of orientation, keep the microwave rows upright and compare the new layout and loaded count.

</section>
