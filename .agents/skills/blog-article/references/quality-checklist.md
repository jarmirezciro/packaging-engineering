# Blog Quality Checklist

## Task setup

- [ ] Mode is identified.
- [ ] Article profile is identified.
- [ ] Relevant skill references were read.
- [ ] Existing article library was checked for overlap.
- [ ] Prepopulated case URL is known for a demo article.

## Evidence

- [ ] Exact case inputs were extracted.
- [ ] Current KolliPack backend reproduced the demo case once.
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
- [ ] The main result appears within the first 100 words.
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
- [ ] A missing or uncertain preset blocks publication.

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

## Minimal validation

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
- [ ] Article remains a draft unless publication was requested.
