/**
 * Lightweight WebUI i18n — no external deps.
 * Catalogs: window.__I18N_CATALOGS__ (see i18n_catalogs.js).
 * Locale persists in localStorage (`shibaclaw_locale`).
 */
(function () {
    const STORAGE_KEY = "shibaclaw_locale";

    const LOCALES = [
        { id: "en", label: "English", short: "EN" },
        { id: "zh-CN", label: "简体中文", short: "中文" },
        { id: "es", label: "Español", short: "ES" },
        { id: "pt-BR", label: "Português (BR)", short: "PT" },
        { id: "ja", label: "日本語", short: "JA" },
        { id: "de", label: "Deutsch", short: "DE" },
        { id: "fr", label: "Français", short: "FR" },
        { id: "ru", label: "Русский", short: "RU" },
    ];

    const catalogs = (typeof window !== "undefined" && window.__I18N_CATALOGS__) || { en: {} };

    let currentLocale = "en";

    function normalizeLocale(raw) {
        if (!raw) return null;
        const s = String(raw).trim();
        if (catalogs[s]) return s;
        const lower = s.toLowerCase();
        if (lower === "zh" || lower.startsWith("zh-")) return "zh-CN";
        if (lower === "pt" || lower.startsWith("pt-")) return "pt-BR";
        const base = lower.split("-")[0];
        const hit = LOCALES.find((l) => l.id.toLowerCase() === lower || l.id.toLowerCase().startsWith(base));
        return hit && catalogs[hit.id] ? hit.id : null;
    }

    function detectLocale() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            const fromStore = normalizeLocale(stored);
            if (fromStore) return fromStore;
        } catch (_) { /* ignore */ }
        const nav = (navigator.languages && navigator.languages[0]) || navigator.language || "en";
        return normalizeLocale(nav) || "en";
    }

    function t(key, vars) {
        const cat = catalogs[currentLocale] || catalogs.en || {};
        const en = catalogs.en || {};
        let s = cat[key] || en[key] || key;
        if (vars && typeof vars === "object") {
            for (const [k, v] of Object.entries(vars)) {
                s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
            }
        }
        return s;
    }

    function applyI18n(root) {
        const scope = root || document;
        scope.querySelectorAll("[data-i18n]").forEach((el) => {
            const key = el.getAttribute("data-i18n");
            if (!key) return;
            el.textContent = t(key);
        });
        scope.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
            const key = el.getAttribute("data-i18n-placeholder");
            if (key) el.setAttribute("placeholder", t(key));
        });
        scope.querySelectorAll("[data-i18n-title]").forEach((el) => {
            const key = el.getAttribute("data-i18n-title");
            if (key) el.setAttribute("title", t(key));
        });
        scope.querySelectorAll("[data-i18n-aria]").forEach((el) => {
            const key = el.getAttribute("data-i18n-aria");
            if (key) el.setAttribute("aria-label", t(key));
        });
        document.documentElement.lang = currentLocale === "zh-CN" ? "zh-CN"
            : currentLocale === "pt-BR" ? "pt-BR"
                : currentLocale.split("-")[0];
    }

    function refreshDynamicUi() {
        try {
            if (typeof window._renderSessionsList === "function") window._renderSessionsList();
            else if (typeof window.loadHistory === "function") window.loadHistory();
        } catch (_) { /* ignore */ }
        try {
            if (typeof window.renderKBSelectorDropdown === "function") window.renderKBSelectorDropdown();
        } catch (_) { /* ignore */ }
        try {
            if (typeof window.loadAutomationPanel === "function") window.loadAutomationPanel();
        } catch (_) { /* ignore */ }
        try {
            if (typeof window.updateSendButton === "function") window.updateSendButton();
        } catch (_) { /* ignore */ }
        try {
            if (typeof window.updateReasoningSelectorDisplay === "function") {
                window.updateReasoningSelectorDisplay();
            }
        } catch (_) { /* ignore */ }
    }

    function setLocale(locale, opts) {
        const next = normalizeLocale(locale) || "en";
        currentLocale = next;
        try {
            localStorage.setItem(STORAGE_KEY, next);
        } catch (_) { /* ignore */ }
        applyI18n();
        renderLangMenu();
        if (!(opts && opts.skipHealth)) {
            if (typeof window.updateUIFromHealthState === "function") {
                try { window.updateUIFromHealthState(); } catch (_) { /* ignore */ }
            } else if (typeof window.checkGatewayHealth === "function") {
                try { window.checkGatewayHealth(); } catch (_) { /* ignore */ }
            }
        }
        if (!(opts && opts.skipDynamic)) refreshDynamicUi();
        document.dispatchEvent(new CustomEvent("shibaclaw:localechange", { detail: { locale: next } }));
        return next;
    }

    function getLocale() {
        return currentLocale;
    }

    function clockLocale() {
        if (currentLocale === "zh-CN") return "zh-CN";
        if (currentLocale === "pt-BR") return "pt-BR";
        return currentLocale;
    }

    function closeLangMenu() {
        const menu = document.getElementById("lang-menu");
        const btn = document.getElementById("btn-lang");
        if (menu) menu.hidden = true;
        if (btn) btn.setAttribute("aria-expanded", "false");
    }

    function renderLangMenu() {
        const menu = document.getElementById("lang-menu");
        const btn = document.getElementById("btn-lang");
        if (!menu) return;
        menu.innerHTML = LOCALES.map((loc) => {
            const active = loc.id === currentLocale ? " is-active" : "";
            return `<button type="button" class="lang-option${active}" role="option" data-locale="${loc.id}" aria-selected="${loc.id === currentLocale}">${loc.label}</button>`;
        }).join("");
        menu.querySelectorAll(".lang-option").forEach((el) => {
            el.addEventListener("click", (e) => {
                e.stopPropagation();
                setLocale(el.getAttribute("data-locale"));
                closeLangMenu();
            });
        });
        if (btn) {
            btn.setAttribute("title", t("footer.language"));
            btn.setAttribute("aria-label", t("footer.language"));
        }
    }

    function initLangSwitcher() {
        const btn = document.getElementById("btn-lang");
        const menu = document.getElementById("lang-menu");
        if (!btn || !menu) return;
        renderLangMenu();
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const open = menu.hidden;
            menu.hidden = !open;
            btn.setAttribute("aria-expanded", open ? "true" : "false");
        });
        document.addEventListener("click", (e) => {
            if (!menu.hidden && !menu.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
                closeLangMenu();
            }
        });
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") closeLangMenu();
        });
    }

    currentLocale = detectLocale();

    window.i18n = {
        LOCALES,
        t,
        setLocale,
        getLocale,
        applyI18n,
        clockLocale,
        initLangSwitcher,
        refreshDynamicUi,
    };
    window.t = t;
})();
