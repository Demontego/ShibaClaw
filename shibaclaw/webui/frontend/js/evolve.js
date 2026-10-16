(function () {
    const EN = {
        title: "Evolution",
        loading: "Loading…",
        fail: "Failed to load evolution",
        ready: "ready",
        off: "off",
        panic: "panic",
        progress: "in progress",
        budget: "daily budget",
        cooldown: "cooldown",
        chronicle: "Chronicle",
        backlog: "Backlog",
        patterns: "Patterns",
        world: "World",
        commits: "Recent commits",
        empty: "Nothing here yet.",
        branch: "branch",
        dirty: "dirty",
        clean: "clean",
        alarm: "alarm",
        last: "last wake",
        body: "running commit",
        applies: "applies",
    };
    const RU = {
        title: "Эволюция",
        loading: "Загрузка…",
        fail: "Не вышло прочитать эволюцию",
        ready: "готова",
        off: "выкл",
        panic: "panic",
        progress: "виток",
        budget: "бюджет дня",
        cooldown: "пауза",
        chronicle: "Хроника",
        backlog: "Бэклог",
        patterns: "Классы",
        world: "Мир",
        commits: "Последние коммиты",
        empty: "Пока пусто.",
        branch: "ветка",
        dirty: "грязно",
        clean: "чисто",
        alarm: "будильник",
        last: "прошлый ход",
        body: "коммит в процессе",
        applies: "установки",
    };

    let timer = null;
    let pending = null;
    let lastData = null;

    function L(key) {
        const ru = window.i18n && window.i18n.getLocale && window.i18n.getLocale() === "ru";
        const dict = ru ? RU : EN;
        return dict[key] || EN[key] || key;
    }

    function esc(text) {
        if (typeof escapeHtml === "function") return escapeHtml(text);
        const el = document.createElement("div");
        el.textContent = text ?? "";
        return el.innerHTML;
    }

    function when(ms) {
        const n = Number(ms);
        if (!n) return "—";
        try {
            return new Date(n).toLocaleString();
        } catch (_) {
            return "—";
        }
    }

    function label(code) {
        if (code === 2) return L("panic");
        if (code === 3) return L("off");
        if (code === 5) return L("progress");
        if (code === 6) return L("budget");
        if (code === 7) return L("cooldown");
        return L("ready");
    }

    function pre(title, text) {
        const body = (text || "").trim();
        return `<section class="evolve-block"><h3>${esc(title)}</h3><pre>${esc(body || L("empty"))}</pre></section>`;
    }

    function render(data) {
        const box = document.getElementById("evolve-content");
        if (!box) return;
        const job = data.job || {};
        const repo = data.repo;
        const body = data.body || {};
        const commits = (repo && repo.commits) || [];
        const commitHtml = commits.length
            ? commits.map((c) => `<li><code>${esc(c.sha)}</code> ${esc(c.subject)} <span>${esc(c.date)}</span></li>`).join("")
            : `<li>${esc(L("empty"))}</li>`;
        const repoLine = repo
            ? `${esc(repo.name)} · ${L("branch")} <code>${esc(repo.branch)}</code> · ${repo.dirty ? L("dirty") : L("clean")}`
            : L("empty");
        box.innerHTML = `
            <div class="evolve-status">
                <span class="evolve-chip">${esc(label(data.code))}</span>
                <span>${esc(L("applies"))} ${esc(String(data.applies))}/${esc(String(data.max_applies))}</span>
                <span>${esc(L("alarm"))} ${job.every_ms ? Math.round(job.every_ms / 60000) + "m" : "—"} · ${esc(when(job.next_run_at_ms))}</span>
                <span>${esc(L("last"))} ${esc(job.last_status || "—")} · ${esc(when(job.last_run_at_ms))}</span>
                <span>${esc(L("body"))} ${esc(body.sha ? String(body.sha).slice(0, 12) : "—")}</span>
            </div>
            <p class="evolve-repo">${repoLine}</p>
            ${pre(L("chronicle"), data.chronicle)}
            ${pre(L("backlog"), data.backlog)}
            ${pre(L("patterns"), data.patterns)}
            ${pre(L("world"), data.world)}
            <section class="evolve-block"><h3>${esc(L("commits"))}</h3><ul class="evolve-commits">${commitHtml}</ul></section>`;
    }

    async function loadEvolve() {
        const box = document.getElementById("evolve-content");
        const modal = document.getElementById("evolve-modal");
        if (!box || !modal?.classList.contains("active") || pending) return;
        const request = {};
        pending = request;
        if (!box.dataset.loaded) {
            box.innerHTML = `<div class="evolve-loading">${esc(L("loading"))}</div>`;
        }
        try {
            const res = await authFetch("/api/evolve");
            if (!res.ok) throw new Error(String(res.status));
            const data = await res.json();
            if (pending !== request || !modal.classList.contains("active")) return;
            lastData = data;
            render(data);
            box.dataset.loaded = "1";
        } catch (err) {
            if (pending === request && modal.classList.contains("active")) {
                box.innerHTML = `<div class="evolve-error">${esc(L("fail"))}: ${esc(err.message)}</div>`;
            }
        } finally {
            if (pending === request) pending = null;
        }
    }

    window.loadEvolve = loadEvolve;
    window.stopEvolvePolling = function () {
        if (timer) clearInterval(timer);
        timer = null;
        pending = null;
    };

    document.addEventListener("shiba-modal-opened", (event) => {
        if (!event.detail || event.detail.id !== "evolve-modal") return;
        loadEvolve();
        if (timer) clearInterval(timer);
        timer = setInterval(() => {
            const modal = document.getElementById("evolve-modal");
            if (!modal || !modal.classList.contains("active")) {
                window.stopEvolvePolling();
                return;
            }
            loadEvolve();
        }, 8000);
    });

    document.addEventListener("shibaclaw:localechange", () => {
        if (lastData && document.getElementById("evolve-modal")?.classList.contains("active")) render(lastData);
    });
})();
