"""Application-owned, fail-closed throttling for external AI calls."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re
import threading
import time
from typing import Callable, Protocol
from uuid import uuid4

from django.conf import settings
from django.core.cache import caches


THROTTLE_ALLOWED = "allowed"
THROTTLE_RATE_LIMITED = "rate_limited"
THROTTLE_UNAVAILABLE = "throttle_unavailable"

CACHE_PROBE_READY = "ready"
CACHE_PROBE_UNSAFE_BACKEND = "unsafe_backend"
CACHE_PROBE_UNAVAILABLE = "unavailable"
CACHE_PROBE_INVALID_SEMANTICS = "invalid_semantics"

_OPAQUE_USER_KEY = re.compile(r"[0-9a-f]{64}\Z")
_CAPABILITY = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")

# These Django backends provide a deployment-shared cache and atomic add/incr
# primitives when their corresponding service and client dependency are
# configured.  LocMemCache and file/database caches are deliberately absent.
SHARED_ATOMIC_CACHE_BACKENDS = frozenset(
    {
        "django.core.cache.backends.redis.RedisCache",
        "django.core.cache.backends.memcached.PyLibMCCache",
        "django.core.cache.backends.memcached.PyMemcacheCache",
        "django_redis.cache.RedisCache",
    }
)

_DJANGO_REDIS_BACKEND = "django.core.cache.backends.redis.RedisCache"

# Django's RedisCache.add() uses SET NX EX and is atomic. Its incr() performs
# an existence check before INCR, which leaves a narrow expiry race where Redis
# could recreate a missing key without a TTL. Keep the existing add/increment
# contract, but make the Redis existing-key increment one atomic server-side
# operation that preserves the original fixed-window expiry.
_REDIS_INCREMENT_EXISTING_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if current == false then
    return false
end
local count = redis.call('INCRBY', KEYS[1], 1)
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


@dataclass(frozen=True)
class ThrottleDecision:
    outcome: str
    retry_after_seconds: int | None = None

    @property
    def allowed(self) -> bool:
        return self.outcome == THROTTLE_ALLOWED


@dataclass(frozen=True)
class CacheBackendProbe:
    ready: bool
    outcome: str
    counter_value: int | None = None
    ttl_seconds: int | None = None


class AtomicCounterBackend(Protocol):
    """Minimum backend contract required by the fixed-window throttle."""

    @property
    def is_deployment_shared(self) -> bool: ...

    def increment(self, key: str, *, ttl_seconds: int) -> int: ...


class DjangoCacheAtomicCounterBackend:
    """Use one configured Django cache alias through atomic add/incr calls."""

    def __init__(self, alias: str = "default"):
        self.alias = alias

    @property
    def _configured_backend(self) -> str:
        cache_config = getattr(settings, "CACHES", {}).get(self.alias, {})
        return cache_config.get("BACKEND", "")

    @property
    def is_deployment_shared(self) -> bool:
        if self._configured_backend not in SHARED_ATOMIC_CACHE_BACKENDS:
            return False
        try:
            caches[self.alias]
        except Exception:
            return False
        return True

    @staticmethod
    def _redis_client_and_key(cache, key: str):
        backend_key = cache.make_key(key)
        client = cache._cache.get_client(backend_key, write=True)
        return client, backend_key

    def _increment_existing_redis(self, cache, key: str) -> int:
        client, backend_key = self._redis_client_and_key(cache, key)
        result = client.eval(
            _REDIS_INCREMENT_EXISTING_SCRIPT,
            1,
            backend_key,
        )
        if not isinstance(result, (list, tuple)) or len(result) != 2:
            raise ValueError("Assistant throttle key expired during increment.")
        count, ttl_seconds = result
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count <= 0
            or isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, int)
            or ttl_seconds < 0
        ):
            raise ValueError("Assistant throttle Redis state is invalid.")
        return count

    def _redis_ttl(self, cache, key: str) -> int:
        client, backend_key = self._redis_client_and_key(cache, key)
        ttl_seconds = client.ttl(backend_key)
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
            raise ValueError("Assistant throttle Redis TTL is invalid.")
        return ttl_seconds

    def increment(self, key: str, *, ttl_seconds: int) -> int:
        cache = caches[self.alias]
        if cache.add(key, 1, timeout=ttl_seconds):
            return 1
        if self._configured_backend == _DJANGO_REDIS_BACKEND:
            return self._increment_existing_redis(cache, key)

        # Reviewed Memcached/django-redis backends provide atomic increment.
        # Reassert the bounded remaining-window TTL and fail closed if the key
        # disappeared rather than silently recreating state.
        count = cache.incr(key)
        if not cache.touch(key, timeout=ttl_seconds):
            raise ValueError("Assistant throttle key expired during increment.")
        return count

    def probe(self, *, ttl_seconds: int = 5) -> CacheBackendProbe:
        """Exercise the configured backend without exposing connection data."""
        if not self.is_deployment_shared:
            return CacheBackendProbe(False, CACHE_PROBE_UNSAFE_BACKEND)
        key = f"kollipack:assistant:readiness:v1:{uuid4().hex}"
        cache = None
        try:
            cache = caches[self.alias]
            first = self.increment(key, ttl_seconds=ttl_seconds)
            second = self.increment(key, ttl_seconds=ttl_seconds)
            visible = cache.get(key)
            if (first, second, visible) != (1, 2, 2):
                return CacheBackendProbe(
                    False,
                    CACHE_PROBE_INVALID_SEMANTICS,
                )

            observed_ttl = None
            if self._configured_backend == _DJANGO_REDIS_BACKEND:
                observed_ttl = self._redis_ttl(cache, key)
                if observed_ttl < 0 or observed_ttl > ttl_seconds:
                    return CacheBackendProbe(
                        False,
                        CACHE_PROBE_INVALID_SEMANTICS,
                        counter_value=visible,
                        ttl_seconds=observed_ttl,
                    )
            return CacheBackendProbe(
                True,
                CACHE_PROBE_READY,
                counter_value=visible,
                ttl_seconds=observed_ttl,
            )
        except Exception:
            return CacheBackendProbe(False, CACHE_PROBE_UNAVAILABLE)
        finally:
            if cache is not None:
                try:
                    cache.delete(key)
                except Exception:
                    pass


class DeterministicAtomicCounterBackend:
    """Thread-safe deterministic backend for unit tests and local simulation.

    It is process-local and therefore not deployment-safe by default.  Tests
    may mark one shared instance as deployment_shared to simulate multiple
    application workers using the same atomic store.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.time,
        deployment_shared: bool = False,
    ):
        self._clock = clock
        self._deployment_shared = deployment_shared
        self._values: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()
        self.last_ttl_seconds: int | None = None

    @property
    def is_deployment_shared(self) -> bool:
        return self._deployment_shared

    def increment(self, key: str, *, ttl_seconds: int) -> int:
        now = float(self._clock())
        with self._lock:
            current = self._values.get(key)
            if current is None or current[1] <= now:
                count = 1
            else:
                count = current[0] + 1
            self._values[key] = (count, now + ttl_seconds)
            self.last_ttl_seconds = ttl_seconds
            return count


def derive_opaque_user_key(user_identifier: object) -> str:
    """HMAC a stable server-side user identifier for cache-key isolation."""
    if isinstance(user_identifier, bool) or user_identifier is None:
        raise ValueError("A stable authenticated-user identifier is required.")
    identifier = str(user_identifier).strip()
    if not identifier or len(identifier) > 128:
        raise ValueError("A stable authenticated-user identifier is required.")
    secret = str(settings.SECRET_KEY).encode("utf-8")
    payload = f"kollipack-assistant-user-v1:{identifier}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


class AssistantThrottle:
    """Simple per-user fixed-window throttle with bounded cache-key lifetime."""

    def __init__(
        self,
        *,
        requests: int,
        window_seconds: int,
        backend: AtomicCounterBackend,
        clock: Callable[[], float] = time.time,
    ):
        if isinstance(requests, bool) or not isinstance(requests, int) or requests <= 0:
            raise ValueError("Throttle request limit must be a positive integer.")
        if (
            isinstance(window_seconds, bool)
            or not isinstance(window_seconds, int)
            or window_seconds <= 0
        ):
            raise ValueError("Throttle window must be a positive integer.")
        self.requests = requests
        self.window_seconds = window_seconds
        self.backend = backend
        self._clock = clock

    @property
    def is_deployment_safe(self) -> bool:
        try:
            return self.backend.is_deployment_shared is True
        except Exception:
            return False

    def probe_backend(self) -> CacheBackendProbe:
        if not self.is_deployment_safe:
            return CacheBackendProbe(False, CACHE_PROBE_UNSAFE_BACKEND)
        probe = getattr(self.backend, "probe", None)
        if probe is None:
            # Deterministic/test backends prove their semantics in focused
            # tests; deployment backends provide the live probe above.
            return CacheBackendProbe(True, CACHE_PROBE_READY)
        try:
            result = probe()
        except Exception:
            return CacheBackendProbe(False, CACHE_PROBE_UNAVAILABLE)
        if not isinstance(result, CacheBackendProbe):
            return CacheBackendProbe(False, CACHE_PROBE_INVALID_SEMANTICS)
        return result

    def check_and_consume(
        self,
        *,
        user_key: str,
        capability: str,
    ) -> ThrottleDecision:
        if not self.is_deployment_safe:
            return ThrottleDecision(THROTTLE_UNAVAILABLE)
        if not isinstance(user_key, str) or not _OPAQUE_USER_KEY.fullmatch(user_key):
            return ThrottleDecision(THROTTLE_UNAVAILABLE)
        if not isinstance(capability, str) or not _CAPABILITY.fullmatch(capability):
            return ThrottleDecision(THROTTLE_UNAVAILABLE)

        try:
            current_second = int(self._clock())
            if current_second < 0:
                raise ValueError("Clock must not be negative.")
            window = current_second // self.window_seconds
            elapsed = current_second % self.window_seconds
            retry_after = self.window_seconds - elapsed
            key = (
                "kollipack:assistant:rate:v1:"
                f"{capability}:{user_key}:{window}"
            )
            count = self.backend.increment(key, ttl_seconds=retry_after)
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                raise ValueError("Throttle backend returned malformed state.")
        except Exception:
            return ThrottleDecision(THROTTLE_UNAVAILABLE)

        if count > self.requests:
            return ThrottleDecision(
                THROTTLE_RATE_LIMITED,
                retry_after_seconds=retry_after,
            )
        return ThrottleDecision(THROTTLE_ALLOWED)


__all__ = [
    "AssistantThrottle",
    "AtomicCounterBackend",
    "CACHE_PROBE_INVALID_SEMANTICS",
    "CACHE_PROBE_READY",
    "CACHE_PROBE_UNAVAILABLE",
    "CACHE_PROBE_UNSAFE_BACKEND",
    "CacheBackendProbe",
    "DeterministicAtomicCounterBackend",
    "DjangoCacheAtomicCounterBackend",
    "THROTTLE_ALLOWED",
    "THROTTLE_RATE_LIMITED",
    "THROTTLE_UNAVAILABLE",
    "ThrottleDecision",
    "derive_opaque_user_key",
]
