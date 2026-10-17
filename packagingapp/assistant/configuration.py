"""Strict server-side configuration for external assistant providers."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
import re
from typing import Mapping

from django.conf import settings

from .providers import SUPPORTED_ASSISTANT_PROVIDERS


EXTERNAL_DISCLOSURE_POLICY_VERSION = "1.0"
_PROVIDER_ID = re.compile(r"[a-z0-9_-]{1,32}\Z")
_SECRET_ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]{1,127}\Z")


@dataclass(frozen=True)
class ProviderPrivacyConfiguration:
    approved: bool
    disclosure_policy_version: str
    training_opt_out_confirmed: bool
    retention_policy: str
    data_residency_policy: str
    deletion_policy: str
    incident_policy: str
    user_disclosure_version: str
    knowledge_external_approved: bool

    @property
    def base_complete(self) -> bool:
        return bool(
            self.approved
            and self.disclosure_policy_version
            == EXTERNAL_DISCLOSURE_POLICY_VERSION
            and self.training_opt_out_confirmed
            and self.retention_policy
            and self.data_residency_policy
            and self.deletion_policy
            and self.incident_policy
            and self.user_disclosure_version
        )

    @property
    def complete(self) -> bool:
        return bool(self.base_complete and self.knowledge_external_approved)


@dataclass(frozen=True)
class ExternalProviderConfiguration:
    enabled: bool
    provider_id: str
    model_id: str
    timeout_seconds: float
    max_output_tokens: int
    reasoning_effort: str
    secret_env_name: str
    secret_present: bool
    throttle_cache_alias: str
    rate_limit_requests: int
    rate_limit_window_seconds: int
    privacy: ProviderPrivacyConfiguration
    errors: tuple[str, ...]


def _strict_bool(value, name: str, errors: list[str]) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    errors.append(f"{name}_invalid")
    return False


def _positive_int(
    value,
    name: str,
    errors: list[str],
    *,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        errors.append(f"{name}_invalid")
        return 0
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value)
    else:
        errors.append(f"{name}_invalid")
        return 0
    if parsed <= 0 or parsed > maximum:
        errors.append(f"{name}_invalid")
        return 0
    return parsed


def _timeout(value, errors: list[str]) -> float:
    if isinstance(value, bool):
        errors.append("provider_timeout_invalid")
        return 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        errors.append("provider_timeout_invalid")
        return 0.0
    if not math.isfinite(parsed) or parsed <= 0 or parsed > 30:
        errors.append("provider_timeout_invalid")
        return 0.0
    return parsed


def _string(value, name: str, errors: list[str], *, maximum: int = 128) -> str:
    if not isinstance(value, str):
        errors.append(f"{name}_invalid")
        return ""
    normalized = value.strip()
    if len(normalized) > maximum or any(ord(character) < 32 for character in normalized):
        errors.append(f"{name}_invalid")
        return ""
    return normalized


def load_external_provider_configuration(
    *,
    environment: Mapping[str, str] | None = None,
) -> ExternalProviderConfiguration:
    """Read settings without ever returning a provider credential value."""
    environment = os.environ if environment is None else environment
    errors: list[str] = []

    enabled = _strict_bool(
        getattr(settings, "AI_EXTERNAL_PROVIDER_ENABLED", False),
        "external_provider_enabled",
        errors,
    )
    provider_id = _string(
        getattr(settings, "AI_EXTERNAL_PROVIDER_ID", ""),
        "provider_id",
        errors,
        maximum=32,
    )
    if provider_id and not _PROVIDER_ID.fullmatch(provider_id):
        errors.append("provider_id_invalid")
        provider_id = ""
    model_id = _string(
        getattr(settings, "AI_EXTERNAL_PROVIDER_MODEL", ""),
        "provider_model",
        errors,
    )
    secret_env_name = _string(
        getattr(settings, "AI_EXTERNAL_PROVIDER_SECRET_ENV", ""),
        "provider_secret_reference",
        errors,
    )
    if secret_env_name and not _SECRET_ENV_NAME.fullmatch(secret_env_name):
        errors.append("provider_secret_reference_invalid")
        secret_env_name = ""
    secret_present = bool(
        secret_env_name and str(environment.get(secret_env_name, "")).strip()
    )

    cache_alias = _string(
        getattr(settings, "AI_ASSISTANT_THROTTLE_CACHE_ALIAS", "default"),
        "throttle_cache_alias",
        errors,
        maximum=64,
    )
    requests = _positive_int(
        getattr(settings, "AI_ASSISTANT_RATE_LIMIT_REQUESTS", 10),
        "rate_limit_requests",
        errors,
        maximum=10_000,
    )
    window_seconds = _positive_int(
        getattr(settings, "AI_ASSISTANT_RATE_LIMIT_WINDOW_SECONDS", 60),
        "rate_limit_window_seconds",
        errors,
        maximum=86_400,
    )
    timeout_seconds = _timeout(
        getattr(settings, "AI_EXTERNAL_PROVIDER_TIMEOUT_SECONDS", 10),
        errors,
    )
    max_output_tokens = _positive_int(
        getattr(settings, "AI_EXTERNAL_PROVIDER_MAX_OUTPUT_TOKENS", 3000),
        "provider_max_output_tokens",
        errors,
        maximum=4096,
    )
    reasoning_effort = _string(
        getattr(settings, "AI_EXTERNAL_PROVIDER_REASONING_EFFORT", ""),
        "provider_reasoning_effort",
        errors,
        maximum=16,
    )
    if reasoning_effort and reasoning_effort not in {
        "none",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
    }:
        errors.append("provider_reasoning_effort_invalid")
        reasoning_effort = ""

    privacy = ProviderPrivacyConfiguration(
        approved=_strict_bool(
            getattr(settings, "AI_EXTERNAL_PROVIDER_PRIVACY_APPROVED", False),
            "privacy_approved",
            errors,
        ),
        disclosure_policy_version=_string(
            getattr(settings, "AI_EXTERNAL_DISCLOSURE_POLICY_VERSION", ""),
            "disclosure_policy_version",
            errors,
        ),
        training_opt_out_confirmed=_strict_bool(
            getattr(
                settings,
                "AI_EXTERNAL_PROVIDER_TRAINING_OPT_OUT_CONFIRMED",
                False,
            ),
            "training_opt_out_confirmed",
            errors,
        ),
        retention_policy=_string(
            getattr(settings, "AI_EXTERNAL_PROVIDER_RETENTION_POLICY", ""),
            "retention_policy",
            errors,
        ),
        data_residency_policy=_string(
            getattr(settings, "AI_EXTERNAL_PROVIDER_DATA_RESIDENCY_POLICY", ""),
            "data_residency_policy",
            errors,
        ),
        deletion_policy=_string(
            getattr(settings, "AI_EXTERNAL_PROVIDER_DELETION_POLICY", ""),
            "deletion_policy",
            errors,
        ),
        incident_policy=_string(
            getattr(settings, "AI_EXTERNAL_PROVIDER_INCIDENT_POLICY", ""),
            "incident_policy",
            errors,
        ),
        user_disclosure_version=_string(
            getattr(settings, "AI_EXTERNAL_PROVIDER_USER_DISCLOSURE_VERSION", ""),
            "user_disclosure_version",
            errors,
        ),
        knowledge_external_approved=_strict_bool(
            getattr(settings, "AI_ASSISTANT_KNOWLEDGE_EXTERNAL_APPROVED", False),
            "knowledge_external_approved",
            errors,
        ),
    )

    return ExternalProviderConfiguration(
        enabled=enabled,
        provider_id=provider_id,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
        secret_env_name=secret_env_name,
        secret_present=secret_present,
        throttle_cache_alias=cache_alias,
        rate_limit_requests=requests,
        rate_limit_window_seconds=window_seconds,
        privacy=privacy,
        errors=tuple(sorted(set(errors))),
    )


def is_supported_external_provider(provider_id: str) -> bool:
    """Session 5 permits only provider IDs already in the explicit registry."""
    return provider_id in SUPPORTED_ASSISTANT_PROVIDERS


__all__ = [
    "EXTERNAL_DISCLOSURE_POLICY_VERSION",
    "ExternalProviderConfiguration",
    "ProviderPrivacyConfiguration",
    "is_supported_external_provider",
    "load_external_provider_configuration",
]
