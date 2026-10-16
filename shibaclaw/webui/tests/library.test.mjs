import test from 'node:test';
import assert from 'node:assert/strict';
import { browserFixture, profileResponse, settle } from './browser-fixture.mjs';

for (const eol of ['\n', '\r\n']) {
    test(`library edit/save preserves frontmatter with ${JSON.stringify(eol)} endings`, async () => {
        const { context: app, nodes, requests } = browserFixture();
        const front = ['---', 'name: Test User', 'role: owner', '---', ''].join(eol);
        const source = front + ['# User', '', '## Preferences', '', 'Original text', ''].join(eol);
        app.openLibraryYou();
        requests[0].resolve({ ok: true, text: async () => source });
        await settle();
        const sheet = nodes['library-sheet'];
        const edit = sheet.querySelector('.library-edit');
        assert.ok(edit);
        edit.dispatchEvent({ type: 'click' });
        const body = sheet.querySelector('[data-role=body]');
        assert.equal(body.value, 'Original text');
        body.value = 'Updated text';
        edit.dispatchEvent({ type: 'click' });
        const save = requests[1];
        assert.equal(save.url, '/api/file-save');
        const payload = JSON.parse(save.options.body);
        assert.equal(payload.path, 'USER.md');
        assert.ok(payload.content.startsWith(front), 'frontmatter must be retained verbatim');
        assert.match(payload.content, /# User\s+## Preferences\s+Updated text/);
        assert.equal(payload.content.match(/role: owner/g).length, 1);
        save.resolve({ ok: true });
        await settle();
        assert.equal(sheet.querySelector('.library-editor-status').textContent, 'Saved');
        assert.ok(!sheet.querySelector('[data-role=body]'));
    });
}

test('library graph and personal tabs dismiss existing panels and profile nodes open the right detail', async () => {
    const { context: app, document, nodes, requests } = browserFixture();
    await app.openModal('knowledge-modal');
    app.openWorkspaceLibrary();
    requests[0].resolve(profileResponse([{ id: 'default' }, { id: 'research' }]));
    await settle();
    const profiles = [
        { id: 'default', label: 'Owner', soul: '## Goal\n\nCoordinate' },
        { id: 'research', label: 'Researcher', soul: '## Goal\n\nResearch', pinned_skills: ['web'] },
    ];
    requests[1].resolve({ ok: true, json: async () => profiles[0] });
    requests[2].resolve({ ok: true, json: async () => profiles[1] });
    await settle();
    assert.equal(nodes['knowledge-modal'].classList.contains('active'), false);
    assert.equal(nodes['workspace-agent-graph'].hidden, false);
    assert.equal(nodes['workspace-library-book'].hidden, true);
    const buttons = nodes['agent-graph-nodes'].querySelectorAll('.agent-node');
    assert.equal(buttons.length, 3);
    assert.ok(nodes['agent-graph-svg'].children.length >= 3);
    assert.ok(buttons.every(button => /^\d+(\.\d+)?px$/.test(button.style.left)));
    buttons.find(button => button.dataset.id === 'research').dispatchEvent({ type: 'click' });
    assert.match(nodes['agent-graph-detail'].textContent, /Researcher/);
    assert.equal(document.querySelectorAll('.agent-node.is-on').length, 1);
    app.openLibraryYou();
    requests[3].resolve({ ok: true, text: async () => '# User\n\nNotes' });
    await settle();
    assert.equal(nodes['workspace-agent-graph'].hidden, true);
    assert.equal(nodes['workspace-library-book'].hidden, false);
    assert.equal(nodes['library-tab-you'].getAttribute('aria-current'), 'page');
});

test('failed document reads expose an error without offering an empty overwrite', async () => {
    const { context: app, nodes, requests } = browserFixture();
    app.openLibraryYou();
    requests[0].resolve({ ok: false, status: 404 });
    await settle();
    assert.match(nodes['library-sheet'].textContent, /Unable to load/);
    assert.equal(nodes['library-sheet'].querySelector('.library-edit'), null);
    assert.equal(requests.length, 1);
});

test('an obsolete graph response cannot replace personal documents', async () => {
    const { context: app, nodes, requests } = browserFixture();
    app.openWorkspaceLibrary();
    app.openLibraryYou();
    requests[1].resolve({ ok: true, text: async () => '# Current user\n\nNotes' });
    await settle();
    requests[0].resolve(profileResponse([{ id: 'obsolete' }]));
    await settle();
    assert.equal(requests.length, 2, 'obsolete lists must not trigger detail requests');
    assert.equal(nodes['workspace-agent-graph'].hidden, true);
    assert.match(nodes['library-sheet'].textContent, /Current user/);
});

test('People lists existing documents, filters names and retains edits on save failure', async () => {
    const { context: app, nodes, requests } = browserFixture();
    app.openLibraryPeople();
    requests[0].resolve({ ok: true, json: async () => ({ items: [
        { name: 'README.md', path: 'memory/people/README.md' },
        { name: '12_Alex.md', path: 'memory/people/12_Alex.md' },
        { name: '13_Sam.md', path: 'memory/people/13_Sam.md' },
    ] }) });
    await settle();
    const buttons = nodes['library-people'].querySelectorAll('.library-rail-item');
    assert.equal(buttons.length, 2);
    // The real DOM click method is represented by dispatchEvent in this fixture.
    requests[1].resolve({ ok: true, text: async () => '## Preferences\n\nOriginal' });
    await settle();
    nodes['library-people-search'].value = 'alex';
    nodes['library-people-search'].dispatchEvent({ type: 'input' });
    assert.equal(buttons[0].hidden, false);
    assert.equal(buttons[1].hidden, true);
    const sheet = nodes['library-sheet'];
    const edit = sheet.querySelector('.library-edit');
    edit.dispatchEvent({ type: 'click' });
    sheet.querySelector('[data-role=body]').value = 'Unsaved';
    edit.dispatchEvent({ type: 'click' });
    assert.equal(JSON.parse(requests[2].options.body).path, 'memory/people/12_Alex.md');
    requests[2].resolve({ ok: false, status: 403 });
    await settle();
    assert.equal(sheet.querySelector('[data-role=body]').value, 'Unsaved');
    assert.equal(sheet.querySelector('.library-editor-status').textContent, 'Error');
});

test('profile detail failures cannot save a fabricated empty soul', async () => {
    const { context: app, nodes, requests } = browserFixture();
    app.openWorkspaceLibrary();
    requests[0].resolve(profileResponse([{ id: 'default', label: '<Owner>' }]));
    await settle();
    requests[1].resolve({ ok: false, status: 403 });
    await settle();
    assert.match(nodes['agent-graph-detail'].textContent, /Unable to load/);
    assert.equal(nodes['agent-graph-detail'].querySelector('.library-edit'), null);
});
