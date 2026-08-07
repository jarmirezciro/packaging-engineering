# Codex Terra Task — Recreate the TOPS Pro Pallet Benchmark and Build the Public KolliPack Demo Article

## Recommended Codex configuration

```text
Model: GPT-5.6 Terra
Reasoning: Medium
Speed: Standard
```

## Objective

Create a **new public-facing KolliPack demo article from scratch** based on the latest corrected TOPS Pro palletization benchmark package.

The article must use the established KolliPack blog structure, editorial workflow, graphic style, and prepopulated-case behavior already used in the previous Packaging Flow and Container Selection demo articles.

This task has two mandatory phases:

1. **Evidence and public-case gate**
2. **Public article creation**

Do not begin Phase 2 unless every Phase 1 gate passes.

The article is intended for:

- Packaging engineers
- Operations and logistics managers
- Packaging buyers
- Business readers evaluating palletization software

The article is **not** an internal QA report, repository report, backend report, or development log.

---

# Source attachments

The task will include:

1. The latest corrected benchmark ZIP:
   ```text
   tops_palletization_comparisson.zip
   ```

2. The latest KolliPack project on the `pre-production` branch.

3. The existing KolliPack blog-agent skill and references.

4. The official KolliPack logo assets and logo guidelines already installed or attached.

Use only the latest corrected benchmark ZIP. Do not use an older comparison package.

---

# Existing failed article

Do not reuse, polish, quote, or salvage prose from any previous failed TOPS Pro comparison article.

If a file already exists at:

```text
packagingapp/content/blog/articles/kollipack-vs-tops-pro-palletization-benchmark.md
```

treat it as disposable and replace it completely only after Phase 1 passes.

Do not preserve its status, warnings, development language, or CTA.

The new article must remain:

```toml
status = "draft"
```

---

# Mandatory agent and skill usage

Before doing any work, read and follow:

```text
.agents/skills/blog-article/SKILL.md
```

Read these references:

```text
.agents/skills/blog-article/references/blog-architecture.md
.agents/skills/blog-article/references/article-schema.md
.agents/skills/blog-article/references/case-package-contract.md
.agents/skills/blog-article/references/demo-case-study-profile.md
.agents/skills/blog-article/references/backend-evidence-policy.md
.agents/skills/blog-article/references/business-context-and-product-selection.md
.agents/skills/blog-article/references/title-and-story-rubric.md
.agents/skills/blog-article/references/fresh-eyes-business-reader.md
.agents/skills/blog-article/references/demo-case-study-lessons.md
.agents/skills/blog-article/references/editorial-style.md
.agents/skills/blog-article/references/image-style-guide.md
.agents/skills/blog-article/references/kollipack-graphic-style-guide.md
.agents/skills/blog-article/references/seo-rules.md
.agents/skills/blog-article/references/quality-checklist.md
```

These are not optional reading.

Use the workflow as sequential review modes inside one Codex task:

1. Backend Evidence Reviewer
2. Public Case Gate
3. Editorial Story Editor
4. Figure and Thumbnail Editor
5. Fresh-Eyes Business Reader
6. SEO and Integration Reviewer

Do not build a multi-agent framework or add new agent infrastructure.

---

# Non-negotiable public-content rule

The public article must never contain internal development language.

The following words or concepts are prohibited from the article body, captions, notes, metadata, CTA, and sources section unless they are part of a public product name:

- `pre-production`
- `repository`
- `backend service`
- `current backend`
- `shared service`
- `Django`
- `session`
- `route implementation`
- `preset mechanism`
- `temporary CTA`
- `draft-only warning`
- `blocking warning`
- `development environment`
- `PDF discrepancy`
- `test client`
- `source package inconsistency`
- `validation failure`
- `Codex`
- `Terra`
- Git branches or commits

Such information may appear only in the final Codex report.

---

# Hard-stop policy

This policy overrides all fallback instructions.

## If any critical evidence is inconsistent:

```text
STOP.
DO NOT WRITE THE ARTICLE.
DO NOT CREATE OR REVISE FIGURES.
DO NOT CREATE THE THUMBNAIL.
DO NOT MODIFY THE ARTICLE FILE.
DO NOT UPDATE THE ARTICLE REGISTRY.
DO NOT CREATE A GENERIC OR TEMPORARY CTA.
ASK THE USER FOR THE EXACT CORRECTED FILE OR AN EXPLICIT EXCLUSION DECISION.
```

Return only:

```text
BLOCKED — CORRECTED INPUT REQUIRED
```

followed by:

- Exact conflicting files
- Exact conflicting field or value
- Which corrected file is required
- Whether the user may explicitly authorize excluding one source

## Critical evidence includes:

- Carton dimensions
- Carton weight
- Pallet dimensions
- Pallet height
- Maximum load height
- Overhang
- TOPS headline result
- KolliPack headline result
- Result table values used in the article
- Any PDF or report intended for an article figure
- The public tutorial URL
- The public prepopulated KolliPack case

Do not continue with “unaffected editorial work.”

Do not insert evidence discrepancies into the public article.

---

# Scope boundaries

## Allowed

- Read the latest benchmark ZIP.
- Read the relevant blog-agent skills.
- Read the minimum palletization code needed to call the existing engine and follow the existing public-case pattern.
- Call the current palletization backend directly.
- Add a minimal data-only palletization case preset using the smallest existing repository pattern.
- Make the minimum targeted view or URL connection needed only when the existing palletization tool requires it for named cases.
- Create the new article Markdown.
- Create article figures from supplied screenshots.
- Create a thumbnail using supplied screenshots and official logo assets.
- Update the article registry when required.
- Add narrowly targeted tests for the new named case.
- Run only the minimal validations listed below.

## Not allowed

Do not modify:

- Palletization engine logic
- Candidate generation
- Pinwheel logic
- Interlock logic
- Deduplication logic
- Pattern ranking
- Calculation formulas
- Three.js rendering
- Existing UI layout or styling
- Existing normal palletization-tool behavior
- PDF logic
- Other articles
- Deployment configuration

Do not:

- Use Playwright
- Take screenshots
- Start broad browser automation
- Run full Django test suites
- Run full palletization regression suites
- Refactor the application
- Commit
- Push
- Merge
- Deploy
- Publish the article

---

# PHASE 1 — EVIDENCE AND PUBLIC-CASE GATE

No article writing is allowed during Phase 1.

## Step 1 — Inspect the latest benchmark package

Unpack:

```text
tops_palletization_comparisson.zip
```

into a temporary task-local folder.

Read every file relevant to the benchmark, including:

- `discussion.txt`
- TOPS carton inputs
- TOPS pallet inputs
- TOPS results table
- TOPS leading result renders
- TOPS secondary result renders
- KolliPack carton inputs
- KolliPack pallet inputs
- KolliPack results table
- KolliPack column result
- KolliPack interlocked result
- KolliPack secondary alternatives
- Any PDF or report included
- Any file containing the public tutorial URL

Do not assume filenames are authoritative.

Do not assume a PDF is correct because it is exported by the application.

## Step 2 — Establish the authoritative benchmark inputs

The expected corrected benchmark values are:

### Carton

```text
Length: 411 mm
Width: 289 mm
Height: 231 mm
Weight: 2,268 g
```

Approximate TOPS reference:

```text
16.2 × 11.4 × 9.1 inches
5 lb
```

### Pallet

```text
Length: 1,219 mm
Width: 1,016 mm
Height: 101 mm
```

Approximate TOPS reference:

```text
48 × 40 × 4 inches
```

### Load limits

```text
Maximum total load height: 1,346 mm
Length overhang: 25 mm
Width overhang: 25 mm
```

Approximate TOPS reference:

```text
53 inches maximum total height
1 inch overhang on each axis
```

Compare every supplied input screenshot, report, PDF, note, and result against these values.

### Mandatory evidence decision

If all files agree, continue.

If a PDF or report disagrees but is intended to appear in the article, stop and request a corrected PDF or report.

If the author explicitly excluded a conflicting file before the task began, record that exclusion in the internal evidence note and do not use the file.

Do not decide independently to exclude a supplied conflicting source.

## Step 3 — Confirm the public TOPS tutorial

Locate the exact public tutorial URL from the supplied benchmark package.

Do not guess it from memory.

Confirm:

- The URL exists in the supplied evidence.
- The TOPS screenshots correspond to that tutorial.
- The title or source description is sufficiently clear for attribution.

If the exact URL is missing or uncertain, stop.

## Step 4 — Reproduce the case with the KolliPack backend

Call the current shared KolliPack palletization engine directly from Python using the corrected values.

Do not copy engine formulas into temporary code.

Record:

- Total generated candidates
- Displayed/deduplicated candidates
- Quantity of each displayed result
- Cartons per layer
- Layers
- Total cartons
- Pattern name
- Layer type
- Interlock availability
- Floor usage
- Volume usage
- Calculated total height
- Total weight when available

The expected headline result is:

```text
50 cartons
10 cartons per layer
5 layers
```

The expected leading displayed quantities from the supplied benchmark are:

```text
50
45
45
40
30
```

If the current backend does not reproduce the approved headline result, stop.

Do not change the engine.

## Step 5 — Reconcile TOPS and KolliPack evidence

Confirm that the supplied evidence supports:

- TOPS maximum: 50 cartons
- KolliPack maximum: 50 cartons
- Both: 10 cartons per layer
- Both: 5 layers
- TOPS supplied result table: 14 candidate rows
- KolliPack current displayed shortlist: 5 options
- Both include leading capacity levels of 50, 45, and 45 cartons
- TOPS leading view is presented as interlocked
- KolliPack leading result shows column plus interlock availability / alternate view

Do not claim exact topology equivalence for lower-ranked patterns unless the images and numbers support it clearly.

## Step 6 — Create the exact public KolliPack case

The demo article is blocked until the exact case is available publicly.

Inspect the existing public-case implementations used by prior articles, including the existing patterns for:

- Container Selection named cases
- Packaging Flow named cases

Follow the smallest, safest existing pattern.

### Preferred route behavior

Create a named public palletization case such as:

```text
/free-palletization-calculator/?case=tops-pro-48x40-benchmark
```

or the equivalent existing palletization route used by the current repository.

Do not invent a new URL family when the existing tool already supports a suitable query-parameter pattern.

### Required populated values

The public case must load:

```text
Carton: 411 × 289 × 231 mm
Carton weight: 2,268 g
Pallet: 1,219 × 1,016 × 101 mm
Maximum total height: 1,346 mm
Length overhang: 25 mm
Width overhang: 25 mm
```

It must produce the approved current results.

### Reader interaction

Readers must be able to:

- View the generated options
- Select the 50-carton result
- Inspect the 45-carton alternatives
- Toggle interlock when available
- Change overhang
- Change height
- Recalculate
- Use the existing report functionality

### Isolation and normal behavior

The named case must not alter the normal empty/default palletization route.

Do not refactor normal tool behavior.

### No generic fallback

If an exact named case cannot be implemented with a small, safe change:

- Stop.
- Do not create the article.
- Ask the user whether to authorize a separate implementation task.

Never point the benchmark CTA to an empty calculator.

Never label a generic calculator link as the benchmark.

## Step 7 — Minimal public-case verification

Run only a narrowly targeted verification.

Confirm through direct view/context, existing service calls, or a targeted Django test client that:

- The named case resolves.
- The expected form/preset values are loaded.
- The result contains 50 cartons.
- The normal palletization route still resolves normally.
- The named case and normal route are distinct.
- The article CTA URL exactly matches the working named case.

Do not run Playwright or take screenshots.

## Phase 1 pass condition

Continue to Phase 2 only when all are true:

```text
[PASS] All critical source inputs agree
[PASS] Exact TOPS tutorial URL confirmed
[PASS] KolliPack backend reproduces 50 cartons
[PASS] Candidate evidence reconciled
[PASS] Exact public KolliPack case works
[PASS] CTA URL opens the exact populated case
```

If any item fails, stop.

---

# PHASE 2 — PUBLIC ARTICLE CREATION

Phase 2 may begin only after Phase 1 passes.

## Public article identity

### Exact visible title

Use:

# One Pallet Case, Two Optimizers: Can KolliPack Match TOPS Pro?

Do not replace it.

### SEO title

Use:

```text
KolliPack vs TOPS Pro Palletization: A 48 × 40 Pallet Benchmark
```

### Slug

Use:

```text
kollipack-vs-tops-pro-palletization-benchmark
```

### Article profile

Use:

```text
demo_case_study
```

Do not classify it as an engineering deep dive.

### Status

Use:

```toml
status = "draft"
```

### Intended length

Target approximately:

```text
1,200–1,600 words
```

Do not create a nine-minute internal-audit article.

---

# Required disclaimer

Include this text verbatim in a compact benchmark-scope note near the beginning:

> TOPS Pro results were reproduced from the public tutorial linked below. KolliPack is not affiliated with or endorsed by TOPS Software Corporation. This article compares one palletization case and does not represent a complete product evaluation.

Do not alter the wording.

Link the exact public tutorial immediately after or inside the same note.

---

# Article narrative

Follow the business-oriented structure used in the successful Packaging Flow and Container Selection articles.

## 1. Result-led opening

Put this result within the first 100 words:

```text
Both tools found 50 cartons:
10 cartons per layer across 5 layers.
```

The opening must answer:

- What was compared?
- What matched?
- Why is that interesting?

Do not begin with product history, software architecture, legal language, or input tables.

## 2. Why this case is useful

Briefly explain:

- The example comes from a public TOPS Pro tutorial.
- The inputs and results are visible.
- It can be reproduced as one focused palletization benchmark.
- The article is not a complete product comparison.

Keep this concise.

## 3. One case, equivalent inputs

Present the corrected common input table.

| Parameter | TOPS Pro | KolliPack |
|---|---:|---:|
| Carton | 16.2 × 11.4 × 9.1 in | 411 × 289 × 231 mm |
| Carton weight | 5 lb | 2,268 g |
| Pallet | 48 × 40 × 4 in | 1,219 × 1,016 × 101 mm |
| Maximum total height | 53 in | 1,346 mm |
| Overhang | 1 × 1 in | 25 × 25 mm |

State only that KolliPack uses rounded metric equivalents.

Do not discuss source-file correction history.

## 4. Same maximum result

Show and discuss:

```text
50 cartons
10 per layer
5 layers
```

Explain the visible difference:

- TOPS presents the leading result as interlocked.
- KolliPack presents the repeated column layer and indicates when an alternate/interlocked layer is available.

Do not declare one more stable.

## 5. Same best result, different search breadth

This is the main discussion.

Explain:

- TOPS supplied table: 14 candidates.
- KolliPack displayed shortlist: 5 options.
- Both recover the maximum.
- Both recover leading 45-carton alternatives.
- TOPS shows more variants at similar quantities.
- KolliPack presents a smaller interactive shortlist.

Explain the business relevance:

- More variants can help when equipment or handling constraints favor a particular pattern.
- A shorter shortlist can make the first review easier.
- Candidate count is not a quality score.

## 6. Interlock is a decision, not a certificate

Explain in plain language:

- Column and interlocked patterns distribute contacts differently.
- The final choice depends on carton strength, wrapping, handling, equipment, and transport.
- The benchmark compares geometry and options, not physical stability.

Keep this to a short section.

## 7. What the benchmark shows

State clearly:

- KolliPack matched the best quantity in this case.
- TOPS showed broader candidate breadth.
- KolliPack offered interactive views and interlock inspection.
- One case cannot establish full product equivalence.

## 8. Try the exact case

Add a short contextual CTA:

> Open the same pallet benchmark in KolliPack, compare the generated patterns, and switch between the column and interlocked views.

Button:

```text
Open the pallet benchmark in KolliPack
```

Use the exact working populated-case URL from Phase 1.

Open in a new tab through the existing CTA implementation.

## 9. Concise conclusion

End with one balanced takeaway.

Do not repeat every limitation.

---

# Prohibited public sections

Do not create sections titled or focused on:

- Height discrepancies
- PDF inconsistencies
- Backend reproduction details
- Repository status
- Missing presets
- Draft CTA warnings
- Development limitations
- Validation logs
- Source correction history

If a discrepancy exists, Phase 1 should have stopped.

---

# Utilization metrics

TOPS and KolliPack may report different utilization percentages.

Do not present them as directly comparable.

The article may say in one short note:

> The applications report utilization using their own conventions, so this article compares carton quantity, layers, and visible pattern alternatives rather than treating the percentages as equivalent.

Do not write a long denominator analysis.

---

# Public claims policy

## Allowed

- Both tools found 50 cartons in this case.
- Both used 10 cartons per layer and 5 layers.
- TOPS supplied more candidate rows.
- KolliPack displayed a shorter shortlist.
- Both included 45-carton alternatives.
- TOPS presented the leading result as interlocked.
- KolliPack provided column and interlock inspection.
- This is one case.

## Not allowed

- KolliPack is equivalent to TOPS Pro.
- KolliPack is better than TOPS Pro.
- TOPS patterns are unrealistic.
- KolliPack patterns are more stable.
- KolliPack is more accurate.
- KolliPack is cheaper.
- TOPS is outdated.
- This validates the whole engine.
- Candidate count proves quality.
- Matching one result proves parity.

---

# Figures

Use only the supplied screenshots.

Do not take new screenshots.

Follow exactly:

```text
.agents/skills/blog-article/references/kollipack-graphic-style-guide.md
```

Use the same graphical family as the approved Container Selection and Packaging Flow articles:

- Soft light-grey background
- Dark navy headings
- Muted grey subtitles
- Rounded white cards
- Green highlights
- Generous whitespace
- Real KolliPack and TOPS screenshots
- Simple editorial compositions
- No dashboard style
- No invented UI

Create approximately four or five figures.

## Figure 1 — One case, equivalent inputs

Use the corrected TOPS and KolliPack input screenshots.

Message:

```text
One case, equivalent rounded inputs
```

## Figure 2 — Same maximum result

Show:

- TOPS leading pallet render
- KolliPack column render
- KolliPack interlocked render

Prominent callout:

```text
50 cartons
10 per layer
5 layers
```

## Figure 3 — Same best result, different breadth

Show:

- TOPS result table
- KolliPack result table

Callout:

```text
Same maximum
Different candidate breadth
```

## Figure 4 — Leading alternatives

Show selected 45-carton alternatives from both tools.

Do not claim exact pattern equivalence.

## Figure 5 — Interactive inspection

Use only when the supplied screenshots add value.

Show the KolliPack top/front/side or interlock inspection alongside a concise TOPS comparison view.

Do not create a feature catalogue.

---

# Thumbnail

Use the approved KolliPack graphic style.

Use the official logo asset.

Do not generate or redraw the logo.

Suggested thumbnail structure:

```text
ONE PALLET CASE
TWO OPTIMIZERS

50 CARTONS
```

Use:

- One TOPS result
- One KolliPack result
- Neutral comparison framing
- No “winner” language
- No TOPS logo used decoratively
- Soft off-white background
- Dark navy text
- Green emphasis

---

# Fresh-Eyes Business Reader review

After the article and figures are complete, run the Fresh-Eyes review.

## Primary persona

Operations or logistics manager

The reviewer must understand:

- What was compared
- What matched
- What differed
- Why candidate breadth matters
- What still requires engineering validation
- How to open and use the exact case

## Secondary persona

Packaging buyer or engineering manager

The reviewer must confirm:

- The comparison is fair
- The disclaimer is visible
- No superiority claim is unsupported
- No internal development language appears
- The article is understandable without knowing the source files
- The CTA opens the exact case

Apply the corrections.

Do not output only a review report.

---

# SEO

## Primary keyword

```text
TOPS Pro palletization comparison
```

## Supporting phrases

Use naturally:

- Palletization software comparison
- Pallet pattern optimization
- 48 × 40 pallet calculator
- Pallet layout software
- Palletization benchmark
- Free palletization calculator

Do not keyword-stuff.

The article must provide real benchmark value, not exist only to capture a competitor keyword.

---

# Article files and structure

Create:

```text
packagingapp/content/blog/articles/
└── kollipack-vs-tops-pro-palletization-benchmark.md
```

Create:

```text
static/img/blog/kollipack-vs-tops-pro-palletization-benchmark/
├── thumbnail.webp
├── benchmark-inputs.webp
├── maximum-result-comparison.webp
├── results-breadth-comparison.webp
├── leading-alternatives.webp
└── interactive-inspection.webp
```

The last image is optional only when the supplied evidence does not justify it.

Update:

```text
docs/blog/article-registry.md
```

when required by the existing registry workflow.

Use the same front-matter structure as the successful existing demo articles.

Use:

```toml
article_type = "demo_case_study"
status = "draft"
```

Set the CTA to the exact named public case.

---

# Minimal validation

Run only:

## Evidence and case

- Direct backend reproduction
- Targeted named-case route/context test
- Targeted normal-route unaffected check
- Exact CTA URL check

## Article

- Existing article schema validator
- Referenced-image existence
- WebP readability and dimensions
- Registry generation when required
- Exact disclaimer string check
- Exact public tutorial URL check
- `status = "draft"` check
- Prohibited-public-language scan

Do not run:

- Full Django suite
- Full palletization suite
- Playwright
- Browser screenshots
- Visual regression
- Deployment checks
- Full-project link crawling

Perform one focused correction pass.

If a critical gate fails, stop.

---

# Acceptance criteria

The task is complete only when:

- The latest corrected benchmark ZIP was used.
- Every critical source agrees.
- The exact TOPS tutorial is confirmed.
- KolliPack reproduces 50 cartons.
- The exact public palletization case exists.
- The exact CTA opens the populated benchmark.
- The normal palletization tool remains unchanged.
- The article is written from scratch.
- The exact visible title is used.
- The required disclaimer appears verbatim.
- The article is public-facing and contains no development language.
- The article uses the successful demo-article structure.
- The figures match the approved KolliPack graphic style.
- The official logo is used.
- The Fresh-Eyes review is applied.
- The article remains a draft.
- No palletization engine or UI behavior was changed.
- Minimal validation passes.

---

# Final Codex report

Report only:

- Phase 1 pass/fail status
- Evidence files inspected
- Corrected benchmark inputs
- TOPS headline result
- KolliPack reproduced result
- Candidate counts
- Exact public case URL
- Targeted case validation performed
- Article file created
- Final title
- SEO title
- Disclaimer location
- Figures created
- Official logo asset used
- Fresh-Eyes personas used
- Exact files changed
- Minimal validations run
- Remaining warnings

Do not include internal analysis in the public article.
