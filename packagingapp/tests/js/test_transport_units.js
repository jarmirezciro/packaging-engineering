"use strict";

const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const {test} = require("node:test");
const {runInNewContext} = require("node:vm");

const read = name => readFileSync(path.resolve(__dirname, name), "utf8");
const unitScript = read("../../../static/js/unit_selector.js");
const numericScript = read("../../../static/js/numeric_inputs.js");
const [, transportScript] = read("../../templates/container_tool/partials/_transport_scripts.html")
    .match(/<script>([\s\S]*?)<\/script>/);

function element(properties = {}) {
    return Object.assign(new EventTarget(), {
        dataset: {}, value: "", hidden: false,
        classList: {contains: () => false, remove() {}},
        setAttribute() {}, focus() {},
        querySelector: () => null, querySelectorAll: () => [],
    }, properties);
}

// Exercise the actual selector and Transport handlers with row-local form controls.
function formHarness({dimension = "in", mass = "lb"} = {}) {
    const rows = [];
    const selectors = new Map();
    const hiddenUnits = new Map();
    const groups = {length: "transport-load-unit-dimensions_0", mass: "transport-load-unit-mass_0"};
    let context;
    const form = {querySelector: selector => document.querySelector(selector)};
    const inputs = () => rows.flatMap(row => Object.values(row.inputs));
    const document = element({
        readyState: "loading", documentElement: {dataset: {}},
        querySelector(selector) {
            const group = selector.match(/data-unit-group="([^"]+)"/)?.[1];
            return selectors.get(group) || null;
        },
        querySelectorAll(selector) {
            if (selector === "[data-unit-input]") return inputs();
            if (selector === "[data-unit-selector]") return [...selectors.values()];
            const group = selector.match(/^\[data-unit-group="([^"]+)"\]$/)?.[1];
            if (!group) return [];
            return [selectors.get(group), hiddenUnits.get(group),
                ...inputs().filter(input => input.dataset.unitGroup === group)];
        },
    });
    for (const [quantity, units, selected] of [
        ["length", ["mm", "cm", "m", "in", "ft"], dimension],
        ["mass", ["g", "kg", "t", "oz", "lb"], mass],
    ]) {
        const group = groups[quantity];
        const trigger = element();
        const options = units.map(unit => element({dataset: {unit}}));
        const selector = element({
            dataset: {unitGroup: group, unitQuantity: quantity}, options,
            matches: query => query === "[data-unit-selector]",
            querySelector: query => query === ".unit-selector-trigger" ? trigger : element(),
            querySelectorAll: query => query === "[data-unit-option]" ? options : [],
        });
        selectors.set(group, selector);
        hiddenUnits.set(group, element({value: selected,
            matches: query => query === "input[data-unit-hidden]"}));
    }
    context = {window: {}, document, CSS: {escape: value => value}, Event,
        CustomEvent: class extends Event {
            constructor(type, options) { super(type); this.detail = options.detail; }
        }};
    runInNewContext(transportScript, context);
    runInNewContext(numericScript, context);
    runInNewContext(unitScript, context);
    const api = context.window.KolliPackUnitSelector;
    const numeric = context.window.KolliPackNumericInputs;
    return {
        api,
        addRow({values = ["15.749999999999998", "62.99999999999999", "39.39999999999999", "661.386786821"],
            canonical = [400.04999999999995, 1600.1999999999998, 1000.7599999999998, 300.000000123],
            source = "manual"} = {}) {
            const row = {inputs: {}, canonical: {}, source: {value: source}};
            row.querySelector = selector => {
                if (selector === "[data-transport-row-source]") return row.source;
                const key = selector.match(/item_canonical_(\w+)\[\]/)?.[1];
                return row.canonical[key] || null;
            };
            row.querySelectorAll = () => Object.values(row.canonical);
            ["length", "width", "height", "weight"].forEach((key, index) => {
                const quantity = key === "weight" ? "mass" : "length";
                const input = element({
                    name: `item_${key}[]`, value: values[index],
                    step: "any", validity: {},
                    dataset: {unitGroup: groups[quantity]},
                    closest: selector => selector === "tr" ? row : form,
                    matches: query => query === 'input[data-unit-input]' || query === 'input[type="number"]',
                });
                if (canonical[index] !== "") {
                    input.dataset.unitCanonicalValue = String(canonical[index]);
                    input.dataset.unitCanonicalUnit = key === "weight" ? "kg" : "mm";
                }
                row.inputs[key] = input;
                row.canonical[key] = {value: String(canonical[index])};
                input.addEventListener("input", () => context.transportMarkRowManual(input));
                numeric.commit(input);
            });
            rows.push(row);
            return row;
        },
        init: () => api.init(),
        choose(quantity, unit) {
            const option = selectors.get(groups[quantity]).options.find(option => option.dataset.unit === unit);
            option.dispatchEvent(new Event("click"));
        },
        edit(row, key, value) {
            const input = row.inputs[key];
            input.value = value;
            // Mirror the capture listener before the target's input handlers.
            const event = new Event("input");
            Object.defineProperty(event, "target", {value: input});
            document.dispatchEvent(event);
            input.dispatchEvent(new Event("input"));
        },
        blur: (row, key) => numeric.commit(row.inputs[key]),
        exact: (row, key) => numeric.getValue(row.inputs[key]),
        format: numeric.format,
        formData() {
            const elements = inputs();
            const formData = new FormData();
            elements.forEach(input => formData.append(input.name, input.value));
            const event = new Event("formdata");
            Object.defineProperty(event, "target", {value: {elements}});
            event.formData = formData;
            document.dispatchEvent(event);
            return formData;
        },
        remove: row => rows.splice(rows.indexOf(row), 1),
    };
}

test("initialization preserves exact server canonical values beside rounded inputs", () => {
    const form = formHarness();
    const row = form.addRow();
    form.init();
    assert.equal(row.inputs.length.value, "15.75");
    assert.equal(form.exact(row, "length"), "15.749999999999998");
    assert.equal(form.api.getCanonicalValue(row.inputs.length, "length"), 400.04999999999995);
    assert.equal(form.api.getCanonicalValue(row.inputs.weight, "mass"), 300.000000123 * 1000);
    assert.equal(row.canonical.weight.value, "300.000000123");
    form.init();
    assert.equal(form.api.getCanonicalValue(row.inputs.length, "length"), 400.04999999999995);
});

test("all supported unit switches reuse canonical values and the three-decimal rule", () => {
    const form = formHarness();
    const row = form.addRow();
    form.init();
    for (let cycle = 0; cycle < 10; cycle++) {
        for (const unit of ["mm", "cm", "m", "ft", "in"]) form.choose("length", unit);
        for (const unit of ["kg", "g", "t", "oz", "lb"]) form.choose("mass", unit);
        assert.deepEqual(Object.values(row.inputs).map(input => input.value), ["15.75", "63", "39.4", "661.387"]);
        assert.equal(form.api.getCanonicalValue(row.inputs.length, "length"), 400.04999999999995);
        assert.equal(row.canonical.length.value, "400.04999999999995");
        assert.equal(row.canonical.weight.value, "300.000000123");
    }
});

test("editing weight retains exact dimensions and does not reformat typing", () => {
    const form = formHarness();
    const row = form.addRow({source: "catalogue"});
    form.init();
    const original = ["length", "width", "height"].map(key => row.canonical[key].value);
    form.edit(row, "weight", "662.123456789");
    assert.equal(row.inputs.weight.value, "662.123456789");
    assert.equal(row.source.value, "manual");
    assert.deepEqual(["length", "width", "height"].map(key => row.canonical[key].value), original);
    assert.ok(Math.abs(Number(row.canonical.weight.value) - 662.123456789 * 0.45359237) < 1e-12);
    const edited = form.api.getCanonicalValue(row.inputs.weight, "mass");
    form.blur(row, "weight");
    assert.equal(row.inputs.weight.value, "662.123");
    assert.equal(form.exact(row, "weight"), "662.123456789");
    form.choose("mass", "kg");
    form.choose("mass", "lb");
    assert.equal(row.inputs.weight.value, "662.123");
    assert.equal(form.api.getCanonicalValue(row.inputs.weight, "mass"), edited);
});

test("editing or clearing a dimension replaces stale canonical metadata only for that field", () => {
    const form = formHarness();
    const row = form.addRow({source: "inherited"});
    form.init();
    const width = row.canonical.width.value;
    form.edit(row, "length", "16.123456789");
    assert.equal(row.inputs.length.value, "16.123456789");
    assert.equal(Number(row.canonical.length.value), 16.123456789 * 25.4);
    assert.equal(row.canonical.width.value, width);
    form.edit(row, "length", "");
    assert.equal(row.canonical.length.value, "");
    assert.equal(form.api.getCanonicalValue(row.inputs.length, "length"), null);
});

test("canonical imports preserve nonzero values near zero and optional blanks", () => {
    const form = formHarness();
    const row = form.addRow();
    form.init();
    form.api.setCanonicalValue(row.inputs.length, 1600.1999999999998, "mm");
    assert.equal(row.inputs.length.value, "63");
    form.api.setCanonicalValue(row.inputs.weight, -0.000001, "kg");
    assert.ok(Number(row.inputs.weight.value) < 0);
    assert.equal(form.api.getCanonicalValue(row.inputs.weight, "mass"), -0.001);
    form.api.setCanonicalValue(row.inputs.height, null, "mm");
    assert.equal(row.inputs.height.value, "");
});

test("manual metric values round trip without converting rounded text", () => {
    const form = formHarness({dimension: "mm"});
    const row = form.addRow({values: ["100", "1.23456789", "1", "0"],
        canonical: ["", "", "", ""]});
    form.init();
    form.choose("length", "in");
    assert.equal(row.inputs.length.value, "3.937");
    assert.equal(row.inputs.width.value, "0.049");
    form.choose("length", "mm");
    assert.equal(row.inputs.length.value, "100");
    assert.equal(form.exact(row, "width"), "1.23456789");
    assert.equal(row.inputs.width.value, "1.235");
});

test("shared formatting rounds both signs, trims zeros and handles empty input", () => {
    const {format} = formHarness();
    for (const [raw, expected] of [
        ["3.93700787", "3.937"], ["1.96850394", "1.969"], ["0.39370079", "0.394"],
        ["14.39926", "14.399"], ["2.5019", "2.502"], ["-2.5015", "-2.502"],
        ["3.249999999", "3.25"], ["3.20000000", "3.2"], ["1200.00000000", "1200"],
        ["", ""], ["-0.000000", "0"], ["0.000041", "0.000041"],
    ]) assert.equal(format(raw), expected);
});

test("form submission retains exact values and blanks in repeated row order", () => {
    const form = formHarness();
    const first = form.addRow();
    form.addRow({values: ["", "1.23456", "1", "0"], canonical: ["", "", "", ""]});
    form.addRow({values: ["15.7500123", "2", "1", "0"], canonical: ["", "", "", ""]});
    form.init();
    assert.deepEqual(form.formData().getAll("item_length[]"), ["15.749999999999998", "", "15.7500123"]);
    form.edit(first, "length", "15.75");
    assert.deepEqual(form.formData().getAll("item_length[]"), ["15.75", "", "15.7500123"]);
});

test("adding and deleting rows keeps canonical values attached to the correct row", () => {
    const form = formHarness();
    const first = form.addRow();
    form.init();
    const second = form.addRow({values: ["", "", "", "0.00"], canonical: ["", "", "", ""]});
    form.init();
    form.edit(second, "length", "18.123456789");
    const exact = second.canonical.length.value;
    form.remove(first);
    form.init();
    form.choose("length", "mm");
    form.choose("length", "in");
    assert.equal(second.inputs.length.value, "18.123");
    assert.equal(second.canonical.length.value, exact);
    assert.equal(first.canonical.length.value, "400.04999999999995");
});

test("standalone, workflow and new-row templates use continuous physical fields and integer quantities", () => {
    const template = read("../../templates/container_tool/partials/_transport_product_section.html");
    const physical = template.match(/<input[^>]*name="item_(?:length|width|height|weight)\[\]"[^>]*>/g);
    assert.equal(physical.length, 16);
    for (const input of physical) assert.match(input, /step="any".*data-unit-input/);
    const integers = template.match(/<input[^>]*name="item_(?:qty|sequence)\[\]"[^>]*>/g);
    for (const input of integers) assert.doesNotMatch(input, /step="any"|data-unit-input/);
});
