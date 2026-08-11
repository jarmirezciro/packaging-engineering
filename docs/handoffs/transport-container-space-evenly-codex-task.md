# Codex Task — Transport Container: Space Evenly MVP

## Execution style

Use Plan mode first. This is an algorithmic change. The three established modes are protected contracts and the baseline regression harness must pass before implementation.

## Goal

Add a fourth Transport Container packing mode, **Space evenly** (`space_evenly`), using KolliPack's own deterministic artificial-ceiling + block-first heuristic. The mode should spread cargo across more floor area while preserving the full-height Space-Evenly target quantities whenever feasible.

This is an independent KolliPack implementation direction. Do not claim equivalence with undocumented proprietary algorithms.

## Required reading

- `AGENTS.md`
- `.agents/skills/transport-container-engine/SKILL.md`
- `docs/domain/transport-container-engine.md` — authoritative mode/invariant/Space-Evenly contract
- `docs/domain/transport-selection-logic.md` — service/form/consumer contract
- `docs/engineering/testing-and-verification.md`
- the direct transport engine regression module created from the baseline-harness task
- current engine, transport service, form choices, result labeling, and transport integration tests

Do not copy mode semantics from this task into another source. If this task and the domain document differ, stop and resolve the domain document first.

## Preconditions / stop conditions

Stop before editing packing behavior if:

- the direct regression harness does not pass on the starting commit;
- current Strict Sequence does not enforce the documented full-width-per-row frontier;
- current Maximum or Accessible Sequence contradicts the documented accepted fixtures;
- implementing Space Evenly appears to require changing an established mode's semantics.

## Phase 1 — Add the fourth mode surface

Add `space_evenly` as a new dispatch branch and user-facing choice **Space evenly** through existing shared form/service/workflow infrastructure.

Short explanation:

> Reduces the effective loading height when possible so cargo uses more of the transport-unit floor area.

No new user inputs in the MVP.

Do not alter the three existing dispatch branches.

## Phase 2 — Separate Space Evenly engine path

Create an isolated entry point such as:

`_pack_container_space_evenly(container, products)`

Sequence controls processing priority only in this mode; it does not create Strict/Accessible frontiers.

### Full-height target

Run the Space-Evenly construction at the full internal height first. Record the packed count vector by original `row_index`, packed volume, and loaded weight. This is the target for ceiling reduction.

Do not use Maximum, Accessible, or Strict results as the target.

### Artificial ceiling

Find the lowest deterministic bounded effective height that reproduces the full-height Space-Evenly target count vector.

Use geometric lower-bound ideas from `docs/domain/transport-container-engine.md`, including cargo volume / floor area and required vertical dimensions, but do not perform a 1-mm brute-force scan. Candidate generation/search must be bounded and deterministic. If no reduced candidate reproduces the target, keep full height.

Expose JSON-safe diagnostic metadata, for example:

- `space_evenly_effective_height`
- `space_evenly_height_reduction`
- `space_evenly_ceiling_candidates_evaluated`
- `space_evenly_target_counts`

## Phase 3 — Block-first construction

Generate a bounded set of homogeneous cuboid blocks for each product/orientation:

`nx × ny × nz`

Respect quantity, orientation restrictions, current free geometry, artificial ceiling, stackability, support assumptions, bounds, and payload.

Do not enumerate every possible integer triple for large requests. Include useful shape diversity such as maximum grid, length-dominant, width-dominant, low/wide, balanced, single-layer, and single-unit fallback candidates.

Lexicographic construction priorities:

1. reproduce target packed quantities / packed volume;
2. respect the current artificial ceiling;
3. prefer coherent larger homogeneous blocks;
4. prefer broader floor use over tall compact stacking when capacity is equal;
5. use physical contact/compactness as deterministic tie-breakers, not arbitrary visual spacing.

Residual-space bookkeeping must not become an unintended physical frontier.

## Phase 4 — Residual fill

When useful block placement is exhausted, place residual quantities under the same effective ceiling using a bounded physical-anchor/extreme-point-style mechanism.

Reuse existing pure physical helpers where safe, preferably through Space-Evenly-specific wrappers. Do not call Accessible/Strict transition-band, frontier, or compaction helpers.

Validate actual collision, full-base support, stackability, payload, bounds, and allowed rotations.

## Phase 5 — Tests and benchmark

Add direct tests for:

1. a homogeneous case where the artificial ceiling decreases and target quantity is preserved;
2. a case that requires full-height fallback;
3. a non-stackable case;
4. at least one 3-product case;
5. deterministic repeat output;
6. unchanged established-mode regression signatures;
7. minimal standalone/Packaging Flow mode-value integration needed for the new option.

Record, without brittle CI timing assertions, representative diagnostics for approximately:

- 1 product / ~100 units;
- 2 products / ~120 units;
- 3 products / ~150–250 units.

Report elapsed time and bounded candidate counts. Keep in mind that transport service may invoke the engine repeatedly during automatic maximum-quantity searches.

## Scope exclusions

Do not in this task:

- redesign Maximum Utilization;
- redesign Accessible Sequence Loading;
- redesign Strict Sequence Loading;
- modify Three.js placement geometry;
- redesign PDF rendering beyond mode labeling/metadata if required;
- add axle load, center-of-gravity, lashing, or airflow optimization;
- add a user-tunable spread factor/ceiling;
- perform a wholesale engine-module refactor.

## Documentation

Update `docs/domain/transport-container-engine.md` only with what was actually implemented: fourth-mode semantics, exact ceiling search, block generation, residual-fill strategy, limitations, regression cases, and measured performance notes. Change Space Evenly status from future direction to current mode only when the implementation and integration are complete.

Record a concise durable architecture decision in `docs/engineering/decision-log.md` only if the final implementation differs materially from the approved direction.

## Final Codex report

Include:

- files changed;
- concise algorithm explanation;
- exact artificial-ceiling candidate/search method;
- representative before/after Space Evenly metrics;
- regression result for all three established modes;
- tests/checks and results;
- performance diagnostics;
- limitations/full-height fallback cases;
- confirmation that no established mode semantics were intentionally changed;
- confirmation of no commit/push/deployment/migration unless explicitly requested.
