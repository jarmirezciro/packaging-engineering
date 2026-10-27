# KolliPack Transport Container Engine — Balanced Spread and Progressive Fill DGFE

## Status and authority

This is the technical deep dive for the current Transport Container calculation
engine and the checked-out repository baseline (August 2026). The authoritative
implementation is:

`packagingapp/utils/container_tool/engine.py`

The active engine contains four isolated deterministic modes: the approved
baselines **Balanced Spread with V1 Product Blocks and Residual Frontier Closure
V2** and **Progressive Fill with DGFE**, plus their opt-in **Mixed Cargo
Infill** variants. The canonical identifiers are `space_evenly`,
`front_to_back`, `space_evenly_infill`, and `front_to_back_infill`.
These backend values are deliberately retained for saved configurations,
session state, requests, exports, diagnostics, and regression fixtures. The
product-facing names are **Balanced Spread** (formerly Space Evenly) and
**Progressive Fill** (formerly Load Front-to-Back); `balanced_spread` and
`progressive_fill`, including their infill variants, normalize to the retained
canonical values.
Progressive Fill retains `maximum_utilization`,
`maximum_utilization_floor_first`, `front_to_back_blocks`, and
`load_front_to_back` as input compatibility aliases only. Its baseline internal
strategy remains `front_to_back_blocks`. The transport service, forms, views, templates,
serializers, and tests are supporting consumers and must be checked against
the engine when behavior changes.

### Max quantity service boundary

The UI's **Max qty?** option is a service-level caller of the selected packing
mode; it is not a fifth engine mode and does not alter Product Block or residual
semantics. The service derives a safe physical upper bound from enabled
orientations, volume, payload, and fixed-row reservations. A lone
non-stackable row also uses the safe floor-area limit; that limit is not applied
when another requested row could provide elevated support. The service then
evaluates requested quantities in descending order with
the real engine and selects the first request for which all required rows are
fully packed. Multiple automatic rows remain ordered: each resolved row becomes
fixed input to the next.

This search must not use binary search. Engine feasibility can be non-monotonic
with respect to the request because synchronized Product Blocks are committed as
whole bounded constructions. For example, a partial request can leave a unit
unplaced while the next complete block multiple fits. The service search is
deterministic, capped at 5,000 candidate units, and contains no dimension- or
quantity-specific fixture rules. The four packing modes and their isolated
behavioral contracts remain unchanged.

`packagingapp/utils/container_tool/engine_legacy.py` is retained historical code.
It is not the current algorithm specification and is not imported by the active
engine. A requested mode other than the four canonical modes or a recognized
compatibility alias returns a graceful unsupported result with no placements.

## Progressive Fill with DGFE

Progressive Fill reuses the Balanced Spread normalizer, product ordering,
R1/R2/R3 orientation families, Product Block candidate generation and ranking,
block materialization, payload checks, and placement structures. Its distinct
orchestration is:

```text
complete Product Block
→ current-product orientation × four residual base candidates
→ derive each candidate's actual Pi residual X footprint
→ preserve Native and DGFE Extended family outcomes
→ all-orientation next-product evaluation inside the Native footprint
→ bounded Row-First next-product population
→ deferred-gravity settlement where applicable
→ final physical validation and extension-value comparison
→ select the bounded transition winner
→ close frontier
→ next product's complete Product Block
```

When a next product exists, every enabled current-product orientation is paired
with exactly four strategies: deferred Top-Down Row First, deferred Top-Down
Column First, Bottom-Up Row First, and Bottom-Up Column First. Residual
construction is quantity-agnostic and uses one orientation per candidate.
Top-Down candidates reserve real three-dimensional cuboids from the ceiling;
the reserved cuboids are collision obstacles, not temporary supports.

Each orientation/strategy base preserves two isolated family outcomes. The
**Native Frontier Candidate** ends at the actual Pi residual X footprint:

```text
D_pi = max(Pi placement x + Pi placement length) - frontier_start_x
```

This is measured from materialized candidate geometry, so residuals spanning
multiple X slices are handled without assuming that one orientation length is
the complete footprint. The **DGFE Extended Candidate** keeps the established
bounded envelope: every Pi+1 X row intersecting Pi's projection plus the first
fully clean re-synchronization row. The extension never mutates or erases its
paired Native result.

The established all-orientation next-product evaluator remains authoritative.
It evaluates the exact residual frontier and selects the incoming orientation
using the existing quantity, width-utilization, preferred-orientation, and
stable tie rules. The selected next product then populates Bottom-Up Row First
through every valid local position. Native population is bounded by `D_pi`;
DGFE population uses the intersecting-plus-first-clean-row envelope. A partial
row does not terminate a later clean row.

After next-product population, a deferred residual may move only in negative Z.
X, Y, and orientation remain fixed. Settlement processes lower reserved units
first, requires a collision-free vertical path, and accepts complete base
coverage from the union of coplanar stackable supports. The virtual state is
never scored or committed; bounds, overlap, support, stackability, and payload
are validated on the final settled state.

For a valid Native/Extended pair, extension value is measured only over its
additional X prism:

```text
D_extra = D_extended - D_native
V_extra = V_extended - V_native
marginal_efficiency = V_extra / (D_extra × container_width × container_height)
```

### Frontier efficiency

**Current implementation note:** frontier efficiency is the packed product
volume inside one bounded local residual-frontier prism divided by that prism's
volume:

```text
frontier_efficiency = frontier_packed_volume
                      / (frontier_depth × container_width × container_height)
```

It is a Transport candidate-comparison metric for that local frontier, not the
overall transport-unit utilization and not Container Design efficiency. DGFE's
separate marginal efficiency measures only the extra packed volume divided by
the additional X prism beyond the paired Native frontier.

The benchmark is the transverse utilization of the normal Pi+1 Product Block
selected by the shared generator and selector for the quantity, payload, and
length remaining after Native. DGFE remains eligible only when its marginal
efficiency exceeds that benchmark by tolerance. An effective tie prefers
Native. If no regular block is feasible, a valid extension that adds volume
remains eligible. If Native cannot reach a valid settled physical state but its
paired DGFE outcome can, the valid DGFE outcome remains eligible.

Candidate ranking applies validity, maximum Pi residual quantity, minimum
actual Pi residual X footprint, paired Native-versus-extension eligibility,
local frontier efficiency, useful Pi+1 quantity, and smaller total envelope
depth in that order. Effective ties prefer Row First, Bottom-Up, and stable
orientation order. The last product retains its established Bottom-Up Row-First
residual behavior without look-ahead. A committed frontier is never reopened by
later products. There is no global residual-at-the-end phase, free-space tree,
lateral gravity, compaction, or legacy solver import. All products remain
forced to sequence `1` and use the same deterministic size ordering as Space
Evenly.

## Mixed Cargo Infill variants

The two infill variants preserve their parent macro orchestration and add one
shared constructive closure over each bounded local product/frontier window.
Balanced Spread closes a current product's contiguous span after all of its
approved complete blocks are committed, and then closes each committed
Balanced Spread residual frontier in its own X window. Progressive Fill closes
after the current product's complete blocks and its approved Native/DGFE
transition are committed. Every window is fixed in X and is never reopened
after the phase is closed. Residual-frontier candidate selection is completed
before its optional side closure; side infill never changes the winning
candidate, depth, or frontier score.

Within that window, side residuals are derived from the actual committed
placement geometry. X breakpoints come from the window edges and every
intersecting placement's `x`/`x + l`; each X slab is complemented against the
projected occupied Y intervals. The complements are floor-to-ceiling spaces:

```text
x = slab_start ... slab_end
y = each free interval in 0 ... container width
z = 0 ... container height
```

Only complete-face-compatible neighbours are merged. A Product Block boundary
is therefore computational only: a physically continuous residual can span
multiple blocks, and a partial filler leaves its unused X tail for the next
local closure iteration. Z is intentionally ignored when projecting occupied
XY footprints; this V1 closure solves lateral side spaces, not top cavities.
Mixed Cargo Infill then runs a separate supported-top closure in the same fixed
X window. It collects coplanar top planes from actual stackable placements,
coordinate-compresses the support union and any cargo above that plane, and
emits only roof-clear rectangles. Different support heights never merge;
complete-face-compatible atomic cells may merge within one plane. Top fillers
reuse the Product Block candidate generator and are physically validated
against local committed placements, with bottom-up re-derivation after every
committed block. The closure order is therefore side first, supported top
second, then window close.

Top closure may evaluate the current/anchor product when its remaining quantity
is positive; it competes with the existing permitted later-product set under
the same sequence, payload, orientation, support, overlap, and bounds rules.
Side closure continues to exclude the current anchor product.

The filler reuses the active Product Block candidate generator inside each
derived space. It selects one product/candidate, commits whole modules and at
most one deterministic partial final module, then re-derives the local envelope
from the committed placements. There is no global free-space search and no
historical window reopening.

Candidate ranking is stable and local to the current residual:

1. maximum actual packed volume;
2. maximum Product Block transverse utilization in the residual;
3. maximum quantity;
4. minimum X depth required;
5. largest valid footprint in the residual;
6. larger unit volume and longest dimension;
7. parent product order and Product Block stable orientation key.

The parent block quantity is authoritative. Fillers use enabled R1/R2/R3
orientations, the existing non-stackable vertical cap, and the shared payload
arithmetic. Materialized filler blocks start on the floor; physical overlap is
excluded by deriving the next residual envelope from all committed geometry.

Balanced Spread and Balanced Spread Infill normalize every product to sequence `1`.
Progressive Fill and Progressive Fill Infill preserve input sequence
values. In the Progressive Fill infill variant, more than one distinct sequence
activates protection: side/top infill is limited to the current sequence group,
while different groups may interact only through the immediate Pi/Pi+1
transition frontier. A later sequence group cannot fill an earlier closed
window or leapfrog an intermediate group.

The implementation performs no permutation, historical-gap scan, recursion,
backtracking, beam search, or container cloning. Candidate work is bounded by
committed side residuals × eligible products × geometry-derived Product Block
candidates. Quantity affects the committed module count and final placement
materialization, not the number of future packing branches.

## What Balanced Spread is

Balanced Spread is a deterministic, explainable, block-based heuristic for
rectangular transport loads. It is intended to create a structured candidate
layout for several rectangular load-unit types, particularly when quantities
are large enough to form repeated blocks. It is not a mathematical optimizer
and does not claim global optimality.

Its defining vocabulary is:

- structured candidate;
- deterministic;
- block based;
- support aware;
- width conscious;
- explainable.

The concise definition is:

> **Balanced Spread is a deterministic two-phase transport-loading heuristic that first converts large product quantities into YZ-optimized regular blocks and then closes bounded, union-supported residual frontiers, following a Y → Z → X filling philosophy.**

## Coordinate system and loading philosophy

The engine uses the transport unit's internal usable dimensions:

```text
x = transport-unit length (back wall toward the doors)
y = transport-unit width
z = transport-unit height (floor upward)
```

The construction philosophy is:

```text
Y → Z → X
```

1. Optimize the current width and discover valid support planes.
2. Fill the complete bounded residual frontier before consuming more length.
3. Advance the longitudinal frontier after the selected candidate is validated.

This is a construction order, not arbitrary traversal of individual items. It
does not mean that every placement is globally searched in Y, then Z, then X.

## Physical invariants

The active construction must preserve these result-level invariants:

1. positive-volume placements do not overlap;
2. every placement is within container length, width, and height;
3. only enabled orthogonal rotations are used;
4. a positive maximum payload is not exceeded;
5. a non-stackable load unit does not support another unit;
6. elevated units have a full rectangular base on an accepted support surface;
7. identical normalized inputs produce deterministic results;
8. requested quantities and `row_index` product identity remain traceable.

These are geometry and operational rules. The engine does not model cargo
securing, structural strength, friction, or legal transport compliance.

## Inputs and orientation families

Products are normalized with dimensions, quantity, unit weight, stackability,
row identity, and enabled rotation families. Container dimensions are normalized
as `L`, `W`, and `H`, with optional `max_weight` and `tare_weight`.

The application uses the R1/R2/R3 terminology already shown in the form. Each
enabled family contributes axis-aligned permutations in stable order:

| Family | Generated `(length, width, height)` permutations |
|---|---|
| R1 | `(L, W, H)`, `(W, L, H)` |
| R2 | `(L, H, W)`, `(H, L, W)` |
| R3 | `(W, H, L)`, `(H, W, L)` |

Duplicate tuples are removed. These flags are hard constraints: a disabled
family cannot appear in a placement. No diagonal or arbitrary-angle placement
is generated.

## Sequence semantics and product order

Balanced Spread deliberately has one common loading group, including its Mixed
Cargo Infill variant:

```text
all products are normalized to sequence = 1
```

The service sets each Balanced Spread row to sequence `1` before validation, the
template renders the field as read-only in that mode, and the engine enforces
the same rule again before normalization. A stale posted sequence value cannot
change Balanced Spread allocation.

The engine still retains a sequence key internally because the shared result
contract supports other modes. Balanced Spread therefore uses the effective
deterministic product order:

1. larger valid footprint among enabled orientations that fit the container;
2. larger unit volume;
3. larger longest dimension;
4. original input order.

This is automatic ordering, not a user loading sequence. It determines the
order of Phase 1 Product Blocks and is the primary residual-anchor priority in
Phase 2. A lower-priority SKU may still fill valid capacity inside the active
anchor frontier.

Progressive Fill uses the same geometric priority after sequence: products
are ordered by ascending input sequence, then larger valid footprint, unit
volume, longest dimension, and original input order. Its Mixed Cargo Infill
variant applies the existing same-sequence side/top eligibility rules within
each bounded local window.

## Two-phase architecture

```text
BALANCED SPREAD
      |
      +-- PHASE 1 — REGULAR PRODUCT BLOCKS
      |
      +-- complete frontier
      |
      +-- PHASE 2 — RESIDUAL FRONTIER CLOSURE V2
```

The global ordering is important:

```text
ALL PRODUCTS — complete regular blocks first
then
ALL PRODUCT RESIDUALS — one common Balanced Spread residual group
```

The engine does not load a product's residual immediately after that product's
regular block. Residual quantities are collected for every product after Phase
1, then Phase 2 starts at the complete-block frontier.

## Phase 1 — Product Blocks

### Product Block definition

> **Product Block:** a regular cuboidal loading module for one SKU, constructed
> by optimizing its transverse Y × Z geometry and repeating that module along X.

A Product Block:

- contains one SKU;
- uses one orientation or at most two enabled orientations of that SKU;
- is regular and explainable;
- has an explicit longitudinal envelope;
- may contain exact synchronized mixed-orientation lanes with one flat frontier;
- may contain an Adaptive Mixed-Lane Block (AMLB) whose populated lane tails
  end at different exact X coordinates.

Mixed orientation is not inherently undesirable. Exact synchronized blocks
remain regular repeatable modules. AMLB is a quantity-aware, non-repeatable
Product Block plan: compatible-height lanes use independent integral X
repetition counts, and metadata records each populated lane's start Y, stack
heights, unit count, and actual X end. Its overall `depth` is the maximum
physical lane tail, not a fictitious synchronized boundary.

### Transverse pattern and capacity

The **transverse pattern** is the arrangement in the container's Y × Z plane
before the module is repeated along X. For one orientation `(d, w, h)`:

```text
ny = floor(container_width  / w)
nz = floor(container_height / h)
```

For a non-stackable product the regular block caps `nz` at `1`.

```text
occupied_width  = ny × w
occupied_height = nz × h

YZ utilization =
    occupied_width × occupied_height
    ---------------------------------
    container_width × container_height
```

The transverse capacity is `ny × nz`. A module's `module_capacity` also
includes X repetitions when a synchronized mixed block needs more than one
copy of an orientation along its common depth.

Example transverse sketch:

```text
z ↑
A A A
A A A
A A A  → y
```

### Mixed orientation and synchronized depth

The candidate generator tests pairs of enabled orientations from the same SKU.
The pair is eligible only when:

- both orientations have compatible heights;
- both fit the transverse container geometry;
- their X depths can share an exact integer common depth.

For orientation depths `dA` and `dB`, the engine finds integer repetitions:

```text
rA × dA = rB × dB
```

The resulting common value is the **synchronized depth**. Lane groups then end
on one flat X frontier instead of leaving one orientation group shorter than
the other.

```text
AAAA | BBB
AAAA | BBB
```

The pair's lane counts and repetition counts determine its occupied width,
transverse capacity, module capacity, and common depth. Non-stackable products
still use only one vertical layer (`nz <= 1`) in a mixed block.

### Candidate families and phase-aware AMLB geometry

Single-orientation and exact synchronized candidates remain
quantity-independent repeatable modules. Quantity controls whether one of
those modules is eligible:

```text
module_capacity <= payload-feasible quantity
module_depth    <= remaining container length
```

AMLB candidates are phase-aware. For each compatible enabled orientation pair
and bounded lane composition, the generator uses the current payload-feasible
quantity and remaining X length. Exact rational integer bisection finds the
smallest critical depth whose integral lane positions can hold the planned
quantity. Every populated floor position stores its actual vertical stack
height, so a partial last lane or layer does not occupy virtual cells.

AMLB lane-count work is sampled only above 128 possible lanes and materialized
candidate columns are capped at 4,096. Ordinary pallet-scale families are
fully evaluated. These are search-complexity caps, not physical near-equality
tolerances.

Stacked phases continue to select the approved repeatable Product Block and
residual-frontier orchestration. Stacked AMLB candidate geometry is still
generated and materializable for validation, including partial vertical
layers, while non-stackable AMLB is eligible in single- and multi-SKU phases.
This boundary prevents quantity-aware stacked candidates from silently
consuming the residual quantities that define the approved P4/P2 Native/DGFE,
Balanced Spread, and existing single-SKU presentation contracts.

### Candidate ranking

After invalid repeatable candidates are removed, their established staged
ranking remains:

1. maximize YZ utilization;
2. retain candidates within the YZ utilization equivalence tolerance;
3. maximize transverse capacity;
4. minimize synchronized/module X depth;
5. prefer one orientation when geometrically equivalent;
6. apply the stable orientation/lane/repetition tie-break.

The code constant is:

```text
YZ_UTILIZATION_EQ_TOL = 0.0025
```

This is an **absolute normalized-utilization fraction**, equal to 0.25
percentage points. It is a ranking-equivalence tolerance, not a physical-fit
tolerance.

The best AMLB is ranked by maximum actual planned quantity, minimum actual X
depth, actual occupied-envelope volume efficiency, effective container-prism
utilization, and the stable geometry key. AMLB displaces the established
repeatable winner only when it loads more units in the current phase or loads
the same units in strictly less X. A true outcome tie retains the existing
winner, especially an exact synchronized block.

### Complete repetition and residual definition

For a selected repeatable candidate:

```text
complete_blocks = min(
    floor(payload_feasible_quantity / module_capacity),
    floor(remaining_length / module_depth)
)
```

All complete modules are materialized contiguously from the current X frontier.
Phase 1 does not greedily fill partial module gaps. The deferred quantity is:

```text
residual_qty = requested_qty - regular_qty
```

A selected AMLB is committed once with its exact `planned_quantity` and
per-lane stack geometry. It is never repeated as though its unequal tails were
a synchronized module. Side/top residual derivation continues to use the
committed placement cuboids, so physical openings are not inferred from empty
AMLB cells.

Residuals for all products are collected before Phase 2. If payload prevents a
positive-weight unit from being loaded, it remains unplaced even when geometric
space is still visible.

## Mono-product bounded lane-transition outcome

After an active mode has produced its normal complete result, a separate
floor-plan competitor is considered only when the complete request contains
exactly one positive-quantity input row. Zero-quantity rows are ignored for
eligibility, but distinct positive rows are never merged even when their
dimensions are identical. Mixed-cargo Product Block, residual, DGFE, infill,
and sequence orchestration therefore remains unchanged.

The competitor enumerates enabled, physically fitting floor orientations and
bounded Y-lane compositions. With `max_lane_transitions=1`, it pairs a
left-anchored composition with a right-anchored composition. Each lane has an
independent integral X endpoint: a right lane begins at its own furthest
overlapping left-lane endpoint, rather than at one artificial full-width cut
or the far container wall. Critical cuts come only from input dimensions and
integral item boundaries. Every candidate that can become the incumbent is
materialized as exact `Placement` cuboids and passed through the shared bounds,
collision, and support validator; dominated candidates are rejected before the
expensive full validation pass.

The complete baseline and transition outcomes are compared in this order:

1. more placed units;
2. shorter actual occupied X extent;
3. less unused area inside the placements' XY bounding envelope;
4. the approved baseline on an effective tie.

This comparison occurs after the normal mode has finished, so a local adaptive
choice cannot suppress a stronger residual or stacked result. A stackable row
is eligible when one or two identical-footprint Z layers fit; every upper unit
is emitted directly above its own floor unit and validated for full support.
When any fitting orientation permits more than two layers, the transition
competitor is conservatively skipped and the established supported 3D path
remains authoritative.

The initial interface intentionally supports only transition limits `0` and
`1`; `0` disables this candidate and another value raises an explicit error.
Search work is capped at 128 physical lanes, 128 lane configurations, 256
dimension-derived cuts per configuration, 4,096 materialized candidates, 512
requested placements, and two supported Z layers for the transition extension.
Above a cap the engine falls back to the approved baseline without
materializing the unsupported transition search. These are complexity
controls, not packing assumptions. The search is a bounded constructive
optimizer, not a complete general rectangular bin-packing proof.

## Phase 2 — Residual Frontier Closure V2

Phase 2 keeps the common residual pool and starts at the unchanged Phase 1
frontier. The first feasible product in `ordered_products` is the residual
anchor Pi. Support potential does not override that priority.

For every enabled Pi orientation, the engine evaluates Bottom-Up Row-First and
deferred Top-Down Row-First candidates. Pi is materialized with the maximum
payload- and geometry-feasible quantity in the smallest actual X footprint.
That placement-derived footprint defines the Native Frontier; an orientation's
nominal length is not assumed to be the whole footprint.

The remaining SKUs are then processed in `ordered_products` priority inside the
complete bounded frontier. Every enabled orientation is evaluated, and the
selected orientation maximizes quantity, Y utilization, and local volume
utilization before preferred-orientation and stable-index ties. Candidate
positions include the floor and top planes of stackable local placements.

Elevated cargo requires full rectangular base support from the **union** of
coplanar stackable lower surfaces. Contiguous seams are valid; unsupported gaps
and overhangs are not. The frontier is therefore not split into independent
per-unit support columns, and upper cargo is not centered on one supporter.

Deferred candidates reserve Pi cuboids from the top, fill other residual SKUs,
then settle Pi vertically without changing X, Y, or orientation. Settlement
requires a clear vertical path. Every final trial is checked for bounds,
positive-volume overlap, full-base support, stackability, height, and payload
before it can be ranked or committed.

Candidate ranking is:

1. maximum Pi quantity;
2. minimum actual Pi X footprint;
3. maximum frontier volume efficiency;
4. maximum other-product packed volume and quantity;
5. minimum committed depth;
6. Row-First, Bottom-Up, and stable orientation ties.

The frontier volume efficiency is packed local volume divided by the complete
`depth × container width × container height` prism. A bounded extension may add
the first clean row implied by the next remaining SKU. Its extra packed volume
is divided by only the extra X prism and compared with a clean whole-pool Pj
frontier built by the same Native physics. The extension remains eligible only
when its marginal efficiency exceeds that clean alternative; a tolerance tie
closes Native.

Only the selected trial mutates placements, quantities, weight, item indices,
and the X frontier. The loop stops when residuals are complete, no physical
candidate exists, payload is exhausted, or X is exhausted. The previous
`SupportSurface` greedy helpers remain in the module for compatibility testing
but are not the active Balanced Spread Phase 2 path.

## Payload behavior

When a positive maximum payload is configured, the engine tracks loaded cargo
weight and bounds additional positive-weight units by:

```text
remaining_payload = max_payload - loaded_weight
```

For a positive-weight SKU, the payload-feasible quantity is limited by the
remaining payload divided by unit weight. With no positive payload limit, or
with zero unit weight, geometry and quantity determine the available count.
Geometry can remain available after payload capacity is exhausted; the result
then reports unplaced units and the payload reason.

The transport summary separately reports cargo weight, optional tare, gross
weight (`tare + cargo` when tare is supplied), and payload utilization.

## Determinism and bounded work

Identical normalized inputs should produce the same product order, Product
Blocks, residual-frontier candidates, diagnostics, and placements. Stable orientation
order, row identity, input order, and explicit tie-break keys make results
reproducible for tests, engineering review, PDF/report output, and scenario
comparison.

The search is bounded by geometry and quantity feasibility. It does not perform
a beam search, global combinatorial search, arbitrary lateral-direction search,
or a generic item permutation search. Diagnostics expose candidate counts so
performance changes can be reviewed without treating timing as a correctness
threshold.

## Technical diagnostics

The active result keeps JSON-safe `space_evenly_*` metadata. The most useful
fields are:

| Diagnostic | Meaning |
|---|---|
| `space_evenly_product_order` | normalized product order and common sequence |
| `space_evenly_product_blocks` | per-product requested, regular, residual, and selected-block summaries; AMLB blocks include planned quantity and physical lane tails |
| `space_evenly_main_blocks` | materialized complete Product Block summaries |
| `space_evenly_main_blocks_end_x` | complete-block frontier |
| `space_evenly_residual_frontiers` | selected anchor, geometry, scores, physical validation, and JSON-safe candidate diagnostics for each closed frontier |
| `space_evenly_residual_bands` | compatibility alias for the selected residual frontiers |
| `space_evenly_support_surface_count` | contiguous stackable top surfaces in committed residual frontiers |
| `space_evenly_support_checks` | compatibility count for local placement evaluations |
| `space_evenly_residual_local_placement_evaluations` | deterministic local candidate-position evaluations |
| `space_evenly_support_relationship_count` | committed elevated placements requiring support |
| `space_evenly_residual_units` | all residual units sent to Phase 2 |
| `space_evenly_residual_packed_units` | residual units placed |
| `space_evenly_block_candidates_generated` | generated Phase 1 candidates |
| `space_evenly_block_candidates_evaluated` | Phase 1 candidates evaluated |
| `space_evenly_residual_candidates_evaluated` | Phase 2 candidates evaluated |
| `space_evenly_x_used` | final occupied longitudinal frontier |
| `mono_lane_transition` | additive mono-only diagnostics: eligibility, selection reason, 0/1 limit, realized transition count, exact lane tails, occupied X, compactness waste, search caps/counts, and a bounded placement sample |
| `front_to_back_frontiers` | bounded transition diagnostics, all orientation/strategy/family outcomes, final physical state, and the selected winner |
| `front_to_back_product_blocks` | per-product block, residual, and carry-forward summaries |
| `front_to_back_frontier_candidates_evaluated` | next-product orientation evaluations across the isolated transition candidates |
| `space_evenly_infill_*` / `front_to_back_infill_*` | bounded side-residual counts, volume, units by product, block candidate counts, sequence status, and deterministic action records |
| `residual_strategy_candidates` | Native and DGFE Extended outcomes with current orientation, gravity mode, traversal, virtual/settled coordinates, next orientation/quantity, support, validity, value metrics, and compact phase diagnostics |
| `selected_residual_orientation` | current-product orientation selected for the committed frontier |
| `pi_residual_x_footprint` | actual Pi placement footprint from the local frontier start, independent of total envelope depth |
| `candidate_family` / `selected_candidate_family` | whether an outcome is the compact `native` baseline or `dgfe_extended` envelope |
| `native_frontier_depth`, `extended_frontier_depth`, `extra_extension_depth` | paired envelope depths and the additional X consumed by DGFE |
| `native_next_product_qty`, `extended_next_product_qty` | Pi+1 quantities in the paired family outcomes |
| `dgfe_extra_packed_volume`, `dgfe_marginal_efficiency` | volume gained by DGFE and its utilization of only the additional X prism |
| `next_product_regular_block_efficiency`, `extension_value_delta` | shared Product Block benchmark and DGFE marginal advantage/disadvantage |
| `selected_frontier_volume_efficiency` | packed current-plus-next frontier volume divided by the candidate frontier prism volume |

The result also retains compatibility aliases such as
`space_evenly_residual_miniblocks`, target counts, packed volume, actual height,
and zero beam-state counts. These aliases are output compatibility metadata;
they do not imply a legacy mini-block or beam algorithm is active.

## Intended operating profile

The architecture is particularly suited to several rectangular load-unit types
with moderate or relatively large quantities. Complete Product Blocks handle a
large share of the request, leaving the bounded residual phase to resolve
leftovers. Small quantities are supported, but they tend to produce fewer
complete blocks and delegate a larger share of the load to the heuristic
residual phase. The result remains a candidate layout, not a proof of the best
possible packing.

## Limitations

Balanced Spread does not prove or calculate:

- global mathematical optimum;
- cargo securing, lashing, or dunnage design;
- structural compression strength or crushing limits;
- axle loads or center-of-gravity compliance;
- forklift accessibility or an exact loading path through doors;
- friction, dynamic stability, or route vibration;
- regulatory or dangerous-goods compliance;
- refrigeration airflow or thermal constraints;
- irregular, deformable, or non-rectangular geometry;
- diagonal or arbitrary-angle placement.

Internal dimensions must be usable loading dimensions. Door aperture, handling
clearance, practical loading/unloading order, and legal transport checks remain
engineering responsibilities outside this geometric candidate solver.

## Validation recommendations

Direct engine regression should check, at minimum:

- deterministic repeated geometry;
- bounds and enabled orientations;
- positive-volume non-overlap;
- full-base support for elevated units;
- non-stackable support rejection;
- quantity accounting and unplaced reasons;
- payload-limited cases;
- sequence forcing to one for Balanced Spread;
- regular-before-residual phase order;
- synchronized mixed-block flat frontiers;
- adaptive mixed-lane partial quantities, unequal physical lane tails, exact
  enabled orientations, and true-tie preference for synchronized blocks;
- mono-product 0/1 lane-transition monotonicity, independent stepped-transition
  geometry, complete-outcome ranking, one-layer stackable parity, true stacked
  baseline preservation, mixed-row exclusion, and bounded-search fallback;
- ordered residual-anchor priority and quantity-agnostic compact Pi footprints;
- whole-frontier floor/top-plane population and combined union support;
- unsupported gaps, non-stackable foundations, and non-stackable upper cargo;
- Bottom-Up and deferred Top-Down Row-First trials;
- clean-frontier versus marginal-extension efficiency and Native tie preference;
- Progressive Fill orientation × traversal base candidates and both family outcomes;
- four residual strategies per current orientation and quantity-agnostic residuals;
- actual Pi X-footprint compactness before local frontier efficiency;
- Native preservation, bounded DGFE extension, marginal extra-X efficiency, and
  the shared Pi+1 regular Product Block benchmark;
- deferred vertical-only settlement, collision-free paths, and union support;
- partial intersecting rows followed by the first clean re-synchronization row;
- current-residual priority, effective Row-First ties, and carry-forward quantity;
- JSON-safe diagnostics and standalone/Packaging Flow parity.

The engine is the source of truth for any discrepancy. Historical handoffs and
older mode descriptions must be treated as context, not as evidence against
the active implementation.

## Historical mode note

Maximum Utilization and Maximum Utilization Floor First remain recognizable
input compatibility values and may be referenced by older regression material;
they are not current user-facing labels. Sequence Loading and Strict Sequence
Loading remain unsupported historical values. Their former algorithm descriptions
are historical compatibility context, not active behavior in the current
`engine.py`. The former generic sequence-loading algorithms remain historical
compatibility context and are not imported by the current engine. The
`maximum_utilization` and `maximum_utilization_floor_first` values now route to
Progressive Fill with DGFE; other historical values return an explicit
unsupported-mode result.

## Glossary

| Term | Definition |
|---|---|
| Balanced Spread | The structured two-phase heuristic using V1 regular Product Blocks and Residual Frontier Closure V2. |
| Progressive Fill | The approved block-and-local-frontier DGFE heuristic, canonically `front_to_back`. |
| Mixed Cargo Infill | An opt-in parent-mode extension that constructively fills only the current Product Block's bounded side strip with compatible later products. |
| Deferred-Gravity Frontier Envelope (DGFE) | A bounded Progressive Fill candidate construction that temporarily reserves a top-down residual, fills the next product around it, and restores vertical gravity before validation. |
| Stepped Frontier Envelope (SFE) | The physically valid local boundary produced by residual construction, next-product population, and any deferred settlement. |
| Product Block | A regular one-SKU module repeated longitudinally. |
| Transverse Pattern | The Y × Z arrangement defining a Product Block. |
| Module Capacity | Units in one complete longitudinal Product Block module. |
| Transverse Capacity | Units represented in the Y × Z cross-section before X repetitions. |
| Synchronized Depth | Common X depth satisfying `rA × dA = rB × dB` for mixed lanes. |
| Adaptive Mixed-Lane Block (AMLB) | A quantity-aware, non-repeatable Product Block whose compatible-height mixed lanes have independent integral X repetitions and honest populated stack/tail metadata. |
| Mono Lane Transition | A mono-request floor-plan competitor that may exchange bounded Y-lane compositions once along X while retaining independent physical lane endpoints. |
| Residual Quantity | Requested units remaining after complete regular blocks. |
| Residual Frontier | One bounded, physically validated local XYZ section established by the current residual anchor Pi. |
| Native Frontier | The residual frontier ending at Pi's actual compact X footprint. |
| Union Support | Complete elevated base coverage supplied by one or more coplanar stackable placements without gaps. |
| Frontier | Current X coordinate after the completed regular or residual region. |
