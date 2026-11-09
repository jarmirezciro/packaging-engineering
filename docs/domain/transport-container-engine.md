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
→ optional side and supported-top infill in the selected trial window
→ finalize the frontier from the active geometry
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
residual behavior without look-ahead. Progressive Fill preserves input sequence
groups and uses the shared deterministic size ordering within each group. A
committed frontier is never reopened by later products. There is no global
residual-at-the-end phase, free-space tree, lateral gravity, compaction, or
legacy solver import.

For a winning DGFE Extended trial, the original window stays available for both
local infill passes. Before closing the phase, the engine may anchor the clean
row at the preceding occupied X face when a full-width empty strip separates
it from all other placements in the phase. The row keeps its Y and Z geometry,
orientations, quantities, and sequence. It must pass physical validation at the
new position. Cargo that shares the row's X span, including supported-top infill,
keeps the row at its trial position. The frontier closes at the last occupied X
face, including any infill, so an unused terminal portion becomes available to
the next phase. The original trial depth and score remain the basis for selection.

## Mixed Cargo Infill variants

The two infill variants preserve their parent macro orchestration and add one
shared constructive closure over each bounded local product/frontier window.
Balanced Spread closes a current product's contiguous span after all of its
approved complete blocks are committed, and then closes each committed
Balanced Spread residual frontier in its own X window. Progressive Fill runs
infill in a fixed trial window spanning the current product's complete blocks
and its selected Native/DGFE transition. Each window is closed before the next
phase begins. The winning trial depth and frontier score are recorded
separately from the final Progressive Fill frontier.

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

Supported-top closure also opts into stackable Adaptive Mixed-Lane Blocks
through the default-disabled `allow_stackable_adaptive` capability of
`_fill_candidate_plan()`. The existing generator already builds quantity-aware,
compatible-height lanes and partial vertical stacks. Top closure now admits
those plans to its existing materialization, full union-support/collision/bounds
validation, and volume-first ranking. A non-repeatable plan commits once with
its exact lane stack heights; it is never replicated as a synchronized module.
Remaining quantity, item indices, and weight update from the committed units,
then residuals are re-derived from actual placement cuboids. True local outcome
ties retain a repeatable candidate before the stable geometry key. This policy
does not activate stackable adaptive blocks in regular phases or side closure,
and does not alter Native/DGFE selection or support-envelope construction.

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
arithmetic. Side fillers start on the floor; supported-top fillers start on
their actual support plane. Residuals are re-derived from committed geometry,
and supported-top candidates also pass explicit physical validation.

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

## Bounded support-bed construction in Mixed Cargo Infill

The ordinary parent construction and the approved full-request support-bed
construction remain unchanged in `_pack_container_approved()`. If an infill request
is incomplete and contains both stackable and non-stackable positive-quantity
rows, that path permits one additional construction through the same
mode orchestration (`_pack_container_blocks`). This is not another packing
engine, a beam search, a product permutation, or a reopening of committed space.
Both baseline modes and complete ordinary outcomes bypass it.

In that additional construction, before a non-stackable product's regular
floor block is committed, `_choose_support_bed()` can combine its complete
remaining request with a homogeneous foundation of an eligible later product.
It evaluates enabled upper/lower orientations, bounded upper lane counts and
foundation layer counts. Foundation columns cover the upper footprint with
coplanar tops and reserve the upper orientation's actual height. The existing
single-orientation Product Block generator/materializer and top-candidate
support/collision/bounds validator remain authoritative. The compound is not
a new heterogeneous `ProductBlockCandidate` family.

The local ranking estimates the X needed for the compound plus remaining
requested rows using existing homogeneous block capacities. This disjoint-row
estimate is a ranking heuristic, not a feasibility certificate; empty volume
or theoretical support area is not counted as packed cargo. A compound must
improve that estimate before it can compete. The actual parent mode constructs
the continuation. The complete support-aware outcome is accepted only when it
loads strictly more units and reduces no row's loaded quantity. An equal or
row-losing outcome retains the exact ordinary placement signature. Diagnostics
describe the trial even when the ordinary outcome is retained (`selected=false`).

Progressive Fill restricts a foundation and its upper cargo to the same input
sequence. Balanced Spread keeps its normalized common sequence. Side and top
closure operate on the resulting committed compound window before advancing,
with separate support-bed accounting and shared remaining quantities, item
indices and loaded weight. Native/DGFE evaluation, Pi footprint priority,
extension value comparisons and deferred gravity are unchanged. The narrow
exception to ordinary infill's parent-block preservation is selection of an
uncommitted compound in this additional construction; no existing block moves.

Work is capped at 256 evaluated compounds per product window and 512 placement
objects per compound. Larger requests and exhausted budgets retain the ordinary
fallback. Layer/lane samples reuse the geometry-bounded adaptive count helper.
The original synthesis covers one foundation SKU and one complete non-stackable
upper request. Multiple foundation SKUs within a new bed and new
stackable-cap synthesis are not introduced. Existing mixed support unions and
stackable supported-top placement remain available through their established
paths. A positive configured payload still applies; a geometry-only experiment
supplies no payload limit. No package compression strength is inferred.

TC-REG-017 protects the supplied ExpV2-2 reconstruction (566.9×98.5×108 inches,
task dimensions and B/E non-stackability, all rotations, A/B/C group 1 and
D/E/F/G group 3, no payload). Progressive Infill improves 103→133 and Balanced
Infill 105→133, with all 48 D units. The local public preset is different and is
not rewritten. EasyCargo's A=1, B/C=2 sequence variant is tested separately;
Progressive's sequence restrictions continue to apply. See
`SupportBedConstructionTests` in `test_transport_mixed_cargo_infill.py` and the
equivalent-unit/service/scene/serialization test in
`test_transport_unit_integration.py`.

### Bounded partial support-bed constructions — TC-REG-019

The owner approved this extension after the diagnosis under
`regressions/TC-REG-019-mixed-cargo-support-bed-orientation/`. If the approved
outcome above is still incomplete, `pack_container()` may run two more complete
constructions: fixed **projected** and **compact** local ranking policies.
The two baseline modes, complete outcomes, ineligible requests and a zero
support-bed budget bypass them. There are at most four parent-mode runs.

Before an uncommitted non-stackable anchor's ordinary block, the new chooser
derives homogeneous foundation lane/column/layer counts from enabled geometry,
remaining quantity and room for the shortest eligible upper height. It samples
large count ranges with the existing bounded count helper, round-robins eligible
foundation rows, and attempts at most 256 bed/roof configurations per window,
including configurations rejected for payload or no upper fit. Foundation plus
cap materialization is capped at 512 units. Every upper orientation that fits
the real roof participates through the existing Product Block generator and
fill planner, including non-stackable Adaptive Mixed-Lane Blocks. The upper
quantity can be partial or complete. There is no dimension/name special case.

Projected ranking uses estimated completion depth, compound depth, upper
quantity, foundation quantity and stable geometry. Compact ranking uses compound
depth, upper quantity, actual compound volume, estimated completion and stable
geometry. The disjoint-row projection is not a hard rejection in this new path:
a useful partial bed can have a worse estimate than ordinary full completion.
The original full-request chooser and its projection gate remain unchanged.

Each construction commits at most one compound per anchor and carries exact
remaining quantities, indices and weight through its existing parent blocks,
Native/DGFE or Balanced residual closure, side infill and supported-top closure.
Later-only foundation eligibility and the parent sequence restrictions remain.
The two policies are fixed whole constructions, not a branching search or a
reopening of committed windows.

The complete alternatives pass orientation, identity, sequence, quantity/index,
weight/payload and shared bounds/overlap/full-support validation. Selection
requires strictly more units and no row loss against the **approved incumbent**,
including its full-request support-bed improvement. Highest admissible total
wins; stable policy order resolves new-policy ties. Rejection preserves the
incumbent placement signature exactly. Additive primitive diagnostics under
`*_infill_partial_support_beds` record both policies and rejection reasons.
Shared consumers continue using the selected ordinary placement list.

This compatibility portfolio raised the Progressive Infill R3 reconstruction
from 53 to 119 units with 15 non-stackable B on A. Its projected E/D choice left
no room for F/G. `PartialSupportBedConstructionTests` protect those two policies
and their fallback behavior.

### Supported constructions with either current-row role

The public path uses the compatibility portfolio as its incumbent and can try
up to two additional parent runs for an incomplete mixed infill result. They
prefer the current row as upper cargo and as foundation, respectively. Either
role can be used at the uncommitted frontier. Foundation and intermediate cargo
must be stackable. Upper cargo can
use either flag, and the planner retains its original flag and orientations.
Progressive Fill uses one sequence per compound. Balanced Spread uses its
sequence-neutral rows. Complete, single-row and baseline-mode outcomes bypass
these additional runs.

The planner samples homogeneous foundation footprints and layer counts across
eligible row pairs and orientations. It ranks roof Product Blocks using
estimated tail depth, with stackable adaptive blocks eligible on actual support.
It keeps a shortlist across foundation orientations and heights. For a staged
option, an upper column can rest on an intermediate panel whose units tile the
column's footprint. The planner reserves the chosen upper batch and payload
before assigning panels. It checks each coplanar union and the whole compound
before committing. It can use different middle rows in different columns and
tries full and reduced middle allowances. The bounded search covers a single
intermediate tier and a homogeneous foundation. It does not reopen a window.

Each window tries up to 256 bed or staged configurations and each compound
commits up to 512 units. Two trials share a request limit of 1,024 configurations.
Roof Product Blocks and tail estimates are cached for the request. The existing
parents commit the selected compound and process the remaining quantities.
The complete result must pass the same physical checks and strictly increase
the total while preserving every row's compatibility quantity. Equal totals
and rejected trials keep the incumbent geometry. The engine records trial
counts, rejection reasons and exhaustion in `*_infill_supported_constructions`.

The four TC-REG-019 Progressive Infill R3 variants load 125 to 127 units.
With all rows stackable, 15 B units rest on A and the total rises from 83 to
127. The owner approved six revised public outcomes after reviewing both
layouts. Compatibility tests still protect the original counts and support
behavior. See [the reference matrix and verification](../../regressions/TC-REG-019-mixed-cargo-support-bed-orientation/generalized/results.md).

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

Transport and Container Selection share the same meanings for R1/R2/R3:

| Family | Original dimension vertical | Generated `(length, width, height)` permutations |
|---|---|---|
| R1 | Length | `(W, H, L)`, `(H, W, L)` |
| R2 | Width | `(L, H, W)`, `(H, L, W)` |
| R3 | Height | `(L, W, H)`, `(W, L, H)` |

Transport evaluates enabled families in height, width, length order to preserve
its physical tie order. It removes duplicate tuples and generates only the
union of enabled axis-aligned orientations. R3-only is the Transport default
and preserves the original height-vertical behavior. Catalogue flags pass
through directly. Historical Transport rows without a known rotation convention
are left as stored; review their R1/R3 choices before recalculating.

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
| `trial_frontier_end_x`, `committed_clean_row_x`, `reclaimed_x_depth` | winning Extended trial end, actual clean-row start when populated, and X depth released at closure |

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

## Supported-top adaptive regression evidence — 2026-11-07

The baseline is production commit `9369aa8e9ac32c120456640f3552c67d2a608f3f`.
An existing uncommitted 48-ft preset was preserved. The central protection
entries are TC-REG-013/014 in the engineering regression register; that register
is authoritative for cumulative test membership.

### Isolated supported roofs

The direct test places a real rectangular stackable foundation beneath the
cavity, then calls `fill_top_residual_deterministically()`. It also tests nonzero
XYZ offsets. Dimensions here are canonical engine numbers in mm; the original
inch study is a different physical scale. Tests separately exercise scaling and
the service's physically equivalent inch/mm normalization.

| Roof L×W×free H | Cargo / request | Before | After | Selected physical construction |
|---|---|---:|---:|---|
| 275.5×94.2×45.01 | 63×23.6×39.44 / 17 | 12 | 15 | One 23.6-wide lane with four 63-long units; one 63-wide lane with eleven 23.6-long units; depth 259.6, width 86.6 |
| 275.8×94.5×45.01 | same / 17 | 17 | 17 | Exact existing 4×4 grid at depth 252, then one rotated unit at X=252; final X=275.6 |
| 275.5×94.2×45.01 | same / 5000 | 12 | 15 | Same bounded geometry as the 17-unit request |

In the smaller roof, the generator produces exactly three candidates with three
evaluations: a repeatable three-wide plan loading 12, an adaptive plan loading
15, and a repeatable rotated plan loading 11. The adaptive plan already existed
before the change but its fill plan returned zero. The top-only opt-in admits
it to full validation and volume-first comparison. At unit weight 2 kg, the
isolated load changes from 24 to 30 kg; remaining quantity changes from 5 to 2
and the next item index from 12 to 15. All 15 objects are distinct and fully
supported. No fit tolerance, overhang, or candidate generator was changed.

### Controlled seven-row reconstruction

This is a reproducible reconstruction, **not an exact replay of hidden screenshot
state**. Container: 567×98.5×107 mm; no payload limit or tare. All rows are
stackable, all three rotation families enabled, and no Max quantity flags.
Weights use the existing local preset's pound values converted by
`0.45359237 kg/lb`; this is an explicit assumption for the mm experiment.

| Row | L×W×H (mm) | Request | Source weight (lb) | Sequence |
|---|---|---:|---:|---:|
| A | 15.7×55.1×63.2 | 30 | 88.11 | 1 |
| B | 63×23.6×39.4 | 17 | 191.93 | 1 |
| C | 23.6×17.7×51.2 | 16 | 1198.76 | 2 |
| D | 31.5×47.2×15.7 | 48 | 11.02 | 3 |
| E | 47.2×47.2×21.7 | 14 | 1375.67 | 3 |
| F | 47.2×47.2×21.7 | 4 | 661.38 | 3 |
| G | 47.2×47.2×21.7 | 4 | 165.35 | 3 or 4, controlled independently |

PFI means Progressive Fill + Infill; BSI means Balanced Spread + Infill. The
perturbed case changes only A to 15.8×55.2×63.2 mm. Balanced modes normalize all
sequences to 1, so G3/G4 are identical there.

| A / G / mode | A–G loaded before → after | Total | Packed volume mm³ before → after | Volume utilization % | Occupied X mm |
|---|---|---|---|---|---|
| Original / 3 / PFI | 30,17,16,24,14,4,4 → 30,17,16,36,14,4,4 | 109→121 | 4602024.640→4882137.760 | 77.0098→81.6972 | 560.9→553.0 |
| Original / 4 / PFI | 30,17,16,32,14,4,0 → 30,17,16,44,14,4,0 | 113→125 | 4595390.208→4875503.328 | 76.8988→81.5861 | 561.0→553.1 |
| Original / either / BSI | 30,16,16,46,12,4,4 → 30,17,13,45,14,4,4 | 128→127 | 4960297.184→5028060.808 | 83.0051→84.1390 | 553.2→557.1 |
| Perturbed / 3 / PFI | 30,17,16,48,14,4,4 unchanged | 133 | 5175693.520 unchanged | 86.6095 | 561.4 |
| Perturbed / 4 / PFI | 30,17,16,48,14,4,0 unchanged | 129 | 4982317.008 unchanged | 83.3735 | 545.7 |
| Perturbed / either / BSI | 30,17,16,44,14,4,4 unchanged | 129 | 5082322.480 unchanged | 85.0470 | 551.7 |

For original A, the **actual detected** roof is 275.5×94.2×43.8 mm at Z=63.2;
it is not the historical 45.01-high study. B supported fully on A increases
from 12 to 15 in both infill modes. PFI B on the floor decreases from 2 to 1;
BSI B on the floor stays 1, while total B increases from 16 to 17. Therefore,
loading all 17 B is not equivalent to loading 17 on A. PFI gains space for
twelve extra D units. BSI follows the same volume-first local policy and changes
later frontiers: it gains one B and two E, loses three C and one D, loads one
fewer unit overall, and uses 3.9 mm more X while loading 67763.624 mm³ more
cargo. This is a documented heuristic tradeoff, not a claim of universal
whole-load improvement. No earlier frontier is reopened.

The perturbed cases retain 17 B on A and their exact before/after placement
signatures. The existing local inch preset was also run unchanged through
service normalization: its 566.9×98.5×108-inch container, R3-only rows, and
A/B sequence groups 1/2 differ from the reconstruction. PFI remains
30,17,16,4,14,2,0 (83 total, 63.6730%, X=14094.46 mm); BSI remains
30,16,8,46,8,0,0 (108 total, 69.7082%, X=14244.32 mm). B fully on A remains
zero in that fixture; different groups cannot cooperate in A's top closure.
Both approved baseline modes also retained exact signatures across all five
input scenarios (ten baseline runs).

An extra physically equivalent service check used the isolated roof dimensions
as inches above a 63-inch-high foundation (total height 108.01 inches), then
multiplied every dimension by 25.4 for its mm counterpart. Each infill mode
loaded 15 and returned identical canonical geometry in both units, with full
physical validation. This is distinct from entering the same numeric dimensions
as mm. Earlier committed frontier placements remain authoritative in either
unit system; top closure never reopens their occupied volume.

### Bounds, performance, and verification

The existing 128-lane/4096-column caps remain unchanged. Small-roof and
5000-request runs each generate/evaluate three candidates; the larger roof
evaluates four cumulatively across its 16+1 closure. Original-A/G3 top candidate
counts are PFI 8→8 and BSI 26→25; no quantity-dependent search expansion was
introduced. Five alternating old/new local runs measured these median times
(observations, not CI thresholds):

| Fixture | Before | After |
|---|---:|---:|
| Small supported roof | 1.856 ms | 3.402 ms |
| Same roof, request 5000 | 1.290 ms | 3.240 ms |
| Original A/G3 PFI | 170.621 ms | 78.468 ms |
| Original A/G3 BSI | 35.865 ms | 72.709 ms |
| Perturbed A/G3 PFI | 82.146 ms | 84.564 ms |

BSI's changed complete outcome costs about 37 ms in this local measurement;
physical validation remains intact. Both isolated and complete fixtures passed
the reusable independent bounds/orientation/overlap/union-support/stackability/
weight/quantity/item-index validator. Repeated signatures and diagnostics are
deterministic and JSON-safe.

The complete active command in `../engineering/testing-and-verification.md`
passed **173/173 before** in 252.168 s and **185/185 after** in 163.525 s, with
zero failures/errors/skips. The twelve added test methods protect TC-REG-013/014;
the red run first demonstrated the expected missing 15-unit eligibility.
The existing historical expectations were not edited. All 16 active registry
entries passed, including EasyCargo clean-row values, mono compaction,
P4/P2 Native/DGFE, adaptive blocks, TOPS manifests, Balanced closure, sequence,
Max quantity, units, standalone/public/Flow, scene, and PDF contracts.
`manage.py check` passed; the Node sequence suite passed 2/2. Retired-mode
`test_transport_container_engine` was not rerun; its previous diagnostic record
remains explicitly historical in the central register.

No service, UI, session, renderer, catalogue normalization, other calculation
engine, dependency, migration, or deployment code changed. Multi-product
Container/Bag use separate engines and are not Transport consumers. No commit,
push, merge, deployment, Railway operation, migration, or production-data write
was performed.

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
