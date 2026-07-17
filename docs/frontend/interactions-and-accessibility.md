# Interaction and accessibility rules

## Page-position preservation

A recurring problem was that selecting an option or running a tool moved the page to the top. Before applying a workaround, identify the cause. Common causes to inspect:

- form submission to the same URL without an anchor/scroll restoration;
- buttons accidentally defaulting to `type="submit"`;
- links with `href="#"`;
- focus being moved to the top or a replaced DOM node;
- full-page re-render after POST;
- explicit `scrollIntoView`, `window.scrollTo`, or modal code;
- URL fragments being removed;
- dynamic partial replacement losing the active element.

Preferred solutions are lifecycle-based and accessible:

- use correct button types;
- preserve/restore a meaningful section anchor after POST;
- use PRG and fragments where appropriate;
- retain focus on the action/result region;
- for asynchronous updates, update only the needed region;
- avoid arbitrary `setTimeout` scrolling unless no stable event exists.

The implemented cross-tool contract, root-cause inventory, opt-in markup,
programmatic-submit API, validation behavior, and regression checklist are
documented in `tool-scroll-preservation.md`.

## Prefix-safe interaction

In Packaging Flow, all JavaScript must work when:

- several steps are on one page;
- two steps use the same tool type;
- the same modal/selector component is repeated;
- standalone mode uses an empty prefix.

## 3D controls

Approved interaction direction:

- controls such as Reset, Top, and other views sit beside the “Interactive 3D result” heading;
- avoid redundant explanatory paragraphs when the controls are self-evident;
- mouse/touch controls should not unexpectedly scroll the document;
- the model should open slightly zoomed out so the full package/load fits;
- PDF export should capture the intended report view, not an accidental clipped state.

## Accessibility baseline

- labels are associated with inputs;
- row selection has focus and keyboard behaviour;
- button text describes the action;
- validation messages identify the field and remedy;
- color is not the only indication of state;
- collapsible instructions expose correct expanded state;
- result changes should be announced or focused appropriately without stealing the user’s location.
