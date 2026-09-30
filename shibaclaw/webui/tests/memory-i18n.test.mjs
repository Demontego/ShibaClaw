import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { browserFixture, readFrontend, settle } from './browser-fixture.mjs';

const placeholders = value => [...value.matchAll(/\{([\w]+)\}/g)].map(match => match[1]).sort();
const emptyMemory = () => ({ memory: '', user: '', history: '', diary: '', tokens: 25, max_tokens: 1500, quarantined: [] });
const response = data => ({ ok: true, json: async () => data });

function memoryFixture() {
    const fixture = browserFixture();
    const { context: app, document, nodes } = fixture;
    const requests = [], alerts = [], confirmations = [];
    let allowForget = false;
    for (const id of ['memory-content-area', 'memory-token-badge', 'btn-memory-edit-toggle', 'btn-memory-save', 'memory-save-status', 'memory-forget-input']) {
        assert.ok(readFrontend('index.html').includes(`id="${id}"`), `missing real Memory element: ${id}`);
        nodes[id] = document.createElement(id.includes('input') ? 'input' : 'div');
        nodes[id].setAttribute('id', id);
        nodes['memory-modal'].appendChild(nodes[id]);
    }
    const saveLabel = document.createElement('span');
    saveLabel.setAttribute('data-i18n', 'common.save');
    nodes['btn-memory-save'].appendChild(saveLabel);
    nodes['memory-modal'].classList.add('active');

    // Represent just the two dynamic editor nodes; the shared fixture does not parse HTML.
    const area = nodes['memory-content-area'];
    const html = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(area), 'innerHTML');
    Object.defineProperty(area, 'innerHTML', {
        get() { return html.get.call(this); },
        set(value) {
            html.set.call(this, value);
            if (!value.includes('id="memory-editor-textarea"')) return;
            const caption = document.createElement('div');
            caption.setAttribute('id', 'memory-editor-caption');
            const editor = document.createElement('textarea');
            editor.setAttribute('id', 'memory-editor-textarea');
            this.append(caption, editor);
        },
    });
    app.authFetch = (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject }));
    app.alert = message => alerts.push(message);
    app.confirm = message => { confirmations.push(message); return allowForget; };
    app.renderMarkdown = value => app.escapeHtml(value);
    app.setTimeout = () => 0;
    vm.runInContext(readFrontend('js/memory.js'), app, { filename: 'memory.js' });
    return { ...fixture, requests, alerts, confirmations, saveLabel, allowForget: value => { allowForget = value; } };
}

test('all eight locales provide every Memory label with matching placeholders', () => {
    const { context: app } = browserFixture();
    const catalogs = app.__I18N_CATALOGS__;
    const keys = Object.keys(catalogs.en).filter(key => key.startsWith('memory.')).sort();
    assert.equal(app.i18n.LOCALES.length, 8);
    assert.equal(keys.length, 27);
    const html = readFrontend('index.html');
    const modal = html.slice(html.indexOf('<div id="memory-modal"'), html.indexOf('<!-- ══ Connected Apps Modal'));
    const references = new Set();
    for (const source of [modal, readFrontend('js/memory.js')]) {
        for (const match of source.matchAll(/["']((?:memory|common)\.[a-z_]+)["']/g)) references.add(match[1]);
    }
    for (const locale of app.i18n.LOCALES) {
        const catalog = catalogs[locale.id];
        assert.deepEqual(Object.keys(catalog).filter(key => key.startsWith('memory.')).sort(), keys);
        for (const key of keys) {
            assert.ok(catalog[key].trim(), `${locale.id}: empty ${key}`);
            assert.deepEqual(placeholders(catalog[key]), placeholders(catalogs.en[key]), `${locale.id}: ${key}`);
        }
        for (const key of references) assert.ok(catalog[key], `${locale.id}: missing UI key ${key}`);
    }
});

test('locale changes refresh visible Memory without replacing an unsaved editor draft', async () => {
    const { context: app, document, nodes, requests, saveLabel } = memoryFixture();
    const load = app.loadMemoryData();
    requests[0].resolve(response(emptyMemory()));
    await load;
    for (const locale of app.i18n.LOCALES) {
        app.i18n.setLocale(locale.id, { skipHealth: true, skipDynamic: true });
        assert.ok(nodes['memory-content-area'].innerHTML.includes(app.escapeHtml(app.t('memory.empty_hint'))));
    }
    app.toggleMemoryEdit();
    const editor = document.getElementById('memory-editor-textarea');
    editor.value = 'Unsaved draft <img src=x> $& {preview}';
    const originalHTML = nodes['memory-content-area'].innerHTML;
    for (const locale of app.i18n.LOCALES) {
        app.i18n.setLocale(locale.id, { skipHealth: true, skipDynamic: true });
        assert.equal(document.getElementById('memory-editor-textarea'), editor);
        assert.equal(editor.value, 'Unsaved draft <img src=x> $& {preview}');
        assert.equal(nodes['memory-content-area'].innerHTML, originalHTML);
        assert.equal(document.getElementById('memory-editor-caption').textContent, app.t('memory.editing', { file: 'MEMORY.md' }));
        assert.equal(nodes['btn-memory-edit-toggle'].getAttribute('aria-label'), app.t('memory.view'));
        assert.equal(saveLabel.textContent, app.t('common.save'));
        assert.ok(nodes['memory-token-badge'].innerHTML.includes(app.escapeHtml(app.t('memory.tokens', { current: 25, max: 1500, pct: 2 }))));
    }
    const save = app.saveCurrentMemoryFile();
    assert.equal(requests[1].url, '/api/memory/save');
    assert.deepEqual(JSON.parse(requests[1].options.body), { file: 'MEMORY.md', content: editor.value });
    requests[1].resolve(response({ tokens: 30 }));
    await save;
    assert.equal(document.getElementById('memory-editor-textarea'), null);
    assert.equal(nodes['memory-save-status'].textContent, app.t('memory.saved'));
});

test('forget requests require confirmation and retain literal search content and the preview limit', async () => {
    const { context: app, nodes, requests, confirmations, allowForget } = memoryFixture();
    const needle = '$& {preview} <needle>';
    nodes['memory-forget-input'].value = needle;
    const matches = { counts: { 'MEMORY.md': 7 }, matches: { 'MEMORY.md': ['one', 'two', 'three', 'four', 'five', 'six', 'seven'] } };
    const cancelled = app.searchForgetMemory();
    assert.equal(requests[0].url, '/api/memory/forget');
    assert.deepEqual(JSON.parse(requests[0].options.body), { needle, confirm: false });
    requests[0].resolve(response(matches));
    await cancelled;
    assert.equal(requests.length, 1, 'declining confirmation must prevent the destructive request');
    assert.equal(confirmations.length, 1);
    assert.ok(confirmations[0].includes(needle), 'search input must remain literal after interpolation');
    assert.ok(confirmations[0].includes('[MEMORY] five'));
    assert.ok(!confirmations[0].includes('[MEMORY] six'));

    allowForget(true);
    const accepted = app.searchForgetMemory();
    requests[1].resolve(response(matches));
    await settle();
    assert.equal(confirmations.length, 2);
    assert.equal(requests[2].url, '/api/memory/forget');
    assert.deepEqual(JSON.parse(requests[2].options.body), { needle, confirm: true });
    requests[2].resolve(response({}));
    await settle();
    assert.equal(requests[3].url, '/api/memory');
    requests[3].resolve(response(emptyMemory()));
    await accepted;
    assert.equal(nodes['memory-forget-input'].value, '');
});

test('Memory load errors escape server text and refresh translated server status on locale change', async () => {
    const { context: app, nodes, requests } = memoryFixture();
    const failed = app.loadMemoryData();
    requests[0].resolve({ ok: false, status: 503 });
    await failed;
    app.i18n.setLocale('de', { skipHealth: true, skipDynamic: true });
    assert.ok(nodes['memory-content-area'].innerHTML.includes(app.t('memory.server_error', { status: 503 })));
    const unsafe = app.loadMemoryData();
    requests[1].reject(new Error('<img src=x onerror=alert(1)> $& {error}'));
    await unsafe;
    assert.ok(nodes['memory-content-area'].innerHTML.includes(app.escapeHtml('<img src=x onerror=alert(1)> $& {error}')));
    assert.ok(!nodes['memory-content-area'].innerHTML.includes('<img src=x'));
});
