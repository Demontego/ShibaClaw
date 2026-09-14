/**
 * ShibaClaw WebUI — Profile Selector
 * Handles agent profile switching per session.
 */

// ── Profile state ────────────────────────────────────────────
let _profilesCache = null;

const profileBtn = document.getElementById("btn-profile");
const profileDropdown = document.getElementById("profile-dropdown");
const profileLabel = document.getElementById("profile-label");

// ── API helpers ──────────────────────────────────────────────
async function fetchProfiles() {
    try {
        const res = await authFetch("/api/profiles");
        if (!res.ok) return [];
        const data = await res.json();
        _profilesCache = data.profiles || [];
        return _profilesCache;
    } catch {
        return _profilesCache || [];
    }
}

async function switchProfile(profileId) {
    if (!state.sessionId || profileId === state.profileId) return;
    try {
        await authFetch(`/api/sessions/${encodeURIComponent(state.sessionId)}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ profile_id: profileId }),
        });
        await syncProfileSelection(profileId);
        closeProfileDropdown();
    } catch (e) {
        console.error("Failed to switch profile:", e);
    }
}

function _applyProfileAvatar(profileId) {
    const profiles = _profilesCache || [];
    const current = profiles.find(p => p.id === profileId);
    const avatarUrl = (current && current.avatar) ? current.avatar : DEFAULT_AVATAR;
    state.profileAvatar = avatarUrl;
    document.querySelectorAll(".agent-avatar-img").forEach(img => {
        img.src = avatarUrl;
    });
    const sidebarLogo = document.querySelector(".logo img");
    if (sidebarLogo) sidebarLogo.src = avatarUrl;
    const welcomeLogo = document.querySelector(".welcome-logo");
    if (welcomeLogo) welcomeLogo.src = avatarUrl;
}

// ── UI helpers ───────────────────────────────────────────────
function updateProfileLabel() {
    if (!profileLabel) return;
    const profiles = _profilesCache || [];
    const current = profiles.find(p => p.id === state.profileId);
    profileLabel.textContent = current ? current.label : (state.profileId || "Default");
}

async function syncProfileSelection(profileId) {
    if (!_profilesCache) {
        await fetchProfiles();
    }
    state.profileId = profileId || "default";
    _applyProfileAvatar(state.profileId);
    updateProfileLabel();
    if (typeof window.loadSkillsPanel === "function") {
        const selectEl = document.getElementById("skills-profile-select");
        if (selectEl) {
            selectEl.value = state.profileId;
        }
        window.loadSkillsPanel();
    }
}

window.syncProfileSelection = syncProfileSelection;

function closeProfileDropdown() {
    if (profileDropdown) profileDropdown.classList.remove("active");
}

async function renderProfileDropdown() {
    if (!profileDropdown) return;
    const profiles = await fetchProfiles();

    let html = "";
    for (const p of profiles) {
        const isActive = p.id === state.profileId;
        html += `
            <div class="profile-option ${isActive ? "active" : ""}"
                 data-profile-id="${p.id}" title="${p.description || ""}">
                <span class="material-icons-round profile-option-icon">
                    ${isActive ? "radio_button_checked" : "radio_button_unchecked"}
                </span>
                <div class="profile-option-info">
                    <div class="profile-option-name">${escapeHtml(p.label)}</div>
                    ${p.description ? `<div class="profile-option-desc">${escapeHtml(p.description)}</div>` : ""}
                </div>
                ${p.builtin ? `<span class="profile-option-badge">${escapeHtml(typeof t === "function" ? t("profiles.builtin") : "built-in")}</span>` : ""}
            </div>`;
    }
    html += '<div class="profile-divider"></div>';
    html += `
        <div class="profile-action" id="profile-action-create">
            <span class="material-icons-round">add_circle_outline</span>
            ${escapeHtml(typeof t === "function" ? t("profiles.create") : "Create custom profile")}
        </div>
        <div class="profile-action" id="profile-action-edit">
            <span class="material-icons-round">tune</span>
            ${escapeHtml(typeof t === "function" ? t("profiles.configure") : "Configure current profile")}
        </div>`;

    profileDropdown.innerHTML = html;

    profileDropdown.querySelectorAll(".profile-option").forEach(el => {
        el.addEventListener("click", () => switchProfile(el.dataset.profileId));
    });

    const createBtn = profileDropdown.querySelector("#profile-action-create");
    if (createBtn) createBtn.addEventListener("click", () => openProfileModal());
    const editBtn = profileDropdown.querySelector("#profile-action-edit");
    if (editBtn) editBtn.addEventListener("click", () => openProfileModal(state.profileId));
}

// escapeHtml — uses global from utils.js (loaded before profiles.js)

// ── Toggle dropdown ──────────────────────────────────────────
if (profileBtn) {
    profileBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const isOpen = profileDropdown.classList.contains("active");
        if (isOpen) {
            closeProfileDropdown();
        } else {
            await renderProfileDropdown();
            profileDropdown.classList.add("active");
        }
    });
}

document.addEventListener("click", (e) => {
    if (profileDropdown && !profileDropdown.contains(e.target) && e.target !== profileBtn) {
        closeProfileDropdown();
    }
});

async function openProfileModal(profileId = null) {
    closeProfileDropdown();
    let profile = {};
    if (profileId) {
        const response = await authFetch(`/api/profiles/${encodeURIComponent(profileId)}`);
        if (!response.ok) return;
        profile = await response.json();
    }

    const overlay = document.createElement("div");
    overlay.className = "modal-backdrop active";
    overlay.innerHTML = `
        <div class="modal" role="dialog" aria-modal="true" aria-labelledby="profile-modal-title">
            <div class="modal-header">
                <h2 id="profile-modal-title">${escapeHtml(profileId ? (typeof t === "function" ? t("profiles.configure_title") : "Configure profile") : (typeof t === "function" ? t("profiles.create_title") : "Create profile"))}</h2>
                <button class="modal-close" type="button" aria-label="Close">×</button>
            </div>
            <form class="modal-body">
                <div class="form-group"><label for="profile-modal-id">${escapeHtml(typeof t === "function" ? t("profiles.id") : "ID")}</label><input class="form-input" id="profile-modal-id" required ${profileId ? "readonly" : ""}></div>
                <div class="form-group"><label for="profile-modal-label">${escapeHtml(typeof t === "function" ? t("profiles.label") : "Label")}</label><input class="form-input" id="profile-modal-label" required></div>
                <div class="form-group"><label for="profile-modal-description">${escapeHtml(typeof t === "function" ? t("profiles.description") : "Description")}</label><input class="form-input" id="profile-modal-description"></div>
                <div class="form-group"><label for="profile-modal-soul">${escapeHtml(typeof t === "function" ? t("profiles.soul") : "SOUL.md")}</label><textarea class="form-input" id="profile-modal-soul" rows="6"></textarea></div>
                <div class="form-group"><label for="profile-modal-disabled-tools">Disabled tools (comma-separated)</label><input class="form-input" id="profile-modal-disabled-tools" placeholder="exec, write_file"></div>
                <div class="form-group"><label for="profile-modal-enabled-tools">Enabled tools (comma-separated)</label><input class="form-input" id="profile-modal-enabled-tools" placeholder="web_search, web_fetch"></div>
                <div class="form-group"><label for="profile-modal-temperature">Temperature</label><input class="form-input" id="profile-modal-temperature" type="number" min="0" max="2" step="0.1"></div>
                <div class="form-group"><label for="profile-modal-knowledge-bases">Knowledge bases (comma-separated IDs)</label><input class="form-input" id="profile-modal-knowledge-bases" placeholder="docs, product-notes"></div>
                <div id="profile-modal-error" role="alert"></div>
                <div class="modal-footer">
                    <button class="btn-secondary" type="button">${escapeHtml(typeof t === "function" ? t("common.cancel") : "Cancel")}</button>
                    <button class="btn-primary" type="submit">${escapeHtml(typeof t === "function" ? t("common.save") : "Save")}</button>
                </div>
            </form>
        </div>`;
    document.body.appendChild(overlay);

    const input = (id) => overlay.querySelector(`#profile-modal-${id}`);
    const csv = (value) => Array.isArray(value) ? value.join(", ") : "";
    input("id").value = profile.id || "";
    input("label").value = profile.label || "";
    input("description").value = profile.description || "";
    input("soul").value = profile.soul || "";
    input("disabled-tools").value = csv(profile.disabled_tools);
    input("enabled-tools").value = csv(profile.enabled_tools);
    input("temperature").value = profile.temperature ?? "";
    input("knowledge-bases").value = csv(profile.knowledge_bases);

    const close = () => overlay.remove();
    overlay.querySelector(".modal-close").addEventListener("click", close);
    overlay.querySelector(".btn-secondary").addEventListener("click", close);
    overlay.addEventListener("click", (event) => {
        if (event.target === overlay) close();
    });
    overlay.querySelector("form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const list = (name) => {
            const values = input(name).value.split(",").map((item) => item.trim()).filter(Boolean);
            return values.length ? values : null;
        };
        const payload = {
            id: input("id").value.trim(),
            label: input("label").value.trim(),
            description: input("description").value.trim(),
            soul: input("soul").value,
            disabled_tools: list("disabled-tools"),
            enabled_tools: list("enabled-tools"),
            temperature: input("temperature").value === "" ? null : Number(input("temperature").value),
            knowledge_bases: list("knowledge-bases"),
        };
        const response = await authFetch(
            profileId ? `/api/profiles/${encodeURIComponent(profileId)}` : "/api/profiles",
            {
                method: profileId ? "PUT" : "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            }
        );
        if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            overlay.querySelector("#profile-modal-error").textContent = body.error || (typeof t === "function" ? t("profiles.save_fail") : "Unable to save profile.");
            return;
        }
        await fetchProfiles();
        close();
        if (!profileId) await switchProfile(payload.id);
    });
}

function initProfileSocket() {
    realtime.on("connected", (data) => {
        if (data.profile_id) {
            syncProfileSelection(data.profile_id);
        }
    });

    realtime.on("session_reset", (data) => {
        if (data.profile_id) {
            syncProfileSelection(data.profile_id);
        }
    });
}

if (typeof realtime !== "undefined") {
    initProfileSocket();
} else {
    const _checkSocket = setInterval(() => {
        if (typeof realtime !== "undefined") {
            clearInterval(_checkSocket);
            initProfileSocket();
        }
    }, 200);
}

if (state.profileId) {
    syncProfileSelection(state.profileId);
}
