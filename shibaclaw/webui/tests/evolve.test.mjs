import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { browserFixture, readFrontend, settle } from './browser-fixture.mjs';

function fixture() {
    const fixture = browserFixture();
    const timers = new Map();
    let nextTimer = 0;
    fixture.context.setInterval = callback => {
        timers.set(++nextTimer, callback);
        return nextTimer;
    };
    fixture.context.clearInterval = id => timers.delete(id);
    vm.runInContext(readFrontend('js/evolve.js'), fixture.context);
    return { ...fixture, timers };
}

const snapshot = overrides => ({
    code: 3, applies: 0, max_applies: 3, job: null, repo: null, body: null,
    chronicle: '', backlog: '', patterns: '', world: '', ...overrides,
});
const response = data => ({ ok: true, json: async () => data });

test('Evolution opens as a workspace page and only requests a read-only snapshot', async () => {
    const { context: app, nodes, requests, timers } = fixture();
    assert.equal(requests.length, 0, 'loading the module must not contact or activate Evolution');
    await app.openModal('evolve-modal');
    assert.equal(nodes['evolve-modal'].parentNode, nodes['workspace-stage']);
    assert.equal(nodes['workspace-page-heading'].textContent, app.t('workspace.evolution'));
    assert.equal(nodes['workspace-evolve-actions'].hidden, false);
    assert.equal(nodes['workspace-library-tabs'].hidden, true);
    assert.equal(timers.size, 1);
    assert.deepEqual(requests.map(request => request.url), ['/api/evolve']);
    requests[0].resolve(response(snapshot()));
    await settle();
    assert.match(nodes['evolve-content'].innerHTML, />off</);
    assert.match(nodes['evolve-content'].innerHTML, /Nothing here yet/);
    app.showWorkspaceChat();
    assert.equal(timers.size, 0, 'leaving the page must stop polling immediately');
    await app.loadEvolve();
    assert.equal(requests.length, 1, 'a hidden page must not request status');
});

test('Evolution escapes notes, repository names and commit subjects before rendering', async () => {
    const { context: app, nodes, requests } = fixture();
    await app.openModal('evolve-modal');
    const unsafe = '<img src=x onerror=alert(1)>';
    requests[0].resolve(response(snapshot({
        chronicle: unsafe, backlog: unsafe, patterns: unsafe, world: unsafe,
        repo: { name: unsafe, branch: unsafe, dirty: true, commits: [{ sha: unsafe, subject: unsafe, date: unsafe }] },
    })));
    await settle();
    assert.ok(nodes['evolve-content'].innerHTML.includes('&lt;img'));
    assert.ok(!nodes['evolve-content'].innerHTML.includes('<img'));
    app.showWorkspaceChat();
});

test('Evolution polls while visible, avoids overlapping requests, and renders gate states', async () => {
    const { context: app, nodes, requests, timers } = fixture();
    await app.openModal('evolve-modal');
    const poll = [...timers.values()][0];
    poll();
    await app.loadEvolve();
    assert.equal(requests.length, 1);
    for (const [index, [code, label]] of [[2, 'panic'], [5, 'in progress'], [6, 'daily budget'], [7, 'cooldown'], [0, 'ready']].entries()) {
        if (index) poll();
        requests[index].resolve(response(snapshot({ code })));
        await settle();
        assert.ok(nodes['evolve-content'].innerHTML.includes(`>${label}</`));
    }
    app.closeModal('evolve-modal');
    assert.equal(timers.size, 0);
});

test('Evolution reports authorization or transport failures and refresh recovers', async () => {
    const { context: app, nodes, requests } = fixture();
    await app.openModal('evolve-modal');
    requests[0].resolve({ ok: false, status: 401 });
    await settle();
    assert.match(nodes['evolve-content'].innerHTML, /Failed to load evolution.*401/);
    const retry = app.loadEvolve();
    requests[1].resolve(response(snapshot({ code: 0 })));
    await retry;
    assert.match(nodes['evolve-content'].innerHTML, />ready</);
    app.showWorkspaceChat();
});

test('an old Evolution response cannot overwrite a reopened page', async () => {
    const { context: app, nodes, requests } = fixture();
    await app.openModal('evolve-modal');
    await app.openModal('connected-apps-modal');
    await app.openModal('evolve-modal');
    requests[1].resolve(response(snapshot({ chronicle: 'Current snapshot' })));
    await settle();
    requests[0].resolve(response(snapshot({ chronicle: 'Obsolete snapshot' })));
    await settle();
    assert.match(nodes['evolve-content'].innerHTML, /Current snapshot/);
    assert.doesNotMatch(nodes['evolve-content'].innerHTML, /Obsolete snapshot/);
    app.showWorkspaceChat();
});

test('opening Library directly stops Evolution polling', async () => {
    const { context: app, nodes, requests, timers } = fixture();
    await app.openModal('evolve-modal');
    requests[0].resolve(response(snapshot()));
    await settle();
    app.openWorkspaceLibrary();
    assert.equal(timers.size, 0);
    assert.equal(nodes['evolve-modal'].classList.contains('active'), false);
    assert.equal(nodes['workspace-agent-graph'].hidden, false);
});

test('Evolution heading and navigation track all supported locales', async () => {
    const { context: app, nodes, requests } = fixture();
    await app.openModal('evolve-modal');
    requests[0].resolve(response(snapshot()));
    await settle();
    for (const locale of app.i18n.LOCALES) {
        app.i18n.setLocale(locale.id, { skipHealth: true, skipDynamic: true });
        assert.equal(nodes['workspace-page-heading'].textContent, app.t('workspace.evolution'));
        assert.equal(nodes['workspace-page-description'].textContent, app.t('workspace.evolution_subtitle'));
    }
    app.showWorkspaceChat();
});
