# Transport Container Selection Tool — Service, User, and Business Contract

## Purpose

The Transport Container Selection Tool estimates how rectangular products,
cartons, pallets, crates, or other load units fit inside a selected transport
unit such as an ISO container or trailer. It reports loaded and unplaced
quantity, volume use, occupied dimensions, cargo weight, optional payload use,
and a clean 3D candidate layout.

The calculation is geometric and heuristic. It supports packaging-development
feedback and scenario comparison; it does not replace a physical loading trial,
cargo-securing review, or legal transport assessment.

## Algorithm authority and current mode status

The technical algorithm contract is maintained in:

`docs/domain/transport-container-engine.md`

The active source is:

`packagingapp/utils/container_tool/engine.py`

The active engine provides the approved **Balanced Spread** and **Progressive
Fill** baselines plus opt-in **Balanced Spread – Mixed Cargo Infill** and
**Progressive Fill – Mixed Cargo Infill** variants. Their canonical values
are `space_evenly`, `front_to_back`, `space_evenly_infill`, and
`front_to_back_infill`. These established backend values remain stable for
saved and serialized data. Product-name inputs such as `balanced_spread` and
`progressive_fill` normalize to them, while the former product names remain
accepted as invisible compatibility inputs. The persisted values
`maximum_utilization` and
`maximum_utilization_floor_first` remain compatibility aliases for the
unchanged Progressive Fill baseline. Sequence Loading and Strict Sequence
Loading remain unsupported historical values and return a graceful unsupported
result. Historical implementations remain separate and are not imported by the
active engine.

Packaging Flow is an orchestrator. It passes prefix-safe, JSON-safe transport
configuration and rows to the same transport service; it does not implement a
second packing algorithm. Standalone Transport and Transport as a first Flow
step should therefore have the same calculation behavior for the same inputs.

## What a user enters

### Transport unit

The unit may be entered manually or selected from a packaging catalogue. The
runtime catalogue record is authoritative for catalogue-backed dimensions.
Usable internal dimensions are entered as:

```text
length (L) × width (W) × height (H)
```

Optional transport values are maximum payload and tare weight. Catalogue
dimensions are reference data, not a universal legal specification for every
manufacturer or route.

Reference records historically discussed by the tool include:

| Code | L × W × H (mm) | Type |
|---|---:|---|
| CONT20STD | 5900 × 2352 × 2395 | 20 ft standard container |
| CONT40STD | 12032 × 2352 × 2395 | 40 ft standard container |
| CONT40HC | 12032 × 2350 × 2700 | 40 ft high cube |
| CONT45HC | 13556 × 2352 × 2700 | 45 ft high cube |
| CONT20REEFER | 5450 × 2280 × 2159 | 20 ft reefer reference |
| CONT40HCREEFER | 11599 × 2290 × 2425 | 40 ft HC reefer reference |
| TRAILERSTD | 13620 × 2480 × 2700 | European standard trailer reference |
| TRAILERMEGA | 13620 × 2480 × 3000 | Mega trailer reference |
| TRAILERBOX | 13620 × 2490 × 2710 | Box trailer reference |
| TRAILERREEFER | 13400 × 2460 × 2650 | Reefer trailer reference |

These values are reference templates only; the selected catalogue item or
manual dimensions are the inputs used for the calculation.

### Product/load rows

Each row contains:

- a display name and stable `row_index` identity;
- external load-unit length, width, and height;
- a requested quantity or the **Max qty?** flag;
- unit weight;
- stackable/non-stackable status;
- permitted R1, R2, and R3 orthogonal orientation families;
- a loading sequence field shared by the standalone tool, public calculator,
  and Packaging Flow.

Both Balanced Spread modes display a read-only sequence of `1` and normalize
submitted sequences to `1`. Both Progressive Fill modes accept user-defined
sequence groups. Switching modes on the same form temporarily displays `1` in
Balanced Spread and restores each row's editable value in Progressive Fill.

The rotation flags are safety constraints, not suggestions. Enable only
orientations that are physically permitted for the packaged unit.

### Manual input units

Manual input may be displayed and entered using the shared KolliPack length
vocabulary (`mm`, `cm`, `m`, `in`, `ft`) and mass vocabulary (`g`, `kg`, `t`,
`oz`, `lb`). All load-row dimensions share one selector and all load-row
weights share one selector. Manual transport-unit dimensions share a third
selector; manual maximum payload and tare share a fourth.

The submitted unit metadata is validated by the Transport service. Supported
values normalize to the unchanged engine contract:

```text
load and transport geometry -> mm
load-unit weight             -> kg
maximum payload and tare     -> kg
```

Missing metadata defaults to `mm`/`kg` for saved-session and request
compatibility. Explicit unsupported values are errors. Catalogue-backed
transport dimensions/tare and exact catalogue/inherited load-row scalars stay
canonical and bypass rounded display values. No unit conversion occurs inside
the packing engine, max-quantity solver, serializer, Three.js viewer, or report
calculation.

The editable Items to load table formats automatically populated dimensions
and weights with exactly two decimals, using the same standalone/public/Flow
adapter. Every rendered scalar, including restored manual inputs, retains its
unrounded canonical value in the existing hidden fields. Editing an input
replaces only that scalar's canonical value; typing itself is not reformatted.
Unit switches reuse the exact per-input canonical value and opt in to two
decimals without changing other tools' precision. Downstream Flow physical
inputs remain governed by the existing upstream chaining contract.

## How Balanced Spread behaves for users

Balanced Spread puts all product rows into one common loading group. In this mode:

- products receive a deterministic size-based order;
- large quantities are first turned into regular Product Blocks;
- quantities that cannot complete another block are deferred to a bounded
  residual-frontier phase;
- mixed products may be stacked only when dimensions, enabled rotations, full
  support, height, stackability, quantity, and payload permit it;
- the first feasible product in the same deterministic order anchors each
  residual frontier;
- the residual phase fills the complete bounded frontier using floor and valid
  union-supported top planes before advancing longitudinally;
- Bottom-Up and deferred Top-Down Row-First trials are physically validated,
  and extra X is used only when its marginal efficiency beats a clean next
  residual frontier;
- one deterministic placement is returned for the normalized inputs.

The camera controls and report views inspect that same placement. They are not
separate algorithmic alternatives.

The layout is a candidate engineering arrangement. It is not a cargo-securing
plan and should not be read as proof of globally optimal utilization.

## Single-product rectangular floor refinement

For a complete request with exactly one positive-quantity row, every active
mode also compares its finished result with the shared bounded mono-product
lane-transition planner. This planner is based only on container dimensions,
enabled rotations, item dimensions, quantity, weight, and stackability; names
or packaging categories do not affect eligibility. It can exchange lane
orientations once along container length with independent staggered endpoints,
which covers arrangements that cannot be represented as one repeatable flat-
front Product Block.

The normal mode result remains available and wins a true tie. The refinement
is selected only for more units, equal units in less X, or equal units/X with a
tighter XY bounding envelope. For stackable products, one or two identical-
footprint layers may be emitted with direct full-base support; deeper stacks
stay on the established supported 3D path. One positive row plus zero-quantity
rows is still a mono request; two positive rows remain mixed cargo even when
their physical dimensions match. The implementation currently accepts an
internal transition limit of zero or one and uses documented hard search caps.
Results outside independently certified fixtures are best feasible layouts
found by the bounded search, not universal optimum claims.

## How Progressive Fill behaves for users

Progressive Fill keeps the shared product ordering and Product Block
mathematics, then closes one bounded Pi/Pi+1 transition at a time. Each current
residual orientation evaluates Bottom-Up and deferred Top-Down Row/Column
strategies. The next product retains the established all-orientation evaluation
and always populates Bottom-Up Row First. Every residual base preserves a Native
outcome ending at Pi's actual placement-derived X footprint and a separate DGFE
outcome ending after the first clean Pi+1 X row. After maximizing Pi quantity,
selection minimizes Pi's own X footprint before considering local fill value.
DGFE may consume additional X only when its marginal extra-prism utilization
beats Pi+1's shared normal Product Block utilization; a value tie prefers the
compact Native outcome. A valid DGFE outcome may remain eligible when no regular
block exists or when Native cannot physically settle.

Top-Down residuals are committed only after vertical-only gravity settlement,
full union support, bounds, overlap, stackability, and payload validation.

Before a winning DGFE Extended phase closes, an isolated clean row can start at
the preceding cargo face. The next product phase starts at the last occupied
face. In Mixed Cargo Infill, both local infill passes use the original trial
window before this final boundary is set.

The resulting stepped local frontier is a deterministic candidate geometry,
not a loading-path, cargo-securing, or global-optimality proof. Detailed DGFE
semantics and ranking are maintained in `transport-container-engine.md`.

## How Mixed Cargo Infill behaves for users

Mixed Cargo Infill is never selected implicitly for an existing workflow. It
keeps the selected parent strategy and opportunistically fills only the
bounded local side envelope for the current product phase. After side closure,
the mixed modes also evaluate a separate supported-top envelope above local,
coplanar, stackable, roof-clear support unions. The envelope is
derived from committed XY geometry, so continuous space can cross internal
Product Block boundaries and a partial filler can leave an X tail for the next
local iteration. Balanced Spread Infill also applies the same closure after each
committed residual frontier, using the frontier's own X window and the same
remaining quantity state. It does not reopen older windows or run a general
free-space optimizer. Top closure is bottom-up and re-derived after each
committed Product Block; top units have separate accounting and diagnostics.
The current product may compete in that supported-top closure when it still has
remaining quantity; side closure retains its later-product-only eligibility.
Balanced Spread Infill normalizes sequence to one, so its geometry is sequence-
agnostic. Progressive Fill Infill preserves explicit sequence groups: later
products may cooperate locally only within the active group, and different
groups can meet only at the adjacent active transition frontier.

## Bounded support-bed construction

For incomplete mixed infill requests, the shared engine can additionally
construct a non-stackable row above a stackable supporting bed before committing
that row's floor block. This is bounded and uses the existing block and physical
validation functions. It keeps the ordinary result unless the complete new
outcome loads more units without reducing any row's loaded count. Progressive
Fill permits these compounds only within the same sequence; Balanced Spread
keeps its common group. Existing baseline modes, payload inputs, unit conversion,
forms and public presets retain their contracts.

Support-bed decisions are additive JSON-safe `*_infill_support_beds` diagnostics;
`selected=false` describes a rejected trial rather than committed cargo. Ordinary
placements remain the sole source for summary, Three.js, PDF and Flow output.
No new session configuration, UI control or presentation-side calculation is
needed. Geometry-only benchmark runs omit payload; configured positive payload
limits continue to apply. The geometry does not certify package strength.

For an incomplete approved result, the engine can also evaluate partial upper
batches through two fixed, bounded support-bed constructions. It reuses the
same block, infill and physical-validation paths and retains the approved
incumbent unless the complete outcome loads more units without losing any row.
`*_infill_partial_support_beds` contains primitive policy/rejection diagnostics;
the selected placements remain authoritative for standalone, public, Flow,
Three.js and PDF/report output. No service input or session setting is added.
The supported construction search also handles stackable upper cargo
and can reserve part of the foundation roof for an intermediate tier. Its
`*_infill_supported_constructions` diagnostics use JSON-safe data. The
all-stackable R3 TC-REG-019 request loads 127 units in Progressive Infill.
The same selected placements drive standalone, public, Flow, Three.js and
report output.

## Max qty preprocessing

**Max qty?** is implemented in the transport service, not as a special packing
primitive inside `engine.py`.

The service:

1. validates the entered rows;
2. treats a checked row as an automatic quantity request;
3. computes a necessary physical upper bound from enabled orientations,
   container volume, and payload; a single non-stackable row also receives the
   safe floor-area bound because no other requested row can provide support;
4. tightens that bound by reserving the volume and payload requested by every
   fixed row;
5. searches candidate quantities downward from the bounded upper limit and
   repeatedly asks the real current transport heuristic whether every fixed row
   and the candidate row were fully packed;
6. selects the first fully packed candidate, which is therefore the largest
   heuristic-feasible quantity within the bound;
7. resolves multiple Max qty rows in row order, with earlier resolved rows
   becoming fixed inputs for later rows;
8. passes the resolved quantities into the selected normal packing mode.

The descending search is deliberate. Packing feasibility is not monotonic in
the requested quantity: completing one more synchronized Product Block can make
a larger request fully packable even when the immediately smaller request leaves
an incomplete block and one or more units unplaced. A binary search may therefore
discard valid larger quantities. The solver does not assume monotonicity and does
not contain dimension-, pallet-, or quantity-specific exceptions.

The service caps the automatic search at 5,000 units to keep rendering
responsive. A checked row can therefore resolve to zero when it cannot fit, or
to an exact heuristic maximum within the physical/capped search bound when the
current mode and payload allow it. In the worst case it evaluates every integer
quantity in that bounded interval; the physical bound and fixed-row reservations
normally make the interval substantially smaller.
This is a service/preprocessing behavior; it must not be documented as an
analytic capacity formula hidden inside the engine.

## Weight and payload

Cargo weight is:

```text
cargo_weight = Σ(loaded_quantity_i × unit_weight_i)
```

When a positive maximum payload is supplied, Balanced Spread limits additional
positive-weight units by the remaining payload while it constructs blocks and
residual rows. A zero-weight row is not reduced by payload. Geometry may still
be available after the payload limit is reached, so the result reports the
governing constraint and unplaced quantity.

Tare is reported separately. When supplied, gross loaded weight is:

```text
gross_weight = tare_weight + cargo_weight
```

These values do not establish road gross-weight, axle-load, route, or legal
limits unless a separate module explicitly models them.

## Results, metrics, and presentation

The shared result is built from ordinary `Placement` objects and JSON-safe
metadata. It includes, where applicable:

- requested, packed, and unplaced quantity by row;
- occupied volume and usable internal volume;
- volume utilization percentage and cubic-metre values;
- occupied length, width, and height;
- residual dimensions;
- cargo weight, optional tare, gross weight, and payload utilization;
- active strategy/mode status and unplaced reasons;
- Balanced Spread technical diagnostics for engineering review.

The interactive Three.js scene, Loading View, Opposite Side, Top View, and PDF
report all refer to the same selected placement list. Final customer views do
not show debug axes or mesh overlays. Rendering changes must preserve the
calculation/result contract rather than recalculate placements in templates or
JavaScript.

Standalone, public and Packaging Flow Per-item summary tables use the shared
Transport presenter's `table_display` strings: load-unit dimensions and mass
follow the effective load-unit selectors, with exactly two decimal places.
Missing values display an em dash and rounded negative zero displays `0.00`.
The web Summary uses `display.summary` for dimensions and weights at up to two
decimal places, following the separate transport-unit selectors. Account
defaults initialize new state; explicit selections remain authoritative.
These web-only strings leave canonical scalars, report/legend formatting,
packing results and workflow chaining unchanged. Incomplete inherited mass
remains unavailable in both web and report presentation.

## Doors, access, and physical validation

The renderer shows the transport-unit doors at the approved end of the model,
but the geometric solver does not guarantee:

- door-aperture fit versus the internal cross-section;
- forklift aisle or handling access;
- a practical loading or unloading path;
- dunnage, lashing, or cargo securing;
- stack compression strength or crushing limits;
- center of gravity, axle distribution, or dynamic stability;
- refrigeration airflow, dangerous-goods segregation, or route compliance.

Confirm those constraints against the actual transport unit and load-unit
handling process.

## Business use and Packaging Flow role

The tool is intended to make transport consequences visible during packaging
development: compare usable unit dimensions, quantities, rotations, stackability,
weight, and payload assumptions before supplier drawings, samples, or physical
loading trials. Its value is explainability and repeatability, not an
unqualified “best” claim.

In Packaging Flow, Transport consumes inherited JSON-safe rows and configuration
from earlier steps. It may adapt prefixes, preserve selected catalogue items,
and carry results forward, but it must not duplicate Product Block, residual
support, payload, presenter, or renderer logic. A first-step Flow calculation
must remain functionally equivalent to standalone Transport.

## Regression & Case Compendium

`/regressions` lists the existing Transport cases directly from
`TRANSPORT_CONTAINER_CASE_PRESETS` in
`packagingapp/tools/transport/case_presets.py`. Each relative link opens the
normal `/container-tool/?case=<slug>` page. The standalone view uses the
existing deep-copy preset getter and shared page builder to populate inputs
and run the initial analysis. POST submissions use the user's edited inputs;
the case query is applied only on GET. Unknown standalone case slugs return 404.

To expose another case, add its label, config and rows to that existing Python
registry; it appears in the compendium automatically. Use the existing config
and row fields, including explicit unit metadata for non-metric inputs. The
public calculator's TOPS demo keeps its established single-group override;
the compendium's standalone link preserves the registry's loading groups.

The compact extension keeps at most two variants per benchmark family. These
five additions reuse the same loader; no preset sets an expected engine result:

| Case slug | Input source and distinct challenge |
|---|---|
| `p1-p2-imperial-supported-roof` | Existing `artifacts/transport-supported-top/evidence.json`, `equivalent_unit_checks[0].imperial_input`; documented under **Supported-top adaptive regression evidence** in the engine contract. A 275.5×94.2×45.01-inch roof above a 63-inch support, with 17 cargo units of 63×23.6×39.44 inches. Mass stays kg, as in that service check. This is the documented isolated fixture, not the unavailable original truck state. |
| `40hc-euro-pallet-unequal-lane-tails` | `test_transport_adaptive_mixed_lane.test_perturbed_pallet_builds_unequal_lane_tails_and_loads_25` and `TCEFV1_adaptive_mixed_blocks_regression.md`: 12032×2352×2698 mm container; 30 non-stackable 1200×801×144 mm units, 1 kg each, R3 only. The deliberate 801 mm width exposes unequal lane tails rather than the easier exact 800 mm synchronized pattern. |
| `tops-dgfe-shared-loading-group` | Deep copy of the existing TOPS preset with all sequences set to 1, matching `test_transport_front_to_back.primary_case_products()`. Unlike the four-group article baseline, it exercises both P4/P2 Native preservation and P2/P1 DGFE accommodation in one full manifest. |
| `easycargo-40hc-r3-only-dgfe` | Deep copy of the existing EasyCargo preset with R1/R2 disabled throughout, matching `EasyCargoEngineTests.benchmark_inputs(all_rotations=False)`. Preserves the restrictive-orientation clean-row/DGFE witness without adding a third EasyCargo variant. |
| `48ft-semitrailer-expv2-2-support-beds` | Deep copy of the imperial semitrailer preset with the exact `test_transport_mixed_cargo_infill.stackability_expv2_2()` overrides: A=15.75×55.15×63 inches; all rotations; A/B/C group 1, D/E/F/G group 3; B/E non-stackable; no payload. The existing fixture's canonical mm/kg values independently verify the inputs. |

The four original presets remain unchanged. In particular, the public
semitrailer's R3-only, differently grouped inputs are **not** the approved
133-unit support-bed setup. Separate strategy copies, the larger/easier roof,
quantity-only sweeps and separate P4/P2/P2/P1 subsets are omitted. The two TOPS,
two EasyCargo and two semitrailer variants differ in material constraints;
the Mix Load, isolated roof and perturbed-pallet families each have one case.

The full historical imperial P1/P2 truck inputs remain unavailable; the
275.5/275.8 roof values alone cannot reconstruct them. The controlled seven-row
mm roof experiments are explicitly different physical inputs and are not
silently relabeled as that original imperial load. The screenshot transcription
claiming a complete 133-unit load also disagrees with its visible 121/133;
the ExpV2-2 fixture is retained with its own provenance rather than conflating
those investigations. The five-row optimized TOPS reconstruction is omitted
because its P5 rotation permissions are unconfirmed.

## Session and serialization contract

Rows, configuration, results, and inherited Flow state must remain JSON-safe.
Do not put Django model instances, QuerySets, `Decimal` values, dataclasses,
placement objects, engine objects, matplotlib objects, or Three.js objects into
session state. Serialize stable scalar row fields and the result metadata only.

## User-facing interpretation

When reviewing a result, ask:

1. Were the internal transport dimensions and external load-unit dimensions
   entered correctly?
2. Are all enabled orientations physically allowed?
3. Are stackability and unit weights realistic?
4. Is payload, rather than geometry, the governing limit?
5. Which requested rows remain unplaced, and why?
6. Does the candidate layout require a handling, securing, or legal check outside
   the calculator?

The deterministic output makes scenario comparison and report review easier, but
does not remove engineering judgment.

## Validation and regression focus

Consumer and engine checks should cover:

- exact grid fits and orientation restrictions;
- too-tall or otherwise invalid load units;
- geometry capacity greater than payload capacity;
- omitted payload/tare values;
- multiple rows with stable identity and deterministic order;
- sequence forcing to one in Balanced Spread;
- complete-block-before-residual behavior;
- four residual strategies and Native/DGFE family outcomes per current-product
  orientation;
- Pi residual X-footprint compactness, marginal DGFE extension value, and the
  shared next-product Product Block benchmark;
- bounded clean-row envelopes and vertical-only deferred settlement;
- support, stackability, and non-overlap invariants;
- standalone/Packaging Flow parity;
- Three.js views and PDF using the same placements;
- JSON-safe session and result serialization;
- canonical mode alias normalization and exact baseline geometry preservation;
- deterministic bounded side infill from committed XY geometry, complete-face
  residual merging, X-tail preservation, quantity carry-forward,
  residual-local orientation ranking, sequence-group protection, and zero
  historical search, backtracking, or beam states;
- deterministic supported-top infill from local coplanar support unions,
  roof-clear envelopes, bottom-up re-derivation, support/overlap validation,
  separate top accounting, and explicit no-fit diagnostics.

Supported-top infill can evaluate quantity-aware adaptive mixed-lane plans for
stackable cargo inside the actual bounded roof cavity. Each plan uses enabled
rotations, commits once, and passes the existing full support/collision/bounds
checks before selection. Regular Product Blocks, side infill, sequence groups,
and the two baseline modes retain their established behavior. All surfaces
continue to consume the same placements and JSON-safe diagnostics; no new
service option, session field, renderer, or UI control is introduced.

For algorithm detail, use the technical deep dive rather than copying heuristic
rules into this contract document.
