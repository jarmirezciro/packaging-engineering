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

## Palletization cases

The [case compendium](/regressions) opens the standalone Palletization tool
with editable inputs. The [preset registry](../../packagingapp/tools/palletization/case_presets.py)
records the exact inputs. Quantities below are shipping cartons per pallet
unless the row specifies products, primary cartons, or bottles.

| Case | Status | Source | Historical result | Current result | Remarks |
|---|---|---|---|---|---|
| PB-01 `tops-pro-48x40-benchmark` | Already covered | [TOPS 48×40 benchmark](../../packagingapp/content/blog/articles/kollipack-vs-tops-pro-palletization-benchmark.md), Stage 2 `tops_splitrow_overhang` | Splitrow 10 × 5 = 50 | Splitrow 10 × 5 = 50, interlock available | Existing benchmark preset uses 25 mm added to each footprint axis, centred on the deck. |
| PB-02 `tops-case-pack-8` | Registered | [TOPS case-pack article](../../packagingapp/content/blog/articles/tops-pro-case-size-optimization-kollipack-comparison.md), source capture `kollipack_box_input_palletization_8_units.png` | 24 × 6 = 144, 1,152 products | 24 × 6 = 144 | The capture gives 314 × 148 × 194 mm external. Current Flow searches for those numbers as internal dimensions and falls back to 288 × 161 × 194 mm external, also yielding 144. Gross carton weight is unavailable. |
| PB-03 `tops-case-pack-16` | Registered | TOPS case-pack article, source capture `kollipack_box_input_palletization_16_units.png`, and Flow design | 11 × 7 = 77, 1,232 products | 11 × 7 = 77 | Flow reproduces the captured 364 × 288 × 169 mm external dimensions. Gross carton weight is unavailable. |
| PB-04 `capepack-original-216` | Registered | [Original CapePack study](../../packagingapp/content/blog/articles/cartons-per-pallet-case-design-exploration.md), Flow `cape-pack-12-carton-two-layouts` | 9 × 2 = 18, 216 primary cartons | 9 × 2 = 18 | 15 × 12 × 16 in internal, 389 × 312.8 × 422.4 mm external in current Flow. |
| PB-05 `capepack-original-240` | Registered | Original CapePack study and Flow `cape-pack-12-carton-two-layouts` | 4 × 5 = 20, 240 primary cartons | 4 × 5 = 20 | 20 × 18 × 8 in internal, 516 × 465.2 × 219.2 mm external. The shorter carton fits five layers. |
| PB-06 `capepack-72in-12-pack` | Registered | [CapePack fine-tuning study](../../packagingapp/content/blog/articles/capepack-parameter-fine-tuning.md), Flow `capepack-parameter-fine-tuning` | 10 × 3 = 30, 360 primary cartons | 10 × 3 = 30 | 18 × 8 × 20 in internal, 465.2 × 211.2 × 524 mm external. |
| PB-07 `capepack-72in-16-pack` | Registered | Fine-tuning study and [Flow case test](../../packagingapp/tests/test_full_packaging_case.py) | 8 × 3 = 24, 384 primary cartons | 8 × 3 = 24 | 16 × 12 × 20 in internal, 414.4 × 312.8 × 524 mm external. |
| PB-08 Bottle 24-pack | Covered in Packaging Flow | [Bottle benchmark](../../packagingapp/content/blog/articles/capepack-kollipack-bottle-case-pallet-benchmark.md), Flow `capepack-bottle-24` | 21 × 2 = 42, 1,008 bottles | 21 × 2 = 42, 1,008 bottles | 6 × 2 × 2 upright, 405.888 × 140.718 × 524.256 mm external. Zero overhang reproduces the layout. The original controls are collapsed. |
| PB-09 Bottle 15-pack | Covered in Packaging Flow | Bottle benchmark, Flow `capepack-bottle-15` | 18 × 4 = 72, 1,080 bottles | 18 × 4 = 72, 1,080 bottles | 5 × 3 × 1 upright, 343.408 × 209.298 × 263.906 mm external. The captured KolliPack length and width allowances are 1.45 and 1 in. |
| PB-10 Bottle 20-pack | Covered in Packaging Flow | Bottle benchmark, Flow `capepack-bottle-20` | 12 × 4 = 48, 960 bottles | 12 × 4 = 48, 960 bottles | 5 × 4 × 1 upright, 335.788 × 270.258 × 276.606 mm external. The capture shows zero overhang. |
| PR-01 `north-american-splitrow` | Registered | [Splitrow tests](../../packagingapp/tests/test_pallet_splitrow.py), Stage 2 `na4840_splitrow` | Splitrow 24 × 6 = 144 | Splitrow 24 × 6 = 144, tied with Block and Pinwheel | Splitrow mixes 18 and six cartons by orientation. Block ranks first. |
| PR-02 `pinwheel-mosaic` | Registered | [Stage 2 benchmark utility](../../packagingapp/tests/benchmark_palletization_stage2.py), `standard` | Frozen footprint has 24-carton Pinwheel and Splitrow | Pinwheel 24 × 8 = 192, with interlock available | Uses the complete unweighted benchmark. Hybrid and Nested are visible on the Brick case and remain covered by the pattern suite. |
| PR-03 `brick-centre-filled` | Registered | Stage 2 `brick_and_centre_filled`, shared pattern core | Brick 18 × 5 = 90, Centre-filled pinwheel 9 × 5 = 45 | Brick 90 and Centre-filled pinwheel 45 | Spiral bonded weave is an internal Brick construction. Block is a separate result and ranks first on this input. |
| PR-04 Sparse Splitrow | Retained as automated test | Splitrow tests and Stage 2 footprints | 284 × 160 mm fits 25 per layer including in interlock. Odd fillers are centred on 362 × 146 and 364 × 288 mm. | Frozen footprints and focused tests retained | No full 284 × 160 or 362 × 146 input was verified. The 364 × 288 mm footprint also appears in PB-03. |
| PR-05 `maximum-pallet-load` | Registered | [Maximum load tests](../../packagingapp/tests/test_pallet_max_load.py), Stage 2 `maximum_pallet_load` | 30 geometrically, 22 with the cargo limit | 22 in layers of 6 + 6 + 6 + 4 | 22,000 g limits carton cargo. Empty pallet tare is excluded by the cargo-load contract. |
| PR-06 `bottom-carton-load` | Registered | Stage 2 `standard_pallet` | Pinwheel 24 × 8 = 192 | 192 with a maximum bottom-carton load of 8,750 g | The 9,000 g input permits the full stack. The case exposes the load calculation and alternative patterns. |
| PR-07 `overhang-feasibility` | Registered | [Pallet height and feasibility tests](../../packagingapp/test_pallet_height.py) | 0 without allowance, 2 with 200 mm length allowance | 1 × 2 = 2 with allowance | The zero-overhang negative remains in the feasibility tests. |
| PR-08 `fractional-dimensions` | Registered | Stage 2 `fractional_dimensions` | Pinwheel 34 × 6 = 204 | Pinwheel 34 × 6 = 204 | Full precision is retained in the inputs. |
| PR-09 `exact-stack-height` | Registered | Pallet height and feasibility tests | 8 on one layer at exactly 1,200 mm | 8 on one layer at exactly 1,200 mm | 150 mm deck and 1,050 mm carton. Default/manual/catalogue height and infeasible-height paths remain automated. |
| `think-beyond-the-box-compact` | Registered | [Think Beyond the Box study](../../packagingapp/content/blog/articles/think-beyond-the-box-packaging-flow-case-study.md), Flow carton handoff | 16, corresponding to 9,600 products downstream | 20 Splitrow, 16 Block | With the Flow preset’s 25.4 mm allowance on both axes, Splitrow fits five per layer. With zero allowance the current result is 16. |
| `think-beyond-the-box-alternative-7` | Registered | Think Beyond the Box study and Flow `think-beyond-the-box` | 24, corresponding to 14,400 products downstream | 6 × 4 = 24 | Exact downstream carton is 608 × 258 × 316 mm. The compact handoff is 508 × 308 × 316 mm. Both use the Flow pallet of 1200 × 800 × 80 mm and 1,350 mm total-height limit. The downstream product counts are article references. |

The four CapePack benchmarks reproduce the verified geometry from Packaging
Flow. They use the 48 × 40 × 5.5 in pallet, zero overhang, and exact carton
dimensions handed off by the current design calculation with its 4 mm default
caliper. The historical 0.16 in board is 4.064 mm. The historical setup and
Flow form record a 2,000 lb limit. Flow runs these cases without weight checks
because only the 2.25 lb primary-carton weight and net contents are known. The
standalone presets therefore leave gross shipping-carton mass and cargo load
limit blank.

The three bottle Flow cases apply 0.12 in allowance on each horizontal product
axis, zero on height, and 0.16 in caliper with the captured FEFCO C-flute board.
The original KolliPack pallet captures are `Screenshot 2026-11-02 224021.png`
(24-pack), `Screenshot 2026-11-03 001437.png` (15-pack), and
`Screenshot 2026-11-03 002826.png` (20-pack). All show a 50 in total height
limit and a blank cargo limit. The 24- and 20-pack cases use the manual
equivalent of the captured NA4840 catalogue pallet (1,219 × 1,016 × 141 mm).
The 15-pack uses the captured manual 48 × 40 in footprint and 141 mm deck.
The 24-pack carries the captured 3.19 lb bottle input for geometry parity.
The other two use 1.19 lb per bottle. These are geometric comparisons with
the source study.

The TOPS 10-, 18-, and 24-pack variants add no distinct regression to this
compendium. CapePack’s 16 × 15 × 12 in internal alternative remains documented
with PB-06. Its 0.75 cubicity offers more balanced proportions and the design
table estimates 360 primary cartons per pallet. Its theoretical RSC blank
uses about 15% more board than the reference, and stability still needs
physical testing. Think Beyond the Box Alternative 23 also reaches 24 cartons
per pallet historically and is excluded as a second example of that capacity.

The [Stage 2 fixture](../../packagingapp/tests/palletization_stage2_baseline.json)
retains all 19 footprint scenarios, 12 pattern calls, and seven complete
analyses. The other square, near-square, elongated, exact-footprint,
residual-space, equal-count, near-insufficient, large, and imperial-equivalent
geometries remain in the automated suite. The 70 × 40 mm high-density case
protects Palletization’s broader search policy. The full container-reference
analysis also stays automated because its pattern families are already exposed
by other compendium cases.

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
