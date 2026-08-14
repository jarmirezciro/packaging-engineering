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

The current active calculation is **Space Evenly V1**. The form and persisted
workflow configuration still contain compatibility labels for Maximum
Utilization, Maximum Utilization Floor First, Sequence Loading, and Strict
Sequence Loading. Those values are not evidence that their historical solvers
are active: the current engine returns a graceful unsupported-mode result for a
requested mode other than Space Evenly. Historical implementations remain
separate and are not imported by the active engine.

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
- a sequence field retained by the shared form contract.

The rotation flags are safety constraints, not suggestions. Enable only
orientations that are physically permitted for the packaged unit.

## How Space Evenly behaves for users

Space Evenly puts all product rows into one common loading group. In this mode:

- every row is normalized to sequence `1`;
- the sequence input is rendered read-only and stale posted values are ignored;
- products receive a deterministic size-based order;
- large quantities are first turned into regular Product Blocks;
- quantities that cannot complete another block are deferred to a support-aware
  residual phase;
- mixed products may be stacked only when dimensions, enabled rotations, full
  support, height, stackability, quantity, and payload permit it;
- the residual phase fills width rows, then uses resulting support surfaces for
  higher passes before advancing longitudinally;
- one deterministic placement is returned for the normalized inputs.

The camera controls and report views inspect that same placement. They are not
separate algorithmic alternatives.

The layout is a candidate engineering arrangement. It is not a cargo-securing
plan and should not be read as proof of globally optimal utilization.

## Max qty preprocessing

**Max qty?** is implemented in the transport service, not as a special packing
primitive inside `engine.py`.

The service:

1. validates the entered rows;
2. treats a checked row as an automatic quantity request;
3. computes a practical geometry/weight upper bound;
4. binary-searches quantities by repeatedly asking the real current transport
   heuristic whether the fixed rows and the candidate row can be packed;
5. resolves multiple Max qty rows in row order, with earlier resolved rows
   becoming fixed inputs for later rows;
6. passes the resolved quantities into the normal Space Evenly calculation.

The service caps the automatic search at 5,000 units to keep rendering
responsive. A checked row can therefore resolve to zero when it cannot fit, or
to a bounded practical maximum when the current heuristic and payload allow it.
This is a service/preprocessing behavior; it must not be documented as an
analytic capacity formula hidden inside the engine.

## Weight and payload

Cargo weight is:

```text
cargo_weight = Σ(loaded_quantity_i × unit_weight_i)
```

When a positive maximum payload is supplied, Space Evenly limits additional
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
- Space Evenly technical diagnostics for engineering review.

The interactive Three.js scene, Loading View, Opposite Side, Top View, and PDF
report all refer to the same selected placement list. Final customer views do
not show debug axes or mesh overlays. Rendering changes must preserve the
calculation/result contract rather than recalculate placements in templates or
JavaScript.

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
- sequence forcing to one in Space Evenly;
- complete-block-before-residual behavior;
- support, stackability, and non-overlap invariants;
- standalone/Packaging Flow parity;
- Three.js views and PDF using the same placements;
- JSON-safe session and result serialization.

For algorithm detail, use the technical deep dive rather than copying heuristic
rules into this contract document.
