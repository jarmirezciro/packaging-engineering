# Git, branches, environment, and deployment

## Branch discipline

Historical workflow:

- development/integration branch: `pre-production`;
- live branch: `production`.

Always verify the actual branch:

```powershell
git branch --show-current
git status
```

Do not assume a copied `.git` directory is correctly configured. Before push work, inspect remotes and upstream:

```powershell
git remote -v
git status -sb
git branch -vv
```

## Agent permissions

Agents may inspect and edit local files within the repository when requested. They must not commit, push, merge, deploy, or alter remote infrastructure unless the user explicitly asks for that action.

## Checkpoints

Before a risky refactor:

```powershell
git add .
git commit -m "Checkpoint before <task>"
```

Do not create a checkpoint commit automatically unless asked; recommend or verify it.

## Local environment variables

A local PowerShell session has historically used:

```powershell
$env:SERVE_MEDIA_FILES="True"
$env:DEBUG="True"
```

These are development settings. Do not copy them into production configuration without reviewing Django settings and Railway variables. Other required secrets/variables must be read from the current project documentation or environment; never invent them.

## Railway and production

Deployment steps may include migrations, static collection, environment variables, custom domains, and superuser creation. These are separate from code implementation.

### AI assistant shared cache (Session 5B)

KolliPack's repository deployment shape is a non-Docker Django application on
Railway. Dependencies are installed from `requirements.txt`; Gunicorn is the
declared production server, PostgreSQL is supplied through `DATABASE_URL`, and
there is no checked-in Railway/Docker/Procfile manifest. The start command,
Gunicorn worker count, and environment/service bindings are therefore owned by
Railway configuration rather than this repository. Verify those values in each
Railway environment before deployment.

The external-assistant throttle uses one dedicated Django cache alias named
`assistant`. Railway's managed Redis service is the selected backend because
Railway supplies an internal `REDIS_URL`, Redis provides deployment-shared
atomic operations and TTLs, and Django 5.2 has a built-in Redis cache backend.
See Railway's [Redis documentation](https://docs.railway.com/databases/redis).
No Memcached service or client is introduced.

Railway work is parked while the assistant is developed and evaluated locally.
The approved sequence is local real provider, local authenticated ask endpoint,
local UI, local input-assistant features, evaluation/polish, and only then final
Railway deployment. When that final deployment phase begins, provision and
validate pre-production before production:

1. Add one Railway Redis service to the pre-production environment.
2. On the pre-production web service, define `REDIS_URL` as a Railway reference
   to the Redis service's `REDIS_URL`; do not paste the resolved credential into
   source or documentation.
3. Set the server-owned values below. Keep external traffic disabled.
4. Deploy the code containing the `redis` dependency and dedicated cache alias.
5. Run `python manage.py check_ai_readiness --smoke --require-cache` in that
   environment. The command exercises atomic add/increment, bounded expiration,
   and concurrent clients without printing the cache URL or credentials.
6. Repeat with a separate Redis service/reference in production only after the
   pre-production check passes. Never reuse the pre-production endpoint or
   credential in production.

Required infrastructure and rate-limit variables:

```text
REDIS_URL=${{Redis.REDIS_URL}}
AI_ASSISTANT_THROTTLE_CACHE_ALIAS=assistant
AI_ASSISTANT_RATE_LIMIT_REQUESTS=10
AI_ASSISTANT_RATE_LIMIT_WINDOW_SECONDS=60
AI_EXTERNAL_PROVIDER_ENABLED=false
```

The repository now supports the local `openai` adapter, but production provider
values must remain unset and external traffic disabled until the final
deployment/privacy approval phase:

```text
AI_EXTERNAL_PROVIDER_ID=
AI_EXTERNAL_PROVIDER_MODEL=
AI_EXTERNAL_PROVIDER_SECRET_ENV=
AI_EXTERNAL_PROVIDER_TIMEOUT_SECONDS=10
AI_EXTERNAL_PROVIDER_MAX_OUTPUT_TOKENS=3000
AI_EXTERNAL_PROVIDER_REASONING_EFFORT=
```

Privacy approval values are deployment-owned and must not be invented:

```text
AI_EXTERNAL_PROVIDER_PRIVACY_APPROVED=false
AI_EXTERNAL_DISCLOSURE_POLICY_VERSION=
AI_EXTERNAL_PROVIDER_TRAINING_OPT_OUT_CONFIRMED=false
AI_EXTERNAL_PROVIDER_RETENTION_POLICY=
AI_EXTERNAL_PROVIDER_DATA_RESIDENCY_POLICY=
AI_EXTERNAL_PROVIDER_DELETION_POLICY=
AI_EXTERNAL_PROVIDER_INCIDENT_POLICY=
AI_EXTERNAL_PROVIDER_USER_DISCLOSURE_VERSION=
```

The eventual user disclosure must state that an external AI service is used,
only bounded engineering context is sent, deterministic KolliPack engines remain
authoritative, and assistant availability is independent of the engineering
tools. Do not mark that disclosure approved until the product/legal decision and
the actual UI copy exist.

Environment behavior:

- Local and standard unit CI require no Redis. The default cache remains local,
  deterministic KolliPack and the fake provider tests continue to work, and the
  external path reports a missing shared cache when otherwise evaluated.
- Optional local/integration testing sets `KOLLIPACK_TEST_REDIS_URL` and runs
  `packagingapp.tests.test_assistant_redis_integration`.
- The local OpenAI pilot uses a developer-owned Redis instance and explicit
  local acknowledgement values documented in
  `docs/engineering/ai-assistant-local-openai.md`; those values are not valid
  production approvals.
- Pre-production and production each require their own managed Redis service and
  server-side `REDIS_URL` reference for the external-provider path.
- Redis connections are lazy and have two-second connect/read timeouts. Missing
  or unavailable Redis does not prevent Django startup or deterministic tools;
  the external-provider gate fails closed.

The key namespace is versioned under `kollipack:assistant:rate:v1`. User identity
is a SHA-256 HMAC; raw user IDs, usernames, emails, IP addresses, and session keys
are absent. Readiness keys use a separate ephemeral namespace and are deleted
after probing.

### Contact-form email delivery

The public contact form sends to `CONTACT_EMAIL` (default:
`jaramirezciro@gmail.com`). Set the following variables in the deployment
environment to enable delivery through an SMTP provider; keep the username and
password out of the repository:

```text
CONTACT_EMAIL=jaramirezciro@gmail.com
DEFAULT_FROM_EMAIL=<verified sender address>
EMAIL_HOST=<smtp host>
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp username>
EMAIL_HOST_PASSWORD=<smtp password or app password>
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_TIMEOUT=20
```

For Gmail SMTP, use `smtp.gmail.com` on port `587` with TLS and an App Password
for the sending account. `DEFAULT_FROM_EMAIL` should be an address that the
provider permits that account to send from. A local development setup can use
Django's console backend by setting `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`.

If the hosting provider blocks outbound SMTP, use Brevo's HTTPS API instead of
SMTP. Set `EMAIL_TRANSPORT=brevo_api`, add `BREVO_API_KEY` using a Brevo API key
(not an SMTP key), and keep `DEFAULT_FROM_EMAIL` set to a verified Brevo sender.
The API endpoint defaults to `https://api.brevo.com/v3/smtp/email` and uses
normal HTTPS traffic.

Rules:

- no production/Railway change during a normal coding task;
- no production migration without explicit request and migration review;
- no hard-coded secrets;
- no enabling `DEBUG=True` in production;
- do not confuse DNS/SSL/domain issues with application-code correctness;
- verify both pre-production and production targets before merging/deploying.

## Promotion checklist

When explicitly asked to move pre-production to production:

1. clean Git state;
2. tests/checks pass;
3. review branch diff;
4. merge using the project’s chosen workflow;
5. push the intended branch;
6. verify Railway service/branch mapping;
7. run only required migrations;
8. smoke-test key public and authenticated routes;
9. verify media/static/PDF/3D output;
10. document rollback point.
