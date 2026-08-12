# KolliPack Transport Container Engine — Codex Context

## Purpose
This document is durable context for Codex work on the Transport Container engine. It summarizes the accepted behavior and constraints that have emerged from iterative debugging and design work. Read this before changing `packagingapp/utils/container_tool/engine.py` or transport packing modes.

## Current authoritative code
- Engine: `packagingapp/utils/container_tool/engine.py`
- Transport service/orchestration: `packagingapp/tools/transport/service.py`
- Form mode choices: `packagingapp/forms.py` (`ContainerToolForm`)
- Standalone view: `packagingapp/views/container_tool.py`
- Transport templates: `packagingapp/templates/container_tool/`
- Three.js viewer: `static/js/transport_container_threejs_viewer.js`
- Transport visualization tests: `packagingapp/tests/test_transport_visualization.py`

Do not use a stored line count or historical copy as evidence of the current implementation. Inspect the checked-out engine and direct tests for exact call graphs and signatures.

## Authority and status

- Sections **Current modes and accepted semantics** and **Global physical invariants** are durable behavioral contracts for the established modes.
- **Space Evenly mode** documents the implemented homogeneous-block contract.
- **Maximum Utilization Floor First** documents the isolated floor-priority variant of Maximum Utilization.
- `docs/domain/transport-selection-logic.md` owns tool/service/consumer contracts and intentionally does not duplicate algorithm details.
- Handoff/task files may be more specific about one implementation session, but they must not override this document.

## Coordinate convention
- `x = 0`: closed/back wall of the transport container.
- `x = container length`: doors.
- `y`: container width.
- `z = 0`: floor.
- Backward compaction means decreasing `x`.
- Forward/door-side compaction means increasing `x`.

## Global physical invariants
Every packing mode must preserve:
1. No positive-volume overlap.
2. Every placement inside container L/W/H.
3. Allowed rotations only (`r1`, `r2`, `r3`).
4. Payload limit.
5. Stackability: non-stackable cargo must not support cargo above it.
6. Full-base support for elevated placements unless a future explicit rule changes this.
7. Deterministic results for identical inputs.
8. Quantities and product identity (`row_index`) preserved.

## Current modes and accepted semantics

### 1. Maximum Utilization (`maximum_utilization`)
Purpose: maximize loaded cargo without an operational accessibility frontier.

Accepted semantics:
- Product sequence controls processing order only.
- Later products may use valid floor, side, top, and deep residual geometry.
- No Sequence Loading transition frontier.
- No Strict Sequence full-width frontier.
- Maximum-specific residual merging removes computational boundaries between physically adjacent residual cuboids.
- Maximum may use a physical-anchor candidate for bounded requests.
- Maximum must not call the middle/strict sequence compaction or frontier logic.

Known regression case:
- EUR palletized load: 1200 × 800 × 1100, qty 20, stackable.
- Product 2: 500 × 400 × 700, qty 100, stackable.
- The long floor-side residual beside repeated EUR pallet rows must behave as a continuous physical corridor; artificial 1200 mm residual cells must not create repeating 200 mm gaps.

### 2. Maximum Utilization Floor First (`maximum_utilization_floor_first`)
Purpose: provide a directly comparable Maximum Utilization variant that prefers
lower floor layers before upper residual spaces.

Accepted semantics:
- Uses the same allowed rotations, support, stackability, payload, bounds,
  and deterministic residual rules as the other Maximum paths.
- For each product row, it first selects one homogeneous integer-grid block
  from the current real free spaces. The candidate family reuses Space
  Evenly's pure transverse geometry (`ny × nz`) and orientation math, but the
  Floor First orchestrator selects the candidate by physical `width × height`
  coverage and back-to-front placement order.
- The selected block is subtracted from the real free-space geometry. Any
  remaining units of that product are then packed beside/above that block and
  into other available side spaces using `x` strip, then upward `z` layer,
  then width `y` row order. Residuals are not moved to a single final door
  zone.
- It has no operational sequence frontier and no strict or accessible sequence
  compaction.
- It does not call Space Evenly's main-block orchestration or door-side
  residual pass. Space Evenly remains an independent mode.
- The existing `maximum_utilization` path keeps its original best-fit scoring.
  It is used only as a capacity guardrail: a floor-first candidate wins when
  capacity is tied, so this mode does not silently reproduce Maximum geometry.

The floor-first policy is a layout preference, not a global-utilization proof.
It may produce a different geometry while preserving the same feasible quantity
and physical invariants.

### 3. Sequence Loading / Accessible Sequence (`accessible_sequence_loading`)
Purpose: operational sequence loading while allowing controlled use of door-accessible residuals in the previous transition band.

Accepted semantics:
- Back-to-front progression.
- Horizontal floor/layer planning.
- Later rows may enter only supported, door-visible residuals in the previous sequence transition band plus the forward floor region.
- Deep inaccessible pockets remain closed.
- Hierarchical backward compaction is allowed here.
- Forward side-gap compaction is allowed here and runs after backward compaction so the backward pass does not undo intentional forward joining.
- This mode is allowed to reuse selected side residuals; that is a defining difference from Strict Sequence.

Regression family used during development:
- EUR palletized load cases with quantities 21, 23, 25, 27, 29 were repeatedly used as coordinate/regression guards.

### 4. Strict Sequence Loading (`sequence_loading` legacy engine value; UI label “Strict sequence loading”)
Purpose: strict operational zones separated by full-width frontiers.

Accepted semantics:
- After each product row, create a full-width frontier at that row’s `zone_end`.
- The frontier is **per product row**, not per distinct numeric sequence value. Two rows with the same sequence value remain two strict zones; sequence determines processing order, not row coalescing.
- The next row starts at or in front of that frontier across the full width.
- Do not reuse side residuals behind the frontier.
- Do not reuse top residuals behind the frontier.
- Do not reuse deep residuals behind the frontier.
- Forward side-gap compaction is not part of Strict mode because there should be no accepted side-gap placements from the preceding row.

Critical regression case:
- EUR palletized load: 1200 × 800 × 1100, qty 20, stackable, sequence 1.
- Product 2: 500 × 200 × 700, qty 100, stackable, sequence 1.
- In Strict Sequence, Product 2 must have zero placements beside Product 1. Its minimum x must be >= Product 1 full-width frontier.

### 5. Space Evenly (`space_evenly`)
Purpose: create a fast, explainable load plan with one complete homogeneous main
block per product followed by one greedy mixed leftover pass at the doors.

Accepted semantics:
- Space Evenly has an independent dispatch and construction path.
- Sequence controls product-row processing priority only; it creates no
  operational frontier or transition band.
- Each product has at most one homogeneous integer-grid main block using one
  allowed orientation.
- Main blocks are contiguous along `x` from the back wall and do not interleave
  or use another product's side/top gaps.
- Main-block selection is sequential and deterministic. It chooses at most one
  candidate for each product after reserving a cheap lower-bound length for
  later rows; it does not build a beam or Cartesian product.
- Residual units are packed only at `x >= residual_zone_start`, where
  `residual_zone_start` is the end of the final main block.
- All main blocks are completed before any leftovers are calculated.
- The leftover phase calls the existing greedy helper exactly once on a local
  full-width/full-height sub-container from `residual_zone_start` to the doors.
- Space Evenly does not perform artificial-ceiling or effective-height search;
  `space_evenly_effective_height` reports the actual container height for
  compatibility with existing consumers.
- Homogeneous blocks and residual units are materialized as ordinary
  `Placement` objects.
- Standard summary, Three.js, report, standalone, and Packaging Flow consumers
  continue to use ordinary placements.

## Important architecture lessons from previous iterations
1. Do not infer behavior from mode names; trace the exact call graph.
2. Residual-space partitions are computational, not physical. Maximum Utilization must not let artificial split planes reject a physically feasible placement.
3. Connected-component count is not sufficient to judge layout coherence; a connected arrangement may still contain visually fragmented orientation parcels.
4. Compaction must never substitute for correct space-generation semantics. Example: Strict Sequence should prevent side residual placement in the first place rather than trying to compact it afterward.
5. Never fix one mode by editing shared helpers unless the effect on the other modes is explicitly tested.
6. Prefer mode-specific wrappers/helpers when behavior differs.

## Direct engine regression baseline

The dedicated baseline is:

`packagingapp/tests/test_transport_container_engine.py`

It calls `pack_container()` directly and is independent of Three.js, HTML,
reports, and Packaging Flow. Reusable assertions cover bounds, allowed
orientations, positive-volume overlap, full-base support, stackability,
quantity accounting, payload, and determinism.

Canonical fixture settings used by the baseline:

- Internal transport dimensions: 12032 × 2352 × 2395 mm (the current
  repository SEO example transport unit).
- Maximum payload: 26500 kg.
- Unless stated otherwise: sequence 1, stackable, R1 enabled, R2/R3 disabled.
  R1 permits the two current floor rotations.
- EUR palletized load: 1200 × 800 × 1100 mm, 900 kg each.

Accepted observable regression results:

- **Maximum residual continuity:** 20 EUR loads plus 100 units of
  500 × 400 × 700 mm all pack; Maximum exposes no sequence zones/frontier and
  the protected Product 2 floor run contains no artificial periodic gap.
- **Strict per-row frontier:** with Product 2 changed to 500 × 200 × 700 mm,
  both rows still use numeric sequence 1, but the second row begins at the
  first row's full-width frontier (`x = 4800 mm` in this fixture).
- **Accessible Sequence:** the same 500 × 200 × 700 mm fixture uses supported
  transition residuals behind the Strict frontier and records both backward
  and forward compaction. It must not fall back to Strict for this case.
- **Accessible quantity family:** EUR quantities 21, 23, 25, 27, and 29,
  followed by 100 units of 500 × 400 × 700 mm, all reproduce accessible
  transition-residual use without moving behind the documented transition
  band. The harness deliberately protects geometry/invariants instead of
  inventing historical coordinates that were not fully documented.

Run it with:

```powershell
python manage.py test packagingapp.tests.test_transport_container_engine
```

An optional non-asserting timing helper is available at
`packagingapp/tests/benchmark_transport_container_engine.py`:

```powershell
python -m packagingapp.tests.benchmark_transport_container_engine
python -m packagingapp.tests.benchmark_transport_container_engine --space-only
python -m packagingapp.tests.benchmark_transport_container_engine --all-modes
```

## Engine evolution direction
The preferred long-term direction is a structured construction engine rather than pure item-by-item greedy packing:
1. Generate homogeneous cuboid blocks from products/orientations.
2. Place large useful blocks into physical free space.
3. Use smaller blocks and/or physical-anchor greedy logic for residual quantities.
4. Run safe mode-specific compaction/regularization.
5. Validate support, stackability, overlap, bounds, payload.

Do not attempt a wholesale refactor and a new algorithm in the same change unless explicitly requested. Preserve current production behavior behind existing mode dispatch.

## Space Evenly implementation
Mode name: `space_evenly`.

High-level intent:
- Keep every product together in one regular main cuboid where possible.
- Arrange main blocks sequentially from the back wall toward the doors.
- Put leftover units from all products in one mixed door-side residual zone.
- Prefer regular, lower main blocks over fragmented high-utilization mosaics.
- This mode is independent of Strict and Accessible Sequence frontiers.
- Sequence controls processing priority only unless a future task explicitly changes that rule.

### Space Evenly objective hierarchy
1. Maximize the complete cuboid's transverse `ny × nz` utilization.
2. Within that transverse choice, maximize complete quantity/volume.
3. Reserve enough length for later product rows.
4. Preserve sequence priority, payload, rotations, support, stackability,
   bounds, collision rules, quantity identity, and deterministic output.

### Target quantities
- Product rows retain the existing sequence-priority ordering.
- The analytic target is bounded by requested quantity, payload, remaining
  container volume, and the product's best single-product orientation grid.
- This is not a preliminary complete packing run.
- If the bounded architecture cannot realize all target quantities, the best
  retained valid state is returned and unplaced quantities are reported.

### Main-block candidate generation
- A candidate is one homogeneous cuboid grid `nx × ny × nz` for one product
  and one orientation returned by `allowed_orientations(...)`.
- Width/height counts are sampled around `1`, maximum, maximum minus one,
  one-half maximum, and three-quarters maximum.
- `nx` is derived analytically from target quantity and a small set of
  quantity/length fractions; there is no complete `nx` loop.
- Non-stackable products use `nz = 1`.
- Candidates are deduplicated, ranked by transverse utilization before complete
  quantity, and capped at:

```text
SPACE_EVENLY_CANDIDATES_PER_PRODUCT = 12
```

### Main-block selection
- Products are processed in the existing sequence-priority order.
- For each row, candidates that exceed the remaining length or the cheap
  later-product volume reservation are rejected.
- The largest remaining complete cuboid is selected once, then the x frontier
  is advanced contiguously.

### Main-block placement
- Selected blocks are placed contiguously from `x = 0`.
- Blocks use the deterministic `y = 0` lateral convention.
- Every product has at most one main block.
- Main blocks never use another product's side/top/deep residual geometry.

### Residual fill
- `residual_zone_start` is the maximum main-block `x_end`.
- Only target leftovers enter the local greedy pass; payload remaining after
  the main blocks is transferred to that sub-container.
- Local coordinates start at `x = 0` and are translated by
  `residual_zone_start`, so no leftover can return behind the frontier.
- The existing greedy helper validates bounds, collision, support, stackability,
  rotations, payload, and quantity identity. Maximum Utilization's own call
  path and result are unchanged.

### Diagnostics and current limitations
JSON-safe result metadata includes main block summaries/count/units,
`main_blocks_end_x`, residual-zone start and residual counts,
effective/actual/theoretical height, target counts/volume/units, retained block
candidate count, and the one greedy residual evaluation count.

This is a deterministic bounded heuristic, not a proof of global utilization.
The one-main-block-per-product rule deliberately rejects interleaving, multiple
main blocks for one product, and use of side/top gaps behind the residual
frontier. A physically feasible irregular mosaic can therefore load more units
than Space Evenly. The engine reports unplaced quantities rather than expanding
into an exhaustive fallback search.

Indicative local timings on the canonical 12032 × 2352 × 2395 mm fixture
(August 2026; diagnostic only, no CI threshold):

- 1 product / 100 units: 0.006 s; 12 candidates; one greedy pass.
- 2 products / 120 units: 0.011 s; 24 candidates; one greedy pass.
- 3 products / 170 units: 0.020 s; 36 candidates; one greedy pass.
- 4 products / 200 units: 0.030 s; 48 candidates; one greedy pass; all 200
  units loaded.
- Reported 12039 × 2362 × 2692 mm case / 1228 units: approximately 0.13 s;
  48 candidates; 1180 main-block units and 48 leftovers sent to the greedy
  pass; all 1228 units loaded.

Wall-clock timings vary by machine. Candidate counts are exposed for durable
bounded-search diagnostics.

## Performance principles
- Avoid millimetre scanning.
- Avoid exhaustive permutations of all items.
- Bound candidate generation at 12 complete cuboids per product row.
- Keep Space Evenly to N sequential selections plus one residual greedy pass.
- Keep automatic max-quantity behavior in mind: transport service may call `pack_container()` repeatedly during binary search.
- Benchmark representative 1-product, 2-product, and 3-product cases.

## Mode isolation rule
Space Evenly preserves these isolation rules:
- Existing Maximum Utilization coordinates/quantities must remain unchanged for regression fixtures.
- Maximum Utilization Floor First remains an isolated comparison path and must not change the existing Maximum Utilization path.
- Existing Accessible Sequence coordinates/quantities must remain unchanged for regression fixtures.
- Existing Strict Sequence coordinates/quantities must remain unchanged for regression fixtures.
- Do not repurpose existing mode names.
- Add an explicit dispatch branch rather than changing existing mode semantics.

Future second iteration only: compare deterministic left-to-right and
right-to-left lateral construction. No lateral-direction search is part of the
current mode.

## Definition of done for algorithm changes
1. Focused direct engine tests added.
2. Existing relevant Django tests pass.
3. New algorithm has deterministic output.
4. No overlap, bounds, support, stackability, or payload violations.
5. Representative benchmark recorded before/after.
6. Diff reviewed specifically for cross-mode changes.
7. User-facing mode text accurately describes behavior; do not claim equivalence to proprietary TOPS internals.
