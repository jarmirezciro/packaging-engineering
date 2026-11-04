+++
schema_version = 1
status = "published"
title = "Same Pallet Capacity, Different Design Thinking: KolliPack and CapePack in Three Bottle Cases"
slug = "capepack-kollipack-bottle-case-pallet-benchmark"
subtitle = "Three bottle-to-pallet cases, matched geometric quantities and different engineering workflows."
excerpt = "Three bottle-to-pallet cases reproduce CapePack capacities in KolliPack and show how product design, carton choice and overhang affect packaging decisions."
summary = "A three-case benchmark using one original CapePack reference screenshot, independently formatted comparison tables, and KolliPack carton and pallet evidence."
seo_title = "CapePack vs KolliPack: Three Bottle-to-Pallet Case Studies"
meta_description = "Three bottle-to-pallet benchmarks reproduce CapePack capacities in KolliPack. Explore carton design, product allowances, pallet overhang and workflow differences."
article_type = "demo_case_study"
author = "Alejandro Ramírez"
category = "Packaging Engineering"
read_time = "7 min read"
published_at = 2026-11-04
updated_at = 2026-11-04
thumbnail = "img/blog/capepack-kollipack-bottle-case-pallet-benchmark/thumbnail-approved.png"
featured_image = "img/blog/capepack-kollipack-bottle-case-pallet-benchmark/thumbnail-approved.png"
thumbnail_alt = "KolliLabs thumbnail showing a realistic beverage bottle, open corrugated carton and palletized cartons beside the words 3 Cases — Matched Results"
primary_keyword = "CapePack KolliPack bottle pallet benchmark"
tags = ["CapePack", "KolliPack", "bottle packaging", "case design", "palletization", "packaging benchmark"]
related_articles = ["cartons-per-pallet-case-design-exploration", "capepack-parameter-fine-tuning", "kollipack-vs-tops-pro-palletization-benchmark"]
related_tools = ["packaging-flow", "container-selection", "palletization"]
canonical_path = "/blog/capepack-kollipack-bottle-case-pallet-benchmark/"
og_image = "img/blog/capepack-kollipack-bottle-case-pallet-benchmark/thumbnail-approved.png"
takeaways = ["KolliPack reproduced the observed carton arrangements and pallet capacities in three supplied CapePack examples.", "The featured CapePack Design Group workflow can explore product-size changes; KolliPack connects fixed-product carton alternatives to pallet results.", "Product allowances and pallet overhang can change geometric feasibility but never replace physical validation."]

[[flow_steps]]
icon = "bi-cup-straw"
label = "Round bottle"

[[flow_steps]]
icon = "bi-box-seam"
label = "RSC carton"

[[flow_steps]]
icon = "bi-grid-3x3-gap"
label = "Pallet"

[cta]
label = "Explore Packaging Flow in KolliPack"
url = "/full-packaging/"
new_tab = true
+++

# Same Pallet Capacity, Different Design Thinking: KolliPack and CapePack in Three Bottle Cases

**Three bottle configurations. Three matching pallet capacities: 1,008, 1,080 and 960 bottles.** In all three comparisons, KolliPack reproduced the visible number of cartons per layer and pallet layers from a CapePack demonstration.

The result matters because a packaging decision does not end at the bottle or carton. The same engineering question travels through the complete chain: **how should a product be packed so that the final shipping unit works?** The comparison also highlights two different ways to approach that question—especially when product dimensions are still negotiable.

*Scope: These are three screenshot-supported geometric comparisons, not a controlled head-to-head assessment of either software's optimization quality, usability or complete capabilities. Input allowances, pallet dimensions and weight restrictions were not identical in every captured run. KolliLabs and KolliPack are independent of Esko and CapePack.*

## From bottle to shipping carton to pallet

We examined three variations of a round beverage bottle, each packed upright into a regular slotted corrugated shipping carton (RSC). The cases were then evaluated on a **48 × 40 in pallet**, with a **50 in maximum loaded height** in the benchmark setup.

<figure class="blog-figure">
  <img src="static://img/blog/capepack-kollipack-bottle-case-pallet-benchmark/01_packaging_scenario_setup_revised.webp" alt="Conceptual sequence from round beverage bottle to RSC carton and palletized load" />
  <figcaption>Figure 1. The same three-stage packaging chain is evaluated for different bottle sizes and carton quantities. The illustration is conceptual, not a specific packing result.</figcaption>
</figure>

### What went into the calculations?

<div class="blog-table-wrap" markdown="1">

| Case | CapePack bottle diameter × height | KolliPack bottle diameter × height | Bottles per carton | Arrangement |
|---|---|---|---:|---|
| A | 2.491 × 10.00 in | 2.49 × 10.00 in | **24** | 6 × 2 × 2 |
| B | 2.523 × 9.75 in | 2.52 × 9.75 in | **15** | 5 × 3 × 1 |
| C | 2.460 × 10.25 in | 2.46 × 10.25 in | **20** | 5 × 4 × 1 |

</div>

All configurations use approximately **0.16 in corrugated thickness**. The source demonstration also uses **0.12 in bulge allowance** in bottle diameter and height. In the captured KolliPack calculations, length and width allowances were 0.12 in but the height allowance was left at zero. We return to this difference below.

Rather than reproduce several CapePack application windows, we retain **one original reference frame** from its 15-bottle result. The other case inputs and results are summarized in our own tables, with KolliPack's actual output shown separately.

<figure class="blog-figure">
  <img src="static://img/blog/capepack-kollipack-bottle-case-pallet-benchmark/02_capepack_single_reference.webp" alt="Original CapePack demonstration frame showing the 15-bottle carton and a 72-carton pallet load" />
  <figcaption>Figure 2. Original CapePack demonstration frame, shown solely as a source reference for technical comparison. It reports 15 bottles per carton, 72 cartons per pallet and 1,080 bottles per load. Source video identity and rights to reproduce this frame require confirmation before publication.</figcaption>
</figure>

## Three matching pallet quantities

<div class="blog-table-wrap" markdown="1">

| Configuration | Cartons per layer | Pallet layers | CapePack cartons / pallet | KolliPack cartons / pallet | Bottles / pallet, both tools |
|---|---:|---:|---:|---:|---:|
| 24 bottles / carton | 21 | 2 | 42 | 42 | **1,008** |
| 15 bottles / carton | 18 | 4 | 72 | 72 | **1,080** |
| 20 bottles / carton | 12 | 4 | 48 | 48 | **960** |

</div>

### Case A — 24 bottles in two tiers

A **6 × 2 × 2 arrangement** produces a comparatively tall carton. Only two carton layers fit under the pallet height limit, but each layer holds 21 cartons. Both applications reach **1,008 bottles per pallet**.

<figure class="blog-figure">
  <img src="static://img/blog/capepack-kollipack-bottle-case-pallet-benchmark/03_kollipack_24_bottles.webp" alt="Real KolliPack 24-bottle carton design and 42-carton pallet arrangement" />
  <figcaption>Figure 3. KolliPack's actual carton and pallet visualizations: 24 bottles per carton, 42 cartons per pallet. The two-tier bottle arrangement would require suitable physical support and protection checks.</figcaption>
</figure>

### Case B — 15 bottles, four pallet layers

Here, a **5 × 3 × 1 carton arrangement** is shorter and permits four layers. Both tools report **18 cartons per layer**, reaching **1,080 bottles per pallet**. It is the largest calculated quantity in these three observed configurations, although the bottle dimensions differ across cases.

<figure class="blog-figure">
  <img src="static://img/blog/capepack-kollipack-bottle-case-pallet-benchmark/04_kollipack_15_bottles.webp" alt="Real KolliPack 15-bottle carton design and four-layer, 72-carton pallet visualization" />
  <figcaption>Figure 4. The KolliPack reproduction of the 15-bottle case. The captured run permits some pallet overhang; its overhang inputs were not identical to the CapePack capture.</figcaption>
</figure>

### Case C — 20 bottles, no permitted overhang

With **5 × 4 × 1 bottles per carton**, both programs show **12 cartons per layer and four layers**, or **960 bottles per pallet**. KolliPack produced its result with **zero permitted pallet overhang**.

<figure class="blog-figure">
  <img src="static://img/blog/capepack-kollipack-bottle-case-pallet-benchmark/05_kollipack_20_bottles.webp" alt="Real KolliPack 20-bottle carton design and 48-carton palletization result" />
  <figcaption>Figure 5. A 20-bottle configuration matching the observed CapePack layer count and pallet quantity, with no overhang allowed in the KolliPack calculation.</figcaption>
</figure>

The most useful observation is not that one carton quantity wins. **Bigger cases do not automatically mean more bottles per pallet.** The relative carton proportions determine how many fit in each layer and how many layers can be stacked. Because the source configurations vary in more than one input, these three totals are comparisons of reproduced examples—not a controlled experiment isolating case quantity.

## Different approaches to packaging optimization

The CapePack demonstration explores a question that is especially relevant during product development: **what if the bottle itself can change?** In the featured **Design Group / Vary** workflow, the engineer defines allowable primary-product dimensional variations and evaluates how those decisions affect case geometry and palletization. CapePack also supports fixed-size product workflows; resizing is not its only approach.

KolliPack addresses a different starting point in this study: **the bottle dimensions have been specified; which shipping-carton design works best downstream?** The engineer enters the bottle, quantity and permitted orientations in **Container Selection**, generates carton arrangements, then uses **Palletization** or the connected **Packaging Flow** to examine their final pallet performance.

<figure class="blog-figure">
  <img src="static://img/blog/capepack-kollipack-bottle-case-pallet-benchmark/06_optimization_approaches.webp" alt="Original explanatory diagram comparing CapePack Design Group product-size exploration with KolliPack fixed-product carton alternatives and pallet results" />
  <figcaption>Figure 6. Two workflows emphasized in this study. The diagram explains their starting design questions, not the complete capabilities of either platform.</figcaption>
</figure>

**Modularity is a central part of KolliPack's design.** An engineer can use the Container Selection and Palletization tools independently, or connect them through Packaging Flow. The browser-based interface combines editable engineering inputs, alternative tables and interactive 3D views. Its *Optimize final capacity* feature makes the effect of a carton choice visible at pallet level without requiring a separate manual calculation for every alternative.

This describes KolliPack's interface and workflow rather than proving that it is objectively easier to use than CapePack.

## Packaging software matters at different stages of product development

**During product design**, dimensions may still be flexible. Small changes in bottle diameter or height could improve shipping efficiency. A tool that explores permissible product variation can help R&D, manufacturing and packaging engineering understand those implications *before* specifications become fixed. Any proposed change must still satisfy bottle volume, performance, production and branding requirements.

**During industrialization**, product drawings meet manufacturing reality. Bottles may vary within tolerances, deform or require insertion clearance. The CapePack example uses a **bulge allowance**. KolliPack's **Product Dimensional Allowance** provides separate additional space along length, width and height for packing calculations while keeping the nominal 3D product geometry unchanged.

The difference is tangible in this benchmark: the KolliPack captures omitted the 0.12 in height allowance used in the CapePack setup. That accounts for the main difference in carton heights while leaving the reproduced pallet counts unchanged. These allowances should reflect the actual product and packing process, not be added indiscriminately or double-counted.

**During established production**, changing the primary package may no longer be attractive. Optimization then shifts toward case quantity, carton geometry, corrugated construction, pallet pattern and loading restrictions. This is the part of the lifecycle where KolliPack's modular fixed-product workflow is particularly relevant.

## Pallet overhang: opportunity and trade-off

Pallet overhang occurs when cartons extend beyond the supporting pallet deck. In the **15-bottle CapePack result**, the load footprint is larger than the nominal 48 × 40 in pallet. Its reported pallet area usage therefore exceeds 100%, without necessarily exceeding the software's permitted overhang restriction.

**The advantage** is practical: allowing a modest extension can make an otherwise excluded carton pattern fit, potentially carrying more product per pallet. **The drawback** is equally real: unsupported carton corners and edges can lose compression support, while protruding loads may be more vulnerable to contact, shifting and handling damage. Not all supply chains or customers permit overhang.

<figure class="blog-figure">
  <img src="static://img/blog/capepack-kollipack-bottle-case-pallet-benchmark/08_allowance_and_pallet_overhang_explained.png" alt="Approved conceptual illustration of product dimensional allowance, pallet overhang, and support and stability considerations" />
  <figcaption>Figure 7. Dimensional allowance changes reserved space around the product; overhang changes how far the palletized load may extend beyond its deck. The illustration is conceptual.</figcaption>
</figure>

When overhang is an available option, comparing **zero-overhang and permitted-overhang** solutions can expose the capacity benefit. The final decision still needs checks for carton strength, product protection, stability, equipment clearance and customer requirements. The software's geometric result is a design candidate, not a certified transport load.

## What these three cases demonstrate

KolliPack reproduced the **carton arrangements, layer counts and final geometric capacities** visible in three CapePack bottle examples. One original CapePack screenshot provides a reference to the demonstrated source; the rest of the comparison uses independently formatted data and actual KolliPack results.

The results do **not** establish equal optimization coverage, identical search methods, or physical stacking performance. The captured settings were not fully matched: for example, one KolliPack run used a different product weight, some height allowances were omitted, and overhang/pallet-height choices varied. The comparison is strongest as a demonstration of reproduced packaging geometry.

The wider lesson is that packaging design changes over a product's life. During development, **the product can be part of the design freedom**. Later, **the product is often fixed and the packaging system becomes the optimization opportunity**. Tools that reveal consequences from bottle to carton to pallet make that trade-off clearer.

**Explore [KolliPack's Packaging Flow](/full-packaging/)** to see how container designs and pallet layouts can be evaluated as connected decisions.

*Source and independence note: The CapePack result shown in Figure 2 comes from a supplied public-demonstration capture. The exact original video URL, publisher details and image-reuse basis must be documented before publication. [Esko's Cape Pack resources](https://innovation.esko.com/en/esko/home/products/cape-pack/resources) describe the product's design and palletization workflows but are not a substitute for identifying the precise source footage. KolliLabs/KolliPack is independent of, and not endorsed by, Esko.*
