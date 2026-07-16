# Agent workflow and anti-loop rules

## Why this exists

The project experienced long loops when changes were delivered one file at a time, when an agent assumed architecture without inspecting the latest ZIP/repository, or when it declared success while a second surface still used legacy code.

## Required task lifecycle

### 1. Inspect

Before coding:

- confirm branch and `git status`;
- inspect current files, not remembered paths;
- map views, forms, engine/service/presenter, templates, partials, JavaScript, URLs, reports, Flow adapter, and relevant multi-product consumers;
- identify every consumer of the shared functionality;
- reproduce the issue or establish a fixture.

### 2. Explain root cause

For bugs, describe the actual cause before changing code. For refactors, describe the duplication or contract mismatch.

Avoid vague diagnoses such as “cache” or “CSS conflict” without evidence.

### 3. Define acceptance criteria

Write observable completion criteria. Include shared surfaces and non-regression constraints.

### 4. Implement one complete vertical slice

A vertical slice may cross Python, template, JS, and test files. Complete the requested behaviour end-to-end before stopping.

Do not deliver this incomplete sequence:

```text
backend updated
→ workflow context prepared
→ template still needs replacement
→ scripts still use legacy IDs
```

That is progress, not completion.

### 5. Verify

- focused automated tests;
- Django/system checks where relevant;
- manual request or browser checks where automated coverage is insufficient;
- session serialization;
- PDF/image generation;
- standalone/Flow/multi-product/SEO parity as applicable;
- final `git diff` review.

### 6. One correction pass

If verification finds a defect, make one focused correction pass. If the same issue remains, stop rewriting and report:

- exact failing fixture;
- observed versus expected;
- files/lines involved;
- what was attempted;
- the remaining unknown.

## Scope control

- Small safe batches are encouraged, but every batch must leave the repository coherent.
- Do not redesign stable workflow shell behaviour while fixing a tool.
- Do not refactor unrelated CSS, models, or URLs.
- Do not overwrite a whole global file when a local/shared component change is sufficient.
- Do not ask for confirmation for every obvious implementation step after the requirement is clear.
- Do not silently broaden a UI request into an algorithm rewrite.

## Agent final report

Every coding task should end with:

```text
Root cause / architecture finding
Solution
Files changed and why
Tests/checks and results
Consumer matrix: standalone / Flow / multi-product / SEO / report
Remaining risks or none
Git/deployment actions: explicit confirmation
```
