from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from packagingapp.assistant.throttle import (
    CACHE_PROBE_INVALID_SEMANTICS,
    CACHE_PROBE_READY,
    CACHE_PROBE_UNAVAILABLE,
    CACHE_PROBE_UNSAFE_BACKEND,
    DjangoCacheAtomicCounterBackend,
)


REDIS_CACHES = {
    "assistant": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://example.invalid:6379/0",
    }
}


class _FakeRedisClient:
    def __init__(self, cache):
        self.cache = cache
        self.eval_result = "normal"

    def eval(self, script, key_count, backend_key):
        self.cache.last_script = script
        if self.eval_result == "missing":
            return None
        if self.eval_result == "malformed":
            return ["bad", -1]
        count, ttl = self.cache.values[backend_key]
        count += 1
        self.cache.values[backend_key] = (count, ttl)
        return [count, ttl]

    def ttl(self, backend_key):
        return self.cache.values.get(backend_key, (None, -2))[1]


class _FakeRedisCacheClient:
    def __init__(self, cache):
        self.client = _FakeRedisClient(cache)

    def get_client(self, backend_key, write=False):
        return self.client


class _FakeRedisCache:
    def __init__(self):
        self.values = {}
        self._cache = _FakeRedisCacheClient(self)
        self.last_script = ""
        self.raise_connection = False

    @staticmethod
    def make_key(key):
        return f":1:{key}"

    def add(self, key, value, timeout):
        if self.raise_connection:
            raise ConnectionError("secret connection detail")
        backend_key = self.make_key(key)
        if backend_key in self.values:
            return False
        self.values[backend_key] = (value, timeout)
        return True

    def get(self, key, default=None):
        value = self.values.get(self.make_key(key))
        return default if value is None else value[0]

    def delete(self, key):
        return self.values.pop(self.make_key(key), None) is not None


@override_settings(CACHES=REDIS_CACHES)
class DjangoRedisAssistantCacheTests(SimpleTestCase):
    def setUp(self):
        self.cache = _FakeRedisCache()
        self.caches_patch = patch(
            "packagingapp.assistant.throttle.caches",
            {"assistant": self.cache},
        )
        self.caches_patch.start()
        self.addCleanup(self.caches_patch.stop)
        self.backend = DjangoCacheAtomicCounterBackend("assistant")

    def test_atomic_add_then_existing_key_increment_preserves_ttl(self):
        self.assertEqual(self.backend.increment("quota", ttl_seconds=9), 1)
        self.assertEqual(self.backend.increment("quota", ttl_seconds=9), 2)
        self.assertEqual(self.cache.get("quota"), 2)
        self.assertEqual(self.cache.values[":1:quota"][1], 9)
        self.assertIn("INCRBY", self.cache.last_script)
        self.assertIn("TTL", self.cache.last_script)

    def test_missing_or_malformed_existing_state_fails_closed(self):
        self.cache.values[":1:quota"] = (1, 9)
        client = self.cache._cache.client
        for result in ("missing", "malformed"):
            with self.subTest(result=result):
                client.eval_result = result
                with self.assertRaises(ValueError):
                    self.backend.increment("quota", ttl_seconds=9)

    def test_probe_verifies_add_increment_visibility_and_ttl(self):
        result = self.backend.probe(ttl_seconds=5)
        self.assertTrue(result.ready)
        self.assertEqual(result.outcome, CACHE_PROBE_READY)
        self.assertEqual(result.counter_value, 2)
        self.assertEqual(result.ttl_seconds, 5)
        self.assertEqual(self.cache.values, {})

    def test_probe_rejects_invalid_ttl_and_backend_outage(self):
        original_ttl = self.cache._cache.client.ttl
        self.cache._cache.client.ttl = lambda _key: -1
        invalid = self.backend.probe(ttl_seconds=5)
        self.assertFalse(invalid.ready)
        self.assertEqual(invalid.outcome, CACHE_PROBE_INVALID_SEMANTICS)

        self.cache._cache.client.ttl = original_ttl
        self.cache.raise_connection = True
        unavailable = self.backend.probe(ttl_seconds=5)
        self.assertFalse(unavailable.ready)
        self.assertEqual(unavailable.outcome, CACHE_PROBE_UNAVAILABLE)


class AssistantCacheSafetyTests(SimpleTestCase):
    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        }
    )
    def test_unknown_alias_and_process_local_cache_are_unsafe(self):
        unknown = DjangoCacheAtomicCounterBackend("assistant").probe()
        local = DjangoCacheAtomicCounterBackend("default").probe()
        self.assertEqual(unknown.outcome, CACHE_PROBE_UNSAFE_BACKEND)
        self.assertEqual(local.outcome, CACHE_PROBE_UNSAFE_BACKEND)
