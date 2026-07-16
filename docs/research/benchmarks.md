# Benchmarks and similar tools

## Status

This is a summary of project benchmark discussions from March–June 2026, not a current market audit. Verify features, pricing, availability, and product names before publishing external comparisons.

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

Use this only after reproducing it with the current engine/script. It is an educational example, not a broad competitor benchmark.

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
