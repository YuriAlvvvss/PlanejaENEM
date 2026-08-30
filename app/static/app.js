document.addEventListener("DOMContentLoaded", () => {
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

    const toggles = document.querySelectorAll("[data-sidebar-toggle]");
    toggles.forEach((button) => {
        button.addEventListener("click", () => {
            document.body.classList.toggle("sidebar-open");
        });
    });
});
