"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const expert = require(path.resolve(
    __dirname,
    "../../../static/js/kollipack_public_expert.js"
));

async function main() {
    const request = expert.buildRequest(
        "What does cubicity mean?",
        "container_selection"
    );
    assert.deepEqual(request, {
        message: "What does cubicity mean?",
        knowledge_scope: "container_selection",
    });
    assert.deepEqual(
        expert.buildRequest("mm", "container_selection", "signed-token"),
        {
            message: "mm",
            knowledge_scope: "container_selection",
            continuation_token: "signed-token",
        }
    );

    const privateDomState = {
        product_l: "300",
        product_w: "200",
        product_h: "100",
        result: "45 products",
        utilization: "72%",
        selected_product_id: "981",
    };
    let transmitted = null;
    const response = await expert.postQuestion({
        fetchImpl: async (url, options) => {
            transmitted = {url, options, privateDomState};
            return {
                ok: true,
                async json() {
                    return {
                        ok: true,
                        response: {
                            schema_version: "1.0",
                            type: "answer",
                            message: "Cubicity describes shape balance.",
                        },
                    };
                },
            };
        },
        url: "/assistant/public-ask/",
        csrfToken: "csrf-token",
        payload: request,
    });
    assert.equal(response.type, "answer");
    assert.deepEqual(JSON.parse(transmitted.options.body), request);
    const body = transmitted.options.body;
    for (const value of Object.values(privateDomState)) {
        assert.equal(body.includes(value), false);
    }
    assert.equal(transmitted.options.headers["X-CSRFToken"], "csrf-token");

    assert.throws(
        () => expert.validateResponsePayload({
            ok: true,
            response: {
                schema_version: "1.0",
                type: "proposal_preview",
                message: "Unsafe",
            },
        }),
        /unreadable response/
    );
    const clarification = expert.validateResponsePayload({
        ok: true,
        response: {
            schema_version: "1.0",
            type: "clarifying_question",
            message: "Which tool do you mean?",
        },
        continuation_token: "signed-public-token",
    });
    assert.equal(clarification.continuation_token, "signed-public-token");
    assert.throws(
        () => expert.validateResponsePayload({
            ok: true,
            response: {
                schema_version: "1.0",
                type: "clarifying_question",
                message: "Which tool do you mean?",
            },
        }),
        /unreadable response/
    );
    process.stdout.write("kollipack_public_expert.js tests passed\n");
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
