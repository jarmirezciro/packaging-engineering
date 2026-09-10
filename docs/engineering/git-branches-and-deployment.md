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
