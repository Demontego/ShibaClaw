let _availableModels = [];
let _fetchingModelsPromise = null;
let _hasFetchedModels = false;
const SETTINGS_MODEL_PICKERS = [
    {
        valueId: "s-agent-model",
        buttonId: "s-agent-model-button",
        displayId: "s-agent-model-display",
        providerId: "s-agent-model-provider",
        menuId: "s-agent-model-menu",
        searchId: "s-agent-model-search",
        listId: "s-agent-model-list",
        emptyLabel: "Select a default model",
        emptyProvider: "New sessions",
        emptyChoiceLabel: null,
        emptyChoiceProvider: null,
        allowEmpty: false,
    },
    {
        valueId: "s-agent-consolidationModel",
        buttonId: "s-agent-consolidationModel-button",
        displayId: "s-agent-consolidationModel-display",
        providerId: "s-agent-consolidationModel-provider",
        menuId: "s-agent-consolidationModel-menu",
        searchId: "s-agent-consolidationModel-search",
        listId: "s-agent-consolidationModel-list",
        emptyLabel: "Same as default session model",
        emptyProvider: "Inherits",
        emptyChoiceLabel: "Same as default session model",
        emptyChoiceProvider: "Inherits",
        allowEmpty: true,
    },
];
let _settingsModelPickersInitialized = false;

async function fetchModels() {
    try {
        const res = await authFetch("/api/models");
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || "Failed to fetch models");
        }
        if (Array.isArray(data.errors) && data.errors.length) {
            console.warn("Some providers failed to return models", data.errors);
        }
        return data.models || [];
    } catch (e) {
        console.error("Failed to fetch models", e);
        return [];
    }
}

async function ensureAvailableModels(listEl = null) {
    if (_availableModels.length || _hasFetchedModels) {
        return _availableModels;
    }
    if (_fetchingModelsPromise) {
        return _fetchingModelsPromise;
    }
    if (listEl) {
        listEl.innerHTML = `<div style="padding: 10px; text-align: center; color: var(--text-secondary); font-size: 0.85rem;">${escapeHtml(typeof t === "function" ? t("chat.loading_models") : "Loading models...")}</div>`;
    }
    _fetchingModelsPromise = fetchModels().then(models => {
        _availableModels = models || [];
        _hasFetchedModels = true;
        _fetchingModelsPromise = null;
        return _availableModels;
    }).catch(err => {
        _hasFetchedModels = true;
        _fetchingModelsPromise = null;
        return [];
    });
    return _fetchingModelsPromise;
}

function filterModelsByQuery(query) {
    const q = (query || "").trim().toLowerCase();
    if (!q) {
        return _availableModels.slice();
    }
    return _availableModels.filter(m =>
        (m.name || "").toLowerCase().includes(q)
        || (m.raw_id || m.id || "").toLowerCase().includes(q)
        || (m.provider_label || "").toLowerCase().includes(q)
        || (m.provider || "").toLowerCase().includes(q)
    );
}

function findAvailableModel(modelId) {
    if (!modelId) {
        return null;
    }
    const cleanId = String(modelId).trim().toLowerCase();
    const rawName = cleanId.split("/").pop();
    return _availableModels.find(m => {
        const mId = (m.id || "").toLowerCase();
        const mRaw = (m.raw_id || "").toLowerCase();
        return mId === cleanId || mRaw === cleanId || mRaw === rawName || mId.endsWith("/" + rawName);
    }) || null;
}

function createModelListItem(model, currentModelId, onSelect) {
    const item = document.createElement("div");
    item.className = "model-item" + (model.id === currentModelId ? " selected" : "");

    const nameEl = document.createElement("span");
    nameEl.className = "model-item-name";
    nameEl.textContent = model.name || model.raw_id || model.id || "";

    const providerEl = document.createElement("span");
    providerEl.className = "model-item-provider";
    providerEl.textContent = model.provider_label || model.provider || "";

    item.appendChild(nameEl);
    item.appendChild(providerEl);
    item.title = [model.raw_id || model.id || "", model.provider_label || model.provider || ""].filter(Boolean).join(" • ");
    item.addEventListener("click", (e) => {
        e.stopPropagation();
        onSelect(model);
    });
    return item;
}

function renderModelList(list, models, currentModelId, onSelect, extraItems = []) {
    list.innerHTML = "";
    const allItems = [...extraItems, ...models];
    if (!allItems.length) {
        list.innerHTML = `<div style="padding: 10px; text-align: center; color: var(--text-secondary); font-size: 0.85rem;">${escapeHtml(typeof t === "function" ? t("chat.no_models") : "No models found")}</div>`;
        return;
    }
    allItems.forEach(model => list.appendChild(createModelListItem(model, currentModelId, onSelect)));
}

let _activeSessionReasoningEffort = null;

function checkModelSupportsReasoning(modelId) {
    if (!modelId) return false;
    const model = findAvailableModel(modelId);
    if (model && typeof model.supports_reasoning === "boolean") {
        return model.supports_reasoning;
    }
    const mid = String(modelId).toLowerCase().trim();
    const raw = mid.split("/").pop();
    const base = raw.split(":")[0];

    // 1. OpenAI o-series & Azure/OpenRouter o-deployments (o1, o3, o4)
    if (base.startsWith("o1") || base.startsWith("o3") || base.startsWith("o4") || base.includes("-o1") || base.includes("o1-") || base.includes("-o3") || base.includes("o3-") || base.includes("-o4") || base.includes("o4-")) {
        return true;
    }
    // 2. Anthropic Claude 3.7+
    if (base.includes("claude-3-7") || base.includes("claude-3.7") || base.includes("claude-4")) {
        return true;
    }
    // 3. Gemini thinking models
    if (base.includes("thinking") || base.includes("gemini-2.5") || base.includes("gemini-3")) {
        return true;
    }
    // 4. DeepSeek R1 / Reasoner models
    if (base.includes("deepseek-r1") || base.includes("reasoner") || base.includes("-r1") || base.includes("r1-") || raw.includes("r1:") || base === "r1") {
        return true;
    }
    // 5. Qwen QwQ / QvQ
    if (base.includes("qwq") || base.includes("qvq")) {
        return true;
    }
    // 6. Grok 3 / xAI
    if (base.includes("grok-3") || base.includes("grok-beta")) {
        return true;
    }
    // 7. Kimi / Moonshot
    if (base.includes("kimi-k1.5") || base.includes("kimi-k2") || (base.includes("kimi") && (base.includes("1.5") || base.includes("2")))) {
        return true;
    }
    // 8. GLM zero
    if (base.includes("glm-4-zero") || base.includes("glm-zero")) {
        return true;
    }
    // 9. Generic open reasoning models & keywords
    if (base.includes("marco-o1") || base.includes("sky-t1") || base.includes("smallthinker") || base.includes("reasoning") || base.includes("think") || base.includes("thought")) {
        return true;
    }

    return false;
}

function updateReasoningSelectorDisplay(reasoningEffort = null, modelId = null) {
    if (typeof reasoningEffort !== "undefined" && reasoningEffort !== null) {
        _activeSessionReasoningEffort = reasoningEffort;
    }
    const currentModel = modelId || state.activeModelId || "";
    const btn = document.getElementById("btn-reasoning-select");
    const display = document.getElementById("active-reasoning-display");
    const menu = document.getElementById("reasoning-dropdown-menu");
    const list = document.getElementById("reasoning-dropdown-list");
    if (!display || !btn) return;

    const supports = checkModelSupportsReasoning(currentModel);
    if (!supports) {
        display.textContent = typeof t === "function" ? t("chat.effort_na") : "Effort: N/A";
        btn.title = typeof t === "function" ? t("chat.effort_unsupported") : "Reasoning effort not supported for current model";
        btn.classList.add("disabled");
        btn.style.opacity = "0.5";
        btn.style.cursor = "not-allowed";
        if (menu) menu.style.display = "none";
        return;
    }

    btn.classList.remove("disabled");
    btn.style.opacity = "";
    btn.style.cursor = "";
    btn.title = typeof t === "function" ? t("chat.reasoning_title") : "Change reasoning effort for active session";

    const effortStr = _activeSessionReasoningEffort ? String(_activeSessionReasoningEffort).toLowerCase() : "";
    let label = typeof t === "function" ? t("chat.effort_default") : "Default";
    if (effortStr === "low") label = typeof t === "function" ? t("chat.effort_low") : "Low";
    else if (effortStr === "medium") label = typeof t === "function" ? t("chat.effort_medium") : "Medium";
    else if (effortStr === "high") label = typeof t === "function" ? t("chat.effort_high") : "High";

    display.textContent = (typeof t === "function" ? t("chat.effort_prefix") : "Effort: ") + label;

    if (list) {
        renderReasoningDropdownList(list, effortStr);
    }
}

function renderReasoningDropdownList(container, currentEffort) {
    container.innerHTML = "";
    const options = [
        { value: "", label: typeof t === "function" ? t("chat.effort_default") : "Default", desc: typeof t === "function" ? t("chat.effort_default_desc") : "Use provider default effort" },
        { value: "low", label: typeof t === "function" ? t("chat.effort_low") : "Low", desc: typeof t === "function" ? t("chat.effort_low_desc") : "Faster, lower reasoning depth" },
        { value: "medium", label: typeof t === "function" ? t("chat.effort_medium") : "Medium", desc: typeof t === "function" ? t("chat.effort_medium_desc") : "Balanced speed and depth" },
        { value: "high", label: typeof t === "function" ? t("chat.effort_high") : "High", desc: typeof t === "function" ? t("chat.effort_high_desc") : "Deep reasoning, slower" }
    ];

    options.forEach(opt => {
        const item = document.createElement("div");
        const isSelected = (opt.value === currentEffort) || (!opt.value && !currentEffort);
        item.className = "model-item" + (isSelected ? " selected" : "");
        item.title = opt.desc;
        item.style.cssText = "display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; cursor: pointer; border-radius: 6px; font-size: 12px; font-weight: 500; min-height: 28px; transition: background 0.15s ease;";
        
        const nameEl = document.createElement("span");
        nameEl.className = "model-item-name";
        nameEl.style.cssText = "font-size: 12px; font-weight: 500; color: var(--text-primary);";
        nameEl.textContent = opt.label;

        item.appendChild(nameEl);

        if (isSelected) {
            const checkEl = document.createElement("span");
            checkEl.className = "material-icons-round";
            checkEl.style.cssText = "font-size: 14px; color: var(--shiba-gold); margin-left: 8px;";
            checkEl.textContent = "check";
            item.appendChild(checkEl);
        }

        item.addEventListener("click", async (e) => {
            e.stopPropagation();
            const val = opt.value || null;
            _activeSessionReasoningEffort = val;
            updateReasoningSelectorDisplay(val, state.activeModelId);
            const menu = document.getElementById("reasoning-dropdown-menu");
            if (menu) menu.style.display = "none";

            if (state.sessionId) {
                try {
                    await authFetch("/api/sessions/" + encodeURIComponent(state.sessionId), {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ reasoning_effort: val })
                    });
                } catch (err) {
                    console.error("Failed to update session reasoning effort", err);
                }
            }
        });

        container.appendChild(item);
    });
}

function setupReasoningSelector() {
    const btn = document.getElementById("btn-reasoning-select");
    const menu = document.getElementById("reasoning-dropdown-menu");
    if (!btn || !menu) return;

    btn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (btn.classList.contains("disabled")) return;
        const isHidden = menu.style.display === "none";
        if (isHidden) {
            menu.style.display = "block";
            updateReasoningSelectorDisplay(_activeSessionReasoningEffort, state.activeModelId);
        } else {
            menu.style.display = "none";
        }
    });

    document.addEventListener("click", (e) => {
        if (!menu.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
            menu.style.display = "none";
        }
    });
}

window.checkModelSupportsReasoning = checkModelSupportsReasoning;
window.updateReasoningSelectorDisplay = updateReasoningSelectorDisplay;

async function updateModelSelectorDisplay(modelId) {
    const display = document.getElementById("active-model-display");
    const btn = document.getElementById("btn-model-select");
    if (!display) return;
    let resolvedModelId = modelId;
    if (!resolvedModelId) {
        try {
            const cfgRes = await authFetch("/api/settings");
            const cfg = await cfgRes.json();
            resolvedModelId = cfg.agents?.defaults?.model || "";
        } catch (e) { }
    }

    state.activeModelId = resolvedModelId || "";

    await ensureAvailableModels();
    const match = findAvailableModel(resolvedModelId);
    const fullName = match ? (match.name || match.raw_id || match.id) : (resolvedModelId || "Default");
    display.textContent = fullName;

    if (btn) {
        const providerText = match && (match.provider_label || match.provider) ? ` (${match.provider_label || match.provider})` : "";
        const rawIdText = match && match.raw_id && match.raw_id !== fullName ? ` • ${match.raw_id}` : "";
        btn.title = typeof t === "function" ? t("chat.active_model", { name: `${fullName}${providerText}${rawIdText}` }) : `Active Model: ${fullName}${providerText}${rawIdText}`;
    }

    updateReasoningSelectorDisplay(_activeSessionReasoningEffort, resolvedModelId);
    if (typeof refreshTokenBadge === "function") {
        refreshTokenBadge();
    }
}


function closeSettingsModelMenus(exceptMenu = null) {
    SETTINGS_MODEL_PICKERS.forEach(cfg => {
        const menu = document.getElementById(cfg.menuId);
        if (menu && menu !== exceptMenu) {
            menu.style.display = "none";
        }
    });
}

async function updateSettingsModelPickerDisplay(config) {
    const input = document.getElementById(config.valueId);
    const display = document.getElementById(config.displayId);
    const provider = document.getElementById(config.providerId);
    if (!input || !display || !provider) {
        return;
    }

    const value = input.value.trim();
    if (!value && config.allowEmpty) {
        display.textContent = config.emptyLabel;
        provider.textContent = config.emptyProvider;
        provider.classList.add("settings-model-button-provider-placeholder");
        return;
    }
    if (!value) {
        display.textContent = config.emptyLabel;
        provider.textContent = config.emptyProvider;
        provider.classList.add("settings-model-button-provider-placeholder");
        return;
    }

    await ensureAvailableModels();
    const match = findAvailableModel(value);
    display.textContent = match ? (match.name || match.raw_id || match.id) : value;
    provider.textContent = match ? (match.provider_label || match.provider || "") : "Custom";
    provider.classList.toggle("settings-model-button-provider-placeholder", !match);
}

async function refreshSettingsModelPickers() {
    for (const config of SETTINGS_MODEL_PICKERS) {
        await updateSettingsModelPickerDisplay(config);
    }
}

function renderSettingsModelPickerOptions(config) {
    const list = document.getElementById(config.listId);
    const search = document.getElementById(config.searchId);
    const input = document.getElementById(config.valueId);
    if (!list || !search || !input) {
        return;
    }

    const models = filterModelsByQuery(search.value);
    const extraItems = [];
    if (config.allowEmpty) {
        extraItems.push({
            id: "",
            raw_id: "",
            name: config.emptyChoiceLabel,
            provider_label: config.emptyChoiceProvider,
            provider: "",
        });
    }

    renderModelList(
        list,
        models,
        input.value.trim(),
        (model) => {
            input.value = model.id || "";
            void updateSettingsModelPickerDisplay(config);
            const menu = document.getElementById(config.menuId);
            if (menu) {
                menu.style.display = "none";
            }
        },
        extraItems,
    );
}

function setupSettingsModelPickers() {
    if (_settingsModelPickersInitialized) {
        return;
    }

    SETTINGS_MODEL_PICKERS.forEach(config => {
        const button = document.getElementById(config.buttonId);
        const menu = document.getElementById(config.menuId);
        const search = document.getElementById(config.searchId);
        const list = document.getElementById(config.listId);
        if (!button || !menu || !search || !list) {
            return;
        }

        button.addEventListener("click", async (e) => {
            e.stopPropagation();
            const isOpen = menu.style.display === "flex";
            if (isOpen) {
                menu.style.display = "none";
                return;
            }

            closeSettingsModelMenus(menu);
            menu.style.display = "flex";
            await ensureAvailableModels(list);
            search.value = "";
            renderSettingsModelPickerOptions(config);
            search.focus();
        });

        menu.addEventListener("click", (e) => e.stopPropagation());
        search.addEventListener("input", debounce(() => renderSettingsModelPickerOptions(config), 250));
    });

    document.addEventListener("click", () => closeSettingsModelMenus());
    _settingsModelPickersInitialized = true;
}

function setupModelSelector() {
    const btn = document.getElementById("btn-model-select");
    const menu = document.getElementById("model-dropdown-menu");
    const search = document.getElementById("model-search-input");
    const list = document.getElementById("model-list-container");
    if (!btn || !menu) return;

    btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const isHidden = menu.style.display === "none";
        if (isHidden) {
            menu.style.display = "flex";
            await ensureAvailableModels(list);
            renderModels(_availableModels);
            search.value = "";
            search.focus();
        } else {
            menu.style.display = "none";
        }
    });

    document.addEventListener("click", (e) => {
        if (!menu.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
            menu.style.display = "none";
        }
    });

    search.addEventListener("input", debounce(() => {
        const filtered = filterModelsByQuery(search.value);
        renderModels(filtered);
    }, 250));

    function renderModels(models) {
        const currentModelId = state.activeModelId || "";
        renderModelList(list, models, currentModelId, async (model) => {
            state.activeModelId = model.id;
            updateModelSelectorDisplay(model.id);
            menu.style.display = "none";
            if (state.sessionId) {
                await authFetch("/api/sessions/" + encodeURIComponent(state.sessionId), {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ model: model.id })
                });
                if (typeof refreshTokenBadge === "function") {
                    refreshTokenBadge();
                }
            }
        });
    }
}
document.addEventListener("DOMContentLoaded", () => {
    setupSettingsModelPickers();
    setTimeout(() => {
        setupModelSelector();
        setupReasoningSelector();
    }, 500);
});


window.updateReasoningSelectorDisplay = updateReasoningSelectorDisplay;
