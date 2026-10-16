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
