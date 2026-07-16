# Application architecture

## Platform

KolliPack is a Django application. Exact app layout must be read from the current repository, but the intended responsibilities are stable.

## Layer responsibilities

### Domain engines

Pure or mostly pure calculation code:

- geometry;
- orientation generation;
- feasibility constraints;
- ranking inputs;
- placements and pattern generation;
- engineering metrics.

Engines should not know about HTTP requests, templates, browser element IDs, or session objects.

### Shared tool services

A tool service commonly:

- normalizes inputs from manual and catalogue sources;
- calls the engine;
- applies business-level filtering and ranking;
- converts engine objects into serializable result structures;
- prepares data for presenter/report layers.

The project has used shared structures such as:

```text
packagingapp/tools/<tool>/state.py
packagingapp/tools/<tool>/serializers.py
packagingapp/tools/<tool>/service.py
packagingapp/tools/<tool>/presenter.py
```

Verify current paths before editing.

### Presenters / UI contracts

Presenters convert domain results into stable template-friendly contracts. Contracts should contain primitives, lists, dictionaries, image URLs/paths, display labels, and explicit unit values.

### Views and orchestration consumers

Standalone views handle request parsing, forms, permissions, messages, and response selection. Packaging Flow views orchestrate steps and adapt shared tools to prefixed workflow fields.

Multi-product Container Selection and Multi-product Bag Selection are also consumers of their respective shared tools. They may add multi-row input handling, aggregation, batch selection, and multi-product-specific result composition, but must call the same authoritative engine/service/presenter/renderer contracts as the standalone tool wherever the underlying operation is the same.

### Templates and shared wrappers

The target architecture is one shared wrapper/partial tree per tool, consumed by standalone and workflow contexts with parameters such as:

- `mode` (`standalone`, `workflow`, or public/SEO context);
- `prefix` for unique field IDs and names;
- tool UI contract;
- current values;
- source/catalogue mode;
- selected/pending result.

### JavaScript

JavaScript may:

- browse/select catalogue rows;
- hydrate forms;
- maintain prefixed DOM IDs;
- switch views/tabs;
- rotate/zoom/pan 3D scenes;
- preserve page position;
- submit or fetch results.

It must not become a second calculation engine.

### Reports

Report builders receive normalized result data. They should not re-run a separate interpretation of the algorithm unless explicitly designed as a reproducible engine call using the same service.

## Architecture health test

A tool is architecturally healthy when a small shared UI, result-label, or graphics change can be made once and appear in every relevant consumer without copying a large block of HTML/JS/Python. For Bag and Container Selection, this includes standalone, Packaging Flow, and the corresponding multi-product tool.

Current historical maturity notes:

- Container Selection reached the desired shared-wrapper direction and became the reference.
- Bag Selection followed the same direction after workflow cleanup.
- Palletization was moved toward shared wrapper/partials and a `pallet_ui` / `pallet_values` contract.
- Transport reused shared pieces but historically retained some workflow-owned hidden fields/JavaScript and required strict parity checks.

Treat these as prompts for inspection, not proof of the current branch state.
