# KolliLabs evidence archive contract

An evidence package lets a future reviewer trace a published claim back to the source, the KolliPack run, and the exact public version. It accompanies the existing [case package](../../.agents/skills/blog-article/references/case-package-contract.md). Accept the existing formats, including supplied ZIPs, folders, screenshots, structured results and author notes.

## What a package preserves

Assign a stable evidence package ID to the investigation, a case ID to each distinct fixture, and a run ID to each calculation. Keep a manifest and use the IDs wherever a claim, figure, extract or result points to another record. The following names describe logical groups. They can map to a directory in private storage or to durable references within the same package.

| Group | Record |
| --- | --- |
| Original evidence | Immutable files as supplied or retrieved when retention is permitted. Include uploaded captures, source documents, datasets and original author notes. A reference-only source can have a manifest entry with no local bytes. |
| Source extracts | Transcribed settings, quantities, constraints and measured or reported values. Each extract points to the original source ID and locator. Label reported data, inferred data and unknowns. Record conversions, rounding and any uncertainty. |
| KolliPack reproductions | Exact inputs, settings, structured outputs and genuine tool captures tied to the case and run IDs. Preserve original captures separately from figure crops. |
| Engineering and editorial interpretation | Author observations, comparison boundaries, reasoning, evidence discrepancies, draft figures and review decisions. Link each factual claim to sources, extracts or runs. Use a stable claim ID and the article section, table row or caption. |
| Published versions | Approved article, tables, thumbnails and composed figures, identified by repository revision and path. For composed figures, list parent source and run IDs, crops, labels and overlays, final hash, and the applicable approval. Public copies use the current blog article and static paths. |

An approved visual style reference can guide composition. Technical claims require the corresponding source data, observed geometry or verified calculation. Use the [comparative benchmarking policy](../../.agents/skills/blog-article/references/comparative-benchmarking.md) for claims, comparator attribution and external publication review.

## Minimum manifest

Use one entry per independently retrievable item or identifiable artifact. Record unavailable values as unknown with a short reason where the absence affects use or verification. Store captured and publication dates separately with the precision available.

| Field | Meaning |
| --- | --- |
| `package_id`, `case_ids`, `source_id`, `type` | Investigation and applicable fixtures, a unique item ID within the package, and the kind of evidence listed below. |
| `original_filename`, `url`, `title` | Original supplied filename or precise source locator. Keep both filename and URL when known. Include the source title when it helps identify the material. |
| `publisher_or_author`, `source_version`, `published_at` | Publisher, creator or supplier and the available edition, product version, dataset release or publication date. Use an explicit unknown for an unavailable version. |
| `captured_or_retrieved_at`, `locator` | When the item was obtained or observed, and the relevant timestamp/range, page, figure, table row, dataset instance or screenshot area. |
| `sha256`, `storage_ref`, `preservation_state` | Hash of the item's preserved bytes, an authorized durable reference when available, and whether the material is archived, pending archival, reference only, or unavailable. Derivatives have their own hashes and parent IDs. |
| `verification` | What was verified, against which source or run, by whom and on what date. Record partial or disputed checks and their outstanding questions. Receipt of evidence and verification of its values are distinct states. |
| `observations`, `supports` | Specific engineering observations and the claim IDs they support, with conditions or unresolved differences. Record references to parent items or run IDs. |
| `usage_and_review` | Whether retention and publication are permitted, the basis, what versions or excerpts the decision covers, and who recorded it and when. Preserve pending or restricted decisions explicitly. |

| Evidence type | Useful locator or qualification |
| --- | --- |
| Competitor screenshot or excerpt | Supplied filename, original context, visible edition or run settings, and the panel used. Keep the unchanged capture independently of any crop. |
| YouTube video | Exact watch URL, title, publisher/channel, relevant timestamps or ranges and the observation supported by each. A full video download is optional and depends on availability and permission. |
| Website or demonstration | Exact page, heading or demo state, retrieval date, and observed settings or publicly stated version. |
| Academic paper or technical PDF | DOI or stable source URL, edition, page, figure, table or equation. Preserve the data used and its attribution. |
| Benchmark dataset | Repository or publisher, release or snapshot, file and class/instance IDs, filters and aggregation rules. |
| User observation or editorial review | Author, context and date as known. For embedded review visuals, identify the original document and part. Mark whether the observation describes a finding, approval, preference or proposed artwork. |
| KolliPack calculation | Fixture and run IDs, exact inputs, selected mode, verified output and repository or engine revision. |
| Genuine KolliPack screenshot | Tool view and run ID, capture date and relevant visible setup fields, figures or metrics. |
| Published comparison figure | Approved version, parent source/run IDs, crop and composition notes, Git revision, public path and file hash. |

## Where evidence may be stored

- Use the existing repository for cleared public article material. Keep raw third-party images, source documents, private author notes, sensitive settings and manifests containing private locators in approved, access-controlled storage when authorized. Publication clearance of a figure does not determine where its raw inputs can be kept.
- Record `archived` after authorized reviewers can reopen the durable copy and the recorded hash verifies its bytes. A URL is `reference only` when that is all the package retains. Temporary review copies or session uploads with preserved bytes awaiting a durable location are `pending archival`. Record why a source or its bytes are unavailable or restricted.
- Preserve originals and prior approved versions. Record corrections as new versions with provenance to the earlier record. Keep crops, OCR, notes and editorial composites identifiable as derivatives.
- Private storage needs a named owner, controlled access, stable references, recoverable versions and a retention decision. No approved private archive was verified for this calibration. Preserve the owner review locators in the [examples library](editorial-examples.md#original-review-locators) until an authorized durable destination is assigned.
- The CapePack article identifies a supplied demo frame and records pending source identification and reuse review. The precise source video, timestamp and decision still need evidence. The TOPS [comparator record](research-notes-tops-maxload-kollipack-container-loading-benchmark.md#comparator-record) provides a source URL and author review. Track those decisions per source and keep the published composites distinct from originals.

## Reproducing a dated result

For each result used materially in an article, preserve the run record with:

- Tool and calculation entry point, selected algorithm or loading mode and options, original run or capture date, repository commit or engine version, and any relevant configuration or catalogue snapshot.
- Exact inputs as supplied and used. Include units, conversions, product dimensions and quantities, permitted orientations, packaging or transport dimensions, weights, support or stacking restrictions, overhang and other applicable constraints.
- Verified outputs with units and metric definitions. Retain the selected result, alternatives relevant to the claim, and any output geometry or screenshots used in the article.
- The case ID and exact prepopulated URL, when available, plus an independent input snapshot. Capture any difference between the live preset and the historical run.
- If a later run differs, keep it as a separate run with its own inputs, settings, revision and date. Record verified differences, known causes or open questions, and affected claims alongside the original.

Follow the [backend evidence policy](../../.agents/skills/blog-article/references/backend-evidence-policy.md) for current demo verification. A reproduction using today's engine can validate current behavior and expose changes. A historical claim remains tied to its dated run. Preserve the original populations, support assumptions and metric definitions when comparing measured KolliPack results with academic references or vendor-reported outcomes.

This contract defines requirements for a future archive and leaves the current case-package and publishing workflow in place.
