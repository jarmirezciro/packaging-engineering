(function () {
    "use strict";

    const STORAGE_KEY = "kollipackSidebarCollapsed";
    const desktopMedia = window.matchMedia("(min-width: 992px)");
    const root = document.documentElement;
    const sidebar = document.getElementById("appSidebar");
    const desktopToggle = document.getElementById("appSidebarToggle");
    const mobileMenuButton = document.getElementById("appMobileMenuButton");
    const mobileCloseButton = document.getElementById("appSidebarClose");
    const backdrop = document.getElementById("appSidebarBackdrop");

    if (!sidebar || !desktopToggle || !mobileMenuButton || !mobileCloseButton || !backdrop) {
        return;
    }

    const navItems = Array.from(sidebar.querySelectorAll(".app-nav-link"));
    let drawerReturnFocus = null;
    let tooltipInstances = [];

    function readCollapsedPreference() {
        try {
            return window.localStorage.getItem(STORAGE_KEY) === "true";
        } catch (error) {
            return false;
        }
    }

    function writeCollapsedPreference(collapsed) {
        try {
            window.localStorage.setItem(STORAGE_KEY, collapsed ? "true" : "false");
        } catch (error) {
            // Storage can be unavailable in privacy modes; in-page behavior still works.
        }
    }

    function navItemLabel(item) {
        const label = item.querySelector(":scope > span");
        return label ? label.textContent.trim() : "";
    }

    function disposeTooltips() {
        tooltipInstances.forEach(function (tooltip) {
            tooltip.dispose();
        });
        tooltipInstances = [];
        navItems.forEach(function (item) {
            item.removeAttribute("title");
            item.removeAttribute("data-bs-original-title");
        });
    }

    function syncTooltips(collapsed) {
        disposeTooltips();
        if (!collapsed) {
            return;
        }

        navItems.forEach(function (item) {
            const label = navItemLabel(item);
            if (!label) {
                return;
            }
            item.setAttribute("title", label);
            if (!item.hasAttribute("aria-label")) {
                item.setAttribute("aria-label", label);
            }
        });

        if (window.bootstrap && window.bootstrap.Tooltip) {
            tooltipInstances = navItems
                .filter(function (item) { return item.hasAttribute("title"); })
                .map(function (item) {
                    return new window.bootstrap.Tooltip(item, {
                        placement: "right",
                        trigger: "hover focus",
                        container: document.body,
                    });
                });
        }
    }

    function syncDesktopToggle(collapsed) {
        const label = collapsed ? "Expand navigation" : "Collapse navigation";
        const icon = desktopToggle.querySelector("i");
        desktopToggle.setAttribute("aria-label", label);
        desktopToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
        desktopToggle.setAttribute("title", label);
        sidebar.dataset.desktopState = collapsed ? "collapsed" : "expanded";
        if (icon) {
            icon.className = collapsed ? "bi bi-chevron-right" : "bi bi-chevron-left";
        }
    }

    function setDesktopCollapsed(collapsed, persist) {
        const shouldCollapse = desktopMedia.matches && collapsed;
        root.classList.toggle("app-sidebar-collapsed", shouldCollapse);
        syncDesktopToggle(shouldCollapse);
        syncTooltips(shouldCollapse);
        if (persist) {
            writeCollapsedPreference(collapsed);
        }
    }

    function drawerIsOpen() {
        return document.body.classList.contains("app-sidebar-drawer-open");
    }

    function setMobileSidebarAvailability(open) {
        mobileMenuButton.setAttribute("aria-expanded", open ? "true" : "false");
        sidebar.setAttribute("aria-hidden", open ? "false" : "true");
        sidebar.inert = !open;
    }

    function openDrawer() {
        if (desktopMedia.matches || drawerIsOpen()) {
            return;
        }
        drawerReturnFocus = document.activeElement;
        const scrollbarGutter = Math.max(
            0,
            window.innerWidth - document.documentElement.clientWidth
        );
        document.body.style.setProperty(
            "--app-drawer-scrollbar-gutter",
            scrollbarGutter + "px"
        );
        document.body.classList.add("app-sidebar-drawer-open");
        setMobileSidebarAvailability(true);
        window.requestAnimationFrame(function () {
            mobileCloseButton.focus();
        });
    }

    function closeDrawer(restoreFocus) {
        document.body.classList.remove("app-sidebar-drawer-open");
        document.body.style.removeProperty("--app-drawer-scrollbar-gutter");
        setMobileSidebarAvailability(false);
        if (restoreFocus && drawerReturnFocus && typeof drawerReturnFocus.focus === "function") {
            drawerReturnFocus.focus();
        }
        drawerReturnFocus = null;
    }

    function focusableDrawerElements() {
        return Array.from(sidebar.querySelectorAll(
            'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )).filter(function (element) {
            return element.getClientRects().length > 0;
        });
    }

    function handleDrawerKeydown(event) {
        if (!drawerIsOpen() || desktopMedia.matches) {
            return;
        }
        if (event.key === "Escape") {
            event.preventDefault();
            closeDrawer(true);
            return;
        }
        if (event.key !== "Tab") {
            return;
        }

        const focusable = focusableDrawerElements();
        if (!focusable.length) {
            event.preventDefault();
            return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    function handleViewportChange() {
        if (desktopMedia.matches) {
            const focusWasInDrawer = drawerIsOpen() && sidebar.contains(document.activeElement);
            document.body.classList.remove("app-sidebar-drawer-open");
            document.body.style.removeProperty("--app-drawer-scrollbar-gutter");
            sidebar.removeAttribute("aria-hidden");
            sidebar.inert = false;
            mobileMenuButton.setAttribute("aria-expanded", "false");
            setDesktopCollapsed(readCollapsedPreference(), false);
            if (focusWasInDrawer) {
                desktopToggle.focus();
            }
        } else {
            const focusWasOnDesktopToggle = document.activeElement === desktopToggle;
            root.classList.remove("app-sidebar-collapsed");
            syncDesktopToggle(false);
            syncTooltips(false);
            closeDrawer(false);
            if (focusWasOnDesktopToggle) {
                mobileMenuButton.focus();
            }
        }
    }

    desktopToggle.addEventListener("click", function () {
        if (!desktopMedia.matches) {
            return;
        }
        setDesktopCollapsed(!root.classList.contains("app-sidebar-collapsed"), true);
    });
    mobileMenuButton.addEventListener("click", openDrawer);
    mobileCloseButton.addEventListener("click", function () { closeDrawer(true); });
    backdrop.addEventListener("click", function () { closeDrawer(true); });
    document.addEventListener("keydown", handleDrawerKeydown);

    navItems.forEach(function (item) {
        item.addEventListener("click", function () {
            if (!desktopMedia.matches) {
                closeDrawer(false);
            }
        });
    });

    if (typeof desktopMedia.addEventListener === "function") {
        desktopMedia.addEventListener("change", handleViewportChange);
    } else {
        desktopMedia.addListener(handleViewportChange);
    }

    sidebar.addEventListener("transitionend", function (event) {
        if (event.propertyName === "width" || event.propertyName === "transform") {
            window.dispatchEvent(new Event("resize"));
        }
    });

    handleViewportChange();
}());
