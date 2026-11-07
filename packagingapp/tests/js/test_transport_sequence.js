"use strict";

const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const {test} = require("node:test");
const {runInNewContext} = require("node:vm");

const template = readFileSync(path.resolve(__dirname,
    "../../templates/container_tool/partials/_transport_scripts.html"), "utf8");
const [, script] = template.match(/<script>([\s\S]*?)<\/script>/);
const transport = {window: {}, document: {addEventListener() {}}};
runInNewContext(script, transport);

function sequenceInput(value, readOnly = false) {
    const attributes = new Map();
    return {
        value,
        readOnly,
        dataset: {},
        setAttribute(name, value) {
            attributes.set(name, value);
        },
        removeAttribute(name) {
            attributes.delete(name);
        },
        getAttribute(name) {
            return attributes.get(name);
        },
    };
}

function packingForm(initialMode, inputs) {
    const radios = ["space_evenly", "front_to_back", "space_evenly_infill", "front_to_back_infill"]
        .map(value => Object.assign(new EventTarget(), {value, dataset: {}}));
    let selected = radios.find(radio => radio.value === initialMode);
    const root = {
        dataset: {transportSequenceLockedModes: "space_evenly space_evenly_infill "},
        querySelector() {
            return selected;
        },
        querySelectorAll(selector) {
            return selector === "[data-transport-sequence-input]" ? inputs : radios;
        },
    };
    transport.transportBindPackingMode(root);
    return {
        select(mode) {
            selected = radios.find(radio => radio.value === mode);
            selected.dispatchEvent(new Event("change"));
        },
        addRow(input) {
            inputs.push(input);
            transport.transportSyncSequenceInputs(root);
        },
    };
}

function assertSequences(inputs, values, locked) {
    assert.deepEqual(inputs.map(input => input.value), values);
    for (const input of inputs) {
        assert.equal(input.readOnly, locked);
        assert.equal(input.getAttribute("aria-readonly"), locked ? "true" : undefined);
    }
}

test("switching through both Balanced Spread modes preserves editable sequence values", () => {
    const values = ["1", "1", "2", "2", "3"];
    const inputs = values.map(value => sequenceInput(value));
    const form = packingForm("front_to_back_infill", inputs);
    assertSequences(inputs, values, false);

    form.select("space_evenly");
    assertSequences(inputs, Array(5).fill("1"), true);
    form.select("space_evenly_infill");
    assertSequences(inputs, Array(5).fill("1"), true);
    form.select("front_to_back_infill");
    assertSequences(inputs, values, false);

    form.select("front_to_back");
    inputs[0].value = "4";
    form.select("space_evenly_infill");
    assertSequences(inputs, Array(5).fill("1"), true);
    form.select("front_to_back");
    assertSequences(inputs, ["4", ...values.slice(1)], false);
});

test("new rows follow the selected mode even when their template used the initial mode", () => {
    const inputs = [sequenceInput("1", true)];
    const form = packingForm("space_evenly_infill", inputs);
    assertSequences(inputs, ["1"], true);

    form.select("front_to_back");
    form.addRow(sequenceInput("1", true));
    assertSequences(inputs, ["1", "1"], false);

    const editableInputs = [sequenceInput("2")];
    const editableForm = packingForm("front_to_back", editableInputs);
    editableForm.select("space_evenly");
    editableForm.addRow(sequenceInput("1"));
    assertSequences(editableInputs, ["1", "1"], true);
    editableForm.select("front_to_back_infill");
    assertSequences(editableInputs, ["2", "1"], false);
});
