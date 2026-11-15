+++
schema_version = 1
status = "published"
title = "Why Empty Container Space Doesn’t Always Mean More Cargo Will Fit"
slug = "why-empty-container-space-doesnt-fit-more-cargo"
excerpt = "A mixed-carton load shows why empty container space can be hard to use and what to check before approving a load plan or buying loading software."
seo_title = "Why Container Volume Doesn’t Equal Loadable Capacity"
meta_description = "See why empty container space can leave cartons unpacked, how loading constraints shape usable capacity, and what to check when evaluating loading software."
article_type = "engineering_deep_dive"
subtitle = "How carton geometry, handling rules and loading order shape the capacity you can use."
author = "Alejandro Ramírez"
category = "Transport Loading"
read_time = "8 min read"
published_at = 2026-11-16
updated_at = 2026-11-16
thumbnail = "img/blog/why-empty-container-space-doesnt-fit-more-cargo/thumbnail-v1.webp"
thumbnail_alt = "Open shipping container holding mixed cartons with one carton outside"
primary_keyword = "container loading space utilization"
tags = ["container loading", "3D bin packing", "load planning"]
related_tools = ["transport-container"]
flow_steps = [{icon = "bi-box-seam", label = "Mixed cartons"}, {icon = "bi-truck", label = "20-foot container"}]
takeaways = ["Use volume and payload to screen the shipment, then check what fits by item.", "Compare plans with the same handling rules and delivery requirements.", "Validate access, stack strength and securing with the people who will load and unload the cargo."]
canonical_path = "/blog/why-empty-container-space-doesnt-fit-more-cargo/"
og_image = "img/blog/why-empty-container-space-doesnt-fit-more-cargo/thumbnail-v1.webp"

[cta]
label = "Run the 20-foot case in KolliPack"
url = "/free-container-loading-calculator/?case=20ft-upright-mixed-cartons"
+++

When planning a shipment, a useful first check is to add up the carton volumes and confirm the total weight is within the container’s limit. If both figures look comfortable, it is reasonable to ask whether the whole order can go in one container. With mixed carton sizes and a required loading sequence, answering that question takes a load plan.

In a calculated 20-foot load, KolliPack placed 119 of 121 cartons while leaving nearly 30% of the container’s internal volume empty. The two unplaced cartons were ordinary cubes. The space left over was spread around the load, and the positions available to those last cartons depended on what had already been loaded.

For a planner deciding whether to rework the arrangement or book more space, the useful question is where each remaining carton could go and how the crew would get it there.

## Three ways to measure container capacity

**Internal volume** is the geometric space inside the container. For a rectangular interior, multiply the internal length, width and height. Use the actual equipment dimensions for planning. Door openings, protrusions and any clearance you reserve for handling can further limit the space you can use.

**Cargo volume utilization** tells you how much of the internal volume the loaded cartons occupy. Use their outside dimensions and count the cartons that are actually in the plan.

**Volume utilization (%) = (loaded cargo volume ÷ container internal volume) × 100**

**Feasible loading capacity** asks how many of the requested cartons can be arranged under the stated rules. For a mixed order, check that count by item. A shipment can have a high overall count and still be short of the particular item needed to complete an order.

Weight is a separate capacity check. **Payload** is the weight the container is allowed to carry. Compare the loaded cargo weight with that limit and account for other weight carried as applicable, such as pallets or securing materials. A light load can use up its practical placements long before it reaches the weight limit. A dense load can reach the weight limit while leaving open space.

## What makes mixed-cargo loading difficult?

Packing different sizes into one container is a practical example of **three-dimensional bin packing**. Each carton occupies a particular length, width and height, and the arrangement of one carton changes the positions available to the next. A gap beside one stack can be too narrow, while the space over another can be too low. Cartons farther inside can limit how deep an opening goes. In Figure 1, moving the front stacks changes where the space is available while the cartons at the back stay in place.

<figure class="blog-figure">
  <picture>
    <source media="(max-width: 600px)" srcset="static://img/blog/why-empty-container-space-doesnt-fit-more-cargo/mixed-carton-gap-fit-mobile.webp">
    <img src="static://img/blog/why-empty-container-space-doesnt-fit-more-cargo/mixed-carton-gap-fit.webp" alt="Two open container cutaways show cartons at the back and uneven front stacks. In the first, the blue outline overlaps a front stack. In the second, the front stacks sit against one wall and the blue carton fits beside them, ahead of the rear row." loading="lazy">
  </picture>
  <figcaption>Figure 1. Conceptual cutaway of the same mixed cartons in two layouts. On the left, the dashed blue outline hits the front stack. The side gaps are too narrow and the opening above the shorter stack is too shallow in height. On the right, moving the front stacks beside one wall opens room in front of the rear cargo.</figcaption>
</figure>

**Orientation and support** narrow the options further. A carton that must stay upright can turn on its base and exchange its length and width. Its height stays fixed. A suitable opening above another carton also needs a base that can support the load. A carton marked stackable in a model may accept cargo on top. The real package still has a limit on the weight it can carry.

**Loading sequence** affects when space is available. The worked example uses three groups. The mix of footprints and heights placed for earlier groups shapes the openings the last group can use. In an operation that unloads through the rear doors at several stops, the planner also has to consider which group can be reached first. A tightly packed arrangement can create extra work if the crew has to move later-stop freight to reach the early-stop cartons.

Geometry can establish that the cartons fit within the dimensions and rules entered for the calculation. The crew still has to be able to build, secure and unload the arrangement.

## How loading software searches for an arrangement

A loading tool starts with the container, a list of cargo units and the rules supplied by the planner. For each carton, it can consider the orientations that are allowed and test positions on the floor or on supported surfaces. Each placement must stay within the container without overlapping another carton. Rules such as a required group order or a top that must stay clear can eliminate otherwise possible positions.

The tool can then try a different order, turn a carton on its base, or revisit spaces next to or above a stack. Each choice changes the openings left for the rest of the shipment. An arrangement might be scored by the number of cartons placed, the amount of volume used or how well it serves a shipment priority. A planner who needs to ship a complete order should check the item counts even when volume is the main score.

One way to keep the search practical is to use a **heuristic**, a method that quickly tests promising choices. For example, it might place several similar cartons together, then look for smaller cartons that can use the openings beside them. The resulting plan shows what the search found under the selected settings. A different search, or moving cartons already in place, can produce another plan.

## A worked example with 121 cartons

The test used a 20-foot container with internal dimensions of **5,758 × 2,352 × 2,385 mm** and a payload limit of **28,200 kg**. The manifest contained nine carton types across three loading groups. Every carton weighed 10 kg, could support other cartons in the model and could turn on its base while staying upright. The variety of heights and footprints makes the last group a useful test of how much of the remaining space can be used.

<figure class="blog-figure">
<p class="d-md-none small">Scroll the table to see all columns.</p>
<div class="blog-table-wrap" tabindex="0" role="region" aria-label="Carton dimensions, loading groups and handling rules">
<table class="table table-sm">
<thead>
<tr>
<th>Group</th>
<th>Carton / 3D label</th>
<th class="text-center">Color</th>
<th>L × W × H (mm)</th>
<th>Stackable</th>
<th>Upright only</th>
<th class="text-end">Requested</th>
</tr>
</thead>
<tbody>
<tr>
<td>1</td>
<td class="text-nowrap">A / P1</td>
<td class="text-center"><span aria-hidden="true" style="display:inline-block;width:1rem;height:1rem;background-color:#f59e0b;border:1px solid rgba(0,0,0,.2);vertical-align:middle"></span></td>
<td class="text-nowrap">500 × 500 × 600</td>
<td>Yes</td>
<td>Yes</td>
<td class="text-end">12</td>
</tr>
<tr>
<td>1</td>
<td class="text-nowrap">B / P2</td>
<td class="text-center"><span aria-hidden="true" style="display:inline-block;width:1rem;height:1rem;background-color:#2563eb;border:1px solid rgba(0,0,0,.2);vertical-align:middle"></span></td>
<td class="text-nowrap">500 × 600 × 500</td>
<td>Yes</td>
<td>Yes</td>
<td class="text-end">14</td>
</tr>
<tr>
<td>1</td>
<td class="text-nowrap">C / P3</td>
<td class="text-center"><span aria-hidden="true" style="display:inline-block;width:1rem;height:1rem;background-color:#0d9488;border:1px solid rgba(0,0,0,.2);vertical-align:middle"></span></td>
<td class="text-nowrap">500 × 500 × 500</td>
<td>Yes</td>
<td>Yes</td>
<td class="text-end">14</td>
</tr>
<tr>
<td>2</td>
<td class="text-nowrap">D / P4</td>
<td class="text-center"><span aria-hidden="true" style="display:inline-block;width:1rem;height:1rem;background-color:#dc2626;border:1px solid rgba(0,0,0,.2);vertical-align:middle"></span></td>
<td class="text-nowrap">600 × 700 × 600</td>
<td>Yes</td>
<td>Yes</td>
<td class="text-end">14</td>
</tr>
<tr>
<td>2</td>
<td class="text-nowrap">E / P5</td>
<td class="text-center"><span aria-hidden="true" style="display:inline-block;width:1rem;height:1rem;background-color:#7c3aed;border:1px solid rgba(0,0,0,.2);vertical-align:middle"></span></td>
<td class="text-nowrap">700 × 500 × 500</td>
<td>Yes</td>
<td>Yes</td>
<td class="text-end">14</td>
</tr>
<tr>
<td>2</td>
<td class="text-nowrap">H / P6</td>
<td class="text-center"><span aria-hidden="true" style="display:inline-block;width:1rem;height:1rem;background-color:#65a30d;border:1px solid rgba(0,0,0,.2);vertical-align:middle"></span></td>
<td class="text-nowrap">700 × 700 × 700</td>
<td>Yes</td>
<td>Yes</td>
<td class="text-end">10</td>
</tr>
<tr>
<td>3</td>
<td class="text-nowrap">F / P7</td>
<td class="text-center"><span aria-hidden="true" style="display:inline-block;width:1rem;height:1rem;background-color:#ea580c;border:1px solid rgba(0,0,0,.2);vertical-align:middle"></span></td>
<td class="text-nowrap">600 × 600 × 600</td>
<td>Yes</td>
<td>Yes</td>
<td class="text-end">14</td>
</tr>
<tr>
<td>3</td>
<td class="text-nowrap">G / P8</td>
<td class="text-center"><span aria-hidden="true" style="display:inline-block;width:1rem;height:1rem;background-color:#0891b2;border:1px solid rgba(0,0,0,.2);vertical-align:middle"></span></td>
<td class="text-nowrap">500 × 500 × 500</td>
<td>Yes</td>
<td>Yes</td>
<td class="text-end">14</td>
</tr>
<tr>
<td>3</td>
<td class="text-nowrap">I / P9</td>
<td class="text-center"><span aria-hidden="true" style="display:inline-block;width:1rem;height:1rem;background-color:#f59e0b;border:1px solid rgba(0,0,0,.2);vertical-align:middle"></span></td>
<td class="text-nowrap">600 × 600 × 600</td>
<td>Yes</td>
<td>Yes</td>
<td class="text-end">15</td>
</tr>
</tbody>
</table>
</div>
<figcaption>Figure 2. Case inputs in loading-group order. Each row gives the carton dimensions, handling rules and requested quantity. The color squares and P-labels match the calculated view in Figure 3.</figcaption>
</figure>

With its Progressive Fill – Mixed Cargo Infill mode, KolliPack placed **119 of 121 cartons**, or **98.35%** of the request. The placed cartons occupied **22.640 m³**, for **70.09%** volume utilization. The loaded weight was **1,190 kg**, or **4.22%** of the payload limit.

<figure class="blog-figure">
  <img src="static://img/blog/why-empty-container-space-doesnt-fit-more-cargo/kollipack-loading-view.webp" alt="KolliPack loading view of the calculated mixed-carton load in a 20-foot container" loading="lazy">
  <figcaption>Figure 3. KolliPack’s calculated arrangement. The labels match Figure 2. Item I is P9 near the doors, with 13 of its 15 cartons placed. <a href="static://img/blog/why-empty-container-space-doesnt-fit-more-cargo/kollipack-loading-view.webp">Open the full-size loading view</a>.</figcaption>
</figure>

The public EasyCargo example supplied the manifest and shows **116 of 121** cartons placed. The case owner confirmed the same upright and stackable settings. KolliPack placed three more in the arrangements shown. Both left some Item I cartons behind, and the detailed EasyCargo group-handling and solver settings are unspecified. [Original EasyCargo load-plan figure](https://www.easycargo3d.com/wp-content/uploads/2025/05/How-to-calculate-container-volume_loaded-cargo.jpg)

In the KolliPack plan, the two remaining 600 mm cubes total **0.432 m³** against about **9.660 m³** of unused internal volume. At the tallest point, there was just 85 mm of clearance below the roof. That air contributes to the unused total and offers too little height for either cube. A placement elsewhere would still need a full cube of clear space, a supporting surface and a way in. The run establishes a shortfall in this arrangement. Whether a different arrangement can place all 121 remains open.

## What the warehouse needs from a load plan

Walk through the proposed plan in the order the crew will use it. Check that the cartons and handling equipment can pass through the door, reach each position and move clear again. For a multi-stop shipment, check the unloading order as well. The test is whether the crew can reach the goods due at each stop without moving freight that should stay on board.

Then check how the load will behave during transport. A supported position in the model needs real package strength underneath it. Ask what weight can be placed on each stack and verify how that weight is distributed across the floor. Allow room for any blocking or restraints and confirm that the load can be secured for its route. Low payload utilization can still coexist with a concentrated load or with space that allows cargo to shift.

A load plan gives the team positions and quantities to work from. The organization still needs to confirm its equipment, packaging, securing method and handling process before releasing the shipment. The joint cargo transport guidance covers planning, packing and securing. [IMO/ILO/UNECE CTU Code](https://www.imo.org/en/ourwork/safety/pages/ctu-code.aspx)

## What to test before buying loading software

Start with a recurring shipment where an incomplete order, slow planning or extra handling has a measurable consequence. Use the same container, carton list, rules and delivery priorities in the trial as in your current process. Include ordinary shipments and a difficult mixed load, where the differences are easier to see.

- **Can it represent what you ship?** Enter the outside dimensions, weights and quantities for each item. Include the actual load units your business handles, such as cartons and pallets, and test any upright, stacking or group rules that matter.
- **Does it improve the decision you make?** Compare two valid plans and check which item quantities are left out, whether a full order can ship and whether the tool keeps delivery requirements in view. Ask which measure drives the ranking when two plans place different mixes of cargo.
- **Can the crew use the output?** Give the warehouse the same loading view or instructions it would receive on a normal shift. Ask the crew to walk through the plan and record where they need clarification, extra equipment or unplanned moves.

Measure results over several representative loads. Compare planning and revision time, orders shipped complete and the handling changes the crew actually needed. Agree in advance what improvement would justify changing the process. A single high utilization figure cannot answer that business question.

## From available volume to better loading decisions

The 20-foot case passed the volume and weight checks for the full manifest. The calculated arrangement still left two cartons behind. Before changing the booking, a planner can inspect the remaining item’s dimensions, compare placements under the same rules and ask the warehouse whether the proposed arrangement can be built and unloaded. If a workable alternative closes the shortfall, update the booking from the verified item counts. If the shortfall remains, use those counts to plan the overflow.

The three checks below carry over to other mixed shipments. To see how they work on this manifest, [open the prepopulated 20-foot case in KolliPack](/free-container-loading-calculator/?case=20ft-upright-mixed-cartons). Find Item I by its P9 label and compare the item counts after changing the loading strategy with the carton settings held fixed.
