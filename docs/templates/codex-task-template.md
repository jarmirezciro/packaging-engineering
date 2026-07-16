# Codex task template

Copy this into a task and replace bracketed sections.

```markdown
# Task: [clear outcome]

## Required reading

- `AGENTS.md`
- `[relevant docs]`

## Current behaviour

[What happens now. Include route, mode, fixture, error, screenshot details, or reproduction steps.]

## Desired behaviour

[What the user should observe.]

## Scope

- Primary tool/surface: [...]
- Shared consumers to assess: standalone / Packaging Flow / Multi-product Container / Multi-product Bag / SEO / PDF / catalogue / graphics / JS
- Relevant engine/service/template areas to inspect: [...]

## Constraints

- Preserve existing calculation logic unless explicitly changed.
- Keep workflow session JSON-safe.
- Do not duplicate shared logic or UI.
- Do not redesign unrelated pages or the Packaging Flow shell.
- Do not commit, push, deploy, or run production migrations.

## Acceptance criteria

1. [...]
2. [...]
3. Standalone, Packaging Flow, and relevant multi-product parity is verified where applicable.
4. Public/SEO, graphics, and PDF consumers are verified or marked not applicable.
5. Relevant tests pass and final diff is clean.

## Execution

1. Inspect the current implementation and consumer matrix.
2. State root cause/architecture finding and concise plan.
3. Implement the smallest coherent vertical slice.
4. Run focused tests and practical checks.
5. Review the final diff and correct issues found.

Continue through implementation without asking for confirmation unless a decision would change business logic, destroy data, or require deployment access.

## Final report

- Root cause / architecture finding
- Solution
- Files changed and why
- Tests/checks and results
- Consumer matrix
- Remaining risks
- Confirmation of no commit/push/deployment/migration
```
