# Local OpenAI assistant provider pilot

## Scope

This guide covers the local provider pilot, the authenticated ask endpoint,
the Session 8.5B-calibrated approved-documentation knowledge layer, the
Session 9 proposal preview, and the Session 10 explicit input-only Apply
boundary. It does not
approve production external AI or configure Railway. The command and opt-in
tests below make an external request only after explicit invocation and only
through KolliPack's normal readiness, Redis throttle, provider, and Assistant
Response validation path.

## Request contract

The local provider uses the OpenAI Responses API through the official Python
SDK `openai==3.24.0`:

```text
ExternalAssistantRequest
        + current Tool Context
        + selected Knowledge Context
        ↓
OpenAI Responses API
        ↓
strict text.format JSON Schema
        ↓
untrusted provider candidate
        ↓
KolliPack Provider Candidate 1.1 validation
        ↓
answer/clarification/unavailable or local Proposal Preview 1.0 validation
```

Each call sets `store=false`, uses a server-configured model, applies the
application timeout, sets a 3,000-token default maximum output, and disables SDK
retries with `max_retries=0`. No OpenAI tools, function calls, web search,
conversation object, `previous_response_id`, or assistant/thread state is used.
Usage metadata is ignored in this pilot.

For an explicit input-change request, the provider may return only a bounded
`propose_input_changes` candidate tied to the current Tool Context fingerprint.
KolliPack then reconstructs fresh state, normalizes reviewed units, validates a
copy through the current Container form/readiness path, and builds the browser
preview. The provider candidate is not an Apply instruction and is never sent
directly to JavaScript.

When the user explicitly presses **Apply changes**, the separate
`POST /assistant/apply-proposal/` endpoint validates the short-lived signed
review reference against freshly reconstructed current state. Apply is wholly
application-side: it makes no OpenAI/provider or knowledge-retrieval request,
does not consume the Redis provider quota, and does not run a Container
calculation. It updates approved current inputs only; the user must still run
the normal tool action.

The request input contains only:

- versioned application instructions (`read_only/v4`);
- the current validated user question;
- canonical JSON for the current validated Tool Context;
- canonical JSON for the bounded application-selected Knowledge Context.

Tool Context and Knowledge Context are supplied in separate developer-role
input items and are explicitly labelled as data/reference data. The user
question is a separate user-role item. Knowledge is selected only from the
application allow-list; the browser and model cannot choose repository files.

Identity, email, username, session and CSRF values, database and owner IDs,
private catalogue names, part numbers and descriptions, file paths, scenes,
placements, full workflow state, Redis keys, and API credentials are excluded
from prompt/input data. The OpenAI API key is used only by the SDK as a
transport credential.

## Install local dependencies

Use the project's normal environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Start a local Redis service

Use an existing local Redis installation, or optionally start a disposable
development container:

```powershell
docker run --name kollipack-local-redis -p 6379:6379 redis:8-alpine
```

Docker is not a KolliPack runtime dependency. On a Windows development machine
without Docker or WSL, the local pilot was also verified with the portable
Redis for Windows package available through `winget`:

```powershell
winget install --id taizod1024.redis-windows-fork --exact --scope user `
  --silent --accept-package-agreements --accept-source-agreements

# Open a new PowerShell after installation so the command alias is available.
$redisServer = (Get-Command redis-server.exe).Source
Start-Process -FilePath $redisServer `
  -ArgumentList '--port 6379 --bind 127.0.0.1 --protected-mode yes --save "" --appendonly no' `
  -WindowStyle Hidden
```

This alternative is loopback-only and non-persistent for the local pilot; it
is not a KolliPack runtime or production dependency. Configure a non-production
Redis database, for example:

```powershell
$env:REDIS_URL = "redis://127.0.0.1:6379/15"
$env:AI_ASSISTANT_THROTTLE_CACHE_ALIAS = "assistant"
```

## Configure the local provider

Set these values in the same PowerShell process that will run Django. Replace
`<compatible-model-id>` with one model available to the developer's OpenAI
project that supports Responses API Structured Outputs.

```powershell
$env:AI_EXTERNAL_PROVIDER_ENABLED = "true"
$env:AI_EXTERNAL_PROVIDER_ID = "openai"
$env:AI_EXTERNAL_PROVIDER_MODEL = "<compatible-model-id>"
$env:AI_EXTERNAL_PROVIDER_SECRET_ENV = "OPENAI_API_KEY"
$env:OPENAI_API_KEY = "<developer-secret>"
$env:AI_EXTERNAL_PROVIDER_TIMEOUT_SECONDS = "10"
$env:AI_EXTERNAL_PROVIDER_MAX_OUTPUT_TOKENS = "3000"
$env:AI_EXTERNAL_PROVIDER_REASONING_EFFORT = "low"
$env:AI_ASSISTANT_RATE_LIMIT_REQUESTS = "50"
$env:AI_ASSISTANT_RATE_LIMIT_WINDOW_SECONDS = "60"
```

`AI_EXTERNAL_PROVIDER_REASONING_EFFORT` is optional. Leave it empty for a
compatible model that does not accept reasoning-effort configuration. It is
always server-owned and is never accepted from a browser or user message.

## Record explicit local privacy acknowledgement

The readiness gate deliberately requires explicit values. The following are
local-development acknowledgements, not production legal/privacy approval:

```powershell
$env:AI_EXTERNAL_PROVIDER_PRIVACY_APPROVED = "true"
$env:AI_EXTERNAL_DISCLOSURE_POLICY_VERSION = "1.0"
$env:AI_EXTERNAL_PROVIDER_TRAINING_OPT_OUT_CONFIRMED = "true"
$env:AI_EXTERNAL_PROVIDER_RETENTION_POLICY = "openai-standard-abuse-monitoring-up-to-30-days-local-ack-v1"
$env:AI_EXTERNAL_PROVIDER_DATA_RESIDENCY_POLICY = "no-provider-region-guarantee-local-pilot-v1"
$env:AI_EXTERNAL_PROVIDER_DELETION_POLICY = "store-false-no-response-application-state-local-pilot-v1"
$env:AI_EXTERNAL_PROVIDER_INCIDENT_POLICY = "developer-local-pilot-no-production-approval-v1"
$env:AI_EXTERNAL_PROVIDER_USER_DISCLOSURE_VERSION = "developer-only-no-end-user-ui-v1"
$env:AI_ASSISTANT_KNOWLEDGE_EXTERNAL_APPROVED = "true"
```

The knowledge approval is a separate disclosure decision because approved
repository documentation text is a different outbound data category from Tool
Context. It defaults to false. Set it only for a deliberate local knowledge
evaluation; production approval remains separate and parked.

To show the application-generated section trace locally, both Django `DEBUG`
and this explicit flag must be enabled:

```powershell
$env:AI_ASSISTANT_KNOWLEDGE_TRACE_ENABLED = "true"
```

The trace contains semantic refs, titles, and heading paths only. It never
contains retrieved source text, scores, or absolute paths.

OpenAI states that API data is not used to train models by default unless the
organization opts in. Standard abuse-monitoring logs may contain customer
content and are normally retained for up to 30 days. This integration sets
`store=false` to disable Responses API application-state storage, but that does
not by itself mean Zero Data Retention, no provider logging, GDPR compliance,
or EU-only processing. Zero Data Retention, Modified Abuse Monitoring, and data
residency are separate organization/project controls and are not assumed by
KolliPack. See the official OpenAI documentation for [data controls](https://developers.openai.com/api/docs/guides/your-data), [Responses API state and storage](https://developers.openai.com/api/docs/guides/migrate-to-responses), and [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## Check readiness before any real call

```powershell
.\.venv\Scripts\python.exe manage.py check_ai_readiness --smoke --require-cache
```

Do not continue unless the output includes:

```text
external_provider_readiness=ready
```

Do not bypass a different outcome. Correct the reported local prerequisite.

## Run one explicit real smoke request

```powershell
$env:KOLLIPACK_OPENAI_LOCAL_SMOKE = "1"
.\.venv\Scripts\python.exe manage.py smoke_openai_assistant
```

The command builds a safe synthetic Container calculation with KolliPack's
existing deterministic service (`200 × 100 × 80 mm` product,
`600 × 400 × 300 mm` internal container, desired quantity `20`), then sends its
validated Tool Context through the normal external policy gate. It prints only
the provider/model, question, calculation status, validated response type,
validated message, validated fact references, and review flags. It never prints
the API key or raw OpenAI response.

## Run the opt-in live test or evaluation set

Ordinary tests never call OpenAI. To run the opt-in live integration tests:

```powershell
$env:KOLLIPACK_TEST_OPENAI_LIVE = "1"
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_openai_live_integration
```

To run all 11 initial engineering questions through the same gate:

```powershell
.\.venv\Scripts\python.exe manage.py smoke_openai_assistant --evaluation
```

To run the 40-case Session 8.5B knowledge evaluation:

```powershell
.\.venv\Scripts\python.exe manage.py smoke_openai_assistant --knowledge-evaluation
```

To run the five-case Session 9 structured-proposal evaluation:

```powershell
.\.venv\Scripts\python.exe manage.py smoke_openai_assistant --proposal-evaluation
```

To run the 20-case Session 10.5 realistic input-action evaluation:

```powershell
.\.venv\Scripts\python.exe manage.py smoke_openai_assistant --input-action-evaluation
```

This suite covers explanation, simple and multi-field proposals, reviewed unit
conversion, rotations, Design inputs, ambiguity, relative requests,
unsupported units, invalid values, current-result references, catalogue and
workflow source authority, unsupported candidate selection, and prompt
injection. Use repeated `--case` options to run only gaps from an ongoing
manual browser evaluation; the command still performs no Apply and makes no
calculation after provider evaluation.

The proposal evaluation covers a single-field change, an atomic two-field
change, explicit `cm` normalization, an ambiguous request that must not invent
a value, and a read-only explanation regression. Valid proposal candidates are
reconstructed into an application-owned preview with before/after values,
field statuses, resulting validation state, and the fixed not-applied notice.
The command does not apply inputs or invoke a Container calculation engine.

One or more cases can be selected for an explicit manual follow-up:

```powershell
.\.venv\Scripts\python.exe manage.py smoke_openai_assistant `
  --knowledge-evaluation `
  --case design_mode `
  --case frontier_efficiency
```

The knowledge evaluation prints application-generated retrieved refs in
addition to the existing safe fields. It does not print source text or raw
provider structures. Session 8.5B set the server-owned default to 3,000 after
four complex `xhigh` knowledge cases exhausted the original 1,000-token bound
and all four passed an explicit 3,000-token follow-up. The configuration
validator still caps this setting at 4,096, the browser cannot select it, and
the final Assistant Response message remains capped at 4,000 characters by
KolliPack.

The live module covers both the provider-level full gate and a real
authenticated, CSRF-protected `POST /assistant/ask/` request. The endpoint test
first creates a normal complete Container result, then asks `Explain this
result.` so it verifies fresh server reconstruction, policy, Redis, OpenAI, and
final Assistant Response validation together. It prints no credential or raw
provider object.

The initial engineering evaluation covers empty, partial, invalid, ready, complete, capacity,
utilization, thickness assumption, informational payload, stale, and
unsupported stacking-safety questions. Configure at least 11 requests in the
current rate window before running it. The knowledge evaluation covers 40
questions and requires a configured allowance of at least 40 requests. The
proposal evaluation covers five questions and requires at least five requests
in the current window. The command never bypasses the throttle.
Review the validated answers and `grounding_flags` for invented global
optimality, payload constraints, strength/protection/manufacturing conclusions,
rejected-candidate causes, orientation sensitivity, or unsupported limiting
constraints.

## Run the anonymous Public Expert evaluation

The Public Expert uses the same reviewed OpenAI credential/privacy settings and
stateless Responses transport, but it has a separate `public_knowledge`
capability, prompt, context/response schema, UI flag, and throttle namespace.
It never sends Tool Context, form state, results, actions, catalogue records,
user identity, session identity, or conversation history.

Enable it only in the local shell where the provider and shared-cache settings
above are already ready:

```powershell
$env:AI_PUBLIC_EXPERT_ENABLED = "true"
$env:AI_PUBLIC_EXPERT_THROTTLE_CACHE_ALIAS = "assistant"
$env:AI_PUBLIC_EXPERT_SESSION_RATE_LIMIT_REQUESTS = "28"
$env:AI_PUBLIC_EXPERT_SESSION_RATE_LIMIT_WINDOW_SECONDS = "600"
$env:AI_PUBLIC_EXPERT_GLOBAL_RATE_LIMIT_REQUESTS = "29"
$env:AI_PUBLIC_EXPERT_GLOBAL_RATE_LIMIT_WINDOW_SECONDS = "3600"
$env:AI_PUBLIC_EXPERT_MAX_OUTPUT_TOKENS = "1000"
$env:KOLLIPACK_OPENAI_LOCAL_SMOKE = "1"
```

The global allowance is one larger than the 28-case catalogue because the
command intentionally runs one readiness request through the real public gate
before evaluation. A selected subset may use correspondingly smaller session
and global allowances.

Run the full set:

```powershell
.\.venv\Scripts\python.exe manage.py smoke_openai_public_expert
```

Or run named cases while investigating a gap:

```powershell
.\.venv\Scripts\python.exe manage.py smoke_openai_public_expert `
  --case kollipack `
  --case container_this_tool `
  --case result_utilization `
  --case injection_internal
```

The command uses the public feature gate, cache probe, HMAC session/global
quotas, deterministic public retrieval, application boundary responses, real
OpenAI adapter where required, and final Public Expert Response validation. It
prints case names, categories, scopes, semantic knowledge refs, validated
response types/messages, provider/model, and totals. It does not print the API
key, retrieved source text, raw request/response bodies, cache keys, or session
identifier. Ordinary tests and normal page rendering make no real provider
request; opening the panel also makes no request.

Public source tracing in HTTP responses is off by default. For deliberate local
debugging it additionally requires Django `DEBUG` and:

```powershell
$env:AI_PUBLIC_EXPERT_KNOWLEDGE_TRACE_ENABLED = "true"
```

This flag returns only application-generated semantic refs/titles/heading
paths. It never returns retrieved text, scores, repository paths, prompts, or
provider structures. Keep `AI_PUBLIC_EXPERT_ENABLED=false` in every environment
until its own shared-cache, provider, privacy/disclosure, abuse, accessibility,
and content evaluation is explicitly approved.
