# Historical handoff — Transport Container Space Evenly V3 (superseded)

> This execution handoff is retained for historical context. It is **not** the
> current algorithm contract. The active implementation is Space Evenly V1 as
> documented in `docs/domain/transport-container-engine.md`. In particular,
> the older one-pass full-width door-side residual description below predates
> the current support-surface residual bands, width planning, and pattern
> continuity.

This handoff supersedes the earlier artificial-ceiling Space Evenly brief.
The authoritative contract is `docs/domain/transport-container-engine.md`.

## Frozen behavior

Space Evenly is an independent mode with two phases:

1. Select at most one complete homogeneous `nx × ny × nz` cuboid per product,
   using an existing allowed orientation, and place selected blocks contiguously
   from the back (`x = 0`) toward the doors.
2. After every main block is complete, send only the target leftovers to one
   invocation of the existing greedy helper in a local full-width/full-height
   sub-container. Translate local `x` by `main_blocks_end_x`.

The main blocks never reuse side, top, or deep gaps behind the frontier. No
leftover may have `x < main_blocks_end_x`.

## Bounded construction

- Candidate generation samples useful `ny`/`nz` counts and derives `nx`
  analytically; retain at most 12 complete candidates per product row.
- Select one candidate sequentially per product, reserving a cheap later-row
  volume length estimate.
- Do not build a beam, Cartesian product, artificial ceiling, repeated full
  packing attempt, or lateral-direction search.
- Use the deterministic `y = 0` convention and materialize floor-to-ceiling.

## Payload and physical rules

- Transfer payload remaining after main blocks to the local greedy container.
- Preserve existing allowed orientations, stackability, support, bounds,
  collision, quantity identity, and zero-weight handling.
- Maximum Utilization, Maximum Utilization Floor First, Accessible Sequence
  Loading, and Strict Sequence Loading remain protected and must not be
  changed to implement this mode.

## Diagnostics

Keep JSON-safe metadata for `main_blocks`, `main_blocks_end_x`, main-block
units, leftover requested/packed units, candidate count, residual-zone start,
and the one greedy residual evaluation count. Ordinary `Placement` objects
remain authoritative for rendering, reports, standalone tools, and Packaging
Flow.

## Verification

Run the direct engine and Transport visualization tests, plus the optional
benchmark:

```powershell
$env:DEBUG='True'
python manage.py test packagingapp.tests.test_transport_container_engine packagingapp.tests.test_transport_visualization
python -m packagingapp.tests.benchmark_transport_container_engine --space-only
```

Document only the deferred second-iteration experiment: compare deterministic
left-to-right and right-to-left lateral construction.
