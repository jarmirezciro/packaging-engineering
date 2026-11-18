# Palletization Tool logic

## Purpose

Generate and rank practical rectangular-carton pallet patterns, calculate layers and total quantity, evaluate dimensional and weight constraints, and explain the chosen result in 2D/3D and PDF outputs.

## Inputs

Current implemented inputs include:

- carton L/W/H;
- pallet L/W/H;
- maximum total stack/load height;
- acceptable length and width overhang;
- carton/product weight;
- optional maximum pallet load for carton cargo only;
- optional maximum cargo load on the bottom carton;
- pattern families and column/interlock preference;
- advanced carton/stability parameters where present in the current form.

Dimensions are millimetres. Carton weight, maximum pallet load, and maximum
bottom-carton load are grams at the shared service/engine boundary. The maximum
pallet load excludes empty-pallet tare. A catalogue pallet's kg tare is used
only by Packaging Flow when it constructs the downstream physical load mass.
All fields and units must still be verified against the current form and
service before logic edits.

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

Before pattern generation, the engine rejects geometry that cannot produce a
single carton placement. The carton height must not exceed the available cargo
height, and either the entered length/width footprint or its orthogonal rotation
must fit inside the effective pallet footprint including permitted overhang.
Exact height and footprint equality remain feasible.

## Pattern families

**Stage 2 shared-library contract:** Container Selection and Palletization now
consume the same constructive geometry in `shared-mosaic-patterns.md`.
Palletization retains stable public functions such as `pattern_splitrow()` and
`pattern_pinwheel()`, but those functions are compatibility adapters that call
the shared implementation with the Palletization search policy. Pallet-only
balancing, stacking, interlock safety, ranking, load, and presentation rules
remain in the Palletization engine and service layers.

The project has discussed and implemented/refined these engineered pattern families:

- Block
- Row
- Brick
- Spiral Brick
- Pinwheel / Block Pinwheel
- Split Row
- Hybrid Pinwheel
- Perimeter-Core Mosaic
- Nested Simple Lattice — 1D
- Nested Simple Lattice — 2D
- Mosaic patterns with main, secondary, and filler blocks

Perimeter-Core Mosaic is the shared ten-carton mixed-orientation topology. It
is feasible when the normalized carton sides satisfy `L >= 2*S` and its
complete `(2*L + S) x (2*L)` footprint, or its whole-pattern rotation, fits
the effective pallet area. The palletization catalogue preserves it as a
distinct candidate when its placement geometry differs from Block, even when
the carton count is tied.

Pattern definitions are deterministic constructive heuristics. They are not generic unrestricted 2D nesting.

### Block pattern

**Current implementation note:** the Palletization Block pattern is one regular
rectangular grid using a single carton footprint orientation across the layer.
The engine generates the P1 and P2 grids, selects the one with more cartons,
and uses P1 on a quantity tie. This Palletization term is unrelated to a
Transport Product Block.

### Brick pattern

**Current implementation note:** the customer-facing Brick family is limited
to carton footprints close to a 2:1 side ratio. The engine compares validated
bonded/basket-weave candidates with centered staggered-row candidates and ranks
them by quantity, pallet-area utilization, family preference, orientation mix,
and bounding-box utilization. It returns no Brick candidate when a genuine
validated brick arrangement is unavailable; it does not relabel a plain Block
grid as Brick.

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

### P1 and P2

**Current implementation note:** P1 is the unrotated carton footprint with
carton length on pallet X and carton width on pallet Y (`L × W`). P2 is the
orthogonal footprint with carton width on pallet X and carton length on pallet
Y (`W × L`). The active engine stores those values as `LxW` and `WxL`; P1/P2
are the user-facing names for the same two footprint orientations.

## Split and mosaic patterns

A split/mosaic candidate divides the usable footprint into non-overlapping zones. Each zone uses P1 or P2, then optional filler regions are evaluated. The engine should:

1. enumerate meaningful split positions based on carton multiples, not every floating-point coordinate;
2. fill each zone with an integer grid;
3. test residual strips/blocks for alternate orientation fillers;
4. reject overlap and out-of-bounds placements;
5. deduplicate equivalent mosaics;
6. score symmetry/contour only after feasibility and count.

Balanced filler symmetry may improve operational quality but must not falsely inflate count or create unsupported cartons.

### Split Row implementation

KolliPack's Split Row candidate divisions are evaluated arithmetically along
both pallet axes: each possible number of rows or columns in the first
orientation is combined with the integer row/column capacity of the remaining
band. Only the winning division is materialized as `Placement2D` geometry. A
genuine mixed split wins a capacity tie over an all-one-orientation Block
fallback, so a side split such as 6x3 + 1x6 remains visible when feasible.

Sparse Split Row rows or columns are balanced from their known band boundaries
using deterministic opposite-edge coordinates anchored to the fixed main
arrangement, not the outer pallet boundary. A six-carton compact filler is
therefore placed 3 + 3 at the main arrangement's opposite edges. Generic
free-position X-by-Y searches and iterative filler reconstruction are not used on
this path. Odd residual rows use a centered carton (1 + 1 + 1 for three, 2 +
1 + 2 for five) with equal remaining space on both sides. If a candidate split
on one axis would collide with the fixed main block, the engine falls through
to the other known Split Row axis instead of aborting the symmetry pass. The
shared collision validator remains as a final safety check after the complete
layer is built.

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

Pallet height is resolved consistently across standalone Palletization,
Packaging Flow, rendering, and downstream transport handoff:

- catalogue pallet: use its positive height; missing or invalid values fall back to 150 mm;
- manual pallet: use the entered positive height; a blank value falls back to 150 mm;
- `max_stack_height` is the finished load height and must exceed pallet height.

## Weight limits

### Maximum pallet load

```text
cargo_weight = total_cartons × carton_weight
weight_capacity = floor(max_pallet_load / carton_weight)
```

The optional maximum pallet load is the combined gross weight of the cartons on
one pallet and excludes pallet tare. When supplied, carton gross weight must be
a finite positive value. The engine caps the actual placement construction,
including a partial final layer, so serialized 2D/3D geometry and displayed
carton counts cannot diverge. Decimal count-flooring and a narrow unit-
conversion tolerance protect exact kg/lb boundaries without admitting a truly
overweight carton. A limit below one carton is an infeasible input.

When the limit is blank, layer construction, ranking, and placement geometry
follow the prior geometric path unchanged. Result presentation may still show
actual pallet load when carton weight is available, but maximum-load utilization
is absent.

### Bottom-carton load

The discussed definition is cargo load from cartons above only. For pure column stacking with equal overlap:

```text
load_above_bottom_carton = (layers - 1) × carton_weight
```

For interlock or partial overlap, a prior design used overlap-area load distribution. The current implementation must be inspected and tested; do not replace it with a simple full-load assumption during unrelated work.

The current engine receives carton weight and the bottom-carton limit in grams.
Its primary result keys are `max_bottom_load_g`, `avg_bottom_load_g`, and
`weight_limit_g`. Historical `_kg` keys remain temporary compatibility aliases
but contain the same gram values; they are not kilogram conversions.

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

Detailed analysis displays the selected result's engine-provided pattern family
on all three surfaces. Selecting another layout refreshes the family with the result.

## Visualization and report

- Lattice options include their parameters and quarter-turn orientation in
  the selection key. The table, alternate preview, workflow state, and report
  use that same option identity. Existing topology keys keep their format.
  Older family-only lattice selections resolve to the first matching variant.
- the selected engine placements are serialized once into a JSON-safe Three.js scene shared by standalone, Packaging Flow, and the SEO calculator;
- the interactive Three.js pallet stack is the primary clean 3D result;
- no axes/mesh in final user-facing output;
- show carton and pallet dimensions, overhang, layers, quantity, weight, and result interpretation;
- the ReportLab PDF uses the validated current Three.js browser snapshot and returns HTTP 400 when the snapshot is missing;
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

The immutable Stage 2 fixture records the pre-migration commit, ordered raw
placements, occupied contours, bounding boxes, Layer A/Layer B geometry,
complete 3D stacks, engineering metrics, serialized result order/keys,
Three.js scenes, and report rows. It is generated only from the locked original
engine source and is never regenerated by a failing test. Shared-pattern
changes must pass both this Palletization fixture and the independent Container
Stage 1 candidate/selection baseline.

### Pattern calibration cases

Cases 1–8 come from `Pcases.docx`, and Case 9 comes from a later screenshot.
All nine are listed under Palletization Cases at `/regressions`. Each link loads
the captured inputs and runs the current engine.
Case 3 shares its geometry with the existing Cape Pack Perimeter-Core case and
has its own link for calibration. Case 2 uses the same carton as the Nested
Simple Lattice cases with a 304 × 316 mm pallet and a 300 mm stack-height limit.

The observations below refer to the original screenshots and their option
numbers. Current option order and availability can differ.

1. Option 2 appeared as a 2D lattice in Column view and a centered pinwheel in
   Interlock view. Option 4 was considered irrelevant. Option 5's nine-carton
   pinwheel was considered redundant and inefficient.
2. The capture showed neither a 1D nor a 2D lattice.
3. Reference arrangement for future review. The source recorded no defect claim.
4. Option 1 was mathematically correct. Centering its three-carton row was
   suggested for symmetry. Option 9 was considered irrelevant. Option 8 was
   considered worth preserving, and whether it is hardcoded remains open.
5. Option 3 was considered irrelevant.
6. Options 1 and 2 were considered good. Option 3 was also considered good, with
   symmetric behavior expected. Option 5 was considered irrelevant, irregular,
   and apparently unstable.
7. Option 4 was considered irrelevant. Option 5 was considered irrelevant,
   unstable, and incoherent.
8. Option 3 was considered reasonable, with its four-carton line suggested for
   centering. Option 6 was considered a good example to preserve.
9. Hybrid pinwheel reference with 33 cartons per layer and six layers for
   198 cartons on the pallet.

#### Nested pinwheel calibration

The existing search ranks feasible candidates primarily by carton count. It
centers the four-carton inner motif in any opening between one and two motif
spans on each axis. The resulting gap can separate the inner group from the
outer ring even when the overall fill is high.

| Case | Carton and pallet (native units) | Before, cartons per layer | Outer contour | Opening / inner span | Centered gap per side (X, Y) | Bounding-box / pallet fill |
| --- | --- | ---: | --- | --- | --- | --- |
| 1 | 292 × 316 on 2000 × 2000 mm | 24 | 1776 × 1776 | 1144 × 1144 / 608 | 268, 268 | 70.2% / 55.4% |
| 4 | 16 × 8 on 48 × 40 in | 12 | 40 × 40 | 24 × 24 / 24 | 0, 0 | 96.0% / 80.0% |
| 6 | 12 × 6 on 48 × 40 in | 18 | 48 × 30 | 24 × 18 / 18 | 3, 0 | 90.0% / 67.5% |
| 7 | 200 × 50 on 1200 × 800 mm | 84 | 1200 × 800 | 400 × 400 / 250 | 75, 75 | 87.5% / 87.5% |
| 8 | 250 × 50 on 1200 × 800 mm | 64 | 1200 × 700 | 300 × 300 / 300 | 0, 0 | 95.2% / 83.3% |
| 9 | 300 × 400 on 2000 × 2000 mm | 24 | 1900 × 1900 | 1100 × 1100 / 700 | 200, 200 | 79.8% / 72.0% |

Cases 1, 7, and 9 leave a continuous void around the inner motif, isolating the
inner group in plan. Case 6 has contact on two opposing sides and leaves two
3 × 18 in channels, each half a carton short side wide. Cases 4 and 8 have
edge contact on all four sides and retain only the inner pinwheel's intrinsic
square void, with side lengths of 8 in and 200 mm respectively. The Case 1
alternate orientation reaches 97.3% bounding-box fill with a detached inner
group, so fill alone would miss that defect. These are in-plane contact
observations. Vertical support uses the existing stacking checks.

Cases 1 and 9 have no contact-fit candidate in either orientation. Case 6's
contact-fit candidate is a scaled equivalent of the Case 4 layout, but its
12-carton contour leaves 18 × 10 in of unused axis spans on its pallet. Case 7's
largest contact-fit contour in each orientation is 950 × 550 mm (50 cartons)
or 1050 × 650 mm (66 cartons), leaving 250 × 250 mm or 150 × 150 mm of unused
axis spans. In both cases the unused span exceeds one carton short side on
both axes. Cases 4 and 8 have a full pallet axis, with all exterior slack
along the other axis.

Palletization requires both opening spans to equal `L + S` within the
existing geometric tolerance, where `L` and `S` are the long and short
carton sides. The centered gap per wall is half the difference between the
opening span and `L + S`. Zero gap on both axes gives four-sided edge contact
and leaves only the intrinsic `(L - S) × (L - S)` void. The smaller difference
between the effective pallet span and the contour span across the two axes
must be at most `S`. One short side is one minimum carton pitch, so the rule
admits a compact nest that leaves room along one axis and excludes an inset
nest that leaves more than one minimum pitch along both axes. The rule
conservatively excludes centered motifs with positive clearance outside the
geometric tolerance.

Both checks run before sorting and placement construction under the existing
search bounds. Each orientation keeps its existing ranking among eligible
candidates. An eligible rotated candidate becomes the base if the primary
orientation has none. Cases 1, 6, 7, and 9 no longer offer Nested pinwheel.
Cases 4 and 8 retain their ordered base placements, with 12 and 64 cartons
per layer and 24 and 640 per pallet. Case 9 retains Hybrid pinwheel at
33 cartons per layer and 198 per pallet.

#### Hybrid pinwheel calibration

Hybrid starts with the existing block-pinwheel candidates and tiled simple
motif. It retains each bare core and also considers margin filling: a
staggered Brick on the right and a best-orientation uniform grid above the
core. Sparse top filler lines are spread to opposite strip edges in the
primary orientation. Previously carton-count ranking could prefer fragmented
filler geometry without an eligibility check.

| Case | Core and filler geometry | Floor utilization | Outcome |
| --- | --- | ---: | --- |
| 4 | 12-carton, 1219.2 × 812.8 mm core; attached 3-carton rectangular top band | 100% | Preserve the ordered 15-carton Hybrid and its 14-carton alternate orientation |
| 5 | 4-carton, 604 × 604 mm core; detached 2 + 1 staggered filler at X=610/902/756 mm | 66.43% | Reject the fragmented 7-carton candidate |
| 9 | 28-carton, 2000 × 1700 mm core; attached 5-carton rectangular top band | 99% | Preserve the ordered 33-carton winner, 6 layers and 198 total; its 28-carton alternate is also unchanged |

In Case 5 the right strip is 596 mm wide. Two 292 mm cartons occupy 584 mm,
so centered Brick rows start 6 mm beyond the core. The next row contains
only one carton and is offset by another half carton length. The whole filler
group is detached, has a stepped contour, and gives an asymmetric protrusion.
It is not a sparse-line-balancing defect: each X-aligned filler line contains
only one carton, so that pass leaves the staggered arrangement unchanged.
A 60% threshold alone would retain this poor arrangement.

The Palletization Hybrid policy requires each nonempty margin to be an
attached, unbroken rectangular group. It uses the existing arithmetic:

- A right-margin Brick is nonempty only with at least two rows and two full-row
  columns. Its alternating column counts are `c` and `c-1`; that union cannot
  be a rectangle. Reject the filled candidate, retaining the bare core as a
  separately ranked alternative.
- For the top grid, use the same orientation and integer counts as the existing
  two-orientation filler. If balancing is enabled, a row with `c >= 2` and
  `c * carton_pitch < core_length` has positive gaps after edge spreading and
  is excluded. Full-span rows, single-column groups, and contiguous unbalanced
  grids remain eligible. The last two may be asymmetric but are still regular,
  attached rectangles.

These checks run in constant time after the already materialized core's
existing bounding-box calculation, before allocating or validating fillers.
No pinwheel enumeration, search bounds, core construction or ranking changes.
The core's existing central-hole constraints remain in force; no carton graph,
new candidate search or mechanical model is introduced.

As a separate relevance rule, eligible cores and filled candidates must cover
at least 60% of the effective footprint, including permitted overhang. This
removes Case 5's remaining 4- and 6-carton cores (37.96% and 56.94%). Both
orientations therefore produce no Hybrid option; its best existing Block
result remains 8 per layer and 56 total. These are geometric quality and
relevance checks, not proof of physical load stability. The rule deliberately
excludes staggered Hybrid margins; the independent Brick family is unchanged.

The policy is off for Container Selection. Standalone Palletization, Packaging
Flow, the public calculator, scene serialization and reports consume the same
filtered engine results. No form or session schema changes are needed.
Historical fixtures remain immutable, with explicitly enumerated Hybrid deltas
and a compatibility run that disables both calibrated policies. See
[verification and benchmark evidence](../engineering/hybrid-pinwheel-calibration.md).
