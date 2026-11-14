# Publish Approved Article/Assets — Preservation Mode (v1)

Use when the owner has already approved the **actual article text and final figure files**, and requests only repository integration, staging or publication.

## Non-negotiable

- **Do not** rewrite, reorganize, shorten or embellish the supplied copy.
- **Do not** regenerate, redraw, recompose, crop, recolor or replace the approved figures.
- **Do not** change the approved title, number claims, captions or figure order to fit a generic article template.
- **Do not** turn the supplied image into an image-generation prompt. The supplied *file* is the deliverable.
- **Do not** add extra figure types/stages beyond the exact approved body.

## Allowed integration changes

1. Map approved copy to existing blog Markdown / TOML front matter, preserving paragraph content and order.
2. Change asset references to valid `static://...` paths, using byte-identical approved image copies or explicit owner-approved compression.
3. Populate required metadata using verified facts; preserve original slug if updating an existing article.
4. Verify the prepopulated case using existing routes and mechanisms. Register a missing case only with explicit authorization for that functional change. A missing or incorrect case blocks publication.
5. Connect existing CTA/footer to the verified case URL, without changing unrelated website behavior.
6. Run repository validators and a narrow rendered-page visual inspection.

## Preservation evidence

- Record each supplied image SHA-256 and the final installed asset SHA-256. Differences require explicit approval.
- Compare supplied approved copy with rendered source body. Describe any *required technical* changes; otherwise zero narrative edits.
- Confirm full render boundaries of figures; CSS that inadvertently cuts figures is a bug to fix, not permission to crop source assets.
- Keep working existing article routes/links and assets untouched unless explicitly in scope.

## Publishing semantics

`publish_approved` means approval of the **content and figures**, not implicit authorization for deployment to production. If the owner explicitly asks to publish, perform only authorized publishing steps; otherwise leave `status = "draft"`. Never state that publication occurred until the repository/app confirms it.

For uncertain rights, competitor source usage, or contradictory engineering settings, do not rewrite the article to hide the issue; flag the blocker for owner review. Follow `comparative-benchmarking.md`.
