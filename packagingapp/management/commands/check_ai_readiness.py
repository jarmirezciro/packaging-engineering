"""Safely inspect external-assistant deployment readiness."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import time
from uuid import uuid4

from django.conf import settings
from django.core.cache import caches
from django.core.management.base import BaseCommand, CommandError

from packagingapp.assistant.configuration import (
    load_external_provider_configuration,
)
from packagingapp.assistant.policy import evaluate_external_provider_readiness
from packagingapp.assistant.throttle import (
    AssistantThrottle,
    DjangoCacheAtomicCounterBackend,
)


class Command(BaseCommand):
    help = (
        "Check the deployment-shared assistant cache and external-provider "
        "readiness without exposing credentials or making an LLM request."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--smoke",
            action="store_true",
            help="Also verify expiration and concurrent cross-client increments.",
        )
        parser.add_argument(
            "--require-cache",
            action="store_true",
            help="Exit non-zero unless the shared cache probe passes.",
        )

    def handle(self, *args, **options):
        config = load_external_provider_configuration()
        backend = DjangoCacheAtomicCounterBackend(config.throttle_cache_alias)
        configured_backend = (
            getattr(settings, "CACHES", {})
            .get(config.throttle_cache_alias, {})
            .get("BACKEND", "not_configured")
        )

        try:
            throttle = AssistantThrottle(
                requests=config.rate_limit_requests,
                window_seconds=config.rate_limit_window_seconds,
                backend=backend,
            )
            probe = throttle.probe_backend()
        except (TypeError, ValueError):
            probe = None

        self.stdout.write(
            f"external_ai_enabled={'yes' if config.enabled else 'no'}"
        )
        self.stdout.write(
            f"assistant_cache_alias={config.throttle_cache_alias or 'invalid'}"
        )
        self.stdout.write(f"assistant_cache_backend={configured_backend}")
        self.stdout.write(
            "assistant_cache_probe="
            + (probe.outcome if probe is not None else "invalid_configuration")
        )
        if probe is not None and probe.ready:
            self.stdout.write("assistant_cache_atomic_add_incr=pass")
            self.stdout.write("assistant_cache_bounded_ttl=pass")

        readiness = evaluate_external_provider_readiness(config=config)
        self.stdout.write(f"external_provider_readiness={readiness.outcome}")

        smoke_ok = True
        if options["smoke"] and probe is not None and probe.ready:
            expiry_ok = self._verify_expiry(backend)
            concurrency_ok = self._verify_concurrency(
                alias=config.throttle_cache_alias,
            )
            self.stdout.write(
                f"assistant_cache_expiration={'pass' if expiry_ok else 'fail'}"
            )
            self.stdout.write(
                "assistant_cache_cross_client_atomicity="
                + ("pass" if concurrency_ok else "fail")
            )
            smoke_ok = expiry_ok and concurrency_ok

        cache_ready = bool(probe is not None and probe.ready and smoke_ok)
        if options["require_cache"] and not cache_ready:
            raise CommandError("Assistant shared-cache readiness check failed.")

    @staticmethod
    def _verify_expiry(backend) -> bool:
        key = f"kollipack:assistant:smoke:expiry:v1:{uuid4().hex}"
        try:
            if backend.increment(key, ttl_seconds=1) != 1:
                return False
            time.sleep(1.2)
            return caches[backend.alias].get(key) is None
        except Exception:
            return False
        finally:
            try:
                caches[backend.alias].delete(key)
            except Exception:
                pass

    @staticmethod
    def _verify_concurrency(*, alias: str, workers: int = 12) -> bool:
        key = f"kollipack:assistant:smoke:concurrency:v1:{uuid4().hex}"

        def increment(_index):
            worker_backend = DjangoCacheAtomicCounterBackend(alias)
            return worker_backend.increment(key, ttl_seconds=10)

        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                counts = list(pool.map(increment, range(workers)))
            return sorted(counts) == list(range(1, workers + 1)) and (
                caches[alias].get(key) == workers
            )
        except Exception:
            return False
        finally:
            try:
                caches[alias].delete(key)
            except Exception:
                pass
