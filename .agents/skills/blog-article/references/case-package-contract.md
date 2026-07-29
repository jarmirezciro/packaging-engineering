# Case Package Contract

Use this contract when the author supplies a ZIP or folder for a demo or case-study article.

## Preferred structure

```text
article_case/
├── discussion.txt
├── brief.yaml
├── screenshots/
│   ├── inputs.png
│   ├── result-01.png
│   ├── result-02.png
│   └── detailed-result.png
├── backend-results.csv
├── backend-results.json
└── notes/
    └── optional-notes.md
```

The structure may differ. Inspect the actual package rather than rejecting it because filenames do not match the preference.

## Minimum usable package

A demo article normally needs:

- Author observations in `discussion.txt`, a brief, or equivalent notes.
- Exact calculation inputs.
- Real screenshots or existing article figures.
- Identification of the relevant KolliPack tool.
- A working prepopulated case URL, or a clear warning that the article is not publishable as a demo yet.
- Access to the latest project when backend reproduction is required.

## `discussion.txt`

Treat `discussion.txt` as the author's editorial intent.

Extract:

- What the author expected.
- What looked attractive.
- What was surprising.
- Which alternatives seem realistic or unrealistic.
- Which business lesson matters.
- Which claims should be investigated.
- Any preferred audience, tone, or context.

Develop the thoughts. Do not merely correct grammar.

## `brief.yaml`

When present, it may define:

```yaml
article:
  type: demo_case_study
  audience:
    - packaging buyers
    - operations managers

case:
  tool: container_selection
  prepopulated_url: /tools/box-size-calculator/?case=example

author_goal:
  main_message: Product orientation changes real capacity.
  observations:
    - The upright result looked reasonable.
    - Mixed orientations increased capacity.

seo:
  primary_topic: box packing calculator
```

The brief controls intent. Current backend evidence controls numerical claims.

## Screenshot handling

- Use real KolliPack screenshots as evidence and visual material.
- Do not assume folder names are numerically authoritative.
- Compare screenshot values with the reproduced backend result.
- Do not alter numbers shown in screenshots.
- Exclude inconsistent screenshots or label the discrepancy.
- Keep raw evidence separate from composed figures.

## Missing information

When an input or result is unclear:

1. Check `discussion.txt`.
2. Check input screenshots.
3. Check the existing article.
4. Check the current case preset.
5. Reproduce the case through the backend.
6. Report unresolved ambiguity.

Do not invent missing values.
