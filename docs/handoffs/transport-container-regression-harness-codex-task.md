# Codex Task — Transport Container baseline regression harness

## Goal

Create durable direct engine regression coverage for the current accepted Transport Container behavior **without changing any packing algorithm or customer-visible behavior**.

## Required reading

- `AGENTS.md`
- `.agents/skills/transport-container-engine/SKILL.md`
- `docs/domain/transport-container-engine.md`
- `docs/domain/transport-selection-logic.md`
- `docs/engineering/testing-and-verification.md`
- current transport engine/service/tests in the checked-out repository

## Scope

Create or extend a direct engine test module, preferably:

`packagingapp/tests/test_transport_container_engine.py`

No engine, form, template, Three.js, PDF, service, or Packaging Flow behavior change is allowed in this task.

## Required regression families

Use the canonical fixtures documented in `docs/domain/transport-container-engine.md`:

1. Maximum Utilization residual continuity.
2. Accessible Sequence regression cases, including the established EUR-pallet quantity family where still reproducible from the current repository.
3. Strict Sequence full-width frontier.

For each fixture, capture stable loaded counts and a deterministic placement signature (`row_index`, position, dimensions/orientation). Add reusable invariant assertions for bounds, positive-volume overlap, allowed orientations, support/stackability, and payload where applicable.

## Important baseline rule

The tests must describe the **current accepted baseline**, not force the repository to match an assumption.

If the current code contradicts a durable contract in `docs/domain/transport-container-engine.md` (for example Strict Sequence permits side reuse), stop and report:

- exact fixture;
- observed versus documented behavior;
- current call path/functions involved;
- no algorithm modification.

Do not “fix” the engine during this task.

## Verification

Run:

- the new direct engine regression module;
- existing transport-related tests;
- `python manage.py check` where the repository supports it.

Do not add brittle wall-clock assertions.

## Final report

- files added/changed;
- fixtures/signatures established;
- tests/checks and results;
- any baseline/document discrepancy;
- confirmation that packing behavior was not modified;
- confirmation of no commit/push/deployment/migration unless explicitly requested.
