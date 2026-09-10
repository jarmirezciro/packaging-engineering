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
