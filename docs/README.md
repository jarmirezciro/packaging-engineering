# KolliPack engineering documentation

## Purpose

This folder transfers durable project context from historical development discussions into the repository so Codex and other coding agents do not depend on conversational memory.

It documents:

- product and company intent;
- architecture and shared-surface rules;
- approved frontend direction;
- deterministic packaging logic, assumptions, and constraints;
- workflow session and propagation rules;
- 3D/report/blog/catalogue/analytics decisions;
- known failure modes and anti-loop development rules;
- benchmark and differentiation notes.

## Authority and confidence

Use this hierarchy:

1. **Current checked-out repository** for exact paths, signatures, fields, migrations, and runtime behaviour.
2. **Approved product/architecture rules in this folder** for intended design boundaries.
3. **Historical implementation notes** for context and known regressions.

Labels used in domain documents:

- **Established** — repeatedly confirmed in project work.
- **Current implementation note** — observed in a supplied file or prior repository inspection; verify it still exists.
- **Intended rule** — agreed behaviour that agents should preserve or move toward.
- **Repository verification required** — exact implementation was not present in the documentation source set and must be inspected before a logic edit.

## Reading map

| Task | Read first |
|---|---|
| Any change | `../AGENTS.md`, this file |
| Company/site copy | `product/company-context.md`, `product/product-vision.md` |
| Architecture/refactor | `architecture/application-architecture.md`, `architecture/shared-tool-contract.md` |
| Packaging Flow | `architecture/packaging-flow.md` |
| Multi-product Bag/Container | `architecture/shared-tool-contract.md` plus the affected domain document |
| CSS/templates/JS | `frontend/theme-and-components.md`, `frontend/interactions-and-accessibility.md` |
| Bag logic | `domain/bag-selection-logic.md` |
| Container/box selection | `domain/container-selection-logic.md` |
| Palletization | `domain/palletization-logic.md` |
| Transport loading | `domain/transport-selection-logic.md` |
| 3D/PDF | `features/three-d-rendering-and-reports.md` |
| Public site/blog/SEO | `features/public-site-blog-and-seo.md` |
| Catalogue/access/analytics | `features/catalogue-access-and-analytics.md` |
| Testing/process | `engineering/agent-workflow.md`, `engineering/testing-and-verification.md` |
| Known regressions | `engineering/known-issues-and-regressions.md` |
| Context/token efficiency | `maintenance/context-and-token-policy.md` |
| Competitors | `research/benchmarks.md` |

## Source lineage

The initial version was assembled in July 2026 from Packaging Engineering Project conversations and available project notes, including:

- palletization shared UI/workflow refactor notes;
- container-selection engine and 3D-rendering code excerpts;
- blog/SEO asset notes;
- historical decisions from Container, Multi-product Container, Bag, Multi-product Bag, Palletization, Transport, Packaging Flow, public-site, analytics, and deployment work.

This is a living repository asset. Update it in the same pull request when a change alters an architecture contract, formula, assumption, result meaning, URL, shared surface, or workflow state shape.
