import test from 'node:test';
import assert from 'node:assert/strict';
import { browserFixture, profileResponse, settle } from './browser-fixture.mjs';

test('workspace routes reuse the original panels and expose exactly one active panel', async () => {
    const { context: app, document, nodes } = browserFixture();
    const routes = [
        ['fs-modal', 'library'], ['knowledge-modal', 'library'], ['memory-modal', 'library'],
        ['automation-modal', 'automations'], ['connected-apps-modal', 'apps'],
    ];
    let retainedClicks = 0;
    const original = nodes['fs-modal'];
    original.addEventListener('click', () => retainedClicks++);
    const originalDialog = original.querySelector(':scope > .modal');
    Object.assign(originalDialog.style, { width: '600px', 'max-width': '90vw', height: '80vh', 'max-height': '90vh' });
    for (const [id, page] of [...routes, routes[0]]) {
        await app.openModal(id);
        assert.equal(document.getElementById(id), nodes[id], 'routing must preserve element identity');
        assert.equal(nodes[id].parentNode, nodes['workspace-stage']);
        assert.deepEqual(routes.filter(([key]) => nodes[key].classList.contains('active')).map(([key]) => key), [id]);
        assert.equal(nodes['chat-area'].style.display, 'none');
        assert.equal(nodes['workspace-view'].style.display, 'flex');
        const selected = document.querySelectorAll('[data-workspace-page]').filter(button => button.getAttribute('aria-current') === 'page');
        assert.equal(selected.length, 1);
        assert.equal(selected[0].dataset.workspacePage, page);
        assert.equal(nodes['workspace-library-tabs'].hidden, page !== 'library');
        assert.equal(nodes['workspace-app-actions'].hidden, page !== 'apps');
        assert.equal(nodes['workspace-agents'].hidden, true);
        assert.equal(nodes['workspace-page-heading'].textContent, app.t(`workspace.${page}`));
    }
    original.dispatchEvent({ type: 'click' });
    assert.equal(retainedClicks, 1, 'handlers must survive repeated routing');
    for (const property of ['width', 'max-width', 'height', 'max-height']) {
        assert.equal(originalDialog.style[property], undefined, 'modal dimensions must not constrain the page panel');
    }
    app.closeModal('fs-modal');
    assert.equal(nodes['chat-area'].style.display, 'flex');
    assert.equal(nodes['workspace-view'].style.display, 'none');
    assert.equal(original.classList.contains('active'), false);
});

test('a response from Agents cannot repaint the grid or cache after navigating away', async () => {
    const { context: app, nodes, requests } = browserFixture();
    app.openWorkspaceAgents();
    assert.equal(requests[0].url, '/api/profiles');
    await app.openModal('knowledge-modal');
    const gridBefore = nodes['workspace-agent-grid'].textContent;
    requests[0].resolve(profileResponse([{ id: 'old', label: 'Stale profile' }]));
    await settle();
    assert.equal(nodes['workspace-agent-grid'].textContent, gridBefore);
    assert.equal(app._profilesCache.length, 0);
    assert.equal(nodes['knowledge-modal'].classList.contains('active'), true);
});

test('a stale failed Agents request cannot replace content after navigation', async () => {
    const { context: app, nodes, requests } = browserFixture();
    app.openWorkspaceAgents();
    app.showWorkspaceChat();
    const gridBefore = nodes['workspace-agent-grid'].textContent;
    requests[0].reject(new Error('offline'));
    await settle();
    assert.equal(nodes['workspace-agent-grid'].textContent, gridBefore);
    assert.equal(nodes['workspace-view'].style.display, 'none');
});

test('the latest Agents request wins when requests complete in reverse order', async () => {
    const { context: app, nodes, requests } = browserFixture();
    app.openWorkspaceAgents();
    const newest = app.refreshWorkspaceAgents();
    requests[1].resolve(profileResponse([{ id: 'new', label: 'Current profile' }]));
    await newest;
    requests[0].resolve(profileResponse([{ id: 'old', label: 'Old profile' }]));
    await settle();
    assert.equal(nodes['workspace-agent-grid'].children.length, 1);
    assert.ok(nodes['workspace-agent-grid'].textContent.includes('Current profile'));
    assert.ok(!nodes['workspace-agent-grid'].textContent.includes('Old profile'));
    assert.equal(app._profilesCache[0].id, 'new');
});

test('Agents shows a current fetch error and a retry can recover to an empty result', async () => {
    const { context: app, nodes, requests } = browserFixture();
    app.openWorkspaceAgents();
    requests[0].resolve({ ok: false });
    await settle();
    assert.equal(nodes['workspace-agent-grid'].textContent, app.t('workspace.agents_error'));
    const retry = app.refreshWorkspaceAgents();
    assert.equal(nodes['workspace-agent-grid'].textContent, app.t('workspace.loading_agents'));
    requests[1].resolve(profileResponse([]));
    await retry;
    assert.equal(nodes['workspace-agent-grid'].textContent, app.t('workspace.agents_empty'));
});

test('Agents cards keep profile text as text and start a chat with the chosen profile', async () => {
    const { context: app, nodes, requests, emissions } = browserFixture();
    app.openWorkspaceAgents();
    const label = '<img src=x onerror=alert(1)>';
    requests[0].resolve(profileResponse([{ id: 'research', label, description: '<script>bad()</script>' }]));
    await settle();
    const card = nodes['workspace-agent-grid'].children[0];
    assert.equal(card.children[1].textContent, label);
    assert.equal(card.children[1].children.length, 0);
    assert.equal(card.children[2].children.length, 0);
    card.children[3].children[2].dispatchEvent({ type: 'click' });
    assert.deepEqual(JSON.parse(JSON.stringify(emissions)), [['new_session', { profile_id: 'research' }]]);
    assert.equal(nodes['chat-area'].style.display, 'flex');
    assert.equal(nodes['workspace-view'].style.display, 'none');
    assert.equal(nodes['chat-input'].focused, true);
});

test('context open, close and Escape use the real modal hooks to synchronize state and aria', async () => {
    const { context: app, document, nodes } = browserFixture();
    await app.openModal('context-modal');
    assert.equal(nodes['context-modal'].parentNode, nodes['chat-area']);
    assert.equal(app.state.contextModalOpen, true);
    assert.equal(nodes['context-modal'].classList.contains('active'), true);
    assert.equal(nodes['chat-area'].classList.contains('context-visible'), true);
    assert.equal(nodes['workspace-context-toggle'].getAttribute('aria-expanded'), 'true');
    app.closeModal('context-modal');
    assert.equal(app.state.contextModalOpen, false);
    assert.equal(nodes['context-modal'].classList.contains('active'), false);
    assert.equal(nodes['chat-area'].classList.contains('context-visible'), false);
    assert.equal(nodes['workspace-context-toggle'].getAttribute('aria-expanded'), 'false');
    await app.openModal('context-modal');
    document.dispatchEvent({ type: 'keydown', key: 'Escape' });
    assert.equal(app.state.contextModalOpen, false);
    assert.equal(nodes['workspace-context-toggle'].getAttribute('aria-expanded'), 'false');
});

test('Escape preserves context while a foreground dialog is active', async () => {
    const { context: app, document, nodes } = browserFixture();
    await app.openModal('context-modal');
    const dialog = document.createElement('div');
    dialog.className = 'modal-backdrop active';
    document.body.appendChild(dialog);
    document.dispatchEvent({ type: 'keydown', key: 'Escape' });
    assert.equal(app.state.contextModalOpen, true);
    assert.equal(nodes['workspace-context-toggle'].getAttribute('aria-expanded'), 'true');
});

test('appearance follows system changes and persists an explicit selection across reloads', () => {
    const { document, nodes, storage, systemTheme } = browserFixture({ dark: true });
    assert.equal(document.documentElement.dataset.theme, 'dark');
    assert.equal(nodes['workspace-theme'].value, 'system');
    systemTheme.matches = false;
    systemTheme.dispatchEvent({ type: 'change' });
    assert.equal(document.documentElement.dataset.theme, 'light');
    nodes['workspace-theme'].value = 'dark';
    nodes['workspace-theme'].dispatchEvent({ type: 'change' });
    assert.equal(storage.get('shibaclaw_theme'), 'dark');
    systemTheme.dispatchEvent({ type: 'change' });
    assert.equal(document.documentElement.dataset.theme, 'dark');
    const restored = browserFixture({ stored: Object.fromEntries(storage), dark: false });
    assert.equal(restored.document.documentElement.dataset.theme, 'dark');
    assert.equal(restored.nodes['workspace-theme'].value, 'dark');
});

test('sidebar collapse is reversible and survives reloads', () => {
    const { context: app, document, storage } = browserFixture();
    app.toggleWorkspaceSidebar();
    assert.equal(document.body.classList.contains('workspace-sidebar-collapsed'), true);
    assert.equal(storage.get('shibaclaw_sidebar_collapsed'), 'true');
    const restored = browserFixture({ stored: Object.fromEntries(storage) });
    assert.equal(restored.document.body.classList.contains('workspace-sidebar-collapsed'), true);
    restored.context.toggleWorkspaceSidebar();
    assert.equal(restored.document.body.classList.contains('workspace-sidebar-collapsed'), false);
    assert.equal(restored.storage.get('shibaclaw_sidebar_collapsed'), 'false');
});
