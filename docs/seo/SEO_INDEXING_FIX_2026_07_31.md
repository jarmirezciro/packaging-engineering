# SEO indexing fix — 2026-07-31

This patch keeps one canonical SEO URL per public calculator and uses permanent redirects for legacy or phrase-based aliases.

## Canonical public tool URLs

- `/free-palletization-calculator/`
- `/free-bag-size-calculator/`
- `/free-box-size-calculator/`
- `/free-container-loading-calculator/`

## Palletization aliases redirected to the canonical page

These URLs return permanent redirects to `/free-palletization-calculator/`:

- `/tools/palletization-calculator/`
- `/palletization-calculator/`
- `/pallet-calculator/`
- `/pallet-tool/`
- `/palletization-calculation/`
- `/pallet-pattern-calculator/`
- `/boxes-per-pallet-calculator/`
- `/cartons-per-pallet-calculator/`
- `/ti-hi-calculator/`

## Indexing checks after deployment

Open these URLs in production:

- `https://kollilabs.com/free-palletization-calculator/`
- `https://kollilabs.com/sitemap.xml`
- `https://kollilabs.com/robots.txt`

Then use Google Search Console URL Inspection for:

- `https://kollilabs.com/free-palletization-calculator/`

Check that Google reports:

- URL can be indexed
- Page fetch successful
- Canonical URL is the same page
- No `noindex` detected
- Not blocked by `robots.txt`

Submit or resubmit:

- `https://kollilabs.com/sitemap.xml`
