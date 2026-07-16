# Shared tool contract

## Goal

A tool must have one authoritative implementation that can be rendered in different contexts without logic or UI divergence.

## Required consumers

For every shared tool change, create a consumer matrix:

| Consumer | Required check |
|---|---|
| Standalone tool | Full manual and catalogue flow |
| Packaging Flow | Prefix-safe fields, upstream inheritance, result selection, session persistence |
| Multi-product Container Selection | Shared Container engine/service/presenter/renderer; multi-row orchestration and aggregate output remain coherent |
| Multi-product Bag Selection | Shared Bag engine/service/presenter/renderer; multi-row orchestration and aggregate output remain coherent |
| Public SEO calculator | Shared engine/UI contract; page-specific demo state only |
| PDF/report | Same values, selected visualization, original units |
| Catalogue | Product/packaging images, row selection, no redundant buttons |
| JavaScript | Unique IDs, hydration, no unexpected scrolling |

Not every tool currently has an SEO page, but the check must explicitly say “not applicable” rather than ignore the surface.

## Tool-specific consumer graph

### Container / Box Selection

Mandatory consumers to assess after a shared logic, UI, result-contract, or graphics change:

1. Standalone Container Selection.
2. Container step inside Packaging Flow.
3. Multi-product Container Selection.
4. Container result/PDF/image endpoints and catalogue integration where applicable.

### Bag Selection

Mandatory consumers to assess after a shared logic, UI, result-contract, or graphics change:

1. Standalone Bag Selection.
2. Bag step inside Packaging Flow.
3. Multi-product Bag Selection.
4. Bag result/PDF/image endpoints and catalogue integration where applicable.

Multi-product tools can have additional aggregation rules, but they must not be left on an older renderer, result-card schema, instruction block, CSS contract, or graphics style when the shared tool is upgraded. The previous graphics refactor missed these consumers; treat that as a named regression fixture.

## Context contract

A shared wrapper should receive a predictable context. A representative contract is:

```python
{
    "mode": "standalone" | "workflow" | "seo",
    "prefix": "" | "<step index or stable prefix>",
    "ui": {...},
    "values": {...},
    "pending_result": {...} | None,
    "selected_result": {...} | None,
    "messages": [...],
}
```

Palletization historical integration used:

```python
step["pallet_ui"]
step["pallet_values"]
step["mode"] = "workflow"
step["prefix"] = str(idx)
```

The exact current keys may differ. Do not add parallel contract names without first checking the existing wrapper and presenter.

## Prefix rules

- Every workflow field, hidden input, modal target, result action, and JavaScript lookup must be derived from `prefix`.
- Do not leave hard-coded `pallet_...`, `bag_...`, or transport IDs inside multi-step workflow pages.
- Shared scripts should be included by the wrapper once, not copied into the workflow template.
- Multiple steps of the same tool type must coexist without DOM collisions.

## Selection and propagation

- Calculating a result does not always equal selecting it.
- The effective display result may be `pending_result`, `selected`, or another explicit state depending on current architecture.
- Only the selected/committed output should feed downstream steps unless the product specification explicitly allows pending propagation.
- Changing an upstream selected output invalidates downstream steps that depend on it.

## Completion rule

Do not deliver a backend-only shared contract while saying integration is complete if the workflow template still contains an old inline block. A refactor is complete only after the old duplicate path is removed or explicitly documented as transitional.
