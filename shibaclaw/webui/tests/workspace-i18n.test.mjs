import test from 'node:test';
import assert from 'node:assert/strict';
import { browserFixture, readFrontend } from './browser-fixture.mjs';

const placeholders = value => [...value.matchAll(/\{([\w]+)\}/g)].map(match => match[1]).sort();

test('all eight locales supply every workspace key with matching placeholders', () => {
    const { context: app } = browserFixture();
    const catalogs = app.__I18N_CATALOGS__;
    const locales = Array.from(app.i18n.LOCALES, locale => locale.id);
    assert.equal(locales.length, 8);
    const keys = Object.keys(catalogs.en).filter(key => key.startsWith('workspace.')).sort();
    assert.ok(keys.length > 0);
    const used = new Set();
    for (const path of ['index.html', 'js/workspace.js', 'js/ui_panels.js', 'js/utils.js']) {
        for (const match of readFrontend(path).matchAll(/["'](workspace\.[a-z_]+)["']/g)) used.add(match[1]);
    }
    for (const key of used) assert.ok(keys.includes(key), `missing English key used by UI: ${key}`);
    for (const locale of locales) {
        assert.deepEqual(Object.keys(catalogs[locale]).filter(key => key.startsWith('workspace.')).sort(), keys, `${locale} key parity`);
        for (const key of keys) {
            assert.equal(typeof catalogs[locale][key], 'string', `${locale}: ${key}`);
            assert.ok(catalogs[locale][key].trim(), `${locale}: ${key} is empty`);
            assert.deepEqual(placeholders(catalogs[locale][key]), placeholders(catalogs.en[key]), `${locale}: ${key} placeholders`);
        }
    }
});

test('the real translation runtime interpolates workspace values in every locale', () => {
    const { context: app } = browserFixture();
    const catalogs = app.__I18N_CATALOGS__;
    const variables = { model: 'ExampleModel', limit: '128k', used: '12k', pct: 9 };
    for (const locale of app.i18n.LOCALES) {
        app.i18n.setLocale(locale.id, { skipHealth: true, skipDynamic: true });
        assert.equal(app.i18n.getLocale(), locale.id);
        for (const [key, value] of Object.entries(catalogs[locale.id]).filter(([key]) => key.startsWith('workspace.'))) {
            const expected = value.replace(/\{([\w]+)\}/g, (_, name) => variables[name]);
            assert.equal(app.t(key, variables), expected, `${locale.id}: ${key}`);
        }
    }
});

test('locale changes update the currently open workspace heading and navigation labels', async () => {
    const { context: app, document, nodes } = browserFixture();
    await app.openModal('knowledge-modal');
    for (const locale of app.i18n.LOCALES) {
        app.i18n.setLocale(locale.id, { skipHealth: true, skipDynamic: true });
        assert.equal(nodes['workspace-page-heading'].textContent, app.__I18N_CATALOGS__[locale.id]['workspace.library']);
        assert.equal(nodes['workspace-page-description'].textContent, app.t('workspace.library_subtitle'));
        for (const button of document.querySelectorAll('[data-workspace-page]')) {
            const key = button.dataset.workspacePage === 'chat' ? 'conversations' : button.dataset.workspacePage;
            assert.equal(button.getAttribute('aria-label'), app.t(`workspace.${key}`));
        }
    }
});

test('conversation titles survive language changes and new chat restores a localized label', () => {
    const { context: app, nodes } = browserFixture();
    app.setWorkspaceChatTitle('Design review', 'workspace.conversations');
    for (const locale of app.i18n.LOCALES) {
        app.i18n.setLocale(locale.id, { skipHealth: true, skipDynamic: true });
        assert.equal(nodes['workspace-chat-title'].textContent, 'Design review');
    }
    app.setWorkspaceChatTitle('');
    assert.equal(nodes['workspace-chat-title'].textContent, app.t('workspace.new_chat'));
    app.setWorkspaceChatTitle(null, 'workspace.conversations');
    assert.equal(nodes['workspace-chat-title'].textContent, app.t('workspace.conversations'));
});

test('token cards localize their content and escape a model name before inserting HTML', () => {
    const { context: app, nodes } = browserFixture();
    const tokens = {
        active_model: 'provider/<img src=x onerror=alert(1)>', auto_detected: true,
        context_window: 128000, system_prompt: 1234, tools: 500, messages: 1000, total: 2734, usage_pct: 2,
    };
    for (const locale of app.i18n.LOCALES) {
        app.i18n.setLocale(locale.id, { skipHealth: true, skipDynamic: true });
        const html = app.buildTokenCard(tokens);
        assert.ok(html.includes(app.escapeHtml(app.t('workspace.tokens'))));
        assert.ok(html.includes(app.escapeHtml(app.t('workspace.tokens_system'))));
        assert.ok(html.includes((1234).toLocaleString(app.i18n.clockLocale())));
        assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;'));
        assert.ok(!html.includes('<img src=x'));
        assert.ok(!html.includes('{model}') && !html.includes('{limit}'));
        app.updateTokenBadge(tokens);
        assert.ok(nodes['token-badge'].title.includes(app.t('workspace.tokens_badge', { used: '2.7k', limit: '128k', pct: 2 })));
        assert.ok(nodes['token-badge'].title.includes(app.t('workspace.context_open')));
    }
});
