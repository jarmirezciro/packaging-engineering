"""Opt-in tests against the same Redis backend used by deployment.

Set KOLLIPACK_TEST_REDIS_URL to run this module locally or in integration CI.
Standard unit CI does not require an external cache service.
"""

from concurrent.futures import ThreadPoolExecutor
import os
import time
from unittest import skipUnless
from uuid import uuid4

from django.core.cache import caches
from django.test import SimpleTestCase, override_settings

from packagingapp.assistant.throttle import (
    AssistantThrottle,
    CACHE_PROBE_READY,
    DjangoCacheAtomicCounterBackend,
    THROTTLE_ALLOWED,
    THROTTLE_RATE_LIMITED,
    derive_opaque_user_key,
)


TEST_REDIS_URL = os.environ.get("KOLLIPACK_TEST_REDIS_URL", "").strip()
TEST_CACHES = {
    "assistant": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": TEST_REDIS_URL or "redis://127.0.0.1:6379/15",
        "KEY_PREFIX": "kollipack-assistant-integration-test",
        "OPTIONS": {
            "socket_connect_timeout": 1,
            "socket_timeout": 1,
        },
    }
}


@skipUnless(TEST_REDIS_URL, "KOLLIPACK_TEST_REDIS_URL is not configured")
@override_settings(CACHES=TEST_CACHES)
class AssistantRedisIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.backend = DjangoCacheAtomicCounterBackend("assistant")

    def test_live_probe_and_fixed_window_rate_limit(self):
        probe = self.backend.probe()
        self.assertTrue(probe.ready)
        self.assertEqual(probe.outcome, CACHE_PROBE_READY)

        throttle = AssistantThrottle(
            requests=3,
            window_seconds=60,
            backend=self.backend,
        )
        user_key = derive_opaque_user_key(f"integration-{uuid4().hex}")
        outcomes = [
            throttle.check_and_consume(
                user_key=user_key,
                capability="read_only",
            ).outcome
            for _ in range(4)
        ]
        self.assertEqual(
            outcomes,
            [
                THROTTLE_ALLOWED,
                THROTTLE_ALLOWED,
                THROTTLE_ALLOWED,
                THROTTLE_RATE_LIMITED,
            ],
        )

    def test_counter_expires_and_starts_fresh(self):
        key = f"kollipack:assistant:test:expiry:v1:{uuid4().hex}"
        try:
            self.assertEqual(self.backend.increment(key, ttl_seconds=1), 1)
            self.assertEqual(self.backend.increment(key, ttl_seconds=1), 2)
            time.sleep(1.2)
            self.assertIsNone(caches["assistant"].get(key))
            self.assertEqual(self.backend.increment(key, ttl_seconds=1), 1)
        finally:
            caches["assistant"].delete(key)

    def test_concurrent_clients_do_not_lose_increments(self):
        key = f"kollipack:assistant:test:atomic:v1:{uuid4().hex}"
        increment_count = 40

        def increment(_index):
            backend = DjangoCacheAtomicCounterBackend("assistant")
            return backend.increment(key, ttl_seconds=10)

        try:
            with ThreadPoolExecutor(max_workers=12) as pool:
                counts = list(pool.map(increment, range(increment_count)))
            self.assertEqual(sorted(counts), list(range(1, increment_count + 1)))
            self.assertEqual(caches["assistant"].get(key), increment_count)
        finally:
            caches["assistant"].delete(key)

    @override_settings(
        CACHES={
            "assistant": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": "redis://127.0.0.1:1/0",
                "OPTIONS": {
                    "socket_connect_timeout": 0.1,
                    "socket_timeout": 0.1,
                },
            }
        }
    )
    def test_connection_refused_fails_probe(self):
        result = DjangoCacheAtomicCounterBackend("assistant").probe()
        self.assertFalse(result.ready)
