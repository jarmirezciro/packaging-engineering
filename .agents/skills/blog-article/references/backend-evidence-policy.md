# Backend Evidence Policy for Demo Articles

The current KolliPack backend is the primary source for numerical claims in demo and case-study articles.

## Purpose

A focused backend reproduction provides:

- Quality control.
- Confirmation that screenshots and notes match current logic.
- Additional alternatives or metrics for discussion.
- Protection against stale article results.

It is not a broad software-validation task.

## Required approach

1. Extract exact inputs from the case package.
2. Identify the existing shared backend entry point.
3. Call that backend directly from Python.
4. Use the current engine and shared services.
5. Do not duplicate formulas in temporary scripts.
6. Record the inputs and outputs used in the article.
7. Compare the result with screenshots, folder labels, and author notes.
8. Run one focused reproduction pass.

## Evidence hierarchy

Use this order:

1. Current KolliPack backend result using the stated inputs.
2. Current KolliPack interface output visible in supplied screenshots.
3. Structured result files in the package.
4. Existing article claims.
5. Author observations.

The author's observations control editorial focus. They do not override verified numerical output.

## What to record

Record only what is relevant:

- Input dimensions and restrictions.
- Desired quantities.
- Primary calculated result.
- Relevant alternatives.
- Efficiency.
- Weight and payload values where applicable.
- Pattern, orientation, or selected mode.
- Values quoted in the article.
- Differences between alternatives that matter to the story.

## Discrepancies

Never silently choose the value that makes the better story.

Create a concise note:

```markdown
## Evidence discrepancy

Screenshot:
16 boxes per pallet and 9,600 products per container.

Current backend:
24 boxes per pallet and 14,400 products when the first-ranked pallet result is used.

Likely interpretation:
The screenshot may show a manually retained lower-ranked pallet pattern.

Article treatment:
Use only the intentionally approved interpretation and report the unresolved difference.
```

When the conflict changes the article's central conclusion, stop and request author review.

## Scope boundaries

Allowed:

- Read-only backend inspection.
- One direct reproduction.
- Existing lightweight unit-level calls.
- Alternative enumeration when it is already part of the tool and helps the article.

Not allowed:

- Engine changes.
- Backend refactoring.
- Optimization experiments unrelated to the case.
- Browser automation.
- Screenshot generation.
- Full regression testing.
- Performance testing.
- Repeated debugging loops.

## Environment failure

When the backend cannot run:

- Record the failing command and reason.
- Do not change application logic.
- Preserve the latest approved numbers only when the evidence is otherwise sufficient.
- Add a warning to the final report.
