"""Authenticated application boundary for deterministic assistant Tool Context."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import logging
import math

from django.http import JsonResponse

from ..entitlements import AI_ASSISTANT, has_feature
from ..tools.container.assistant import (
    STANDALONE_CONTAINER_RESULT_SESSION_KEY,
    TOOL_ID as CONTAINER_TOOL_ID,
    build_container_tool_context,
    build_container_tool_context_from_workflow_step,
)
from ..tools.container.assistant_actions import (
    CONTAINER_PROPOSAL_FIELDS,
    build_container_proposal_review,
)
from ..tools.container.serializers import sanitize_container_config_for_session
from ..tools.container.service import (
    apply_catalogue_choices,
    build_container_form,
    get_materials_for_catalogue,
    get_packaging_catalogues,
    get_product_catalogues,
    get_selected_material,
    get_selected_product,
)
from ..tools.container.state import default_container_config
from .contracts import (
    ASSISTANT_RESPONSE_SCHEMA_VERSION,
    AssistantMessageValidationError,
    ToolContextValidationError,
    build_knowledge_gap_answer_response,
    build_unavailable_response,
    validate_tool_context,
    validate_user_message,
)
from .clarification import (
    CLARIFICATION_DEPTH_MESSAGE,
    EXPIRED_CONTINUATION_MESSAGE,
    INVALID_CONTINUATION_MESSAGE,
    MAX_CLARIFICATION_ROUNDS,
    MAX_CONTINUATION_TOKEN_LENGTH,
    STALE_CONTINUATION_MESSAGE,
    ClarificationContextError,
    ContinuationTokenBindingMismatch,
    ContinuationTokenError,
    ContinuationTokenExpired,
    ContinuationTokenStale,
    build_clarification_retrieval_query,
    build_next_clarification_context,
    clarification_depth,
    issue_authenticated_continuation_token,
    load_authenticated_continuation_token,
)
from .actions import (
    APPLY_RESPONSE_SCHEMA_VERSION,
    APPLY_RESPONSE_TYPE,
    APPLY_SUCCESS_MESSAGE,
    NoEffectiveProposalChanges,
    ProposalCandidateValidationError,
    ProposalStateMismatchError,
    build_no_effective_changes_response,
    is_provider_proposal_candidate,
    validate_apply_response,
)
from .prompts import READ_ONLY_CAPABILITY
from .knowledge import (
    knowledge_trace,
    knowledge_trace_enabled,
    retrieve_knowledge_context,
)
from .knowledge_gaps import register_ai_knowledge_gap
from .service import AssistantServiceError, ask_external
from .proposal_tokens import (
    MAX_PROPOSAL_TOKEN_LENGTH,
    ProposalTokenError,
    ProposalTokenExpired,
    ProposalTokenUserMismatch,
    issue_reviewed_proposal_token,
    load_reviewed_proposal_token,
)
from .workflow import ensure_workflow_step_refs, find_workflow_step_by_ref


MAX_ASSISTANT_CONTEXT_REQUEST_BYTES = 32 * 1024
MAX_ASSISTANT_APPLY_REQUEST_BYTES = 16 * 1024

_SUPPORTED_SURFACES = frozenset({"standalone", "workflow"})
_STATE_KEYS = frozenset(default_container_config())
_BOOLEAN_STATE_KEYS = frozenset({"r1", "r2", "r3"})
_MAX_STATE_STRING_LENGTH = 256

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ContainerAssistantState:
    context: dict
    config: dict
    form: object
    selected_product: object | None
    selected_material: object | None


class AssistantContextRequestError(ValueError):
    def __init__(self, code, message, *, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _error(code, message, *, status):
    return JsonResponse(
        {"ok": False, "error": {"code": code, "message": message}},
        status=status,
    )


def _reject_json_constant(_value):
    raise ValueError("Non-finite JSON numbers are not supported.")


def _parse_json_request(request, *, max_bytes=MAX_ASSISTANT_CONTEXT_REQUEST_BYTES):
    content_length = request.META.get("CONTENT_LENGTH")
    if content_length:
        try:
            declared_size = int(content_length)
        except (TypeError, ValueError):
            raise AssistantContextRequestError(
                "invalid_request_schema", "Invalid request size metadata."
            )
        if declared_size > max_bytes:
            raise AssistantContextRequestError(
                "assistant_request_too_large",
                "Assistant request exceeds the application size limit.",
                status=413,
            )

    raw_body = request.body
    if len(raw_body) > max_bytes:
        raise AssistantContextRequestError(
            "assistant_request_too_large",
            "Assistant request exceeds the application size limit.",
            status=413,
        )
    try:
        payload = json.loads(
            raw_body.decode("utf-8"),
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise AssistantContextRequestError(
            "malformed_json", "Request body must contain valid UTF-8 JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise AssistantContextRequestError(
            "invalid_request_schema", "Request JSON must be an object."
        )
    return payload


def _validate_state(state):
    if not isinstance(state, dict):
        raise AssistantContextRequestError(
            "invalid_current_state", "State must be a JSON object."
        )
    unknown = sorted(set(state) - _STATE_KEYS)
    if unknown:
        raise AssistantContextRequestError(
            "invalid_current_state", "State contains unsupported fields."
        )

    normalized = {}
    for key, value in state.items():
        if key in _BOOLEAN_STATE_KEYS:
            if not isinstance(value, bool):
                raise AssistantContextRequestError(
                    "invalid_current_state",
                    "Rotation state values must be JSON booleans.",
                )
        elif isinstance(value, bool) or not isinstance(
            value, (str, int, float, type(None))
        ):
            raise AssistantContextRequestError(
                "invalid_current_state", "State values must be scalar JSON values."
            )
        if isinstance(value, float) and not math.isfinite(value):
            raise AssistantContextRequestError(
                "invalid_current_state", "State contains a non-finite number."
            )
        if isinstance(value, str) and len(value) > _MAX_STATE_STRING_LENGTH:
            raise AssistantContextRequestError(
                "invalid_current_state", "State contains an overlong value."
            )
        normalized[key] = value
    return normalized


def _validate_context_request_payload(payload):
    tool = payload.get("tool")
    if tool != CONTAINER_TOOL_ID:
        raise AssistantContextRequestError(
            "unsupported_tool", "The requested assistant tool is not supported."
        )
    surface = payload.get("surface")
    if surface not in _SUPPORTED_SURFACES:
        raise AssistantContextRequestError(
            "unsupported_surface", "The requested assistant surface is not supported."
        )

    expected_keys = {"tool", "surface", "state"}
    if surface == "workflow":
        expected_keys.add("step_ref")
    if set(payload) != expected_keys:
        raise AssistantContextRequestError(
            "invalid_request_schema", "Request fields do not match the endpoint schema."
        )
    state = _validate_state(payload.get("state"))
    if surface == "workflow" and not isinstance(payload.get("step_ref"), str):
        raise AssistantContextRequestError(
            "invalid_request_schema", "Workflow requests require an opaque step reference."
        )
    return surface, state


def _validate_ask_request_payload(payload):
    tool = payload.get("tool")
    if tool != CONTAINER_TOOL_ID:
        raise AssistantContextRequestError(
            "unsupported_tool", "The requested assistant tool is not supported."
        )
    surface = payload.get("surface")
    if surface not in _SUPPORTED_SURFACES:
        raise AssistantContextRequestError(
            "unsupported_surface", "The requested assistant surface is not supported."
        )

    expected_keys = {"tool", "surface", "state", "message"}
    if surface == "workflow":
        expected_keys.add("step_ref")
    allowed_key_sets = {frozenset(expected_keys), frozenset(expected_keys | {"continuation_token"})}
    if frozenset(payload) not in allowed_key_sets:
        raise AssistantContextRequestError(
            "invalid_request_schema", "Request fields do not match the endpoint schema."
        )

    state = _validate_state(payload.get("state"))
    if surface == "workflow" and not isinstance(payload.get("step_ref"), str):
        raise AssistantContextRequestError(
            "invalid_request_schema", "Workflow requests require an opaque step reference."
        )
    try:
        message = validate_user_message(payload.get("message"))
    except AssistantMessageValidationError as exc:
        raise AssistantContextRequestError(
            "invalid_assistant_message",
            "Assistant message must be non-empty plain text within the application limit.",
        ) from exc
    continuation_token = payload.get("continuation_token")
    if continuation_token is not None and (
        not isinstance(continuation_token, str)
        or not continuation_token
        or len(continuation_token) > MAX_CONTINUATION_TOKEN_LENGTH
    ):
        raise AssistantContextRequestError(
            "invalid_continuation",
            INVALID_CONTINUATION_MESSAGE,
        )
    return surface, state, message, continuation_token


def _clarification_reset_response(message):
    return {
        "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
        "type": "answer",
        "message": message,
        "fact_refs": [],
    }


def _validate_apply_request_payload(payload):
    expected = {"proposal_token", "state"}
    expected_workflow = expected | {"step_ref"}
    if frozenset(payload) not in {frozenset(expected), frozenset(expected_workflow)}:
        raise AssistantContextRequestError(
            "invalid_request_schema", "Request fields do not match the Apply schema."
        )
    token = payload.get("proposal_token")
    if not isinstance(token, str) or not token or len(token) > MAX_PROPOSAL_TOKEN_LENGTH:
        raise AssistantContextRequestError(
            "invalid_proposal", "The reviewed proposal is invalid."
        )
    state = _validate_state(payload.get("state"))
    step_ref = payload.get("step_ref")
    if step_ref is not None and not isinstance(step_ref, str):
        raise AssistantContextRequestError(
            "invalid_request_schema", "Workflow Apply requires an opaque step reference."
        )
    return token, state, step_ref


def _current_container_state(state, *, base_config=None):
    config = default_container_config()
    if base_config:
        config.update(base_config)
    config.update(state)
    # Context inspection is never a calculation attempt.  The action is
    # accepted as ordinary browser state but intentionally made non-semantic.
    config["action"] = "refresh"
    return sanitize_container_config_for_session(config)


def _build_current_form(config, user):
    selected_product = get_selected_product(config, user=user)
    selected_material = get_selected_material(config, user=user)
    materials = get_materials_for_catalogue(config, user=user)

    request_stub = type(
        "AssistantContainerRequest",
        (),
        {"method": "POST", "POST": dict(config)},
    )()
    form = build_container_form(
        request=request_stub,
        config=config,
        selected_product=selected_product,
        selected_material=selected_material,
    )
    apply_catalogue_choices(
        form,
        get_packaging_catalogues(user),
        get_product_catalogues(user),
    )
    form.is_valid()
    return form, selected_product, selected_material, materials


def _build_standalone_state(request, state):
    config = _current_container_state(state)
    form, selected_product, selected_material, materials = _build_current_form(
        config, request.user
    )
    context = build_container_tool_context(
        config=config,
        form=form,
        selected_product=selected_product,
        selected_material=selected_material,
        available_materials=materials,
        surface="standalone",
        result_snapshot=request.session.get(
            STANDALONE_CONTAINER_RESULT_SESSION_KEY
        ),
    )
    return _ContainerAssistantState(
        context=context,
        config=config,
        form=form,
        selected_product=selected_product,
        selected_material=selected_material,
    )


def _build_standalone_context(request, state):
    return _build_standalone_state(request, state).context


def _session_workflows(request):
    # Imported lazily to keep the assistant boundary out of Packaging Flow's
    # module initialization and avoid a second source of session-key truth.
    from ..views.full_packaging import CASE_SESSION_PREFIX, SESSION_KEY

    for session_key in list(request.session.keys()):
        if session_key == SESSION_KEY or session_key.startswith(CASE_SESSION_PREFIX):
            workflow = request.session.get(session_key)
            if isinstance(workflow, dict):
                yield session_key, workflow


def _find_current_workflow_step(request, step_ref):
    for _session_key, workflow in _session_workflows(request):
        # Assistant reads must never persist migration metadata or mutate the
        # workflow object held by the session. Normal Packaging Flow rendering
        # owns durable opaque step-ref creation.
        detached_workflow = deepcopy(workflow)
        ensure_workflow_step_refs(detached_workflow)
        step, index = find_workflow_step_by_ref(detached_workflow, step_ref)
        if step is not None:
            return detached_workflow, index
    raise AssistantContextRequestError(
        "workflow_step_not_found",
        "The requested workflow step is unavailable in the current session.",
        status=404,
    )


def _persist_workflow_container_config(request, step_ref, proposed_config):
    """Atomically replace only the bound step's JSON-safe input config."""
    for session_key, workflow in _session_workflows(request):
        step, _index = find_workflow_step_by_ref(workflow, step_ref)
        if step is None:
            continue
        if step.get("type") != "container":
            raise AssistantContextRequestError(
                "unsupported_workflow_step",
                "The requested workflow step is not supported by this assistant tool.",
            )
        step["config"] = sanitize_container_config_for_session(
            deepcopy(proposed_config)
        )
        step["config"]["action"] = "refresh"
        request.session[session_key] = workflow
        request.session.modified = True
        return
    raise AssistantContextRequestError(
        "workflow_step_not_found",
        "The requested workflow step is unavailable in the current session.",
        status=404,
    )


def _workflow_has_retained_result(step):
    return any(
        step.get(key)
        for key in (
            "result",
            "analysis_report",
            "top5",
            "design_candidates",
            "pending_result",
            "selected",
        )
    )


def _build_workflow_state(request, step_ref, state):
    from ..views.full_packaging import _apply_chained_defaults

    workflow, step_index = _find_current_workflow_step(request, step_ref)
    copied_workflow = deepcopy(workflow)
    steps = copied_workflow.get("steps") or []
    step = steps[step_index]
    if step.get("type") != "container":
        raise AssistantContextRequestError(
            "unsupported_workflow_step",
            "The requested workflow step is not supported by this assistant tool.",
        )

    step["config"] = _current_container_state(
        state,
        base_config=step.get("config") or {},
    )
    _apply_chained_defaults(step, steps, step_index)
    if step_index > 0:
        step["config"].update(
            {
                "product_source": "manual",
                "product_catalogue_id": "",
                "selected_product_id": "",
            }
        )
    step["config"] = _current_container_state({}, base_config=step["config"])

    form, selected_product, selected_material, materials = _build_current_form(
        step["config"], request.user
    )
    snapshot = step.get("assistant_result_snapshot")
    raw_result_fingerprint = None
    if snapshot is None and _workflow_has_retained_result(step):
        # Older/unversioned session results cannot be treated as current.  The
        # deliberately non-matching marker makes the adapter fail closed.
        raw_result_fingerprint = "unversioned"

    context = build_container_tool_context_from_workflow_step(
        step,
        form=form,
        selected_product=selected_product,
        selected_material=selected_material,
        available_materials=materials,
        step_ordinal=step_index + 1,
        input_origin=(
            "inherited"
            if step_index > 0
            else step["config"].get("product_source") or "manual"
        ),
        result_state_fingerprint=raw_result_fingerprint,
        result_snapshot=snapshot,
    )
    return _ContainerAssistantState(
        context=context,
        config=step["config"],
        form=form,
        selected_product=selected_product,
        selected_material=selected_material,
    )


def _build_workflow_context(request, step_ref, state):
    return _build_workflow_state(request, step_ref, state).context


def build_current_container_proposal_state(
    request,
    *,
    surface,
    state,
    step_ref=None,
):
    """Rebuild fresh proposal-validation state without running an engine."""
    if surface == "standalone":
        return _build_standalone_state(request, state)
    return _build_workflow_state(request, step_ref, state)


def build_current_assistant_context(
    request,
    *,
    surface,
    state,
    step_ref=None,
):
    """Reconstruct current trusted Tool Context without running an engine."""
    if surface == "standalone":
        return _build_standalone_context(request, state)
    return _build_workflow_context(request, step_ref, state)


def assistant_context(request):
    """Return validated deterministic Tool Context; never run a tool engine."""
    if not getattr(request.user, "is_authenticated", False):
        return _error(
            "authentication_required",
            "Authentication is required for assistant context.",
            status=401,
        )
    if not has_feature(request.user, AI_ASSISTANT):
        return _error(
            "assistant_not_entitled",
            "Your account does not include the AI assistant feature.",
            status=403,
        )
    if request.method != "POST":
        response = _error(
            "method_not_allowed", "Use POST for assistant context requests.", status=405
        )
        response["Allow"] = "POST"
        return response
    if request.content_type != "application/json":
        return _error(
            "unsupported_content_type",
            "Assistant context requests require application/json.",
            status=415,
        )

    try:
        payload = _parse_json_request(request)
        surface, state = _validate_context_request_payload(payload)
        context = build_current_assistant_context(
            request,
            surface=surface,
            state=state,
            step_ref=payload.get("step_ref"),
        )
        validate_tool_context(context)
    except AssistantContextRequestError as exc:
        return _error(exc.code, exc.message, status=exc.status)
    except ToolContextValidationError as exc:
        if "exceeds" in str(exc).lower():
            return _error(
                "assistant_context_too_large",
                "Assistant context exceeds the application size limit.",
                status=413,
            )
        return _error(
            "assistant_context_build_failed",
            "Current tool state could not be represented safely.",
            status=422,
        )

    return JsonResponse({"ok": True, "context": context})


def assistant_ask(request):
    """Answer one question from freshly reconstructed current Tool Context."""
    if not getattr(request.user, "is_authenticated", False):
        return _error(
            "authentication_required",
            "Authentication is required for assistant requests.",
            status=401,
        )
    if not has_feature(request.user, AI_ASSISTANT):
        return _error(
            "assistant_not_entitled",
            "Your account does not include the AI assistant feature.",
            status=403,
        )
    if request.method != "POST":
        response = _error(
            "method_not_allowed", "Use POST for assistant requests.", status=405
        )
        response["Allow"] = "POST"
        return response
    if request.content_type != "application/json":
        return _error(
            "unsupported_content_type",
            "Assistant requests require application/json.",
            status=415,
        )

    try:
        payload = _parse_json_request(request)
        surface, state, message, continuation_token = _validate_ask_request_payload(payload)
        context = build_current_assistant_context(
            request,
            surface=surface,
            state=state,
            step_ref=payload.get("step_ref"),
        )
        validate_tool_context(context)
        clarification_context = None
        if continuation_token is not None:
            try:
                clarification_context = load_authenticated_continuation_token(
                    continuation_token,
                    user_identifier=request.user.pk,
                    tool=CONTAINER_TOOL_ID,
                    surface=surface,
                    state_fingerprint=context["tool"]["state_fingerprint"],
                    step_ref=payload.get("step_ref"),
                )
            except ContinuationTokenExpired:
                return _error(
                    "expired_continuation",
                    EXPIRED_CONTINUATION_MESSAGE,
                    status=410,
                )
            except ContinuationTokenStale:
                return _error(
                    "stale_continuation",
                    STALE_CONTINUATION_MESSAGE,
                    status=409,
                )
            except (ContinuationTokenBindingMismatch, ContinuationTokenError):
                return _error(
                    "invalid_continuation",
                    INVALID_CONTINUATION_MESSAGE,
                    status=400,
                )
        retrieval_query = build_clarification_retrieval_query(
            message,
            clarification_context,
        )
        knowledge_context = retrieve_knowledge_context(
            retrieval_query,
            active_tool=context["tool"]["id"],
        )
        assistant_request = {
            "user": request.user,
            "message": message,
            "tool_context": context,
            "knowledge_context": knowledge_context,
            "capability": READ_ONLY_CAPABILITY,
        }
        if clarification_context is not None:
            assistant_request["clarification_context"] = clarification_context
        response = ask_external(**assistant_request)
        if response.get("type") == "knowledge_gap":
            register_ai_knowledge_gap(
                question=message,
                source="authenticated",
                surface=surface,
                knowledge_scope=context["tool"]["id"],
                reason="documentation_gap",
            )
            response = build_knowledge_gap_answer_response()
        elif is_provider_proposal_candidate(response):
            fresh_state = build_current_container_proposal_state(
                request,
                surface=surface,
                state=state,
                step_ref=payload.get("step_ref"),
            )
            try:
                review = build_container_proposal_review(
                    response,
                    tool_context=fresh_state.context,
                    current_config=fresh_state.config,
                    current_form=fresh_state.form,
                    selected_product=fresh_state.selected_product,
                    selected_material=fresh_state.selected_material,
                )
                response = review.preview
                if response["can_apply"]:
                    response = dict(response)
                    response["proposal_token"] = issue_reviewed_proposal_token(
                        user_identifier=request.user.pk,
                        tool=CONTAINER_TOOL_ID,
                        surface=surface,
                        state_fingerprint=response["state_fingerprint"],
                        changes=review.normalized_changes,
                        allowed_fields=set(CONTAINER_PROPOSAL_FIELDS),
                        step_ref=payload.get("step_ref"),
                    )
            except NoEffectiveProposalChanges:
                response = build_no_effective_changes_response()
            except (ProposalCandidateValidationError, ProposalTokenError):
                logger.warning(
                    "Assistant proposal failed fresh-state validation safely.",
                    extra={"assistant_failure_category": "proposal_invalid_or_stale"},
                )
                response = build_unavailable_response()
        response_continuation_token = None
        if response.get("type") == "clarifying_question":
            if (
                clarification_context is not None
                and clarification_depth(clarification_context)
                >= MAX_CLARIFICATION_ROUNDS
            ):
                response = _clarification_reset_response(
                    CLARIFICATION_DEPTH_MESSAGE
                )
                register_ai_knowledge_gap(
                    question=clarification_context["turns"][0]["message"],
                    source="authenticated",
                    surface=surface,
                    knowledge_scope=context["tool"]["id"],
                    reason="clarification_exhausted",
                )
            else:
                try:
                    next_context = build_next_clarification_context(
                        previous_context=clarification_context,
                        current_user_message=message,
                        assistant_question=response["message"],
                    )
                    response_continuation_token = (
                        issue_authenticated_continuation_token(
                            clarification_context=next_context,
                            user_identifier=request.user.pk,
                            tool=CONTAINER_TOOL_ID,
                            surface=surface,
                            state_fingerprint=context["tool"]["state_fingerprint"],
                            step_ref=payload.get("step_ref"),
                        )
                    )
                except (ClarificationContextError, ContinuationTokenError):
                    response = _clarification_reset_response(
                        CLARIFICATION_DEPTH_MESSAGE
                    )
    except AssistantContextRequestError as exc:
        return _error(exc.code, exc.message, status=exc.status)
    except ToolContextValidationError as exc:
        if "exceeds" in str(exc).lower():
            return _error(
                "assistant_context_too_large",
                "Assistant context exceeds the application size limit.",
                status=413,
            )
        return _error(
            "assistant_context_build_failed",
            "Current tool state could not be represented safely.",
            status=422,
        )
    except AssistantServiceError:
        return _error(
            "assistant_request_failed",
            "The current assistant request could not be processed safely.",
            status=422,
        )

    envelope = {"ok": True, "response": response}
    if response_continuation_token is not None:
        envelope["continuation_token"] = response_continuation_token
    if knowledge_trace_enabled():
        envelope["knowledge_trace"] = knowledge_trace(knowledge_context)
    return JsonResponse(envelope)


def assistant_apply_proposal(request):
    """Apply one reviewed proposal to inputs only; never calculate or call AI."""
    if not getattr(request.user, "is_authenticated", False):
        return _error(
            "authentication_required",
            "Authentication is required to apply Assistant proposals.",
            status=401,
        )
    if not has_feature(request.user, AI_ASSISTANT):
        return _error(
            "assistant_not_entitled",
            "Your account does not include the AI assistant feature.",
            status=403,
        )
    if request.method != "POST":
        response = _error(
            "method_not_allowed", "Use POST to apply Assistant proposals.", status=405
        )
        response["Allow"] = "POST"
        return response
    if request.content_type != "application/json":
        return _error(
            "unsupported_content_type",
            "Assistant Apply requests require application/json.",
            status=415,
        )

    try:
        payload = _parse_json_request(
            request,
            max_bytes=MAX_ASSISTANT_APPLY_REQUEST_BYTES,
        )
        token, state, step_ref = _validate_apply_request_payload(payload)
        token_payload = load_reviewed_proposal_token(
            token,
            user_identifier=request.user.pk,
            allowed_fields=set(CONTAINER_PROPOSAL_FIELDS),
        )
        surface = token_payload["surface"]
        if surface == "standalone":
            if step_ref is not None or set(payload) != {"proposal_token", "state"}:
                raise ProposalTokenError("Standalone proposal binding is invalid.")
        else:
            if (
                set(payload) != {"proposal_token", "state", "step_ref"}
                or step_ref != token_payload.get("step_ref")
            ):
                raise ProposalTokenError("Workflow proposal binding is invalid.")

        fresh_state = build_current_container_proposal_state(
            request,
            surface=surface,
            state=state,
            step_ref=step_ref,
        )
        if (
            fresh_state.context["tool"]["id"] != token_payload["tool"]
            or fresh_state.context["tool"]["surface"] != surface
        ):
            raise ProposalTokenError("Proposal tool binding is invalid.")
        candidate = {
            "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
            "type": "propose_input_changes",
            "state_fingerprint": token_payload["state_fingerprint"],
            "changes": token_payload["changes"],
            "summary": "Apply the reviewed Container input changes.",
        }
        review = build_container_proposal_review(
            candidate,
            tool_context=fresh_state.context,
            current_config=fresh_state.config,
            current_form=fresh_state.form,
            selected_product=fresh_state.selected_product,
            selected_material=fresh_state.selected_material,
        )
        if not review.preview["can_apply"]:
            if any(
                change["status"] == "not_editable"
                for change in review.preview["changes"]
            ):
                logger.info(
                    "Assistant proposal Apply denied by current editability.",
                    extra={
                        "assistant_action_outcome": "apply_not_editable",
                        "assistant_tool": CONTAINER_TOOL_ID,
                        "assistant_surface": surface,
                    },
                )
                return _error(
                    "not_editable",
                    "These inputs are no longer editable in the current state. Ask KolliPack Assistant again.",
                    status=422,
                )
            logger.info(
                "Assistant proposal Apply failed deterministic validation.",
                extra={
                    "assistant_action_outcome": "apply_invalid_state",
                    "assistant_tool": CONTAINER_TOOL_ID,
                    "assistant_surface": surface,
                },
            )
            return _error(
                "invalid_state",
                "The reviewed changes are no longer valid for the current inputs. Ask KolliPack Assistant again.",
                status=422,
            )

        if surface == "workflow":
            _persist_workflow_container_config(
                request,
                step_ref,
                review.proposed_config,
            )

        response = validate_apply_response(
            {
                "schema_version": APPLY_RESPONSE_SCHEMA_VERSION,
                "type": APPLY_RESPONSE_TYPE,
                "fields": review.applied_fields,
                "calculation_status": review.preview["resulting_state"][
                    "calculation_status"
                ],
                "message": APPLY_SUCCESS_MESSAGE,
            }
        )
        logger.info(
            "Assistant proposal applied to inputs.",
            extra={
                "assistant_action_outcome": "apply_success",
                "assistant_tool": CONTAINER_TOOL_ID,
                "assistant_surface": surface,
                "assistant_field_count": len(review.normalized_changes),
            },
        )
        return JsonResponse({"ok": True, "response": response})
    except ProposalTokenExpired:
        logger.info(
            "Assistant proposal Apply token expired.",
            extra={"assistant_action_outcome": "apply_expired"},
        )
        return _error(
            "expired",
            "This proposal has expired. Ask KolliPack Assistant again to create a new proposal.",
            status=410,
        )
    except ProposalTokenUserMismatch:
        logger.info(
            "Assistant proposal Apply user binding failed.",
            extra={"assistant_action_outcome": "apply_unauthorized"},
        )
        return _error(
            "unauthorized",
            "This proposal is not available for the current user.",
            status=403,
        )
    except (ProposalStateMismatchError, NoEffectiveProposalChanges):
        logger.info(
            "Assistant proposal Apply rejected stale state.",
            extra={"assistant_action_outcome": "apply_stale"},
        )
        return _error(
            "stale_proposal",
            "Inputs have changed since this proposal was created. Ask KolliPack Assistant again.",
            status=409,
        )
    except ProposalTokenError:
        logger.info(
            "Assistant proposal Apply token was invalid.",
            extra={"assistant_action_outcome": "apply_invalid"},
        )
        return _error(
            "invalid_proposal",
            "The reviewed proposal is invalid. Ask KolliPack Assistant again.",
            status=400,
        )
    except AssistantContextRequestError as exc:
        return _error(exc.code, exc.message, status=exc.status)
    except (ProposalCandidateValidationError, ToolContextValidationError):
        logger.info(
            "Assistant proposal Apply failed validation safely.",
            extra={"assistant_action_outcome": "apply_invalid"},
        )
        return _error(
            "invalid_state",
            "The reviewed changes could not be applied to the current inputs. Ask KolliPack Assistant again.",
            status=422,
        )
