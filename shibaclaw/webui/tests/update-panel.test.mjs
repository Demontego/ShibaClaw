import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../frontend/js/update_panel.js', import.meta.url), 'utf8');

function panelContext(update, report) {
    const panel = { innerHTML: '' };
    const requests = [];
    const confirmations = [];
    const context = vm.createContext({
        console,
        document: { getElementById: () => null },
        $: () => panel,
        escapeHtml: value => String(value).replaceAll('<', '&lt;').replaceAll('>', '&gt;'),
        shibaDialog: async (...args) => { confirmations.push(args); return true; },
        authFetch: async (url, options) => {
            requests.push({ url, payload: JSON.parse(options.body) });
            return { ok: true, json: async () => report };
        },
    });
    context.window = context;
    vm.runInContext(source, context);
    vm.runInContext(`_updateState.result = ${JSON.stringify(update)};`, context);
    return { context, panel, requests, confirmations };
}

test('managed download stays open and offers an explicit restart', async () => {
    const state = panelContext({
        install_method: 'exe', managed_install: true, action_kind: 'automatic', latest: '1.0.7',
    }, {
        exe: { ok: true }, ready_to_restart: true, restarting: false,
        message: 'Downloaded and verified.',
    });
    await state.context.runUpdateAction();
    assert.equal(state.requests[0].payload.update.phase, 'download');
    assert.equal(state.confirmations.length, 0);
    assert.match(state.panel.innerHTML, /Restart to update/);
    assert.match(state.panel.innerHTML, /Later/);
    assert.doesNotMatch(state.panel.innerHTML, /Restarting ShibaClaw now/);

    await state.context.runUpdateAction();
    assert.equal(state.requests[1].payload.update.phase, 'restart');
    assert.equal(state.confirmations.length, 1);
    assert.equal(state.confirmations[0][1], 'Restart to install update?');
});

test('failed download never offers restart or claims success', async () => {
    const state = panelContext({
        install_method: 'exe', managed_install: true, action_kind: 'automatic', latest: '1.0.7',
    }, { exe: { ok: false, output: 'SHA256 mismatch' }, message: 'Download failed.' });
    await state.context.runUpdateAction();
    assert.match(state.panel.innerHTML, /SHA256 mismatch/);
    assert.doesNotMatch(state.panel.innerHTML, /Restart to update|Update complete/);
});

test('managed check renders the downloaded state after reopening', () => {
    const state = panelContext({}, {});
    const html = state.context._renderUpdateActionSection({
        update_available: true, managed_install: true, ready_to_restart: true,
        action_kind: 'automatic', notes: [],
    });
    assert.match(html, /Restart to update/);
    assert.doesNotMatch(html, /Download update/);
});

test('portable setup guidance never offers automatic replacement', async () => {
    const state = panelContext({ install_method: 'exe', action_kind: 'manual-url' }, {});
    await state.context.runUpdateAction();
    assert.equal(state.requests.length, 0);
});
