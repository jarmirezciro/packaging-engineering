"""Explicit local-only real-provider evaluation for the Public Expert."""

from __future__ import annotations

import json
import os
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError

from packagingapp.assistant.public_contracts import build_public_expert_context
from packagingapp.assistant.public_evaluation import PUBLIC_EXPERT_EVALUATION_CASES
from packagingapp.assistant.public_knowledge import (
    public_knowledge_trace,
    retrieve_public_knowledge_context,
)
from packagingapp.assistant.public_policy import (
    build_public_external_request,
    build_public_throttle,
    evaluate_public_provider_gate,
    load_public_expert_configuration,
)
from packagingapp.assistant.public_service import ask_public_external
from packagingapp.assistant.providers import get_assistant_provider


class Command(BaseCommand):
    help = (
        "Run the bounded Public Expert evaluation through its public policy, "
        "shared-cache throttle, OpenAI transport, and response validation path."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--case",
            action="append",
            dest="case_names",
            help="Run only a named case; may be repeated.",
        )

    def handle(self, *args, **options):
        if os.environ.get("KOLLIPACK_OPENAI_LOCAL_SMOKE", "").strip() != "1":
            raise CommandError(
                "This local command requires KOLLIPACK_OPENAI_LOCAL_SMOKE=1. "
                "No provider request was made."
            )
        config = load_public_expert_configuration()
        cases = PUBLIC_EXPERT_EVALUATION_CASES
        if options["case_names"]:
            requested = set(options["case_names"])
            cases = tuple(case for case in cases if case.name in requested)
            missing = requested - {case.name for case in cases}
            if missing:
                raise CommandError("Unknown evaluation case(s): " + ", ".join(sorted(missing)))
        if not cases:
            raise CommandError("No Public Expert evaluation cases were selected.")
        if config.session_rate_limit_requests < len(cases):
            raise CommandError(
                "AI_PUBLIC_EXPERT_SESSION_RATE_LIMIT_REQUESTS must be at least "
                f"{len(cases)} for this evaluation. No provider request was made."
            )
        # Readiness consumes one global quota unit before the case loop. Keep
        # that check inside the real public gate instead of bypassing it.
        required_global_requests = len(cases) + 1
        if config.global_rate_limit_requests < required_global_requests:
            raise CommandError(
                "AI_PUBLIC_EXPERT_GLOBAL_RATE_LIMIT_REQUESTS must be at least "
                f"{required_global_requests} for this evaluation plus readiness. "
                "No provider request was made."
            )

        throttle = build_public_throttle(config)
        session_key = f"local-public-evaluation-{uuid4().hex}"
        first = cases[0]
        preflight = evaluate_public_provider_gate(
            session_key=session_key,
            request=build_public_external_request(
                message=first.question,
                expert_context=build_public_expert_context(first.knowledge_scope),
                knowledge_context=retrieve_public_knowledge_context(
                    first.question,
                    knowledge_scope=first.knowledge_scope,
                ),
            ),
            config=config,
            throttle=throttle,
        )
        if not preflight.allowed:
            raise CommandError(
                f"Public Expert readiness is not ready: {preflight.outcome}. "
                "No provider evaluation was run."
            )
        provider = get_assistant_provider(preflight.provider_id)
        # The preflight consumed one quota unit; use the same first case as the
        # first evaluation request only after documenting that bound explicitly.
        # A fresh opaque session avoids double-charging the actual evaluation.
        session_key = f"local-public-evaluation-{uuid4().hex}"

        unavailable = 0
        response_types: dict[str, int] = {}
        for case in cases:
            knowledge = retrieve_public_knowledge_context(
                case.question,
                knowledge_scope=case.knowledge_scope,
            )
            response = ask_public_external(
                session_key=session_key,
                message=case.question,
                expert_context=build_public_expert_context(case.knowledge_scope),
                knowledge_context=knowledge,
                provider=provider,
                config=config,
                throttle=throttle,
            )
            response_types[response["type"]] = response_types.get(response["type"], 0) + 1
            unavailable += int(response["type"] == "unavailable")
            self.stdout.write(f"case={case.name}")
            self.stdout.write(f"category={case.category}")
            self.stdout.write(f"scope={case.knowledge_scope}")
            self.stdout.write(
                "knowledge_refs="
                + json.dumps(
                    [item["ref"] for item in public_knowledge_trace(knowledge)],
                    ensure_ascii=True,
                )
            )
            self.stdout.write(f"response_type={response['type']}")
            self.stdout.write("message=" + json.dumps(response["message"], ensure_ascii=True))

        self.stdout.write(f"provider={preflight.provider_id}")
        self.stdout.write(f"model={preflight.model_id}")
        self.stdout.write(f"cases={len(cases)}")
        self.stdout.write("response_types=" + json.dumps(response_types, sort_keys=True))
        if unavailable:
            raise CommandError(f"{unavailable} case(s) returned the safe unavailable outcome.")
