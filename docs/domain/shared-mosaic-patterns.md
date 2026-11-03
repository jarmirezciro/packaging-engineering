# Shared mosaic-pattern library

## Stage and scope

Stage 1 introduces a tool-independent 2D rectangular-pattern library under
`packagingapp/utils/packing_patterns/` and makes Container Selection evaluate
it as an additional candidate family. The established Palletization runtime in
`packagingapp/utils/palletization/engine.py` is intentionally unchanged.

The Stage 1 shared implementation is carefully adapted from the established
Palletization geometry. Temporary duplication is deliberate: representative
geometry-parity tests compare the shared Block, Row, Splitrow, Brick,
Pinwheel, Hybrid Pinwheel, Nested Pinwheel, and Centre-filled Pinwheel outputs
with the original functions. Palletization will not import the shared package
until the Stage 1 benchmark has been approved.

## Dependency and selection flow

```text
canonical product/container dimensions + R1/R2/R3
                         |
             +-----------+-----------+
             |                       |
      unchanged MainBox       box-selection Mosaic adapter
      legacy placements               |
                              shared 2D pattern API
                                      |
                         validated repeated 3D layers
             |                       |
             +-----------+-----------+
                         |
             strict quantity comparison
             (legacy retains every tie)
                         |
          one authoritative placement collection
                         |
     capacity / Top 5 / Three.js / PDF / Packaging Flow
```

`MainBox`, its residual-space strategy, and `_calculate_pilot_solution()` stay
the legacy baseline. A Mosaic candidate can replace that baseline only when it
has independently valid geometry and a strictly larger placement count. An
exception, invalid result, empty search, or resource-limited search fails
closed to the legacy result.

## Shared API

`enumerate_pattern_candidates(area_l, area_w, box_l, box_w, *,
candidate_budget=96)` returns deterministic `PatternCandidate` values. Every
candidate contains a family, variant, and explicit immutable `Placement2D`
coordinates. Inputs must use one consistent physical unit; Container Selection
passes canonical millimetres.

Available families are:

- Block and Row;
- Splitrow;
- Brick / basket weave;
- Pinwheel;
- Hybrid Pinwheel;
- Nested Pinwheel;
- Centre-filled Pinwheel;
- bounded two-region mosaics whose cut positions come from carton multiples.

Patterns do not know about pallets, overhang, load height, interlock display,
Palletization ranking, Django, views, forms, sessions, or reports.

## Container adapter and rotation semantics

The adapter evaluates one footprint family for each permitted original vertical
axis. R1 permits original product length vertically, R2 width vertically, and
R3 height vertically. Shared patterns may mix the two horizontal orientations
within that family. Every complete layer repeats at stable elevations using
the selected original vertical dimension.

The adapter validates positive finite dimensions, bounds, allowed 3D
orientations, duplicate placements, positive-volume collisions, placement
count, and stable layer elevations. The winning `Placement` collection remains
the source for capacity and rendering, including mixed horizontal orientations.

Container Design Mode is intentionally outside Stage 1. It continues to use
its established regular-grid arrangement generator.

## Numerical and resource policy

Grid counts use an eight-ULP physical-extent tolerance. A near-integer quotient
caused by display-unit conversion may reach the next integer only when the
required extent is within representation error of the available extent. A
genuine physical shortfall remains a floor result.

Search is bounded and deterministic:

- 192 candidates across all permitted vertical families;
- 96 candidates per shared enumeration call;
- at most 12 rows/columns in each block-pinwheel leaf;
- at most 8 materialized block/nested pinwheel parameter candidates;
- at most 16 regional cut positions per footprint axis;
- at most 20,000 products in one materialized Mosaic layer;
- at most 100,000 products in a complete materialized Mosaic stack;
- a 256-entry in-process cache for identical pattern searches.

Before materializing a large regular tie, the adapter compares the regular-grid
quantity with the physical footprint-area upper bound. If they are equal and
cannot beat legacy, the proven best Mosaic quantity is reported arithmetically
and legacy remains selected.

## Shared consumers

The authoritative box-selection entry points remain
`compute_max_quantity_only()` and `run_mode1_and_render()`. Consequently the
improved selected capacity propagates through Single Container Analysis,
Optimal/Top-5 ranking, the public calculator, Packaging Flow capacity analysis,
the selected Three.js/PDF result, and the current one-row Multi-product
Container path. The same selected placement list drives quantity and rendering.

Multi-product mixed-row orchestration remains a separate heuristic and is not
claimed to be a general multi-SKU Mosaic solver.

## Stage 2 handover

After Stage 1 benchmark approval:

1. extend parity fixtures to every published Palletization regression geometry;
2. add Palletization-specific adapters for naming, ranking, overhang, interlock,
   stacking, height, and load limits around the shared coordinates;
3. switch one Palletization family at a time while preserving its public
   function interfaces and exact result signatures;
4. run standalone, Packaging Flow, SEO calculator, Three.js, PDF, height/load,
   and Splitrow regressions after each family;
5. remove the corresponding duplicated Palletization geometry only after
   parity is established for all approved fixtures.

Stage 2 must not move pallet-specific scoring or load behavior into the shared
geometry package.
