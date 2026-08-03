(function () {
    "use strict";

    function selectedValue(name) {
        var node = document.querySelector('input[name="' + name + '"]:checked, select[name="' + name + '"]');
        return node ? node.value : "";
    }

    function setVisible(node, visible) {
        if (!node) return;
        node.hidden = !visible;
    }

    function boardMetadata() {
        var node = document.getElementById("corrugated-board-metadata");
        return node ? JSON.parse(node.textContent || "[]") : [];
    }

    function updateBoardMetadata() {
        var select = document.querySelector('select[name="board_construction_id"]');
        if (!select) return;
        var item = boardMetadata().find(function (entry) { return String(entry.id) === String(select.value); });
        var meta = document.querySelector("[data-corrugated-selected-board]");
        if (!item || !meta) return;
        meta.querySelector("dd:nth-of-type(1)");
        var values = meta.querySelectorAll("dd");
        if (values[0]) values[0].textContent = (item.wall_type || "") + " · " + (item.flute || "");
        if (values[1]) values[1].textContent = (item.combined_grammage_g_m2 || "—") + " g/m²";
        if (values[2]) values[2].textContent = (item.nominal_flute_height_mm || "—") + " mm (not caliper)";
        if (values[3]) values[3].textContent = item.ect_kn_m && item.caliper_mm ? "ECT " + item.ect_kn_m + " kN/m · caliper " + item.caliper_mm + " mm" : "Not included";
        if (values[4]) values[4].textContent = (item.source_type || "") + " · " + (item.source_label || "");
    }

    function updatePalletDimensions() {
        var select = document.querySelector('select[name="pallet_code"]');
        var node = document.getElementById("corrugated-pallet-metadata");
        if (!select || !node) return;
        var item = JSON.parse(node.textContent || "[]").find(function (entry) { return String(entry.id) === String(select.value); });
        if (!item) return;
        [["pallet_length_mm", item.length_mm], ["pallet_width_mm", item.width_mm], ["pallet_height_mm", item.height_mm], ["pallet_weight_kg", item.weight_kg]].forEach(function (pair) {
            var field = document.querySelector('input[name="' + pair[0] + '"]');
            if (field && pair[1] !== null && pair[1] !== undefined) field.value = pair[1];
        });
    }

    function updateVisibility() {
        setVisible(document.querySelector("[data-corrugated-board-catalogue]"), selectedValue("board_mode") === "catalogue");
        setVisible(document.querySelector("[data-corrugated-board-manual]"), selectedValue("board_mode") === "manual");
        setVisible(document.querySelector("[data-corrugated-catalogue-pallet]"), selectedValue("pallet_source") === "catalogue");
        setVisible(document.querySelector("[data-corrugated-custom-distribution]"), selectedValue("distribution_profile") === "CUSTOM");
        setVisible(document.querySelector("[data-corrugated-custom-carbon]"), selectedValue("co2_mode") === "CUSTOM");
        setVisible(document.querySelector("[data-corrugated-flute-2]"), selectedValue("manual_wall_type") === "DOUBLE_WALL");
        updateBoardMetadata();
        updatePalletDimensions();
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("input[name=board_mode], input[name=pallet_source], select[name=manual_wall_type], select[name=distribution_profile], input[name=co2_mode], select[name=board_construction_id], select[name=pallet_code]").forEach(function (node) {
            node.addEventListener("change", updateVisibility);
        });
        updateVisibility();
    });
}());
