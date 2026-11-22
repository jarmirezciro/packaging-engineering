(function () {
    "use strict";

    const fields = [
        "mode", "bag_id", "bag_length", "bag_width", "bag_dimension_unit", "bag_mass_unit",
        "film_preset", "film_preset_override", "film_caliper", "film_caliper_unit", "film_caliper_override",
        "film_grammage", "film_grammage_override", "bag_weight", "bag_weight_override",
    ];

    function bind(panel) {
        const root = panel.closest("[data-bag-tool-root]");
        const form = panel.closest("form");
        if (!root || !form || panel.dataset.bagFilmBound) return;
        panel.dataset.bagFilmBound = "1";
        const suffix = root.dataset.bagPrefix ? "_" + root.dataset.bagPrefix : "";
        const field = (key) => form.elements.namedItem(key + suffix);
        const value = (key) => {
            const input = field(key);
            return input?.matches?.("[data-unit-input]")
                ? window.KolliPackNumericInputs.getValue(input)
                : input?.value ?? "";
        };
        const select = panel.querySelector("[data-bag-film-preset]");
        const weightOverride = panel.querySelector("[data-bag-weight-override]");
        const rows = {caliper: "film_caliper", grammage: "film_grammage", tare: "bag_weight"};
        let timer;
        let pending;

        function enabled(key) {
            return field(key + "_override").value === "1";
        }

        function syncControls() {
            const custom = select.value === "custom";
            field("film_grammage").readOnly = !custom && select.value !== "catalogue";
            field("bag_weight").readOnly = !weightOverride.checked;
            for (const [row, key] of Object.entries(rows)) {
                panel.querySelector(`[data-restore-property="${row}"]`).hidden =
                    !enabled(key) || (row !== "tare" && custom);
            }
        }

        function updateInput(input, nextValue) {
            delete input.dataset.unitCanonicalValue;
            window.KolliPackNumericInputs.setValue(input, nextValue);
        }

        async function preview(signal) {
            const body = new URLSearchParams(fields.map((key) => [key, value(key)]));
            body.set("bag_source", field("bag_source")?.value || "manual");
            body.set("design_length", panel.dataset.designLength);
            body.set("design_width", panel.dataset.designWidth);
            body.set("csrfmiddlewaretoken", form.elements.namedItem("csrfmiddlewaretoken")?.value || "");
            try {
                const response = await fetch(panel.dataset.previewUrl, {method: "POST", body, signal});
                if (!response.ok || signal.aborted) return;
                const previewData = await response.json();
                if (signal.aborted) return;
                for (const [row, key] of Object.entries(rows)) {
                    const editable = enabled(key) || (row !== "tare" && select.value === "custom");
                    if (!editable) updateInput(field(key), previewData.inputs[row]);
                    panel.querySelector(`[data-effective-property-source="${row}"]`).textContent =
                        previewData.sources[row];
                }
                panel.querySelector("[data-bag-film-density]").textContent = previewData.density;
            } catch (error) {
                // A failed preview leaves the form editable for a normal analysis.
            }
        }

        function refresh() {
            syncControls();
            pending?.abort();
            clearTimeout(timer);
            pending = new AbortController();
            const signal = pending.signal;
            timer = setTimeout(() => preview(signal), 150);
        }

        select.addEventListener("change", () => {
            const catalogue = select.value === "catalogue";
            if (!catalogue) field("film_preset").value = select.value;
            field("film_preset_override").value = !catalogue && panel.dataset.catalogueFilm === "1" ? "1" : "0";
            field("film_caliper_override").value = "0";
            field("film_grammage_override").value = "0";
            refresh();
        });

        for (const key of ["film_caliper", "film_grammage"]) {
            field(key).addEventListener("input", () => {
                if (select.value !== "custom") field(key + "_override").value = "1";
                refresh();
            });
        }

        weightOverride.addEventListener("change", () => {
            field("bag_weight_override").value = weightOverride.checked ? "1" : "0";
            if (weightOverride.checked) {
                updateInput(field("bag_weight"), "");
                field("bag_weight").readOnly = false;
                field("bag_weight").focus();
            }
            refresh();
        });
        field("bag_weight").addEventListener("input", refresh);

        for (const [row, key] of Object.entries(rows)) {
            panel.querySelector(`[data-restore-property="${row}"]`).addEventListener("click", () => {
                field(key + "_override").value = "0";
                if (row === "tare") weightOverride.checked = false;
                refresh();
                (row === "tare" ? weightOverride : field(key)).focus();
            });
        }
        for (const key of ["bag_length", "bag_width"]) {
            field(key)?.addEventListener("input", refresh);
        }
        document.addEventListener("kollipack:unit-changed", (event) => {
            if (["film_caliper_unit", "bag_dimension_unit", "bag_mass_unit"]
                .some((key) => field(key)?.dataset.unitGroup === event.detail.group)) refresh();
        });
        syncControls();
    }

    function init() {
        document.querySelectorAll("[data-bag-film-panel]").forEach(bind);
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
