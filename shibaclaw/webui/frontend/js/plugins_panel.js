/**
 * ShibaClaw Apps & Integrations Marketplace
 * Unified UX for Remote MCP, Local MCP, and Native Plugins.
 */

(function () {
  'use strict';

  function _h(extra) {
    return typeof authHeaders === 'function' ? authHeaders(extra || {}) : (extra || {});
  }

  const ICON_SVGS = {
    "google-workspace": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 256 193\"><path fill=\"#4285f4\" d=\"M58.182 192.05V93.14L27.507 65.077L0 49.504v125.091c0 9.658 7.825 17.455 17.455 17.455z\"/><path fill=\"#34a853\" d=\"M197.818 192.05h40.727c9.659 0 17.455-7.826 17.455-17.455V49.505l-31.156 17.837l-27.026 25.798z\"/><path fill=\"#ea4335\" d=\"m58.182 93.14l-4.174-38.647l4.174-36.989L128 69.868l69.818-52.364l4.669 34.992l-4.669 40.644L128 145.504z\"/><path fill=\"#fbbc04\" d=\"M197.818 17.504V93.14L256 49.504V26.231c0-21.585-24.64-33.89-41.89-20.945z\"/><path fill=\"#c5221f\" d=\"m0 49.504l26.759 20.07L58.182 93.14V17.504L41.89 5.286C24.61-7.66 0 4.646 0 26.23z\"/></svg>",
    "github": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 256 250\"><path fill=\"#fff\" d=\"M128.001 0C57.317 0 0 57.307 0 128.001c0 56.554 36.676 104.535 87.535 121.46c6.397 1.185 8.746-2.777 8.746-6.158c0-3.052-.12-13.135-.174-23.83c-35.61 7.742-43.124-15.103-43.124-15.103c-5.823-14.795-14.213-18.73-14.213-18.73c-11.613-7.944.876-7.78.876-7.78c12.853.902 19.621 13.19 19.621 13.19c11.417 19.568 29.945 13.911 37.249 10.64c1.149-8.272 4.466-13.92 8.127-17.116c-28.431-3.236-58.318-14.212-58.318-63.258c0-13.975 5-25.394 13.188-34.358c-1.329-3.224-5.71-16.242 1.24-33.874c0 0 10.749-3.44 35.21 13.121c10.21-2.836 21.16-4.258 32.038-4.307c10.878.049 21.837 1.47 32.066 4.307c24.431-16.56 35.165-13.12 35.165-13.12c6.967 17.63 2.584 30.65 1.255 33.873c8.207 8.964 13.173 20.383 13.173 34.358c0 49.163-29.944 59.988-58.447 63.157c4.591 3.972 8.682 11.762 8.682 23.704c0 17.126-.148 30.91-.148 35.126c0 3.407 2.304 7.398 8.792 6.14C219.37 232.5 256 184.537 256 128.002C256 57.307 198.691 0 128.001 0\"/></svg>",
    "notion": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 256 268\"><path fill=\"#fff\" d=\"M16.092 11.538L164.09.608c18.179-1.56 22.85-.508 34.28 7.801l47.243 33.282C253.406 47.414 256 48.975 256 55.207v182.527c0 11.439-4.155 18.205-18.696 19.24L65.44 267.378c-10.913.517-16.11-1.043-21.825-8.327L8.826 213.814C2.586 205.487 0 199.254 0 191.97V29.726c0-9.352 4.155-17.153 16.092-18.188\"/><path d=\"M164.09.608L16.092 11.538C4.155 12.573 0 20.374 0 29.726v162.245c0 7.284 2.585 13.516 8.826 21.843l34.789 45.237c5.715 7.284 10.912 8.844 21.825 8.327l171.864-10.404c14.532-1.035 18.696-7.801 18.696-19.24V55.207c0-5.911-2.336-7.614-9.21-12.66l-1.185-.856L198.37 8.409C186.94.1 182.27-.952 164.09.608M69.327 52.22c-14.033.945-17.216 1.159-25.186-5.323L23.876 30.778c-2.06-2.086-1.026-4.69 4.163-5.207l142.274-10.395c11.947-1.043 18.17 3.12 22.842 6.758l24.401 17.68c1.043.525 3.638 3.637.517 3.637L71.146 52.095zm-16.36 183.954V81.222c0-6.767 2.077-9.887 8.3-10.413L230.02 60.93c5.724-.517 8.31 3.12 8.31 9.879v153.917c0 6.767-1.044 12.49-10.387 13.008l-161.487 9.361c-9.343.517-13.489-2.594-13.489-10.921M212.377 89.53c1.034 4.681 0 9.362-4.681 9.897l-7.783 1.542v114.404c-6.758 3.637-12.981 5.715-18.18 5.715c-8.308 0-10.386-2.604-16.609-10.396l-50.898-80.079v77.476l16.1 3.646s0 9.362-12.989 9.362l-35.814 2.077c-1.043-2.086 0-7.284 3.63-8.318l9.351-2.595V109.823l-12.98-1.052c-1.044-4.68 1.55-11.439 8.826-11.965l38.426-2.585l52.958 81.113v-71.76l-13.498-1.552c-1.043-5.733 3.111-9.896 8.3-10.404z\"/></svg>",
    "slack": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 256 256\"><path fill=\"#e01e5a\" d=\"M53.841 161.32c0 14.832-11.987 26.82-26.819 26.82S.203 176.152.203 161.32c0-14.831 11.987-26.818 26.82-26.818H53.84zm13.41 0c0-14.831 11.987-26.818 26.819-26.818s26.819 11.987 26.819 26.819v67.047c0 14.832-11.987 26.82-26.82 26.82c-14.83 0-26.818-11.988-26.818-26.82z\"/><path fill=\"#36c5f0\" d=\"M94.07 53.638c-14.832 0-26.82-11.987-26.82-26.819S79.239 0 94.07 0s26.819 11.987 26.819 26.819v26.82zm0 13.613c14.832 0 26.819 11.987 26.819 26.819s-11.987 26.819-26.82 26.819H26.82C11.987 120.889 0 108.902 0 94.069c0-14.83 11.987-26.818 26.819-26.818z\"/><path fill=\"#2eb67d\" d=\"M201.55 94.07c0-14.832 11.987-26.82 26.818-26.82s26.82 11.988 26.82 26.82s-11.988 26.819-26.82 26.819H201.55zm-13.41 0c0 14.832-11.988 26.819-26.82 26.819c-14.831 0-26.818-11.987-26.818-26.82V26.82C134.502 11.987 146.489 0 161.32 0s26.819 11.987 26.819 26.819z\"/><path fill=\"#ecb22e\" d=\"M161.32 201.55c14.832 0 26.82 11.987 26.82 26.818s-11.988 26.82-26.82 26.82c-14.831 0-26.818-11.988-26.818-26.82V201.55zm0-13.41c-14.831 0-26.818-11.988-26.818-26.82c0-14.831 11.987-26.818 26.819-26.818h67.25c14.832 0 26.82 11.987 26.82 26.819s-11.988 26.819-26.82 26.819z\"/></svg>",
    "whatsapp": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 256 258\"><path fill=\"#25D366\" d=\"M218.4 37.8C194.5 13.9 162.7.8 128.8.8C58.3.8 1 58.1 1 128.6c0 22.5 5.9 44.5 17.1 63.9L0 257.2l66.5-17.4c18.8 10.3 40.1 15.7 62.3 15.7h.1c70.5 0 127.8-57.3 127.8-127.8c0-34-13.2-65.9-37.5-89.9\"/><path fill=\"#FFF\" d=\"M128.8 233.9h-.1c-19.1 0-37.8-5.1-54.1-14.8l-3.9-2.3l-40.2 10.5l10.7-39.2l-2.5-4c-10.7-17-16.3-36.6-16.3-56.7c0-58.7 47.8-106.5 106.6-106.5c28.4 0 55.2 11.1 75.3 31.2c20.1 20.1 31.1 46.8 31.1 75.3c0 58.8-47.8 106.5-106.6 106.5\"/></svg>",
  };

  const CATEGORIES = ['all', 'productivity', 'development', 'communication', 'databases', 'search', 'ai', 'media'];

  function label(key, vars) {
    return escapeHtml(t(`apps.${key}`, vars));
  }

  function filteredApps() {
    const { tab, category, query } = _appsState;
    return _appsState.apps.filter(app => {
      if (tab === 'installed' && !app.installed) return false;
      if (tab === 'updates' && (!app.installed || !app.update_available)) return false;
      if (category !== 'all' && (app.category || '').toLowerCase() !== category) return false;
      if (!query) return true;
      const q = query.toLowerCase();
      return (app.name || '').toLowerCase().includes(q)
        || (app.description || '').toLowerCase().includes(q)
        || (app.capabilities || []).some(c => c.toLowerCase().includes(q));
    });
  }

  function cardsHtml() {
    const filtered = filteredApps();
    if (filtered.length) return filtered.map(app => _renderAppCard(app)).join('');
    const message = _appsState.tab === 'updates' && !_appsState.query && _appsState.category === 'all'
      ? 'no_updates' : 'empty';
    return `<div style="grid-column:1/-1; padding:40px; text-align:center; color:var(--text-muted)">
      <span class="material-icons-round" style="font-size:36px; opacity:0.5">search_off</span>
      <div style="margin-top:8px">${label(message)}</div>
    </div>`;
  }

  let _appsState = {
    apps: [],
    tab: "discover",
    category: "all",
    query: "",
    loading: false,
    pollTimer: null,
  };

  window.loadAppsMarketplace = async function (targetEl) {
    const container = typeof targetEl === 'string' ? document.getElementById(targetEl) : targetEl;
    if (!container) return;

    if (_appsState.apps && _appsState.apps.length > 0) {
      _renderMarketplace(container);
    } else {
      container.innerHTML = `
        <div class="settings-loader" style="padding:40px; text-align:center">
          <span class="material-icons-round spin" style="font-size:32px; color:var(--shiba-gold)">progress_activity</span>
          <div style="margin-top:10px; color:var(--text-secondary)">${label('loading')}</div>
        </div>
      `;
    }

    if (_appsState.loading) return;
    _appsState.loading = true;

    try {
      const res = await authFetch('/api/apps');
      const data = await res.json();
      _appsState.apps = data.apps || [];
      _renderMarketplace(container);
    } catch (e) {
      if (!_appsState.apps || _appsState.apps.length === 0) {
        container.innerHTML = `<div style="color:var(--accent-red); padding:20px">${label('load_error', { error: e.message || e })}</div>`;
      }
    } finally {
      _appsState.loading = false;
    }
  };

  function _updateMarketplaceWrap(wrap) {
    if (!wrap) return;
    const { apps, tab, category, query } = _appsState;

    const installedCount = apps.filter(a => a.installed).length;
    const updatesCount = apps.filter(a => a.installed && a.update_available).length;
    const totalCount = apps.length;

    const grid = wrap.querySelector('.apps-grid');
    if (grid) {
      grid.innerHTML = cardsHtml();
    }

    const badgeTotal = wrap.querySelector('.apps-count-total');
    if (badgeTotal) badgeTotal.textContent = totalCount;

    const badgeInstalled = wrap.querySelector('.apps-count-installed');
    if (badgeInstalled) {
      badgeInstalled.textContent = installedCount;
      badgeInstalled.className = `acc-badge apps-count-installed ${installedCount > 0 ? 'on' : 'off'}`;
    }

    const badgeUpdates = wrap.querySelector('.apps-count-updates');
    if (badgeUpdates) {
      badgeUpdates.textContent = updatesCount;
      badgeUpdates.className = `acc-badge apps-count-updates ${updatesCount > 0 ? 'on' : 'off'}`;
    }

    wrap.querySelectorAll('.apps-tab-btn').forEach(btn => {
      const t = btn.getAttribute('data-tab');
      btn.classList.toggle('active', t === tab);
    });

    wrap.querySelectorAll('.apps-cat-pill').forEach(pill => {
      const c = pill.getAttribute('data-cat');
      pill.classList.toggle('active', c === category);
    });

    const input = wrap.querySelector('.apps-search-input') || wrap.querySelector('#apps-search-input');
    if (input && document.activeElement !== input && input.value !== query) {
      input.value = query;
    }
  }

  function _renderMarketplace(container) {
    const wrap = container.querySelector('.apps-marketplace-wrap');
    if (wrap) {
      _updateMarketplaceWrap(wrap);
      return;
    }

    const { apps, tab, category, query } = _appsState;
    const installedCount = apps.filter(a => a.installed).length;
    const updatesCount = apps.filter(a => a.installed && a.update_available).length;
    const totalCount = apps.length;

    container.innerHTML = `
      <div class="apps-marketplace-wrap" style="padding:10px 0">
        <!-- Top Toolbar -->
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:16px">
          <div>
            <h2 style="margin:0; font-size:1.3rem; font-weight:700; color:var(--text-primary)">${label('title')}</h2>
            <div style="font-size:0.82rem; color:var(--text-muted); margin-top:2px">${label('subtitle')}</div>
          </div>
          <button class="btn-secondary btn-sm" onclick="window.openAddCustomAppModal()" style="display:flex; align-items:center; gap:6px">
            <span class="material-icons-round" style="font-size:16px">add</span> ${label('add_plugin')}
          </button>
        </div>

        <!-- Navigation Tabs -->
        <div class="apps-nav-tabs">
          <button class="apps-tab-btn ${tab === 'discover' ? 'active' : ''}" data-tab="discover" onclick="window.switchAppsTab('discover')">
            <span class="material-icons-round" style="font-size:18px">explore</span> ${label('discover')}
            <span class="acc-badge apps-count-total" style="margin-left:4px">${totalCount}</span>
          </button>
          <button class="apps-tab-btn ${tab === 'installed' ? 'active' : ''}" data-tab="installed" onclick="window.switchAppsTab('installed')">
            <span class="material-icons-round" style="font-size:18px">check_circle</span> ${label('installed')}
            <span class="acc-badge apps-count-installed ${installedCount > 0 ? 'on' : 'off'}" style="margin-left:4px">${installedCount}</span>
          </button>
          <button class="apps-tab-btn ${tab === 'updates' ? 'active' : ''}" data-tab="updates" onclick="window.switchAppsTab('updates')">
            <span class="material-icons-round" style="font-size:18px">update</span> ${label('updates')}
            <span class="acc-badge apps-count-updates ${updatesCount > 0 ? 'on' : 'off'}" style="margin-left:4px">${updatesCount}</span>
          </button>
        </div>

        <!-- Search Bar -->
        <div style="position:relative; margin-bottom:12px">
          <span class="material-icons-round" style="position:absolute; left:12px; top:50%; transform:translateY(-50%); color:var(--text-muted); font-size:18px">search</span>
          <input type="text" class="form-input apps-search-input" style="padding-left:38px; width:100%; border-radius:8px"
                 placeholder="${label('search_placeholder')}"
                 value="${escapeHtml(query)}"
                 oninput="window.filterAppsQuery(this.value, this)">
        </div>

        <!-- Category Pills -->
        <div class="apps-categories-bar">
          ${CATEGORIES.map(key => `
            <button class="apps-cat-pill ${category === key ? 'active' : ''}" data-cat="${key}" onclick="window.filterAppsCategory('${key}')">
              ${label(`category.${key}`)}
            </button>
          `).join('')}
        </div>

        <!-- Apps Grid -->
        <div class="apps-grid" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:16px; margin-top:14px">
          ${cardsHtml()}
        </div>
      </div>
    `;
  }

  function _renderAppCard(app) {
    const isInstalled = app.installed;
    const isConnected = app.status === 'connected';
    const needsAuth = app.status === 'needs_auth' || app.status === 'needs_config';
    const isDisabled = app.status === 'disabled';
    const trust = app.trust_level || 'community';

    const brandIcon = ICON_SVGS[app.id]
      ? `<div style="width:36px; height:36px; display:flex; align-items:center; justify-content:center">${ICON_SVGS[app.id]}</div>`
      : `<div style="width:36px; height:36px; border-radius:8px; background:rgba(255,255,255,0.06); display:flex; align-items:center; justify-content:center">
           <span class="material-icons-round" style="color:var(--shiba-gold); font-size:20px">${escapeHtml(app.icon || 'extension')}</span>
         </div>`;

    return `
      <div class="ca-card ${isConnected ? 'ca-card--connected' : ''}" style="display:flex; flex-direction:column; padding:16px; border-radius:10px; border:1px solid var(--border-color); background:var(--bg-secondary); position:relative">
        <!-- Card Top Header -->
        <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:10px">
          <div style="display:flex; align-items:center; gap:10px">
            ${brandIcon}
            <div>
              <div style="font-weight:700; font-size:1rem; color:var(--text-primary)">${escapeHtml(app.name)}</div>
              <div class="app-card-meta">
                <span class="app-trust-badge app-trust-badge--${trust}">
                  ${trust === 'official' || trust === 'verified' ? '✓ ' : ''}${label(`trust.${trust}`)}
                </span>
                <span style="font-size:0.74rem; color:var(--text-muted)">${CATEGORIES.includes(app.category) ? label(`category.${app.category}`) : escapeHtml(app.category)}</span>
              </div>
            </div>
          </div>
          ${isInstalled ? `
            <span class="acc-badge ${isConnected ? 'on' : (isDisabled ? 'off' : 'warn')}" style="font-size:0.72rem">
              ${isConnected ? label('status.connected') : (isDisabled ? label('status.disabled') : label('status.setup_required'))}
            </span>
          ` : ''}
        </div>

        <!-- Description -->
        <div style="font-size:0.83rem; color:var(--text-secondary); line-height:1.4; margin-bottom:12px; flex:1">
          ${escapeHtml(app.description)}
        </div>

        <!-- Capabilities Tags -->
        ${app.capabilities && app.capabilities.length > 0 ? `
          <div style="margin-bottom:14px">
            ${app.capabilities.slice(0, 3).map(c => `<span class="app-cap-tag">${escapeHtml(c)}</span>`).join('')}
            ${app.capabilities.length > 3 ? `<span class="app-cap-tag">+${app.capabilities.length - 3}</span>` : ''}
          </div>
        ` : ''}

        <!-- Footer Actions -->
        <div style="border-top:1px solid rgba(255,255,255,0.06); padding-top:12px; display:flex; align-items:center; justify-content:space-between; gap:8px">
          ${!isInstalled ? `
            <button class="btn-primary btn-sm" onclick="window.installApp('${escapeHtml(app.id)}')" style="width:100%; justify-content:center; display:flex; align-items:center; gap:6px">
              <span class="material-icons-round" style="font-size:16px">download</span> ${label('install')}
            </button>
          ` : needsAuth ? `
            <button class="btn-primary btn-sm" onclick="window.openAppConnectModal('${escapeHtml(app.id)}')" style="flex:1; justify-content:center; display:flex; align-items:center; gap:6px; background:var(--shiba-gold); color:#000">
              <span class="material-icons-round" style="font-size:16px">vpn_key</span> ${label('connect')} ${escapeHtml(app.name)}
            </button>
            <button class="btn-icon" onclick="window.uninstallApp('${escapeHtml(app.id)}')" title="${label('uninstall')}" style="background:transparent; border:none; cursor:pointer">
              <span class="material-icons-round" style="color:var(--accent-red); font-size:18px">delete</span>
            </button>
          ` : isConnected ? `
            <div style="display:flex; align-items:center; gap:8px; width:100%">
              <button class="btn-secondary btn-sm" onclick="window.openAppConfigModal('${escapeHtml(app.id)}')" style="flex:1; display:flex; align-items:center; justify-content:center; gap:4px">
                <span class="material-icons-round" style="font-size:15px">tune</span> ${label('configure')}
              </button>
              <button class="btn-secondary btn-sm" onclick="window.toggleAppEnabled('${escapeHtml(app.id)}', false)" title="${label('disable')}">
                ${label('disable')}
              </button>
              <button class="btn-icon" onclick="window.uninstallApp('${escapeHtml(app.id)}')" title="${label('uninstall')}" style="background:transparent; border:none; cursor:pointer">
                <span class="material-icons-round" style="color:var(--accent-red); font-size:18px">delete</span>
              </button>
            </div>
          ` : isDisabled ? `
            <div style="display:flex; align-items:center; gap:8px; width:100%">
              <button class="btn-primary btn-sm" onclick="window.toggleAppEnabled('${escapeHtml(app.id)}', true)" style="flex:1">
                ${label('enable')}
              </button>
              <button class="btn-icon" onclick="window.uninstallApp('${escapeHtml(app.id)}')" title="${label('uninstall')}" style="background:transparent; border:none; cursor:pointer">
                <span class="material-icons-round" style="color:var(--accent-red); font-size:18px">delete</span>
              </button>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }

  /* ── Tab & Filter Handlers ─────────────────────────────────────────── */
  window.switchAppsTab = function (tab) {
    _appsState.tab = tab;
    _refreshCurrentMarketplace();
  };

  window.filterAppsCategory = function (cat) {
    _appsState.category = cat;
    _refreshCurrentMarketplace();
  };

  window.filterAppsQuery = function (q, inputEl) {
    _appsState.query = q;
    _refreshCurrentMarketplace();
  };

  function _refreshCurrentMarketplace() {
    document.querySelectorAll('.apps-marketplace-wrap').forEach(wrap => {
      _updateMarketplaceWrap(wrap);
    });
  }

  document.addEventListener('shibaclaw:localechange', () => {
    document.querySelectorAll('.apps-marketplace-wrap').forEach(wrap => {
      const container = wrap.parentElement;
      wrap.remove();
      _renderMarketplace(container);
    });
  });

  async function _refreshAllContainers() {
    try {
      const res = await authFetch('/api/apps');
      const data = await res.json();
      _appsState.apps = data.apps || [];
      _refreshCurrentMarketplace();
    } catch (e) {
      console.error('Failed refreshing marketplace apps', e);
    }
  }

  /* ── App Lifecycle Actions ─────────────────────────────────────────── */
  window.installApp = async function (appId) {
    const app = _appsState.apps.find(a => a.id === appId);
    if (!app) return;

    if (app.trust_level === 'community') {
      const ok = await shibaDialog(
        'confirm',
        t('apps.community_install_title'),
        t('apps.community_install_body', { name: app.name }),
        { confirmText: t('apps.install') }
      );
      if (!ok) return;
    }

    try {
      const res = await authFetch(`/api/apps/${appId}/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        alert(data.error || t('apps.install_failed'));
        return;
      }

      await _refreshAllContainers();

      if (data.requires_auth) {
        window.openAppConnectModal(appId);
      }
    } catch (e) {
      alert(t('apps.install_error', { error: e.message || e }));
    }
  };

  window.uninstallApp = async function (appId) {
    const confirmed = await shibaDialog(
      'confirm',
      t('apps.uninstall_title'),
      t('apps.uninstall_body'),
      { confirmText: t('apps.uninstall'), danger: true }
    );
    if (!confirmed) return;

    try {
      const res = await authFetch(`/api/apps/${appId}/uninstall`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        alert(data.error || t('apps.uninstall_failed'));
        return;
      }
      _refreshAllContainers();
    } catch (e) {
      alert(t('apps.uninstall_error', { error: e.message || e }));
    }
  };

  window.toggleAppEnabled = async function (appId, enable) {
    const endpoint = enable ? 'enable' : 'disable';
    try {
      const res = await authFetch(`/api/apps/${appId}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        alert(data.error || t('apps.toggle_failed'));
        return;
      }
      _refreshAllContainers();
    } catch (e) {
      alert(t('apps.error', { error: e.message || e }));
    }
  };

  /* ── Modals: Connect, Configure, Custom App ─────────────────────────── */
  window.openAppConnectModal = function (appId) {
    const app = _appsState.apps.find(a => a.id === appId);
    if (!app) return;

    let modal = document.getElementById('app-connect-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'app-connect-modal';
      modal.className = 'modal-backdrop';
      document.body.appendChild(modal);
    }

    const auth = app.auth || {};
    const isOAuth = auth.type === 'oauth2';
    const isApiKey = auth.type === 'api_key' || auth.type === 'bearer';
    const isCustom = auth.type === 'custom';

    modal.innerHTML = `
      <div class="modal-dialog" style="max-width:480px; background:var(--bg-primary); border-radius:12px; border:1px solid var(--border-color); overflow:hidden">
        <div class="modal-head" style="display:flex; justify-content:space-between; align-items:center; padding:16px 20px; border-bottom:1px solid var(--border-color)">
          <div style="font-weight:700; font-size:1.1rem; color:var(--text-primary)">${label('connect')} ${escapeHtml(app.name)}</div>
          <button class="btn-icon" onclick="closeModal('app-connect-modal')" style="background:transparent; border:none; cursor:pointer">
            <span class="material-icons-round">close</span>
          </button>
        </div>
        <div class="modal-body" style="padding:20px">
          ${isOAuth ? `
            <div style="text-align:center; padding:10px 0">
              <span class="material-icons-round" style="font-size:48px; color:var(--shiba-gold)">lock_open</span>
              <div style="font-size:0.9rem; color:var(--text-secondary); margin:12px 0 20px">
                ${label('oauth_description', { name: app.name })}
              </div>
              ${auth.requires_client_credentials ? `
                <div style="text-align:left; margin-bottom:16px">
                  <label class="form-label">${label('client_id')}</label>
                  <input type="text" id="oauth-client-id" class="form-input" placeholder="${label('client_id_placeholder')}">
                  <label class="form-label" style="margin-top:10px">${label('client_secret')}</label>
                  <input type="password" id="oauth-client-secret" class="form-input" placeholder="${label('client_secret')}">
                  <small style="color:var(--text-muted); font-size:0.75rem; display:block; margin-top:4px">
                    ${label('client_secret_help')}
                  </small>
                </div>
              ` : ''}
              <div id="oauth-status-spinner" style="display:none; margin:16px 0; color:var(--text-secondary)">
                <span class="material-icons-round spin">progress_activity</span> ${label('waiting_authorization')}
              </div>
              <button class="btn-primary" id="oauth-start-btn" onclick="window.startAppOAuth('${escapeHtml(app.id)}')" style="width:100%; justify-content:center">
                ${label('authorize_browser')}
              </button>
            </div>
          ` : isApiKey ? `
            <div>
              <label class="form-label">${escapeHtml((auth.fields && auth.fields[0] && auth.fields[0].label) || t('apps.api_key_label'))}</label>
              <input type="password" id="app-api-key-input" class="form-input" placeholder="${label('token_placeholder')}" style="width:100%">
              <small style="color:var(--text-muted); font-size:0.75rem; display:block; margin-top:6px">
                ${label('secret_help')}
              </small>
              <button class="btn-primary" onclick="window.saveAppApiKey('${escapeHtml(app.id)}')" style="width:100%; margin-top:18px; justify-content:center">
                ${label('save_connect')}
              </button>
            </div>
          ` : isCustom ? `
            <div>
              ${(auth.fields || []).map(f => `
                <div style="margin-bottom:12px">
                  <label class="form-label">${escapeHtml(f.label)}</label>
                  <input type="${f.type === 'password' ? 'password' : 'text'}" id="custom-field-${escapeHtml(f.key)}" class="form-input" placeholder="${escapeHtml(f.placeholder || '')}" style="width:100%">
                </div>
              `).join('')}
              <button class="btn-primary" onclick="window.saveAppCustomCredentials('${escapeHtml(app.id)}')" style="width:100%; margin-top:18px; justify-content:center">
                ${label('save_connect')}
              </button>
            </div>
          ` : ''}
        </div>
      </div>
    `;

    openModal('app-connect-modal');
  };

  window.startAppOAuth = async function (appId) {
    const idInput = document.getElementById('oauth-client-id');
    const secretInput = document.getElementById('oauth-client-secret');
    const payload = {};
    if (idInput && idInput.value.trim()) payload.client_id = idInput.value.trim();
    if (secretInput && secretInput.value.trim()) payload.client_secret = secretInput.value.trim();

    const spinner = document.getElementById('oauth-status-spinner');
    const btn = document.getElementById('oauth-start-btn');
    if (spinner) spinner.style.display = 'block';
    if (btn) btn.disabled = true;

    try {
      const res = await authFetch(`/api/apps/${appId}/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (!res.ok || !data.ok) {
        alert(data.error || t('apps.auth_start_failed'));
        if (spinner) spinner.style.display = 'none';
        if (btn) btn.disabled = false;
        return;
      }

      if (data.auth_url) {
        window.open(data.auth_url, '_blank');
      }

      // Poll until connected
      let tries = 0;
      const pollTimer = setInterval(async () => {
        tries++;
        try {
          const stRes = await authFetch(`/api/apps/${appId}/status`);
          const stData = await stRes.json();
          if (stData.connected) {
            clearInterval(pollTimer);
            closeModal('app-connect-modal');
            _refreshAllContainers();
            return;
          }
        } catch (e) {}

        if (tries > 60) {
          clearInterval(pollTimer);
          if (spinner) spinner.innerText = t('apps.auth_timeout');
        }
      }, 2500);

    } catch (e) {
      alert(t('apps.network_error', { error: e.message || e }));
      if (spinner) spinner.style.display = 'none';
      if (btn) btn.disabled = false;
    }
  };

  window.saveAppApiKey = async function (appId) {
    const input = document.getElementById('app-api-key-input');
    const apiKey = input ? input.value.trim() : '';
    if (!apiKey) return;

    try {
      const res = await authFetch(`/api/apps/${appId}/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        alert(data.error || t('apps.save_credentials_failed'));
        return;
      }
      closeModal('app-connect-modal');
      _refreshAllContainers();
    } catch (e) {
      alert(t('apps.save_credentials_error', { error: e.message || e }));
    }
  };

  window.saveAppCustomCredentials = async function (appId) {
    const app = _appsState.apps.find(a => a.id === appId);
    if (!app || !app.auth || !app.auth.fields) return;

    const payload = {};
    for (const f of app.auth.fields) {
      const el = document.getElementById(`custom-field-${f.key}`);
      if (el) payload[f.key] = el.value.trim();
    }

    try {
      const res = await authFetch(`/api/apps/${appId}/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        alert(data.error || t('apps.save_config_failed'));
        return;
      }
      closeModal('app-connect-modal');
      _refreshAllContainers();
    } catch (e) {
      alert(t('apps.error', { error: e.message || e }));
    }
  };

  window.openAppConfigModal = async function (appId) {
    const app = _appsState.apps.find(a => a.id === appId);
    if (!app) return;

    let modal = document.getElementById('app-config-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'app-config-modal';
      modal.className = 'modal-backdrop';
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <div class="modal-dialog" style="max-width:540px; background:var(--bg-primary); border-radius:12px; border:1px solid var(--border-color); overflow:hidden">
        <div class="modal-head" style="display:flex; justify-content:space-between; align-items:center; padding:16px 20px; border-bottom:1px solid var(--border-color)">
          <div style="font-weight:700; font-size:1.1rem; color:var(--text-primary)">${label('settings_title', { name: app.name })}</div>
          <button class="btn-icon" onclick="closeModal('app-config-modal')" style="background:transparent; border:none; cursor:pointer">
            <span class="material-icons-round">close</span>
          </button>
        </div>
        <div class="modal-body" style="padding:20px">
          <div style="font-weight:600; font-size:0.9rem; margin-bottom:8px">${label('permissions_title')}</div>
          <div style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:12px">
            ${label('permissions_description')}
          </div>
          <div id="app-tools-container" style="min-height:100px">
            <span class="material-icons-round spin">progress_activity</span> ${label('loading_capabilities')}
          </div>

          <!-- Advanced Section -->
          <details class="app-advanced-drawer" style="margin-top:18px">
            <summary style="cursor:pointer; font-weight:600; color:var(--text-primary)">${label('advanced_details')}</summary>
            <div style="margin-top:10px; line-height:1.6; font-family:var(--font-mono); font-size:0.75rem">
              <div><b>${label('runtime')}:</b> ${escapeHtml(app.runtime_type)}</div>
              <div><b>${label('source')}:</b> ${escapeHtml(app.source)}</div>
              <div><b>${label('trust_label')}:</b> ${escapeHtml(app.trust_level)}</div>
              <div><b>${label('version')}:</b> ${escapeHtml(app.version)}</div>
              ${app.mcp_config ? `
                <div><b>${label('transport')}:</b> ${escapeHtml(app.mcp_config.type || 'streamableHttp')}</div>
                ${app.mcp_config.url ? `<div><b>${label('url')}:</b> ${escapeHtml(app.mcp_config.url)}</div>` : ''}
                ${app.mcp_config.command ? `<div><b>${label('command')}:</b> ${escapeHtml(app.mcp_config.command)} ${escapeHtml((app.mcp_config.args || []).join(' '))}</div>` : ''}
              ` : ''}
            </div>
          </details>

          <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:20px">
            <button class="btn-secondary" onclick="closeModal('app-config-modal')">${label('close')}</button>
            <button class="btn-primary" onclick="window.saveAppToolsAllowlist('${escapeHtml(app.id)}')">${label('save_changes')}</button>
          </div>
        </div>
      </div>
    `;

    openModal('app-config-modal');

    // Load tools
    try {
      const res = await authFetch(`/api/apps/${appId}/tools`);
      const data = await res.json();
      const toolsContainer = document.getElementById('app-tools-container');
      if (!toolsContainer) return;

      const tools = data.tools || [];
      const enabledSet = new Set(data.enabled_tools || ['*']);
      const allowAll = enabledSet.has('*');

      if (tools.length === 0) {
        toolsContainer.innerHTML = `<div style="font-size:0.8rem; color:var(--text-muted)">${label('all_tools_enabled')}</div>`;
        return;
      }

      toolsContainer.innerHTML = `
        <div class="app-tools-list">
          ${tools.map(t => {
            const isChecked = allowAll || enabledSet.has(t.name);
            return `
              <label class="app-tool-item" style="cursor:pointer">
                <input type="checkbox" class="tool-checkbox" data-tool-name="${escapeHtml(t.name)}" ${isChecked ? 'checked' : ''} style="margin-top:2px">
                <div style="flex:1">
                  <div style="font-weight:600; font-size:0.84rem; color:var(--text-primary)">${escapeHtml(t.name)}</div>
                  <div style="font-size:0.75rem; color:var(--text-secondary)">${escapeHtml(t.description || window.t('apps.no_description'))}</div>
                </div>
              </label>
            `;
          }).join('')}
        </div>
      `;
    } catch (e) {
      const el = document.getElementById('app-tools-container');
      if (el) el.innerHTML = `<div style="color:var(--accent-red)">${label('load_tools_failed', { error: e.message || e })}</div>`;
    }
  };

  window.saveAppToolsAllowlist = async function (appId) {
    const checkboxes = document.querySelectorAll('#app-tools-container .tool-checkbox');
    const enabled = [];
    checkboxes.forEach(cb => {
      if (cb.checked) enabled.push(cb.getAttribute('data-tool-name'));
    });

    try {
      const res = await authFetch(`/api/apps/${appId}/tools`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled_tools: enabled }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        alert(data.error || t('apps.update_tools_failed'));
        return;
      }
      closeModal('app-config-modal');
      _refreshAllContainers();
    } catch (e) {
      alert(t('apps.error', { error: e.message || e }));
    }
  };

  window.openAddCustomAppModal = function () {
    let modal = document.getElementById('app-custom-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'app-custom-modal';
      modal.className = 'modal-backdrop';
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <div class="modal-dialog" style="max-width:500px; background:var(--bg-primary); border-radius:12px; border:1px solid var(--border-color); overflow:hidden">
        <div class="modal-head" style="display:flex; justify-content:space-between; align-items:center; padding:16px 20px; border-bottom:1px solid var(--border-color)">
          <div style="font-weight:700; font-size:1.1rem; color:var(--text-primary)">${label('custom_title')}</div>
          <button class="btn-icon" onclick="closeModal('app-custom-modal')" style="background:transparent; border:none; cursor:pointer">
            <span class="material-icons-round">close</span>
          </button>
        </div>
        <div class="modal-body" style="padding:20px">
          <div style="margin-bottom:12px">
            <label class="form-label">${label('integration_name')}</label>
            <input type="text" id="custom-app-name" class="form-input" placeholder="${label('integration_name_placeholder')}" style="width:100%">
          </div>
          <div style="margin-bottom:12px">
            <label class="form-label">${label('runtime_type')}</label>
            <select id="custom-app-type" class="form-select" style="width:100%" onchange="window.toggleCustomAppFields(this.value)">
              <option value="mcp_remote">${label('remote_mcp')}</option>
              <option value="mcp_local">${label('local_mcp')}</option>
            </select>
          </div>
          <div id="custom-field-remote-url" style="margin-bottom:12px">
            <label class="form-label">${label('endpoint_url')}</label>
            <input type="url" id="custom-app-url" class="form-input" placeholder="https://mcp.company.com/mcp" style="width:100%">
          </div>
          <div id="custom-field-local-cmd" style="margin-bottom:12px; display:none">
            <label class="form-label">${label('command_arguments')}</label>
            <input type="text" id="custom-app-cmd" class="form-input" placeholder="${label('command_placeholder')}" style="width:100%">
          </div>
          <div style="margin-bottom:12px">
            <label class="form-label">${label('authentication')}</label>
            <select id="custom-app-auth" class="form-select" style="width:100%">
              <option value="none">${label('no_authentication')}</option>
              <option value="api_key">${label('api_key_option')}</option>
            </select>
          </div>
          <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:20px">
            <button class="btn-secondary" onclick="closeModal('app-custom-modal')">${label('cancel')}</button>
            <button class="btn-primary" onclick="window.submitCustomApp()">${label('install_app')}</button>
          </div>
        </div>
      </div>
    `;

    openModal('app-custom-modal');
  };

  window.toggleCustomAppFields = function (type) {
    const urlEl = document.getElementById('custom-field-remote-url');
    const cmdEl = document.getElementById('custom-field-local-cmd');
    if (urlEl) urlEl.style.display = type === 'mcp_remote' ? 'block' : 'none';
    if (cmdEl) cmdEl.style.display = type === 'mcp_local' ? 'block' : 'none';
  };

  window.submitCustomApp = async function () {
    const name = (document.getElementById('custom-app-name') || {}).value || '';
    const runtime_type = (document.getElementById('custom-app-type') || {}).value || 'mcp_remote';
    const url = (document.getElementById('custom-app-url') || {}).value || '';
    const cmdStr = (document.getElementById('custom-app-cmd') || {}).value || '';
    const auth_type = (document.getElementById('custom-app-auth') || {}).value || 'none';

    if (!name.trim()) {
      alert(t('apps.name_required'));
      return;
    }

    const payload = {
      name: name.trim(),
      runtime_type,
      auth_type,
      url: url.trim(),
    };

    if (runtime_type === 'mcp_local') {
      const parts = cmdStr.trim().split(/\s+/);
      payload.command = parts[0] || '';
      payload.args = parts.slice(1);
    }

    try {
      const res = await authFetch('/api/apps/custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        alert(data.error || t('apps.create_failed'));
        return;
      }
      closeModal('app-custom-modal');
      _refreshAllContainers();
    } catch (e) {
      alert(t('apps.create_error', { error: e.message || e }));
    }
  };

  /* ── Backward Compatibility Hooks ─────────────────────────────────── */
  window.loadPluginsPanel = async function () {
    const pContainer = document.getElementById('subpanel-plugins');
    if (!pContainer) return;

    let marketDiv = document.getElementById('apps-marketplace-container');
    if (!marketDiv) {
      marketDiv = document.createElement('div');
      marketDiv.id = 'apps-marketplace-container';
      pContainer.innerHTML = '';
      pContainer.appendChild(marketDiv);
    }
    await window.loadAppsMarketplace(marketDiv);
  };

  window.loadConnectedAppsPanel = async function () {
    const container = document.getElementById('connected-apps-container');
    if (container) await window.loadAppsMarketplace(container);
  };

  window.installPlugin = async function (explicitName) {
    if (explicitName) return window.installApp(explicitName);
    const input = document.getElementById('plugin-install-name');
    if (input && input.value.trim()) return window.installApp(input.value.trim());
  };

  window.uninstallPlugin = async function (name) {
    return window.uninstallApp(name);
  };

  window.updateTtsSettingsVisibility = function () {
    const toggle = document.getElementById("tts-toggle");
    const provSelect = document.getElementById("s-audio-ttsProvider");
    const voiceRow = document.getElementById("tts-voice-row");
    const langRow = document.getElementById("tts-lang-row");
    const speedRow = document.getElementById("tts-speed-row");
    const provRow = document.getElementById("tts-provider-row");

    if (!toggle || !provSelect) return;
    const checked = toggle.checked;
    const provider = provSelect.value;

    const showSupertonic = (checked && provider === "supertonic");
    if (provRow) provRow.style.display = checked ? "flex" : "none";
    if (voiceRow) voiceRow.style.display = showSupertonic ? "flex" : "none";
    if (langRow) langRow.style.display = showSupertonic ? "flex" : "none";
    if (speedRow) speedRow.style.display = showSupertonic ? "flex" : "none";
  };

  window.openRagSettingsModal = async function () {
    try {
      const res = await authFetch("/api/settings");
      const cfg = await res.json();
      if (cfg.error) throw cfg.error;
      window._shibaConfig = cfg;
      if (typeof populateSettings === "function") populateSettings(cfg);
    } catch (e) {
      console.error("Failed to load settings before opening modal", e);
    }
    openModal("rag-settings-modal");
  };

})();
