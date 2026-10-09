import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFrontend } from './browser-fixture.mjs';

function fixture() {
    const events = () => ({ listeners: {}, addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); } });
    const element = () => ({ ...events(), attributes: {}, classes: new Set(), style: {},
        setAttribute(name, value) { this.attributes[name] = value; },
        classList: { toggle() {}, remove() {} }, contains() { return false; }, closest() { return null; } });
    const nodes = Object.fromEntries(['sidebar', 'sidebar-backdrop', 'notification-center', 'mobile-menu-btn', 'sidebar-toggle',
        'btn-new-session', 'btn-send', 'chat-input', 'btn-stop'].map(id => [id, element()]));
    nodes.sidebar.classList.toggle = (name, enabled) => enabled ? nodes.sidebar.classes.add(name) : nodes.sidebar.classes.delete(name);
    const controls = [nodes['mobile-menu-btn'], nodes['sidebar-toggle'], element()];
    const properties = new Map();
    const rootStyle = { setProperty: (name, value) => properties.set(name, value), removeProperty: name => properties.delete(name) };
    const document = { ...events(), documentElement: { style: rootStyle },
        getElementById: id => nodes[id] || null,
        querySelectorAll: selector => selector === '.mobile-menu-btn, .workspace-mobile-menu, .sidebar-toggle' ? controls : [] };
    const media = { ...events(), matches: true };
    const viewport = { ...events(), height: 667, offsetTop: 0, scale: 1 };
    nodes['chat-input'].scrollHeight = 600;
    const app = vm.createContext({ ...events(), document, visualViewport: viewport, matchMedia: () => media,
        $: id => nodes[id] || null, state: {}, chatInput: nodes['chat-input'], btnSend: nodes['btn-send'],
        getComputedStyle: () => ({ maxHeight: '84px' }), setTimeout: () => 1, clearTimeout() {}, clockTimer: null,
        console, navigator: {}, localStorage: { getItem: () => null } });
    app.window = app;
    vm.runInContext(readFrontend('js/chat.js'), app);
    vm.runInContext(readFrontend('js/main.js'), app);
    return { app, nodes, media, viewport, properties, controls };
}

test('keyboard viewport changes resize the visible mobile shell and cap multiline input', () => {
    const { app, viewport, properties, nodes } = fixture();
    app.initListeners();
    assert.equal(properties.get('--mobile-viewport-height'), '667px');
    assert.equal(nodes['chat-input'].style.height, '84px');
    viewport.height = 360;
    viewport.offsetTop = 12;
    viewport.listeners.resize.forEach(fn => fn());
    assert.equal(properties.get('--mobile-viewport-height'), '360px');
    assert.equal(properties.get('--mobile-viewport-top'), '12px');
    assert.equal(viewport.listeners.scroll.length, 1);
    app.initListeners();
    assert.equal(viewport.listeners.resize.length, 1, 'initialization must not duplicate viewport handlers');
});

test('pinch zoom and desktop resizing release the mobile viewport override', () => {
    const { app, viewport, media, properties } = fixture();
    app.syncMobileViewport();
    viewport.scale = 2;
    app.syncMobileViewport();
    assert.equal(properties.has('--mobile-viewport-height'), false);
    viewport.scale = 1;
    app.syncMobileViewport();
    media.matches = false;
    app.syncMobileViewport();
    assert.equal(properties.has('--mobile-viewport-height'), false);
    assert.equal(properties.has('--mobile-viewport-top'), false);
});

test('closed mobile navigation leaves the focus order and desktop navigation remains accessible', () => {
    const { app, nodes, media, controls } = fixture();
    app.setSidebarOpen(false);
    assert.equal(nodes.sidebar.inert, true);
    assert.equal(nodes.sidebar.attributes['aria-hidden'], 'true');
    app.setSidebarOpen(true);
    assert.equal(nodes.sidebar.inert, false);
    assert.ok(controls.every(button => button.attributes['aria-expanded'] === 'true'));
    app.closeSidebarOnMobile();
    assert.equal(nodes.sidebar.inert, true);
    assert.ok(controls.every(button => button.attributes['aria-expanded'] === 'false'));
    media.matches = false;
    app.setSidebarOpen(false);
    assert.equal(nodes.sidebar.inert, false);
    assert.equal(nodes.sidebar.attributes['aria-hidden'], 'false');
});
