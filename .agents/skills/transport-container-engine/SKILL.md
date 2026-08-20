---
name: transport-container-engine
description: Analyze, test, debug, or extend KolliPack Transport Container packing algorithms while preserving mode isolation, physical invariants, and regression fixtures.
---

# KolliPack Transport Container Engine Skill

Use this skill for Transport Container packing-engine bugs, new packing modes, heuristic changes, compaction changes, residual-space logic, and engine performance work.

## Authority

Do **not** duplicate the full algorithm contract in this skill.

Read, in order:

1. `AGENTS.md`.
2. `docs/domain/transport-container-engine.md` — authoritative mode semantics, invariants, regression cases, and approved evolution direction.
3. `docs/domain/transport-selection-logic.md` only when forms, services, workflow, reports, catalogue inputs, or visualization consumers are in scope.
4. `docs/engineering/testing-and-verification.md`.
5. The current engine/service/tests in the repository.

Current code is authoritative for exact call graphs and signatures. The domain document is authoritative for intended behavior. If they disagree, stop and report the discrepancy rather than silently choosing one.

## Required workflow

### 1. Identify the exact mode

Trace the dispatch and call graph before editing. Never infer behavior from UI labels alone.

Classify the task as one of:

- Maximum Utilization;
- Accessible Sequence Loading;
- Strict Sequence Loading;
- Space Evenly (when/after implemented);
- shared physical geometry/invariant helper.

### 2. Reproduce and measure

Create or use a direct engine fixture. Record:

- loaded quantity by `row_index`;
- strategy/mode;
- placement coordinates/orientations or a deterministic geometry signature;
- overlap, bounds, support, stackability, payload;
- relevant frontiers/residual/compaction metadata;
- elapsed time for performance work.

### 3. Protect unaffected modes

Before changing behavior, run the established regression fixtures from `docs/domain/transport-container-engine.md` or the repository regression module. Any shared-helper edit requires proof that unaffected mode signatures remain unchanged.

Prefer a mode-specific helper when the behavior is not a true physical invariant.

### 4. Implement

- Keep geometry deterministic.
- Avoid millimetre scanning and unbounded permutations.
- Treat residual partitions as computational representations, not physical walls, except where a mode deliberately defines an operational frontier.
- Do not use compaction to hide an incorrect space-generation rule.
- Preserve product identity, quantity, allowed orientations, support, stackability, bounds, and payload.

### 5. Verify

Run focused direct engine tests first, then relevant service/Django/integration tests. For algorithm changes, compare unaffected modes against their baseline geometry signatures.

### 6. Stop instead of looping

After one focused correction pass, stop and report the exact failing fixture if the same defect remains. Do not keep rewriting multiple packing modes to chase one visual symptom.

## Task handoffs

- Baseline regression harness: `docs/handoffs/transport-container-regression-harness-codex-task.md`.
- Space Evenly implementation: `docs/handoffs/transport-container-space-evenly-codex-task.md`.

Handoffs are execution briefs. The domain document remains the durable source of truth.
