from dataclasses import dataclass

from django.test import SimpleTestCase, override_settings

from packagingapp.assistant.throttle import (
    AssistantThrottle,
    DeterministicAtomicCounterBackend,
    DjangoCacheAtomicCounterBackend,
    THROTTLE_ALLOWED,
    THROTTLE_RATE_LIMITED,
    THROTTLE_UNAVAILABLE,
    derive_opaque_user_key,
)


@dataclass
class MutableClock:
    value: float = 0.0

    def __call__(self):
        return self.value


class AssistantThrottleTests(SimpleTestCase):
    def build_throttle(self, *, requests=3, window_seconds=60, clock=None, backend=None):
        clock = clock or MutableClock()
        backend = backend or DeterministicAtomicCounterBackend(
            clock=clock,
            deployment_shared=True,
        )
        return AssistantThrottle(
            requests=requests,
            window_seconds=window_seconds,
            backend=backend,
            clock=clock,
        ), backend, clock

    def test_first_and_within_limit_requests_are_allowed_then_rejected(self):
        throttle, _backend, _clock = self.build_throttle(requests=3)
        user_key = derive_opaque_user_key(101)

        outcomes = [
            throttle.check_and_consume(user_key=user_key, capability="read_only")
            for _ in range(4)
        ]

        self.assertEqual(
            [decision.outcome for decision in outcomes],
            [
                THROTTLE_ALLOWED,
                THROTTLE_ALLOWED,
                THROTTLE_ALLOWED,
                THROTTLE_RATE_LIMITED,
            ],
        )
        self.assertEqual(outcomes[-1].retry_after_seconds, 60)

    def test_new_window_is_allowed_and_ttl_is_bounded(self):
        clock = MutableClock(59)
        throttle, backend, _clock = self.build_throttle(
            requests=1,
            window_seconds=60,
            clock=clock,
        )
        user_key = derive_opaque_user_key(102)

        first = throttle.check_and_consume(
            user_key=user_key,
            capability="read_only",
        )
        self.assertEqual(first.outcome, THROTTLE_ALLOWED)
        self.assertEqual(backend.last_ttl_seconds, 1)

        clock.value = 60
        next_window = throttle.check_and_consume(
            user_key=user_key,
            capability="read_only",
        )
        self.assertEqual(next_window.outcome, THROTTLE_ALLOWED)
        self.assertEqual(backend.last_ttl_seconds, 60)
        self.assertLessEqual(backend.last_ttl_seconds, throttle.window_seconds)

    def test_different_authenticated_users_have_independent_limits(self):
        throttle, _backend, _clock = self.build_throttle(requests=1)
        first_user = derive_opaque_user_key(201)
        second_user = derive_opaque_user_key(202)

        self.assertEqual(
            throttle.check_and_consume(
                user_key=first_user,
                capability="read_only",
            ).outcome,
            THROTTLE_ALLOWED,
        )
        self.assertEqual(
            throttle.check_and_consume(
                user_key=first_user,
                capability="read_only",
            ).outcome,
            THROTTLE_RATE_LIMITED,
        )
        self.assertEqual(
            throttle.check_and_consume(
                user_key=second_user,
                capability="read_only",
            ).outcome,
            THROTTLE_ALLOWED,
        )

    def test_two_worker_clients_share_one_atomic_backend_state(self):
        clock = MutableClock()
        shared_backend = DeterministicAtomicCounterBackend(
            clock=clock,
            deployment_shared=True,
        )
        worker_one, _backend, _clock = self.build_throttle(
            requests=2,
            clock=clock,
            backend=shared_backend,
        )
        worker_two, _backend, _clock = self.build_throttle(
            requests=2,
            clock=clock,
            backend=shared_backend,
        )
        user_key = derive_opaque_user_key(301)

        self.assertEqual(
            worker_one.check_and_consume(
                user_key=user_key,
                capability="read_only",
            ).outcome,
            THROTTLE_ALLOWED,
        )
        self.assertEqual(
            worker_two.check_and_consume(
                user_key=user_key,
                capability="read_only",
            ).outcome,
            THROTTLE_ALLOWED,
        )
        self.assertEqual(
            worker_one.check_and_consume(
                user_key=user_key,
                capability="read_only",
            ).outcome,
            THROTTLE_RATE_LIMITED,
        )

    def test_backend_failure_and_malformed_state_fail_closed(self):
        class FailingBackend:
            is_deployment_shared = True

            def increment(self, key, *, ttl_seconds):
                raise RuntimeError("private backend detail")

        class MalformedBackend:
            is_deployment_shared = True

            def increment(self, key, *, ttl_seconds):
                return "not-an-integer"

        user_key = derive_opaque_user_key(401)
        for backend in (FailingBackend(), MalformedBackend()):
            with self.subTest(backend=type(backend).__name__):
                throttle, _backend, _clock = self.build_throttle(backend=backend)
                decision = throttle.check_and_consume(
                    user_key=user_key,
                    capability="read_only",
                )
                self.assertEqual(decision.outcome, THROTTLE_UNAVAILABLE)
                self.assertIsNone(decision.retry_after_seconds)

    def test_process_local_backend_is_never_deployment_safe(self):
        clock = MutableClock()
        backend = DeterministicAtomicCounterBackend(clock=clock)
        throttle, _backend, _clock = self.build_throttle(
            clock=clock,
            backend=backend,
        )
        decision = throttle.check_and_consume(
            user_key=derive_opaque_user_key(501),
            capability="read_only",
        )
        self.assertFalse(throttle.is_deployment_safe)
        self.assertEqual(decision.outcome, THROTTLE_UNAVAILABLE)

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        }
    )
    def test_django_local_memory_cache_is_not_marked_shared(self):
        self.assertFalse(DjangoCacheAtomicCounterBackend().is_deployment_shared)

    def test_cache_keys_use_opaque_user_identity(self):
        raw_user_id = "private-user-identifier-8675309"
        throttle, backend, _clock = self.build_throttle()
        opaque_key = derive_opaque_user_key(raw_user_id)
        throttle.check_and_consume(user_key=opaque_key, capability="read_only")

        stored_keys = list(backend._values)
        self.assertEqual(len(stored_keys), 1)
        self.assertNotIn(raw_user_id, stored_keys[0])
        self.assertIn(opaque_key, stored_keys[0])
