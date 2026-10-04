// Memory Manager Panel Logic
(function () {
    let _memData = {
        memory: "",
        user: "",
        history: "",
        diary: "",
        tokens: 0,
        max_tokens: 1500,
        quarantined: []
    };
    let _activeTab = "memory"; // "memory", "user", "history", "diary"
    let _isEditMode = false;
    let _loadState = "ready";
    let _loadError = null;
    let _saveStatus = null;

    // Replace variables with callbacks so user content containing $ stays literal.
    function _mt(key, vars) {
        const values = vars || {};
        return t(key).replace(/\{([^}]+)\}/g, (match, name) =>
            Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match);
    }

    function _errorMessage(error) {
        if (error.status) return _mt("memory.server_error", { status: error.status });
        return error.key ? _mt(error.key) : error.message;
    }

    function _renderLoadState() {
        const contentEl = document.getElementById("memory-content-area");
        if (!contentEl) return;
        const loading = _loadState === "loading";
        contentEl.innerHTML = `
            <div style="padding: 3rem; text-align: center; color: ${loading ? "var(--text-muted)" : "var(--accent-red, #e06c75)"};">
                <span class="material-icons-round ${loading ? "spin" : ""}" style="font-size: 24px;">${loading ? "progress_activity" : "error_outline"}</span>
                <div style="margin-top: 8px;">${escapeHtml(loading ? _mt("memory.loading") : _mt("memory.load_error", { error: _errorMessage(_loadError) }))}</div>
            </div>`;
    }

    function _updateEditorControls() {
        const editBtn = document.getElementById("btn-memory-edit-toggle");
        const saveBtn = document.getElementById("btn-memory-save");
        const editKey = _isEditMode ? "memory.view" : "common.edit";
        if (editBtn) {
            editBtn.innerHTML = `<span class="material-icons-round">${_isEditMode ? "visibility" : "edit"}</span> <span>${escapeHtml(_mt(editKey))}</span>`;
            editBtn.setAttribute("data-i18n-aria", editKey);
            editBtn.setAttribute("aria-label", _mt(editKey));
        }
        if (saveBtn) saveBtn.style.display = _isEditMode ? "inline-flex" : "none";
        const caption = document.getElementById("memory-editor-caption");
        const textarea = document.getElementById("memory-editor-textarea");
        const editing = _mt("memory.editing", { file: getTargetFilename() });
        if (caption) caption.textContent = editing;
        if (textarea) textarea.setAttribute("aria-label", editing);
    }

    function _updateSaveStatus() {
        const statusEl = document.getElementById("memory-save-status");
        if (!statusEl || !_saveStatus) return;
        const vars = _saveStatus.error ? { error: _errorMessage(_saveStatus.error) } : _saveStatus.vars;
        statusEl.textContent = _mt(_saveStatus.key, vars);
        statusEl.style.color = _saveStatus.color;
    }

    window.loadMemoryData = async function () {
        const contentEl = document.getElementById("memory-content-area");
        if (!contentEl) return;

        _loadState = "loading";
        _renderLoadState();

        try {
            const res = await authFetch("/api/memory");
            if (!res.ok) throw Object.assign(new Error(), { status: res.status });
            _memData = await res.json();
            _loadState = "ready";
            _updateTokenBadge();
            renderMemoryView();
        } catch (e) {
            _loadState = "error";
            _loadError = e;
            _renderLoadState();
        }
    };

    function _updateTokenBadge() {
        const badge = document.getElementById("memory-token-badge");
        if (!badge) return;
        const current = _memData.tokens || 0;
        const max = _memData.max_tokens || 1500;
        const pct = Math.min(100, Math.round((current / max) * 100));
        
        let color = "var(--shiba-gold)";
        if (pct > 90) color = "var(--accent-red, #e06c75)";
        else if (pct > 75) color = "#e5c07b";

        badge.innerHTML = `
            <span class="material-icons-round" style="font-size: 14px; vertical-align: middle;">memory</span>
            <span>${escapeHtml(_mt("memory.tokens", { current, max, pct }))}</span>
        `;
        badge.style.color = color;
    }

    window.switchMemoryTab = function (tab) {
        _activeTab = tab;
        _isEditMode = false;
        document.querySelectorAll(".memory-tab-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.tab === tab);
        });
        renderMemoryView();
    };

    window.toggleMemoryEdit = function () {
        _isEditMode = !_isEditMode;
        renderMemoryView();
    };

    function getTargetFilename() {
        if (_activeTab === "user") return "USER.md";
        if (_activeTab === "history") return "HISTORY.md";
        if (_activeTab === "diary") return "DREAM_DIARY.md";
        return "MEMORY.md";
    }

    function getCurrentContent() {
        if (_activeTab === "user") return _memData.user || "";
        if (_activeTab === "history") return _memData.history || "";
        if (_activeTab === "diary") return _memData.diary || "";
        return _memData.memory || "";
    }

    function renderMemoryView() {
        const contentEl = document.getElementById("memory-content-area");
        if (!contentEl) return;

        const content = getCurrentContent();
        const filename = getTargetFilename();

        _updateEditorControls();

        if (_isEditMode) {
            contentEl.innerHTML = `
                <div style="height: 100%; display: flex; flex-direction: column;">
                    <div id="memory-editor-caption" style="font-size: 11px; color: var(--text-muted); margin-bottom: 6px;">${escapeHtml(_mt("memory.editing", { file: filename }))}</div>
                    <textarea id="memory-editor-textarea" class="form-input" aria-labelledby="memory-editor-caption" style="flex: 1; min-height: 380px; font-family: var(--font-mono, monospace); font-size: 13px; line-height: 1.5; resize: none;">${escapeHtml(content)}</textarea>
                </div>`;
        } else {
            if (_activeTab === "diary" && !content && (!_memData.quarantined || _memData.quarantined.length === 0)) {
                contentEl.innerHTML = `
                    <div style="padding: 2.5rem; text-align: center; color: var(--text-muted);">
                        <span class="material-icons-round" style="font-size: 36px; opacity: 0.5;">bedtime</span>
                        <div style="margin-top: 8px;">${escapeHtml(_mt("memory.diary_empty"))}</div>
                    </div>`;
                return;
            }

            if (!content && _activeTab !== "diary") {
                contentEl.innerHTML = `
                    <div style="padding: 2.5rem; text-align: center; color: var(--text-muted);">
                        <span class="material-icons-round" style="font-size: 36px; opacity: 0.5;">description</span>
                        <div style="margin-top: 8px;">${escapeHtml(_mt("memory.empty", { file: filename }))}</div>
                        <div style="margin-top: 6px; font-size: 12px;">${escapeHtml(_mt("memory.empty_hint"))}</div>
                    </div>`;
                return;
            }

            let html = `<div class="markdown-body" style="padding: 1rem; line-height: 1.6;">${renderMarkdown(content)}</div>`;

            if (_activeTab === "diary" && _memData.quarantined && _memData.quarantined.length > 0) {
                html += `
                    <div style="margin-top: 2rem; border-top: 1px solid var(--border-color); padding-top: 1rem;">
                        <h4 style="display: flex; align-items: center; gap: 6px; color: var(--accent-red, #e06c75); font-size: 13px; margin-bottom: 8px;">
                            <span class="material-icons-round" style="font-size: 16px;">shield</span>
                            ${escapeHtml(_mt("memory.quarantined", { n: _memData.quarantined.length }))}
                        </h4>
                        <div style="display: flex; flex-direction: column; gap: 8px;">`;
                for (const q of _memData.quarantined) {
                    html += `
                        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; padding: 8px 12px; font-size: 12px;">
                            <div style="font-weight: 600; color: var(--text-primary);">${escapeHtml(q.name)}</div>
                            <pre style="margin-top: 4px; padding: 6px; background: rgba(0,0,0,0.2); border-radius: 4px; font-size: 11px; white-space: pre-wrap; color: var(--text-muted);">${escapeHtml(q.preview)}</pre>
                        </div>`;
                }
                html += `</div></div>`;
            }

            contentEl.innerHTML = html;
            if (typeof enhanceCodeBlocks === "function") enhanceCodeBlocks(contentEl);
        }
    }

    window.saveCurrentMemoryFile = async function () {
        const textarea = document.getElementById("memory-editor-textarea");
        const statusEl = document.getElementById("memory-save-status");
        if (!textarea) return;

        const filename = getTargetFilename();
        const content = textarea.value;

        _saveStatus = { key: "memory.saving", color: "var(--shiba-gold)" };
        _updateSaveStatus();

        try {
            const res = await authFetch("/api/memory/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file: filename, content: content })
            });
            const data = await res.json();
            if (!res.ok) throw data.error ? new Error(data.error) : Object.assign(new Error(), { key: "memory.save_failed" });

            if (_activeTab === "user") _memData.user = content;
            else if (_activeTab === "history") _memData.history = content;
            else if (_activeTab === "diary") _memData.diary = content;
            else _memData.memory = content;

            if (data.tokens !== undefined) _memData.tokens = data.tokens;
            _updateTokenBadge();

            if (statusEl) {
                _saveStatus = { key: "memory.saved", color: "#98c379" };
                _updateSaveStatus();
                setTimeout(() => { _saveStatus = null; statusEl.textContent = ""; }, 3000);
            }
            _isEditMode = false;
            renderMemoryView();
        } catch (e) {
            if (statusEl) {
                _saveStatus = { key: "memory.error", error: e, color: "var(--accent-red, #e06c75)" };
                _updateSaveStatus();
            }
        }
    };

    window.searchForgetMemory = async function () {
        const input = document.getElementById("memory-forget-input");
        const needle = (input ? input.value : "").trim();
        if (needle.length < 3) {
            alert(_mt("memory.forget_min"));
            return;
        }

        try {
            const res = await authFetch("/api/memory/forget", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ needle: needle, confirm: false })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || _mt("memory.forget_search_failed"));

            const memCount = data.counts ? data.counts["MEMORY.md"] || 0 : 0;
            const histCount = data.counts ? data.counts["HISTORY.md"] || 0 : 0;
            const total = memCount + histCount;

            if (total === 0) {
                alert(_mt("memory.forget_none", { needle }));
                return;
            }

            const previewLines = [
                ...(data.matches?.["MEMORY.md"] || []).map(m => `[MEMORY] ${m}`),
                ...(data.matches?.["HISTORY.md"] || []).map(m => `[HISTORY] ${m}`)
            ].slice(0, 5).join("\n");

            const msg = _mt("memory.forget_confirm", { n: total, needle, preview: previewLines });
            
            if (confirm(msg)) {
                const confRes = await authFetch("/api/memory/forget", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ needle: needle, confirm: true })
                });
                const confData = await confRes.json();
                if (!confRes.ok) throw new Error(confData.error || _mt("memory.forget_failed"));
                alert(_mt("memory.forget_success"));
                if (input) input.value = "";
                await loadMemoryData();
            }
        } catch (e) {
            alert(_mt("memory.error", { error: e.message }));
        }
    };

    document.addEventListener("shibaclaw:localechange", () => {
        const modal = document.getElementById("memory-modal");
        if (!modal || !modal.classList.contains("active")) return;
        _updateTokenBadge();
        _updateEditorControls();
        _updateSaveStatus();
        if (_isEditMode && document.getElementById("memory-editor-textarea")) return;
        if (_loadState === "ready") renderMemoryView();
        else _renderLoadState();
    });
})();
