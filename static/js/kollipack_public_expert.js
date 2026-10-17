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

    function buildRequest(message, knowledgeScope) {
        return {message: String(message).trim(), knowledge_scope: knowledgeScope};
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
            throw new Error(SAFE_FAILURE);
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
            const questionNode = shell.querySelector("[data-public-expert-question]");
            const responseNode = shell.querySelector("[data-public-expert-response]");
            const sendButton = shell.querySelector("[data-public-expert-send]");
            const spinner = shell.querySelector("[data-public-expert-spinner]");
            const csrfInput = form.querySelector("input[name='csrfmiddlewaretoken']");
            let restoreFocus = null;

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
                input.disabled = true;
                spinner.hidden = false;
                interaction.hidden = false;
                questionNode.textContent = message;
                responseNode.textContent = "Thinking…";
                try {
                    const response = await postQuestion({
                        fetchImpl,
                        url: shell.dataset.publicExpertUrl,
                        csrfToken: csrfInput ? csrfInput.value : "",
                        payload: buildRequest(message, shell.dataset.publicExpertScope),
                    });
                    responseNode.textContent = response.message;
                } catch (error) {
                    responseNode.textContent = SAFE_FAILURE;
                } finally {
                    sendButton.disabled = false;
                    input.disabled = false;
                    spinner.hidden = true;
                    input.focus();
                }
            });

            updateCount();
        });
    }

    return {buildRequest, initialize, postQuestion, validateResponsePayload};
}));
