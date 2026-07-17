# Tool scroll preservation

## Status and scope

Implemented in July 2026 for interactive KolliPack tool surfaces that perform a
full-page request. The shared implementation is
`static/js/tool_scroll_preservation.js`.

The contract applies to:

- standalone Palletization, Container Selection, Bag Selection, and Transport
  Container tools;
- Palletization on the public SEO calculator page;
- Packaging Flow step forms, including repeated instances of the same tool;
- native form submissions and tool scripts that submit programmatically.

Multi-product Container Selection and Multi-product Bag Selection were assessed
as part of the change. Their Run and result interactions already use `fetch()`
and update the existing page, so they do not opt into full-page scroll
restoration. This distinction is intentional.

No Sales Multiple or separate branding/packaging-selection tool route existed
in the repository when this contract was introduced. New interactive tools must
be assessed against this contract when they are added.

## Root causes found

The investigation identified two causes:

1. Standalone and SEO tool actions POST back to the current page. Packaging Flow
   performs POST-redirect-GET for step actions. Both navigation patterns create
   a new document without preserving the active tool's viewport position.
2. Shared tool scripts frequently called `form.submit()` directly. That method
   does not dispatch a `submit` event, so a listener for native submissions
   alone cannot preserve the position. The Transport tool also contained two
   delayed `scrollIntoView()` calls that forced the catalogue or product section
   into the viewport after a response.

The audit found no tool `href="#"` links, autofocus behavior, global
`history.scrollRestoration` override, global `scrollTo`, or result DOM
replacement responsible for the page-to-top jump.

## Shared contract

### Opt-in markup

A full-page tool form or stable ancestor opts in with a semantic instance key:

```html
<form data-preserve-tool-scroll="container-selection-standalone">
```

Keys must be unique within a rendered page. Packaging Flow uses
`workflow-step-<index>` on each expanded step form and `packaging-flow` on the
stable page ancestor. Prefix-safe tool IDs and names remain unchanged.

Do not derive keys from CSS classes, element order outside the established
workflow index, translated labels, or generated display text.

### Native and programmatic submission

The shared script captures native `submit` events. Code that calls
`form.submit()` must instead use:

```javascript
window.KolliPackToolScroll.submit(form);
```

This method records the marked tool instance and then preserves the existing
submission behavior. Do not duplicate storage or scrolling code in individual
tool partials.

### Stored state and restoration

The script stores one pending interaction in `sessionStorage` with:

- the current path and query string;
- the semantic tool-instance key;
- the marked element's top position relative to the viewport;
- a creation timestamp.

The state is tab-scoped, expires after 30 seconds, and is consumed once. A
matching response restores the same layout-relative position with one
`requestAnimationFrame` adjustment. The frame waits for initial rendering and
native scroll handling to settle; it is not a delay, retry loop, timer, or
polling mechanism. The solution stores no hard-coded page offsets and does not
change workflow session data.

State is ignored when:

- the path or query string does not match;
- the marked tool instance no longer exists;
- the state is stale or malformed;
- the URL contains a fragment, so intentional anchor navigation wins;
- the navigation is Back or Forward, so native history restoration wins.

Normal page entry, copied URLs, new tabs, refreshes without a pending tool
submission, and navigation to other pages therefore receive no unrelated tool
position.

### Validation exception

Validation remains deliberate and accessible. Error summaries use
`data-tool-validation-errors`, `role="alert"`, and `tabindex="-1"`. When a
matching response contains a validation target, the shared script focuses it
without an intermediate scroll and then brings it into view. Django fields with
`aria-invalid="true"`, `.is-invalid`, and `.errorlist` are also supported.

Do not mark successful notices or ordinary warnings as validation errors.

## Transport-specific cleanup

The legacy `scroll_target` hidden field/context value and delayed catalogue and
product `scrollIntoView()` calls were removed. Catalogue visibility and selected
row behavior remain unchanged; only the forced viewport movement was removed.

## Consumer and regression checklist

When changing shared tool forms or scripts, verify:

| Surface | Expected behavior |
|---|---|
| Standalone Palletization | Radio/select changes, result selection, valid calculation, and invalid calculation preserve or deliberately show errors. |
| Standalone Container Selection | Product/container source, catalogue selection, Top 5, and result selection preserve the active area. |
| Standalone Bag Selection | Product/bag source, catalogue selection, Top 5, and result selection preserve the active area. |
| Standalone Transport | Catalogue and product-row actions do not force another section into view; result view buttons remain local DOM updates. |
| Packaging Flow | Each step restores only its own prefixed form; repeat the check with two instances of the same tool type. |
| Multi-product Container/Bag | Run, row expansion, drawing, and result selection remain non-navigating `fetch()` updates. |
| SEO Palletization | The calculator preserves position without affecting public-page anchors. |
| Navigation | Direct entry, valid fragments, refresh, Back/Forward, copied URLs, and a new tab retain native behavior. |

Also check the browser console at desktop and mobile widths. Automated template
coverage lives in `ToolScrollPreservationTests` in `packagingapp/tests.py`.

## Non-goals

This mechanism does not convert tools to AJAX, alter engines or result contracts,
store state in Django sessions, disable native browser restoration globally, or
move users automatically to successful results.
