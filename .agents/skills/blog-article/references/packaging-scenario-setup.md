# Packaging Scenario Setup — Approved Modular Figure Pattern (v1)

## Purpose and scope

Introduce the **physical packaging progression or engineering decision** before presenting input screens, calculations or software comparisons. This figure is a *conceptual editorial explanation*, not a substitute for measured geometry, backend output, real result renders or a screenshot.

The figure's **approved visual reference** is:

`../assets/approved-packaging-scenario-setup-reference.webp`

It establishes the editorial language (clean, recognizable packaging objects; light background; rounded panels; navy type; restrained KolliPack green accents; concise input strips; easy-to-follow arrows). **It is not a layout or data template to copy literally.** Do not reuse its three stages, dimensions, object counts or product type in unrelated articles.

## Select and specify the figure from the case

1. **Decide whether setup helps.** Identify what the reader needs to understand before seeing the results. Use a setup figure when it clarifies the case. If the article explains a mechanism in one fixed package, a concept or comparison figure may do more useful work. A tool mention alone does not call for a figure.
2. **Name the relationship.** It may be physical containment or transfer, selection among alternatives, design evaluation, a branch, or convergence of mixed loads. Use connectors only where their direction conveys a real relationship.
3. **Identify stages and inputs.** Derive each stage and its necessary constraints from the article scope and verified evidence. An assortment represents catalogue choices. A pallet represents a physical level only when the case evaluates it.
4. **Choose the smallest clear composition.** Select the appropriate pattern in the editorial figure skill. Let the evidence determine the number of stages, and check the reading order on mobile. A compact navigation or workflow strip serves a separate purpose from a full setup illustration.
5. **Separate facts from depiction.** Mark conceptual artwork and record the source of dimensions, units, counts and constraints. Use actual results or verified geometry for exact packing. Use a takeaway band only when it explains the decision.

Illustrative scenarios (not mandatory or exhaustive):

| Case scope | Suitable flow |
|---|---|
| Individual packaging | Product → Bag; Product → Box |
| Stock-case selection | Product → Packaging Catalogue → Selected Case |
| Pallet arrangement selection | Case Alternatives → Palletization Evaluation → Selected Arrangement |
| Palletization | Shipping case → Pallet |
| Pallet transport | Pallet → Transport container |
| Integrated design | Product → Shipping case → Pallet |
| End-to-end | Product → Case → Pallet → Transport container |
| Multi-level | Product → Inner pack → Case → Pallet → Transport container |
| Mixed cargo | Boxes + Pallets → Transport container |
| Two viable designs | Product → Case A / Case B → alternative pallet loads |

Include *only* the stages the actual article evaluates. A generic header widget or extra Transport icon is not evidence that the article covers transport.

## Editorial visual contract

- Light off-white or soft grey canvas; rounded white cards; thin subtle borders; restrained shadows.
- Navy for headings, muted grey for explanations, KolliPack green for stage numbers and connecting arrows. Natural cardboard/wood tones in the physical illustrations.
- Large, recognizable physical objects, preferably consistent isometric/three-quarter perspective, complete and uncropped.
- Clear stage name, illustration, and one concise input strip per stage; green arrows show meaningful relationships.
- Simple headline and short subtitle. Optional short takeaway banner when it conveys a decision.
- Match existing article width; inspect at actual rendered website and mobile sizes.
- Two-stage cases should have two generous cards; four/five stages can use a wide or wrapped layout with clear reading direction. Branching/mixed cases require genuine branch/converge connectors.
- Use appropriate objects: a bag must look like a bag, an RSC should show believable flaps when opened, a pallet must show its deck and load, a container must show its enclosure/loading opening if relevant. Avoid generic cubes or detached glyphs.
- This can be an **editorial AI illustration** because it explains the hierarchy conceptually; for exact engineering counts, patterns, dimensions, or physical placements, use deterministically produced geometry and validate against the backend/source.
- If generated imagery contains visually countable objects inconsistent with a stated quantity, fix the illustration or remove the implied exact count. The approved example contains illustrative packing and is **not proof** of a particular 12-item layer pattern.
- Never invent text, technical results, competitor UI, logos or certified performance from the illustration.

## Required figure specification (fill before generation)

- `purpose`: one sentence stating what the reader should grasp.
- `stage_list`: physical stages or decision steps in order, with branching where appropriate.
- `stage_inputs`: exact verified values and units for each stage.
- `illustration_role`: `conceptual` or `evidence_derived`.
- `visual_reference`: approved asset above, used **for style**, not content.
- `composition`: 2-card, 3-card, 4/5-stage adapted, branching or convergence.
- `headline`, `subtitle`, optional `takeaway`: user-facing, no promotional filler.
- `excluded_stages`: out-of-scope steps the image must not add.

## Before integrating

Render, **look at the actual image**, and test at native size, article width and mobile width. Record conceptual correctness and visual consistency separately. Confirm:

1. A non-expert understands the progression in five seconds.
2. Every stage belongs to this case and all labels/units are correct.
3. The physical objects are complete and easy to recognize.
4. The figure does not depict unverified geometry as factual evidence.
5. The visual style matches the approved reference without cloning the reference's content.
6. The caption explains its *conceptual* role when exact geometry is not evidenced.

If any item fails, do not ship the figure; follow `visual-editorial-critic.md`.

## Distinguish two visual jobs

**Packaging Scenario Setup** illustrates the physical chain or engineering decision. **Software Input Comparison** displays real application screenshots explaining how inputs are entered. Do not force both into a single dense image. In a named-tool comparison, show the conceptual setup first when it adds clarity, then separate input comparisons and real result render matrices.

## Thumbnail distinction

This figure follows the **light in-article** KolliPack graphic style. It is *not* the dark approved thumbnail system. All new blog thumbnails still follow `thumbnail-workflow.md` and the approved thumbnail board.

<!-- BEGIN KOLLILABS-EDITORIAL-FIGURES-V1 -->
## Reproducible visual execution (KolliLabs Editorial Figures)

For every selected setup figure, follow `../../kollilabs-editorial-figures/SKILL.md`. Inspect the approved artwork, produce subject illustrations and a figure specification, and compose them with the existing deterministic renderer and design tokens. This case-setup reference still determines **which physical stages or decision steps and verified inputs** belong in a scenario. Its approved existing style example remains authoritative; the additional two owner-approved examples in the new skill provide complementary graphical references. Do not use the new skill to copy benchmark values into unrelated cases.
<!-- END KOLLILABS-EDITORIAL-FIGURES-V1 -->
