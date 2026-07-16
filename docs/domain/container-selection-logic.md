# Container / Box Selection Tool logic

## Purpose

Determine how many rectangular products fit in a rectangular packaging container, or rank packaging candidates for a required quantity, using allowed orthogonal orientations and recursive use of leftover rectangular regions.

## Established engine model

The project’s box-selection algorithm uses:

- product dimensions `(L, W, H)`;
- container usable dimensions `(Lc, Wc, Hc)`;
- rotation controls `R1/R2/R3`;
- six orthogonal product orientations, filtered by allowed rotations;
- a `MainBox` calculation that selects a best main rectangular subbox/grid;
- up to three leftover regions along length, width, and height;
- recursive packing of valid leftover regions;
- bounded recursion for safety;
- separate fast quantity calculation and rendering.

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
8. Recurse into positive leftover regions until no product fits or the safety depth is reached.
9. Sum placements/counts without double-counting.
10. Apply desired-quantity draw limits only to visualization; do not change the maximum-capacity calculation.

## Current implementation notes

A supplied render path used:

- recursion depth limit `max_depth=6`;
- a mutable `remaining=[N]` draw limit for Optimal mode;
- `render_style="debug"` with subbox overlays;
- `render_style="clean"` with an open RSC-style box shell;
- server-safe matplotlib `Agg` backend;
- output below `MEDIA_ROOT/box_selection/`.

Verify these values and paths in the current branch.

## Rotation restrictions

A critical rule from prior fixes:

> Rotation restrictions are global and must apply to every box, main subbox, leftover subbox, recursive call, and render placement.

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
- recursive leftover decomposition is a heuristic and is not a proof of global 3D-bin-packing optimality;
- recursion depth is a safety/complexity trade-off;
- the RSC flaps are visual only unless explicitly used in usable dimensions.

## Invariants

- no product crosses container bounds;
- no placements overlap;
- reported count equals placement count when full placements are generated;
- all orientation dimensions are positive;
- no zero-step numpy range or recursion loop;
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
- recursion terminates on zero/near-zero dimensions;
- desired draw limit does not change maximum count;
- selected Top-5 result controls the exported image;
- product plus packaging weight respects max payload;
- standalone, Flow, and report counts agree for equivalent single-product fixtures;
- Multi-product Container Selection reproduces the same placements/graphics for an equivalent one-row fixture;
- clean-render and product-detail improvements appear in the multi-product result and report where applicable.
