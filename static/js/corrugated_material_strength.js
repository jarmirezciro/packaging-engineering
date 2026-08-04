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

    function metadata(id, fallback) {
        var node = document.getElementById(id);
        return node ? JSON.parse(node.textContent || fallback) : [];
    }

    function boardMetadata() {
        return metadata("corrugated-board-metadata", "[]");
    }

    function referenceMetadata() {
        return metadata("corrugated-reference-grade-metadata", "[]");
    }

    function selectedBoard() {
        var select = document.querySelector('select[name="board_construction_id"]');
        if (select) {
            return boardMetadata().find(function (entry) { return String(entry.id) === String(select.value); }) || null;
        }
        return null;
    }

    function selectedFluteFamily() {
        var board = selectedBoard();
        if (selectedValue("board_mode") === "catalogue" && board) return board.flute || "";
        var flute1 = selectedValue("manual_flute_1");
        var flute2 = selectedValue("manual_flute_2");
        return selectedValue("manual_wall_type") === "DOUBLE_WALL" ? flute1 + flute2 : flute1;
    }

    function updateBoardMetadata() {
        var item = selectedBoard();
        var meta = document.querySelector("[data-corrugated-selected-board]");
        if (!item || !meta) return;
        var values = meta.querySelectorAll("dd");
        if (values[0]) values[0].textContent = (item.wall_type || "") + " · " + (item.flute || "");
        if (values[1]) values[1].textContent = (item.combined_grammage_g_m2 || "—") + " g/m²";
        if (values[2]) values[2].textContent = (item.caliper_mm || "Not stored") + (item.caliper_mm ? " mm" : "");
        if (values[3]) values[3].textContent = item.ect_kn_m ? "ECT " + item.ect_kn_m + " kN/m" : "Not stored";
        if (values[4]) values[4].textContent = item.measured_bct_n ? item.measured_bct_n + " N" : "Not stored";
        if (values[5]) values[5].textContent = (item.source_type || "") + " · " + (item.source_label || "");
    }

    function updateReferenceGrades() {
        var select = document.querySelector('select[name="reference_ect_grade_id"]');
        var info = document.querySelector("[data-corrugated-selected-reference]");
        if (!select) return;
        var family = selectedFluteFamily();
        var selected = null;
        referenceMetadata().forEach(function (entry) {
            if (String(entry.id) === String(select.value)) selected = entry;
        });
        var compatible = true;
        Array.prototype.forEach.call(select.options, function (option) {
            if (!option.value) {
                option.hidden = false;
                option.disabled = false;
                return;
            }
            var entry = referenceMetadata().find(function (item) { return String(item.id) === String(option.value); });
            var visible = !family || (entry && entry.flute_family === family);
            option.hidden = !visible;
            option.disabled = !visible;
            if (!visible && option.selected) compatible = false;
        });
        if (!compatible) {
            select.value = "";
            selected = null;
        }
        if (info) {
            if (!selected || !compatible) {
                info.textContent = family ? "Select a reference category compatible with " + family + "." : "Select a board construction or manual flute to filter categories.";
            } else {
                info.textContent = selected.flute_family + " · " + selected.ect_lb_in + " ECT · " + Number(selected.ect_kn_m).toFixed(3) + " kN/m · reference caliper " + selected.reference_caliper_mm + " mm · " + (selected.caliper_basis || "reference value");
            }
        }
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
        updateReferenceGrades();
        updatePalletDimensions();
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("input[name=board_mode], input[name=pallet_source], select[name=manual_wall_type], select[name=manual_flute_1], select[name=manual_flute_2], select[name=distribution_profile], input[name=co2_mode], select[name=board_construction_id], select[name=reference_ect_grade_id], select[name=pallet_code]").forEach(function (node) {
            node.addEventListener("change", updateVisibility);
        });
        updateVisibility();
    });
}());
