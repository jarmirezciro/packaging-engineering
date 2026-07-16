# Context and token policy

## Purpose

Keep durable KolliPack knowledge available without forcing Codex to load the complete documentation set for every task.

## What loads automatically

Codex automatically discovers applicable `AGENTS.md` instruction files at session start. Ordinary files under `docs/` are reference material; they should be opened only when relevant to the task.

## Selective-reading rule

Do not run a blanket read of every Markdown file. Use this sequence:

1. Read the applicable `AGENTS.md`.
2. Use `docs/README.md` only as a routing index when needed.
3. Inspect the current code and search documentation for the exact tool/topic.
4. Open the affected domain document and no more than the necessary architecture/frontend/report/testing references.
5. Open product, SEO, deployment, or benchmark documents only for tasks in those areas.

Typical examples:

| Task | Recommended documentation |
|---|---|
| Small Bag UI fix | `domain/bag-selection-logic.md`, relevant frontend section |
| Container renderer refactor | `architecture/shared-tool-contract.md`, `domain/container-selection-logic.md`, `features/three-d-rendering-and-reports.md`, testing checklist |
| Packaging Flow bug | `architecture/packaging-flow.md`, affected domain document, known regressions |
| Company/About copy | company and product vision only |
| Competitor analysis | `research/benchmarks.md` plus fresh external verification |

## Size guidance

The documentation set may be large on disk because it is a repository knowledge base. That is acceptable. The important constraints are:

- keep root `AGENTS.md` concise and actionable;
- avoid duplicating the same long explanation across many files;
- link to one authoritative domain document;
- search for relevant headings rather than reading everything;
- start a new Codex session when switching to an unrelated feature area and the previous transcript is no longer useful.

## When to promote content into AGENTS.md

Add a rule to root `AGENTS.md` only when it affects most tasks or prevents a repeated costly mistake. Keep detailed formulas, history, examples, and benchmark notes in task-specific documents.

## Optional future optimization: skills

Repeated, specialized workflows can later become repository skills under `.agents/skills/`. Skills allow progressive disclosure: Codex can see a concise description first and load full instructions only when the skill is selected. Do this only after the workflow is stable; the current documentation remains the source reference.
