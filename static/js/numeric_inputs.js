(function () {
    "use strict";

    const selector = 'input[type="number"]';
    const exactValues = new WeakMap();
    const formatter = new Intl.NumberFormat("en-US", {
        maximumFractionDigits: 3,
        useGrouping: false,
    });

    function isContinuous(input) {
        if (!input.matches?.(selector)) return false;
        const step = Number(input.step);
        return input.step === "any" || (step > 0 && !Number.isInteger(step));
    }

    function format(value) {
        if (value === "" || value == null) return "";
        const number = Number(value);
        if (!Number.isFinite(number)) return String(value);
        const rounded = formatter.format(number === 0 ? 0 : number);
        // Keep small nonzero inputs distinguishable from a genuine zero.
        return number !== 0 && Number(rounded) === 0 ? String(value) : rounded;
    }

    function getValue(input) {
        const exact = exactValues.get(input);
        return exact && input.value === exact.display ? exact.raw : input.value;
    }

    function validationState(input) {
        const {rangeUnderflow, rangeOverflow, stepMismatch} = input.validity;
        return [rangeUnderflow, rangeOverflow, stepMismatch].join();
    }

    function commit(input) {
        if (!isContinuous(input) || input.validity.badInput) return;
        const raw = getValue(input);
        const display = format(raw);
        if (input.value === display) return;
        const original = input.value;
        const validation = validationState(input);
        input.value = display;
        // A rounded value can cross a bound or fall off the field's step grid.
        if (input.value !== display || validationState(input) !== validation) {
            input.value = original;
            return;
        }
        exactValues.set(input, {raw, display});
    }

    function setValue(input, value) {
        exactValues.delete(input);
        input.value = value == null ? "" : String(value);
        commit(input);
    }

    function restoreFormData(event) {
        const fields = new Map();
        for (const input of event.target.elements) {
            if (!input.name || !input.matches(selector) || input.matches(":disabled")) continue;
            if (!fields.has(input.name)) fields.set(input.name, []);
            fields.get(input.name).push(input);
        }
        for (const [name, inputs] of fields) {
            const exact = inputs.map(getValue);
            if (inputs.every((input, index) => input.value === exact[index])) continue;
            const submitted = event.formData.getAll(name);
            // Transport repeats names across rows. Match the browser's actual
            // successful entries before replacing them in the same row order.
            if (submitted.length !== inputs.length
                || inputs.some((input, index) => input.value !== submitted[index])) continue;
            event.formData.set(name, exact[0]);
            for (const value of exact.slice(1)) event.formData.append(name, value);
        }
    }

    function init() {
        document.querySelectorAll(selector).forEach(commit);
        new MutationObserver((records) => {
            for (const record of records) {
                for (const node of record.addedNodes) {
                    if (node.nodeType !== 1) continue;
                    commit(node);
                    node.querySelectorAll(selector).forEach(commit);
                }
            }
        }).observe(document.body, {childList: true, subtree: true});
    }

    // Clear the saved value before tool-specific input handlers read a user edit,
    // even when the user retypes exactly the same text as the rounded display.
    document.addEventListener("input", (event) => exactValues.delete(event.target), true);
    document.addEventListener("blur", (event) => commit(event.target), true);
    document.addEventListener("formdata", restoreFormData, true);
    window.KolliPackNumericInputs = Object.freeze({format, getValue, setValue, commit});
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
