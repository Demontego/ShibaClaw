/* Workspace shell. Existing panels, IDs and API handlers remain the owners of data. */
(function () {
    const panels = {
        "fs-modal": "library",
        "knowledge-modal": "library",
        "memory-modal": "library",
        "automation-modal": "automations",
        "connected-apps-modal": "apps",
        "evolve-modal": "evolution",
    };
    let page = "chat";
    let activePanel = null;
    let agents = [];
    let agentsRequest = 0;
    let theme = "system";
    let chatTitle = "";
    let chatTitleKey = "workspace.new_chat";
    const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");

    function applyTheme() {
        document.documentElement.dataset.theme = theme === "system"
            ? (systemTheme.matches ? "dark" : "light") : theme;
        const select = document.getElementById("workspace-theme");
        if (select) select.value = theme;
        const color = document.documentElement.dataset.theme === "light" ? "#fcfbf9" : "#191918";
        const meta = document.getElementById("theme-color");
        if (meta) meta.setAttribute("content", color);
    }

    window.setWorkspaceNav = function (next) {
        page = next;
        document.querySelectorAll("[data-workspace-page]").forEach(button => {
            const selected = button.dataset.workspacePage === next;
            button.classList.toggle("active", selected);
            if (selected) button.setAttribute("aria-current", "page");
            else button.removeAttribute("aria-current");
        });
    };

    function translateWorkspace() {
        const chatHeading = document.getElementById("workspace-chat-title");
        if (chatHeading) chatHeading.textContent = chatTitle || t(chatTitleKey);
        const title = document.getElementById("workspace-view-title");
        const heading = document.getElementById("workspace-page-heading");
        const description = document.getElementById("workspace-page-description");
        if (["agents", "library", "automations", "apps", "evolution"].includes(page)) {
            if (title) title.textContent = t(`workspace.${page}`);
            if (heading) heading.textContent = t(`workspace.${page}`);
            if (description) description.textContent = t(`workspace.${page}_subtitle`);
        }
        document.querySelectorAll("[data-workspace-page]").forEach(button => {
            button.title = t(`workspace.${button.dataset.workspacePage === "chat" ? "conversations" : button.dataset.workspacePage}`);
            button.setAttribute("aria-label", button.title);
        });
        if (page === "agents") renderAgents();
    }

    function setMainPane(mode) {
        const open = mode !== "chat";
        document.body.classList.toggle("workspace-page-open", open);
        const chat = document.getElementById("chat-area");
        const view = document.getElementById("workspace-view");
        if (chat) chat.style.display = open ? "none" : "flex";
        if (view) view.style.display = open ? "flex" : "none";
    }

    window.leaveWorkspace = function () {
        ++agentsRequest;
        Object.keys(panels).forEach(id => document.getElementById(id)?.classList.remove("active"));
        activePanel = null;
        setMainPane("chat");
    };

    window.setWorkspaceChatTitle = function (title, key = "workspace.new_chat") {
        chatTitle = title || "";
        chatTitleKey = key;
        document.getElementById("workspace-chat-title")?.removeAttribute("data-i18n");
        translateWorkspace();
    };

    window.showWorkspaceChat = function () {
        window.leaveWorkspace();
        if (typeof window.closeSettingsView === "function") window.closeSettingsView();
        setMainPane("chat");
        window.setWorkspaceNav("chat");
        if (typeof window.closeSidebarOnMobile === "function") window.closeSidebarOnMobile();
    };

    function showPage(next) {
        window.leaveWorkspace();
        if (typeof window.closeSettingsView === "function") window.closeSettingsView();
        setMainPane(next);
        document.getElementById("workspace-agents").hidden = next !== "agents";
        document.getElementById("workspace-library-tabs").hidden = next !== "library";
        document.getElementById("workspace-app-actions").hidden = next !== "apps";
        const evolveActions = document.getElementById("workspace-evolve-actions");
        if (evolveActions) evolveActions.hidden = next !== "evolution";
        window.setWorkspaceNav(next);
        translateWorkspace();
        if (typeof window.closeSidebarOnMobile === "function") window.closeSidebarOnMobile();
    }

    window.prepareWorkspaceModal = function (id) {
        if (id === "context-modal") {
            const modal = document.getElementById(id);
            document.getElementById("chat-area").appendChild(modal);
            modal.classList.add("workspace-context");
            document.getElementById("chat-area").classList.add("context-visible");
            document.getElementById("workspace-context-toggle").setAttribute("aria-expanded", "true");
            return;
        }
        if (!panels[id]) return;
        showPage(panels[id]);
        const panel = document.getElementById(id);
        const dialog = panel.querySelector(":scope > .modal");
        if (dialog) {
            ["width", "max-width", "height", "max-height"].forEach(property => dialog.style.removeProperty(property));
        }
        panel.classList.add("workspace-panel");
        panel.dataset.backdropClose = "false";
        document.getElementById("workspace-stage").appendChild(panel);
        activePanel = id;
        document.querySelectorAll("[data-workspace-modal]").forEach(button => {
            button.classList.toggle("active", button.dataset.workspaceModal === id);
            button.setAttribute("aria-current", button.dataset.workspaceModal === id ? "page" : "false");
        });
    };

    window.onWorkspaceModalClosed = function (id) {
        if (id === "context-modal") {
            document.getElementById("chat-area").classList.remove("context-visible");
            document.getElementById("workspace-context-toggle").setAttribute("aria-expanded", "false");
        } else if (id === activePanel) {
            activePanel = null;
            window.showWorkspaceChat();
        }
    };

    window.toggleWorkspaceContext = function () {
        if (state.contextModalOpen) window.closeModal("context-modal");
        else window.openModal("context-modal");
    };

    window.toggleWorkspaceSidebar = function () {
        const collapsed = document.body.classList.toggle("workspace-sidebar-collapsed");
        try { localStorage.setItem("shibaclaw_sidebar_collapsed", String(collapsed)); } catch (_) { /* optional storage */ }
    };

    function applySidebarForViewport() {
        if (window.matchMedia("(max-width: 900px)").matches) {
            document.body.classList.remove("workspace-sidebar-collapsed");
            return;
        }
        try {
            const stored = localStorage.getItem("shibaclaw_sidebar_collapsed");
            if (stored === "true" || stored === "false") {
                document.body.classList.toggle("workspace-sidebar-collapsed", stored === "true");
                return;
            }
        } catch (_) { /* optional storage */ }
        document.body.classList.toggle(
            "workspace-sidebar-collapsed",
            window.matchMedia("(max-width: 1199px)").matches,
        );
    }

    function renderAgents() {
        const grid = document.getElementById("workspace-agent-grid");
        if (!grid) return;
        grid.replaceChildren();
        if (!agents.length) {
            grid.textContent = t("workspace.agents_empty");
            return;
        }
        agents.forEach(profile => {
            const card = document.createElement("article");
            card.className = "workspace-agent-card";
            const avatar = document.createElement("div");
            avatar.className = "workspace-agent-avatar";
            if (profile.avatar) {
                const img = document.createElement("img");
                img.src = profile.avatar;
                img.alt = "";
                avatar.append(img);
            } else avatar.append(createMaterialIcon("smart_toy"));
            const name = document.createElement("h3");
            name.textContent = profile.label || profile.id;
            const description = document.createElement("p");
            description.textContent = profile.description || "";
            const footer = document.createElement("div");
            footer.className = "workspace-agent-footer";
            const badge = document.createElement("span");
            badge.className = "workspace-profile-badge";
            badge.textContent = profile.id === state.profileId ? t("workspace.agent_active")
                : profile.builtin ? t("profiles.builtin") : "";
            const edit = document.createElement("button");
            edit.type = "button";
            edit.className = "btn-icon";
            edit.setAttribute("aria-label", t("profiles.configure"));
            edit.title = t("profiles.configure");
            edit.append(createMaterialIcon("tune"));
            edit.addEventListener("click", () => openProfileModal(profile.id));
            const chat = document.createElement("button");
            chat.type = "button";
            chat.className = "btn-secondary";
            chat.textContent = t("workspace.agent_chat");
            chat.addEventListener("click", () => {
                window.showWorkspaceChat();
                realtime.emit("new_session", { profile_id: profile.id });
                document.getElementById("chat-input").focus();
            });
            footer.append(badge, edit, chat);
            card.append(avatar, name, description, footer);
            grid.append(card);
        });
    }

    window.refreshWorkspaceAgents = async function () {
        const request = ++agentsRequest;
        const grid = document.getElementById("workspace-agent-grid");
        grid.textContent = t("workspace.loading_agents");
        try {
            // Keep the existing profile picker cache in sync with this page.
            const response = await authFetch("/api/profiles");
            if (!response.ok) throw new Error("profiles unavailable");
            const data = await response.json();
            if (request !== agentsRequest || page !== "agents") return;
            agents = Array.isArray(data.profiles) ? data.profiles : [];
            _profilesCache = agents;
            renderAgents();
        } catch (_) {
            if (request === agentsRequest && page === "agents") grid.textContent = t("workspace.agents_error");
        }
    };

    window.openWorkspaceAgents = function () {
        showPage("agents");
        window.refreshWorkspaceAgents();
    };

    window.openWorkspaceTools = async function (extensions) {
        await window.openSettingsView();
        window.switchSettingsTab(extensions ? "extensions" : "tools");
        if (extensions) window.switchExtensionsSubTab("mcp");
    };

    function init() {
        try {
            const stored = localStorage.getItem("shibaclaw_theme");
            if (["system", "light", "dark"].includes(stored)) theme = stored;
        } catch (_) { /* optional storage */ }
        applyTheme();
        applySidebarForViewport();
        window.matchMedia("(max-width: 900px)").addEventListener("change", applySidebarForViewport);
        window.matchMedia("(max-width: 1199px)").addEventListener("change", applySidebarForViewport);
        window.setWorkspaceNav(page);
        systemTheme.addEventListener("change", applyTheme);
        document.getElementById("workspace-theme")?.addEventListener("change", event => {
            theme = event.target.value;
            try { localStorage.setItem("shibaclaw_theme", theme); } catch (_) { /* optional storage */ }
            applyTheme();
        });
        // The same profile selector keeps its existing handlers and session metadata.
        const profile = document.getElementById("profile-selector");
        const actions = document.querySelector(".input-actions");
        if (profile && actions) actions.prepend(profile);
        const newChat = document.getElementById("btn-new-session");
        newChat?.addEventListener("click", window.showWorkspaceChat, { capture: true });
        document.querySelector(".logo")?.addEventListener("keydown", event => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                window.showWorkspaceChat();
            }
        });
        // Session items are rebuilt by the history renderer; delegation survives rerenders.
        document.getElementById("history-list")?.addEventListener("click", event => {
            if (event.target.closest(".history-item") && !event.target.closest(".btn-session-menu, .session-dropdown")) {
                window.showWorkspaceChat();
            }
        }, { capture: true });
        document.addEventListener("shibaclaw:localechange", () => {
            translateWorkspace();
            if (state.contextModalOpen) void _loadContextModalContent();
            else void refreshTokenBadge();
        });
        translateWorkspace();
        document.addEventListener("keydown", event => {
            if (event.key === "Escape" && state.contextModalOpen && !document.querySelector("body > .modal-backdrop.active")) {
                window.closeModal("context-modal");
            }
        });
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
