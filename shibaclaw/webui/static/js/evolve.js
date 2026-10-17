(function () {
    const EN = {
        title: "Evolution",
        loading: "Loading…",
        fail: "Failed to load evolution",
        refresh: "Refresh",
        off: "Off",
        wait: "Waiting",
        run: "Working",
        error: "Needs attention",
        switchOn: "Evolution is on",
        switchOff: "Evolution is off",
        overview: "Overview",
        tasks: "Tasks",
        history: "History",
        settings: "Settings",
        next: "Next run",
        unscheduled: "Not scheduled",
        installs: "Installs today",
        installsHint: "An install is an accepted change. It is not a run and not a commit.",
        reasonPanic: "Stopped by panic.",
        reasonBudget: "Stopped: the daily install limit is used.",
        reasonCooldown: "Waiting out the cooldown.",
        reasonOff: "Evolution is off.",
        reasonLast: "The last run failed.",
        nowTitle: "Current run",
        nowEmpty: "Nothing is running.",
        since: "Since",
        lastTitle: "Last run",
        lastUnknown: "No result recorded.",
        resultOk: "Finished",
        resultError: "Failed",
        resultSkipped: "Skipped",
        resultPending: "Pending",
        queue: "Next tasks",
        allTasks: "All tasks",
        warnings: "Needs attention",
        open: "Open",
        done: "Done",
        search: "Search tasks",
        empty: "Nothing here.",
        noMatch: "No tasks match.",
        wake: "Run",
        chronicle: "Note",
        commits: "Commits",
        zone: "Times",
        schedule: "Schedule",
        every: "How often",
        model: "Model",
        modelDefault: "Chat default",
        modelFind: "Find a model",
        tools: "Tools",
        mcpHint: "An empty selection keeps the usual tools. It does not ban them.",
        digest: "Daily digest",
        digestOff: "Digest is off",
        advanced: "Advanced",
        prompt: "Evolution prompt",
        promptHint: "Shown as stored text. Saving does not run it.",
        save: "Save",
        saved: "Saved",
        dirty: "Unsaved changes",
        min: "min",
        hour: "h",
        inMin: "in {n} min",
        agoMin: "{n} min ago",
        inHour: "in {n} h",
        agoHour: "{n} h ago",
        soon: "within a minute",
        commit: "commit",
    };
    const RU = {
        title: "Эволюция",
        loading: "Загрузка…",
        fail: "Не вышло прочитать эволюцию",
        refresh: "Обновить",
        off: "Выключена",
        wait: "Ожидает",
        run: "Работает",
        error: "Нужно внимание",
        switchOn: "Эволюция включена",
        switchOff: "Эволюция выключена",
        overview: "Обзор",
        tasks: "Задачи",
        history: "История",
        settings: "Настройки",
        next: "Следующий запуск",
        unscheduled: "Не запланирован",
        installs: "Установки сегодня",
        installsHint: "Установка — принятое изменение. Это не запуск и не коммит.",
        reasonPanic: "Остановка: panic.",
        reasonBudget: "Остановка: дневной лимит установок исчерпан.",
        reasonCooldown: "Пауза после последней установки.",
        reasonOff: "Эволюция выключена.",
        reasonLast: "Последний запуск закончился ошибкой.",
        nowTitle: "Текущий запуск",
        nowEmpty: "Сейчас работа не идёт.",
        since: "С",
        lastTitle: "Последний запуск",
        lastUnknown: "Результат не записан.",
        resultOk: "Завершён",
        resultError: "Ошибка",
        resultSkipped: "Пропущен",
        resultPending: "Ждёт",
        queue: "Ближайшие задачи",
        allTasks: "Все задачи",
        warnings: "Нужно внимание",
        open: "Открытые",
        done: "Завершённые",
        search: "Поиск задач",
        empty: "Пока пусто.",
        noMatch: "Ничего не найдено.",
        wake: "Запуск",
        chronicle: "Запись",
        commits: "Коммиты",
        zone: "Время",
        schedule: "Расписание",
        every: "Как часто",
        model: "Модель",
        modelDefault: "Модель чата",
        modelFind: "Найти модель",
        tools: "Инструменты",
        mcpHint: "Пустой список оставляет обычные инструменты. Он их не запрещает.",
        digest: "Сводка за день",
        digestOff: "Сводка выключена",
        advanced: "Расширенные",
        prompt: "Промпт эволюции",
        promptHint: "Текст как в хранилище. Сохранение его не запускает.",
        save: "Сохранить",
        saved: "Сохранено",
        dirty: "Есть несохранённые изменения",
        min: "мин",
        hour: "ч",
        inMin: "через {n} мин",
        agoMin: "{n} мин назад",
        inHour: "через {n} ч",
        agoHour: "{n} ч назад",
        soon: "меньше минуты",
        commit: "коммит",
    };
    const TOOLS = {
        "gcalendar-klavis": "Google Calendar",
        gdocs: "Google Docs",
        gdrive: "Google Drive",
        "github-klavis": "GitHub",
        "gmail-klavis": "Gmail",
        gsheets: "Google Sheets",
        headroom: "Headroom",
        "outlook-klavis": "Outlook",
        outlook_calendar: "Outlook Calendar",
        polymarket: "Polymarket",
    };
    const EVERY = [10, 30, 60, 180, 360, 720, 1440];

    let timer = null;
    let busy = false;
    let models = [];
    let modelsLoaded = false;
    let tab = "overview";
    let query = "";
    let detail = null;
    let form = null;
    let pending = null;
    let note = "";
    let last = null;
    let skipRead = false;

    function L(key) {
        const ru = window.i18n && window.i18n.getLocale && window.i18n.getLocale() === "ru";
        return (ru ? RU : EN)[key] || EN[key] || key;
    }

    function esc(text) {
        if (typeof escapeHtml === "function") return escapeHtml(String(text ?? ""));
        const el = document.createElement("div");
        el.textContent = text ?? "";
        return el.innerHTML;
    }

    function zoneName() {
        try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "local"; }
        catch (_) { return "local"; }
    }

    function absolute(ms) {
        const n = Number(ms);
        if (!n) return "";
        try {
            return `${new Date(n).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} (${zoneName()})`;
        } catch (_) {
            return "";
        }
    }

    function relative(ms) {
        const delta = Number(ms) - Date.now();
        const min = Math.round(Math.abs(delta) / 60000);
        if (min < 1) return L("soon");
        if (min < 60) return (delta >= 0 ? L("inMin") : L("agoMin")).replace("{n}", String(min));
        return (delta >= 0 ? L("inHour") : L("agoHour")).replace("{n}", String(Math.round(min / 60)));
    }

    function everyLabel(min) {
        if (min % 60 === 0) return `${min / 60} ${L("hour")}`;
        return `${min} ${L("min")}`;
    }

    function face(data) {
        if (data.code === 2) return "error";
        if (!data.enabled || data.code === 3) return "off";
        if (data.code === 5) return "run";
        if (data.job && data.job.last_status === "error") return "error";
        return "wait";
    }

    function reason(data) {
        if (data.code === 2) return L("reasonPanic");
        if (!data.enabled || data.code === 3) return L("reasonOff");
        if (data.code === 6) return L("reasonBudget");
        if (data.code === 7) return L("reasonCooldown");
        if (data.job && data.job.last_status === "error") return L("reasonLast");
        return "";
    }

    function planned(data) {
        const job = data.job || {};
        if (!data.enabled || data.code === 3 || !Number(job.next_run_at_ms)) return null;
        return Number(job.next_run_at_ms);
    }

    function resultLabel(status) {
        if (status === "ok") return L("resultOk");
        if (status === "error") return L("resultError");
        if (status === "skipped") return L("resultSkipped");
        if (status === "pending") return L("resultPending");
        return "";
    }

    function outline(text) {
        const out = [];
        for (const line of String(text || "").split("\n")) {
            const item = line.trim();
            if (item.startsWith("## ")) out.push({ kind: "stage", text: item.slice(3).trim() });
            else if (item.startsWith("- ")) out.push({ kind: "step", text: item.slice(2).trim() });
        }
        return out;
    }

    function taskItems(data) {
        const full = outline(data && data.backlog);
        return full.length ? full : ((data && data.map) || []);
    }

    function noteItems(data) {
        const full = outline(data && data.chronicle).filter((item) => item.kind === "step");
        if (full.length) return full.slice().reverse();
        return ((data && data.steps) || []).slice().reverse();
    }

    function splitTasks(items) {
        let bucket = "open";
        const open = [];
        const done = [];
        for (const item of items || []) {
            if (item.kind === "stage") {
                bucket = /done|closed|complete|заверш|готов/i.test(item.text || "") ? "done" : "open";
                continue;
            }
            (bucket === "done" ? done : open).push(item);
        }
        return { open, done };
    }

    function toolName(id) {
        return TOOLS[id] || id;
    }

    function itemId(item) {
        return item.id || item.raw_id || "";
    }

    function modelName(id) {
        if (!id) return L("modelDefault");
        const found = models.find((item) => item.id === id || item.raw_id === id);
        return found ? (found.name || itemId(found)) : id;
    }

    function editing() {
        const el = document.activeElement;
        return Boolean(el && el.closest && el.closest("#evolve-content") && /^(INPUT|TEXTAREA)$/.test(el.tagName));
    }

    function readForm() {
        const next = Object.assign({}, form || {});
        const every = document.getElementById("evolve-every");
        const model = document.getElementById("evolve-model");
        const prompt = document.getElementById("evolve-prompt");
        const digest = document.getElementById("evolve-digest");
        const digestModel = document.getElementById("evolve-digest-model");
        const digestOn = document.getElementById("evolve-digest-enabled");
        if (every) next.every = every.value;
        if (model) next.model = model.value;
        if (document.querySelector("#evolve-tools")) {
            next.mcps = [...document.querySelectorAll("#evolve-tools input:checked")].map((el) => el.value);
        }
        if (prompt) next.campaign = prompt.value;
        if (digest) next.digest = digest.value;
        if (digestModel) next.digestModel = digestModel.value;
        if (digestOn) next.digestOn = digestOn.checked;
        if (every || model || prompt || digest) form = next;
    }

    function dirtyWake(data) {
        if (!form) return false;
        const settings = data.settings || {};
        if (form.every != null && String(form.every) !== String(settings.every_min || 10)) return true;
        if (form.model != null && form.model !== (settings.model || "")) return true;
        if (form.mcps && form.mcps.join("\n") !== (settings.mcps || []).join("\n")) return true;
        return false;
    }

    function dirtyDigest(data) {
        if (!form || !data.digest) return false;
        if (form.digest != null && form.digest !== data.digest.message) return true;
        if (form.digestModel != null && form.digestModel !== (data.digest.model || "")) return true;
        if (form.digestOn != null && Boolean(form.digestOn) !== Boolean(data.digest.enabled)) return true;
        return false;
    }

    function dirtyPrompt(data) {
        return Boolean(form && form.campaign != null && form.campaign !== (data.campaign || ""));
    }

    function warnings(data) {
        const lines = [];
        if (data.code === 2) lines.push(L("reasonPanic"));
        if (data.code === 6) lines.push(L("reasonBudget"));
        if (data.code === 7) lines.push(L("reasonCooldown"));
        if (data.job && data.job.last_status === "error") lines.push(L("resultError"));
        return lines;
    }

    function setRefreshing(on) {
        document.querySelectorAll(".evolve-refresh").forEach((btn) => {
            btn.classList.toggle("busy", on);
            btn.disabled = on;
        });
    }

    function combo(id, selected) {
        return `<div class="evolve-combo">
            <input id="${id}-q" type="text" autocomplete="off" placeholder="${esc(L("modelFind"))}" value="${esc(modelName(selected))}" aria-autocomplete="list">
            <input id="${id}" type="hidden" value="${esc(selected || "")}">
            <ul class="evolve-combo-list" hidden></ul>
        </div>`;
    }

    function fillCombo(input) {
        const wrap = input.closest(".evolve-combo");
        const list = wrap && wrap.querySelector(".evolve-combo-list");
        const hidden = wrap && wrap.querySelector("input[type=hidden]");
        if (!list || !hidden) return;
        const q = input.value.trim().toLowerCase();
        const rows = models.filter((item) => {
            const blob = `${item.name || ""} ${item.id || ""} ${item.raw_id || ""} ${item.provider_label || ""} ${item.provider || ""}`.toLowerCase();
            return !q || q === modelName(hidden.value).toLowerCase() || blob.includes(q);
        });
        list.innerHTML = `<li data-model-pick="" data-model-for="${esc(hidden.id)}">${esc(L("modelDefault"))}</li>` + rows.map((item) => {
            const id = itemId(item);
            const exact = item.raw_id && item.raw_id !== id ? item.raw_id : id;
            return `<li data-model-pick="${esc(id)}" data-model-for="${esc(hidden.id)}"><strong>${esc(item.name || id)}</strong><span>${esc(exact)}</span></li>`;
        }).join("");
        list.hidden = false;
    }

    function taskButton(item, index) {
        return `<button type="button" class="evolve-task" data-task="${index}">
            <span class="evolve-task-title">${esc(item.text || "")}</span>
        </button>`;
    }

    function taskList(items, empty) {
        if (!items.length) return `<p class="evolve-empty">${esc(empty)}</p>`;
        return items.map((item, index) => taskButton(item, index)).join("");
    }

    function render(data) {
        const box = document.getElementById("evolve-content");
        if (!box) return;
        if (!skipRead) readForm();
        skipRead = false;
        last = data;
        const state = face(data);
        const why = reason(data);
        const nextAt = planned(data);
        const tasks = splitTasks(taskItems(data));
        const settings = data.settings || {};
        const everyValue = form && form.every != null ? form.every : String(settings.every_min || 10);
        const modelValue = form && form.model != null ? form.model : (settings.model || "");
        const picked = form && form.mcps ? form.mcps : (settings.mcps || []);
        const campaign = form && form.campaign != null ? form.campaign : (data.campaign || "");
        const digest = data.digest;
        const digestText = form && form.digest != null ? form.digest : (digest ? digest.message : "");
        const digestModel = form && form.digestModel != null ? form.digestModel : (digest ? digest.model || "" : "");
        const digestOn = form && form.digestOn != null ? form.digestOn : (digest ? digest.enabled : false);
        const minutes = Number(everyValue) || 10;
        const everyOptions = (EVERY.includes(minutes) ? EVERY : [minutes, ...EVERY]).map((min) => (
            `<option value="${min}" ${min === minutes ? "selected" : ""}>${esc(everyLabel(min))}</option>`
        )).join("");
        const servers = data.mcp_servers || [];
        const q = query.trim().toLowerCase();
        const open = tasks.open.filter((item) => !q || String(item.text || "").toLowerCase().includes(q));
        const done = tasks.done.filter((item) => !q || String(item.text || "").toLowerCase().includes(q));
        const flags = warnings(data);
        const job = data.job || {};
        const known = resultLabel(job.last_status);
        const commits = ((data.repo && data.repo.commits) || []).slice(0, 8);
        const dirty = dirtyWake(data) || dirtyDigest(data) || dirtyPrompt(data);
        const active = document.activeElement;
        const focusId = active && active.id;
        const caret = active && typeof active.selectionStart === "number" ? active.selectionStart : null;
        const caretEnd = active && typeof active.selectionEnd === "number" ? active.selectionEnd : caret;

        box.innerHTML = `
            <div class="evolve-head">
                <span class="evolve-state ${state}">${esc(L(state))}</span>
                <label class="evolve-switch">
                    <input type="checkbox" id="evolve-enabled" ${data.enabled ? "checked" : ""} ${busy ? "disabled" : ""}>
                    <span>${esc(data.enabled ? L("switchOn") : L("switchOff"))}</span>
                </label>
                <button type="button" class="btn-icon evolve-refresh" onclick="loadEvolve()" aria-label="${esc(L("refresh"))}">
                    <span class="material-icons-round" aria-hidden="true">refresh</span>
                </button>
            </div>
            <div class="evolve-summary">
                ${why ? `<p>${esc(why)}</p>` : ""}
                <p><strong>${esc(L("next"))}.</strong> ${nextAt ? `${esc(absolute(nextAt))} · ${esc(relative(nextAt))}` : esc(L("unscheduled"))}</p>
                <p><strong>${esc(L("installs"))}.</strong> ${esc(String(data.applies ?? 0))} / ${esc(String(data.max_applies ?? 0))}</p>
                <p class="evolve-hint">${esc(L("installsHint"))}</p>
            </div>
            <div class="evolve-tabs" role="tablist">
                ${["overview", "tasks", "history", "settings"].map((name) => (
                    `<button type="button" data-evolve-tab="${name}" class="${tab === name ? "active" : ""}" role="tab" aria-selected="${tab === name}">${esc(L(name))}</button>`
                )).join("")}
            </div>
            <div class="evolve-pane">
                ${tab === "overview" ? overview() : ""}
                ${tab === "tasks" ? tasksPane() : ""}
                ${tab === "history" ? historyPane() : ""}
                ${tab === "settings" ? settingsPane() : ""}
            </div>
            ${detail ? `<aside class="evolve-drawer" role="dialog">
                <button type="button" class="evolve-drawer-close" id="evolve-drawer-close">×</button>
                <div class="evolve-md">${detailHtml(detail)}</div>
            </aside>` : ""}`;

        const prompt = document.getElementById("evolve-prompt");
        if (prompt) prompt.value = campaign;
        const digestBox = document.getElementById("evolve-digest");
        if (digestBox) digestBox.value = digestText;
        if (focusId) {
            const el = document.getElementById(focusId);
            if (el) {
                el.focus({ preventScroll: true });
                if (caret != null && el.setSelectionRange) {
                    try { el.setSelectionRange(caret, caretEnd); } catch (_) { /* search inputs can reject a range */ }
                }
            }
        }

        function overview() {
            const running = data.code === 5;
            const preview = tasks.open.slice(0, 3);
            return `<div class="evolve-stack">
                ${flags.length ? `<section class="evolve-card evolve-alert"><h3>${esc(L("warnings"))}</h3>${flags.map((line) => `<p>${esc(line)}</p>`).join("")}</section>` : ""}
                <section class="evolve-card">
                    <h3>${esc(L("nowTitle"))}</h3>
                    ${running ? `<p>${esc(L("since"))} ${esc(absolute(Date.parse(data.running_since || "") || job.last_run_at_ms) || data.running_since || "—")}</p>` : `<p class="evolve-empty">${esc(L("nowEmpty"))}</p>`}
                </section>
                <section class="evolve-card">
                    <h3>${esc(L("lastTitle"))}</h3>
                    ${known ? `<p><span class="evolve-result ${esc(job.last_status)}">${esc(known)}</span> ${esc(absolute(job.last_run_at_ms) || "")}</p>` : `<p class="evolve-empty">${esc(L("lastUnknown"))}</p>`}
                </section>
                <section class="evolve-card">
                    <h3>${esc(L("queue"))}</h3>
                    ${preview.length ? preview.map((item) => `<p class="evolve-task-title">${esc(item.text || "")}</p>`).join("") : `<p class="evolve-empty">${esc(L("empty"))}</p>`}
                    <button type="button" class="evolve-link" data-evolve-tab="tasks">${esc(L("allTasks"))}</button>
                </section>
            </div>`;
        }

        function tasksPane() {
            return `<div class="evolve-stack">
                <input id="evolve-search" class="evolve-search" type="search" value="${esc(query)}" placeholder="${esc(L("search"))}" aria-label="${esc(L("search"))}">
                <section class="evolve-card">
                    <h3>${esc(L("open"))} ${tasks.open.length}</h3>
                    <div data-task-bucket="open">${taskList(open, q ? L("noMatch") : L("empty"))}</div>
                </section>
                <section class="evolve-card">
                    <h3>${esc(L("done"))} ${tasks.done.length}</h3>
                    <div data-task-bucket="done">${taskList(done, q ? L("noMatch") : L("empty"))}</div>
                </section>
            </div>`;
        }

        function historyPane() {
            const events = [];
            if (Number(job.last_run_at_ms)) {
                events.push({
                    ms: Number(job.last_run_at_ms),
                    when: absolute(job.last_run_at_ms),
                    zone: "",
                    type: L("wake"),
                    result: known,
                    status: known ? (job.last_status || "") : "",
                    text: "",
                });
            }
            for (const item of noteItems(data)) {
                const raw = String(item.text || "");
                const dated = raw.match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(?:\s+([A-Za-z]{2,5}))?/);
                const body = dated ? raw.slice(dated[0].length).replace(/^[\s:.-]+/, "") : raw;
                const ms = dated ? Date.parse(`${dated[1]}T${dated[2]}:00`) : 0;
                events.push({
                    ms: Number.isFinite(ms) ? ms : 0,
                    when: dated ? `${dated[1].slice(5)} ${dated[2]}` : "",
                    zone: dated && dated[3] ? dated[3] : "",
                    type: L("chronicle"),
                    result: "",
                    status: "",
                    text: body,
                });
            }
            events.sort((a, b) => b.ms - a.ms);
            return `<div class="evolve-stack">
                <p class="evolve-hint">${esc(L("zone"))}: ${esc(zoneName())}</p>
                <section class="evolve-card">
                    ${events.length ? events.map((item) => `<article class="evolve-event">
                        <time>${esc(item.when || "—")}${item.zone ? ` ${esc(item.zone)}` : ""}</time>
                        <span>${esc(item.type)}</span>
                        ${item.result ? `<span class="evolve-result ${esc(item.status)}">${esc(item.result)}</span>` : `<span class="evolve-dash">—</span>`}
                        ${item.text ? (item.text.length > 160 ? `<details><summary>${esc(item.text)}</summary><p>${esc(item.text)}</p></details>` : `<p>${esc(item.text)}</p>`) : ""}
                    </article>`).join("") : `<p class="evolve-empty">${esc(L("empty"))}</p>`}
                </section>
                <details class="evolve-card">
                    <summary>${esc(L("commits"))}</summary>
                    ${commits.length ? commits.map((item) => `<p class="evolve-commit"><code>${esc(String(item.sha || "").slice(0, 7))}</code> ${esc(item.subject || "")} <span>${esc(item.date || "")}</span></p>`).join("") : `<p class="evolve-empty">${esc(L("empty"))}</p>`}
                </details>
            </div>`;
        }

        function settingsPane() {
            return `<div class="evolve-stack">
                ${dirty ? `<p class="evolve-dirty">${esc(L("dirty"))}</p>` : ""}
                ${note ? `<p class="evolve-note">${esc(note)}</p>` : ""}
                <section class="evolve-card">
                    <h3>${esc(L("schedule"))}</h3>
                    <label class="evolve-field"><span>${esc(L("every"))}</span><select id="evolve-every">${everyOptions}</select></label>
                </section>
                <section class="evolve-card">
                    <h3>${esc(L("model"))}</h3>
                    ${combo("evolve-model", modelValue)}
                </section>
                <section class="evolve-card">
                    <h3>${esc(L("tools"))}</h3>
                    <p class="evolve-hint">${esc(L("mcpHint"))}</p>
                    <div class="evolve-mcp" id="evolve-tools">${servers.length ? servers.map((name) => (
                        `<label><input type="checkbox" value="${esc(name)}" ${picked.includes(name) ? "checked" : ""}><span><strong>${esc(toolName(name))}</strong><small>${esc(name)}</small></span></label>`
                    )).join("") : `<span class="evolve-empty">${esc(L("empty"))}</span>`}</div>
                </section>
                <button type="button" class="btn-primary evolve-save" id="evolve-settings-save">${esc(L("save"))}</button>
                ${digest ? `<section class="evolve-card">
                    <h3>${esc(L("digest"))}</h3>
                    <label class="evolve-switch"><input type="checkbox" id="evolve-digest-enabled" ${digestOn ? "checked" : ""}><span>${esc(digestOn ? L("digest") : L("digestOff"))}</span></label>
                    <p class="evolve-hint">${esc(digest.expr || "—")}${digest.tz ? ` · ${esc(digest.tz)}` : ""}</p>
                    ${combo("evolve-digest-model", digestModel)}
                    <textarea id="evolve-digest" maxlength="8000"></textarea>
                    <button type="button" class="btn-primary evolve-save" id="evolve-digest-save">${esc(L("save"))}</button>
                </section>` : ""}
                <details class="evolve-card">
                    <summary>${esc(L("advanced"))}</summary>
                    <h3>${esc(L("prompt"))}</h3>
                    <p class="evolve-hint">${esc(L("promptHint"))}</p>
                    <textarea id="evolve-prompt" maxlength="8000" spellcheck="false"></textarea>
                    <button type="button" class="btn-primary evolve-save" id="evolve-save">${esc(L("save"))}</button>
                </details>
            </div>`;
        }
    }

    function detailHtml(text) {
        const raw = String(text || "");
        if (/[`#*]/.test(raw) && typeof renderMarkdown === "function") {
            try { return renderMarkdown(raw); } catch (_) { /* show the source text */ }
        }
        return `<p>${esc(raw)}</p>`;
    }

    async function loadEvolve() {
        const box = document.getElementById("evolve-content");
        if (!box) return;
        if (!box.dataset.loaded) box.innerHTML = `<div class="evolve-loading">${esc(L("loading"))}</div>`;
        setRefreshing(true);
        try {
            if (!modelsLoaded && typeof ensureAvailableModels === "function") {
                try { models = await ensureAvailableModels() || []; } catch (_) { models = []; }
                modelsLoaded = true;
            }
            const res = await authFetch("/api/evolve");
            if (!res.ok) throw new Error(String(res.status));
            const data = await res.json();
            box.dataset.loaded = "1";
            if (editing()) { pending = data; return; }
            pending = null;
            render(data);
        } catch (err) {
            if (editing() || (form && last && (dirtyWake(last) || dirtyDigest(last) || dirtyPrompt(last)))) return;
            box.innerHTML = `<div class="evolve-error">${esc(L("fail"))}: ${esc(err.message)}</div>`;
        } finally {
            setRefreshing(false);
        }
    }

    async function postEvolve(body) {
        const res = await authFetch("/api/evolve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(String(res.status));
        return res.json();
    }

    function taskAt(bucket, index) {
        if (!last) return "";
        const tasks = splitTasks(taskItems(last));
        const q = query.trim().toLowerCase();
        const rows = (bucket === "done" ? tasks.done : tasks.open).filter((item) => !q || String(item.text || "").toLowerCase().includes(q));
        return rows[index] ? rows[index].text : "";
    }

    window.loadEvolve = loadEvolve;

    document.addEventListener("shiba-modal-opened", (event) => {
        if (!event.detail || event.detail.id !== "evolve-modal") return;
        loadEvolve();
        if (timer) clearInterval(timer);
        timer = setInterval(() => {
            const modal = document.getElementById("evolve-modal");
            if (!modal || !modal.classList.contains("active")) {
                clearInterval(timer);
                timer = null;
                return;
            }
            loadEvolve();
        }, 8000);
    });

    document.addEventListener("focusout", () => {
        setTimeout(() => {
            if (!pending || editing()) return;
            const data = pending;
            pending = null;
            render(data);
        }, 0);
    });

    document.addEventListener("change", (event) => {
        if (!event.target || !event.target.closest || !event.target.closest("#evolve-content")) return;
        if (event.target.id !== "evolve-enabled") {
            paintDraft();
            return;
        }
        busy = true;
        note = "";
        postEvolve({ enabled: event.target.checked }).then((data) => render(data)).catch(() => loadEvolve()).finally(() => { busy = false; });
    });

    document.addEventListener("input", (event) => {
        if (event.target && event.target.id === "evolve-search") {
            query = event.target.value;
            if (last) render(last);
            return;
        }
        if (event.target && event.target.closest && event.target.closest("#evolve-content")) paintDraft();
        if (event.target && event.target.classList && event.target.closest(".evolve-combo") && event.target.type === "text") {
            fillCombo(event.target);
        }
    });

    function pickModel(pick) {
        const hidden = document.getElementById(pick.dataset.modelFor);
        const wrap = hidden && hidden.closest(".evolve-combo");
        const input = wrap && wrap.querySelector("input[type=text]");
        if (hidden) hidden.value = pick.dataset.modelPick || "";
        if (input) input.value = modelName(hidden ? hidden.value : "");
        if (wrap) wrap.querySelector(".evolve-combo-list").hidden = true;
        paintDraft();
    }

    function paintDraft() {
        if (!last || tab !== "settings") return;
        readForm();
        const dirty = dirtyWake(last) || dirtyDigest(last) || dirtyPrompt(last);
        const stack = document.querySelector("#evolve-content .evolve-pane .evolve-stack");
        if (!stack) return;
        let el = stack.querySelector(":scope > .evolve-dirty");
        if (dirty && !el) {
            el = document.createElement("p");
            el.className = "evolve-dirty";
            el.textContent = L("dirty");
            stack.prepend(el);
        } else if (!dirty && el) el.remove();
        if (dirty) {
            note = "";
            stack.querySelector(":scope > .evolve-note")?.remove();
        }
    }

    document.addEventListener("mousedown", (event) => {
        const pick = event.target && event.target.closest && event.target.closest("[data-model-pick]");
        if (!pick) return;
        event.preventDefault();
        pickModel(pick);
    });

    document.addEventListener("focusin", (event) => {
        const input = event.target;
        if (!input || !input.closest || input.type !== "text" || !input.closest(".evolve-combo")) return;
        fillCombo(input);
    });

    document.addEventListener("click", (event) => {
        const target = event.target;
        if (!target || !target.closest) return;
        const tabBtn = target.closest("[data-evolve-tab]");
        if (tabBtn && last) {
            readForm();
            tab = tabBtn.dataset.evolveTab;
            render(last);
            return;
        }
        const taskBtn = target.closest("[data-task]");
        if (taskBtn) {
            const bucket = taskBtn.parentElement && taskBtn.parentElement.dataset.taskBucket;
            detail = taskAt(bucket, Number(taskBtn.dataset.task));
            if (last) render(last);
            return;
        }
        if (target.id === "evolve-drawer-close") {
            detail = null;
            if (last) render(last);
            return;
        }
        document.querySelectorAll(".evolve-combo-list").forEach((list) => {
            if (!list.contains(target)) list.hidden = true;
        });
        const id = target.id;
        if (id !== "evolve-save" && id !== "evolve-digest-save" && id !== "evolve-settings-save") return;
        readForm();
        let body;
        if (id === "evolve-settings-save") {
            body = {
                every_min: Number(document.getElementById("evolve-every")?.value || 10),
                model: document.getElementById("evolve-model")?.value || "",
                mcps: [...document.querySelectorAll("#evolve-tools input:checked")].map((el) => el.value),
            };
        } else if (id === "evolve-digest-save") {
            body = {
                digest: document.getElementById("evolve-digest")?.value || "",
                digest_model: document.getElementById("evolve-digest-model")?.value || "",
                digest_enabled: Boolean(document.getElementById("evolve-digest-enabled")?.checked),
            };
        } else {
            body = { campaign: document.getElementById("evolve-prompt")?.value || "" };
        }
        postEvolve(body).then((data) => {
            const keys = id === "evolve-settings-save"
                ? ["every", "model", "mcps"]
                : (id === "evolve-digest-save" ? ["digest", "digestModel", "digestOn"] : ["campaign"]);
            keys.forEach((key) => { if (form) delete form[key]; });
            note = L("saved");
            skipRead = true;
            render(data);
        }).catch((err) => {
            note = err.message;
            if (last) render(last);
        });
    });

    function localizeButton() {
        const btn = document.getElementById("btn-evolve");
        const title = document.getElementById("evolve-title");
        if (btn) {
            btn.title = L("title");
            btn.setAttribute("aria-label", L("title"));
        }
        if (title) title.textContent = L("title");
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", localizeButton);
    else localizeButton();
})();
