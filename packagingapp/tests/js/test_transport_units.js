"use strict";

const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const {test} = require("node:test");
const {runInNewContext} = require("node:vm");

const read = name => readFileSync(path.resolve(__dirname, name), "utf8");
const unitScript = read("../../../static/js/unit_selector.js");
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
    runInNewContext(unitScript, context);
    const api = context.window.KolliPackUnitSelector;
    return {
        api,
        addRow({values = ["15.75", "63.00", "39.40", "661.38"],
            canonical = [400.04999999999995, 1600.1999999999998, 1000.7599999999998, 300.000000123],
            precision = "2", source = "manual"} = {}) {
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
                    dataset: {unitGroup: groups[quantity]},
                    closest: selector => selector === "tr" ? row : form,
                    matches: query => query === "input[data-unit-input]",
                });
                if (precision !== null) input.dataset.unitDisplayPrecision = precision;
                if (canonical[index] !== "") {
                    input.dataset.unitCanonicalValue = String(canonical[index]);
                    input.dataset.unitCanonicalUnit = key === "weight" ? "kg" : "mm";
                }
                row.inputs[key] = input;
                row.canonical[key] = {value: String(canonical[index])};
                input.addEventListener("input", () => context.transportMarkRowManual(input));
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
            row.inputs[key].value = value;
            row.inputs[key].dispatchEvent(new Event("input"));
        },
        remove: row => rows.splice(rows.indexOf(row), 1),
    };
}

test("initialization preserves exact server canonical values beside rounded inputs", () => {
    const form = formHarness();
    const row = form.addRow();
    form.init();
    assert.equal(form.api.getCanonicalValue(row.inputs.length, "length"), 400.04999999999995);
    assert.equal(form.api.getCanonicalValue(row.inputs.weight, "mass"), 300.000000123 * 1000);
    assert.equal(row.canonical.weight.value, "300.000000123");
    form.init();
    assert.equal(form.api.getCanonicalValue(row.inputs.length, "length"), 400.04999999999995);
});

test("all supported unit switches retain canonical precision and fixed two-decimal text", () => {
    const form = formHarness();
    const row = form.addRow();
    form.init();
    for (let cycle = 0; cycle < 10; cycle++) {
        for (const unit of ["mm", "cm", "m", "ft", "in"]) form.choose("length", unit);
        for (const unit of ["kg", "g", "t", "oz", "lb"]) form.choose("mass", unit);
        assert.deepEqual(Object.values(row.inputs).map(input => input.value), ["15.75", "63.00", "39.40", "661.39"]);
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
    form.choose("mass", "kg");
    form.choose("mass", "lb");
    assert.equal(row.inputs.weight.value, "662.12");
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

test("canonical imports and rounded zero are formatted without conversion drift", () => {
    const form = formHarness();
    const row = form.addRow();
    form.init();
    form.api.setCanonicalValue(row.inputs.length, 1600.1999999999998, "mm");
    assert.equal(row.inputs.length.value, "63.00");
    form.api.setCanonicalValue(row.inputs.weight, -0.000001, "kg");
    assert.equal(row.inputs.weight.value, "0.00");
    form.api.setCanonicalValue(row.inputs.height, null, "mm");
    assert.equal(row.inputs.height.value, "");
});

test("precision remains opt-in for other tools", () => {
    const form = formHarness({dimension: "mm"});
    const row = form.addRow({values: ["1.23456789", "1", "1", "0"],
        canonical: ["", "", "", ""], precision: null});
    form.init();
    form.choose("length", "in");
    assert.equal(row.inputs.length.value, "0.04860504");
    form.choose("length", "mm");
    assert.equal(row.inputs.length.value, "1.23456789");
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
    assert.equal(second.inputs.length.value, "18.12");
    assert.equal(second.canonical.length.value, exact);
    assert.equal(first.canonical.length.value, "400.04999999999995");
});

test("standalone, workflow and new-row templates opt in only physical inputs", () => {
    const template = read("../../templates/container_tool/partials/_transport_product_section.html");
    const physical = template.match(/<input[^>]*name="item_(?:length|width|height|weight)\[\]"[^>]*>/g);
    assert.equal(physical.length, 16);
    for (const input of physical) assert.match(input, /data-unit-display-precision="2"/);
    const integers = template.match(/<input[^>]*name="item_(?:qty|sequence)\[\]"[^>]*>/g);
    for (const input of integers) assert.doesNotMatch(input, /data-unit-display-precision/);
});
