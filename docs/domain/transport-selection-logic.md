# Transport Container Tool logic

## Purpose

Load products, cartons, or pallets into a transport unit such as an ISO container or European trailer, calculate geometric and weight capacity, generate a clean 3D load plan, and provide reportable utilization metrics.

## Established inputs and catalogue data

Transport catalogue fields discussed:

```text
part_number
part_description
packaging_type
packaging_materials
part_length
part_width
part_height
tare
max_payload
```

Reference usable internal dimensions discussed in June 2026 included:

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

These are reference templates, not universal legal or manufacturer specifications. Catalogue records are the runtime source of truth.

## Core calculation model

**Repository verification required:** inspect the current transport engine to document exact placement and ranking algorithms.

The intended deterministic flow is:

1. Normalize the transport unit’s usable internal L/W/H, tare, and optional maximum payload.
2. Normalize each load unit’s L/W/H, quantity, weight, and rotation/stacking restrictions.
3. Enumerate allowed orthogonal floor orientations.
4. Compute feasible positions in the transport footprint and, where supported, vertical levels.
5. Generate non-overlapping placements within bounds.
6. Stop when required quantity is loaded or no feasible position remains.
7. Calculate geometric capacity and payload-limited capacity separately.
8. Final feasible quantity is constrained by all mandatory limits.
9. Produce utilization and unallocated quantity with explicit denominators.

## Single versus multiple products

The tool has supported dynamic product/load rows. Document after inspection whether the engine uses:

- sequential first-fit;
- sorted placement order;
- zone allocation;
- 3D bin-packing heuristic;
- one-SKU repeated grid;
- or a hybrid.

Do not describe the output as globally optimal unless the algorithm and tests establish that claim.

## Weight model

Optional `tare` and `max_payload` were approved. Clarify current definitions:

```text
cargo_weight = sum(loaded_quantity_i × unit_weight_i)
```

- Compare cargo weight with maximum payload.
- Report tare separately.
- If showing gross transport-unit weight, define it explicitly as tare + cargo.
- Geometry and payload may produce different capacities; identify the governing constraint.

Do not infer road gross-weight, axle-load, or legal-route compliance unless those modules exist.

## Doors and loading access

The clean renderer shows rear doors on one end. Door placement was corrected historically and is part of the visual contract.

Unless the engine explicitly models it, the result does not guarantee:

- forklift aisle/access;
- unloading sequence;
- door-aperture fit versus internal cross-section;
- center-of-gravity or axle distribution;
- lashing/securement;
- refrigeration airflow;
- dangerous-goods segregation.

Expose these as assumptions when relevant.

## Visualization

Approved views:

- Main
- Opposite
- Top
- Side

User-facing render direction:

- shared interactive Three.js scene in standalone and Packaging Flow;
- doors clearly at the correct end;
- preferred main perspective preserved;
- no axes/mesh in final output;
- result volumes displayed in m³;
- load and transport unit fit inside the viewport;
- product/base-unit detail shown where useful.

## Standalone and Flow parity

Historical fixes added a missing workflow helper such as `_transport_rows_from_selected()` and repaired standalone analysis. The architecture rule is stronger than the helper:

- one shared service and wrapper;
- Flow inherits previous-step results through JSON-safe rows;
- when Transport is first step, it must be functionally identical to standalone;
- workflow layout and result controls must match standalone;
- hidden fields and scripts must be prefix-safe;
- standalone PDF export must use validated Three.js Main, Top, and Opposite-side
  snapshots from the selected shared result, with no Matplotlib fallback.

A historical export route was:

```text
/container-tool/export/pdf/
```

Verify current URL names.

## Ranking and metrics

Document exact ranking after inspecting the service. Metrics should define:

- loaded quantity;
- unallocated quantity;
- occupied volume / usable internal volume;
- occupied footprint where relevant;
- cargo weight / max payload;
- governing constraint;
- transport-unit count if multiple units are calculated.

## Test cases to retain

- exact grid fit in each floor orientation;
- load unit taller than transport unit;
- geometry capacity greater than payload capacity;
- optional payload/tare omitted;
- door end and all four views correspond to the same placements;
- result m³ conversion;
- multiple product rows and deterministic order;
- inherited pallet from Packaging Flow;
- Transport as first step equals standalone;
- selected result and PDF agree;
- all session rows are JSON-safe.
