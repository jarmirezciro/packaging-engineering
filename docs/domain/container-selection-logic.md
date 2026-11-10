# Container / Box Selection Tool logic

## Purpose

Determine how many rectangular products fit in a rectangular packaging container, or rank packaging candidates for a required quantity, using allowed orthogonal orientations, the original pilot's bounded residual-space heuristic, and independently validated shared mosaic candidates.

## Established engine model

The project’s box-selection algorithm uses:

- product dimensions `(L, W, H)`;
- container usable dimensions `(Lc, Wc, Hc)`;
- rotation controls `R1/R2/R3`;
- six orthogonal product orientations, filtered by allowed rotations;
- a `MainBox` calculation that selects a best main rectangular subbox/grid;
- up to three leftover regions along length, width, and height;
- one complete `MainBox` analysis in each of the root result's three leftover regions;
- a shared authoritative placement collection for quantity and rendering.

A supplied engine version imported:

```text
packagingapp.utils.box_selection.box_selection_tool_arrays_2_origin_coordinates.MainBox
```

and exposed a fast `compute_max_quantity_only(...)` path plus `run_mode1_and_render(...)`.

## Multi-product Container Selection consumer

Multi-product Container Selection consumes the same authoritative Container/Box geometry rules and, where applicable, the same normalized placement contract, renderer, result labels, catalogue components, and report components as standalone Container Selection.

Its multi-product-specific responsibilities may include:

- accepting several product rows and quantities;
- applying the current mixed-product loading sequence or allocation heuristic;
- tracking remaining container space and remaining quantities across products;
- aggregating counts, volume, weight, and feasibility;
- presenting both per-product placements and the combined result.

Those responsibilities may require a dedicated orchestration layer, but they do not justify an outdated copy of the base renderer or UI. When standalone Container graphics, clean/debug render modes, product-detail rendering, controls, labels, units, or PDF composition change, explicitly assess and update Multi-product Container Selection in the same coherent task.

**Repository verification required:** inspect and document the current product ordering, mixed-product placement heuristic, tie-breaking, leftover-space reuse, and whether row order affects the result. Do not imply global mixed 3D-bin-packing optimality unless the engine proves it.

## Calculation flow

1. Validate positive product and container dimensions.
2. Enumerate every orientation allowed by `R1/R2/R3`.
3. For a region, compute integer grid counts:

```text
nx = floor(region_length / oriented_product_x)
ny = floor(region_width  / oriented_product_y)
nz = floor(region_height / oriented_product_z)
quantity = nx × ny × nz
```

The implementation uses a shared bounded-ULP floor helper for these counts.
It accepts a next integer only when the required canonical-millimetre extent is
within a small representation-error bound of the available extent; a genuine
physical shortfall remains a floor result. The same helper is used by
`MainBox`, residual candidate calculations, and final placement materialization
so reported capacity and rendered geometry cannot diverge at exact converted
multiples.

4. Compare orientation/partition candidates and choose the main subbox arrangement returned by `MainBox`.
5. Record the orientation used in the main subbox.
6. Partition the remaining rectangular space into length-, width-, and height-side leftovers without overlap.
7. Compute a valid orientation for each leftover.
8. Retain only the selected main-grid placements from the complete-container result; its provisional residual fills are not final.
9. Run one complete `MainBox` analysis independently in each of the three root residual regions.
10. Retain each child result's selected main grid and three direct residual fills, then stop at that pilot-defined depth.
11. Independently evaluate the shared 2D mosaic-pattern library for each permitted vertical-orientation family and repeat valid layers within container height.
12. Keep the legacy result on every quantity tie; select Mosaic only for a strictly greater independently validated placement count.
13. Calculate capacity from the selected final placement collection and use that same collection for Matplotlib and Three.js.
14. Apply desired-quantity draw limits only to visualization; do not change the maximum-capacity calculation.

The shared Mosaic architecture, supported pattern families, resource bounds,
and Stage 2 Palletization handover are documented in
`shared-mosaic-patterns.md`. `MainBox` and the legacy pilot sequence remain
unchanged and independently testable through `calculate_legacy_placements()`.

The shared Perimeter-Core Mosaic is available to the bounded candidate search
as an additive family. A same-quantity ten-carton candidate therefore remains
available for geometry and rendering validation, while the legacy result still
wins ties under the established selection contract.

The root `MainBox.max_quantity` already includes provisional direct residual fills. It must not be added to the child results because those provisional fills are replaced by the complete child analyses. The final quantity is the root main grid plus the three complete child solutions.

## Current implementation notes

A former render path used:

- recursion depth limit `max_depth=6`;
- a mutable `remaining=[N]` draw limit for Optimal mode;
- a second solve beginning from the complete container during rendering;
- Three.js suppression of the recursive placements to avoid duplicate display;

The authoritative Selection Mode engine now uses:

- one root `MainBox` call and up to three Level 1 `MainBox` calls;
- explicit placements carrying origin, orientation, level, and region type;
- `len(placements)` for both fast capacity ranking and rendered result capacity;
- placement slicing for Optimal-mode draw limits;
- `render_style="debug"` with subbox overlays;
- `render_style="clean"` with an open RSC-style box shell;
- server-safe matplotlib `Agg` backend;
- output below `MEDIA_ROOT/box_selection/`.

## Rotation restrictions

A critical rule from prior fixes:

> Rotation restrictions are global and must apply to every box, main subbox, leftover subbox, Level 1 call, and render placement.

Do not apply `R1/R2/R3` only to the first region while allowing unrestricted orientations in leftovers.

The mapping below is verified against the current authoritative orientation
helper and Container Assistant adapter; re-verify both before changing it.

### Restriction

**Current implementation note:** in Container Selection, a restriction is a
server-enforced condition that removes an otherwise possible orientation or
candidate from consideration. R1/R2/R3 are rotation restrictions; positive
dimensions, usable internal bounds, and the selected source/mode impose other
feasibility restrictions. Payload remains informational for Container capacity
in the current implementation and must not be described as a capacity
restriction.

### R1, R2, and R3

**Current implementation note:** the authoritative orientation helper maps the
controls to the product dimension permitted on the vertical container axis:

- **R1:** product length may be vertical;
- **R2:** product width may be vertical;
- **R3:** product height may be vertical.

Disabling a control removes both orthogonal orientations with that product
dimension vertical. The same mapping applies to the main region, every residual
region, Design candidates, standalone Container Selection, and Packaging Flow.

## Modes

### Single mode

- chosen container/packaging;
- return maximum quantity;
- show selected orientation/placements and utilization;
- optionally apply product/packaging weight and max payload.

### Optimal mode

- evaluate catalogue candidates using the fast quantity path;
- filter infeasible options;
- rank, commonly as Top 5;
- render the selected candidate, not a different default candidate;
- if desired quantity is lower than capacity, the clean image may draw only the desired quantity while still reporting maximum capacity separately.

## Product dimensional allowance

Container Selection accepts optional `product_allowance_l`,
`product_allowance_w`, and `product_allowance_h` inputs. The shared
`packagingapp.tools.product_dimensions` helper converts those values to
canonical millimetres and adds each allowance once to its corresponding
nominal product axis before Design, Single, Optimal, or capacity-only engine
entry points are called. The existing packing algorithms, rotation mapping,
container thickness calculation, and ranking remain unchanged.

Nominal dimensions remain the catalogue/manual physical values used by the
product Three.js scene and product detail. Effective dimensions are transient
packing inputs and are exposed separately in JSON-safe reports/exports. Manual
and catalogue allowances use the active shared product-dimension unit; the
catalogue picker converts its canonical millimetre dimensions for display.
Missing or blank allowance fields normalize to zero, preserving older sessions
and submissions.
Container allowances may be positive, zero, or negative. Every resulting
effective axis must be finite and strictly positive before packing starts.

## Assumptions

- product and packaging are axis-aligned rectangular cuboids;
- placements are orthogonal, not arbitrarily angled;
- no deformation, nesting, or irregular shape interaction;
- usable internal dimensions are supplied correctly;
- the bounded residual-space decomposition is a heuristic and is not a proof of global 3D-bin-packing optimality;
- calculation stops after each Level 1 `MainBox` result's direct residual fills;
- the RSC flaps are visual only unless explicitly used in usable dimensions.

## Internal and external carton dimensions

Container Selection and Container Design always use usable **internal** carton
dimensions for fit, capacity, orientation, candidate generation, and Design
ranking. External dimensions are result metadata for physical logistics and do
not change those calculations.

The shared Container dimension resolver produces one complete external L/W/H
triplet using this precedence:

1. a complete, positive catalogue external-dimension triplet;
2. internal length/width plus twice the actual box thickness, and internal
   height plus four times the actual box thickness;
3. the same axis-specific formula using the centralized 4 mm default
   thickness.

Incomplete catalogue external dimensions are never mixed with calculated
axes. When the 4 mm default is required, the JSON-safe result contract marks
the thickness as assumed so Detailed Analysis and downstream consumers can
explain the estimate.

## Carton tare and corrugated-board selection

Container Selection exposes an optional active `CorrugatedBoardConstruction`
choice. New selections use the construction's stable code; older numeric-ID
and legacy custom-grammage session values remain readable without being
offered as new catalogue choices. The board choice supplies tare grammage and
a resolved finished-board caliper. Caliper priority is a valid construction
`caliper_mm`, then the lowest-ECT active `CorrugatedECTReferenceGrade` for the
construction's flute family, then unavailable. Nominal flute height is never
used as caliper.

Caliper, grammage, carton tare, payload and product weight support independent
calculation-only overrides in Single (manual or catalogue), Design and Optimal.
Each has an explicit override flag and a contextual **Restore source** action.
Design requires an explicit tare override flag, including for a deliberate zero.
Otherwise each candidate resolves its own tare from its internal dimensions and
the current board grammage. Advanced Parameters displays the selected
candidate's estimate or unavailable state. The estimate belongs to the result
and is omitted from the editable tare submission and saved input configuration.
Catalogue objects remain read-only. Non-overridden values resolve again on the
server, so a rounded imperial display cannot overwrite canonical values. Legacy
thickness-only sessions and legacy custom grammage remain readable. The
optional input named `combined_grammage_g_m2` follows the active container unit
system at the form boundary: g/m² for metric length units and lb/MSF for inches
or feet. Canonical service/result values remain g/m². The areal-density factor
is `1 lb/MSF = 4.8824276 g/m²`.

A new manual Design configuration selects stable construction code
`FEFCO_C_175_140_175` from the shared catalogue. Its KL175/RF140/TL175 single-wall
C-flute construction supplies 560.2 g/m² and reference caliper 4.08 mm. These
values are reference assumptions until the user explicitly selects a board.
They are not generic defaults for other C-flute boards. Existing sessions
and explicit no-material selections are preserved. The 4 mm legacy external
size fallback is a geometry assumption only, never evidence of grammage/tare.

Finished catalogue cartons have optional `corrugated_construction`,
`combined_grammage_g_m2`, and `carton_style` fields. Existing rows require no
backfill. Effective properties resolve independently for each selected SKU:

- Caliper/grammage: explicit current-analysis override, then SKU property, then
  linked construction, then the agreed C reference for an eligible corrugated
  RSC, then unavailable. An explicitly selected analysis board may supply the
  construction baseline without replacing measured SKU properties. Complete
  catalogue external dimensions remain authoritative after a caliper override.
- Tare: explicit current-analysis override, then non-null `part_weight` (kg
  converted to g), then the existing material estimate for `BOX` with confirmed
  `carton_style="0201"`, valid internal dimensions and effective grammage, then
  unavailable. `BOX` alone does not confirm RSC geometry. Explicit plastic,
  wood or metal material descriptions do not receive a corrugated assumption.
- Product weight: current-analysis override, then catalogue `Product.weight`
  converted once from kg. Missing product mass never blocks geometry.

Changing grammage does not replace an actual SKU tare. Reference-material
estimates say **Estimated from assumed material data**. A caliper alone cannot
provide grammage or tare. No analysis override saves a catalogue object or
requires a schema migration.

Manual cartons use explicit `box_weight` first, otherwise effective grammage
and the established FEFCO 0201 geometry. Both manual and catalogue estimates
call `calculate_rsc_carton_tare()`, which delegates to the existing geometry
provider and `calculate_material()` including their joint/flap defaults.
Caliper does not determine grammage. Each Top 5 candidate resolves its own
material properties and tare; ranking and packing are unchanged. Form/session
override targets identify `catalogue:<id>` or `manual`. Rerunning the same item
preserves its overrides; selecting another item clears the previous scope.

Product keeps dimensions, quantity where applicable, the existing viewer and
rotation controls in its primary area. The existing dimensional-allowance
Advanced component also contains product mass and visualization-only shape.
Container keeps each mode's existing geometry/catalogue controls and action,
followed by a collapsed Advanced section: caliper/grammage, board construction,
then tare/payload. Collapsing never disables or clears inputs. Open state and
unit tokens are prefixed per Flow step; validation errors expand their section.
Edits mark calculated results stale and disable acceptance/PDF actions until
recalculation, including the Flow report link.

The compact result shows quantity, efficiency and complete gross weight, or
**Contents weight** when only net mass is known. Detailed analysis contains
net mass, tare, gross mass, caliper/grammage and their provenance. Missing tare
is `None`, never zero. PDF reports consume the same analysis values.

Container Flow payloads expose JSON-safe `weight_status` values `gross_known`,
`gross_estimated`, `net_only`, and `unknown`, plus separate
`net_content_weight_g`, `carton_tare_g`, tare source and material provenance.
Accepted results also retain a versioned `effective_specification`: original
product/packaging/construction identifiers, effective canonical dimensions and
material properties, baseline/override sources, tare, net/gross mass, payload,
weight status and packed quantity. Pallet and transport outputs carry this
snapshot as `upstream_packaging_specification` without reloading SKU defaults.
Changes to the accepted specification invalidate dependent Flow results; the
accept action recalculates submitted Container fields before accepting them.
Only complete gross mass populates `weight_kg` and its derived `weight_g`.
Palletization clears stale inherited weight and runs geometry without pallet
load/bottom-load constraints when upstream mass is incomplete, with an explicit
message and unavailable weight metrics. Transport uses its existing numeric
zero input only as a geometric placeholder for unknown inherited mass; its
Flow summary and output mark gross mass and payload utilization unavailable.
Neither adapter changes its packing engine. Estimated tare is added once.

Catalogue CRUD and metric-only Excel import/export include the optional fields;
construction references use stable codes in spreadsheets. Older spreadsheets
that omit new columns preserve existing SKU material data. Imports are atomic.

Multi-product Container was assessed: it remains a catalogue-driven capacity
and ranking surface, using canonical internal dimensions and actual SKU weight
metadata; it has no manual board form or gross-weight propagation contract.
The public Container calculator uses the same form/partials/service as the
standalone tool. Three.js geometry is unchanged.

## Invariants

- no product crosses container bounds;
- no placements overlap;
- reported count equals placement count when full placements are generated;
- all orientation dimensions are positive;
- no zero-dimension placement or duplicate coordinate;
- all candidate results are deterministic for the same inputs;
- manual/catalogue/Flow/Multi-product Container consumers use the same authoritative service rules and rotation policy where the operation is shared;
- a graphics or presenter upgrade cannot leave Multi-product Container Selection on a legacy renderer without an explicit documented exception.

## Visualization rules

- Clean customer render: open box shell, products visible, no axes/grid/debug subboxes.
- Debug render: axes and translucent subbox overlays are permitted.
- Base product detail: show original L/W/H as entered, even when placements are rotated.
- Include the base product representation in detailed result and PDF where supported.

## Test cases to retain

- each of six orientations is best in at least one fixture;
- every rotation restriction blocks the corresponding orientation in both main and leftover regions;
- exact fit;
- no fit;
- a leftover region improves count over uniform-only packing;
- zero/near-zero residual dimensions produce no placement;
- desired draw limit does not change maximum count;
- selected Top-5 result controls the exported image;
- product plus packaging weight respects max payload;
- carton tare uses each Design candidate's dimensions and selected grammage;
- explicit analysis tare, catalogue tare, calculated eligible-box tare, and unavailable
  weight sources follow the same precedence in Single, Optimal, Design, and
  Packaging Flow cases;
- unknown product weight does not turn carton tare into gross weight;
- CRATE/CONTAINER/TRAILER catalogue rows do not receive an RSC material
  estimate;
- reference caliper resolves for A/B/C/E/F/N/EB/BC families without inferring
  ECT or using nominal flute height;
- metric and imperial material labels preserve the canonical grammage and
  caliper through unit changes;
- an explicit thickness override changes external dimensions but not material
  grammage or tare, and remains intact through Full Packaging inheritance;
- standalone, Flow, and report counts agree for equivalent single-product fixtures;
- Multi-product Container Selection reproduces the same placements/graphics for an equivalent one-row fixture;
- clean-render and product-detail improvements appear in the multi-product result and report where applicable.

## Design Mode

Container Design Mode and Bag Design Mode use the same canonical arrangement
generator in `packagingapp/utils/package_design_arrangements.py`, including the
shared smooth-quantity and prime-factor distribution helpers. It distributes
the design quantity over three axes to enumerate every ordered rows x columns x
layers grid. Permitted
orientations come from the existing authoritative R1/R2/R3 mapping in
`box_selection_tool_arrays_2_origin_coordinates.allowed_product_orientations`.

Each candidate's required internal rectangular bounding box is the grid count
multiplied by the oriented product dimensions. The RSC remains a browser visual
representation; it is not part of the bounding-box calculation. Horizontal
dimensions are normalized so `length >= width` while height remains the vertical
axis. Rows/columns, product X/Y dimensions and coordinates, and the RSC scene are
rotated with that normalization. Candidates are grouped by the final canonical
key `(length, width, height)` at six-decimal scene precision. Different heights
remain different designs. The retained representative uses the authoritative
orientation order, then the smallest normalized `(rows, columns, layers)` tuple,
then generation order.

Only after grouping are candidates ranked by cubicity
(`min(L, W, H) / max(L, W, H)`) descending, additional capacity ascending,
internal volume ascending, and a stable canonical tie-breaker; ranks and IDs are
then assigned. Design Mode optionally reports net-content product weight;
when a manual/carton-eligible corrugated material or authoritative tare is
available, it also reports the candidate-specific empty-carton tare and gross
carton weight. Tare is a derived result, not a Design ranking input, and
payload metrics remain outside Design. Single and Optimal modes keep their
existing evaluation.
Selection Mode continues to evaluate `MainBox` and its existing leftover-space
logic as the mandatory legacy baseline. It also evaluates shared Mosaic
candidates independently; only a strictly larger valid Mosaic may replace the
legacy placement collection, and legacy retains every tie.
The extraction preserves Container Design's existing candidate dimensions,
ordering, representative choices, render geometry, and candidate identifiers.

### Design quantity and additional capacity

**Current implementation note:** Design Mode first raises the requested
quantity to the smallest quantity at or above it whose prime factors are limited
to 2, 3, and 5. That supported **design quantity** can be distributed into the
regular three-axis factor grids used by the shared arrangement generator.
**Additional capacity** is exactly:

```text
design quantity - requested quantity
```

It describes the extra positions created by that supported regular-grid
quantity. It is not spare capacity discovered in a selected catalogue carton.

### Cubicity

**Current implementation note:** Container Design cubicity is the shape-balance
ratio of a generated candidate's internal bounding dimensions:

```text
min(internal length, internal width, internal height)
----------------------------------------------------
max(internal length, internal width, internal height)
```

The ratio is between 0 and 1. Values nearer 1 identify a more cube-like bounding
box and rank ahead of less balanced candidates before additional capacity and
volume tie-breakers. Cubicity is not volume utilization and does not prove
material efficiency, manufacturability, strength, protection, or overall
packaging quality.

### Design efficiency

**Current implementation note:** the user-visible Design efficiency is `1.0`
(100%) because each generated candidate is the exact axis-aligned bounding box
of its regular product grid. Within that idealized cuboid model, the grid fills
its generated bounding volume without geometric voids. The metric does not
include board thickness, closures, manufacturing allowances, cushioning,
strength, product protection, or other real-world packaging requirements.
