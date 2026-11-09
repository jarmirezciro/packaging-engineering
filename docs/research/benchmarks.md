# Benchmarks and similar tools

## Status

This is a summary of project benchmark discussions from March–June 2026, not a current market audit. Verify features, pricing, availability, and product names before publishing external comparisons.

## External comparison publishing policy

Treat every named-tool comparison as a bounded benchmark, not a complete product review
or a universal product claim. Before external publication, record the comparator, source
URL, capture date, region, product/version or plan, exact inputs, unit conversions,
rounding, settings, supported constraints, outputs, and unresolved discrepancies.

Use neutral, case-scoped language such as “under these inputs, both tools found…”
Avoid unsupported claims that one product is universally better, cheaper, faster, more
accurate, equivalent, or compliant. Do not present calculated geometry as physical safety,
compression validation, transport approval, or a released packaging specification.

Comparison articles should state that KolliLabs/KolliPack is independent of the named
vendor and that the result does not represent a complete product evaluation. Source
screenshots, recordings, logos, quotations, and extracts require a rights check. Flag
claims involving misconduct, infringement, safety, compliance, pricing, market position,
customer outcomes, restricted material, paid advertising, or vendor complaints for human
legal review. The benchmark process is not legal advice or legal approval.

The operational checklist for agents is maintained in
`.agents/skills/blog-article/references/comparative-benchmarking.md`.

## Similar commercial tools discussed

| Tool/vendor | Benchmark strength | Gap/opportunity for KolliPack |
|---|---|---|
| Esko Cape Pack / Cape Truckfill | Mature palletization and truck/container workflows; industry recognition | Enterprise complexity/cost; opportunity for a more accessible integrated engineering workflow |
| TOPS Pro | Packaging design, palletization, case/pallet analysis | KolliPack can differentiate through modern web UX, catalogues, chained Flow, and broader selection tools |
| TreeDim StackBuilder | Free desktop palletization and truck/container loading; closest free reference | Primarily focused on stacking/loading, not a full shared catalogue and packaging-selection platform |
| Packsize | Right-sized packaging ecosystem and automation | Different business model; KolliPack focuses on independent engineering analysis/catalogue decisions |
| MagicLogic Cube-IQ | 3D packing/container loading optimization | KolliPack can connect packaging choice, pallet, transport, reports, and public education |
| EasyCargo | Online truck/container loading planner, 3D visualization, approachable UX | Strong benchmark for Transport UI; narrower than the complete packaging chain |
| CargoWiz | Container/truck loading | Benchmark for load planning, but not the complete product-to-packaging workflow |
| LoadCargo.in | Accessible/free online load planning | Useful UX/availability benchmark; limited integrated packaging engineering context |
| py3dbp and other open-source bin-packing libraries | Algorithm/reference implementation and testing fixtures | Libraries are components, not a customer-ready packaging platform |
| Ecochain / Sphera | Sustainability/LCA and enterprise environmental data | KolliPack opportunity: connect actual packaging geometry and logistics utilization to CO2 scenarios |

Other limited/free references discussed included Cape Pack Essentials, Cube-IQ trials, and EasyCargo free/trial tiers. Re-verify current offers.

## Differentiation hypothesis

No benchmark discussed combined all of these in one coherent, accessible platform:

- product and packaging catalogues;
- carton/container selection;
- bag optimization;
- multi-product analysis;
- palletization;
- transport loading;
- chained Packaging Flow;
- shared deterministic engines across standalone/public/workflow surfaces;
- visual result explanations and reports;
- packaging education/blog;
- future packaging + logistics CO2 scenario analysis.

This is a strategic hypothesis, not a verified claim that no competitor has any overlapping capability.

## UX benchmarks

### Container Selection

Benchmark against:

- clear orientation restrictions;
- Top-5 candidate comparison;
- clean 3D product-in-box render;
- transparent max quantity and payload;
- product/packaging catalogue integration;
- report export.

### Palletization

Benchmark against:

- uniform, row/brick, split, pinwheel, and mixed-orientation mosaics;
- 2D layer clarity;
- column/interlock visualization;
- overhang, height, payload, and compression/load constraints;
- deduplicated and operationally meaningful patterns.

### Transport

EasyCargo and Cape Truckfill are useful references for:

- approachable 3D views;
- door/access orientation;
- multiple views;
- loaded/unloaded quantities;
- volume and payload utilization;
- printable reports.

### Packaging Flow

The main benchmark is not one screen but continuity:

```text
select package → select result → feed palletization → feed transport
```

A user should not have to re-enter dimensions or interpret incompatible result models.

## Article/engine benchmark fixture

A technical blog fixture compared:

```text
Product: 130 × 70 × 30 mm
Box: 500 × 300 × 200 mm
Best uniform/base orientation: 84
KolliPack-style mosaic illustration: 102
Improvement: +18 (+21.4%)
```

The best uniform grid is 7 × 2 × 6 in orientation (70, 130, 30).
The historical article illustration shows 70 units in the main block plus
32 in the top region. The same inputs with all rotations enabled now yield
106 in Container Selection. The current legacy residual-space candidate
produces 106, and the independently evaluated shared Mosaic candidate
produces 84.

## Container Selection cases

The [case compendium](/regressions) opens the standalone Container Selection
tool with editable inputs and a calculated result. The links use the same
Python preset registry as the public box calculator. Historical results are
recorded here separately from the output calculated on each visit.

| Case | Input source | Historical reference | Verified Container Selection result |
|---|---|---|---|
| Mosaic Packing Benchmark | [3D box packing article](../../packagingapp/content/blog/articles/box-selection-3d-bin-packing-problem.md) | 84 uniform, 102 illustrated | 106 with all rotations |
| Product Orientation Capacity | Existing `product-orientation-capacity` preset and [orientation article](../../packagingapp/content/blog/articles/how-many-products-fit-in-a-box-orientation-case-study.md) | R1 10, R2 12, R3 15, all 18 | R1 10, R2 16 (pinwheel), R3 15, all 18 |
| Pinwheel Packing Benchmark | [Shared Mosaic benchmark](../../packagingapp/tests/benchmark_shared_mosaic_patterns.py), `reference_imperial_equivalent` | 12 legacy, 16 pinwheel | 16 with R3 only |
| Bottle Packaging — 24 Units | [Bottle benchmark article](../../packagingapp/content/blog/articles/capepack-kollipack-bottle-case-pallet-benchmark.md), Case A | 24 per carton, 42 cartons and 1,008 bottles per pallet | 6 × 2 × 2 upright, 15.66 × 5.22 × 20 in internal |
| Bottle Packaging — 15 Units | [Bottle benchmark article](../../packagingapp/content/blog/articles/capepack-kollipack-bottle-case-pallet-benchmark.md), Case B | 15 per carton, 72 cartons and 1,080 bottles per pallet | 5 × 3 × 1 upright, 13.2 × 7.92 × 9.75 in internal |
| Design Mode Quantity Optimization | [Asymmetric seven-unit Design fixture](../../packagingapp/tests/test_product_shape_visualization.py) | 180 × 120 × 80 mm, all rotations, request of 7 | Designs for 8 units. The generator evaluates 60 grids and retains 30 distinct carton geometries. The first is 240 × 180 × 320 mm. |

The bottle cases use the documented KolliPack nominal diameters and heights
(2.49 × 10 in and 2.52 × 9.75 in, respectively), 0.12 in on each horizontal
product axis, zero height allowance, and the article's approximately 0.16 in
caliper. The preset uses the bottle visualization and selects the captured
carton arrangement in Design Mode. The pallet totals are historical references.
The two cases also cover imperial units and allowances in the compendium.

## Future benchmark: packaging and logistics CO2

A proposed KolliPack LCM/CO2 module would combine:

```text
packaging CO2 = Σ(component weight × emission factor)
transport CO2 = shipment or tonne-km model
scenario savings = baseline - optimized
```

The differentiation would be linking material choices with carton fill, pallet fill, transport fill, annual shipments, and operational savings rather than reporting material footprint alone.

## Benchmark research protocol

Before external publication:

1. verify vendor website and current product name;
2. capture date and region;
3. distinguish free, trial, paid, desktop, and cloud;
4. test the same engineering fixture where possible;
5. compare supported constraints, not only maximum count;
6. record calculation assumptions and whether “optimal” is proven or heuristic;
7. avoid unsupported superiority claims.
