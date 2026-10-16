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
        const icon = document.getElementById("btn-theme-icon");
        const themeBtn = document.getElementById("btn-theme");
        if (icon) icon.textContent = theme === "system" ? "routine" : (document.documentElement.dataset.theme === "light" ? "light_mode" : "dark_mode");
        if (themeBtn) {
            const label = typeof t === "function" ? t("workspace.theme") : "Appearance";
            themeBtn.title = label;
            themeBtn.setAttribute("aria-label", label);
        }
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
        applyLibraryMode(next);
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
        document.getElementById("workspace-library-book")?.setAttribute("hidden", "");
        document.getElementById("workspace-agent-graph")?.setAttribute("hidden", "");
        ["graph", "you", "people"].forEach(name => {
            document.getElementById("library-tab-" + name)?.classList.remove("active");
        });
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

    let _libraryMode = "graph";

    function applyLibraryMode(next = page) {
        const on = next === "library" && !activePanel;
        const graph = document.getElementById("workspace-agent-graph");
        const book = document.getElementById("workspace-library-book");
        const rail = book?.querySelector(".library-rail");
        if (graph) graph.hidden = !on || _libraryMode !== "graph";
        if (book) {
            book.hidden = !on || _libraryMode === "graph";
            book.classList.toggle("is-solo", on && _libraryMode === "you");
            book.style.gridTemplateColumns = _libraryMode === "people" ? "" : "minmax(0, 1fr)";
        }
        if (rail) rail.hidden = _libraryMode !== "people";
        const peopleOnly = _libraryMode === "people";
        document.getElementById("library-you-title")?.toggleAttribute("hidden", peopleOnly);
        document.getElementById("library-you")?.toggleAttribute("hidden", peopleOnly);
        document.getElementById("library-people-title")?.toggleAttribute("hidden", !peopleOnly);
        document.getElementById("library-people-search")?.toggleAttribute("hidden", !peopleOnly);
        document.getElementById("library-people")?.toggleAttribute("hidden", !peopleOnly);
        ["graph", "you", "people"].forEach(name => {
            const tab = document.getElementById("library-tab-" + name);
            if (!tab) return;
            const current = on && _libraryMode === name;
            tab.classList.toggle("active", current);
            tab.setAttribute("aria-current", current ? "page" : "false");
        });
    }

    function libraryRu() {
        return t("workspace.library") === "Библиотека";
    }

    function libraryHue(id) {
        let hue = 0;
        for (const ch of String(id)) hue = (hue * 33 + ch.charCodeAt(0)) % 360;
        return hue;
    }

    function libraryAvatar(id) {
        const img = document.createElement("img");
        img.src = "/static/shibaclaw_logo.webp";
        img.alt = "";
        const hue = libraryHue(id);
        if (hue) img.style.filter = `hue-rotate(${hue}deg)`;
        return img;
    }

    function libraryItem(title, id, onClick) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "library-rail-item";
        const label = document.createElement("span");
        label.textContent = title;
        button.append(libraryAvatar(id), label);
        button.addEventListener("click", () => {
            document.querySelectorAll(".library-rail-item").forEach(item => item.classList.remove("active"));
            button.classList.add("active");
            onClick();
        });
        return button;
    }

    function librarySections(text) {
        const body = String(text || "").replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, "").trim();
        const sections = [];
        for (const part of body.split(/\n(?=## )/)) {
            const block = part.trim();
            if (!block) continue;
            if (block.startsWith("## ")) {
                const cut = block.indexOf("\n");
                sections.push({
                    title: (cut === -1 ? block.slice(3) : block.slice(3, cut)).trim(),
                    body: cut === -1 ? "" : block.slice(cut + 1).trim(),
                });
            } else {
                sections.push({ title: "", body: block });
            }
        }
        return sections;
    }

    function fillLibraryBody(el, text) {
        let list = null;
        for (const line of String(text || "").split("\n")) {
            const item = line.match(/^\s*[-*]\s+(.*)$/);
            if (item) {
                if (!list) {
                    list = document.createElement("ul");
                    el.append(list);
                }
                const li = document.createElement("li");
                li.textContent = item[1].replace(/\*\*/g, "").replace(/`([^`]+)`/g, "$1");
                list.append(li);
                continue;
            }
            list = null;
            const plain = line.trim().replace(/\*\*/g, "").replace(/`([^`]+)`/g, "$1");
            if (!plain || plain === "---") continue;
            const p = document.createElement("p");
            p.textContent = plain.replace(/^#+\s+/, "");
            el.append(p);
        }
    }

    function paintSectionCards(host, source, editing) {
        host.querySelectorAll(".library-doc").forEach(node => node.remove());
        const sections = librarySections(source);
        const rows = sections.length ? sections : [{ title: "", body: "" }];
        for (const section of rows) {
            const doc = document.createElement("article");
            doc.className = "library-doc";
            if (editing) {
                if (section.title) {
                    const head = document.createElement("div");
                    head.className = "library-doc-head";
                    const input = document.createElement("input");
                    input.className = "library-doc-title";
                    input.dataset.role = "title";
                    input.value = section.title;
                    head.append(input);
                    doc.append(head);
                }
                const area = document.createElement("textarea");
                area.className = "library-doc-edit";
                area.dataset.role = "body";
                area.value = section.body;
                area.rows = Math.min(14, Math.max(3, section.body.split("\n").length));
                doc.append(area);
            } else if (section.title || section.body) {
                if (section.title) {
                    const head = document.createElement("div");
                    head.className = "library-doc-head";
                    const strong = document.createElement("strong");
                    strong.textContent = section.title;
                    head.append(strong);
                    doc.append(head);
                }
                const body = document.createElement("div");
                body.className = "library-doc-body";
                fillLibraryBody(body, section.body);
                doc.append(body);
            }
            host.append(doc);
        }
    }

    function readSectionCards(host) {
        const parts = [];
        host.querySelectorAll(".library-doc").forEach(doc => {
            const title = doc.querySelector("[data-role=title]")?.value.trim() || "";
            const body = (doc.querySelector("[data-role=body]")?.value || "").trim();
            if (!title && !body) return;
            parts.push(title ? `## ${title}\n\n${body}` : body);
        });
        return parts.length ? parts.join("\n\n") + "\n" : "";
    }

    function visibleProfile(source) {
        source = String(source || "");
        const front = source.match(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/);
        const head = front ? front[0] : "";
        const rest = source.slice(head.length);
        const sections = librarySections(rest);
        const first = sections[0];
        if (!first || first.title) return { head, body: rest };
        const lines = first.body.split("\n").map(line => line.trim()).filter(Boolean);
        const stub = lines.length > 0 && lines.every(line => /^#+\s/.test(line) || /^[A-Za-z0-9_]+:\s*\S/.test(line));
        if (!stub) return { head, body: rest };
        const body = sections.slice(1).map(section => `## ${section.title}\n\n${section.body.trim()}`).join("\n\n");
        return { head: `${head}${first.body.trim()}\n\n`, body: body ? `${body}\n` : "" };
    }

    function mountSectionEdit(host, hero, source, onSave) {
        const kept = visibleProfile(source);
        let text = kept.body;
        const status = document.createElement("span");
        status.className = "library-editor-status";
        const edit = document.createElement("button");
        edit.type = "button";
        edit.className = "btn-secondary library-edit";
        const viewLabel = () => libraryRu() ? "Править" : "Edit";
        edit.textContent = viewLabel();
        hero.append(edit, status);
        const paint = (editing) => {
            host.classList.toggle("is-editing", editing);
            paintSectionCards(host, text, editing);
            edit.textContent = editing ? (libraryRu() ? "Сохранить" : "Save") : viewLabel();
        };
        paint(false);
        edit.addEventListener("click", async () => {
            if (!host.classList.contains("is-editing")) {
                paint(true);
                host.querySelector(".library-doc-edit")?.focus();
                return;
            }
            edit.disabled = true;
            status.textContent = "";
            try {
                const next = kept.head + readSectionCards(host);
                const ok = await onSave(next);
                status.textContent = ok ? (libraryRu() ? "Сохранено" : "Saved") : (libraryRu() ? "Ошибка" : "Error");
                if (!ok) return;
                text = readSectionCards(host);
                paint(false);
            } catch {
                status.textContent = libraryRu() ? "Ошибка" : "Error";
            } finally {
                edit.disabled = false;
            }
        });
    }

    async function openLibraryDoc(path, title, id) {
        const sheet = document.getElementById("library-sheet");
        if (!sheet) return;
        sheet.replaceChildren();
        const inner = document.createElement("div");
        inner.className = "library-sheet-inner";
        const hero = document.createElement("div");
        hero.className = "library-sheet-hero";
        const titles = document.createElement("div");
        const heading = document.createElement("h3");
        heading.textContent = title;
        const sub = document.createElement("p");
        titles.append(heading, sub);
        hero.append(libraryAvatar(id), titles);
        inner.append(hero);
        sheet.append(inner);
        let text = "";
        try {
            const res = await authFetch(`/api/file-get?path=${encodeURIComponent(path)}`);
            text = res.ok ? await res.text() : "";
        } catch { /* empty sheet */ }
        const named = text.match(/^peer_name:\s*(.+)$/m);
        if (named && !named[1].includes("неизвестно")) heading.textContent = named[1].trim();
        const h1 = text.match(/^#\s+(.+)$/m);
        if (!named && h1) heading.textContent = h1[1].trim();
        const sections = librarySections(text);
        const lead = sections[0]?.body.split("\n").map(line => line.trim()).find(line => line && !line.startsWith("-") && !line.startsWith("#") && !/^[A-Za-z0-9_]+:\s/.test(line));
        sub.textContent = (lead || "").replace(/\*\*/g, "").replace(/`([^`]+)`/g, "$1").slice(0, 140);
        sub.hidden = !sub.textContent;
        mountSectionEdit(inner, hero, text, async (next) => {
            const res = await authFetch("/api/file-save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path, content: next }),
            });
            return res.ok;
        });
    }

    async function loadLibraryBook(mode) {
        const ru = libraryRu();
        const youTitle = document.getElementById("library-you-title");
        const peopleTitle = document.getElementById("library-people-title");
        if (youTitle) youTitle.textContent = ru ? "Вы" : "You";
        if (peopleTitle) peopleTitle.textContent = ru ? "Знакомые" : "People";
        const you = document.getElementById("library-you");
        const people = document.getElementById("library-people");
        if (!you || !people) return;
        you.replaceChildren(libraryItem(ru ? "Вы" : "You", "default", () => openLibraryDoc("USER.md", ru ? "Вы" : "You", "default")));
        if (mode === "you") {
            openLibraryDoc("USER.md", ru ? "Вы" : "You", "default");
            return;
        }
        people.replaceChildren();
        try {
            const res = await authFetch("/api/fs/explore?path=" + encodeURIComponent("memory/people"));
            const data = await res.json();
            const grouped = new Map();
            (data.items || []).forEach(item => {
                if (item.is_dir || !item.name.endsWith(".md") || item.name === "README.md") return;
                const title = item.name.replace(/^\d+_/, "").replace(/\.md$/, "");
                const id = (item.name.match(/^(\d+)_/) || [null, item.name])[1];
                const row = { ...item, title };
                const prev = grouped.get(id);
                if (!prev) {
                    grouped.set(id, row);
                    return;
                }
                const rowCyr = /[А-Яа-яЁё]/.test(title);
                const prevCyr = /[А-Яа-яЁё]/.test(prev.title);
                const newer = (item.mtime || 0) > (prev.mtime || 0);
                const sameTime = (item.mtime || 0) === (prev.mtime || 0);
                if (newer || (sameTime && rowCyr && !prevCyr)) {
                    row.title = rowCyr || !prevCyr ? title : prev.title;
                    grouped.set(id, row);
                } else if (rowCyr && !prevCyr) {
                    prev.title = title;
                }
            });
            [...grouped.values()].sort((a, b) => a.title.localeCompare(b.title, "ru")).forEach(item => {
                people.append(libraryItem(item.title, item.name, () => openLibraryDoc(item.path, item.title, item.name)));
            });
        } catch { /* empty rail */ }
        const search = document.getElementById("library-people-search");
        if (search && !search.dataset.wired) {
            search.dataset.wired = "1";
            search.addEventListener("input", () => {
                const query = search.value.trim().toLowerCase();
                people.querySelectorAll(".library-rail-item").forEach(item => {
                    item.hidden = Boolean(query) && !item.textContent.toLowerCase().includes(query);
                });
            });
        }
        const first = people.querySelector(".library-rail-item");
        if (first) first.click();
        else {
            const sheet = document.getElementById("library-sheet");
            if (sheet) sheet.replaceChildren();
        }
    }

    const _GRAPH_HUE = { default: 0, polymarket: 108, dungeon: 248, gym: 332, boardnight: 196 };
    let _graphProfiles = [];
    let _graphFocus = null;

    function graphHue(id) {
        if (Object.prototype.hasOwnProperty.call(_GRAPH_HUE, id)) return _GRAPH_HUE[id];
        return libraryHue(id);
    }

    function showGraphDetail(profile) {
        const box = document.getElementById("agent-graph-detail");
        if (!box) return;
        box.replaceChildren();
        _graphFocus = profile.id;
        document.querySelectorAll(".agent-node").forEach(node => {
            node.classList.toggle("is-on", node.dataset.id === profile.id);
        });
        const hero = document.createElement("div");
        hero.className = "library-sheet-hero";
        const titles = document.createElement("div");
        const heading = document.createElement("h3");
        heading.textContent = profile.label || profile.id;
        const sub = document.createElement("p");
        sub.textContent = profile.description || "";
        sub.hidden = !sub.textContent;
        titles.append(heading, sub);
        const face = libraryAvatar(profile.id);
        face.style.filter = graphHue(profile.id) ? `hue-rotate(${graphHue(profile.id)}deg)` : "";
        hero.append(face, titles);
        box.append(hero);
        const skills = profile.pinned_skills || [];
        const bases = profile.knowledge_bases || [];
        if (skills.length || bases.length) {
            const row = document.createElement("div");
            row.className = "agent-graph-chips";
            [...skills, ...bases].forEach(name => {
                const chip = document.createElement("span");
                chip.className = "library-chip";
                chip.textContent = name;
                row.append(chip);
            });
            box.append(row);
        }
        mountSectionEdit(box, hero, profile.soul || "", async (next) => {
            const res = await authFetch(`/api/profiles/${encodeURIComponent(profile.id)}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ soul: next }),
            });
            if (!res.ok) return false;
            profile.soul = next;
            return true;
        });
    }

    function graphConcepts(profile) {
        const items = [];
        for (const name of profile.pinned_skills || []) {
            items.push({ id: `${profile.id}:skill:${name}`, label: name, kind: "skill" });
        }
        for (const name of profile.knowledge_bases || []) {
            items.push({ id: `${profile.id}:kb:${name}`, label: name, kind: "kb" });
        }
        return items;
    }

    function paintGraph() {
        const stage = document.querySelector(".agent-graph-stage");
        const nodes = document.getElementById("agent-graph-nodes");
        const svg = document.getElementById("agent-graph-svg");
        if (!stage || !nodes || !svg) return;
        const width = stage.clientWidth || 640;
        const height = stage.clientHeight || 420;
        const cx = width * 0.5;
        const cy = height * 0.46;
        const ns = "http://www.w3.org/2000/svg";
        const verb = t("workspace.library") === "Библиотека" ? "будит" : "wakes";
        const others = _graphProfiles.filter(profile => profile.id !== "default");
        const spots = new Map();
        spots.set("default", { x: cx, y: cy });
        others.forEach((profile, index) => {
            const angle = (-Math.PI / 2) + (index / Math.max(others.length, 1)) * Math.PI * 2;
            spots.set(profile.id, {
                x: cx + Math.cos(angle) * width * 0.28,
                y: cy + Math.sin(angle) * height * 0.28,
            });
            graphConcepts(profile).forEach((item, itemIndex, list) => {
                const spread = (itemIndex - (list.length - 1) / 2) * 0.22;
                spots.set(item.id, {
                    x: cx + Math.cos(angle + spread) * width * 0.44,
                    y: cy + Math.sin(angle + spread) * height * 0.42,
                    concept: item,
                    owner: profile.id,
                });
            });
        });
        const core = _graphProfiles.find(profile => profile.id === "default");
        if (core) {
            graphConcepts(core).forEach((item, itemIndex, list) => {
                spots.set(item.id, {
                    x: Math.max(64, Math.min(width - 64, cx + width * 0.16 + (itemIndex - (list.length - 1) / 2) * 96)),
                    y: Math.min(height - 32, cy + height * 0.14),
                    concept: item,
                    owner: core.id,
                });
            });
        }
        spots.forEach(spot => {
            spot.x = Math.max(64, Math.min(width - 64, spot.x));
            spot.y = Math.max(32, Math.min(height - 32, spot.y));
        });
        svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
        svg.replaceChildren();
        const drawLine = (from, to, kind) => {
            const line = document.createElementNS(ns, "line");
            line.setAttribute("x1", from.x);
            line.setAttribute("y1", from.y);
            line.setAttribute("x2", to.x);
            line.setAttribute("y2", to.y);
            if (kind) line.setAttribute("class", kind);
            svg.append(line);
            return line;
        };
        others.forEach(profile => {
            const from = spots.get("default");
            const to = spots.get(profile.id);
            drawLine(from, to, "is-wake");
            const text = document.createElementNS(ns, "text");
            text.setAttribute("x", (from.x + to.x) / 2);
            text.setAttribute("y", (from.y + to.y) / 2 - 8);
            text.setAttribute("text-anchor", "middle");
            text.textContent = verb;
            svg.append(text);
        });
        spots.forEach(spot => {
            if (!spot.concept) return;
            drawLine(spots.get(spot.owner), spot, "is-link");
        });
        nodes.replaceChildren();
        _graphProfiles.forEach(profile => {
            const spot = spots.get(profile.id);
            const button = document.createElement("button");
            button.type = "button";
            button.className = "agent-node" + (profile.id === "default" ? " is-core" : "");
            button.dataset.id = profile.id;
            button.style.left = `${spot.x}px`;
            button.style.top = `${spot.y}px`;
            const face = libraryAvatar(profile.id);
            face.style.filter = graphHue(profile.id) ? `hue-rotate(${graphHue(profile.id)}deg)` : "";
            const label = document.createElement("span");
            label.textContent = profile.label || profile.id;
            button.append(face, label);
            button.addEventListener("click", () => showGraphDetail(profile));
            nodes.append(button);
        });
        spots.forEach(spot => {
            if (!spot.concept) return;
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "agent-node is-concept";
            chip.style.left = `${spot.x}px`;
            chip.style.top = `${spot.y}px`;
            chip.textContent = spot.concept.label;
            const owner = _graphProfiles.find(profile => profile.id === spot.owner);
            chip.addEventListener("click", () => owner && showGraphDetail(owner));
            nodes.append(chip);
        });
        const focus = _graphProfiles.find(profile => profile.id === _graphFocus) || core || _graphProfiles[0];
        if (focus) showGraphDetail(focus);
    }

    async function loadAgentGraph() {
        document.getElementById("library-tab-graph")?.classList.add("active");
        document.querySelectorAll("[data-workspace-modal]").forEach(button => button.classList.remove("active"));
        const listed = await authFetch("/api/profiles");
        const data = await listed.json();
        const rows = data.profiles || [];
        _graphProfiles = await Promise.all(rows.map(async row => {
            try {
                const res = await authFetch(`/api/profiles/${encodeURIComponent(row.id)}`);
                if (res.ok) return await res.json();
            } catch { /* list row is enough */ }
            return row;
        }));
        paintGraph();
        if (!window._agentGraphResize) {
            window._agentGraphResize = true;
            window.addEventListener("resize", () => {
                const graph = document.getElementById("workspace-agent-graph");
                if (!graph || graph.hidden || !_graphProfiles.length) return;
                paintGraph();
            });
        }
    }

    function dismissLibraryPanel() {
        if (!activePanel) return;
        const panel = document.getElementById(activePanel);
        activePanel = null;
        panel?.classList.remove("active");
    }

    window.openWorkspaceLibrary = function () {
        _libraryMode = "graph";
        dismissLibraryPanel();
        showPage("library");
        loadAgentGraph();
    };

    window.openLibraryYou = function () {
        _libraryMode = "you";
        dismissLibraryPanel();
        if (page !== "library") showPage("library");
        else applyLibraryMode();
        loadLibraryBook("you");
    };

    window.openLibraryPeople = function () {
        _libraryMode = "people";
        dismissLibraryPanel();
        if (page !== "library") showPage("library");
        else applyLibraryMode();
        loadLibraryBook("people");
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
        document.getElementById("btn-theme")?.addEventListener("click", () => {
            const order = ["system", "light", "dark"];
            theme = order[(order.indexOf(theme) + 1) % order.length];
            try { localStorage.setItem("shibaclaw_theme", theme); } catch (_) { /* optional storage */ }
            applyTheme();
        });
        // The same profile selector keeps its existing handlers and session metadata.
        const profile = document.getElementById("profile-selector");
        const actions = document.querySelector(".input-actions");
        if (profile && actions) actions.prepend(profile);
        const plus = document.getElementById("btn-composer-plus");
        const composer = document.querySelector(".workspace-composer");
        const setPlusOpen = (open) => {
            composer?.classList.toggle("plus-open", open);
            plus?.setAttribute("aria-expanded", open ? "true" : "false");
        };
        plus?.addEventListener("click", (event) => {
            event.stopPropagation();
            setPlusOpen(!composer?.classList.contains("plus-open"));
        });
        document.addEventListener("click", (event) => {
            if (composer?.classList.contains("plus-open") && !event.target.closest(".workspace-composer")) {
                setPlusOpen(false);
            }
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") setPlusOpen(false);
        });
        window.syncComposerChips = function () {
            const box = document.getElementById("composer-chips");
            if (!box) return;
            box.replaceChildren();
            const add = (icon, label, onClear) => {
                if (!label) return;
                const chip = document.createElement("span");
                chip.className = "composer-chip";
                const glyph = document.createElement("span");
                glyph.className = "material-icons-round";
                glyph.textContent = icon;
                const text = document.createElement("span");
                text.className = "label";
                text.textContent = label;
                chip.append(glyph, text);
                if (onClear) {
                    const close = document.createElement("button");
                    close.type = "button";
                    close.setAttribute("aria-label", label);
                    close.innerHTML = '<span class="material-icons-round">close</span>';
                    close.addEventListener("click", (event) => {
                        event.stopPropagation();
                        onClear();
                    });
                    chip.appendChild(close);
                } else {
                    chip.addEventListener("click", () => setPlusOpen(true));
                }
                box.appendChild(chip);
            };
            const effortBtn = document.getElementById("btn-reasoning-select");
            const effort = document.getElementById("active-reasoning-display")?.textContent?.trim() || "";
            const effortDefault = typeof t === "function" ? t("chat.effort_default") : "Default";
            const effortNa = typeof t === "function" ? t("chat.effort_na") : "Effort: N/A";
            if (effortBtn && !effortBtn.classList.contains("disabled") && effort && effort !== effortNa && !effort.endsWith(effortDefault)) {
                const prefix = typeof t === "function" ? t("chat.effort_prefix") : "Effort: ";
                add("psychology", effort.startsWith(prefix) ? effort.slice(prefix.length) : effort, () => window.clearComposerEffort?.());
            }
            const kb = document.getElementById("active-kb-display")?.textContent || "";
            const kbCount = Number((kb.match(/(\d+)/) || [])[1] || 0);
            if (kbCount > 0) add("library_books", kb, () => window.clearComposerKBs?.());
        };
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
