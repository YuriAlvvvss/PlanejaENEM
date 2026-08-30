document.addEventListener("DOMContentLoaded", () => {
    const savedTheme = localStorage.getItem("planejaenem-theme") || "dark";
    document.body.setAttribute("data-theme", savedTheme);

    const themeToggle = document.querySelector("[data-theme-toggle]");
    const applyThemeState = () => {
        const theme = document.body.getAttribute("data-theme");
        const isDark = theme === "dark";
        if (themeToggle) {
            themeToggle.classList.toggle("is-light", !isDark);
            themeToggle.setAttribute("aria-label", isDark ? "Ativar tema claro" : "Ativar tema escuro");
        }
    };
    applyThemeState();

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const nextTheme = document.body.getAttribute("data-theme") === "dark" ? "light" : "dark";
            document.body.setAttribute("data-theme", nextTheme);
            localStorage.setItem("planejaenem-theme", nextTheme);
            applyThemeState();
        });
    }

    const tabs = document.querySelectorAll(".view-tab");
    const panels = document.querySelectorAll("[data-panel]");

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            const view = tab.dataset.view;
            tabs.forEach((item) => {
                const active = item === tab;
                item.classList.toggle("is-active", active);
                item.setAttribute("aria-selected", active ? "true" : "false");
            });
            panels.forEach((panel) => {
                panel.hidden = panel.dataset.panel !== view;
            });
        });
    });

    const sidebarToggles = document.querySelectorAll("[data-sidebar-toggle]");
    const closeSidebar = () => {
        document.body.classList.remove("sidebar-open");
        sidebarToggles.forEach((button) => {
            button.setAttribute("aria-expanded", "false");
        });
    };

    const openSidebar = () => {
        document.body.classList.add("sidebar-open");
        sidebarToggles.forEach((button) => {
            button.setAttribute("aria-expanded", "true");
        });
    };

    sidebarToggles.forEach((button) => {
        button.addEventListener("click", () => {
            const isOpen = document.body.classList.contains("sidebar-open");
            if (isOpen) {
                closeSidebar();
                return;
            }
            openSidebar();
        });
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeSidebar();
        }
    });
});
