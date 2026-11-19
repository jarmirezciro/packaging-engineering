# Shared mosaic-pattern library

## Stage and scope

Stage 2 establishes one tool-independent constructive geometry core under
`packagingapp/utils/packing_patterns/`. Container Selection and Palletization
both call this core through the public API in `patterns.py`.

The core owns Block, Row, Splitrow, Brick, Pinwheel, Hybrid Pinwheel, Nested
Pinwheel, Centre-filled Pinwheel, and Perimeter-Core Mosaic construction. Tool-specific selection,
stacking, interlock policy, load engineering, presentation, and reporting are
not part of the shared geometry library.

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
                    Container bounded-search policy
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

Palletization uses the same geometry constructors through stable compatibility
wrappers:

```text
shared 2D pattern core
          |
Palletization compatibility search policy
          |
stable Placement2D adapter
          |
balancing / interlock / stacking / load / ranking / presentation
```

`MainBox`, its residual-space strategy, and `_calculate_pilot_solution()` stay
the legacy baseline. A Mosaic candidate can replace that baseline only when it
has independently valid geometry and a strictly larger placement count. An
exception, invalid result, empty search, or resource-limited search fails
closed to the legacy result.

## Shared API

`enumerate_pattern_candidates(area_l, area_w, box_l, box_w, *,
candidate_budget=96, search_policy=CONTAINER_SEARCH_POLICY)` returns
deterministic `PatternCandidate` values. Every candidate contains a family,
variant, and explicit immutable `Placement2D` coordinates. Inputs must use one
consistent physical unit; Container Selection passes canonical millimetres.

Each public family function accepts an explicit `PatternSearchPolicy`.
Palletization's engine retains its established public signatures and passes
`PALLETIZATION_SEARCH_POLICY` internally, then adapts the shared immutable
placement values to the established Palletization `Placement2D` dataclass.

Available families are:

- Block and Row;
- Splitrow;
- Brick / basket weave;
- Pinwheel;
- Hybrid Pinwheel;
- Nested Pinwheel;
- Centre-filled Pinwheel;
- Perimeter-Core Mosaic: a validated ten-carton mixed-orientation topology for
  `L >= 2*S`, with footprint `(2*L + S) x (2*L)` and no arbitrary upper ratio;
- Nested Simple Lattice — 1D: the independent `[1,j]-1 x 1-1 x 1`
  construction for `j >= 2`, with `(1+j)^2` cartons, `j` square holes, and
  contour `(L + j*S) x (S + j*L)`;
- Nested Simple Lattice — 2D: the independent `[i,j]-1 x 1-1 x 1`
  construction for `i,j >= 2`, with `(i+j)^2` cartons, `i*j` square holes,
  and contour `(i*L + j*S) x (i*S + j*L)`;
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

Container Selection's search remains bounded and deterministic:

- 192 candidates across all permitted vertical families;
- 96 candidates per shared enumeration call;
- at most 12 rows/columns in each block-pinwheel leaf;
- at most 8 materialized block/nested pinwheel parameter candidates;
- at most 16 regional cut positions per footprint axis;
- at most 20,000 products in one materialized Mosaic layer;
- at most 100,000 products in a complete materialized Mosaic stack;
- a 256-entry in-process cache for identical pattern searches.

Palletization uses its approved pre-migration search contract:

- legacy floor semantics for its established numerical results;
- at most 30 rows/columns in each block-pinwheel parameter dimension;
- at most 80 materialized block/nested-pinwheel parameter candidates;
- unchanged candidate ordering and tie-breaking.

These policies configure one implementation; they are not separate copies of
the pattern algorithms. Container defaults remain 12/8 and are not widened by
Palletization calls. Context-local policy selection prevents concurrent tool
requests from leaking one consumer's policy into another.

The Palletization policy also requires a compact Nested Pinwheel. The
centered inner motif must contact all four opening walls, and the outer
contour must reach within one short carton side of the effective footprint
span on at least one axis. Both checks run on the existing dimensions before
ranking and placement construction. Container Selection retains its original
opening allowance. See [Nested pinwheel calibration](palletization-logic.md#nested-pinwheel-calibration).

Hybrid Pinwheel has a separate Palletization-only eligibility policy. Existing
margin parameters must describe one attached, contiguous rectangular filler
group: nonempty staggered right-margin Brick fillers and split balanced top
rows are excluded before filler construction. An eligible core or filled
candidate must then cover at least 60% of the effective footprint. The
constructors, candidate counts, ranking, search bounds, other pattern families,
and Container Selection defaults are unchanged. See
[Hybrid pinwheel calibration](palletization-logic.md#hybrid-pinwheel-calibration)
for the geometry and the secondary relevance filter.

Perimeter-Core Mosaic has its own Palletization-only relevance policy:
`10*L*S` must cover at least 90% of the `(2*L+S)*(2*L)` motif contour and
60% of the supplied effective area. Both area comparisons run before the
ten-carton motif is constructed. Container defaults do not enable the policy.
The shared geometric fit, absolute tolerances, rotation/mirror order and all
other family policies are unchanged. The caller continues to supply the
effective dimensions including permitted overhang; the shared core does not
resolve pallet inputs. See [calibration evidence](../engineering/perimeter-core-calibration.md).

Nested Simple Lattice variants use the existing pinwheel parameter caps.
Placements come directly from the diagonal hole lattice and its boundary
completion triangles. Both contour orientations are eligible. Container
Selection completes its existing search across all permitted vertical axes
first, then spends the remaining slots of the same 192-candidate budget on
lattices. It uses the exact lattice carton count to skip layouts that cannot
beat the best quantity already found. Palletization shortlists up to four
distinct fitting layouts from each lattice family by layer count before
building stacks and checking interlock. Equal counts retain parameter order
within the shortlist. The usual Palletization ranking applies to those rows.

Before its lattice shortlist, Palletization alone rejects motifs whose
`i*j*(L-S)**2 / ((i*L+j*S)*(i*S+j*L))` exceeds the initial 20% calibration
threshold. The O(1) check lives in the Palletization engine, before sorting,
placement construction and either shortlist cap. Shared lattice geometry and
Container Selection enumeration remain unrestricted by this relevance rule.
See [hole-area calibration](palletization-logic.md#nested-simple-lattice-hole-area-calibration).

The Stage 2 paired benchmark loads the pre-migration engine from the recorded
commit and alternates original/migrated calls in one Python process. A timing
change is treated as material only when both the median relative increase is
greater than 20% and the median absolute increase is greater than 25 ms. This
combined threshold prevents sub-millisecond wrapper calls from being labelled
material while still flagging meaningful request-time regressions. Candidate
counts and ordered geometry must match before timing is reported.

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

Palletization's shared geometry propagates through the standalone tool,
Packaging Flow, the public calculator, Three.js scenes, PDF/report data, and
catalogue/manual input paths because all of those surfaces use the same
Palletization service and engine result rows.

## Regression contract

The frozen Palletization Stage 2 baseline is tied to commit
`5754ef9e82b409b93984ac4ffa0672ce55324950` and the original engine source hash.
It contains 19 geometry scenarios across 12 family/variant calls plus seven
complete analysis scenarios. It records ordered placements, occupied contours,
bounding boxes, Layer A/Layer B geometry, complete 3D stacks, engineering
metrics, result ordering and keys, interlock metadata, Three.js scenes, and
report rows.

The independent Container Stage 1 baseline records candidate order and exact
geometry hashes for the same 19 footprints plus the 14-case selection
benchmark. Fixture builders use exclusive creation and source/commit locks;
tests compare current output with checked-in data and never rewrite expected
values.

The pre-migration comparison found no differences for Block, Row, Brick, or
Centre-filled Pinwheel in the 19-case matrix. The old Stage 1 shared path did
differ from Palletization for fractional Splitrow fits and for rotated or
high-ratio Pinwheel, Hybrid Pinwheel, and Nested Pinwheel searches beyond the
12/8 Container bounds. The explicit numerical and search policies resolve
those differences without widening Container's enumeration or narrowing
Palletization's approved 30/80 coverage.

Future changes to an existing family must:

1. change the shared core rather than a consumer wrapper;
2. run both immutable consumer baselines;
3. run direct delegation checks proving Palletization still calls the public
   shared API;
4. run standalone, Packaging Flow, public calculator, Three.js, PDF,
   height/load, Splitrow, and Container Selection regressions;
5. treat any approved geometry difference as a separately reviewed behavior
   change rather than refreshing the golden fixture.
