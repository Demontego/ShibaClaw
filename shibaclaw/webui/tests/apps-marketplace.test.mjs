import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const frontend = path.resolve(import.meta.dirname, '../frontend/js');
const read = name => fs.readFileSync(path.join(frontend, name), 'utf8');

test('Updates shows only installed apps with a newer catalog version', async () => {
    const grid = { innerHTML: '' };
    const count = { textContent: '', className: '' };
    const wrap = {
        querySelector: selector => ({ '.apps-grid': grid, '.apps-count-updates': count })[selector] || null,
        querySelectorAll: () => [],
    };
    const document = {
        activeElement: null,
        addEventListener: () => {},
        querySelectorAll: selector => selector === '.apps-marketplace-wrap' ? [wrap] : [],
    };
    const context = { document, console, escapeHtml: value => String(value), t: key => key };
    context.window = context;
    let newerAvailable = false;
    context.authFetch = async () => ({
        json: async () => ({ apps: [
            { id: 'current', name: 'Current', description: '', category: 'development', capabilities: [], installed: true, update_available: false },
            { id: 'newer', name: 'Newer', description: '', category: 'development', capabilities: [], installed: true, update_available: newerAvailable },
            { id: 'uninstalled', name: 'Uninstalled', description: '', category: 'development', capabilities: [], installed: false, update_available: true },
        ] }),
    });
    vm.runInNewContext(read('plugins_panel.js'), context);
    await context.loadAppsMarketplace({ innerHTML: '', querySelector: () => null });

    context.switchAppsTab('updates');
    assert.match(grid.innerHTML, /apps\.no_updates/);
    assert.doesNotMatch(grid.innerHTML, /Current|Newer|Uninstalled/);
    assert.equal(count.textContent, 0);

    newerAvailable = true;
    await context.loadAppsMarketplace({ innerHTML: '', querySelector: () => null });
    context.switchAppsTab('updates');
    assert.match(grid.innerHTML, /Newer/);
    assert.doesNotMatch(grid.innerHTML, /Current|Uninstalled/);
    assert.equal(count.textContent, 1);

    context.filterAppsCategory('productivity');
    assert.match(grid.innerHTML, /apps\.empty/);
    context.filterAppsCategory('all');
    context.switchAppsTab('installed');
    assert.match(grid.innerHTML, /Current/);
    assert.doesNotMatch(grid.innerHTML, /Uninstalled/);
});

test('plugin interface translations cover every supported locale', () => {
    const context = {};
    context.window = context;
    vm.runInNewContext(read('i18n_catalogs.js'), context);
    const catalogs = context.__I18N_CATALOGS__;
    const keys = Object.keys(catalogs.en).filter(key => key.startsWith('apps.'));
    for (const [locale, catalog] of Object.entries(catalogs)) {
        for (const key of keys) {
            assert.ok(catalog[key], `${locale} is missing ${key}`);
        }
    }
    const sections = read('i18n_catalogs.js').split(/^  "(?:en|zh-CN|es|pt-BR|ja|de|fr|ru)": \{/m).slice(1);
    for (const section of sections) {
        const names = [...section.matchAll(/^    "(apps\.[^"]+)":/gm)].map(match => match[1]);
        assert.equal(new Set(names).size, names.length, 'plugin translation keys must not be duplicated');
    }
});
