(function () {
    "use strict";

    const STORAGE_KEY = "kollipack.tool-scroll.pending.v1";
    const MARKER_SELECTOR = "[data-preserve-tool-scroll]";
    const MAX_STATE_AGE_MS = 30000;

    function currentPageKey() {
        return window.location.pathname + window.location.search;
    }

    function markerFor(element) {
        return element && element.closest ? element.closest(MARKER_SELECTOR) : null;
    }

    function writePendingState(element) {
        const marker = markerFor(element);
        const markerKey = marker?.getAttribute("data-preserve-tool-scroll");
        if (!marker || !markerKey) return;

        const state = {
            page: currentPageKey(),
            marker: markerKey,
            viewportTop: marker.getBoundingClientRect().top,
            innerScroll: Array.from(marker.querySelectorAll("[data-preserve-inner-scroll]")).map(function (scrollArea) {
                return {
                    key: scrollArea.getAttribute("data-preserve-inner-scroll"),
                    top: scrollArea.scrollTop,
                    left: scrollArea.scrollLeft,
                };
            }).filter(function (entry) { return entry.key; }),
            createdAt: Date.now(),
        };

        try {
            window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (error) {
            // Storage can be unavailable in restricted browser modes. Submitting
            // the tool must still work even when position restoration cannot.
        }
    }

    function submit(element) {
        if (!element) return;
        writePendingState(element);
        element.submit();
    }

    function takePendingState() {
        let rawState = null;
        try {
            rawState = window.sessionStorage.getItem(STORAGE_KEY);
            window.sessionStorage.removeItem(STORAGE_KEY);
        } catch (error) {
            return null;
        }

        if (!rawState) return null;

        try {
            return JSON.parse(rawState);
        } catch (error) {
            return null;
        }
    }

    function findMarker(markerKey) {
        return Array.from(document.querySelectorAll(MARKER_SELECTOR)).find(function (element) {
            return element.getAttribute("data-preserve-tool-scroll") === markerKey;
        }) || null;
    }

    function restoreInnerScroll(marker, entries) {
        if (!Array.isArray(entries)) return;
        const scrollAreas = Array.from(marker.querySelectorAll("[data-preserve-inner-scroll]"));
        entries.forEach(function (entry) {
            const scrollArea = scrollAreas.find(function (element) {
                return element.getAttribute("data-preserve-inner-scroll") === entry.key;
            });
            if (!scrollArea) return;
            scrollArea.scrollTop = Number(entry.top) || 0;
            scrollArea.scrollLeft = Number(entry.left) || 0;
        });
    }

    function navigationType() {
        const navigationEntry = window.performance?.getEntriesByType?.("navigation")?.[0];
        return navigationEntry?.type || "";
    }

    function validationTarget(marker) {
        const error = marker.querySelector(
            "[data-tool-validation-errors], [aria-invalid='true'], .is-invalid, .errorlist"
        );
        if (!error) return null;

        if (error.matches("input, select, textarea, button, [tabindex]")) return error;
        return error.querySelector("input, select, textarea, button, [tabindex]") || error;
    }

    function restorePendingState() {
        const state = takePendingState();
        if (!state) return;

        const stateAge = Date.now() - Number(state.createdAt || 0);
        const shouldIgnore = (
            state.page !== currentPageKey()
            || !state.marker
            || !Number.isFinite(Number(state.viewportTop))
            || stateAge < 0
            || stateAge > MAX_STATE_AGE_MS
            || window.location.hash
            || navigationType() === "back_forward"
        );
        if (shouldIgnore) return;

        const marker = findMarker(state.marker);
        if (!marker) return;

        // Wait for the initial render and native scroll handling to settle, then
        // make one layout-relative adjustment. This avoids fixed pixel offsets,
        // timers, polling, and repeated viewport movement.
        window.requestAnimationFrame(function () {
            restoreInnerScroll(marker, state.innerScroll);
            const invalid = validationTarget(marker);
            if (invalid) {
                if (typeof invalid.focus === "function") {
                    invalid.focus({ preventScroll: true });
                }
                invalid.scrollIntoView({ block: "center", behavior: "instant" });
                return;
            }

            const delta = marker.getBoundingClientRect().top - Number(state.viewportTop);
            if (Math.abs(delta) > 1) {
                window.scrollBy({ top: delta, left: 0, behavior: "instant" });
            }
        });
    }

    window.KolliPackToolScroll = Object.freeze({
        preserve: writePendingState,
        submit: submit,
    });

    // Native submits are captured here. Tool scripts that use form.submit(),
    // which does not dispatch a submit event, call KolliPackToolScroll.submit.
    document.addEventListener("submit", function (event) {
        writePendingState(event.target);
    }, true);

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", restorePendingState, { once: true });
    } else {
        restorePendingState();
    }
})();
