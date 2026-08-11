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

- Sections **Current modes and accepted semantics** and **Global physical invariants** are durable behavioral contracts for the three established modes.
- **Space Evenly mode** documents the implemented fourth-mode contract.
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

### 2. Sequence Loading / Accessible Sequence (`accessible_sequence_loading`)
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

### 3. Strict Sequence Loading (`sequence_loading` legacy engine value; UI label “Strict sequence loading”)
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

### 4. Space Evenly (`space_evenly`)
Purpose: preserve the mode's full-height load target while reducing occupied
height and using more useful floor projection.

Accepted semantics:
- Space Evenly has an independent dispatch and construction path.
- Sequence controls product-row processing priority only; it creates no
  operational frontier or transition band.
- A full-height Space Evenly construction establishes the target count vector
  by original `row_index` while honoring payload, rotations, and stackability.
- A bounded ordered artificial-ceiling search chooses the first candidate that
  reproduces that complete target vector.
- Homogeneous blocks are materialized immediately into ordinary `Placement`
  objects; physical-anchor residual placement handles remaining target units.
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
- Spread the load across more of the container floor by reducing the effective usable height with an artificial ceiling.
- Use block-first construction under that ceiling.
- Preserve cargo quantity/volume as the primary objective; reduce effective height only when the same target cargo can still be packed.
- This mode is independent of Strict and Accessible Sequence frontiers.
- Sequence controls processing priority only unless a future task explicitly changes that rule.

### Space Evenly objective hierarchy
1. Preserve the full-height Space Evenly engine’s packed count vector / packed volume.
2. Find the lowest feasible artificial ceiling that can reproduce that target.
3. Subject to 1–2, prefer coherent homogeneous blocks and broad floor use.
4. Fill residual quantities with bounded physical-anchor or greedy logic that does not create artificial residual boundaries.

### Artificial ceiling search
- First run the Space Evenly block engine with full container height; record target packed quantities by row.
- Compute the theoretical lower bound as target packed volume / container floor area, raised to at least the smallest allowed target orientation height.
- Generate candidates from allowed orientation-height multiples (at most 64 layers per distinct height), pairwise allowed-height sums, top levels produced by the full-height construction, and actual container height.
- Deduplicate, sort, and retain at most 128 deterministic candidates. Search upward and select the first construction that reproduces the complete target count vector. This is an ordered search, not a binary search, because heuristic feasibility is not assumed to be monotonic.
- Avoid assuming the exact proprietary TOPS formula; implement a documented KolliPack interpretation.
- Ceiling search must be bounded and deterministic.

### Block-first construction
- A block is a homogeneous cuboid arrangement of one product in one allowed orientation: `nx × ny × nz`.
- Respect available quantity, container/free-space dimensions, effective ceiling, stackability, and payload.
- Generate at most 24 shapes per product orientation and placement iteration.
  The family combines maximum/clipped grids, six axis-priority shapes,
  low/wide single layers, length- and width-dominant strips, balanced shapes,
  and small two-unit blocks. A lone unit is reserved for residual fill.
- Score candidate blocks lexicographically by target contribution, new floor
  projection, lower resulting/block height, coherent aspect, physical face
  contact, and natural back-wall compactness.
- Generate block anchors from container walls and actual cargo faces, with at
  most 24 coordinates per horizontal axis and 16 supported height levels.
- Use existing safe geometry helpers where appropriate without changing their semantics for the three established modes.

### Residual fill
- After primary blocks, fill remaining units with a bounded physical-anchor / extreme-point-style pass under the same artificial ceiling.
- The residual filler may cross computational residual partitions if the actual geometry is collision-free and fully supported.
- Residual candidates prefer new floor projection and lower resulting height,
  followed by same-product/all-cargo contact and compact deterministic ties.

### Diagnostics and current limitations
JSON-safe result metadata includes effective/actual height, height reduction,
theoretical average height, target counts/volume/units, accepted block and
residual counts, selected-pass and total ceiling/block/residual candidate
counts.

This is a deterministic bounded heuristic, not a proof of globally minimal
height or globally optimal floor distribution. A candidate height can be
physically feasible yet missed by the retained height family, and a feasible
multi-product arrangement can be missed by greedy block choice. In either
case, the mode retains the full-height Space Evenly result rather than reducing
its target quantities.

Indicative local timings on the canonical 12032 × 2352 × 2395 mm fixture
(August 2026; diagnostic only, no CI threshold):

- 1 product / 100 units: Maximum 4.04 s; Space Evenly 0.29 s, 1/4 ceiling candidates, 48 selected-pass / 128 total block candidates.
- 2 products / 120 units: Maximum 6.09 s; Space Evenly 1.21 s, 2/5 ceiling candidates, 3,893 selected-pass / 10,395 total block candidates.
- 3 products / 170 units: Maximum 10.70 s; Space Evenly 4.80 s, 4/8 ceiling candidates, 7,087 selected-pass / 28,641 total block candidates.

Wall-clock timings vary by machine. Candidate counts are exposed for durable
bounded-search diagnostics.

## Performance principles
- Avoid millimetre scanning.
- Avoid exhaustive permutations of all items.
- Bound candidate generation per product/orientation/free-space.
- Keep automatic max-quantity behavior in mind: transport service may call `pack_container()` repeatedly during binary search.
- Benchmark representative 1-product, 2-product, and 3-product cases.

## Mode isolation rule
Space Evenly preserves these isolation rules:
- Existing Maximum Utilization coordinates/quantities must remain unchanged for regression fixtures.
- Existing Accessible Sequence coordinates/quantities must remain unchanged for regression fixtures.
- Existing Strict Sequence coordinates/quantities must remain unchanged for regression fixtures.
- Do not repurpose existing mode names.
- Add a fourth dispatch branch rather than changing existing semantics.

## Definition of done for algorithm changes
1. Focused direct engine tests added.
2. Existing relevant Django tests pass.
3. New algorithm has deterministic output.
4. No overlap, bounds, support, stackability, or payload violations.
5. Representative benchmark recorded before/after.
6. Diff reviewed specifically for cross-mode changes.
7. User-facing mode text accurately describes behavior; do not claim equivalence to proprietary TOPS internals.
