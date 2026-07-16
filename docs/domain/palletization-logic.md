# Palletization Tool logic

## Purpose

Generate and rank practical rectangular-carton pallet patterns, calculate layers and total quantity, evaluate dimensional and weight constraints, and explain the chosen result in 2D/3D and PDF outputs.

## Inputs

Established or discussed inputs include:

- carton L/W/H;
- pallet L/W/H and pallet weight;
- maximum total stack/load height;
- acceptable length and width overhang;
- carton/product weight;
- optional maximum pallet payload;
- optional maximum cargo load on the bottom carton;
- pattern families and column/interlock preference;
- advanced carton/stability parameters where present in the current form.

All fields and units must be verified against the current form and service before logic edits.

## Core geometry

For a layer mosaic, each placement is a rectangle with:

```text
x, y, footprint_length, footprint_width, orientation (P1 or P2)
```

A valid layer must satisfy:

- positive carton footprint;
- no pairwise overlap;
- every carton remains inside the allowed pallet footprint including permitted overhang;
- count equals number of placements;
- equivalent symmetric/rotated duplicates are deduplicated unless operationally distinct.

## Pattern families

The project has discussed and implemented/refined these engineered pattern families:

- Block
- Row
- Brick
- Spiral Brick
- Pinwheel / Block Pinwheel
- Split Row
- Hybrid Pinwheel
- Mosaic patterns with main, secondary, and filler blocks

Pattern definitions are deterministic constructive heuristics. They are not generic unrestricted 2D nesting.

Preferred terminology:

- layer top view = **mosaic**;
- orientations = **P1/P2**;
- use **main block**, **secondary block**, **filler block**, **filler line**, **sparse filler line**, **edge-balanced filler**;
- do not call a filler-symmetry adjustment a new pattern when the underlying mosaic is unchanged.

## Uniform patterns

For P1 and P2, simple grid capacity is:

```text
count_P1 = floor(usable_length / carton_length) × floor(usable_width / carton_width)
count_P2 = floor(usable_length / carton_width)  × floor(usable_width / carton_length)
```

These are baseline candidates and useful benchmarks, not the full engine.

## Split and mosaic patterns

A split/mosaic candidate divides the usable footprint into non-overlapping zones. Each zone uses P1 or P2, then optional filler regions are evaluated. The engine should:

1. enumerate meaningful split positions based on carton multiples, not every floating-point coordinate;
2. fill each zone with an integer grid;
3. test residual strips/blocks for alternate orientation fillers;
4. reject overlap and out-of-bounds placements;
5. deduplicate equivalent mosaics;
6. score symmetry/contour only after feasibility and count.

Balanced filler symmetry may improve operational quality but must not falsely inflate count or create unsupported cartons.

## Pinwheel

Pinwheel patterns arrange alternating orientations around a central or block region. A known validation fixture is:

```text
Carton: 230 × 170 × 130 mm
Pallet: 1200 × 800 mm
```

Earlier results looked geometrically strange compared with the intended reference pattern. Any pinwheel change must use explicit placement validation and visual regression fixtures, not only count comparison.

## Layer count and height

The engine must clearly distinguish:

- pallet height;
- carton layer height;
- maximum total load height;
- maximum cargo height above pallet.

A typical relationship is:

```text
available_cargo_height = max_total_height - pallet_height
geometric_layers = floor(available_cargo_height / carton_height)
```

Use the exact current field definitions. Do not subtract pallet height twice or omit it from reported total height.

## Weight limits

### Pallet payload

```text
cargo_weight = total_cartons × carton_weight
```

Compare with maximum pallet payload according to whether pallet tare is excluded or included in the current definition.

### Bottom-carton load

The discussed definition is cargo load from cartons above only. For pure column stacking with equal overlap:

```text
load_above_bottom_carton = (layers - 1) × carton_weight
```

For interlock or partial overlap, a prior design used overlap-area load distribution. The current implementation must be inspected and tested; do not replace it with a simple full-load assumption during unrelated work.

## Column and interlock

- **Column view:** repeat the same mosaic layer.
- **Interlock view:** alternate a valid transformed/alternate mosaic.
- **Interlock possible:** only true when the alternate layer passes bounds, overlap, count, and compatibility checks.
- Conservative filtering is preferred over visually attractive but invalid interlocks.

An interlock pattern is not automatically structurally superior. Reports should not make strength claims without compression/stability modelling.

## Ranking

Feasibility comes first. A transparent ranking can consider:

1. mandatory geometry/height/weight constraints;
2. cartons per layer;
3. total feasible quantity;
4. pallet area utilization;
5. contour alignment and edge balance;
6. operational pattern preference;
7. interlock availability;
8. stable tie-breaking.

Do not let a cosmetic symmetry score beat a higher-priority feasibility requirement.

## Shared surfaces

Palletization has three important consumers:

- standalone tool;
- Packaging Flow;
- public SEO Palletization Calculator.

The SEO page may have prefilled demonstration values and a visible initial result, but that demo state must be page-specific. It must not change standalone or Flow defaults.

All three must reuse the shared engine/service/UI contract. Changes to inputs, catalogues, results, JS, 3D, and reports must be assessed everywhere.

## Visualization and report

- clean 2D/3D patterns;
- no axes/mesh in final user-facing output;
- show carton and pallet dimensions, overhang, layers, quantity, weight, and result interpretation;
- selected pattern visualization in the ReportLab PDF;
- PDF should be concise, ideally one page for the standalone result where possible;
- images from selected catalogue records should appear where relevant.

## Test fixtures

Retain fixtures for:

- Euro pallet and 230×170×130 carton;
- P1/P2 uniform baselines;
- pinwheel visual coordinates;
- split/mosaic count improvement;
- no-overlap and bounds assertions;
- deduplication of symmetric patterns;
- max height with pallet height;
- pallet payload governing layers;
- bottom-box load governing layers;
- column/interlock result parity across standalone, Flow, SEO, and PDF;
- page-specific SEO demo state.
