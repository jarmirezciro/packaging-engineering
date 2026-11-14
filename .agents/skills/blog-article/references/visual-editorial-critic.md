# Visual Editorial Critic — Hard Quality Gate (v1)

## Goal

Prevent technically correct but confusing, unattractive, inaccessible, or misleading blog visuals from being incorporated or published.

This review supplements—not replaces—`fresh-eyes-business-reader.md`, `kollipack-graphic-style-guide.md`, `comparative-figure-workflow.md`, and the article's factual verification.

## Review the **visible results**, not intentions

The critic must examine:
1. Each final generated/composed figure as an actual image, at native scale and realistic article/mobile display width.
2. The rendered complete article, including the figure order, white space, heading hierarchy and captions.
3. At least one approved article figure reference plus the applicable visual pattern (for scenario setup, `../assets/approved-packaging-scenario-setup-reference.webp`).

Do not pass a figure from filenames, resolution checks, prompt descriptions, code output, an image manifest, or a self-reported claim alone. If final images cannot be viewed, report **NOT REVIEWED** and block final/published status.

## Independent challenge

Prefer an editorial review pass isolated from the brief and from the authoring agent, preferably a separate reviewer/context when available. The critic should receive only the draft article, rendered figures, captions and verified claims required to check factual fidelity. If a separate reviewer is unavailable, explicitly record that this was a self-review; do not claim independent approval.

## Per-figure questions

- **Five-second test:** What one idea does this figure explain? Is it immediately understandable?
- **Fidelity:** Are units, counts and shown geometry consistent with evidence? Is conceptual art clearly distinguished from real calculation output?
- **Cropping:** Is every important object complete, including cartons, case flaps, entire pallet base, stack top, and relevant straps/edges?
- **Comparability:** Are like-for-like source/result views similarly scaled with consistent labels?
- **Readability:** Is the image legible at actual article width and on a mobile screen, not just at 100% desktop zoom?
- **Hierarchy:** Are the key physical objects and result numbers visually prominent, rather than empty card space or UI chrome?
- **Aesthetics:** Does it look like a polished KolliPack editorial figure instead of a documentation screenshot collage, QA worksheet or generic icon strip?
- **Scope:** Are all depicted packaging stages actually in the study?
- **Family resemblance:** Do cards, palette and text treatment match the applicable approved in-article examples?

Record two independent decisions for each applicable figure. Inspect the finished artwork beside the applicable approved reference at native resolution and in realistic desktop and mobile layouts.

- **Visual fidelity.** Check materials, perspective, completeness, scale, composition, typography, stage cards, labels, input strips and connectors as applicable to the chosen figure family.
- **Engineering meaning.** Check what the figure communicates, including its relationships, scope, terminology, verified constraints and whether it distinguishes conceptual depiction from evidence.

Use `REVISE` when either criterion needs correction and the figure does not meet a hard-fail condition below. A faithful style cannot compensate for the wrong relationship, and technical accuracy cannot compensate for a weak illustration. Automated reports verify structure only.

## Automatic FAIL — must correct before publication

- A core object or important result render is cropped, hidden or too small to inspect.
- An apparent geometry, count, result, label or metric is incorrect or unsupported.
- Figure recreates a comparator interface or invents a screenshot as if it were real evidence.
- A figure presents an unsupported stage as part of a verified calculation or result.
- Poor visual hierarchy makes the main message impossible to recognize quickly.
- Critical labels cannot be read at realistic display size.
- Excessive irrelevant whitespace shrinks actual evidence or makes a render misleading.
- An approved visual/figure was replaced without explicit authorization in `publish_approved` mode.
- No actual visual inspection was performed.

## Decision states

- `PASS`: all hard fails absent and the figure communicates its intended message.
- `REVISE`: no critical factual violation, but composition, legibility or clarity requires rework.
- `FAIL`: any hard fail above; do not publish.
- `NOT REVIEWED`: final image/page cannot be inspected; do not publish.

Do not turn subjective quality into a pretend automated score. Record concise, concrete feedback per figure with image filename, intended message, decision and needed correction.

## Revision and stopping rule

- Repair only failed figures; protect previously approved visuals.
- Review a revised image again at normal display size.
- No more than one focused revision pass per figure in an ordinary article task. If still not passing, stop and report to the owner; do not silently accept and do not enter an endless regeneration loop.
- Keep thumbnail approval separate: the existing canonical thumbnail workflow remains `review_required` pending owner approval.

## Required output

At the end of the article task report include a short **Visual QA** record:

| Asset | Purpose | Native + display inspected? | Decision | Notes |
|---|---|---|---|---|

Add an overall `PASS / REVISE / FAIL / NOT REVIEWED` decision. Publication requires `PASS` plus the normal human approval/evidence gates. A self-review is not a substitute for owner approval when the task requires it.
