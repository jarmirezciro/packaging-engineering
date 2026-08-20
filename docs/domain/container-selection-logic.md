# Container / Box Selection Tool logic

## Purpose

Determine how many rectangular products fit in a rectangular packaging container, or rank packaging candidates for a required quantity, using allowed orthogonal orientations and the original pilot's bounded residual-space heuristic.

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

4. Compare orientation/partition candidates and choose the main subbox arrangement returned by `MainBox`.
5. Record the orientation used in the main subbox.
6. Partition the remaining rectangular space into length-, width-, and height-side leftovers without overlap.
7. Compute a valid orientation for each leftover.
8. Retain only the selected main-grid placements from the complete-container result; its provisional residual fills are not final.
9. Run one complete `MainBox` analysis independently in each of the three root residual regions.
10. Retain each child result's selected main grid and three direct residual fills, then stop at that pilot-defined depth.
11. Calculate capacity from the final placement collection and use that same collection for Matplotlib and Three.js.
12. Apply desired-quantity draw limits only to visualization; do not change the maximum-capacity calculation.

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

The exact semantic mapping of R1/R2/R3 must be read from current forms/engine and documented here before changing it.

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
then assigned. Design Mode optionally reports net-content product weight only;
container tare, total package weight, and payload metrics are not inputs or
serialized results. Single and Optimal modes keep their existing evaluation.
Selection Mode continues to use `MainBox` and its existing leftover-space logic.
The extraction preserves Container Design's existing candidate dimensions,
ordering, representative choices, render geometry, and candidate identifiers.
