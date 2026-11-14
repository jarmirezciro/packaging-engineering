# KolliLabs blog production workflow

Codex coordinates the existing blog tools. Use one production sequence with the relevant steps for the request. The [article architecture](blog-architecture.md) and [schema](article-schema.md) govern integration. The [editorial examples](../../../../docs/blog/editorial-examples.md) and [regression register](../../../../docs/blog/editorial-regressions.md) guide review and preservation.

## Choose the mode and profile

The mode describes the work. The editorial profile describes what the reader should get. Set `article_type` independently using the existing schema.

| Mode | Start with | Mode-specific handoff |
| --- | --- | --- |
| `benchmark_from_evidence` | Comparator material, a technical question and any supplied settings or observations | **Comparative Benchmark.** Identify the source and its visible fixture, version, settings, outcome and rights. Separate observed results from independently reproduced KolliPack results, including unmatched constraints and alternatives. Reproduce through the existing backend when the evidence supports it. If equivalence cannot be established, use only supportable, explicitly scoped comparisons. Route factual visuals through [Comparative Figure Workflow](comparative-figure-workflow.md). Use a named preset if the article is a runnable benchmark or uses `demo_case_study` metadata. |
| `research_deep_dive` | A packaging engineering subject or question | **Engineering Deep Dive.** Establish the engineering decision, consult authoritative sources and verify formulas, their assumptions, and examples. Use the concept-figure skill where it clarifies a mechanism. A named case applies only if the article includes a reproducible KolliPack demonstration. |
| `demo_from_case` | Tool, case inputs, screenshots or results, and owner observations | **Practical Demo.** Use the [demo profile](demo-case-study-profile.md) with `demo_case_study` metadata. Verify the actual scope, conditions, and result. Compare with supplied captures and identify the reader decision, practical consequence and exact working case. Use genuine result visuals. Add a physical setup figure when it aids comprehension. |
| `refine_article` | Stable slug or draft, a defect and the requested correction | Keep the current profile. Locate the affected EDR rules and record the approved text, figures, thumbnail and URLs. Make the smallest authorized change and compare the resulting diff and affected render with the original. Regenerate only an affected asset when necessary and authorized. Identify pre-existing findings outside the requested correction and surface any that block release. |
| `calibrate_from_feedback` | Owner criticism or approval tied to a specific artifact | Follow [calibration from feedback](#calibration-from-feedback). If the owner also requests an article correction, use `refine_article` for that part. Calibration alone leaves article and asset files unchanged. |

Keep `polish`, `research`, `refresh` and `rewrite` as explicit requests for the corresponding editorial operation. Select the relevant profile and reuse the applicable stages below. Use `publish_approved` for integration of supplied final material under the [preservation contract](publish-approved-artifact.md). Apply QA to the integration and return any proposed changes to approved material to the owner.

## Shared production sequence

| Stage | Existing capability | Handoff |
| --- | --- | --- |
| 1. Scope and inspect | [Case package](case-package-contract.md), current article and assets, task brief | Record mode, profile, intended reader, scope, publication intent, available evidence and approved elements. Protect stable slugs and preserve approved versions. |
| 2. Research and verify | [Research notes template](../../../../docs/blog/research-notes-template.md), [comparative benchmarking](comparative-benchmarking.md), [evidence archive contract](../../../../docs/blog/evidence-archive-contract.md) | Record the sources actually consulted and what they establish. Capture source dates, version, locators such as video timestamps, visible settings, outcomes, uncertainties and applicable rights. Distinguish observations, reported claims, verified principles and interpretation. Retain originals in permitted storage or record the reference and storage limitation. |
| 3. Reproduce and verify the case, when applicable | [Backend evidence policy](backend-evidence-policy.md), existing case presets and views | Record exact inputs, units, restrictions, tooling and backend revision, results, alternatives and discrepancies. Compare like-for-like metrics and document unmatched constraints. Verify the named case's URL and that the actual tool loads the expected inputs. If a required preset is absent, write the exact case specification for separately authorized registration and block publication. General authority to publish an article does not authorize preset changes, including under `publish_approved`. |
| 4. Establish the story and write | Existing title and story, business context, [editorial style](editorial-style.md), [SEO](seo-rules.md) and schema references | Draft from verified claims and identify their evidence. Keep comparisons bounded and practical demos focused. Ground illustrative packaging context in the case and keep invented customer data out. |
| 5. Prepare visuals | [Scenario setup](packaging-scenario-setup.md), [editorial figure skill](../../kollilabs-editorial-figures/SKILL.md), comparative figure workflow, [thumbnail workflow](thumbnail-workflow.md) | Choose distinct roles for concepts and engineering evidence. Use authentic captures or verified backend geometry and retain the source links for each composed figure. Prepare the versioned thumbnail, validation report and provenance. |
| 6. Review the finished draft | [Fresh-Eyes Business Reader](fresh-eyes-business-reader.md), [Visual Editorial Critic](visual-editorial-critic.md), [quality checklist](quality-checklist.md) | Review the actual article and finished figures at relevant display sizes. Record the decision, reviewer, asset or article version and remaining defects. Identify self-review when used. The visual critic applies to both publication intents. Thumbnail release authorization follows the thumbnail workflow. |
| 7. Run the audit and decide | [Iteration 2 auditor](../scripts/audit_editorial.py), checklist and regression register | Consume the JSON findings as described below. Complete the applicable gates and record the decision before publication. |
| 8. Integrate and verify | Article architecture, existing static asset conventions and [registry generator](../scripts/generate_registry.py) | Integrate only the authorized edition. Regenerate the registry when metadata changes. Verify the actual article, URLs, asset references, hashes and state. Report what was integrated and what remains pending. |

Use existing research notes or the case package for handoffs. Carry the evidence references, decisions and artifact versions forward there. A temporary attachment or source URL does not establish that bytes are archived. Keep restricted third-party material out of public repository paths unless authorized.

Use the normal article and static paths for an authorized draft integration. Keep unapproved thumbnail candidates and proposed revisions to published articles in an isolated preview. The auditor resolves static references within its own checkout, so run it there with the candidate bytes at their intended static-relative paths and the article filename matching its slug. For a release, verify the proposed published metadata in the isolated version and rerun the same checks after final integration.

## Drafting with incomplete evidence

1. Investigate the gap or conflict using the available source material and a focused run of the existing backend when the known inputs support it. Check whether the results use the same inputs, units, restrictions, mode and metric. Keep source observations and reproduced results distinct.
2. If the issue remains unresolved, omit the affected claim or narrow it to what the evidence establishes. If the central comparison falls away, choose the closest supported editorial angle, such as the engineering trade-off shown by a verified subset or a self-contained KolliPack result. Align the title, figures, captions, thumbnail and CTA with the revised scope. Keep unsupported numbers, inferred settings and unverified parity claims out of the draft.
3. For `draft_only`, continue through writing, usable visuals and applicable QA whenever a complete, useful and factually defensible article is possible. In the backend and comparative references, a stop on conflicting evidence applies to the affected claim, comparison or figure and to release while a required gate remains open. If no factual article can be written, report the specific missing evidence and what it would establish.
4. Record missing evidence, contradictions, excluded claims, QA failures, missing presets and publication blockers in research notes or the final report. Keep internal QA commentary, TODOs, evidence-processing explanations, unresolved-source lists and developer-facing caveats out of reader-facing copy. Keep any qualification a reader needs to interpret a material claim accurately.

A required preset that is absent, broken or unverified blocks publication. Continue the draft without a named-case CTA until the destination is verified. Keep any alternative tool link clearly labeled as a general tool link.

## Run the editorial audit

From the repository root, in the project Python environment:

```bash
python .agents/skills/blog-article/scripts/audit_editorial.py <article-file> --json
```

Use `--comparative` for external comparisons, `--require-case` for a runnable benchmark outside the demo metadata type, `--thumbnail-report <validation.json>` for the validation from the thumbnail workflow, and `--approval-record <approval.json>` only for a trusted byte baseline. See the checklist for the approval record format. A report from the renderer or a hash of today's candidate is not an approval record.

Read `automated_validation`, `editorial_and_visual_review`, `publication_readiness` and the `findings` list. Each finding has `rule`, `kind`, `status` and `message`. A rule can have several findings, such as a source check that passes and an artwork check that still needs review. Keep the raw report and record dispositions with the relevant evidence or artifact version. Consult all applicable register IDs, including any later approved rules that have no automated finding yet.

| Status | How to use it |
| --- | --- |
| `PASS` | The stated check passed on the identified artifact. For an automated finding, keep separate review requirements open. |
| `FAIL` | Correct the defect or block release. |
| `WARNING` | Resolve the issue or document why it does not block the intended claim or release. A reference-only source can be sufficient if it is verified and usable under the applicable evidence and rights policy. |
| `REVIEW_REQUIRED` | Complete the stated review or report a blocker. If the auditor or renderer cannot run, the automated gate remains incomplete. |
| `NOT_APPLICABLE` | Confirm the check is outside the article's scope, especially when the auditor inferred applicability from metadata or source text. |

The auditor returns `BLOCKED` or `REVIEW_REQUIRED` in `publication_readiness`. Its `editorial_and_visual_review` remains `REVIEW_REQUIRED` even when automated validation passes. Keep that raw result. Record completed reviews and the release decision separately using the quality checklist. A zero exit code can accompany warnings and outstanding reviews.

## Publication intent and decision

- **`draft_only`** is the default for creation or preparation. Deliver a complete unpublished candidate whenever the evidence supports one, with the evidence record and QA findings separately. `BLOCKED` and `REVIEW_REQUIRED` describe release readiness. Continue the draft under the evidence procedure above. An existing published edition remains available while its proposed changes are reviewed.
- **`direct_publish`** requires an explicit owner request to publish. Proceed with ordinary in-scope writing and revisions without a mandatory intermediate draft approval. For a new article, that request covers first release of newly generated figures after visual and evidence review and of the thumbnail under the [first-release thumbnail policy](thumbnail-workflow.md#first-release-of-a-new-article). This first-release policy governs the general approval language in the demo, figure and visual review references when they are used together. Requests for owner review, replacement of an approved thumbnail, changes to previously approved deliverables and required human/legal review retain their existing approval requirements.
- **`publish_approved`** integrates the exact owner-approved copy and assets using the preservation contract. Publication still requires explicit authorization. Changes beyond technical integration require owner review.

Record automated validation, editorial/visual review and publication readiness separately. Mark **ready** only when applicable automated checks pass or warnings have documented dispositions, all material claims and calculations are verified, tables and figures have passed actual review, the required case opens with the correct inputs, the thumbnail gate is satisfied, rights and required human/legal review are cleared, and approved content is preserved. An incomplete visual inspection, unresolved factual discrepancy, unavailable audit, missing functional case or required approval blocks release. Readiness and authorization are both required.

Once ready and authorized, integrate the exact reviewed copy and versioned assets through the existing paths. Use `status = "published"` only for the authorized version. Run final verification on the integrated files and confirm the preview matches the reviewed edition. If verification fails, keep a new article unpublished or preserve the prior published version. Report the failure and the corrective action. A local `published` status is a repository state. Commit, push, merge, deployment and live-site verification each have their own authorization and evidence.

## Recover from a failed stage

Preserve valid evidence, draft sections and approved assets. Record the failed gate and its exact cause. Make one focused correction pass, respecting the thumbnail workflow's cumulative attempt budget, and rerun the affected and dependent checks. If the source frame, engineering input, image inspection or case verification remains unavailable, report exactly what is needed and leave the release blocked. Use supplied genuine captures or existing verified outputs. This workflow does not automate screenshot capture.

## Calibration from feedback

1. Inspect the actual artifact and owner feedback. Identify the article, component and evidence or version. Record the failure or approved behavior and preserve the original reference.
2. Match the finding to the [register](../../../../docs/blog/editorial-regressions.md). Add the example to the [library](../../../../docs/blog/editorial-examples.md) under the relevant rule. Update that rule only when the expected behavior or verification needs clarification. Propose a new stable EDR ID for a genuinely new failure category and keep IDs unique.
3. Extend the existing auditor and focused tests when the authorized change can be verified deterministically. For visual or reader-centered defects, update the relevant existing review guidance. Treat owner approval as authoritative for the specified artifact or standard.
4. Verify the affected case and the preservation of previous approvals. Report the example, rule and how it will be checked. If a finding concerns an engine, document it for a separate engineering task.
