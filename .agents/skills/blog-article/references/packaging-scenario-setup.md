# Packaging Scenario Setup — Approved Modular Figure Pattern (v1)

## Purpose and scope

Introduce the **physical packaging scenario** before presenting input screens, calculations or software comparisons. This figure is a *conceptual editorial explanation*, not a substitute for measured geometry, backend output, real result renders or a screenshot.

The figure's **approved visual reference** is:

`../assets/approved-packaging-scenario-setup-reference.webp`

It establishes the editorial language (clean, recognizable packaging objects; light background; rounded panels; navy type; restrained KolliPack green accents; concise input strips; easy-to-follow arrows). **It is not a layout or data template to copy literally.** Do not reuse its three stages, dimensions, object counts or product type in unrelated articles.

## Build the flow from the actual case

1. Read the case inputs and article scope, not the list of KolliPack tools.
2. Identify the **minimum two to five physically meaningful stages** that explain the problem. Fewer stages are acceptable if the requested article genuinely requires only one packaging unit; do not manufacture a second stage.
3. Select names matching the case: product, bag, retail carton, inner pack, shipping case / RSC, crate, palletized load, transport container, trailer, or mixed load.
4. Decide whether the flow is sequential, branching (multiple case alternatives), or convergent (mixed cargo loaded together). The shape of the diagram must match that relationship.
5. Record just the **essential verified inputs** for each stage: dimensions, weight, quantity, orientation, material thickness, permitted overhang, stack height, payload, or other actually relevant constraint.
6. Write one reader-facing sentence describing why the stages are connected. Use it as an optional small bottom takeaway banner—not as a repeating slogan.
7. Choose the figure layout for readability; never squeeze five tiny cards into a three-card design.

Illustrative scenarios (not mandatory or exhaustive):

| Case scope | Suitable flow |
|---|---|
| Individual packaging | Product → Bag; Product → Box |
| Case selection | Product → Shipping case |
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
- `stage_list`: actual packaging objects in order; include branching when appropriate.
- `stage_inputs`: exact verified values and units for each stage.
- `illustration_role`: `conceptual` or `evidence_derived`.
- `visual_reference`: approved asset above, used **for style**, not content.
- `composition`: 2-card, 3-card, 4/5-stage adapted, branching or convergence.
- `headline`, `subtitle`, optional `takeaway`: user-facing, no promotional filler.
- `excluded_stages`: out-of-scope steps the image must not add.

## Before integrating

Render, **look at the actual image**, and test at full size and article width. Confirm:

1. A non-expert understands the physical progression in five seconds.
2. Every stage belongs to this case and all labels/units are correct.
3. The physical objects are complete and easy to recognize.
4. The figure does not depict unverified geometry as factual evidence.
5. The visual style matches the approved reference without cloning the reference's content.
6. The caption explains its *conceptual* role when exact geometry is not evidenced.

If any item fails, do not ship the figure; follow `visual-editorial-critic.md`.

## Distinguish two visual jobs

**Packaging Scenario Setup** illustrates the physical chain. **Software Input Comparison** displays real application screenshots explaining how inputs are entered. Do not force both into a single dense image. In a named-tool comparison, show the conceptual setup first when it adds clarity, then separate input comparisons and real result render matrices.

## Thumbnail distinction

This figure follows the **light in-article** KolliPack graphic style. It is *not* the dark approved thumbnail system. All new blog thumbnails still follow `thumbnail-workflow.md` and the approved thumbnail board.

<!-- BEGIN KOLLILABS-EDITORIAL-FIGURES-V1 -->
## Reproducible visual execution (KolliLabs Editorial Figures)

Use `../../kollilabs-editorial-figures/SKILL.md` for the approved graphical identity, artwork direction, editable figure-spec contract and deterministic rendering of this setup pattern. This case-setup reference still determines **what physical stages and verified inputs** belong in a scenario. Its approved existing style example remains authoritative; the additional two owner-approved examples in the new skill provide complementary graphical references. Do not use the new skill to copy benchmark values into unrelated cases.
<!-- END KOLLILABS-EDITORIAL-FIGURES-V1 -->
