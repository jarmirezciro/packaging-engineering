# Known issues and regression traps

## 1. Partial shared refactors

Symptom: backend creates a shared UI contract but workflow template still renders an old inline block.

Prevention: remove or migrate the legacy template and scripts in the same coherent task; do not report full parity before that.

## 2. Duplicate hidden inputs and hard-coded IDs

Symptom: catalogue selection or result hydration works standalone but fails in Flow, especially with repeated steps.

Prevention: all IDs/names/selectors derive from `prefix`; wrapper includes scripts once; workflow owns no duplicate tool hidden fields.

## 3. Non-JSON session objects

Observed example:

```text
TypeError: Object of type PackagingMaterial is not JSON serializable
```

Prevention: shared serializer converts models, QuerySets, `Decimal`, numpy, dataclasses, and placement objects to primitives before session write.

## 4. Rotation restrictions applied only to the main region

Symptom: Container Selection produces forbidden orientations in recursive leftover subboxes.

Prevention: pass and enforce R1/R2/R3 in every `MainBox`, leftover, recursive, ranking, and render path.

## 5. Bag sealing margin drawn on the wrong dimension

Symptom: image adds sealing allowance to width or lets product occupy sealing area.

Prevention: reserve sealing space in bag length only; keep tolerance separate; test displayed geometry and calculation.

## 6. Pallet pinwheel/mosaic looks plausible but is wrong

Symptom: odd pattern for 230×170×130 on 1200×800, duplicate cartons, bad filler symmetry, or invalid interlock.

Prevention: coordinate/bounds/overlap assertions plus visual fixture; conservative interlock filtering; dedupe symmetric results.

## 7. Transport door end or view inconsistency

Symptom: doors are on the wrong end or Main/Opposite/Top/Side show inconsistent placements.

Prevention: one coordinate system and one placement list for every camera; explicit door-end fixture.

## 8. PDF exports the wrong candidate

Symptom: Top-5 selected result differs from the image/data in PDF.

Prevention: report receives selected normalized result ID/data; no independent “first candidate” lookup.

## 9. Tool actions scroll to page top

Symptom: every select/calculate action loses the working position.

Prevention: identify form/link/focus/DOM cause; use anchors/focus/partial update;
avoid timeout hacks. Full-page KolliPack tool forms now use the shared contract
in `docs/frontend/tool-scroll-preservation.md`; new programmatic submissions must
use `window.KolliPackToolScroll.submit(form)` and stable opt-in instance keys.

## 10. Global CSS replacement for local issue

Symptom: one tool looks better but other pages regress or lose the approved theme.

Prevention: inspect actual loaded CSS, reuse shared classes, add scoped rules, test app shell/sidebar/responsive widths.

## 11. Debug visuals leak into final UI

Symptom: matplotlib axes, mesh, subbox wireframes, titles, or development colors appear in customer result/PDF.

Prevention: explicit clean/debug render modes with tests/defaults.

## 12. SEO demo changes application defaults

Symptom: standalone or Flow unexpectedly opens with public demo values.

Prevention: inject demo state only in SEO-page view/context; shared engine remains stateless.

## 13. “Done” before consumer parity

Symptom: agent repeatedly asks for the next file after each partial change.

Prevention: map the vertical slice first and finish all required layers before final reporting.
## 14. Multi-product consumers left on legacy graphics

Symptom: standalone Bag or Container Selection receives improved graphics/result components, while Multi-product Bag Selection or Multi-product Container Selection still renders the former image style or copied template.

Prevention: include both multi-product tools in the initial consumer map; reuse the shared renderer/presenter/component; verify an equivalent one-row fixture and a genuine multi-row fixture before completion.

## 15. Transport packing-mode semantics leak into another mode

The specific Maximum, Accessible Sequence, and Strict Sequence examples below
are historical compatibility traps. The current active engine dispatches Space
Evenly V1 only; retain these notes for archived mode work, not as a claim that
those solvers currently produce placements.

Symptom: fixing a residual/compaction issue in one mode changes geometry in Maximum, Accessible Sequence, or Strict Sequence.

Prevention: treat `docs/domain/transport-container-engine.md` as the algorithm contract; trace dispatch before editing; prefer mode-specific helpers for mode semantics; run direct engine geometry signatures for all unaffected modes after any shared-helper change.

## 16. Strict Sequence reuses a side residual

Symptom: a later product is placed beside an earlier product behind its strict frontier.

Prevention: Strict Sequence creates one full-width forward space after every product row. Do not pass side/top/deep residuals from the completed row to the next row. This is a space-generation rule, not a compaction problem.

## 17. Maximum residual partitions become invisible physical walls

Symptom: later products show repeating gaps aligned with earlier-product split boundaries even though the physical corridor is continuous.

Prevention: Maximum Utilization must evaluate physical free geometry without treating guillotine/residual split planes as obstacles. Regression fixtures and accepted semantics are maintained in `docs/domain/transport-container-engine.md`.
