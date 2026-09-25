document.addEventListener("DOMContentLoaded", () => {
    const serverTheme = document.body.getAttribute("data-theme") === "light" ? "light" : "dark";
    const savedTheme = localStorage.getItem("planejaenem-theme") || serverTheme;
    document.body.setAttribute("data-theme", savedTheme);

    const themeToggle = document.querySelector("[data-theme-toggle]");
    const persistTheme = (theme) => {
        try {
            const endpoint = themeToggle && themeToggle.dataset.endpoint;
            const csrfToken = themeToggle && themeToggle.dataset.csrfToken;
            if (!endpoint || !csrfToken) {
                return;
            }
            fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: new URLSearchParams({ theme, csrf_token: csrfToken }),
            }).catch(() => {});
        } catch (error) {
            /* preferência local já aplicada; servidor sincroniza depois */
        }
    };
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
            persistTheme(nextTheme);
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

    const sidebarCollapseBtn = document.querySelector("[data-sidebar-collapse]");
    const COLLAPSE_KEY = "planejaenem-sidebar-collapsed";

    const applyCollapseState = (collapsed) => {
        document.body.classList.toggle("sidebar-collapsed", collapsed);
        if (sidebarCollapseBtn) {
            sidebarCollapseBtn.setAttribute("aria-expanded", collapsed ? "false" : "true");
            sidebarCollapseBtn.setAttribute(
                "aria-label",
                collapsed ? "Expandir menu lateral" : "Recolher menu lateral"
            );
        }
    };

    if (sidebarCollapseBtn) {
        applyCollapseState(localStorage.getItem(COLLAPSE_KEY) === "1");
        sidebarCollapseBtn.addEventListener("click", () => {
            const next = !document.body.classList.contains("sidebar-collapsed");
            applyCollapseState(next);
            localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
        });
    }

    const recommendButton = document.querySelector("[data-task-recommend]");
    const recommendationPanel = document.querySelector("[data-task-recommendation]");
    const confirmButton = document.querySelector("[data-task-confirm]");
    let currentRecommendation = null;
    if (recommendButton && recommendationPanel) {
        recommendButton.addEventListener("click", async () => {
            recommendButton.disabled = true;
            recommendButton.setAttribute("aria-busy", "true");
            try {
                const csrfToken = recommendButton.dataset.csrfToken
                    || document.querySelector('meta[name="csrf-token"]')?.content
                    || "";
                const response = await fetch(recommendButton.dataset.endpoint, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken,
                    },
                    body: JSON.stringify({ available_minutes: 60 }),
                });
                const payload = await response.json();
                if (!response.ok || !payload.success) {
                    throw new Error(payload.error || "Não foi possível gerar uma sugestão.");
                }
                const suggestion = payload.recommendation;
                currentRecommendation = suggestion;
                recommendationPanel.querySelector("[data-task-title]").textContent = suggestion.title;
                recommendationPanel.querySelector("[data-task-description]").textContent = suggestion.description;
                recommendationPanel.querySelector("[data-task-meta]").textContent = `${suggestion.subject} · ${suggestion.duration_minutes} min · ${suggestion.study_type}`;
                recommendationPanel.querySelector("[data-task-reason]").textContent = suggestion.reason;
                recommendationPanel.hidden = false;
                confirmButton.disabled = false;
            } catch (error) {
                window.alert(error.message);
            } finally {
                recommendButton.disabled = false;
                recommendButton.removeAttribute("aria-busy");
            }
        });
    }

    if (confirmButton) {
        confirmButton.addEventListener("click", async () => {
            if (!currentRecommendation) return;
            confirmButton.disabled = true;
            if (!currentRecommendation.idempotency_key && window.crypto?.randomUUID) {
                try { currentRecommendation.idempotency_key = window.crypto.randomUUID(); } catch (e) { /* sem chave */ }
            }
            const metaToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
            const response = await fetch(confirmButton.dataset.endpoint, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": confirmButton.dataset.csrfToken || metaToken,
                    ...(currentRecommendation.idempotency_key ? { "Idempotency-Key": currentRecommendation.idempotency_key } : {}),
                },
                body: JSON.stringify(currentRecommendation),
            });
            const payload = await response.json();
            if (response.ok && payload.success) {
                window.location.reload();
                return;
            }
            window.alert(payload.error || "Não foi possível adicionar a tarefa.");
            confirmButton.disabled = false;
        });
    }

    // Anti-dupla-submissão genérico (P1-4): desabilita botões submit do form
    // no primeiro submit. Sem mudar validação; pageshow reabilita (voltar).
    document.querySelectorAll("form[method]").forEach((form) => {
        if ((form.getAttribute("method") || "get").toLowerCase() !== "post") return;
        form.addEventListener("submit", () => {
            form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((btn) => {
                btn.disabled = true;
                btn.setAttribute("aria-disabled", "true");
            });
            window.setTimeout(() => {
                form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((btn) => {
                    // Reabilita se ainda estamos na página (erro de rede/validação).
                    if (document.contains(btn)) btn.disabled = false;
                });
            }, 8000);
        });
    });
});
