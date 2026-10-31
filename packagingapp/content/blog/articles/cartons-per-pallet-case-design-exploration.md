+++
schema_version = 1
status = "published"
title = "Can KolliPack Match CapePack? From 216 to 240 Cartons per Pallet"
slug = "cartons-per-pallet-case-design-exploration"
subtitle = "A practical carton-to-case-to-pallet benchmark showing matching results, alternative case designs, and why visible design choices matter."
excerpt = "KolliPack matches CapePack's 216 and later 240 results in this documented case, then makes the geometry trade-off visible."
summary = "A bounded carton-to-case-to-pallet benchmark: reproduce the original 216-carton result, explore the 240-carton case geometry, and compare the visible evidence without making a universal vendor claim."
description = "Compare KolliPack and CapePack on 216 and 240 cartons per pallet, then inspect how two 12-carton RSC geometries change the pallet result."
seo_title = "KolliPack vs CapePack: 216 and 240 Cartons per Pallet"
meta_description = "Can KolliPack reproduce CapePack's carton-to-pallet results? Compare 216 and 240 cartons per pallet and see how shipping-case design changes capacity."
article_type = "demo_case_study"
author = "Alejandro Ramírez"
category = "Packaging Engineering"
read_time = "5 min read"
published_at = 2026-10-31
updated_at = 2026-10-31
hero_icon = "bi-boxes"
featured_image = "img/blog/cartons-per-pallet-case-design-exploration/thumbnail-v2.webp"
thumbnail = "img/blog/cartons-per-pallet-case-design-exploration/thumbnail-v2.webp"
thumbnail_alt = "Two palletized case layouts representing 216 and 240 cartons per pallet"
primary_keyword = "cartons per pallet case design"
tags = ["cartons per pallet", "case design", "palletization", "CapePack Arrange", "packaging engineering benchmark"]
related_articles = ["kollipack-vs-tops-pro-palletization-benchmark", "think-beyond-the-box-packaging-flow-case-study", "rsc-material-optimization"]
related_tools = ["packaging-flow"]
canonical_path = "/blog/cartons-per-pallet-case-design-exploration/"
og_image = "img/blog/cartons-per-pallet-case-design-exploration/thumbnail-v2.webp"
takeaways = ["KolliPack reproduces the demonstrated 216-carton result from a 15 × 12 × 16 in internal, 12-carton RSC case.", "The same 12-carton content can be arranged in a flatter 20 × 18 × 8 in internal case to reach 240 cartons per pallet in the selected KolliPack design.", "The later supplied CapePack screenshot also shows 240, so the evidence supports bounded parity and exploration—not a universal superiority claim.", "The two calculated layouts still require structural, manufacturing, supplier, and physical validation before release."]

[[flow_steps]]
icon = "bi-bounding-box"
label = "Primary carton"

[[flow_steps]]
icon = "bi-box-seam"
label = "Shipping case"

[[flow_steps]]
icon = "bi-grid-3x3-gap"
label = "Pallet"

[cta]
label = "Open the interactive 216 / 240 case in KolliPack"
url = "/full-packaging/case/cape-pack-12-carton-two-layouts/?reset=1"
new_tab = true
+++

<section class="blog-content-section" markdown="1">

**Can two packaging optimization tools reach the same results—and what happens when we explore different shipping case designs?**

We recreated a publicly available CapePack demonstration using KolliPack, starting with a rectangular carton and following the calculation through shipping case design and palletization.

The first result was an exact match in capacity: **216 cartons per pallet**, with the same case dimensions and loading arrangement.

But that wasn't the end of the exercise. By using KolliPack's *Optimize final capacity* functionality, we identified a different case design accommodating **240 cartons per pallet**, an increase of 11.1% over the initial configuration.

After adjusting the case settings in CapePack, we also obtained a 240-carton result.

Both tools therefore reached the same capacities in the demonstrated configurations. The interesting question is not which software wins, but **why changing the shipping case can improve pallet capacity—and how the software helps engineers discover those opportunities.**

</section>

<section class="blog-content-section" markdown="1">

## 1. Case setup: from individual carton to pallet

We began with a simple packaging problem: arrange 12 identical primary cartons inside a Regular Slotted Container (RSC), then find how many shipping cases can fit on a standard North American pallet.

<figure class="blog-figure">
  <img src="static://img/blog/cartons-per-pallet-case-design-exploration/01_benchmark_setup_approved.png" alt="Illustrated benchmark setup showing a primary carton, an open corrugated shipping case and a palletized load, with the common engineering constraints" />
  <figcaption>Figure 1. The common packaging problem: primary carton → shipping case → pallet. The primary carton and pallet requirements remain fixed while the shipping case design changes. Conceptual packaging hierarchy, not an exact geometric result render.</figcaption>
</figure>

The primary carton measures 6 × 5 × 8 inches and weighs 2.25 lb. The 8-inch dimension must remain vertical. The shipping case is an RSC using a 0.16-inch corrugated board thickness, and the pallet has a 48 × 40-inch footprint, a maximum loaded height of 50 inches and a 2,000-lb load limit.

CapePack's original setup permits between 12 and 24 cartons per case. For this comparison, we focus on **12 cartons per case**, the quantity used in both demonstrated configurations. This keeps the product quantity constant and isolates the effect of case geometry.

The objective is straightforward: which arrangement of the same 12 cartons creates the more effective pallet load?

</section>

<section class="blog-content-section" markdown="1">

## 2. Setting up the calculation: CapePack vs. KolliPack

Both applications begin with the same engineering information, but their workflows present it differently.

<figure class="blog-figure">
  <img src="static://img/blog/cartons-per-pallet-case-design-exploration/02_inputs_comparison.png" alt="CapePack and KolliPack input screenshots side by side, showing the successive configuration steps in each tool" />
  <figcaption>Figure 2. Original input screenshots from both applications. CapePack uses separate Carton, Case and Pallet setup screens; KolliPack's Container Selection and Palletization tools can also operate together through Packaging Flow.</figcaption>
</figure>

### CapePack: configuring the packaging stages

In the CapePack demonstration, the user starts by defining the individual carton, its outside dimensions, weight and permitted orientation. The next screen specifies the RSC shipping case, corrugated thickness and the permitted number of cartons per case. Finally, the pallet dimensions and loading restrictions are entered.

This is a conventional packaging engineering workflow. It provides considerable control over the specifications of each stage, including case dimensional constraints.

### KolliPack: exploring designs through Packaging Flow

KolliPack starts with the same carton dimensions, weight and orientation restrictions. In Container Selection's **Design Mode**, the user specifies the desired quantity of 12 cartons and generates alternative shipping case designs.

Instead of presenting only one candidate, KolliPack displays the available calculated arrangements in a table. Each design can be inspected in 3D, and the *Optimize final capacity* function ranks alternatives according to their downstream palletization capacity.

The selected case can then be transferred directly into Palletization through Packaging Flow.

This is an important aspect of KolliPack's modular approach. Engineers can use Container Selection and Palletization independently, or connect them when exploring how a decision at one packaging level affects the next.

In this particular case, the interface makes the exploration especially straightforward: the user can examine several case geometries and identify the highest-capacity pallet option without manually specifying the dimensions of the final shipping case.

</section>

<section class="blog-content-section" markdown="1">

## 3. First comparison: reproducing 216 cartons per pallet

The initial CapePack example uses an RSC shipping case with internal dimensions of **15 × 12 × 16 inches**. Its 12 primary cartons are arranged in a 3 × 2 × 2 configuration.

Accounting for the corrugated board thickness, the external case dimensions become 15.32 × 12.32 × 16.64 inches.

When palletized, nine of these cases fit in each layer, with two layers fitting within the maximum height.

<figure class="blog-figure">
  <img src="static://img/blog/cartons-per-pallet-case-design-exploration/03_216_case_and_pallet_comparison.png" alt="216-carton comparison showing both the shipping case and the complete palletized load in CapePack and KolliPack" />
  <figcaption>Figure 3. Both tools reproduce the 216-carton arrangement: 12 primary cartons per case, nine cases per pallet layer and two layers. All four views use crops of the supplied original results.</figcaption>
</figure>

The match is clear. Both applications produce 18 shipping cases per pallet, equivalent to 216 primary cartons, with identical case geometry.

CapePack reports a loaded pallet height of 38.780 inches, compared with 38.831 inches in KolliPack. The difference is explained by the selected pallet height: 5.500 inches in CapePack versus approximately 5.551 inches in the KolliPack catalogue entry.

For this configuration, KolliPack successfully reproduces the CapePack result. That gives us a useful baseline for investigating alternative case designs.

</section>

<section class="blog-content-section" markdown="1">

## 4. Second comparison: increasing capacity to 240 cartons

The next question is whether the original case is the best choice for palletization.

Using KolliPack's *Optimize final capacity* function, a different shipping case emerged among the highest-capacity alternatives.

Instead of the original 15 × 12 × 16-inch internal case, this design measures **20 × 18 × 8 inches internally**. The 12 primary cartons are arranged in a single layer, using a 4 × 3 × 1 pattern.

The resulting case is considerably flatter, with external dimensions of 20.32 × 18.32 × 8.64 inches.

That changes the palletization result.

Only four cases fit in each pallet layer, compared with nine in the original configuration. However, the lower case height allows five layers instead of two.

The result is 20 shipping cases, or **240 primary cartons per pallet**.

<figure class="blog-figure">
  <img src="static://img/blog/cartons-per-pallet-case-design-exploration/04_240_case_and_pallet_comparison.png" alt="240-carton comparison showing both the shipping case and the complete palletized load in CapePack and KolliPack" />
  <figcaption>Figure 4. Both tools reach 240 primary cartons per pallet using the flatter case: four cases per layer and five layers. The supplied CapePack result was obtained after additional case-settings adjustments; KolliPack's candidate was surfaced through Optimize final capacity.</figcaption>
</figure>

### Two tools, the same result—but a different exploration experience

This second result is particularly interesting because CapePack also reaches 240 cartons per pallet after case settings are adjusted.

Both applications therefore arrive at the same geometric capacity for the alternative design.

The distinction observed in this exercise is in how we reached that result.

In KolliPack, the 240-carton design appears directly among the alternatives evaluated by *Optimize final capacity*. The engineer can see the case geometry alongside the predicted downstream capacity and choose which design to explore further.

In the supplied CapePack walkthrough, obtaining the flatter solution involved returning to the case settings and modifying additional dimensional parameters.

This does not mean that CapePack cannot generate or compare alternatives. Rather, it illustrates the value of KolliPack's approach to making those alternatives visible within one connected design workflow.

</section>

<section class="blog-content-section" markdown="1">

## 5. Why the first attractive-looking case is not always the best

At first glance, the original 216-carton solution appears more efficient.

Its nine-case pallet layer uses approximately 88.5% of the available pallet footprint. The flatter 240-carton design covers only 77.6%.

If floor utilization were the only criterion, the original case would look preferable.

However, pallet utilization is a three-dimensional problem. The flatter case uses considerably more of the available stacking height.

<figure class="blog-figure">
  <img src="static://img/blog/cartons-per-pallet-case-design-exploration/05_geometry_tradeoff.png" alt="216 versus 240 cartons per pallet: comparison of floor utilization, cube utilization and overall carton count" />
  <figcaption>Figure 5. The 240-carton configuration sacrifices floor utilization but improves cube utilization and total pallet capacity. The comparison uses the rounded reference results.</figcaption>
</figure>

The contrast illustrates a fundamental packaging engineering principle: **optimizing a shipping case independently does not necessarily optimize the complete pallet load.**

Both designs accommodate the same number of primary cartons per case. What changes is the geometry of the shipping case and how efficiently those cases fit together on the pallet.

For a manufacturer selecting a new shipping case, evaluating alternative geometries can therefore reveal opportunities that would remain hidden if the first satisfactory design were accepted.

There are, of course, further engineering considerations. A five-layer pallet load places greater compression demands on the lower cases than a two-layer arrangement. Corrugated strength, manufacturing equipment, case-size limitations, stability and handling requirements must still be assessed before approving a design.

These are reasons to evaluate the promising alternatives—not reasons to avoid exploring them.

</section>

<section class="blog-content-section" markdown="1">

## 6. Conclusion: matching results and making better packaging decisions

So, can KolliPack match CapePack?

**For the two configurations examined in this case study, yes.**

KolliPack reproduced the original 216-carton result, including the shipping case dimensions and pallet arrangement. Both tools also demonstrated the alternative 240-carton configuration.

The more important finding is how much the choice of shipping case influences the result.

Changing the case geometry increased capacity from 216 to 240 primary cartons per pallet without changing the product, the quantity per case or the nominal pallet footprint.

For this example, KolliPack's modular Packaging Flow offers a practical way to investigate that relationship. Engineers can generate case alternatives, inspect their geometry, compare downstream pallet capacity and carry a preferred design into further evaluation.

The purpose of packaging optimization software should not be merely to produce a satisfactory arrangement. It should also help engineers understand what other arrangements are possible—and why one might be better suited to the wider packaging system.

**A good shipping case is not necessarily the first one that fits the products. It is the one that performs well across the packaging and logistics requirements that matter.**

</section>

<section class="blog-content-section" markdown="1">

## Explore this case in KolliPack

Recreate the 216-carton reference, inspect the alternative designs, and use *Optimize final capacity* to identify the 240-carton configuration.

<a href="/full-packaging/case/cape-pack-12-carton-two-layouts/?reset=1" target="_blank" rel="noopener"><strong>Open the verified prepopulated 216 / 240 case in KolliPack</strong></a>

<small>Source: <a href="https://www.youtube.com/watch?v=9be4hp7gRf4" target="_blank" rel="noopener">Public CapePack Arrange demonstration</a> and supplied result screenshots. This is a comparison of the two demonstrated configurations, not a general product-performance evaluation. KolliPack is independent of and not affiliated with CapePack.</small>

</section>
