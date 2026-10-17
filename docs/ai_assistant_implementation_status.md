# KolliPack AI assistant implementation status

Last updated: 2026-10-09

## Phase

Anonymous Public Expert implemented and deterministically validated locally; Session 10.5 authenticated Assistant baseline preserved

## Local provider validation

- Verified on 2026-10-04 with Windows 11, Python 3.11.13, local Redis
  8.10.1, `openai==3.24.0`, and `gpt-5.6-sol` using `xhigh` reasoning.
- Readiness reached `ready` only after the real shared-cache probe, explicit
  local privacy acknowledgements, server-owned provider configuration, and
  credential-presence check all passed.
- The first real Responses API request traversed the normal policy gate,
  Redis throttle, OpenAI adapter, strict Structured Outputs, and KolliPack
  Assistant Response `1.0` validation successfully.
- The bounded live evaluation covered complete-result explanation, capacity,
  utilization, thickness assumption, informational payload, unsupported
  stacking safety, ready/no-result, and stale-result behavior. All required
  behaviors produced validated grounded outcomes with no grounding flags. One
  initial thickness-assumption candidate was rejected safely and the single
  manual retry validated; application retries remain disabled.
- This is local developer verification only. Railway configuration,
  production provider enablement, and production privacy/legal approval remain
  parked.
- Session 8.5A was evaluated locally with `gpt-5.6-sol`, `xhigh` reasoning,
  the normal Redis/policy gate, the explicit knowledge-disclosure
  acknowledgement, and the 12-case knowledge suite. The first full pass exposed
  a console-encoding defect and insufficient 1,000-token reasoning headroom for
  four complex cases; console output was made ASCII-safe, the no-match rule was
  tightened, and those four cases passed in one explicit 3,000-token manual
  follow-up. Application retries remain disabled.
- Session 10.5 was evaluated locally on 2026-10-09 with the same model,
  reasoning level, shared Redis gate, and 3,000-token bound. Twenty-one
  realistic requests produced 14 valid proposal previews, three
  clarifications, three answers/source denials, and one application-owned safe
  unavailable outcome. There were no retries and no grounding flags. Manual
  browser checks covered Single, Design, Optimal, Packaging Flow, desktop,
  drawer, and phone widths. The complete Single and Design Apply-to-explicit-
  calculation paths matched equivalent manual entry. Full evidence is in
  `engineering/ai-assistant-input-action-evaluation.md`.
- The anonymous Public Expert was evaluated locally on 2026-10-09 with
  `gpt-5.6-sol`, `xhigh`, a loopback-only non-persistent Redis cache, its own
  HMAC session/global throttle, and the normal privacy/provider gate. All 28
  cases returned valid answers: 15 reviewed-knowledge provider calls, 12
  application-owned state/action/disclosure boundaries, and one application-
  owned documentation fallback. There were no unavailable outcomes or retries.
  A purpose-heading ranking issue found in three overview questions was fixed
  once and all three passed a selected real-provider follow-up. Full evidence
  is in `engineering/ai-public-expert-evaluation.md`.

## Implemented

- Architecture investigation
- AI assistant architecture specification
- Versioned `1.0` Tool Context schema and strict validator
- Canonical JSON and semantic SHA-256 state fingerprints
- Deterministic `empty`, `partial`, `invalid`, `ready`, `complete`, and `stale` classification
- Container Selection semantic adapter for Single, Optimal, and Design modes
- Standalone, public Box Size Calculator, and Packaging Flow normalization helpers
- Workflow inherited-input and pending/selected result-state metadata
- Explicit outbound allow-list with database IDs, owners, identity/session data, paths, scenes, placements, and raw model/query objects excluded
- Strict rejection of models, QuerySets, dataclasses, `Decimal`, paths, NumPy values, unknown objects, and non-finite numbers
- Deterministic context, string, nesting, validation-error, warning, fact, proposal, and alternative limits
- Safe deterministic explanation facts and descriptive allowed-proposal metadata
- Catalogue container-weight withholding for the unresolved `PackagingMaterial.part_weight` unit conflict
- Focused contract, privacy, state, fingerprint, mode, public-surface, and Packaging Flow tests
- Authenticated `POST /assistant/context/` application endpoint for the Container Selection pilot
- Server-side `AI_ASSISTANT` entitlement enforcement before catalogue/workflow reconstruction
- Strict JSON request schema, `application/json` content-type enforcement, and 32 KiB inbound request limit
- Fresh standalone reconstruction through the existing form, catalogue visibility, and readiness paths
- Versioned compact standalone result snapshots containing only the semantic fingerprint, compact result, and compact alternatives
- Opaque, session-owned Packaging Flow step references with explicit Container-step binding
- Workflow reconstruction that reapplies the existing inherited-input mechanism and preserves pending versus selected state
- Stale-result suppression when current semantic inputs no longer match the retained result fingerprint
- Endpoint-level CSRF, catalogue isolation, workflow isolation, privacy, response-size, and no-hidden-calculation tests
- Versioned `1.0` Assistant Response contract with strict `answer`, `clarifying_question`, and application-owned `unavailable` outcomes
- Explicit 2,000-character user-message, 4,000-character assistant-message, 16-reference, and 16 KiB provider-response limits
- Plain-text response policy rejecting HTML, URLs, control payloads, unexpected properties, unknown response types/versions, and arbitrary provider metadata
- `fact_refs` validation against existing stable `explanation_facts[].code` values only
- Application-owned read-only assistant orchestration that revalidates and detaches Tool Context before provider invocation
- Minimal versioned read-only provider instructions covering every Tool Context state and the no-calculation/no-mutation boundary
- Small provider protocol with explicit bounded timeout input and an allow-listed provider registry
- Deterministic offline fake provider covering answer, clarification, malformed output, unknown type, missing field, oversized output, timeout, provider failure, and invalid fact reference
- Safe failure normalization with internal diagnostic categories and one fixed unavailable response; raw user/context/provider content is not logged
- No automatic retries and no conversation persistence
- Provider-independent service/contract/privacy/no-hidden-calculation tests
- Application-owned external-provider configuration loader with strict, fail-closed parsing
- External provider traffic disabled by default through `AI_EXTERNAL_PROVIDER_ENABLED`
- Explicit provider identifier, model, credential-reference, timeout, and allow-list checks
- Server-side credential reference contract; credential values are read only from the named environment variable and never returned by configuration objects
- Provider privacy readiness contract covering explicit approval, disclosure-policy version, training/data-use opt-out, retention, data residency, deletion, incident handling, and user-disclosure version
- Explicit readiness outcomes for disabled, invalid, missing-cache, missing-provider, missing-secret, missing-privacy, unsupported-provider, and ready states
- Central external-transmission gate covering authentication, `AI_ASSISTANT` entitlement, capability/context compatibility, readiness, shared-cache safety, and rate allowance
- Mechanically bounded `ExternalAssistantRequest` containing only versioned instructions, the current validated user message, detached validated Tool Context, and detached validated Knowledge Context
- Explicit external-only rejection of private catalogue names, product/material names, descriptions, and part numbers
- Application-owned per-user fixed-window throttle using an HMAC-derived opaque user key, bounded TTL, and fail-closed outcomes
- Atomic backend contract using cache `add`/`incr`; Django local-memory, file, and database caches are not accepted as deployment-shared backends
- Deterministic thread-safe throttle backend for unit tests and shared-state worker simulation
- External service boundary that proves provider non-invocation for every gate denial while preserving the direct offline fake-provider path
- Focused throttle, configuration, readiness, privacy-payload, gate-ordering, failure, and provider-spy tests
- Railway managed Redis selected as the single deployment-shared cache backend
- Pinned `redis==8.1.0` dependency for Django's built-in Redis cache backend
- Optional dedicated `assistant` cache alias sourced only from server-side `REDIS_URL`
- Lazy two-second Redis connection/read bounds that do not make application startup depend on AI infrastructure
- Atomic Redis existing-key increment that preserves the original fixed-window TTL and closes the generic Django Redis expiry race
- Live cache readiness probe covering first add, later increment, final visibility, bounded TTL, cleanup, unsafe aliases, and outages
- `check_ai_readiness` management command with optional expiration/concurrent-client deployment smoke checks and no credential output
- Opt-in live Redis integration tests for rate limits, expiration/reset, concurrent increments, and connection refusal
- Environment-specific deployment documentation for local, test, pre-production, and production
- Explicit `openai` provider registry entry alongside the deterministic `fake` provider
- Official pinned `openai==3.24.0` Python SDK
- Stateless OpenAI Responses API mapping with application instructions, a separate user message, canonical Tool Context JSON, and canonical Knowledge Context JSON
- Strict Structured Outputs through `text.format`, mechanically aligned with Assistant Response `1.0`
- Explicit `store=false`, no provider tools/functions, and no conversation or previous-response state
- Server-owned model, credential-reference, timeout, 3,000-token default output bound, and optional reasoning-effort configuration
- SDK retries disabled with `max_retries=0`; one KolliPack request makes at most one provider invocation
- Explicit refusal, incomplete/empty/unexpected output, authentication, permission, provider rate-limit, timeout, connection, API/server, malformed, oversized, and invalid-response normalization
- Mocked OpenAI adapter tests covering request shape, prompt-injection boundaries, privacy exclusions, strict schema use, no state/tools, failure mapping, and final `fact_refs` authority
- Explicitly opt-in live OpenAI/Redis integration test; ordinary test runs perform zero real OpenAI calls
- Local-only `smoke_openai_assistant` management command using readiness, the real shared Redis throttle, `ask_external`, and final response validation
- First deterministic evaluation set for empty, partial, invalid, ready, complete, capacity, utilization, assumptions, informational payload, stale, and unsupported questions
- Local Redis/OpenAI/privacy-acknowledgement and data-policy documentation
- Authenticated `POST /assistant/ask/` endpoint for the Container Selection pilot
- Strict ask request schema accepting only `tool`, `surface`, `state`, `message`, and workflow-only `step_ref`
- Rejection of browser-supplied Tool Context, provider/model/prompt/history/timeout/reasoning/capability controls, and all other unknown top-level fields
- Shared `build_current_assistant_context` reconstruction used by both `/assistant/context/` and `/assistant/ask/`
- Fresh visibility-scoped standalone catalogue rehydration and current-session workflow `step_ref` reconstruction for every ask
- Existing Packaging Flow inherited-input, pending/selected, compact-result, and complete/ready/stale semantics preserved
- Authentication and `AI_ASSISTANT` entitlement checks before reconstruction/provider work, with normal Django CSRF protection retained
- Final Tool Context `1.0` validation immediately before the external assistant service boundary
- Provider-agnostic view calling `ask_external` with fixed `read_only` capability; configured provider selection remains inside the service and occurs only after the gate allows the request
- Existing external policy/readiness and Redis per-user throttle reused without an HTTP-specific provider quota
- Application-owned successful JSON transport for validated `answer`, `clarifying_question`, and safe `unavailable` Assistant Response `1.0` outcomes
- Endpoint gate-ordering, request-boundary, CSRF, standalone/workflow parity, catalogue isolation, privacy, no-hidden-calculation, response-normalization, throttle, state-mutation, and conversation-persistence tests
- Opt-in live OpenAI integration coverage for an authenticated `/assistant/ask/` request using a freshly reconstructed complete Container result
- Reusable right-side KolliPack Assistant workspace integrated outside engineering forms in the application shell
- Entitled standalone Container Selection entry point and explicitly bound per-step Packaging Flow Container entry points
- Public calculator, anonymous, and non-entitled assistant UI exclusion
- Server-declared prefix-safe Container field map covering the canonical current state without duplicating calculation rules in JavaScript
- Exact stateless ask request construction for standalone and opaque-reference workflow surfaces
- One-turn latest-question/latest-response UI with no history, persistence, retries, actions, or engineering-state mutation
- Escaped plain-text rendering for validated `answer`, `clarifying_question`, and `unavailable` responses
- Visible stale-response invalidation whenever a relevant current engineering input changes
- Context-sensitive suggested questions for before-result and after-result states
- External-AI disclosure and deterministic-calculation authority statement in the panel
- Wide sticky workspace plus responsive drawer/full-width layouts that coexist with expanded/collapsed navigation and preserve the engineering workspace
- Keyboard focus on open, focus trap in overlay mode, Escape close, trigger-focus restoration, accessible labels, and live-region response announcements
- Focused Django rendering/entitlement/form-boundary tests and dependency-free JavaScript serialization/request/error-path tests
- Practical local browser verification of standalone and Packaging Flow binding, stale invalidation, responsive layouts, navigation coexistence, 3D resize behavior, and one real gated OpenAI answer
- Knowledge Context `1.0` kept separate from Tool Context `1.0`
- Explicit ten-file approved documentation source registry with no directory auto-indexing
- Heading-hierarchy Markdown parsing, stable semantic refs, deterministic long-section splitting, and preserved authority/confidence markers
- Process-local per-file mtime/size cache with next-request hot reload and no watcher/database/index service
- Deterministic lexical retrieval with exact/heading/body scoring, definition boosts, explicit and distinctive term aliases, heading-specific terminology tags, active-tool ambiguity scope, and multi-tool comparison-purpose coverage
- Ambiguity protection that keeps Container efficiency separate from Transport frontier efficiency and returns `no_match` for an unqualified cross-tool `block`
- Centrally enforced bounds of six sections, 2,500 characters per section, and 12,000 total documentation characters
- Separate provider mapping for current Tool Context and inert KolliPack Knowledge reference data
- Fail-closed `AI_ASSISTANT_KNOWLEDGE_EXTERNAL_APPROVED` readiness requirement for external documentation transmission
- Browser rejection of `knowledge`, `knowledge_context`, `documents`, and source authority
- Local-debug-only application-generated knowledge trace containing refs, titles, and heading paths without source text or relevance internals
- No-result conceptual answering, cross-tool conceptual knowledge, cross-tool comparison retrieval, and explicit other-tool live-state boundary instructions
- Forty-case Session 8.5B real-provider evaluation fixture and selectable local smoke-command cases
- Focused parser, retrieval, authority, allow-list, hot-reload, bounds, privacy, prompt-injection, trace, provider, endpoint, UI, and failure-isolation tests
- Development knowledge evaluation report and documentation-gap backlog
- Explicit Assistant Response `1.1` evolution preserving answer, clarification, and unavailable semantics while adding a separate provider proposal-candidate path
- Strict `propose_input_changes` Provider Candidate `1.1` with mechanically generated OpenAI Structured Output schema, eight-change cap, known semantic fields, bounded value types, duplicate/extra-property rejection, plain-text summary policy, and SHA-256 state binding
- Separate application-owned Proposal Preview `1.0`; raw provider proposals never reach JavaScript
- Fresh post-provider Container Tool Context reconstruction and fingerprint comparison before proposal preview creation
- Container proposal mapping for manual product dimensions/weight, desired quantity, allowed vertical axes, manual container dimensions/thickness/tare/payload, with current-mode/source-dependent availability
- Explicit deterministic unit normalization limited to mm/cm/m, g/kg, integral pcs, and the existing length/width/height orientation vocabulary
- Proposal merge into copied config only, followed by `ContainerSelectionMode1Form` and shared calculation-free `inspect_container_readiness`
- Ready, incomplete, and invalid resulting-state classification with application-owned per-field valid/invalid/not-editable/unsupported-unit statuses
- Atomic multi-field previews, no-op suppression, catalogue and inherited-source denial, and Optimal-catalogue desired-quantity metadata correction
- Standalone and explicitly bound Packaging Flow Container proposal previews with no upstream/downstream workflow mutation
- Semantic accessible proposal diff rendering, responsive wrapping, explicit not-applied notice, and stale-on-current-input-edit behavior
- Deterministic fake-provider proposal modes for valid single/multi, unknown field, invalid unit/type, stale fingerprint, excessive changes, extra property, and malformed proposal
- Five-case bounded local real-provider proposal evaluation fixture and command option
- Focused proposal contract, Container adapter, endpoint, provider, no-engine, no-mutation, UI, and JavaScript tests
- Application-owned 10-minute Django-signed reviewed-proposal token with random proposal identity and strict bounded payload validation
- Opaque HMAC-derived authenticated-user binding plus tool, surface, original semantic fingerprint, and Packaging Flow `step_ref` binding
- Dedicated authenticated, entitled, CSRF-protected `POST /assistant/apply-proposal/` endpoint with a tighter 16 KiB request limit
- Exact Apply request schemas accepting only the signed token, current allow-listed state, and workflow `step_ref` where required
- Fresh standalone/workflow reconstruction at Apply time through existing catalogue visibility, inheritance, form, readiness, and Tool Context paths
- Repeated fingerprint, field allow-list, source/editability, unit, value, copied-state, form, and conditional-readiness validation
- Atomic application of valid multi-field changes and support for field-valid proposals whose resulting tool state remains incomplete
- Strict Apply Response `1.0` containing only application-owned semantic fields, current config keys, canonical primitive values/units, status, and fixed guidance
- Prefix-safe browser application through the existing server-declared Container field map; no server-provided selectors or JavaScript commands
- Explicit **Apply changes** control, input-only explanation, in-flight double-click protection, live-region success/failure status, and stale/expired handling
- Standalone form-control updates without submission and Packaging Flow persistence limited to the bound Container step's JSON-safe input config
- Existing result-snapshot fingerprint reuse so prior results become stale after Apply, with immediate browser and derived Flow reload warnings
- Replay rejection after current state incorporates the signed changes; tampered, expired, cross-user, and workflow-mismatched tokens fail closed
- Privacy-safe Apply outcome logging without proposal values, prompts, identities, or token content
- Focused Apply tests for standalone, multi-field, units, rotations, incomplete state, stale/replay, signature, expiry, user/step binding, entitlement, CSRF, size, catalogue writes, provider/engine non-invocation, workflow isolation, and JavaScript mapping
- Separate anonymous `public_knowledge` capability; it does not reuse the authenticated `read_only` authority
- Dedicated CSRF-protected `POST /assistant/public-ask/` endpoint accepting exactly `message` and `knowledge_scope`
- Public Expert flag disabled by default, with separate session/global throttle configuration and a fail-closed shared-cache readiness path
- HMAC-derived anonymous-session quota key plus a distinct application-wide public quota; no IP address is read or retained
- Exact three-field public context containing only schema version, public surface, and application-owned scope hint
- Eleven-file, section-level public source registry with no directory auto-indexing and explicit exclusion of AI/provider/deployment/testing/security internals
- Deterministic bounded public retrieval supporting scope-biased “this tool” questions and cross-tool conceptual questions
- Dedicated public prompt and strict three-field Public Expert Response `1.0` schema with no action or fact-reference authority
- Reuse of the one-shot OpenAI Responses transport with `store=false`, strict Structured Outputs, no tools/conversation state, and SDK retries disabled
- Deterministic no-provider boundaries for current form state, current results, calculations, actions, hidden prompts, implementation details, private catalogues, and premium/authenticated behavior
- Fixed public-documentation fallback for genuine no-match questions without a provider call
- Lightweight accessible component on the KolliLabs landing/About routes, KolliPack application home, blog index, every published blog article, and the actual public Box, Bag, Palletization, and Transport calculator routes
- Blog and KolliPack-home Public Expert placement intentionally uses global public knowledge only; article bodies, catalogue data, page DOM, user identity, engineering inputs, and results remain outside the provider request
- Public browser request built only from the component textarea and server-owned scope; no calculator DOM reads, load/open calls, browser storage, or persisted history
- Twenty-eight-case reusable public evaluation catalogue plus a local real-provider smoke command using the public policy, shared cache, retrieval, provider, and final response validation path
- Focused endpoint, capability-isolation, response-schema, cache/throttle, provider-spy, retrieval, prompt-injection, DOM privacy, accessibility, OpenAI request-shape, and existing authenticated-assistant regression tests

## Not implemented

- Live Railway pre-production Redis service, web-service variable reference, and deployment smoke result
- Production provider enablement, credential, and approved privacy-policy values
- Automatic recalculation after Apply
- AI conversation persistence
- Tool Context adapters for other KolliPack tools
- Semantic embeddings, a vector database, external file search, or LLM-selected repository files
- Live Bag, Palletization, or Transport Tool Context adapters
- Public Tool Context, current-form/result access, calculations, actions, private catalogue access, conversation history, or public personalization

## Pilot tool

- Container Selection

## Parked final deployment action

- In the authenticated Railway pre-production environment, provision managed Redis,
  reference its internal URL as the web service's `REDIS_URL`, and run
  `python manage.py check_ai_readiness --smoke --require-cache`. Keep
  `AI_EXTERNAL_PROVIDER_ENABLED=false`.
- Record the exact Gunicorn worker count/start command from Railway and confirm
  the smoke check against the deployed workers. The repository does not own
  those platform values.
- Do not perform this work until the local UI, input-assistant features, and
  evaluation/polish have been approved.

## Next recommended product slice

- **Bag Selection Tool Context plus Assistant actions**, with the mandatory
  Multi-product Bag Selection consumer assessment.
- The Public Expert was deliberately completed first because its authority is
  knowledge-only and independent; it does not count as a Bag Tool Context or
  authenticated Assistant adapter.
- Reuse the validated one-shot proposal, application-owned preview, explicit
  Apply, source-authority, stale-state, and no-hidden-calculation boundaries.
- Keep provider/model/credential/prompt/timeout/reasoning settings server-owned.
- Keep Railway pre-production deployment and privacy approval as a separate,
  explicit deployment decision.

## Architectural decisions recorded

- KolliPack's existing forms, services, and deterministic engines remain authoritative; AI only explains and proposes.
- Tool Context will be versioned, minimal, allow-listed, JSON-safe, and rebuilt from current application state for each request.
- Standalone, public, and Packaging Flow surfaces will normalize into the same semantic contract.
- Tool-specific adapters will live beside each tool; provider orchestration and response validation will live in a shared `packagingapp/assistant/` boundary.
- Provider calls will not be placed in views, templates, JavaScript, calculation engines, or workflow session code.
- LLM output will be treated as untrusted. Only explicit action schemas and field allow-lists may produce a proposal.
- Proposals will be tied to a state fingerprint, validated against fresh state, shown as a diff, and applied only after explicit user action and revalidation.
- Catalogue records, inherited workflow outputs, and selected results will not be silently modified.
- Database IDs, owners, session identifiers, file paths, scenes, raw placements, secrets, and unrelated workflow/catalogue data are excluded from default LLM context.
- The existing `AI_ASSISTANT` entitlement in `packagingapp/entitlements.py` is the future commercial-access authority.
- The first application endpoint is JSON POST-only, authenticated, CSRF-protected, provider-free, and validates Tool Context immediately before returning it.
- Standalone complete/stale state uses a bounded tool-owned result snapshot rather than PDF exports or conversation state.
- Packaging Flow steps use opaque random references stored in the current Django session; indexes, DOM prefixes, case slugs, and client session keys are not accepted as step authority.
- A provider adapter never decides whether transmission is permitted. `packagingapp.assistant.policy` owns the decision before adapter invocation.
- Browser requests cannot choose provider, model, credential, endpoint, prompt, timeout, privacy mode, or throttle bypass. Those values remain server configuration.
- Private catalogue names and part numbers are not sent to external providers in the initial implementation. Alternatives retain anonymous semantic labels.
- `/assistant/ask/` never accepts Tool Context as browser authority; it rebuilds the same trusted current context used by `/assistant/context/`.
- Assistant provider availability is represented as a validated `unavailable` response over successful HTTP transport when the browser request itself is valid.
- The ask view does not import OpenAI or a provider adapter. `ask_external` resolves the configured allow-listed provider only after policy/readiness and quota checks allow the request.

## Repository findings affecting implementation

- Container Selection already has a reusable form, config state, session sanitizer, service, dimension resolver, presenter, shared template wrapper, renderer contract, and Packaging Flow adapter.
- The public Box Size Calculator uses the same Container form/service/result path with public-only catalogue access.
- Packaging Flow stores JSON-safe primitive state and distinguishes a calculated `pending_result` from the explicit `selected` result.
- Standalone calculation results are request-scoped; only PDF export payloads are stored in session. Export payloads are not a suitable assistant state store.
- Design Mode has deterministic candidate generation, ranking, stable candidate IDs, and JSON-safe result structures that a future adapter can consume without duplicating logic.
- Multi-product Container Selection uses the shared geometry engine but currently duplicates some ranking and catalogue serialization; it is not the pattern for the pilot adapter.
- The Multi-product Container draw endpoint currently resolves posted row IDs without the shared visibility-scoped catalogue helpers; it must not be reused as an assistant access pattern and should be reviewed separately before batch-assistant support.
- `PackagingMaterial.part_weight` has conflicting unit semantics across the repository. Container Selection treats it as grams, while model/import and other tool paths describe or consume kilograms. Catalogue weights must not be exposed with a claimed unit until this is resolved.
- Payload is currently an informational metric, not a capacity constraint in the Container packing engine.
- The repository is a non-Docker Railway Django deployment with dependencies in
  `requirements.txt`, Gunicorn declared, and no checked-in start command or
  worker count. Those process values must be read from Railway configuration.
- Railway provides managed Redis and an internal `REDIS_URL`; no repository or
  deployment evidence supports Memcached, so Session 5B selects Redis only.
- PostgreSQL remains application data storage and is not used as a cache.

## Provider-readiness decision classification

### Resolved in Session 5

- External AI is disabled by default and malformed configuration fails closed.
- KolliPack owns one central transmission decision before provider invocation.
- Per-user quotas use only an opaque HMAC of the authenticated server-side user identifier; identity never enters the provider request.
- Private catalogue names and part numbers are excluded from the initial external-provider policy.
- Provider credentials are server-side environment secrets referenced by configuration, never source/browser/session/Tool Context/log values.
- Provider privacy approval and training, retention, residency, deletion, incident, and user-disclosure policy identifiers are mandatory readiness inputs.

### Resolved in Session 5B repository implementation

- One deployment-compatible backend is selected: Railway managed Redis through
  Django's built-in Redis backend.
- The dependency, dedicated cache alias, opaque namespace, atomic counter path,
  bounded TTL validation, fail-closed live probe, management command, integration
  fixture, and environment documentation are implemented.
- Core startup and deterministic tools remain independent of Redis.

### Safely deferred

- `PackagingMaterial.part_weight` remains withheld from Tool Context when its unit is ambiguous. It is a cross-tool data-quality issue, but no longer blocks read-only external AI while withheld.
- Catalogue/inherited effective values are denied as direct Session 9 edits.
  An explicit source-switch-to-manual proposal remains a future action-system
  decision and does not block the current preview-only provider.

### Still blocking production external traffic

- Live pre-production Redis provisioning/reference and the deployment smoke
  result are still required; the authenticated Railway environment was not
  available to this repository session.
- The real `openai` adapter is registered for the local pilot, but no production provider/model/secret reference and value have been approved or enabled.
- Product/legal approval values for provider data use, retention, data residency, deletion, incident handling, and user disclosure have not been supplied.

## Session 2 guardrails

- Implement contract and adapter code plus tests only.
- Do not add an LLM/provider dependency, assistant endpoint, UI, action application, conversation memory, migration, or engine change.
- Reuse current Container validation and results; do not calculate or validate packaging facts in assistant code.
- Prove JSON safety, privacy-field exclusion, and standalone/workflow semantic parity.

## Session 2 implementation notes

- No provider SDK, prompt, endpoint, assistant UI, action handler, migration, or engine behavior was added.
- The adapter consumes existing forms, visibility-scoped catalogue objects, service analysis reports, Top-5 rows, Design candidates, and JSON-safe workflow state. It does not use PDF/report export session payloads as an assistant source.
- A calculation-free shared readiness inspector was added to the Container service because form validation alone does not express source- and mode-dependent prerequisites. It reuses current Container resolution functions and does not run a packing engine.
- `result` is `null` unless the status is `complete`; stale results and their alternatives are suppressed.
- Results retained beyond their calculation request must carry the original semantic state fingerprint. Same-request results bind to the current fingerprint without creating a new session store.
- Optimal callers can provide the visibility-scoped material set so catalogue engineering changes affect the fingerprint through an opaque geometry/volume digest without exposing catalogue identity or metadata.
- Existing Multi-product Container Selection, PDF/report export, catalogue models/imports, JavaScript, templates, and calculation engines were assessed and require no Session 2 changes because this foundation adds an isolated read-only contract rather than changing their shared result or rendering contracts.

## Session 3 implementation notes

- `POST /assistant/context/` accepts exactly `tool`, `surface`, and `state` for standalone requests, plus `step_ref` for workflow requests. The only supported tool is `container_selection`; supported surfaces are `standalone` and `workflow`.
- Authentication failure returns `401`; missing entitlement returns `403`; malformed/schema-invalid requests return `400`; unknown current-session workflow steps return `404`; wrong method returns `405`; wrong content type returns `415`; request/context size failures return `413`; and controlled unsafe context construction returns `422`.
- The endpoint accepts only the allow-listed scalar Container config fields. Catalogue record references are always re-resolved through the current user's visibility-scoped service queries, and catalogue-authoritative dimensions replace posted values.
- The endpoint calls form validation and `inspect_container_readiness`; it does not call `analyze_container_form`, `analyze_container_capacity`, a packing engine, Design generation, rendering, or PDF export.
- A successful normal standalone calculation stores `container_assistant_result_snapshot` only for authenticated entitled users. The snapshot schema is versioned, limited to 32 KiB, and contains the Tool Context schema version, tool, mode, semantic state fingerprint, compact result, and at most five compact alternatives.
- A successful normal Packaging Flow Container run stores the same compact snapshot on that JSON-safe step. Existing raw workflow result structures remain owned by Packaging Flow and are not copied into the assistant snapshot.
- A matching snapshot produces `complete`; a mismatched retained fingerprint produces `stale` with `result = null` and no alternatives; valid inputs without a snapshot produce `ready` without calculation.
- Workflow lookup scans only KolliPack Packaging Flow objects already present in the authenticated request's Django session and matches an opaque per-step reference. Unsupported step types and references from another session fail safely.
- No reusable rate-limiting facility or dependency currently exists in the project. Add per-user throttling before external provider integration; Session 3 introduces no provider cost and intentionally adds no new dependency.

## Session 4 implementation notes

- `packagingapp.assistant.service.ask` accepts only the current message, validated Tool Context, the `read_only` capability, an application-selected provider, and a bounded timeout. It does not accept model, temperature, prompt, token, tool, or function parameters.
- The service validates the user message, revalidates Tool Context `1.0`, creates detached primitive copies, selects the versioned read-only instructions, invokes the provider once, parses bounded JSON, and validates the application response before returning it.
- Provider failure, timeout, malformed output, invalid fact references, and oversized output all become the same safe `unavailable` response. Internal categories remain `provider_timeout`, `provider_unavailable`, `provider_invalid_response`, `provider_response_too_large`, `unsupported_context_version`, `assistant_invalid_request`, and `assistant_internal_error`.
- At the end of Session 4, the fake provider was the only registered/default provider and made no network calls. Session 4 added no provider SDK, API key, or production provider environment setting.
- Fact references use Option A: only stable codes already present in `explanation_facts` may be cited. No new result-field reference namespace was invented.
- The timeout contract is provider-adapter enforced: the service passes a positive bound capped at 30 seconds, and the fake deterministically raises the normalized timeout exception. There are no automatic retries.
- No ask endpoint was added. The callable service and fake provider can be tested without making the browser authoritative for Tool Context; a future endpoint should reuse the existing server-side reconstruction boundary.
- No throttle was added because the repository has no configured shared cache. Before enabling an external provider, configure a deployment-shared cache and use an atomic per-user fixed/sliding window key based on a server-side user identifier, with bounded TTL and fail-closed behavior for provider calls.
- The service stores no messages, contexts, responses, or conversation history in models, sessions, analytics, or provider instances. Safe warning records contain only a normalized outcome category and allow-listed provider identifier.
- This slice changes no Container calculation, presenter, renderer, UI, report, catalogue, public-calculator, Packaging Flow, or multi-product contract. Standalone/public/workflow Tool Context adapters remain the only current consumers; the new service reads their validated output without introducing a second tool path.

## Session 5 implementation notes

- `packagingapp/assistant/throttle.py` implements a fixed window with configurable defaults of 10 requests per 60 seconds. Each cache key contains the capability, window number, and a SHA-256 HMAC of the authenticated user's stable server-side primary key. Email, username, IP address, session key, and raw user ID are not used.
- A first counter is created with atomic cache `add`; subsequent requests use atomic `incr`. Counter TTL is the remaining fixed-window duration and is never longer than the configured window. Backend failure, missing/expired state during increment, malformed counter state, or an unsafe backend returns `throttle_unavailable` and blocks the external path.
- The deterministic backend is for tests/local simulation only. The default Django `LocMemCache` is explicitly not deployment-safe. The production requirement is a configured Redis or Memcached cache alias using one of the reviewed atomic backends; deployment must provide the service and corresponding Python client before eventual Railway external-provider enablement.
- `packagingapp/assistant/configuration.py` parses all optional external settings without making ordinary KolliPack startup depend on AI readiness. It never stores or returns a credential value—only whether the configured server-side environment reference resolves.
- `packagingapp/assistant/policy.py` owns readiness and per-request authorization. Its `ExternalAssistantRequest` contains only instructions, the validated current message, and detached validated Tool Context. Django request/user/session/entitlement objects, secrets, database objects, and throttle identity stop before this boundary.
- `packagingapp/assistant/service.py::ask_external` has no URL and accepts no browser-selected provider options. It invokes an injected, matching allow-listed adapter only after the central gate allows the request. Existing `ask` behavior remains available for deterministic fake-provider unit tests without Redis.
- Session 5 adds no SDK, HTTP provider client, API key, ask endpoint, UI, action, mutation, conversation persistence, migration, or engineering-engine change. It makes no external AI provider calls.

## Session 6 implementation notes

- `packagingapp.assistant.providers.openai.OpenAIAssistantProvider` implements one stateless OpenAI Responses API call behind the existing provider protocol. It does not decide policy and is reached by the real local path only after `ask_external` allows transmission.
- The request sets `store=false`, strict `text.format` JSON Schema, a bounded `max_output_tokens`, the service-owned timeout, and SDK `max_retries=0`. It supplies no tools, function calls, conversation, previous response, web/file search, code execution, or MCP capability.
- OpenAI Structured Outputs requires every field and does not permit a root-level union. The mechanically generated wire schema therefore always includes `fact_refs`; the adapter removes the required empty list for non-answer outcomes before the unchanged Assistant Response validator runs.
- Structured Outputs do not replace KolliPack server-side validation. Unknown response types, wrong fields, unsafe/overlong text, and invented `fact_refs` remain invalid.
- The adapter reads the API key only from the configured server-side environment reference. The credential is passed to the SDK transport and is never included in provider input, readiness output, command output, Tool Context, or logs.
- Provider refusals and every incomplete, malformed, oversized, SDK, or application-validation failure resolve through existing safe outcomes without exposing raw provider structures.
- The deterministic evaluation fixture calculates its complete synthetic Container case through the existing Container service before provider invocation. The provider itself cannot call KolliPack engines or mutate state.
- The implementation stores no messages, responses, response IDs, or conversation history locally and does not use provider-side conversation state.
- The live smoke/evaluation command is local-only, explicitly opt-in, and refuses to run unless readiness is `ready`; the opt-in integration test skips unless all prerequisites are present.
- No Railway configuration or deployment action is part of Session 6.

## Session 7 implementation notes

- `POST /assistant/ask/` requires an authenticated Django user, the existing
  `AI_ASSISTANT` entitlement, normal CSRF, and `application/json`.
- The 32 KiB bounded JSON request accepts exactly `tool`, `surface`, `state`,
  and a message of at most 2,000 characters, plus workflow-only `step_ref`.
- `/assistant/context/` and `/assistant/ask/` use the same
  `build_current_assistant_context` helper. Catalogue IDs remain untrusted and
  are rehydrated with current-user visibility; workflow references remain
  opaque and current-session-owned.
- Each request revalidates Tool Context `1.0` and calls `ask_external` with the
  application-owned `read_only` capability. The view imports neither OpenAI nor
  a concrete provider.
- The external policy gate still owns readiness, privacy, entitlement defense
  in depth, and the existing Redis fixed-window counter. A valid request
  receiving a normalized `unavailable` response remains HTTP 200, preserving
  the distinction between request validity and provider availability.
- The endpoint initiates no Container calculation, Optimal search, Design
  generation, rendering, report work, or result selection. It mutates no
  engineering state and persists no message, response, context, provider ID,
  or conversation history.
- Deterministic tests cover all request gates, all six Tool Context states,
  catalogue and workflow isolation, inherited values, safe provider failures,
  privacy exclusions, quota reuse, and session-state stability. The live test
  remains explicitly opt-in through `KOLLIPACK_TEST_OPENAI_LIVE=1`.
- No Railway configuration or deployment action is part of Session 7.

## Session 8.5A implementation notes

- `packagingapp.assistant.knowledge` owns the ten-file approved registry,
  heading-aware parser, stable semantic refs, authority/confidence markers,
  process-local hot-reload cache, deterministic scoring, strict bounds, context
  validation, and safe trace projection.
- Tool Context continues to represent current engineering state. Knowledge
  Context represents selected documentation only and cannot supply live state
  for Bag, Palletization, Transport, or any non-active tool.
- The OpenAI adapter labels Knowledge Context as inert application-selected
  reference data in a separate developer-role input. It adds no tools, file
  search, embeddings, vector database, retry, conversation, or provider state.
- External readiness requires the original provider privacy contract plus the
  separate knowledge-disclosure acknowledgement. The browser request schema is
  unchanged and rejects every browser-supplied knowledge field.
- Pure conceptual questions can be answered with `result=null`; current-result
  interpretation remains grounded in Tool Context. Unsupported Container
  efficiency produces `no_match`, and the provider instruction prohibits a
  substituted generic or Transport-specific definition.
- The local trace is present only when both `DEBUG` and the explicit trace flag
  are true. It is application-generated and includes no source text, score,
  absolute path, provider metadata, or persistence.
- No deterministic engine, presenter, report, catalogue, Packaging Flow
  calculation, session schema, or multi-product calculation behaviour changed.
- No Railway configuration or deployment action is part of Session 8.5A.

## Session 8.5B implementation notes

- The knowledge evaluation now contains 40 questions across Container, Bag,
  Palletization, Transport, Packaging Flow, cross-tool comparisons, no-result,
  current-result, other-tool-state, and unsupported-documentation behavior.
- A local `gpt-5.6-sol` / `xhigh` run at the server-owned 3,000-token bound
  returned 40 validated responses and zero `unavailable` outcomes. The original
  1,000-token bound had failed four complex cases; no retry behavior was added.
- The current external-Assistant default is 3,000 tokens (Option B). The browser
  still cannot select a budget, configuration remains capped at 4,096, and the
  validated response message remains capped at 4,000 characters.
- Retrieval now applies heading-specific tags to the mixed terminology source,
  distinctive cross-tool concept hints, active-tool scoping for ambiguous
  terms, comparison-purpose reservation, stronger title weighting, and a
  stronger lexical threshold for inferred body-only matches.
- Targeted current-behavior documentation now defines Container cubicity,
  Design efficiency, design quantity/additional capacity, restriction and
  R1/R2/R3; Pallet P1/P2 and Block/Brick; Transport frontier efficiency; and
  Packaging Flow inherited/pending/selected state plus Assistant visibility.
- The first unsupported-question pass exposed one instruction gap: generic
  adhesive advice was offered despite `knowledge_status=no_match`.
  `read_only/v3` now requires an honest documentation limitation when neither
  current Tool Context nor approved Knowledge Context supports the answer. The
  unsupported and current-result cases both passed targeted reruns.
- The approved ten-file registry and the six-section, 2,500-character per
  section, 12,000-character total Knowledge Context bounds are unchanged.
- No response schema, action, Apply capability, live non-Container Tool Context
  adapter, automatic retry, conversation persistence, deterministic engine,
  report, catalogue, renderer, workflow session schema, Railway configuration,
  or deployment behavior changed.

## Session 9 implementation notes

- The provider candidate contract is `1.1`. Existing read-only outcomes retain
  their semantics; `propose_input_changes` is a distinct internal candidate.
  The browser receives Proposal Preview `1.0`, never the raw candidate.
- The OpenAI request remains one stateless Responses API call with
  `store=false`, SDK `max_retries=0`, no tools/functions/search/code/MCP, and no
  provider conversation. Its strict schema is generated from application
  constants and current Tool Context input definitions.
- Each proposal candidate is checked against a freshly reconstructed Tool
  Context fingerprint after the provider returns. Mismatch fails closed.
- The Container adapter normalizes only reviewed units, maps semantic fields to
  current config keys, merges into a deep copy, and reuses
  `ContainerSelectionMode1Form` plus `inspect_container_readiness`.
- Catalogue-authoritative product/container values and inherited Packaging Flow
  product values cannot be directly edited. No source switching is implemented.
- The proposal path calls no Selection, Optimal, Design, renderer, or report
  engine. It modifies no form, workflow step, session result, catalogue/database
  row, browser storage, or conversation state.
- The UI renders application-owned labels and before/after values with semantic
  markup and `textContent`. It has no Apply/Accept/Confirm control and assigns no
  proposed value to an engineering form control.
- The current page keeps only the latest preview in JavaScript memory. Any
  relevant engineering input edit marks it stale; reload clears it.
- The public calculator and all non-Container live adapters remain unchanged.
- No Railway configuration or deployment action is part of Session 9.

## Session 10 implementation notes

- A valid or incomplete-but-field-valid Proposal Preview now receives an
  application-owned `can_apply=true` flag and a signed token. Invalid,
  not-editable, unsupported-unit, and all-no-op outcomes receive no token.
- `packagingapp.assistant.proposal_tokens` uses Django timestamped signing with
  a dedicated salt and 10-minute `max_age`. Its bounded payload contains only
  versions, tool/surface, original fingerprint, canonical changes, an opaque
  HMAC user binding, a random nonce, and workflow `step_ref` when required.
- `POST /assistant/apply-proposal/` accepts exactly the token plus current
  allow-listed state and, for Flow, the opaque step reference. Browser changes,
  fingerprints, labels, selectors, provider output, and other properties are
  rejected.
- Apply reuses fresh context reconstruction, visibility-scoped catalogue
  hydration, Packaging Flow inheritance, the semantic fingerprint,
  `ContainerSelectionMode1Form`, `inspect_container_readiness`, and the Session
  9 unit/source/editability mapping. Validation happens on a deep-copied config
  before any input is changed.
- Successful standalone Apply returns canonical approved field updates for the
  current form. Successful Flow Apply replaces only the bound Container step's
  sanitized config and leaves result, pending/selected output, upstream steps,
  downstream steps, and catalogue/database records unchanged.
- Existing compact result snapshots retain their original fingerprint. Applied
  values therefore make the prior result stale; the browser shows this
  immediately and Flow derives the same warning on subsequent rendering.
- The browser validates the complete Apply Response and field-map plan before
  assigning values. It locks current engineering inputs during the request,
  never submits the form, never focuses Calculate, and replaces the proposal
  action with the fixed applied guidance on success.
- Apply calls no provider, knowledge retrieval, Redis quota, Selection/Optimal/
  Design engine, renderer, report exporter, or workflow result-selection path.
- No model, migration, Redis/cache proposal store, session proposal history,
  browser storage, or conversation persistence was added.
- No Railway configuration or deployment action is part of Session 10.

## Session 10.5 evaluation notes

- Realistic input-action evaluation found one product-facing UI defect: the
  drawer could remain at its introductory scroll position after a provider
  response, leaving the new proposal below the fold. The shared browser UI now
  scrolls only its own content region to the latest interaction.
- Apply now uses the established outline hierarchy rather than the primary
  engineering-action treatment and has an explicit focus-visible ring. It
  remains a labelled, deliberate action and does not resemble Run Analysis,
  Find Top 5, or Generate Designs.
- Starter questions now include `Set product length to 320 mm.` and `Use R1
  and R3 only.` Both still send a normal one-shot message and require proposal
  review and explicit Apply.
- Expired-token wording now tells the user to ask for a new proposal. No
  protocol, token, validation, entitlement, provider, engine, or persistence
  behavior changed.
- The reusable 20-case Session 10.5 evaluation fixture covers realistic
  explanation, proposal, units, rotations, Design, ambiguity, relative input,
  invalid value, deterministic-result reference, source authority, unsupported
  action, and prompt-injection boundaries. Its management-command surface can
  run the whole set or selected cases without applying inputs.
- Manual parity passed for Single (17 pcs, 73%, 9 kg) and Design
  (540 x 400 x 640 mm, cubicity 0.63, efficiency 1.00). Packaging Flow Apply
  changed only its opaque-reference-bound step and created no result until the
  normal step action ran.
- One catalogue-product live response failed provider-output validation and
  resolved to the fixed unavailable outcome. No token or state change occurred;
  catalogue-container and inherited-input live denials plus deterministic
  source-authority tests passed. Monitor recurrence without adding retries.
- `READY_FOR_EXPANSION = YES`. The recommended next product slice is Bag
  Selection Tool Context plus Assistant actions, with the required
  Multi-product Bag Selection consumer assessment. Railway remains a separate
  deployment/privacy decision.
- No Railway configuration or deployment action is part of Session 10.5.

## Anonymous Public Expert implementation notes

- The public capability is additive. The Session 10.5 authenticated Container
  Assistant endpoints, entitlement, Tool Context, proposal, Apply, UI, quotas,
  and tests remain unchanged and continue to pass their focused regression
  suite.
- Supported UI surfaces reflect the requested current public URL map: homepage,
  Box Size Calculator, Bag Size Calculator, Palletization Calculator, and
  Transport Container Loading Calculator. Corrugated and Packaging Flow are
  public knowledge topics but do not currently have equivalent anonymous tool
  routes, so no component was invented for them.
- Public scope is only a retrieval hint. Server-owned capability and response
  contracts, not the active page, enforce the knowledge-only authority.
- Deterministic evaluation covers 28 representative company, product, tool,
  metric, cross-tool, state, calculation, action, disclosure, injection, and
  unsupported-knowledge questions. Retrieval and boundary behavior are
  recorded in `engineering/ai-public-expert-evaluation.md`.
- The live OpenAI command requires the existing explicit local provider/privacy
  acknowledgements, a safe shared cache, `AI_PUBLIC_EXPERT_ENABLED=true`, and
  quotas large enough for the selected cases plus the readiness probe. It does
  not bypass any gate and prints no key, source text, or raw provider payload.
- `READY_FOR_EXPANSION = YES` continues to describe the authenticated Container
  Assistant baseline. Bag Selection Tool Context plus Assistant actions remains
  the recommended next product slice after this deliberately separate public
  feature.
- No migration, deterministic engine change, catalogue write, production data
  change, Railway configuration, deployment, commit, push, or merge is part of
  this implementation.
