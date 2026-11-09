(function () {
    "use strict";

    // Full Packaging Flow includes several tool script partials on one page.
    if (window.KolliPackUnitSelector) return;

    // Keep all browser-side factors together.  The server remains the
    // authoritative conversion boundary; these factors only prevent a
    // surprising round trip while the user edits the form.
    const FACTORS_TO_BASE = Object.freeze({
        length: Object.freeze({
            mm: 1,
            cm: 10,
            m: 1000,
            in: 25.4,
            ft: 304.8,
        }),
        mass: Object.freeze({
            g: 1,
            kg: 1000,
            t: 1000000,
            oz: 28.349523125,
            lb: 453.59237,
        }),
    });
    const numericInputs = window.KolliPackNumericInputs;
    const inputOrigins = new WeakMap();

    function unitKey(value, quantity) {
        const key = String(value || "").trim().toLowerCase();
        return FACTORS_TO_BASE[quantity] && FACTORS_TO_BASE[quantity][key]
            ? key
            : (quantity === "mass" ? "g" : "mm");
    }

    function numericValue(value) {
        if (value === "" || value === null || value === undefined) return null;
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }

    function formatCatalogueDisplayValue(baseValue, unit, quantity) {
        const factor = FACTORS_TO_BASE[quantity][unit];
        const displayValue = baseValue / factor;
        if (!Number.isFinite(displayValue)) return "—";
        if (Object.is(displayValue, -0) || displayValue === 0) return "0";
        return displayValue.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
    }

    function groupNodes(group) {
        return Array.from(document.querySelectorAll(`[data-unit-group="${CSS.escape(group)}"]`));
    }

    function groupInputs(group) {
        return groupNodes(group).filter((node) => node.matches("input[data-unit-input]"));
    }

    function groupDisplays(group) {
        return groupNodes(group).filter((node) => node.matches("[data-unit-display]"));
    }

    function groupHiddenInput(group) {
        return groupNodes(group).find((node) => node.matches("input[data-unit-hidden]"));
    }

    function groupSelectors(group) {
        return groupNodes(group).filter((node) => node.matches("[data-unit-selector]"));
    }

    function currentUnit(group, quantity) {
        const hidden = groupHiddenInput(group);
        return unitKey(hidden ? hidden.value : "", quantity);
    }

    function inputQuantity(input, canonicalUnit) {
        const group = input.dataset.unitGroup;
        const selector = document.querySelector(
            `[data-unit-selector][data-unit-group="${CSS.escape(group)}"]`
        );
        const knownUnit = canonicalUnit || groupHiddenInput(group)?.value;
        return selector?.dataset.unitQuantity || (FACTORS_TO_BASE.mass[knownUnit] ? "mass" : "length");
    }

    function canonicalValue(input, quantity) {
        if (!input) return null;
        const stored = numericValue(input.dataset && input.dataset.unitCanonicalValue);
        if (stored !== null) return stored;

        const exact = numericValue(numericInputs.getValue(input));
        if (exact === null) return null;
        const unit = currentUnit(input.dataset.unitGroup, quantity);
        return exact * FACTORS_TO_BASE[quantity][unit];
    }

    function fromCanonicalValue(value, unit, quantity) {
        const numeric = numericValue(value);
        if (numeric === null) return null;
        const targetUnit = unitKey(unit, quantity);
        return numeric / FACTORS_TO_BASE[quantity][targetUnit];
    }

    function updateOptionState(selector, selectedUnit) {
        selector.querySelectorAll("[data-unit-option]").forEach((option) => {
            const selected = option.dataset.unit === selectedUnit;
            option.setAttribute("aria-selected", selected ? "true" : "false");
            const check = option.querySelector(".unit-selector-check");
            if (check) check.textContent = selected ? "✓" : "";
        });
    }

    function setVisibleUnit(group, selectedUnit) {
        groupSelectors(group).forEach((selector) => {
            const symbol = selector.querySelector("[data-unit-symbol]");
            if (symbol) symbol.textContent = selectedUnit;
            updateOptionState(selector, selectedUnit);
        });
        groupNodes(group).filter((node) => node.matches("[data-unit-label]"))
            .forEach((label) => { label.textContent = selectedUnit; });
        const hidden = groupHiddenInput(group);
        if (hidden) hidden.value = selectedUnit;
    }

    function recordCanonicalValue(input, unit, quantity) {
        const raw = numericInputs.getValue(input);
        const exact = numericValue(raw);
        if (exact === null) {
            delete input.dataset.unitCanonicalValue;
            inputOrigins.delete(input);
            return;
        }
        input.dataset.unitCanonicalValue = String(exact * FACTORS_TO_BASE[quantity][unit]);
        inputOrigins.set(input, {unit, raw});
    }

    function writeConvertedValue(input, baseValue, unit, quantity) {
        const origin = inputOrigins.get(input);
        const value = baseValue / FACTORS_TO_BASE[quantity][unit];
        let raw = origin?.unit === unit ? origin.raw : String(value);
        // Catalogue ModelForms already limit submitted display values to
        // 12 decimals before quantizing to the model's canonical scale.
        const places = Number(input.dataset.unitSubmissionDecimals);
        if (origin?.unit !== unit && Number.isInteger(places) && places > 0 && places <= 20) {
            const bounded = value.toFixed(places);
            if (Number(bounded) !== 0 || value === 0) {
                raw = bounded.replace(/0+$/, "").replace(/\.$/, "");
            }
        }
        numericInputs.setValue(input, Number.isFinite(value) ? raw : "");
    }

    function convertGroup(group, quantity, fromUnit, toUnit) {
        groupInputs(group).forEach((input) => {
            if (numericValue(input.dataset.unitCanonicalValue) === null) {
                recordCanonicalValue(input, fromUnit, quantity);
            }
            const baseValue = numericValue(input.dataset.unitCanonicalValue);
            if (baseValue === null) {
                numericInputs.setValue(input, "");
                return;
            }
            writeConvertedValue(input, baseValue, toUnit, quantity);
        });
    }

    function convertDisplayGroup(group, quantity, toUnit) {
        groupDisplays(group).forEach((display) => {
            const canonical = numericValue(display.dataset.unitCanonical);
            if (canonical === null) {
                display.textContent = "—";
                return;
            }
            const canonicalUnit = unitKey(display.dataset.unitCanonicalUnit, quantity);
            const baseValue = canonical * FACTORS_TO_BASE[quantity][canonicalUnit];
            display.textContent = formatCatalogueDisplayValue(baseValue, toUnit, quantity);
        });
    }

    function setCanonicalValue(input, canonicalValue, canonicalUnit) {
        if (!input || !input.dataset || !input.dataset.unitGroup) return;
        const group = input.dataset.unitGroup;
        const quantity = inputQuantity(input, canonicalUnit);
        const numeric = numericValue(canonicalValue);
        if (numeric === null) {
            numericInputs.setValue(input, "");
            delete input.dataset.unitCanonicalValue;
            inputOrigins.delete(input);
            return;
        }
        const sourceUnit = unitKey(canonicalUnit, quantity);
        const baseValue = numeric * FACTORS_TO_BASE[quantity][sourceUnit];
        const targetUnit = currentUnit(group, quantity);
        inputOrigins.set(input, {unit: sourceUnit, raw: String(canonicalValue)});
        writeConvertedValue(input, baseValue, targetUnit, quantity);
        input.dataset.unitCanonicalValue = String(baseValue);
    }

    function setCanonicalDisplay(display, canonicalValue, canonicalUnit) {
        if (!display || !display.dataset || !display.dataset.unitGroup) return;
        const group = display.dataset.unitGroup;
        const selector = document.querySelector(
            `[data-unit-selector][data-unit-group="${CSS.escape(group)}"]`
        );
        const quantity = selector?.dataset.unitQuantity || "length";
        const numeric = numericValue(canonicalValue);
        if (numeric === null) {
            display.textContent = "—";
            delete display.dataset.unitCanonical;
            return;
        }
        const sourceUnit = unitKey(canonicalUnit, quantity);
        const baseValue = numeric * FACTORS_TO_BASE[quantity][sourceUnit];
        const targetUnit = currentUnit(group, quantity);
        display.dataset.unitCanonical = String(numeric);
        display.dataset.unitCanonicalUnit = sourceUnit;
        display.textContent = formatCatalogueDisplayValue(baseValue, targetUnit, quantity);
    }

    function storedUnit(storageKey, quantity) {
        if (!storageKey) return null;
        try {
            const saved = window.localStorage.getItem(storageKey);
            return saved ? unitKey(saved, quantity) : null;
        } catch (error) {
            return null;
        }
    }

    function rememberUnit(storageKey, unit) {
        if (!storageKey) return;
        try {
            window.localStorage.setItem(storageKey, unit);
        } catch (error) {
            // The page remains usable when browser storage is unavailable.
        }
    }

    function updateUrlParam(param, value) {
        if (!param || !window.history || !window.history.replaceState) return;
        try {
            const url = new URL(window.location.href);
            url.searchParams.set(param, value);
            window.history.replaceState({}, "", url.toString());
        } catch (error) {
            // URL state is an enhancement; the visible selector still works.
        }
    }

    function appendCurrentCatalogueUnits(link) {
        const url = new URL(link.href, window.location.href);
        document.querySelectorAll("input[data-catalogue-unit-state]").forEach((input) => {
            if (input.name && input.value) url.searchParams.set(input.name, input.value);
        });
        link.href = url.toString();
    }

    function closeAll(except) {
        document.querySelectorAll("[data-unit-selector].is-open").forEach((selector) => {
            if (selector === except) return;
            selector.classList.remove("is-open");
            const menu = selector.querySelector(".unit-selector-menu");
            const trigger = selector.querySelector(".unit-selector-trigger");
            if (menu) menu.hidden = true;
            if (trigger) trigger.setAttribute("aria-expanded", "false");
        });
    }

    function openSelector(selector) {
        closeAll(selector);
        const menu = selector.querySelector(".unit-selector-menu");
        const trigger = selector.querySelector(".unit-selector-trigger");
        if (!menu || !trigger) return;
        selector.classList.add("is-open");
        menu.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
    }

    function closeSelector(selector, returnFocus) {
        if (!selector) return;
        selector.classList.remove("is-open");
        const menu = selector.querySelector(".unit-selector-menu");
        const trigger = selector.querySelector(".unit-selector-trigger");
        if (menu) menu.hidden = true;
        if (trigger) {
            trigger.setAttribute("aria-expanded", "false");
            if (returnFocus) trigger.focus();
        }
    }

    function notifyUnitChanged(group, quantity, unit) {
        document.dispatchEvent(new CustomEvent("kollipack:unit-changed", {
            detail: { group, quantity, unit },
        }));
    }

    function chooseUnit(selector, selectedUnit) {
        const group = selector.dataset.unitGroup;
        const quantity = selector.dataset.unitQuantity;
        const fromUnit = currentUnit(group, quantity);
        const toUnit = unitKey(selectedUnit, quantity);
        convertGroup(group, quantity, fromUnit, toUnit);
        convertDisplayGroup(group, quantity, toUnit);
        setVisibleUnit(group, toUnit);
        notifyUnitChanged(group, quantity, toUnit);
        rememberUnit(selector.dataset.unitStorageKey, toUnit);
        updateUrlParam(selector.dataset.unitUrlParam, toUnit);
        closeAll();
        selector.querySelector(".unit-selector-trigger")?.focus();
    }

    function init() {
        document.querySelectorAll("[data-unit-input]").forEach((input) => {
            if (input.dataset.unitSelectorBound === "true") return;
            input.dataset.unitSelectorBound = "true";
            const quantity = inputQuantity(input, input.dataset.unitCanonicalUnit);
            const unit = currentUnit(input.dataset.unitGroup, quantity);
            const canonical = numericValue(input.dataset.unitCanonicalValue);
            if (canonical === null) {
                recordCanonicalValue(input, unit, quantity);
            } else {
                const sourceUnit = input.dataset.unitCanonicalUnit;
                if (sourceUnit) {
                    input.dataset.unitCanonicalValue = String(canonical * FACTORS_TO_BASE[quantity][unitKey(sourceUnit, quantity)]);
                }
                inputOrigins.set(input, {unit, raw: numericInputs.getValue(input)});
            }
            input.addEventListener("input", () => {
                recordCanonicalValue(input, currentUnit(input.dataset.unitGroup, quantity), quantity);
            });
        });

        const notifiedGroups = new Set();
        document.querySelectorAll("[data-unit-selector]").forEach((selector) => {
            if (selector.dataset.unitSelectorBound === "true") return;
            selector.dataset.unitSelectorBound = "true";
            const trigger = selector.querySelector(".unit-selector-trigger");
            if (!trigger) return;

            trigger.addEventListener("click", () => {
                if (selector.classList.contains("is-open")) closeSelector(selector, false);
                else openSelector(selector);
            });

            trigger.addEventListener("keydown", (event) => {
                if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openSelector(selector);
                    selector.querySelector("[data-unit-option]")?.focus();
                }
            });

            selector.querySelectorAll("[data-unit-option]").forEach((option) => {
                option.addEventListener("click", () => chooseUnit(selector, option.dataset.unit));
                option.addEventListener("keydown", (event) => {
                    if (event.key === "Escape") {
                        event.preventDefault();
                        closeSelector(selector, true);
                    }
                });
            });

            const group = selector.dataset.unitGroup;
            const quantity = selector.dataset.unitQuantity;
            const saved = storedUnit(selector.dataset.unitStorageKey, quantity);
            const selected = saved || currentUnit(group, quantity);
            if (saved && saved !== currentUnit(group, quantity)) {
                convertGroup(group, quantity, currentUnit(group, quantity), selected);
            }
            convertDisplayGroup(group, quantity, selected);
            setVisibleUnit(group, selected);
            if (!notifiedGroups.has(group)) {
                notifyUnitChanged(group, quantity, selected);
                notifiedGroups.add(group);
            }
        });

        if (document.documentElement.dataset.unitSelectorDocumentBound !== "true") {
            document.documentElement.dataset.unitSelectorDocumentBound = "true";
            document.addEventListener("click", (event) => {
                if (!event.target.closest("[data-unit-selector]")) closeAll();
            });
            document.addEventListener("keydown", (event) => {
                if (event.key === "Escape") closeAll();
            });
            document.addEventListener("click", (event) => {
                const link = event.target.closest("a[data-preserve-catalogue-units]");
                if (link) appendCurrentCatalogueUnits(link);
            });
        }
    }

    window.KolliPackUnitSelector = Object.freeze({
        init,
        setCanonicalValue,
        setCanonicalDisplay,
        getCanonicalValue: canonicalValue,
        getGroupUnit: currentUnit,
        fromCanonicalValue,
        normalizeUnit: unitKey,
    });

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
