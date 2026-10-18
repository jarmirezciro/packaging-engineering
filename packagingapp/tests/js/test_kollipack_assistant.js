"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const assistant = require(path.resolve(
    __dirname,
    "../../../static/js/kollipack_assistant.js"
));

function fakeStateRoot(fields, controls) {
    const script = {textContent: JSON.stringify(fields)};
    const form = {
        elements: {
            namedItem(name) {
                return Object.prototype.hasOwnProperty.call(controls, name)
                    ? controls[name]
                    : null;
            },
        },
    };
    return {
        dataset: {assistantStateFields: "field-map"},
        ownerDocument: {
            getElementById(id) {
                return id === "field-map" ? script : null;
            },
        },
        closest(selector) {
            return selector === "form" ? form : null;
        },
    };
}

function scalar(value, type = "text") {
    return {type, value};
}

function checkbox(checked) {
    return {type: "checkbox", checked, value: "on"};
}

async function main() {
    const standaloneFields = [
        {key: "mode", name: "mode", kind: "scalar"},
        {key: "product_source", name: "product_source", kind: "scalar"},
        {key: "product_l", name: "product_l", kind: "scalar"},
        {key: "product_w", name: "product_w", kind: "scalar"},
        {key: "product_h", name: "product_h", kind: "scalar"},
        {key: "r1", name: "r1", kind: "boolean"},
        {key: "r2", name: "r2", kind: "boolean"},
        {key: "r3", name: "r3", kind: "boolean"},
        {key: "selected_product_id", name: "selected_product_id", kind: "scalar"},
        {key: "container_id", name: "container_id", kind: "scalar"},
        {key: "selected_design_candidate_id", name: "selected_design_candidate_id", kind: "scalar"},
    ];
    const standalone = assistant.collectCurrentState(fakeStateRoot(
        standaloneFields,
        {
            mode: scalar("single", "select-one"),
            product_source: [
                {type: "radio", value: "manual", checked: true},
                {type: "radio", value: "catalogue", checked: false},
            ],
            product_l: scalar("200"),
            product_w: scalar(""),
            product_h: scalar("80"),
            r1: checkbox(true),
            r2: checkbox(false),
            r3: checkbox(true),
            selected_product_id: scalar("17", "hidden"),
            container_id: scalar("29", "hidden"),
            selected_design_candidate_id: scalar("design-2", "hidden"),
        }
    ));
    assert.deepEqual(standalone.state, {
        mode: "single",
        product_source: "manual",
        product_l: "200",
        product_w: "",
        product_h: "80",
        r1: true,
        r2: false,
        r3: true,
        selected_product_id: "17",
        container_id: "29",
        selected_design_candidate_id: "design-2",
    });

    const workflowFields = standaloneFields.map((field) => ({
        key: field.key,
        name: `${field.name}_3`,
        kind: field.kind,
    }));
    const workflowControls = {};
    Object.entries({
        mode: scalar("design", "select-one"),
        product_source: [{type: "radio", value: "manual", checked: true}],
        product_l: scalar("120"),
        product_w: scalar("90"),
        product_h: scalar("45"),
        r1: checkbox(false),
        r2: checkbox(true),
        r3: checkbox(false),
        selected_product_id: scalar("", "hidden"),
        container_id: scalar("", "hidden"),
        selected_design_candidate_id: scalar("design-7", "hidden"),
    }).forEach(([name, control]) => {
        workflowControls[`${name}_3`] = control;
    });
    const workflow = assistant.collectCurrentState(fakeStateRoot(workflowFields, workflowControls));
    assert.equal(workflow.state.mode, "design");
    assert.equal(workflow.state.selected_design_candidate_id, "design-7");
    assert.deepEqual(
        {r1: workflow.state.r1, r2: workflow.state.r2, r3: workflow.state.r3},
        {r1: false, r2: true, r3: false}
    );

    const standaloneRequest = assistant.buildRequest(
        {tool: "container_selection", surface: "standalone"},
        standalone.state,
        "Explain this result."
    );
    assert.deepEqual(Object.keys(standaloneRequest), ["tool", "surface", "state", "message"]);
    assert.equal(standaloneRequest.step_ref, undefined);

    const workflowRequest = assistant.buildRequest(
        {tool: "container_selection", surface: "workflow", stepRef: "opaque-step-reference-123"},
        workflow.state,
        "What assumptions apply?"
    );
    assert.deepEqual(
        Object.keys(workflowRequest),
        ["tool", "surface", "state", "message", "step_ref"]
    );
    assert.equal(workflowRequest.step_ref, "opaque-step-reference-123");
    const continuationRequest = assistant.buildRequest(
        {tool: "container_selection", surface: "standalone"},
        standalone.state,
        "mm",
        "signed-continuation-token"
    );
    assert.equal(continuationRequest.continuation_token, "signed-continuation-token");
    const workflowApplyRequest = assistant.buildApplyRequest(
        {surface: "workflow", stepRef: "opaque-step-reference-123"},
        workflow.state,
        "signed-token"
    );
    assert.deepEqual(
        Object.keys(workflowApplyRequest),
        ["proposal_token", "state", "step_ref"]
    );

    for (const type of ["answer", "clarifying_question", "unavailable"]) {
        const message = type === "answer" ? "<img src=x onerror=alert(1)>" : `${type} message`;
        const envelope = {
            ok: true,
            response: {schema_version: "1.1", type, message, fact_refs: []},
        };
        if (type === "clarifying_question") {
            envelope.continuation_token = "signed-continuation-token";
        }
        const validated = assistant.validateResponsePayload(envelope);
        const expected = {schema_version: "1.1", type, message};
        if (type === "clarifying_question") {
            expected.continuation_token = "signed-continuation-token";
        }
        assert.deepEqual(validated, expected);
    }
    assert.throws(
        () => assistant.validateResponsePayload({
            ok: true,
            response: {
                schema_version: "1.1",
                type: "clarifying_question",
                message: "Which units?",
            },
        }),
        /unreadable response/
    );
    const traced = assistant.validateResponsePayload({
        ok: true,
        response: {
            schema_version: "1.1",
            type: "answer",
            message: "Design Mode creates and ranks candidate arrangements.",
            fact_refs: [],
        },
        knowledge_trace: [{
            ref: "domain/container-selection-logic#design-mode",
            title: "Design Mode",
            heading_path: ["Container / Box Selection Tool logic", "Design Mode"],
        }],
    });
    assert.deepEqual(traced.knowledge_trace[0].heading_path, [
        "Container / Box Selection Tool logic",
        "Design Mode",
    ]);
    assert.throws(
        () => assistant.validateResponsePayload({
            ok: true,
            response: {schema_version: "1.1", type: "answer", message: "x", fact_refs: []},
            knowledge_trace: [{ref: "unsafe", title: "Unsafe", heading_path: []}],
        }),
        /unreadable response/
    );
    assert.throws(
        () => assistant.validateResponsePayload({ok: true, response: {type: "answer", message: "x"}}),
        /unreadable response/
    );

    const proposal = assistant.validateResponsePayload({
        ok: true,
        response: {
            schema_version: "1.0",
            type: "proposal_preview",
            summary: "Review the proposed input changes below.",
            state_fingerprint: "sha256:" + "a".repeat(64),
            valid: true,
            can_apply: true,
            proposal_token: "signed-reviewed-proposal-token",
            changes: [{
                field: "product.dimensions.length",
                label: "Product length",
                before: {value: 180, unit: "mm"},
                after: {value: 320, unit: "mm"},
                status: "valid",
                message: null,
            }],
            resulting_state: {validation: "valid", calculation_status: "ready"},
            notice: "These changes have not been applied.",
        },
    });
    assert.equal(proposal.type, "proposal_preview");
    assert.equal(proposal.changes[0].before.value, 180);
    assert.equal(proposal.changes[0].after.value, 320);
    assert.equal(proposal.can_apply, true);
    assert.equal(proposal.proposal_token, "signed-reviewed-proposal-token");
    assert.throws(
        () => assistant.validateResponsePayload({
            ok: true,
            response: {...proposal, apply: true},
        }),
        /unreadable response/
    );

    const applied = assistant.validateApplyResponsePayload({
        ok: true,
        response: {
            schema_version: "1.0",
            type: "applied",
            fields: [
                {
                    field: "product.dimensions.length",
                    field_key: "product_l",
                    value: 320,
                    unit: "mm",
                },
                {
                    field: "product.allowed_vertical_axes",
                    field_key: "r2",
                    value: false,
                    unit: null,
                },
            ],
            calculation_status: "ready",
            message: "Changes applied to inputs. Run the tool when you are ready to calculate.",
        },
    });
    assert.equal(applied.fields.length, 2);
    assistant.applyApprovedFields(
        fakeStateRoot(standaloneFields, {
            mode: scalar("single", "select-one"),
            product_source: [{type: "radio", value: "manual", checked: true}],
            product_l: standalone.form.elements.namedItem("product_l"),
            product_w: scalar("120"),
            product_h: scalar("80"),
            r1: checkbox(true),
            r2: standalone.form.elements.namedItem("r2"),
            r3: checkbox(true),
            selected_product_id: scalar("", "hidden"),
            container_id: scalar("", "hidden"),
            selected_design_candidate_id: scalar("", "hidden"),
        }),
        applied.fields
    );
    assert.equal(standalone.form.elements.namedItem("product_l").value, "320");
    assert.equal(standalone.form.elements.namedItem("r2").checked, false);

    let capturedRequest = null;
    const answer = await assistant.postQuestion({
        fetchImpl: async (url, options) => {
            capturedRequest = {url, options};
            return {
                ok: true,
                status: 200,
                async json() {
                    return {
                        ok: true,
                        response: {
                            schema_version: "1.1",
                            type: "answer",
                            message: "The current result fits 24 products.",
                            fact_refs: [],
                        },
                    };
                },
            };
        },
        url: "/assistant/ask/",
        csrfToken: "csrf-test-token",
        payload: standaloneRequest,
    });
    assert.equal(answer.type, "answer");
    assert.equal(capturedRequest.url, "/assistant/ask/");
    assert.equal(capturedRequest.options.method, "POST");
    assert.equal(capturedRequest.options.headers["X-CSRFToken"], "csrf-test-token");
    assert.deepEqual(JSON.parse(capturedRequest.options.body), standaloneRequest);

    const applyResult = await assistant.postApply({
        fetchImpl: async () => ({
            ok: true,
            status: 200,
            async json() {
                return {
                    ok: true,
                    response: {
                        schema_version: "1.0",
                        type: "applied",
                        fields: [{
                            field: "request.desired_quantity",
                            field_key: "desired_qty",
                            value: 24,
                            unit: "pcs",
                        }],
                        calculation_status: "ready",
                        message: "Changes applied to inputs. Run the tool when you are ready to calculate.",
                    },
                };
            },
        }),
        url: "/assistant/apply-proposal/",
        csrfToken: "csrf-test-token",
        payload: {proposal_token: "token", state: standalone.state},
    });
    assert.equal(applyResult.type, "applied");

    await assert.rejects(
        assistant.postApply({
            fetchImpl: async () => ({
                ok: false,
                status: 409,
                async json() {
                    return {ok: false, error: {code: "stale_proposal", message: "unsafe ignored"}};
                },
            }),
            url: "/assistant/apply-proposal/",
            csrfToken: "token",
            payload: {proposal_token: "token", state: standalone.state},
        }),
        /Inputs have changed since this proposal/
    );

    for (const status of [400, 401, 403, 404, 413, 415, 422, 500]) {
        await assert.rejects(
            assistant.postQuestion({
                fetchImpl: async () => ({ok: false, status}),
                url: "/assistant/ask/",
                csrfToken: "token",
                payload: standaloneRequest,
            }),
            (error) => Boolean(error.safeMessage) && !error.safeMessage.includes("JSON")
        );
    }

    await assert.rejects(
        assistant.postQuestion({
            fetchImpl: async () => ({
                ok: true,
                status: 200,
                async json() { throw new Error("invalid json"); },
            }),
            url: "/assistant/ask/",
            csrfToken: "token",
            payload: standaloneRequest,
        }),
        /unreadable response/
    );
    await assert.rejects(
        assistant.postQuestion({
            fetchImpl: async () => { throw new Error("network failure"); },
            url: "/assistant/ask/",
            csrfToken: "token",
            payload: standaloneRequest,
        }),
        /could not be reached/
    );

    process.stdout.write("kollipack_assistant.js tests passed\n");
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
