"""Explicit local-only OpenAI smoke and evaluation command."""

from __future__ import annotations

import json
import os
import tempfile
from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError

from packagingapp.assistant.configuration import (
    load_external_provider_configuration,
)
from packagingapp.assistant.evaluation import (
    build_container_evaluation_cases,
    build_input_action_evaluation_cases,
    build_knowledge_evaluation_cases,
    build_proposal_evaluation_cases,
    grounding_flags,
)
from packagingapp.assistant.actions import is_provider_proposal_candidate
from packagingapp.assistant.knowledge import retrieve_knowledge_context
from packagingapp.assistant.policy import evaluate_external_provider_readiness
from packagingapp.assistant.providers import get_assistant_provider
from packagingapp.assistant.service import ask_external
from packagingapp.forms import ContainerSelectionMode1Form
from packagingapp.tools.container.assistant_actions import (
    build_container_proposal_preview,
)


class Command(BaseCommand):
    help = (
        "Make an explicit local OpenAI Responses API call through KolliPack's "
        "normal policy, Redis throttle, provider, and response-validation path."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--evaluation",
            action="store_true",
            help="Run the complete first evaluation set instead of one smoke case.",
        )
        parser.add_argument(
            "--knowledge-evaluation",
            action="store_true",
            help="Run the 40-case Session 8.5B knowledge evaluation set.",
        )
        parser.add_argument(
            "--proposal-evaluation",
            action="store_true",
            help="Run the five-case Session 9 proposal-preview verification set.",
        )
        parser.add_argument(
            "--input-action-evaluation",
            action="store_true",
            help="Run the 20-case Session 10.5 realistic input-action suite.",
        )
        parser.add_argument(
            "--case",
            action="append",
            dest="case_names",
            help="Run only the named evaluation case; may be repeated.",
        )

    def handle(self, *args, **options):
        if os.environ.get("KOLLIPACK_OPENAI_LOCAL_SMOKE", "").strip() != "1":
            raise CommandError(
                "This local-development command requires "
                "KOLLIPACK_OPENAI_LOCAL_SMOKE=1. No provider request was made."
            )
        config = load_external_provider_configuration()
        readiness = evaluate_external_provider_readiness(config=config)
        if not readiness.ready:
            raise CommandError(
                "External assistant readiness is not ready: "
                f"{readiness.outcome}. No provider request was made."
            )
        if readiness.provider_id != "openai":
            raise CommandError(
                "The local smoke command requires AI_EXTERNAL_PROVIDER_ID=openai."
            )

        with tempfile.TemporaryDirectory(prefix="kollipack-openai-smoke-") as media_root:
            selected_suites = sum(
                bool(options[name])
                for name in (
                    "evaluation",
                    "knowledge_evaluation",
                    "proposal_evaluation",
                    "input_action_evaluation",
                )
            )
            if selected_suites > 1:
                raise CommandError(
                    "Choose only one evaluation suite."
                )
            if options["input_action_evaluation"]:
                cases = build_input_action_evaluation_cases(media_root=media_root)
            elif options["proposal_evaluation"]:
                cases = build_proposal_evaluation_cases()
            elif options["knowledge_evaluation"]:
                cases = build_knowledge_evaluation_cases(media_root=media_root)
            else:
                cases = build_container_evaluation_cases(media_root=media_root)
            if options["case_names"]:
                requested_names = set(options["case_names"])
                cases = tuple(case for case in cases if case.name in requested_names)
                found_names = {case.name for case in cases}
                missing_names = sorted(requested_names - found_names)
                if missing_names:
                    raise CommandError(
                        "Unknown evaluation case(s): " + ", ".join(missing_names)
                    )
            if not any(
                options[name]
                for name in (
                    "evaluation",
                    "knowledge_evaluation",
                    "proposal_evaluation",
                    "input_action_evaluation",
                )
            ):
                cases = tuple(case for case in cases if case.name == "complete_single")
            elif config.rate_limit_requests < len(cases):
                raise CommandError(
                    "The configured assistant rate limit is lower than the "
                    f"{len(cases)}-case evaluation set. No provider request was made."
                )

            self.stdout.write(
                "A real OpenAI API request will now be made through the normal "
                "KolliPack external-provider gate."
            )
            provider = get_assistant_provider(readiness.provider_id)
            local_user = SimpleNamespace(
                is_authenticated=True,
                is_staff=True,
                is_superuser=False,
                pk="local-openai-smoke",
            )
            failed = False
            for evaluation_case in cases:
                knowledge_context = retrieve_knowledge_context(
                    evaluation_case.question,
                    active_tool=evaluation_case.tool_context["tool"]["id"],
                )
                response = ask_external(
                    user=local_user,
                    message=evaluation_case.question,
                    tool_context=evaluation_case.tool_context,
                    knowledge_context=knowledge_context,
                    provider=provider,
                    config=config,
                )
                provider_response_type = response["type"]
                if is_provider_proposal_candidate(response):
                    proposal_config = evaluation_case.proposal_config
                    if proposal_config is None:
                        raise CommandError(
                            "Proposal candidate was returned for a case without proposal state."
                        )
                    proposal_form = ContainerSelectionMode1Form(data=proposal_config)
                    for field_name in ("catalogue_id", "product_catalogue_id"):
                        proposal_form.fields[field_name].choices = [("", "Select")]
                    proposal_form.is_valid()
                    response = build_container_proposal_preview(
                        response,
                        tool_context=evaluation_case.tool_context,
                        current_config=proposal_config,
                        current_form=proposal_form,
                    )
                self.stdout.write(f"provider={readiness.provider_id}")
                self.stdout.write(f"model={readiness.model_id}")
                self.stdout.write(f"case={evaluation_case.name}")
                self.stdout.write(f"category={evaluation_case.category}")
                self.stdout.write(
                    "question=" + json.dumps(evaluation_case.question, ensure_ascii=True)
                )
                self.stdout.write(
                    "active_tool=" + evaluation_case.tool_context["tool"]["id"]
                )
                self.stdout.write(
                    "mode=" + evaluation_case.tool_context["tool"]["mode"]
                )
                self.stdout.write(
                    "calculation_status="
                    + evaluation_case.tool_context["tool"]["calculation_status"]
                )
                self.stdout.write(f"knowledge_status={knowledge_context['status']}")
                self.stdout.write(
                    "knowledge_refs="
                    + json.dumps(
                        [
                            section["ref"]
                            for section in knowledge_context["sections"]
                        ],
                        ensure_ascii=True,
                    )
                )
                self.stdout.write(
                    "knowledge_headings="
                    + json.dumps(
                        [
                            section["heading_path"]
                            for section in knowledge_context["sections"]
                        ],
                        ensure_ascii=True,
                    )
                )
                self.stdout.write(f"response_type={response['type']}")
                self.stdout.write(f"provider_response_type={provider_response_type}")
                if response["type"] == "proposal_preview":
                    self.stdout.write(f"proposal_valid={str(response['valid']).lower()}")
                    self.stdout.write(
                        "proposal_changes="
                        + json.dumps(response["changes"], ensure_ascii=True)
                    )
                    self.stdout.write(
                        "resulting_state="
                        + json.dumps(response["resulting_state"], ensure_ascii=True)
                    )
                    self.stdout.write(
                        "notice=" + json.dumps(response["notice"], ensure_ascii=True)
                    )
                else:
                    self.stdout.write(
                        "message=" + json.dumps(response["message"], ensure_ascii=True)
                    )
                    self.stdout.write(
                        "fact_refs="
                        + json.dumps(response.get("fact_refs", []), ensure_ascii=True)
                    )
                self.stdout.write(
                    "grounding_flags="
                    + json.dumps(
                        grounding_flags(evaluation_case, response),
                        ensure_ascii=True,
                    )
                )
                if response["type"] == "unavailable":
                    failed = True

        if failed:
            raise CommandError(
                "At least one request returned the validated unavailable outcome."
            )
