# Blog Quality Checklist

## Task setup

- [ ] Mode is identified.
- [ ] Article profile is identified.
- [ ] Relevant skill references were read.
- [ ] Existing article library was checked for overlap.
- [ ] Prepopulated case URL is known for a demo article.

## Evidence

- [ ] For an applicable calculation, exact case inputs were extracted.
- [ ] The current KolliPack backend reproduced the demo or reconstructable comparator case.
- [ ] Shared engine logic was called rather than duplicated.
- [ ] Backend values were compared with screenshots and author notes.
- [ ] Relevant alternatives were recorded.
- [ ] Discrepancies were reported rather than hidden.
- [ ] No engine or application logic was changed.

## Business context

- [ ] The product category is understandable.
- [ ] The company need is clear.
- [ ] The customer or distribution setting is plausible.
- [ ] No company, contract, cost, volume, or saving was fabricated.
- [ ] Illustrative assumptions are labeled.
- [ ] A real comparable product, when used, is clearly identified as a comparison.

## Title and story

- [ ] At least six title candidates were considered.
- [ ] Visible title, SEO title, and thumbnail headline serve different purposes.
- [ ] Demo and business articles present the main result within the first 100 words. Other profiles orient readers to the engineering decision early.
- [ ] The article has one continuous decision thread.
- [ ] Every section advances the problem, result, consequence, decision, or CTA.
- [ ] Technical implementation detail was removed from business articles.
- [ ] Important numbers are not repeated unnecessarily.
- [ ] Limitations are clear but not repeated after every result.

## Fresh-Eyes review

- [ ] A relevant non-expert persona was selected.
- [ ] The reviewer used only the article, figures, captions, and CTA.
- [ ] The reader can state the problem in one sentence.
- [ ] The reader understands the result and commercial meaning.
- [ ] Jargon was explained or removed.
- [ ] Documentation-like passages were revised.
- [ ] The reader knows what KolliPack contributes.
- [ ] The reader knows what to do next.

## Metadata and SEO

- [ ] Required front matter is complete.
- [ ] Slug matches filename and remains stable.
- [ ] Primary keyword does not materially cannibalize the tool landing page.
- [ ] SEO title and meta description are useful.
- [ ] Canonical path is correct.
- [ ] Dates are valid.
- [ ] Open Graph image exists.
- [ ] Internal links are descriptive and relevant.
- [ ] Demo article supports the related tool page.

## Prepopulated case

- [ ] Exact case URL is preserved.
- [ ] Front-matter CTA uses the case URL.
- [ ] Article body includes a contextual case link or button.
- [ ] Footer CTA is article-specific.
- [ ] New-tab behavior is preserved through the current implementation.
- [ ] The article explains what readers can change.
- [ ] A missing or uncertain preset blocks publication when the article requires a runnable case.

## Images

- [ ] Real KolliPack evidence is used where required.
- [ ] No fake UI screenshot was created.
- [ ] Numbers visible in screenshots were not changed.
- [ ] Official logo was reused, not regenerated.
- [ ] Thumbnail was composed deterministically.
- [ ] Every relevant approved image was retained or intentionally combined.
- [ ] Each figure communicates one main idea.
- [ ] Labels are readable on mobile.
- [ ] Filenames are semantic.
- [ ] Alt text and captions are meaningful.
- [ ] Production files are optimized.
- [ ] All referenced paths resolve.


<!-- BEGIN KOLLILABS_BLOG_SKILL_UPDATE_V1:quality-gate -->
## Packaging Scenario Setup & visual editorial quality — publication gate

- [ ] Physical packaging stages follow the real article scope; absent or mixed stages are handled correctly.
- [ ] Where beneficial, the illustrated scenario figure follows `packaging-scenario-setup.md` and its approved *style* reference (not copied facts).
- [ ] Conceptual graphics are distinguished from source-verified calculations and real result renders.
- [ ] Every final figure was opened and inspected at native size and realistic article/mobile display widths.
- [ ] Important case, carton, bag, pallet and transport geometry is complete and uncropped.
- [ ] All critical labels, counts and rendered evidence are readable at display size.
- [ ] Software comparisons use real screenshots, faithful values and like-for-like framing.
- [ ] The visuals explain the result promptly; there are no giant empty screenshot cards, decorative cube-only explanations, or needless repeated figures.
- [ ] In-article images match the approved light KolliPack visual language; thumbnails follow their separate canonical workflow.
- [ ] `visual-editorial-critic.md` was applied, with a recorded decision for each figure and the complete page.
- [ ] Overall Visual QA is PASS; FAIL, REVISE or NOT REVIEWED blocks publication.
- [ ] If `publish_approved`, the text and supplied figures were preserved and byte-level differences were reported/approved.
<!-- END KOLLILABS_BLOG_SKILL_UPDATE_V1:quality-gate -->

## Minimal validation

- [ ] Run and consume the Iteration 2 JSON report using the [audit procedure](production-workflow-v2.md#run-the-editorial-audit).
  Review all applicable [regression IDs](../../../../docs/blog/editorial-regressions.md), including findings that need manual checks.
- [ ] Resolve automated failures and review warnings. The audit exits nonzero for automated failures
  or unavailable production rendering. Its exit code does not determine publication readiness.
- [ ] Record Fresh-Eyes decisions for EDR-01–03. Use Packaging Scenario Setup, Comparative Figure
  Workflow and the Visual Editorial Critic for EDR-04–08. Record what was actually inspected,
  including the rendered article, artwork labels, geometry and legibility at relevant display widths.
- [ ] Use Thumbnail Workflow for EDR-09. Pass the workflow's validation JSON with
  `--thumbnail-report` for new candidates. Record the visual result and applicable
  [thumbnail release authorization](thumbnail-workflow.md#first-release-of-a-new-article) separately.
- [ ] Review provenance and numerical accuracy for EDR-10 and confirm the live case inputs for EDR-11
  under the applicable case policy. For EDR-12, use the tracked production thumbnail baseline or supply
  a trusted JSON file with `--approval-record`. Its fields are `article_slug` and an `assets` mapping from
  static-relative paths to approved SHA-256 values. Record preservation review for anything it does not cover.
- [ ] Record automated validation, editorial and visual decisions, publication readiness and
  authorization separately. Apply the [release decision and final verification](production-workflow-v2.md#publication-intent-and-decision).
- [ ] Article schema validator passes.
- [ ] Referenced images exist.
- [ ] CTA URL strings match approved routes.
- [ ] Registry was regenerated when required.
- [ ] WebP files open and dimensions were checked.
- [ ] No broad Django, browser, screenshot, or engine tests were run unless requested.

## Final report

- [ ] Final titles are reported.
- [ ] Backend entry points and headline outputs are reported.
- [ ] Business context and Fresh-Eyes persona are reported.
- [ ] Exact files changed are listed.
- [ ] Validation is listed.
- [ ] Remaining warnings are explicit.
- [ ] Report the actual repository status and, only if verified, the live-site status.
