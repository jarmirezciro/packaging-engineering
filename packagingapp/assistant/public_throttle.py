"""Per-session and global fail-closed throttling for the Public Expert."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import time
from typing import Callable

from django.conf import settings

from .public_contracts import PUBLIC_EXPERT_CAPABILITY
from .throttle import (
    AssistantThrottle,
    AtomicCounterBackend,
    CacheBackendProbe,
    THROTTLE_ALLOWED,
    THROTTLE_RATE_LIMITED,
    THROTTLE_UNAVAILABLE,
)


PUBLIC_THROTTLE_ALLOWED = "allowed"
PUBLIC_SESSION_RATE_LIMITED = "public_session_rate_limited"
PUBLIC_GLOBAL_RATE_LIMITED = "public_global_rate_limited"
PUBLIC_THROTTLE_UNAVAILABLE = "public_throttle_unavailable"


@dataclass(frozen=True)
class PublicThrottleDecision:
    outcome: str
    retry_after_seconds: int | None = None

    @property
    def allowed(self) -> bool:
        return self.outcome == PUBLIC_THROTTLE_ALLOWED


def _derive_opaque_key(value: str, *, purpose: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError("A bounded server-side throttle identifier is required.")
    secret = str(settings.SECRET_KEY).encode("utf-8")
    payload = f"kollipack-public-expert-{purpose}-v1:{value}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def derive_opaque_public_session_key(session_key: str) -> str:
    """Derive a cache-safe identity without storing or logging the raw session key."""
    return _derive_opaque_key(session_key, purpose="session")


def derive_opaque_public_global_key() -> str:
    return _derive_opaque_key("all-public-visitors", purpose="global")


class PublicExpertThrottle:
    """Require both a visitor quota and an application-wide circuit breaker."""

    def __init__(
        self,
        *,
        session_requests: int,
        session_window_seconds: int,
        global_requests: int,
        global_window_seconds: int,
        backend: AtomicCounterBackend,
        clock: Callable[[], float] = time.time,
    ):
        self.session = AssistantThrottle(
            requests=session_requests,
            window_seconds=session_window_seconds,
            backend=backend,
            clock=clock,
        )
        self.global_guard = AssistantThrottle(
            requests=global_requests,
            window_seconds=global_window_seconds,
            backend=backend,
            clock=clock,
        )

    @property
    def is_deployment_safe(self) -> bool:
        return self.session.is_deployment_safe and self.global_guard.is_deployment_safe

    def probe_backend(self) -> CacheBackendProbe:
        return self.session.probe_backend()

    def check_and_consume(self, *, session_key: str) -> PublicThrottleDecision:
        if not self.is_deployment_safe:
            return PublicThrottleDecision(PUBLIC_THROTTLE_UNAVAILABLE)
        try:
            opaque_session = derive_opaque_public_session_key(session_key)
            opaque_global = derive_opaque_public_global_key()
        except ValueError:
            return PublicThrottleDecision(PUBLIC_THROTTLE_UNAVAILABLE)

        session_decision = self.session.check_and_consume(
            user_key=opaque_session,
            capability=PUBLIC_EXPERT_CAPABILITY,
        )
        if session_decision.outcome == THROTTLE_RATE_LIMITED:
            return PublicThrottleDecision(
                PUBLIC_SESSION_RATE_LIMITED,
                session_decision.retry_after_seconds,
            )
        if session_decision.outcome != THROTTLE_ALLOWED:
            return PublicThrottleDecision(PUBLIC_THROTTLE_UNAVAILABLE)

        global_decision = self.global_guard.check_and_consume(
            user_key=opaque_global,
            capability=PUBLIC_EXPERT_CAPABILITY,
        )
        if global_decision.outcome == THROTTLE_RATE_LIMITED:
            return PublicThrottleDecision(
                PUBLIC_GLOBAL_RATE_LIMITED,
                global_decision.retry_after_seconds,
            )
        if global_decision.outcome == THROTTLE_UNAVAILABLE:
            return PublicThrottleDecision(PUBLIC_THROTTLE_UNAVAILABLE)
        return PublicThrottleDecision(PUBLIC_THROTTLE_ALLOWED)


__all__ = [
    "PUBLIC_GLOBAL_RATE_LIMITED",
    "PUBLIC_SESSION_RATE_LIMITED",
    "PUBLIC_THROTTLE_ALLOWED",
    "PUBLIC_THROTTLE_UNAVAILABLE",
    "PublicExpertThrottle",
    "PublicThrottleDecision",
    "derive_opaque_public_global_key",
    "derive_opaque_public_session_key",
]
