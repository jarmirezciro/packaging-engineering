# KolliPack repository instructions

## Identity and source of truth

- **KolliLabs** is the company.
- **KolliPack** is the packaging engineering application.
- This is an independent commercial product. Do not assume it belongs to Volvo or any previous employer.
- The checked-out repository and current branch are the source of truth for code, paths, models, migrations, and commands.
- Historical documentation explains intent and known decisions. When documentation and current code disagree, stop, identify the discrepancy, and report it before changing domain behaviour.

## Required reading and context budget

Use `docs/README.md` as a routing index, then read **only** the documents relevant to the current task. Do not load the whole `docs/` tree into context by default.

- Product/company work: `docs/product/`
- Architecture or workflow work: `docs/architecture/`
- UI/CSS/JavaScript work: `docs/frontend/`
- Calculation-engine work: `docs/domain/`
- Reports, blog, catalogue, analytics, or 3D rendering: `docs/features/`
- Coding process, tests, Git, deployment, and known regressions: `docs/engineering/`
- Competitor or benchmark claims: `docs/research/benchmarks.md`

For a small localized task, read this file, inspect the relevant code, and open only the directly related documentation. For a cross-cutting refactor, read the shared-tool contract, the affected domain document, and the relevant frontend/report/testing documents. See `docs/maintenance/context-and-token-policy.md`.

## Non-negotiable architecture rules

1. **One engine, multiple surfaces.** Standalone tools, Packaging Flow, multi-product tools, and public SEO calculators must use shared domain logic and shared presentation contracts where applicable.
2. **Packaging Flow and multi-product tools are consumers/orchestrators, not second implementations.** They may adapt prefixes, group multiple rows/products, inherit upstream outputs, aggregate results, and maintain JSON-safe state, but they must not silently copy or fork the authoritative calculation, presenter, renderer, or shared UI contract.
3. **A shared-tool change is incomplete until every consumer is checked.** At minimum assess standalone, Packaging Flow, relevant multi-product tools, public SEO/demo page, PDF/report export, catalogue selection, JavaScript hydration, graphics/rendering, and session serialization.
4. **Tool-specific mandatory propagation:**
   - Bag engine, presenter, UI, labels, graphics, and report changes must assess **Multi-product Bag Selection**.
   - Container/Box engine, presenter, UI, labels, graphics, and report changes must assess **Multi-product Container Selection**.
5. Business logic belongs in engines/services. Templates render data; JavaScript coordinates interaction. Do not recalculate packaging results in templates or duplicate Python rules in JavaScript.
6. Preserve JSON-safe workflow and multi-product state. Do not put QuerySets, model instances, `Decimal`, dataclasses, placement objects, matplotlib objects, engine objects, or other non-serializable values in session data.
7. Preserve working behaviour. Use the smallest coherent change. Do not redesign the stable Packaging Flow shell or unrelated tools unless the task explicitly requires it.

## Frontend rules

- `base.html`, Bootstrap, and `static/css/app_theme.css` are the visual foundation.
- Existing approved `app-*`, `tool-*`, `app-card`, `app-table`, wrapper, and shared-partial patterns are preferred over new isolated visual systems.
- Do not replace the global theme file to fix one tool.
- Container Selection and the polished Bag/Palletization/Transport surfaces are reference standards for new tool pages.
- Keep forms compact, aligned, responsive, and customer-facing; show units next to values; remove redundant Select buttons where row selection already exists.
- Tool interactions must not unexpectedly scroll the page to the top. Preserve focus and accessibility while keeping the working position stable.
- User-facing 3D results should be clean: no debug axes/mesh unless explicitly requested. Development overlays must remain a separate debug mode.

## Work method that prevents coding loops

1. Inspect the current repository, current Git status, relevant files, shared consumers, and tests before editing.
2. State the root cause or architecture finding and a short implementation plan.
3. Define acceptance criteria before changing code.
4. Implement a complete vertical slice. Do not report success after only changing the backend when the template, JavaScript, workflow adapter, or export is still pending.
5. Run focused tests and practical checks. Inspect the final diff for unrelated changes.
6. Make at most one deliberate correction pass after verification. If still blocked, report the exact blocker and evidence instead of repeatedly rewriting the same area.
7. Do not use phrases such as “guaranteed” without verification.

## Safety and Git

- Default development branch is historically `pre-production`; verify the actual branch before work.
- Do not commit, push, merge, deploy, alter Railway, run production migrations, or modify production data unless explicitly requested.
- Do not delete or rewrite migrations casually.
- Do not run destructive commands or broad formatting over unrelated files.
- Before finishing, report changed files, commands/tests run, results, remaining risks, and confirmation that no deployment action was taken.

## Definition of done

A task is complete only when:

- The requested behaviour works in its stated surface.
- Shared consumers have been assessed and updated where required.
- Existing calculation behaviour is preserved unless a logic change was explicitly requested.
- Session data remains JSON-safe.
- Relevant tests/checks pass.
- The final diff contains no unexplained unrelated changes.
- Documentation is updated when architecture, domain rules, assumptions, or public behaviour changed.

## Blog architecture

- Blog articles are file-based content under `packagingapp/content/blog/articles/`.
- Never hardcode article bodies or metadata in `packagingapp/views/marketing.py`.
- Production article assets belong under `static/img/blog/<slug>/`.
- Existing published slugs are stable and require redirects if changed.
- Use the repository `$blog-article` skill for article creation, polishing, research, refresh, images, thumbnails, and validation.
- Reuse the canonical official KolliLabs/KolliPack logo; do not regenerate it.