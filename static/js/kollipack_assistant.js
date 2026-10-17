(function (root, factory) {
    "use strict";

    const api = factory(root);
    if (typeof module === "object" && module.exports) {
        module.exports = api;
    }
    root.KolliPackAssistant = api;

    if (root.document) {
        if (root.document.readyState === "loading") {
            root.document.addEventListener("DOMContentLoaded", api.init);
        } else {
            api.init();
        }
    }
}(typeof window !== "undefined" ? window : globalThis, function (root) {
    "use strict";

    const MAX_QUESTION_LENGTH = 2000;
    const MAX_RESPONSE_LENGTH = 4000;
    const ASSISTANT_RESPONSE_SCHEMA_VERSION = "1.1";
    const PROPOSAL_PREVIEW_SCHEMA_VERSION = "1.0";
    const APPLY_RESPONSE_SCHEMA_VERSION = "1.0";
    const RESPONSE_TYPES = new Set(["answer", "clarifying_question", "unavailable"]);
    const PROPOSAL_STATUSES = new Set([
        "valid", "invalid", "not_editable", "unsupported_unit", "no_change",
    ]);
    const COMPLETE_SUGGESTIONS = [
        "Explain this result.",
        "How many products fit?",
        "What does the utilization mean?",
        "What assumptions were used?",
    ];
    const READY_SUGGESTIONS = [
        "How does this tool work?",
        "What do these restrictions mean?",
        "Set product length to 320 mm.",
        "Use R1 and R3 only.",
    ];

    function AssistantUiError(message) {
        this.name = "AssistantUiError";
        this.message = message;
        this.safeMessage = message;
        if (Error.captureStackTrace) {
            Error.captureStackTrace(this, AssistantUiError);
        }
    }
    AssistantUiError.prototype = Object.create(Error.prototype);
    AssistantUiError.prototype.constructor = AssistantUiError;

    function parseStateFieldMap(stateRoot) {
        if (!stateRoot || !stateRoot.dataset || !stateRoot.dataset.assistantStateFields) {
            throw new AssistantUiError("The current Container state is not available. Refresh the page and try again.");
        }
        const ownerDocument = stateRoot.ownerDocument || root.document;
        const script = ownerDocument && ownerDocument.getElementById(
            stateRoot.dataset.assistantStateFields
        );
        if (!script) {
            throw new AssistantUiError("The current Container state is not available. Refresh the page and try again.");
        }

        let fields;
        try {
            fields = JSON.parse(script.textContent);
        } catch (error) {
            throw new AssistantUiError("The current Container state is not available. Refresh the page and try again.");
        }
        if (!Array.isArray(fields) || !fields.length || fields.length > 64) {
            throw new AssistantUiError("The current Container state is not available. Refresh the page and try again.");
        }

        fields.forEach(function (field) {
            if (
                !field ||
                typeof field.key !== "string" ||
                typeof field.name !== "string" ||
                !["scalar", "boolean"].includes(field.kind)
            ) {
                throw new AssistantUiError("The current Container state is not available. Refresh the page and try again.");
            }
        });
        return fields;
    }

    function asControlList(control) {
        if (!control) return [];
        if (
            typeof control.length === "number" &&
            !control.type &&
            !control.tagName
        ) {
            return Array.from(control);
        }
        return [control];
    }

    function readScalarControl(control) {
        const controls = asControlList(control);
        if (!controls.length) return "";
        const radio = controls.find(function (item) {
            return item && item.type === "radio" && item.checked;
        });
        if (radio) return radio.value;
        if (controls.some(function (item) { return item && item.type === "radio"; })) {
            return "";
        }
        const first = controls[0];
        return first && first.value !== undefined && first.value !== null
            ? String(first.value)
            : "";
    }

    function readBooleanControl(control) {
        return asControlList(control).some(function (item) {
            return Boolean(item && item.checked);
        });
    }

    function collectCurrentState(stateRoot) {
        const form = stateRoot && typeof stateRoot.closest === "function"
            ? stateRoot.closest("form")
            : null;
        if (!form || !form.elements || typeof form.elements.namedItem !== "function") {
            throw new AssistantUiError("The current Container form is not available. Refresh the page and try again.");
        }

        const fields = parseStateFieldMap(stateRoot);
        const state = {};
        fields.forEach(function (field) {
            const control = form.elements.namedItem(field.name);
            state[field.key] = field.kind === "boolean"
                ? readBooleanControl(control)
                : readScalarControl(control);
        });
        return {
            state: state,
            form: form,
            fieldNames: new Set(fields.map(function (field) { return field.name; })),
        };
    }

    function buildRequest(target, state, message) {
        const request = {
            tool: target.tool,
            surface: target.surface,
            state: state,
            message: message,
        };
        if (target.surface === "workflow") {
            request.step_ref = target.stepRef;
        }
        return request;
    }

    function buildApplyRequest(target, state, proposalToken) {
        const request = {
            proposal_token: proposalToken,
            state: state,
        };
        if (target.surface === "workflow") {
            request.step_ref = target.stepRef;
        }
        return request;
    }

    function sameKeys(value, expected) {
        if (!value || typeof value !== "object" || Array.isArray(value)) return false;
        const actual = Object.keys(value).sort();
        return actual.length === expected.length && actual.every(function (key, index) {
            return key === expected[index];
        });
    }

    function validateProposalValue(value) {
        if (!sameKeys(value, ["unit", "value"])) return null;
        const raw = value.value;
        const validValue = raw === null ||
            (typeof raw === "number" && Number.isFinite(raw)) ||
            (Array.isArray(raw) && raw.length <= 3 && raw.every(function (item) {
                return ["length", "width", "height"].includes(item);
            }));
        const validUnit = value.unit === null ||
            ["mm", "g", "pcs"].includes(value.unit);
        if (!validValue || !validUnit) return null;
        return {
            value: Array.isArray(raw) ? raw.slice() : raw,
            unit: value.unit,
        };
    }

    function validateProposalPreview(response) {
        const expectedKeys = response && response.can_apply === true
            ? [
                "can_apply", "changes", "notice", "proposal_token",
                "resulting_state", "schema_version", "state_fingerprint",
                "summary", "type", "valid",
            ]
            : [
                "can_apply", "changes", "notice", "resulting_state",
                "schema_version", "state_fingerprint", "summary", "type", "valid",
            ];
        if (
            !sameKeys(response, expectedKeys) ||
            response.schema_version !== PROPOSAL_PREVIEW_SCHEMA_VERSION ||
            response.type !== "proposal_preview" ||
            typeof response.summary !== "string" ||
            !response.summary.trim() ||
            response.summary.length > 512 ||
            typeof response.state_fingerprint !== "string" ||
            !/^sha256:[0-9a-f]{64}$/.test(response.state_fingerprint) ||
            typeof response.valid !== "boolean" ||
            typeof response.can_apply !== "boolean" ||
            response.can_apply !== response.valid ||
            (
                response.can_apply &&
                (
                    typeof response.proposal_token !== "string" ||
                    !response.proposal_token ||
                    response.proposal_token.length > 8192
                )
            ) ||
            !Array.isArray(response.changes) ||
            response.changes.length < 1 ||
            response.changes.length > 8 ||
            response.notice !== "These changes have not been applied." ||
            !sameKeys(response.resulting_state, ["calculation_status", "validation"]) ||
            !["valid", "incomplete", "invalid"].includes(response.resulting_state.validation) ||
            !["ready", "incomplete", "invalid"].includes(response.resulting_state.calculation_status)
        ) {
            throw new AssistantUiError("KolliPack Assistant returned an unreadable response. Please ask again.");
        }

        const changes = response.changes.map(function (change) {
            const before = change && validateProposalValue(change.before);
            const after = change && validateProposalValue(change.after);
            if (
                !sameKeys(change, ["after", "before", "field", "label", "message", "status"]) ||
                typeof change.field !== "string" || !change.field || change.field.length > 128 ||
                typeof change.label !== "string" || !change.label || change.label.length > 180 ||
                !before || !after || !PROPOSAL_STATUSES.has(change.status) ||
                !(
                    change.message === null ||
                    (typeof change.message === "string" && change.message.length <= 512)
                )
            ) {
                throw new AssistantUiError("KolliPack Assistant returned an unreadable response. Please ask again.");
            }
            return {
                field: change.field,
                label: change.label,
                before: before,
                after: after,
                status: change.status,
                message: change.message,
            };
        });

        const validated = {
            schema_version: PROPOSAL_PREVIEW_SCHEMA_VERSION,
            type: "proposal_preview",
            summary: response.summary,
            state_fingerprint: response.state_fingerprint,
            valid: response.valid,
            can_apply: response.can_apply,
            changes: changes,
            resulting_state: {
                validation: response.resulting_state.validation,
                calculation_status: response.resulting_state.calculation_status,
            },
            notice: response.notice,
        };
        if (response.can_apply) {
            validated.proposal_token = response.proposal_token;
        }
        return validated;
    }

    function validateApplyResponsePayload(payload) {
        const response = payload && payload.ok === true ? payload.response : null;
        if (
            !sameKeys(response, [
                "calculation_status", "fields", "message", "schema_version", "type",
            ]) ||
            response.schema_version !== APPLY_RESPONSE_SCHEMA_VERSION ||
            response.type !== "applied" ||
            !["ready", "incomplete"].includes(response.calculation_status) ||
            response.message !== "Changes applied to inputs. Run the tool when you are ready to calculate." ||
            !Array.isArray(response.fields) ||
            response.fields.length < 1 ||
            response.fields.length > 10
        ) {
            throw new AssistantUiError("KolliPack Assistant returned an unreadable Apply response. Please ask again.");
        }
        const seenKeys = new Set();
        const fields = response.fields.map(function (field) {
            if (
                !sameKeys(field, ["field", "field_key", "unit", "value"]) ||
                typeof field.field !== "string" || !field.field || field.field.length > 128 ||
                typeof field.field_key !== "string" || !field.field_key || field.field_key.length > 64 ||
                seenKeys.has(field.field_key) ||
                !(
                    typeof field.value === "boolean" ||
                    (typeof field.value === "number" && Number.isFinite(field.value))
                ) ||
                !(
                    (typeof field.value === "boolean" && field.unit === null) ||
                    (typeof field.value === "number" && ["mm", "g", "pcs"].includes(field.unit))
                )
            ) {
                throw new AssistantUiError("KolliPack Assistant returned an unreadable Apply response. Please ask again.");
            }
            seenKeys.add(field.field_key);
            return {
                field: field.field,
                field_key: field.field_key,
                value: field.value,
                unit: field.unit,
            };
        });
        return {
            schema_version: APPLY_RESPONSE_SCHEMA_VERSION,
            type: "applied",
            fields: fields,
            calculation_status: response.calculation_status,
            message: response.message,
        };
    }

    function validateResponsePayload(payload) {
        const response = payload && payload.ok === true ? payload.response : null;
        if (response && response.type === "proposal_preview") {
            const proposal = validateProposalPreview(response);
            if (Object.prototype.hasOwnProperty.call(payload, "knowledge_trace")) {
                proposal.knowledge_trace = validateKnowledgeTrace(payload.knowledge_trace);
            }
            return proposal;
        }
        if (
            !response ||
            response.schema_version !== ASSISTANT_RESPONSE_SCHEMA_VERSION ||
            !RESPONSE_TYPES.has(response.type) ||
            typeof response.message !== "string" ||
            !response.message.trim() ||
            response.message.length > MAX_RESPONSE_LENGTH
        ) {
            throw new AssistantUiError("KolliPack Assistant returned an unreadable response. Please ask again.");
        }
        const validated = {
            schema_version: ASSISTANT_RESPONSE_SCHEMA_VERSION,
            type: response.type,
            message: response.message,
        };
        if (Object.prototype.hasOwnProperty.call(payload, "knowledge_trace")) {
            validated.knowledge_trace = validateKnowledgeTrace(payload.knowledge_trace);
        }
        return validated;
    }

    function validateKnowledgeTrace(trace) {
        if (!Array.isArray(trace) || trace.length > 6) {
            throw new AssistantUiError("KolliPack Assistant returned an unreadable response. Please ask again.");
        }
        return trace.map(function (item) {
                if (
                    !item ||
                    typeof item.ref !== "string" ||
                    !item.ref ||
                    item.ref.length > 200 ||
                    typeof item.title !== "string" ||
                    !item.title ||
                    item.title.length > 180 ||
                    !Array.isArray(item.heading_path) ||
                    !item.heading_path.length ||
                    item.heading_path.length > 8 ||
                    item.heading_path.some(function (heading) {
                        return typeof heading !== "string" || !heading || heading.length > 180;
                    })
                ) {
                    throw new AssistantUiError("KolliPack Assistant returned an unreadable response. Please ask again.");
                }
                return {
                    ref: item.ref,
                    title: item.title,
                    heading_path: item.heading_path.slice(),
                };
            });
    }

    function messageForHttpStatus(status) {
        if (status === 401) {
            return "Your session has expired. Sign in again to use KolliPack Assistant.";
        }
        if (status === 403) {
            return "KolliPack Assistant is not available for this account.";
        }
        if (status === 413) {
            return "This assistant request is too large. Shorten the question and try again.";
        }
        if ([400, 404, 415, 422].includes(status)) {
            return "KolliPack Assistant could not review the current state. Refresh the page and try again.";
        }
        return "KolliPack Assistant could not be reached. Container Selection remains available normally.";
    }

    async function postQuestion(options) {
        let response;
        try {
            response = await options.fetchImpl(options.url, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": options.csrfToken,
                },
                body: JSON.stringify(options.payload),
            });
        } catch (error) {
            throw new AssistantUiError(
                "KolliPack Assistant could not be reached. Container Selection remains available normally."
            );
        }

        if (!response || !response.ok) {
            throw new AssistantUiError(messageForHttpStatus(response ? response.status : 0));
        }

        let payload;
        try {
            payload = await response.json();
        } catch (error) {
            throw new AssistantUiError("KolliPack Assistant returned an unreadable response. Please ask again.");
        }
        return validateResponsePayload(payload);
    }

    function applyFailureForPayload(status, payload) {
        const code = payload && payload.error && typeof payload.error.code === "string"
            ? payload.error.code
            : "";
        const messages = {
            stale_proposal: "Inputs have changed since this proposal was created. Ask KolliPack Assistant again.",
            expired: "This proposal has expired. Ask KolliPack Assistant again to create a new proposal.",
            invalid_proposal: "This reviewed proposal is no longer valid. Ask KolliPack Assistant again.",
            not_editable: "These inputs are no longer editable in the current state. Ask KolliPack Assistant again.",
            invalid_state: "The reviewed changes are no longer valid for the current inputs. Ask KolliPack Assistant again.",
            unauthorized: "This proposal is not available for the current user.",
            authentication_required: "Your session has expired. Sign in again to use KolliPack Assistant.",
            assistant_not_entitled: "KolliPack Assistant is not available for this account.",
        };
        const message = messages[code] || messageForHttpStatus(status);
        const recoverable = !code && (status === 0 || status >= 500);
        const error = new AssistantUiError(message);
        error.code = code;
        error.recoverable = recoverable;
        return error;
    }

    async function postApply(options) {
        let response;
        try {
            response = await options.fetchImpl(options.url, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": options.csrfToken,
                },
                body: JSON.stringify(options.payload),
            });
        } catch (error) {
            throw applyFailureForPayload(0, null);
        }

        let payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            if (response && !response.ok) {
                throw applyFailureForPayload(response.status, null);
            }
            throw new AssistantUiError("KolliPack Assistant returned an unreadable Apply response. Please ask again.");
        }
        if (!response || !response.ok) {
            throw applyFailureForPayload(response ? response.status : 0, payload);
        }
        return validateApplyResponsePayload(payload);
    }

    function applyApprovedFields(stateRoot, fields) {
        const current = collectCurrentState(stateRoot);
        const definitions = parseStateFieldMap(stateRoot);
        const byKey = new Map(definitions.map(function (definition) {
            return [definition.key, definition];
        }));
        const plan = fields.map(function (field) {
            const definition = byKey.get(field.field_key);
            if (!definition) {
                throw new AssistantUiError("The approved input field is not available. Refresh the page and try again.");
            }
            if (
                (definition.kind === "boolean") !== (typeof field.value === "boolean")
            ) {
                throw new AssistantUiError("The approved input field is not compatible with the current form.");
            }
            const controls = asControlList(current.form.elements.namedItem(definition.name));
            if (!controls.length) {
                throw new AssistantUiError("The approved input field is not available. Refresh the page and try again.");
            }
            return {definition: definition, controls: controls, value: field.value};
        });

        plan.forEach(function (item) {
            if (item.definition.kind === "boolean") {
                item.controls.forEach(function (control) {
                    control.checked = item.value;
                });
            } else {
                item.controls[0].value = String(item.value);
            }
            item.controls.forEach(function (control) {
                if (typeof control.dispatchEvent === "function" && typeof root.Event === "function") {
                    control.dispatchEvent(new root.Event("input", {bubbles: true}));
                    control.dispatchEvent(new root.Event("change", {bubbles: true}));
                }
            });
        });
        return plan.length;
    }

    function init() {
        const document = root.document;
        const panel = document && document.querySelector("[data-kollipack-assistant]");
        if (!panel || panel.dataset.assistantBound === "1") return;
        panel.dataset.assistantBound = "1";

        const appShell = document.getElementById("appShell");
        const engineeringWorkspace = document.querySelector(".app-engineering-workspace");
        const sidebar = document.getElementById("appSidebar");
        const mobileHeader = document.querySelector(".app-mobile-header");
        const mobileMenuButton = document.getElementById("appMobileMenuButton");
        const mobileCloseButton = document.getElementById("appSidebarClose");
        const closeButton = panel.querySelector("[data-assistant-close]");
        const backdrop = document.querySelector("[data-assistant-backdrop]");
        const contextLabel = panel.querySelector("[data-assistant-context-label]");
        const scrollNode = panel.querySelector(".kpa-scroll");
        const suggestionsNode = panel.querySelector("[data-assistant-suggestions]");
        const interactionNode = panel.querySelector("[data-assistant-interaction]");
        const questionNode = panel.querySelector("[data-assistant-question]");
        const responseNode = panel.querySelector("[data-assistant-response]");
        const responseLabel = panel.querySelector("[data-assistant-response-label]");
        const knowledgeTraceNode = panel.querySelector("[data-assistant-knowledge-trace]");
        const knowledgeTraceList = panel.querySelector("[data-assistant-knowledge-trace-list]");
        const staleNode = panel.querySelector("[data-assistant-stale]");
        const staleTextNode = panel.querySelector("[data-assistant-stale-text]");
        const composer = panel.querySelector("[data-assistant-composer]");
        const input = panel.querySelector("[data-assistant-input]");
        const sendButton = panel.querySelector("[data-assistant-send]");
        const countNode = panel.querySelector("[data-assistant-character-count]");
        const csrfInput = composer ? composer.querySelector('[name="csrfmiddlewaretoken"]') : null;
        const overlayMedia = root.matchMedia
            ? root.matchMedia("(max-width: 1699px)")
            : {matches: false};

        if (
            !appShell || !closeButton || !backdrop || !contextLabel || !scrollNode ||
            !suggestionsNode || !interactionNode || !questionNode ||
            !responseNode || !responseLabel || !knowledgeTraceNode ||
            !knowledgeTraceList || !staleNode || !staleTextNode || !composer ||
            !input || !sendButton || !countNode || !csrfInput ||
            !panel.dataset.assistantApplyUrl
        ) {
            return;
        }

        let isOpen = false;
        let currentTarget = null;
        let currentOpener = null;
        let currentForm = null;
        let currentFieldNames = new Set();
        let requestPending = false;
        let applyPending = false;
        let applyingApprovedFields = false;
        let requestVersion = 0;
        let staleDuringRequest = false;
        let latestQuestion = "";
        let latestResponseType = "";
        let inertSnapshot = null;
        let applyInputSnapshot = null;

        function isOverlay() {
            return Boolean(overlayMedia.matches);
        }

        function setBackgroundInert(active) {
            const elements = [engineeringWorkspace, sidebar, mobileHeader].filter(Boolean);
            if (active && !inertSnapshot) {
                inertSnapshot = new Map();
                elements.forEach(function (element) {
                    inertSnapshot.set(element, Boolean(element.inert));
                    element.inert = true;
                });
            } else if (!active && inertSnapshot) {
                inertSnapshot.forEach(function (wasInert, element) {
                    element.inert = wasInert;
                });
                inertSnapshot = null;
            }
        }

        function syncDrawerLayout() {
            if (!isOpen) {
                document.body.classList.remove("app-assistant-drawer-open");
                document.body.style.removeProperty("--app-assistant-scrollbar-gutter");
                setBackgroundInert(false);
                panel.setAttribute("role", "complementary");
                panel.removeAttribute("aria-modal");
                return;
            }

            if (isOverlay()) {
                const gutter = Math.max(0, root.innerWidth - document.documentElement.clientWidth);
                document.body.style.setProperty("--app-assistant-scrollbar-gutter", gutter + "px");
                document.body.classList.add("app-assistant-drawer-open");
                setBackgroundInert(true);
                panel.setAttribute("role", "dialog");
                panel.setAttribute("aria-modal", "true");
            } else {
                document.body.classList.remove("app-assistant-drawer-open");
                document.body.style.removeProperty("--app-assistant-scrollbar-gutter");
                setBackgroundInert(false);
                panel.setAttribute("role", "complementary");
                panel.removeAttribute("aria-modal");
            }
        }

        function notifyWorkspaceResize() {
            root.requestAnimationFrame(function () {
                root.dispatchEvent(new Event("resize"));
            });
        }

        function setOpenButtonsState() {
            document.querySelectorAll("[data-kollipack-assistant-open]").forEach(function (button) {
                button.setAttribute(
                    "aria-expanded",
                    isOpen && button === currentOpener ? "true" : "false"
                );
            });
        }

        function unbindCurrentForm() {
            if (currentForm) {
                currentForm.removeEventListener("input", handleEngineeringEdit, true);
                currentForm.removeEventListener("change", handleEngineeringEdit, true);
            }
            currentForm = null;
            currentFieldNames = new Set();
        }

        function markAnswerStale() {
            if (!latestQuestion && !requestPending) return;
            staleDuringRequest = true;
            const applyButton = responseNode.querySelector("[data-assistant-apply]");
            if (applyButton) {
                applyButton.disabled = true;
                applyButton.setAttribute("aria-disabled", "true");
            }
            staleTextNode.textContent = latestResponseType === "proposal_preview"
                ? "Inputs changed since this proposal. Ask again to create a proposal for the current state."
                : "Inputs changed since this answer. Ask again to review the current state.";
            staleNode.hidden = false;
        }

        function handleEngineeringEdit(event) {
            const field = event.target;
            if (!applyingApprovedFields && field && currentFieldNames.has(field.name)) {
                markAnswerStale();
                markDisplayedResultStale();
            }
        }

        function markDisplayedResultStale() {
            if (!currentTarget || !currentTarget.hasResult) return;
            const stateRoot = document.getElementById(currentTarget.stateRootId);
            if (!stateRoot) return;
            stateRoot.classList.add("is-assistant-result-stale");
            if (!stateRoot.querySelector("[data-assistant-result-stale-note]")) {
                const notice = document.createElement("div");
                notice.className = "alert alert-warning kpa-result-stale-note";
                notice.dataset.assistantResultStaleNote = "";
                notice.setAttribute("role", "status");
                notice.textContent = "Inputs changed. The displayed result is stale until you run the tool again.";
                stateRoot.prepend(notice);
            }
            currentTarget.hasResult = false;
            if (currentOpener) {
                currentOpener.dataset.assistantHasResult = "false";
            }
        }

        function bindCurrentForm(stateRoot) {
            unbindCurrentForm();
            const current = collectCurrentState(stateRoot);
            currentForm = current.form;
            currentFieldNames = current.fieldNames;
            currentForm.addEventListener("input", handleEngineeringEdit, true);
            currentForm.addEventListener("change", handleEngineeringEdit, true);
        }

        function setCurrentInputsLocked(stateRoot, locked) {
            if (locked) {
                const current = collectCurrentState(stateRoot);
                applyInputSnapshot = new Map();
                parseStateFieldMap(stateRoot).forEach(function (field) {
                    asControlList(current.form.elements.namedItem(field.name)).forEach(function (control) {
                        if (!control || applyInputSnapshot.has(control)) return;
                        applyInputSnapshot.set(control, Boolean(control.disabled));
                        control.disabled = true;
                    });
                });
                return;
            }
            if (applyInputSnapshot) {
                applyInputSnapshot.forEach(function (wasDisabled, control) {
                    control.disabled = wasDisabled;
                });
                applyInputSnapshot = null;
            }
        }

        function clearInteraction() {
            requestVersion += 1;
            requestPending = false;
            applyPending = false;
            staleDuringRequest = false;
            latestQuestion = "";
            latestResponseType = "";
            interactionNode.hidden = true;
            staleNode.hidden = true;
            questionNode.textContent = "";
            responseNode.textContent = "";
            responseNode.className = "kpa-response";
            responseLabel.textContent = "KolliPack Assistant";
            knowledgeTraceNode.hidden = true;
            knowledgeTraceNode.open = false;
            knowledgeTraceList.replaceChildren();
            input.value = "";
            sendButton.disabled = false;
            updateCharacterCount();
        }

        function renderSuggestions(hasResult) {
            const questions = hasResult ? COMPLETE_SUGGESTIONS : READY_SUGGESTIONS;
            suggestionsNode.replaceChildren();
            questions.forEach(function (question) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "kpa-suggestion";
                button.textContent = question;
                button.addEventListener("click", function () {
                    input.value = question;
                    updateCharacterCount();
                    sendQuestion(question);
                });
                suggestionsNode.appendChild(button);
            });
        }

        function targetFromOpener(opener) {
            if (!opener || !opener.dataset) return null;
            const surface = opener.dataset.assistantSurface;
            const stateRootId = opener.dataset.assistantStateRootId;
            const stepRef = opener.dataset.assistantStepRef || "";
            if (!stateRootId || !["standalone", "workflow"].includes(surface)) return null;
            if (surface === "workflow" && !stepRef) return null;
            return {
                tool: panel.dataset.assistantTool,
                surface: surface,
                stateRootId: stateRootId,
                stepRef: stepRef,
                contextLabel: opener.dataset.assistantContextLabel || "Container Selection",
                hasResult: opener.dataset.assistantHasResult === "true",
            };
        }

        function sameTarget(left, right) {
            return Boolean(
                left && right &&
                left.surface === right.surface &&
                left.stateRootId === right.stateRootId &&
                left.stepRef === right.stepRef
            );
        }

        function openFrom(opener, options) {
            const target = targetFromOpener(opener);
            if (!target) return false;
            const stateRoot = document.getElementById(target.stateRootId);
            if (!stateRoot) return false;

            if (document.body.classList.contains("app-sidebar-drawer-open") && mobileCloseButton) {
                mobileCloseButton.click();
            }

            if (!sameTarget(currentTarget, target)) {
                clearInteraction();
            }
            currentTarget = target;
            currentOpener = opener;
            contextLabel.textContent = target.contextLabel;
            renderSuggestions(target.hasResult);

            try {
                bindCurrentForm(stateRoot);
            } catch (error) {
                return false;
            }

            isOpen = true;
            appShell.classList.add("app-assistant-open");
            panel.setAttribute("aria-hidden", "false");
            syncDrawerLayout();
            setOpenButtonsState();
            notifyWorkspaceResize();

            const keyboardOpen = options && options.keyboard;
            if (isOverlay() || keyboardOpen) {
                root.requestAnimationFrame(function () { input.focus(); });
            }
            return true;
        }

        function close(restoreFocus) {
            if (!isOpen) return;
            isOpen = false;
            appShell.classList.remove("app-assistant-open");
            panel.setAttribute("aria-hidden", "true");
            syncDrawerLayout();
            setOpenButtonsState();
            notifyWorkspaceResize();
            if (restoreFocus !== false && currentOpener && typeof currentOpener.focus === "function") {
                currentOpener.focus();
            }
        }

        function updateCharacterCount() {
            countNode.textContent = input.value.length + " / " + MAX_QUESTION_LENGTH;
        }

        function revealLatestInteraction() {
            root.requestAnimationFrame(function () {
                const scrollRect = scrollNode.getBoundingClientRect();
                const interactionRect = interactionNode.getBoundingClientRect();
                const targetTop = Math.max(
                    0,
                    scrollNode.scrollTop + interactionRect.top - scrollRect.top - 12
                );
                const reducedMotion = root.matchMedia &&
                    root.matchMedia("(prefers-reduced-motion: reduce)").matches;
                scrollNode.scrollTo({
                    top: targetTop,
                    behavior: reducedMotion ? "auto" : "smooth",
                });
            });
        }

        function renderLoading(question) {
            latestQuestion = question;
            latestResponseType = "";
            interactionNode.hidden = false;
            staleNode.hidden = true;
            questionNode.textContent = question;
            responseLabel.textContent = "KolliPack Assistant";
            responseNode.className = "kpa-response is-loading";
            responseNode.textContent = "KolliPack Assistant is reviewing the available KolliPack context…";
            knowledgeTraceNode.hidden = true;
            knowledgeTraceNode.open = false;
            knowledgeTraceList.replaceChildren();
            revealLatestInteraction();
        }

        function formatProposalValue(measurement) {
            if (measurement.value === null) return "blank";
            if (Array.isArray(measurement.value)) {
                if (!measurement.value.length) return "No vertical axes";
                return measurement.value.map(function (axis) {
                    return axis.charAt(0).toUpperCase() + axis.slice(1);
                }).join(", ");
            }
            return String(measurement.value) + (measurement.unit ? " " + measurement.unit : "");
        }

        function renderProposal(response) {
            const wrapper = document.createElement("section");
            wrapper.className = "kpa-proposal" + (response.valid ? " is-valid" : " is-invalid");
            wrapper.setAttribute("aria-label", "Proposed input changes");

            const title = document.createElement("h3");
            title.textContent = "Proposed changes";
            wrapper.appendChild(title);

            const summary = document.createElement("p");
            summary.className = "kpa-proposal-summary";
            summary.textContent = response.summary;
            wrapper.appendChild(summary);

            const list = document.createElement("ul");
            list.className = "kpa-proposal-list";
            response.changes.forEach(function (change) {
                const item = document.createElement("li");
                item.className = "kpa-proposal-change is-" + change.status;

                const label = document.createElement("h4");
                label.textContent = change.label;
                item.appendChild(label);

                const values = document.createElement("p");
                values.className = "kpa-proposal-values";
                const before = document.createElement("span");
                before.textContent = formatProposalValue(change.before);
                const arrow = document.createElement("span");
                arrow.className = "kpa-proposal-arrow";
                arrow.setAttribute("aria-hidden", "true");
                arrow.textContent = "→";
                const after = document.createElement("span");
                after.textContent = formatProposalValue(change.after);
                values.append(before, arrow, after);
                item.appendChild(values);

                const status = document.createElement("p");
                status.className = "kpa-proposal-status";
                const statusLabels = {
                    valid: "✓ Valid",
                    invalid: "✕ Invalid",
                    not_editable: "✕ Not editable",
                    unsupported_unit: "✕ Unsupported unit",
                    no_change: "No effective change",
                };
                status.textContent = statusLabels[change.status];
                item.appendChild(status);
                if (change.message) {
                    const message = document.createElement("p");
                    message.className = "kpa-proposal-message";
                    message.textContent = change.message;
                    item.appendChild(message);
                }
                list.appendChild(item);
            });
            wrapper.appendChild(list);

            const resulting = document.createElement("p");
            resulting.className = "kpa-proposal-resulting";
            const resultingLabels = {
                ready: "Ready — the resulting inputs meet current calculation prerequisites.",
                incomplete: "Incomplete — additional required inputs are still missing.",
                invalid: "Invalid — the proposal cannot be accepted as one atomic change set.",
            };
            resulting.textContent = "Resulting input state: " + resultingLabels[response.resulting_state.calculation_status];
            wrapper.appendChild(resulting);

            const notice = document.createElement("p");
            notice.className = "kpa-proposal-notice";
            notice.textContent = response.notice;
            wrapper.appendChild(notice);

            if (response.can_apply) {
                const applyArea = document.createElement("div");
                applyArea.className = "kpa-proposal-actions";

                const explanation = document.createElement("p");
                explanation.className = "kpa-proposal-apply-note";
                explanation.textContent = "This updates the input fields only. KolliPack will not recalculate until you run the tool.";
                applyArea.appendChild(explanation);

                const applyButton = document.createElement("button");
                applyButton.type = "button";
                applyButton.className = "btn btn-app-outline kpa-apply";
                applyButton.dataset.assistantApply = "";
                applyButton.textContent = "Apply changes";
                applyButton.setAttribute("aria-label", "Apply reviewed changes to Container inputs");
                applyArea.appendChild(applyButton);

                const applyStatus = document.createElement("p");
                applyStatus.className = "kpa-apply-status";
                applyStatus.dataset.assistantApplyStatus = "";
                applyStatus.setAttribute("role", "status");
                applyStatus.setAttribute("aria-live", "polite");
                applyArea.appendChild(applyStatus);

                applyButton.addEventListener("click", function () {
                    applyProposal(response, applyButton, applyStatus);
                });
                wrapper.appendChild(applyArea);
            }
            responseNode.replaceChildren(wrapper);
        }

        async function applyProposal(proposal, button, statusNode) {
            if (applyPending || !currentTarget || !proposal.can_apply) return;
            const stateRoot = document.getElementById(currentTarget.stateRootId);
            let current;
            try {
                current = collectCurrentState(stateRoot);
            } catch (error) {
                statusNode.textContent = error.safeMessage || "The current Container state is not available. Refresh the page and try again.";
                button.disabled = true;
                return;
            }

            applyPending = true;
            button.disabled = true;
            button.setAttribute("aria-disabled", "true");
            statusNode.textContent = "Applying reviewed input changes…";
            setCurrentInputsLocked(stateRoot, true);
            const payload = buildApplyRequest(
                currentTarget,
                current.state,
                proposal.proposal_token
            );

            try {
                const applied = await postApply({
                    fetchImpl: root.fetch.bind(root),
                    url: panel.dataset.assistantApplyUrl,
                    csrfToken: csrfInput.value,
                    payload: payload,
                });
                applyingApprovedFields = true;
                try {
                    applyApprovedFields(stateRoot, applied.fields);
                } finally {
                    applyingApprovedFields = false;
                }
                markDisplayedResultStale();
                latestResponseType = "applied";
                staleDuringRequest = false;
                staleNode.hidden = true;
                responseLabel.textContent = "KolliPack Assistant · applied";
                responseNode.className = "kpa-response is-applied";
                responseNode.textContent = applied.message;
                renderSuggestions(false);
                revealLatestInteraction();
            } catch (error) {
                statusNode.textContent = error && error.safeMessage
                    ? error.safeMessage
                    : "The reviewed changes could not be applied. Ask KolliPack Assistant again.";
                if (error && error.recoverable) {
                    button.disabled = false;
                    button.removeAttribute("aria-disabled");
                }
            } finally {
                setCurrentInputsLocked(stateRoot, false);
                applyPending = false;
            }
        }

        function renderResponse(response) {
            latestResponseType = response.type;
            responseNode.className = "kpa-response";
            if (response.type === "proposal_preview") {
                responseLabel.textContent = "KolliPack Assistant · proposal";
                renderProposal(response);
                staleTextNode.textContent = "Inputs changed since this proposal. Ask again to create a proposal for the current state.";
            } else if (response.type === "clarifying_question") {
                responseLabel.textContent = "KolliPack Assistant · clarification";
            } else {
                responseLabel.textContent = "KolliPack Assistant";
            }
            if (response.type === "unavailable") {
                responseNode.classList.add("is-unavailable");
            }
            if (response.type !== "proposal_preview") {
                responseNode.textContent = response.message;
                staleTextNode.textContent = "Inputs changed since this answer. Ask again to review the current state.";
            }
            knowledgeTraceList.replaceChildren();
            const trace = response.knowledge_trace || [];
            trace.forEach(function (item) {
                const entry = document.createElement("li");
                entry.textContent = item.heading_path.join(" → ");
                knowledgeTraceList.appendChild(entry);
            });
            knowledgeTraceNode.hidden = trace.length === 0;
            knowledgeTraceNode.open = false;
            revealLatestInteraction();
        }

        function renderError(message) {
            interactionNode.hidden = false;
            responseLabel.textContent = "KolliPack Assistant";
            responseNode.className = "kpa-response is-error";
            responseNode.textContent = message;
            knowledgeTraceNode.hidden = true;
            knowledgeTraceNode.open = false;
            knowledgeTraceList.replaceChildren();
            revealLatestInteraction();
        }

        async function sendQuestion(questionOverride) {
            if (requestPending || !currentTarget) return;
            const question = String(
                questionOverride !== undefined ? questionOverride : input.value
            ).trim();
            if (!question) {
                renderError("Enter a question for KolliPack Assistant.");
                input.focus();
                return;
            }
            if (question.length > MAX_QUESTION_LENGTH) {
                renderError("Questions can contain at most 2,000 characters.");
                input.focus();
                return;
            }

            const stateRoot = document.getElementById(currentTarget.stateRootId);
            let current;
            try {
                current = collectCurrentState(stateRoot);
            } catch (error) {
                renderError(error.safeMessage || "The current Container state is not available. Refresh the page and try again.");
                return;
            }

            const payload = buildRequest(currentTarget, current.state, question);
            const thisRequest = ++requestVersion;
            requestPending = true;
            staleDuringRequest = false;
            sendButton.disabled = true;
            renderLoading(question);

            try {
                const response = await postQuestion({
                    fetchImpl: root.fetch.bind(root),
                    url: panel.dataset.assistantAskUrl,
                    csrfToken: csrfInput.value,
                    payload: payload,
                });
                if (thisRequest !== requestVersion) return;
                renderResponse(response);
                input.value = "";
                updateCharacterCount();
                if (staleDuringRequest) staleNode.hidden = false;
            } catch (error) {
                if (thisRequest !== requestVersion) return;
                renderError(
                    error && error.safeMessage
                        ? error.safeMessage
                        : "KolliPack Assistant could not be reached. Container Selection remains available normally."
                );
                if (staleDuringRequest) staleNode.hidden = false;
            } finally {
                if (thisRequest === requestVersion) {
                    requestPending = false;
                    sendButton.disabled = false;
                }
            }
        }

        document.querySelectorAll("[data-kollipack-assistant-open]").forEach(function (opener) {
            opener.addEventListener("click", function (event) {
                openFrom(opener, {keyboard: event.detail === 0});
            });
        });
        closeButton.addEventListener("click", function () { close(true); });
        backdrop.addEventListener("click", function () { close(true); });
        composer.addEventListener("submit", function (event) {
            event.preventDefault();
            sendQuestion();
        });
        input.addEventListener("input", updateCharacterCount);
        input.addEventListener("keydown", function (event) {
            if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
                event.preventDefault();
                sendQuestion();
            }
        });

        document.addEventListener("keydown", function (event) {
            if (!isOpen) return;
            if (event.key === "Escape") {
                event.preventDefault();
                close(true);
                return;
            }
            if (event.key !== "Tab" || !isOverlay()) return;

            const focusable = Array.from(panel.querySelectorAll(
                'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )).filter(function (element) {
                return element.getClientRects().length > 0;
            });
            if (!focusable.length) {
                event.preventDefault();
                return;
            }
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        });

        if (mobileMenuButton) {
            mobileMenuButton.addEventListener("click", function () {
                if (isOpen) close(false);
            }, true);
        }
        const viewportChange = function () {
            syncDrawerLayout();
            notifyWorkspaceResize();
        };
        if (typeof overlayMedia.addEventListener === "function") {
            overlayMedia.addEventListener("change", viewportChange);
        } else if (typeof overlayMedia.addListener === "function") {
            overlayMedia.addListener(viewportChange);
        }
        panel.addEventListener("transitionend", function (event) {
            if (event.propertyName === "transform") notifyWorkspaceResize();
        });

        updateCharacterCount();
    }

    return {
        init: init,
        collectCurrentState: collectCurrentState,
        buildRequest: buildRequest,
        buildApplyRequest: buildApplyRequest,
        validateResponsePayload: validateResponsePayload,
        validateApplyResponsePayload: validateApplyResponsePayload,
        messageForHttpStatus: messageForHttpStatus,
        postQuestion: postQuestion,
        postApply: postApply,
        applyApprovedFields: applyApprovedFields,
    };
}));
