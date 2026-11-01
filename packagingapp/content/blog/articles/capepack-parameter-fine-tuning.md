+++
schema_version = 1
status = "published"
title = "Can KolliPack Match CapePack After Parameter Fine-Tuning?"
slug = "capepack-parameter-fine-tuning"
subtitle = "Reproducing 384- and 360-unit pallet results while exploring carton material and stack stability."
excerpt = "KolliPack reproduces the visible CapePack pallet capacities after fine-tuning, then raises a useful material-versus-stability question."
summary = "A bounded CapePack–KolliPack demonstration of setup changes, pallet pattern parity and the 0.75-cubicity carton as a test candidate."
seo_title = "CapePack vs KolliPack: Case Design and Pallet Fine-Tuning"
meta_description = "A 50-to-72-inch pallet height change reveals matching 384- and 360-unit results and a new material-versus-stability trade-off."
article_type = "demo_case_study"
author = "Alejandro Ramírez"
category = "Packaging Engineering"
read_time = "10 min read"
published_at = 2026-11-01
updated_at = 2026-11-01
thumbnail = "img/blog/capepack-parameter-fine-tuning/01_benchmark_setup_approved.png"
thumbnail_alt = "Benchmark packaging chain from primary carton to RSC shipping case to palletized load"
featured_image = "img/blog/capepack-parameter-fine-tuning/01_benchmark_setup_approved.png"
primary_keyword = "CapePack KolliPack parameter fine tuning"
tags = ["CapePack", "KolliPack", "case design", "palletization", "packaging benchmark"]
related_articles = ["cartons-per-pallet-case-design-exploration", "think-beyond-the-box-packaging-flow-case-study", "rsc-material-optimization"]
related_tools = ["packaging-flow"]
canonical_path = "/blog/capepack-parameter-fine-tuning/"
og_image = "img/blog/capepack-parameter-fine-tuning/01_benchmark_setup_approved.png"

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
label = "Explore the case-design and palletization workflow"
url = "/full-packaging/case/capepack-parameter-fine-tuning/?reset=1"
new_tab = true
+++

*The same packaging problem, a higher pallet limit, and a new decision: is the carton with the best calculated capacity also the carton worth manufacturing?*

In the next part of a public CapePack demonstration, the pallet-height limit rises from **50 to 72 inches** and the case-design options are reopened. CapePack then shows **384 primary cartons per pallet with a 16-unit shipping case** and **360 with a 12-unit case**. KolliPack reproduces both visible capacities and layer counts. But its alternatives also raise another question: **when two cases carry the same pallet quantity, should we prioritize corrugated material, carton proportions, or stacking performance?**

This follows our earlier [CapePack–KolliPack comparison](https://www.kollilabs.com/blog/cartons-per-pallet-case-design-exploration/), where a change in shipping-case geometry moved the calculated result from 216 to 240 primary cartons per pallet. The present exercise continues the same video rather than introducing a completely different test.

> **Comparison scope.** The CapePack observations come from the supplied demonstration screenshots; the software version and original video publication date have not been documented. KolliPack outcomes come from the supplied application screenshots. This is a focused comparison of those visible results, not a complete evaluation of either product. KolliLabs/KolliPack is independent of and not affiliated with CapePack or its vendor.

## 1. The packaging problem before the software

We start with a **6 × 5 × 8 in primary carton weighing 2.25 lb**. Twelve of these cartons are initially arranged inside a Regular Slotted Container (RSC)—the familiar corrugated shipping box with folding top and bottom flaps. The case has a nominal board thickness of **0.16 in**. Its final dimensions are design variables, not preselected package dimensions.

The shipping cases go onto a **48 × 40 in North American pallet**. The original setup uses a **50 in maximum palletized-load height** and a **2,000 lb load limit**. In this continuation we revisit the packaging problem with higher stacking clearance, alternative orientations and two shipping-case quantities: 12 and 16 primary cartons.

![Conceptual setup from a 6 × 5 × 8 in primary carton through RSC shipping case design to a 48 × 40 in pallet.](static://img/blog/capepack-parameter-fine-tuning/01_benchmark_setup_approved.png)

*Figure 1. The original benchmark setup, preserved from the earlier case study: primary carton → shipping case → pallet. This is a conceptual explanation of the physical packaging chain, not an exact pallet-pattern rendering. The 50 in height is the **starting** limit, not the final setting for this continuation.*

This is a familiar decision for a packaging engineer. The first case design may be easy to justify when looking only at product fit. Yet the geometry of that case determines how many cases can be arranged on a pallet, how many layers can be built, and how much load the bottom cases may need to resist.

## 2. Fine-tuning the constraints in CapePack and KolliPack

The two applications describe the same physical packaging problem through different workflows. CapePack uses its Carton, Case and Pallet stages. KolliPack's Design Mode generates case alternatives from the primary-carton dimensions; the selected case can then be evaluated using its Palletization tool or Packaging Flow.

![Actual CapePack case-setup controls beside KolliPack inputs and permitted primary-carton orientations.](static://img/blog/capepack-parameter-fine-tuning/02_original_inputs_parallel.webp)

*Figure 2. Real input screens from the supplied evidence. CapePack shows RSC construction, thickness and case restrictions; KolliPack shows the primary-carton dimensions, desired 12-unit case quantity and orientation controls. They are comparable inputs to the same packaging exercise, **not** identical software controls.*

The video subsequently changes the pallet-height allowance from **50 to 72 in** and revisits case settings. The CapePack case-settings window visibly lists maximum outside dimensions of **30 × 30 × 20 in** and permits its length, width and height to be vertical **on the pallet**. For KolliPack's new runs, all three **primary-carton** upright orientations are allowed, and the maximum palletized-load height is set to 72 in.

![CapePack original 50 in maximum-load input compared with KolliPack's 72 in pallet-height input.](static://img/blog/capepack-parameter-fine-tuning/03_height_finetuning.webp)

*Figure 3. The CapePack capture shows the earlier 50 in setting, before the change; the KolliPack capture shows a reproduced 72 in run. The video describes the intermediate adjustment to 72 in. CapePack's case-on-pallet orientation permissions and KolliPack's product-within-case permissions apply at different packaging levels.*

That last distinction matters. Relaxing product orientation inside the case is not exactly the same constraint as permitting a completed shipping case to stand in different directions on the pallet. Similarly, CapePack's outside-dimension limits are not proof that every design in KolliPack's wider list would have been eligible in the source demonstration. The comparison below therefore concerns the **observed final capacities and layer structures under closely comparable inputs**, not an assertion that the search spaces are identical.

## 3. The 16-unit case: both tools show 384 per pallet

For a shipping case holding **16 primary cartons**, CapePack displays **8 shipping cases per layer**, stacked **3 layers high**. That is 24 shipping cases, or **384 primary cartons per pallet**.

KolliPack reproduces the same visible result with a **16 × 12 × 20 in internal case**. Its estimated external dimensions are about **16.32 × 12.32 × 20.64 in**, and its palletization screen also shows **24 shipping cases, arranged 8 per layer × 3 layers**.

![Cropped original 3D pallet renders from CapePack and KolliPack for the 16-primary-carton shipping case.](static://img/blog/capepack-parameter-fine-tuning/04_sixteen_pallet_render_parity.webp)

*Figure 4. Actual pallet renders cropped from the two applications. In this configuration, both display 24 shipping cases—384 primary cartons in total. The common result is pallet capacity and layer count; the exact carton outside dimensions, pallet tare and software algorithms are not fully identical.*

The result shows why the higher stack limit changes the packaging decision. A case that looked less attractive under the original height allowance can become competitive when the allowed vertical space increases. Comparing shipping cases only by how efficiently they surround the primary cartons would miss that effect.

## 4. The 12-unit case: one capacity, several patterns

Next, the video returns to **12 primary cartons per shipping case**. CapePack shows **two different palletization patterns** for the same proposed case, each with **10 shipping cases per layer × 3 layers**. Both yield 30 shipping cases, or **360 primary cartons per pallet**.

KolliPack produces the same capacity and two visible pallet patterns with an **18 × 8 × 20 in internal case** (approximately **18.32 × 8.32 × 20.64 in externally** in the KolliPack calculation). The corresponding screenshots show 30 shipping cases, a three-layer stack and an approximately **67.47 in** total palletized height.

![Two actual CapePack 12-unit palletization patterns compared with two actual KolliPack patterns, all holding 30 cases.](static://img/blog/capepack-parameter-fine-tuning/05_twelve_four_pallet_patterns.webp)

*Figure 5. Two CapePack patterns on the top row, two KolliPack patterns below. Every panel shows a 30-case pallet, equivalent to 360 primary cartons. Equal quantity does not establish identical box coordinates, compression support, or transport stability.*

These four renders illustrate a practical point: **a shared pallet maximum is a shortlist, not a finished pallet specification**. Different patterns can offer the same quantity yet behave differently during wrapping, forklift handling or transportation. The application result helps narrow what should be reviewed; it does not remove the need for operational judgment.

## 5. The additional cases KolliPack puts on the table

KolliPack's *Optimize final capacity* list exposes further case geometries for the same twelve primary cartons. Three are especially instructive because they have exactly the same **2,880 in³ internal volume**, but different proportions.

| 12-unit internal shipping case | KolliPack cubicity | Pallet result currently evidenced |
|---|---:|---|
| **18 × 8 × 20 in** — CapePack-like reference | **0.40** | 360 in the standalone palletization result |
| **16 × 15 × 12 in** — more balanced proportions | **0.75** | 360 in the design-alternatives table; standalone check outstanding |
| **18 × 5 × 32 in** — very tall and narrow | **0.16** | 384 in design table versus 432 in a standalone result; not reconciled |

![Three actual KolliPack orange 3D RSC renders: reference, more balanced and tall narrow case designs.](static://img/blog/capepack-parameter-fine-tuning/06_three_real_carton_renders.webp)

*Figure 6. All three images are crops of real KolliPack 3D carton renders, including the RSC flaps. Each arrangement fits twelve primary cartons in the design view. The screenshots are not shown at a common physical scale.*

The **16 × 15 × 12 in** option is the most interesting candidate for further investigation. Its **0.75 cubicity** means its dimensions are more balanced than those of the reference case. KolliPack's design table estimates that it can still reach **360 primary cartons per pallet**, so a more balanced case may be worth testing without giving up the benchmark's nominal capacity.

We should not yet describe it as *more stable*. It has not been independently checked in the standalone palletization run, and a shorter case could require more layers to reach the same total quantity. That may increase the compression demand on lower shipping cases.

### A tall, mathematically attractive alternative

At the other end of the design range is the **18 × 5 × 32 in** case. Its slender proportions may create difficulties in case manufacture, compression resistance, handling, wrapping and transport—even though it fits the twelve primary cartons geometrically.

In the supplied screenshots, this particular case has **384 primary cartons per pallet in the design-alternatives table**, but a separate KolliPack palletization view shows **36 shipping cases × 12 = 432 primary cartons**. The results are not reconciled under a documented identical configuration.

![Tall KolliPack shipping-case pallet screenshot and a comparison of the conflicting table and standalone totals.](static://img/blog/capepack-parameter-fine-tuning/07_tall_design_unreconciled.webp)

*Figure 7. A genuine standalone pallet render of the tall proposal, paired with the two reported capacities. This is an **exploration example**, not a verified 432-unit improvement over CapePack, and not a design we would recommend for manufacture on geometry alone.*

This is a useful limitation of unconstrained search, not a reason to hide the alternative. Software can expose valid-looking geometric arrangements that are poor candidates for real packaging. The engineer still needs to decide which constraints and tests matter before selecting a case.

## 6. The unexpected trade-off: cubicity versus corrugated material

A more balanced box may appear economical because its closed rectangular surface area is relatively small. But a standard Regular Slotted Container requires flaps cut from a corrugated blank. For an idealized RSC with length *L*, width *W* and height *H*, and **L ≥ W**, the approximate board area is:

**Blank area ≈ 2(L + W)(H + W)**

This simple model uses internal dimensions and omits the manufacturer's joint, score allowances, board-thickness effects, trimming, waste and changes in flute or board grade. It is a common-basis analytical comparison—not a supplier quotation or a material output measured by either program.

| Case geometry | Idealized blank area | Difference from the reference |
|---|---:|---:|
| 18 × 8 × 20 in | 1,456 in² | Reference |
| 16 × 15 × 12 in | 1,674 in² | **+15.0%** |
| 18 × 5 × 32 in | 1,702 in² | **+16.9%** |

![Simplified RSC blank-area comparison of the CapePack-like, balanced and tall shipping cases.](static://img/blog/capepack-parameter-fine-tuning/08_rsc_blank_area_comparison.webp)

*Figure 8. Theoretical RSC blank area for the three twelve-unit case designs, using identical material construction assumptions. The chart estimates board area, not cost, compression strength or carbon impact.*

The result is counterintuitive. The **0.75-cubicity case has more balanced proportions**, but in this RSC comparison it requires about **15% more theoretical board area** than the 0.40-cubicity reference. The very tall case does not save board either. This follows the same principle discussed in [*Same Volume, Different Material*](https://www.kollilabs.com/blog/rsc-material-optimization/): closed-box surface area and manufacturing blank area are not interchangeable.

Material is not the only consideration, however. A carton that requires more board might still justify investigation if it improves handling, reduces damage risk or has better structural behavior. Those benefits are possibilities to test, **not measured results of this benchmark**.

## 7. What would make the balanced case a better engineering choice?

A useful next experiment would keep the same primary carton, case quantity, pallet, height limit and board specification and compare the reference against the 0.75-cubicity design in standalone palletization. The investigation should then go beyond the 3D render.

For example, if the balanced case achieved 360 units as **6 shipping cases per layer × 5 layers**, a bottom case in a simple aligned column would carry the contents of four cases above it: **4 × 27 lb = 108 lb**. In the reference's **10 cases per layer × 3 layers**, the corresponding static content load would be **2 × 27 lb = 54 lb**. These are **illustrative loads**, not verified layer placements or compression-strength predictions; carton tare, interlock and contact area would change the real distribution.

The practical tests would compare actual RSC blank sizes and board weights, bottom-case compression performance, pallet-pattern support, stack stability after wrapping, and responses to handling and transport. The 0.75-cubicity candidate should earn its place through those results, not through a cubicity number alone.

![Evidence summary distinguishing the reproduced 384- and 360-unit results from the proposed balanced carton and untested material-versus-stability hypothesis.](static://img/blog/capepack-parameter-fine-tuning/09_evidence_boundary.webp)

*Figure 9. Evidence boundary for this stage: two visible pallet capacities reproduced; one balanced design shortlisted; structural and transport performance still to be tested.*

## Practical takeaway

Under the conditions shown in this part of the demonstration, **KolliPack matches CapePack's visible 384-unit and 360-unit pallet capacities**. It also shows different pallet patterns and additional shipping-case geometries. Some are useful candidates for closer review; others are reminders that a high calculated count is not a complete packaging recommendation.

The most promising unanswered question is not whether a 0.75-cubicity case *looks* better. It is whether its geometry can deliver the same pallet capacity **with acceptable material use, compression strength and pallet stability**. That is the next worthwhile test.

**Explore the case-design and palletization workflow in [KolliPack](/full-packaging/case/capepack-parameter-fine-tuning/?reset=1).** Reproduce the original twelve-unit case, change the height restriction, and compare how selecting a different shipping case affects the downstream pallet.

### Key takeaways

- With the updated pallet-height setting, both applications show **384 primary cartons** for the 16-unit case and **360** for the 12-unit case.
- The supplied video contains two 12-unit CapePack pallet patterns; the KolliPack evidence contains two 30-case patterns as well.
- KolliPack's **0.75-cubicity** case is a plausible engineering candidate, not yet a validated more stable pallet.
- A simplified RSC model indicates **15% more blank area** for that balanced case than for the reference case.
- Actual compression, manufacturing and transport tests—and reconciliation of the tall-design discrepancy—remain necessary before choosing a final specification.

*About the author: Alejandro Ramírez is a chemical engineer and digitalization specialist based in Gothenburg, Sweden. Through KolliLabs, he develops KolliPack to make packaging and logistics engineering decisions more visual, systematic and data-driven.*
