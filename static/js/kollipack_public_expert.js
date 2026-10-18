(function (root, factory) {
    "use strict";
    const api = factory();
    if (typeof module === "object" && module.exports) {
        module.exports = api;
    }
    if (root && root.document) {
        root.KolliPackPublicExpert = api;
        root.document.addEventListener("DOMContentLoaded", function () {
            api.initialize(root.document, root.fetch.bind(root));
        });
    }
}(typeof globalThis !== "undefined" ? globalThis : this, function () {
    "use strict";

    const RESPONSE_TYPES = new Set(["answer", "clarifying_question", "unavailable"]);
    const SAFE_FAILURE = "The Public Expert is temporarily unavailable. Please try again later.";
    const MAX_CONTINUATION_TOKEN_LENGTH = 12 * 1024;

    function buildRequest(message, knowledgeScope, continuationToken) {
        const request = {message: String(message).trim(), knowledge_scope: knowledgeScope};
        if (continuationToken) {
            request.continuation_token = continuationToken;
        }
        return request;
    }

    function validateResponsePayload(payload) {
        if (!payload || payload.ok !== true || !payload.response) {
            throw new Error("The Public Expert returned an unreadable response.");
        }
        const response = payload.response;
        if (
            response.schema_version !== "1.0" ||
            !RESPONSE_TYPES.has(response.type) ||
            typeof response.message !== "string" ||
            !response.message.trim() ||
            Object.keys(response).sort().join(",") !== "message,schema_version,type"
        ) {
            throw new Error("The Public Expert returned an unreadable response.");
        }
        const hasContinuationToken = Object.prototype.hasOwnProperty.call(
            payload, "continuation_token"
        );
        if (response.type === "clarifying_question") {
            if (
                !hasContinuationToken ||
                typeof payload.continuation_token !== "string" ||
                !payload.continuation_token ||
                payload.continuation_token.length > MAX_CONTINUATION_TOKEN_LENGTH
            ) {
                throw new Error("The Public Expert returned an unreadable response.");
            }
            return {...response, continuation_token: payload.continuation_token};
        }
        if (hasContinuationToken) {
            throw new Error("The Public Expert returned an unreadable response.");
        }
        return response;
    }

    async function postQuestion({fetchImpl, url, csrfToken, payload}) {
        let response;
        try {
            response = await fetchImpl(url, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify(payload),
            });
        } catch (error) {
            throw new Error(SAFE_FAILURE);
        }
        if (!response.ok) {
            let payload = null;
            try {
                payload = await response.json();
            } catch (error) {
                payload = null;
            }
            const code = payload && payload.error && typeof payload.error.code === "string"
                ? payload.error.code
                : "";
            const messages = {
                expired_continuation: "That clarification has expired. Please repeat the original request.",
                invalid_continuation: "That clarification can no longer be continued safely. Please repeat the original request.",
            };
            const failure = new Error(messages[code] || SAFE_FAILURE);
            failure.terminalContinuation = Object.prototype.hasOwnProperty.call(messages, code);
            throw failure;
        }
        try {
            return validateResponsePayload(await response.json());
        } catch (error) {
            throw new Error(SAFE_FAILURE);
        }
    }

    function focusableElements(panel) {
        return Array.from(panel.querySelectorAll(
            "button:not([disabled]), textarea:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex='-1'])"
        )).filter((node) => !node.hidden);
    }

    function initialize(documentRef, fetchImpl) {
        documentRef.querySelectorAll("[data-kollipack-public-expert]").forEach(function (shell) {
            const openButton = shell.querySelector("[data-public-expert-open]");
            const panel = shell.querySelector("[data-public-expert-panel]");
            const backdrop = shell.querySelector("[data-public-expert-backdrop]");
            const closeButton = shell.querySelector("[data-public-expert-close]");
            const form = shell.querySelector("[data-public-expert-form]");
            const input = shell.querySelector("[data-public-expert-input]");
            const count = shell.querySelector("[data-public-expert-count]");
            const interaction = shell.querySelector("[data-public-expert-interaction]");
            const historyNode = shell.querySelector("[data-public-expert-history]");
            const questionNode = shell.querySelector("[data-public-expert-question]");
            const responseNode = shell.querySelector("[data-public-expert-response]");
            const resetButton = shell.querySelector("[data-public-expert-reset]");
            const scrollNode = shell.querySelector("[data-public-expert-scroll]");
            const sendButton = shell.querySelector("[data-public-expert-send]");
            const spinner = shell.querySelector("[data-public-expert-spinner]");
            const csrfInput = form.querySelector("input[name='csrfmiddlewaretoken']");
            let restoreFocus = null;
            let activeContinuationToken = "";
            let clarificationTurns = [];

            function appendHistoryTurn(role, message) {
                const turn = documentRef.createElement("div");
                turn.className = role === "assistant"
                    ? "kpe-turn kpe-turn--expert"
                    : "kpe-turn kpe-turn--visitor";
                const label = documentRef.createElement("span");
                label.className = "kpe-turn-label";
                label.textContent = role === "assistant"
                    ? "KolliPack Public Expert"
                    : "You";
                const text = documentRef.createElement("p");
                text.textContent = message;
                turn.append(label, text);
                historyNode.appendChild(turn);
            }

            function renderHistory() {
                historyNode.replaceChildren();
                clarificationTurns.forEach(function (turn) {
                    appendHistoryTurn("user", turn.question);
                    appendHistoryTurn("assistant", turn.answer);
                });
                historyNode.hidden = clarificationTurns.length === 0;
            }

            function resetClarification() {
                activeContinuationToken = "";
                clarificationTurns = [];
                historyNode.replaceChildren();
                historyNode.hidden = true;
                interaction.hidden = true;
                questionNode.textContent = "";
                responseNode.textContent = "";
                resetButton.hidden = true;
                input.value = "";
                updateCount();
                input.focus();
            }

            function updateCount() {
                count.textContent = `${input.value.length} / ${input.maxLength}`;
            }

            function openPanel() {
                restoreFocus = documentRef.activeElement;
                panel.hidden = false;
                backdrop.hidden = false;
                openButton.setAttribute("aria-expanded", "true");
                documentRef.body.classList.add("public-expert-open");
                input.focus();
            }

            function closePanel() {
                panel.hidden = true;
                backdrop.hidden = true;
                openButton.setAttribute("aria-expanded", "false");
                documentRef.body.classList.remove("public-expert-open");
                if (restoreFocus && typeof restoreFocus.focus === "function") {
                    restoreFocus.focus();
                } else {
                    openButton.focus();
                }
            }

            openButton.addEventListener("click", openPanel);
            closeButton.addEventListener("click", closePanel);
            backdrop.addEventListener("click", closePanel);
            resetButton.addEventListener("click", resetClarification);
            input.addEventListener("input", updateCount);
            shell.querySelectorAll("[data-public-expert-suggestion]").forEach(function (button) {
                button.addEventListener("click", function () {
                    input.value = button.dataset.publicExpertSuggestion;
                    updateCount();
                    input.focus();
                });
            });

            panel.addEventListener("keydown", function (event) {
                if (event.key === "Escape") {
                    event.preventDefault();
                    closePanel();
                    return;
                }
                if (event.key !== "Tab") {
                    return;
                }
                const focusable = focusableElements(panel);
                if (!focusable.length) {
                    event.preventDefault();
                    return;
                }
                const first = focusable[0];
                const last = focusable[focusable.length - 1];
                if (event.shiftKey && documentRef.activeElement === first) {
                    event.preventDefault();
                    last.focus();
                } else if (!event.shiftKey && documentRef.activeElement === last) {
                    event.preventDefault();
                    first.focus();
                }
            });

            form.addEventListener("submit", async function (event) {
                event.preventDefault();
                const message = input.value.trim();
                if (!message) {
                    input.focus();
                    return;
                }
                sendButton.disabled = true;
                resetButton.disabled = true;
                input.disabled = true;
                spinner.hidden = false;
                interaction.hidden = false;
                if (!activeContinuationToken) {
                    clarificationTurns = [];
                }
                renderHistory();
                const continuationToken = activeContinuationToken;
                questionNode.textContent = message;
                responseNode.textContent = "Thinking…";
                try {
                    const response = await postQuestion({
                        fetchImpl,
                        url: shell.dataset.publicExpertUrl,
                        csrfToken: csrfInput ? csrfInput.value : "",
                        payload: buildRequest(
                            message,
                            shell.dataset.publicExpertScope,
                            continuationToken
                        ),
                    });
                    responseNode.textContent = response.message;
                    if (response.type === "clarifying_question") {
                        activeContinuationToken = response.continuation_token;
                        clarificationTurns.push({question: message, answer: response.message});
                        resetButton.hidden = false;
                    } else {
                        activeContinuationToken = "";
                        resetButton.hidden = true;
                    }
                } catch (error) {
                    if (error && error.terminalContinuation) {
                        activeContinuationToken = "";
                        resetButton.hidden = true;
                    }
                    responseNode.textContent = error && error.message
                        ? error.message
                        : SAFE_FAILURE;
                } finally {
                    sendButton.disabled = false;
                    resetButton.disabled = false;
                    input.disabled = false;
                    spinner.hidden = true;
                    input.focus();
                    if (scrollNode) {
                        scrollNode.scrollTop = scrollNode.scrollHeight;
                    }
                }
            });

            updateCount();
        });
    }

    return {buildRequest, initialize, postQuestion, validateResponsePayload};
}));
