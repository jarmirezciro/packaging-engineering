"""
Django settings for packagingproject.

This file preserves the existing application configuration while adding the
minimum environment-based settings required for local development and a
Railway soft launch.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    default_value = "true" if default else "false"
    return os.environ.get(name, default_value).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable as a clean list."""
    return [
        item.strip()
        for item in os.environ.get(name, default).split(",")
        if item.strip()
    ]


# -----------------------------------------------------------------------------
# Core security and environment settings
# -----------------------------------------------------------------------------

DEBUG = env_bool("DEBUG", default=False)
SERVE_MEDIA_FILES = env_bool("SERVE_MEDIA_FILES", default=DEBUG)

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-local-development-only-change-me"
    else:
        raise ImproperlyConfigured(
            "SECRET_KEY environment variable is required when DEBUG=False."
        )

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
elif not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS environment variable is required when DEBUG=False."
    )

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")


# -----------------------------------------------------------------------------
# Application definition
# -----------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sitemaps",
    "django.contrib.staticfiles",
    "packagingapp",
    "widget_tweaks",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "packagingproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "packagingapp.context_processors.subscription_context",
                "packagingapp.context_processors.public_expert_context",
            ],
        },
    },
]

WSGI_APPLICATION = "packagingproject.wsgi.application"


# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    raise ImproperlyConfigured(
        "DATABASE_URL environment variable is required when DEBUG=False."
    )


# -----------------------------------------------------------------------------
# Password validation
# -----------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# -----------------------------------------------------------------------------
# Internationalization
# -----------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# -----------------------------------------------------------------------------
# Static files and runtime-generated/user-uploaded media
# -----------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}


# -----------------------------------------------------------------------------
# Authentication redirects
# -----------------------------------------------------------------------------

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"


# -----------------------------------------------------------------------------
# Railway / HTTPS security
# -----------------------------------------------------------------------------

# Railway terminates HTTPS at its proxy and forwards the original protocol.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Keep this disabled for the first deployment. It can be enabled through an
# environment variable after confirming Railway proxy handling works correctly.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=False)


# -----------------------------------------------------------------------------
# Logging to Railway stdout/stderr
# -----------------------------------------------------------------------------

LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}


# -----------------------------------------------------------------------------
# Existing project settings
# -----------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TAILWIND_APP_NAME = "theme"

# -----------------------------------------------------------------------------
# Marketing/contact page settings
# -----------------------------------------------------------------------------
# Email transport is configured through deployment environment variables so
# SMTP credentials never need to be committed to the repository.
EMAIL_TRANSPORT = os.environ.get("EMAIL_TRANSPORT", "smtp").strip().lower()
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "20"))

# Brevo's HTTPS API is useful on hosts that block outbound SMTP connections.
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_API_URL = os.environ.get("BREVO_API_URL", "https://api.brevo.com/v3/smtp/email")
BREVO_API_TIMEOUT = int(os.environ.get("BREVO_API_TIMEOUT", "20"))
BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "KolliLabs")

# Destination for messages submitted through the public contact form. Set the
# CONTACT_EMAIL environment variable in a deployment to override this default.
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "jaramirezciro@gmail.com")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", CONTACT_EMAIL or "webmaster@localhost")


# -----------------------------------------------------------------------------
# AI assistant external-provider safety configuration
# -----------------------------------------------------------------------------
# These values are deliberately read as raw strings.  The assistant's strict
# configuration loader validates them without breaking ordinary deterministic
# KolliPack startup when optional external AI configuration is absent or bad.
# No provider credential is loaded into Django settings; only the name of the
# server-side environment variable that will eventually hold it is configured.
AI_EXTERNAL_PROVIDER_ENABLED = os.environ.get(
    "AI_EXTERNAL_PROVIDER_ENABLED", "false"
)
AI_EXTERNAL_PROVIDER_ID = os.environ.get("AI_EXTERNAL_PROVIDER_ID", "")
AI_EXTERNAL_PROVIDER_MODEL = os.environ.get("AI_EXTERNAL_PROVIDER_MODEL", "")
AI_EXTERNAL_PROVIDER_SECRET_ENV = os.environ.get(
    "AI_EXTERNAL_PROVIDER_SECRET_ENV", ""
)
AI_EXTERNAL_PROVIDER_TIMEOUT_SECONDS = os.environ.get(
    "AI_EXTERNAL_PROVIDER_TIMEOUT_SECONDS", "10"
)
AI_EXTERNAL_PROVIDER_MAX_OUTPUT_TOKENS = os.environ.get(
    "AI_EXTERNAL_PROVIDER_MAX_OUTPUT_TOKENS", "3000"
)
AI_EXTERNAL_PROVIDER_REASONING_EFFORT = os.environ.get(
    "AI_EXTERNAL_PROVIDER_REASONING_EFFORT", ""
)

# Redis is optional at application startup. Railway deployments that need the
# external-provider readiness path reference the managed Redis service through
# REDIS_URL; local development and ordinary deterministic KolliPack operation
# continue to use the process-local default cache without requiring Redis.
REDIS_URL = os.environ.get("REDIS_URL", "").strip()
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "kollipack-default",
    }
}
if REDIS_URL:
    CACHES["assistant"] = {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "kollipack-assistant",
        "OPTIONS": {
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
        },
    }

AI_ASSISTANT_THROTTLE_CACHE_ALIAS = os.environ.get(
    "AI_ASSISTANT_THROTTLE_CACHE_ALIAS", "assistant"
)
AI_ASSISTANT_RATE_LIMIT_REQUESTS = os.environ.get(
    "AI_ASSISTANT_RATE_LIMIT_REQUESTS", "10"
)
AI_ASSISTANT_RATE_LIMIT_WINDOW_SECONDS = os.environ.get(
    "AI_ASSISTANT_RATE_LIMIT_WINDOW_SECONDS", "60"
)

# Production external AI may be enabled only after deployment-owned approvals
# and policy identifiers are explicitly supplied. Empty/false defaults are
# intentionally incomplete and fail closed; local pilot acknowledgements do not
# constitute production approval.
AI_EXTERNAL_PROVIDER_PRIVACY_APPROVED = os.environ.get(
    "AI_EXTERNAL_PROVIDER_PRIVACY_APPROVED", "false"
)
AI_EXTERNAL_DISCLOSURE_POLICY_VERSION = os.environ.get(
    "AI_EXTERNAL_DISCLOSURE_POLICY_VERSION", ""
)
AI_EXTERNAL_PROVIDER_TRAINING_OPT_OUT_CONFIRMED = os.environ.get(
    "AI_EXTERNAL_PROVIDER_TRAINING_OPT_OUT_CONFIRMED", "false"
)
AI_EXTERNAL_PROVIDER_RETENTION_POLICY = os.environ.get(
    "AI_EXTERNAL_PROVIDER_RETENTION_POLICY", ""
)
AI_EXTERNAL_PROVIDER_DATA_RESIDENCY_POLICY = os.environ.get(
    "AI_EXTERNAL_PROVIDER_DATA_RESIDENCY_POLICY", ""
)
AI_EXTERNAL_PROVIDER_DELETION_POLICY = os.environ.get(
    "AI_EXTERNAL_PROVIDER_DELETION_POLICY", ""
)
AI_EXTERNAL_PROVIDER_INCIDENT_POLICY = os.environ.get(
    "AI_EXTERNAL_PROVIDER_INCIDENT_POLICY", ""
)
AI_EXTERNAL_PROVIDER_USER_DISCLOSURE_VERSION = os.environ.get(
    "AI_EXTERNAL_PROVIDER_USER_DISCLOSURE_VERSION", ""
)
AI_ASSISTANT_KNOWLEDGE_EXTERNAL_APPROVED = os.environ.get(
    "AI_ASSISTANT_KNOWLEDGE_EXTERNAL_APPROVED", "false"
)
AI_ASSISTANT_KNOWLEDGE_TRACE_ENABLED = os.environ.get(
    "AI_ASSISTANT_KNOWLEDGE_TRACE_ENABLED", "false"
)

# Anonymous Public Expert. This is a separate, knowledge-only capability and is
# disabled by default. It reuses the configured external provider and shared
# cache transport, but owns independent session/global quotas and output bounds.
AI_PUBLIC_EXPERT_ENABLED = os.environ.get("AI_PUBLIC_EXPERT_ENABLED", "false")
AI_PUBLIC_EXPERT_THROTTLE_CACHE_ALIAS = os.environ.get(
    "AI_PUBLIC_EXPERT_THROTTLE_CACHE_ALIAS",
    AI_ASSISTANT_THROTTLE_CACHE_ALIAS,
)
AI_PUBLIC_EXPERT_SESSION_RATE_LIMIT_REQUESTS = os.environ.get(
    "AI_PUBLIC_EXPERT_SESSION_RATE_LIMIT_REQUESTS", "6"
)
AI_PUBLIC_EXPERT_SESSION_RATE_LIMIT_WINDOW_SECONDS = os.environ.get(
    "AI_PUBLIC_EXPERT_SESSION_RATE_LIMIT_WINDOW_SECONDS", "600"
)
AI_PUBLIC_EXPERT_GLOBAL_RATE_LIMIT_REQUESTS = os.environ.get(
    "AI_PUBLIC_EXPERT_GLOBAL_RATE_LIMIT_REQUESTS", "120"
)
AI_PUBLIC_EXPERT_GLOBAL_RATE_LIMIT_WINDOW_SECONDS = os.environ.get(
    "AI_PUBLIC_EXPERT_GLOBAL_RATE_LIMIT_WINDOW_SECONDS", "3600"
)
AI_PUBLIC_EXPERT_MAX_OUTPUT_TOKENS = os.environ.get(
    "AI_PUBLIC_EXPERT_MAX_OUTPUT_TOKENS", "1000"
)
AI_PUBLIC_EXPERT_KNOWLEDGE_TRACE_ENABLED = os.environ.get(
    "AI_PUBLIC_EXPERT_KNOWLEDGE_TRACE_ENABLED", "false"
)
