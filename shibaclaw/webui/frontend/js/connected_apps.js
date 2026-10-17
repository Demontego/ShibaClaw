/**
 * Connected Apps — unified marketplace bridge.
 * Settings > Connected Apps / Workspace > Apps
 */

(function () {
  'use strict';

  window.loadConnectedAppsPanel = async function () {
    const container = document.getElementById('connected-apps-container');
    if (!container) return;
    if (typeof window.loadAppsMarketplace === 'function') {
      return window.loadAppsMarketplace(container);
    }
    container.innerHTML = `<div class="ca-loading">Loading Apps…</div>`;
  };

  document.addEventListener('shiba-modal-opened', function (e) {
    if (e.detail && e.detail.id === 'connected-apps-modal') {
      if (typeof window.loadConnectedAppsPanel === 'function') {
        window.loadConnectedAppsPanel();
      }
    }
  });
})();
