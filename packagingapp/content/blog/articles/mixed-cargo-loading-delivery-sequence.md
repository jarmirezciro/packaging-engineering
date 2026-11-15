+++
schema_version = 1
status = "draft"
title = "How Orientation, Stacking and Stop Order Shape a Mixed-Cargo Load"
slug = "mixed-cargo-loading-delivery-sequence"
subtitle = "Seven cargo types, two delivery stops and one 48-ft semitrailer."
excerpt = "A 133-unit trailer load shows how permitted orientations, stackable surfaces and stop order shape the space a planner can actually use."
seo_title = "Mixed-Cargo Loading and Delivery Sequence | KolliPack"
meta_description = "Follow a 133-unit trailer case to see how orientation, stacking and unloading order affect mixed-cargo loading and the choice of packing strategy."
article_type = "engineering_deep_dive"
author = "Alejandro Ramírez"
category = "Transport Loading"
hero_icon = "bi-truck"
published_at = 2026-11-15
updated_at = 2026-11-15
thumbnail = "img/blog/mixed-cargo-loading-delivery-sequence/thumbnail-v1.webp"
thumbnail_alt = "Semitrailer with cargo visible through the rear doors and the headline 133 units, two stops"
primary_keyword = "mixed-cargo loading and delivery sequence"
tags = ["mixed cargo loading", "delivery sequence", "stacking", "transport loading"]
related_tools = ["transport-container"]
canonical_path = "/blog/mixed-cargo-loading-delivery-sequence/"
og_image = "img/blog/mixed-cargo-loading-delivery-sequence/thumbnail-v1.webp"
flow_steps = [{icon = "bi-box-seam", label = "Mixed load units"}, {icon = "bi-truck", label = "Rear-unload semitrailer"}]
takeaways = ["Record the faces each product may rest on and whether its top may support cargo.", "Use the unloading order to assign loading groups before comparing volume utilization."]

[cta]
label = "Open the 133-unit trailer case"
url = "/free-container-loading-calculator/?case=48ft-semitrailer-two-stop-mixed-cargo"
new_tab = true
+++

<section class="blog-content-section" markdown="1">

At the first delivery stop, the crew opens the rear doors. Everything due there has to come out while the second stop’s cargo stays on board. During loading, the planner is working through a different set of questions. Which units can travel on their sides? Which can carry another unit? If one stack fills the trailer’s height, can the space beside it still take the next product?

This worked example uses **133 units across seven product types** in a nominal 48-ft semitrailer. The usable interior is **566.9 × 98.5 × 108 in** (length × width × height). We model two stops and enter fixed quantities for every product.

<figure class="blog-figure">
  <picture>
    <source media="(max-width: 600px)" srcset="static://img/blog/mixed-cargo-loading-delivery-sequence/mixed-cargo-case-setup-mobile.webp">
    <img src="static://img/blog/mixed-cargo-loading-delivery-sequence/mixed-cargo-case-setup.webp" alt="Different cargo shapes share one 48-ft semitrailer, with two deliveries through its rear doors." loading="lazy">
  </picture>
  <figcaption>Figure 1. Conceptual setup for seven cargo types sharing one rear-unload trailer and two delivery stops.</figcaption>
</figure>

A multi-stop loading illustration from EasyCargo inspired the case. We developed an independent two-stop configuration using the inputs below. [Original EasyCargo illustration and article](https://www.easycargo3d.com/sv/blog/ssme-logistics-optimize-cargo-transport/)

</section>

<section class="blog-content-section" markdown="1">

## Start with what each product can do

An orientation rule determines which face a unit may rest on. Each allowed base can also turn a quarter turn on the floor. C and D must stay upright. A can also travel with its entered length vertical. B and E need clear tops, so they may sit on suitable support but cannot support other cargo in the model.

<figure class="blog-figure">
  <picture>
    <source media="(max-width: 600px)" srcset="static://img/blog/mixed-cargo-loading-delivery-sequence/loading-constraints-mobile.webp">
    <img src="static://img/blog/mixed-cargo-loading-delivery-sequence/loading-constraints.webp" alt="Orientation arrows show R1 length, R2 width and R3 height vertical. Two stacks show when a top can support other cargo. A trailer schematic shows A–C at the nose for stop 2, and D–G at the rear doors for stop 1." loading="lazy">
  </picture>
  <figcaption>Figure 2. Three constraints shape the load. Allowed orientations set the base, stackability determines what can rest on it, and delivery order determines where each group belongs.</figcaption>
</figure>

<p class="d-md-none small text-muted">Scroll the manifest sideways to see the orientation and stacking rules.</p>
<div class="blog-table-wrap" tabindex="0" role="region" aria-label="Cargo manifest and permitted orientations">
<table class="table table-sm table-striped mb-0">
  <thead><tr><th scope="col">Product</th><th scope="col">Size (in)</th><th scope="col">Units</th><th scope="col">lb per unit</th><th scope="col">Allowed</th><th scope="col">Stackable?</th></tr></thead>
  <tbody>
    <tr><th scope="row">A</th><td class="text-nowrap">15.75 × 55.15 × 63</td><td>30</td><td>88.11</td><td class="text-nowrap">R1, R3</td><td>Yes</td></tr>
    <tr><th scope="row">B</th><td class="text-nowrap">63 × 23.6 × 39.4</td><td>17</td><td>191.93</td><td class="text-nowrap">R1, R2, R3</td><td>No</td></tr>
    <tr><th scope="row">C</th><td class="text-nowrap">23.6 × 17.7 × 51.2</td><td>16</td><td>1,198.76</td><td class="text-nowrap">R3</td><td>Yes</td></tr>
    <tr><th scope="row">D</th><td class="text-nowrap">31.5 × 47.2 × 15.7</td><td>48</td><td>11.02</td><td class="text-nowrap">R3</td><td>Yes</td></tr>
    <tr><th scope="row">E</th><td class="text-nowrap">47.2 × 47.2 × 21.7</td><td>14</td><td>1,375.67</td><td class="text-nowrap">R1, R2, R3</td><td>No</td></tr>
    <tr><th scope="row">F</th><td class="text-nowrap">47.2 × 47.2 × 21.7</td><td>4</td><td>661.38</td><td class="text-nowrap">R1, R2, R3</td><td>Yes</td></tr>
    <tr><th scope="row">G</th><td class="text-nowrap">47.2 × 47.2 × 21.7</td><td>4</td><td>165.35</td><td class="text-nowrap">R1, R2, R3</td><td>Yes</td></tr>
  </tbody>
</table>
</div>

Five A units in line give the B tier just **0.15 in** of extra support length. Reducing A’s two shorter dimensions by **0.05 in** each prevented that exact fit. In the rerun, the planner found a different layout and placed **127 units**, leaving six D units out. A separate rerun with only A’s upright orientation allowed placed **115**, leaving 18 D units out. All A units sit upright in the full-load plan. The reruns show why it pays to use measured dimensions and actual handling restrictions. One input can change the layout for cargo at the other end of the trailer.

</section>

<section class="blog-content-section" markdown="1">

## Work backward from the rear doors

Assign the last delivery to the group that loads first and sits deepest. In Figure 2, A–C are loading group 1 and D–G are loading group 3. Those identifiers track the order in which the planner fills the trailer. On the route, the door-side group comes out first. The calculated boundary between the groups is **311.15 in from the nose**. Check that the crew can work through each group with the intended equipment and securing plan.

</section>

<section class="blog-content-section" markdown="1">

## Use the space above and beside existing blocks

A gap is usable when the next unit fits in an allowed orientation, has a supported base and belongs where it can be unloaded. Headroom above a clear, stackable surface can be particularly valuable because it can take cargo without using more floor length.

<figure class="blog-figure">
  <p class="fw-semibold mb-2 text-center">133 of 133 units loaded</p>
  <picture>
    <source media="(max-width: 600px)" srcset="static://img/blog/mixed-cargo-loading-delivery-sequence/progressive-infill-product-legend-mobile.webp">
    <img src="static://img/blog/mixed-cargo-loading-delivery-sequence/progressive-infill-product-legend.webp" alt="KolliPack product legend with dimensions in inches and matched loaded and planned quantities. P1 A 30 of 30, P2 B 17 of 17, P3 C 16 of 16, P4 D 48 of 48, P5 E 14 of 14, P6 F 4 of 4, P7 G 4 of 4." loading="lazy">
  </picture>
  <img src="static://img/blog/mixed-cargo-loading-delivery-sequence/progressive-infill-loading-view.webp" alt="KolliPack semitrailer loading view, with blue B on amber A at the nose, teal C in the middle, and purple E on red D near the rear doors beside green F and orange G." loading="lazy" width="768" height="392">
  <figcaption>Figure 3. The KolliPack product legend and calculated loading view. Group 1 ends at teal C. The door-side group starts where purple E rests on red D.</figcaption>
</figure>

The model places all **17 B units on A**. The two tiers reach **102.4 in** in the 108 in trailer. One B unit turns a quarter turn to complete the upper tier. B’s tops stay clear.

In the rear section, three layers of D support all **14 E units**. E turns so its shortest dimension runs along the trailer. F and G stack two high on the floor farther toward the doors. These placements use both supported space and floor space within the same delivery group.

</section>

<section class="blog-content-section" markdown="1">

## Choose the strategy that fits the route

**Balanced Spread** builds regular product blocks in a geometry-based order and treats the manifest as one group. **Progressive Fill** builds compact blocks from the nose toward the doors and applies the entered loading groups. Each has a **Mixed Cargo Infill** variant that looks for compatible placements beside blocks or above supported surfaces.

<div class="blog-table-wrap" tabindex="0" role="region" aria-label="KolliPack loading strategy results for the same manifest">
<table class="table table-sm table-striped mb-0">
  <thead><tr><th scope="col">KolliPack strategy</th><th scope="col">Placed (of 133)</th><th scope="col">Volume used</th></tr></thead>
  <tbody>
    <tr><th scope="row">Balanced Spread</th><td>55</td><td>50.15%</td></tr>
    <tr><th scope="row">Balanced Spread – Mixed Cargo Infill</th><td>133</td><td>85.62%</td></tr>
    <tr><th scope="row">Progressive Fill</th><td>67</td><td>52.62%</td></tr>
    <tr><th scope="row">Progressive Fill – Mixed Cargo Infill</th><td>133</td><td>85.62%</td></tr>
  </tbody>
</table>
</div>

**Progressive Fill – Mixed Cargo Infill is the preferred strategy here.** Both infill runs place the full manifest, using **84.619 m³** of the trailer’s **98.825 m³** interior. The same units occupy the same total volume in either run, so fill rate alone cannot distinguish the two. Progressive Fill applies the stop groups as a constraint. Balanced Spread is an option when the route allows cargo to be treated as one group.

The result is a geometric loading plan. The calculated cargo weight is **48,181.53 lb**. The case has no entered tare or payload limit, so payload utilization is unavailable. Before using the layout, check trailer and axle loads, package strength, door and equipment clearances, and cargo securing. Stackability permits support in the model. The operating team still needs to establish how much load each package can carry.

</section>

<section class="blog-content-section" markdown="1">

## When loading software is worth evaluating

Better use of space matters when cargo that would otherwise spill into another vehicle or departure can travel in the planned load. The delivery crew also needs a workable unloading order. Here, a baseline strategy would have left part of the manifest behind, while either infill strategy met the quantity target. Applying the stop order gives planners a better basis for deciding which layout to trial.

Dedicated software is worth a closer look when teams frequently plan mixed loads with varying products, stacking rules or delivery orders and spend significant time on manual trial and error. Test it on representative shipments. Track planning time, whether a feasible plan avoids an overflow load, and whether crews can load, secure and unload it as intended. Weigh those results against licensing, implementation and training costs. Occasional, simple shipments may be quick enough to plan manually.

</section>

<section class="blog-content-section" markdown="1">

## What the 133-unit case demonstrates

KolliPack accommodated the complete **133-unit manifest**. Progressive Fill – Mixed Cargo Infill used compatible spaces while keeping the first-stop cargo at the rear doors. The EasyCargo illustration assigns A to a different group from B and C. This case puts A–C in the same delivery group and uses A to support B. The two layouts illustrate different configurations, so their results cannot establish relative software performance.

Evaluate capacity, orientation, support and unloading order together. Loading software earns its place when the resulting plans help teams make better decisions about vehicle space, handling and delivery.

Open the same manifest and switch between the two infill modes or set A to R3 only. Inspect the layer above A and the cargo nearest the doors after each run. [Explore the 133-unit case in the free loading calculator](/free-container-loading-calculator/?case=48ft-semitrailer-two-stop-mixed-cargo){: target="_blank" rel="noopener"}

</section>
