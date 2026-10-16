import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFrontend } from './browser-fixture.mjs';

// Exercise the production event handlers, not CSS layout. Browser geometry is
// verified separately; these stubs supply computed sizes and viewport events.
function fixture({ mobile = true, viewportAvailable = true, touch = true, stored = {} } = {}) {
    function events() {
        return {
            listeners: new Map(),
            addEventListener(type, callback) {
                const callbacks = this.listeners.get(type) || [];
                callbacks.push(callback);
                this.listeners.set(type, callbacks);
            },
            dispatch(type, event = {}) {
                event.target ||= this;
                for (const callback of this.listeners.get(type) || []) callback(event);
                return event;
            },
        };
    }
    const document = { ...events(), activeElement: null };
    function element() {
        const classes = new Set();
        return {
            ...events(), attributes: {}, style: {}, parentNode: null,
            classList: {
                contains: name => classes.has(name),
                add: name => classes.add(name),
                remove: name => classes.delete(name),
                toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); },
            },
            setAttribute(name, value) { this.attributes[name] = String(value); },
            getClientRects() { return this.visible === false ? [] : [{}]; },
            focus() {
                for (let current = this; current; current = current.parentNode) {
                    if (current.inert) return;
                }
                document.activeElement = this;
            },
            contains(other) {
                for (let current = other; current; current = current.parentNode) {
                    if (current === this) return true;
                }
                return false;
            },
            closest() { return null; },
            querySelector() { return null; },
        };
    }
    const ids = ['sidebar', 'sidebar-backdrop', 'notification-center', 'mobile-menu-btn', 'sidebar-toggle',
        'workspace-sidebar-toggle', 'btn-new-session', 'btn-send', 'chat-input', 'btn-stop',
        'chat-area', 'workspace-view', 'settings-view'];
    const html = readFrontend('index.html');
    for (const id of ids) assert.ok(html.includes(`id="${id}"`), `Fixture control ${id} must exist in the real page`);
    const nodes = Object.fromEntries(ids.map(id => [id, element()]));
    const settingsMenu = element();
    settingsMenu.visible = false;
    const workspaceMenu = element();
    nodes['mobile-menu-btn'].parentNode = nodes['chat-area'];
    settingsMenu.parentNode = nodes['settings-view'];
    workspaceMenu.parentNode = nodes['workspace-view'];
    const sidebarItem = element();
    nodes['sidebar-toggle'].parentNode = nodes.sidebar;
    sidebarItem.parentNode = nodes.sidebar;
    const controls = [nodes['mobile-menu-btn'], nodes['sidebar-toggle'], nodes['workspace-sidebar-toggle'], settingsMenu, workspaceMenu];
    const properties = new Map();
    document.documentElement = { style: {
        setProperty: (name, value) => properties.set(name, value),
        removeProperty: name => properties.delete(name),
    } };
    const composer = { height: 182, getBoundingClientRect() { return { height: this.height }; } };
    document.getElementById = id => nodes[id] || null;
    document.querySelector = selector => selector === '.input-area' ? composer : selector === '.workspace-mobile-menu' ? settingsMenu : null;
    const views = [nodes['chat-area'], nodes['workspace-view'], nodes['settings-view']];
    document.querySelectorAll = selector => selector.includes('#mobile-menu-btn') ? controls
        : selector === '.workspace-mobile-menu' ? [settingsMenu, workspaceMenu]
        : selector === '#chat-area, #workspace-view, #settings-view' ? views : [];
    const media = { ...events(), matches: mobile };
    const viewport = { ...events(), height: 667, offsetTop: 0, scale: 1 };
    const sizing = { maxHeight: '160px' };
    const observers = [];
    const sends = [];
    const app = vm.createContext({
        ...events(), document, visualViewport: viewportAvailable ? viewport : undefined,
        innerHeight: 667, matchMedia: () => media,
        getComputedStyle: node => {
            assert.equal(node, nodes['chat-input']);
            return sizing;
        },
        ResizeObserver: class {
            constructor(callback) { this.callback = callback; observers.push(this); }
            observe(target) { this.target = target; }
        },
        $: id => nodes[id] || null,
        state: {}, chatInput: nodes['chat-input'], btnSend: nodes['btn-send'],
        navigator: { maxTouchPoints: touch ? 1 : 0 },
        localStorage: { getItem: key => stored[key] ?? null },
        setTimeout: () => 1, clearTimeout() {}, clockTimer: null, console,
    });
    app.window = app;
    nodes['chat-input'].value = '';
    nodes['chat-input'].scrollHeight = 600;
    vm.runInContext(readFrontend('js/chat.js'), app);
    // Isolate submission dispatch from rendering/network work; all key and click
    // handling, resizing and navigation behavior still use the production code.
    app.sendMessage = () => sends.push(nodes['chat-input'].value);
    vm.runInContext(readFrontend('js/main.js'), app);
    return { app, document, nodes, controls, views, settingsMenu, workspaceMenu, media, viewport, properties, sizing, composer, observers, sidebarItem, sends, stored };
}

test('textarea growth obeys computed mobile and desktop caps and shrinks after clearing', () => {
    const { app, nodes, sizing } = fixture();
    app.autoResizeInput();
    assert.equal(nodes['chat-input'].style.height, '160px');
    sizing.maxHeight = '84px';
    app.autoResizeInput();
    assert.equal(nodes['chat-input'].style.height, '84px');
    sizing.maxHeight = '200px';
    app.autoResizeInput();
    assert.equal(nodes['chat-input'].style.height, '200px');
    nodes['chat-input'].scrollHeight = 30;
    app.autoResizeInput();
    assert.equal(nodes['chat-input'].style.height, '30px');
});

test('keyboard and viewport scroll events update shell bounds and recalculate multiline input', () => {
    const { app, nodes, viewport, properties, sizing, composer, observers } = fixture();
    app.initListeners();
    assert.equal(properties.get('--mobile-viewport-height'), '667px');
    assert.equal(properties.get('--mobile-composer-height'), '182px');
    viewport.height = 360;
    viewport.offsetTop = 12;
    sizing.maxHeight = '84px';
    viewport.dispatch('resize');
    assert.equal(properties.get('--mobile-viewport-height'), '360px');
    assert.equal(properties.get('--mobile-viewport-offset-top'), '12px');
    assert.equal(nodes['chat-input'].style.height, '84px');
    viewport.offsetTop = 24;
    viewport.dispatch('scroll');
    assert.equal(properties.get('--mobile-viewport-offset-top'), '24px');
    assert.equal(observers.length, 1);
    assert.equal(observers[0].target, composer);
    composer.height = 210;
    observers[0].callback();
    assert.equal(properties.get('--mobile-composer-height'), '210px', 'wrapped controls must reposition dropdowns');
    app.initListeners();
    assert.equal(viewport.listeners.get('resize').length, 1);
    assert.equal(viewport.listeners.get('scroll').length, 1);
    assert.equal(observers.length, 1, 'reinitialization must not duplicate observers');
});

test('pinch zoom preserves layout bounds and desktop removes every mobile override', () => {
    const { app, viewport, media, properties, sizing, nodes } = fixture();
    app.initListeners();
    const beforeZoom = [...properties];
    viewport.scale = 2;
    viewport.height = 180;
    viewport.offsetTop = 90;
    viewport.dispatch('resize');
    assert.deepEqual([...properties], beforeZoom, 'zoom must not truncate the shell to a magnified viewport');
    viewport.scale = 1;
    viewport.height = 360;
    viewport.dispatch('resize');
    assert.equal(properties.get('--mobile-viewport-height'), '360px');
    media.matches = false;
    sizing.maxHeight = '200px';
    media.dispatch('change');
    assert.equal(properties.has('--mobile-viewport-height'), false);
    assert.equal(properties.has('--mobile-viewport-offset-top'), false);
    assert.equal(properties.has('--mobile-composer-height'), false);
    assert.equal(nodes['chat-input'].style.height, '200px');
});

test('mobile viewport falls back to the window when visualViewport is unavailable', () => {
    const { app, properties } = fixture({ viewportAvailable: false });
    app.initListeners();
    assert.equal(properties.get('--mobile-viewport-height'), '667px');
    assert.equal(properties.get('--mobile-viewport-offset-top'), '0px');
    app.innerHeight = 375;
    app.dispatch('resize');
    assert.equal(properties.get('--mobile-viewport-height'), '375px');
});

test('mobile sidebar exposes expanded state, focuses its close control and restores the trigger', () => {
    const { app, document, nodes, controls, views, sidebarItem } = fixture();
    app.initListeners();
    assert.equal(nodes.sidebar.inert, true);
    assert.equal(nodes.sidebar.attributes['aria-hidden'], 'true');
    assert.ok(controls.every(control => control.attributes['aria-expanded'] === 'false'));
    nodes['mobile-menu-btn'].focus();
    nodes['mobile-menu-btn'].dispatch('click');
    assert.equal(nodes.sidebar.inert, false);
    assert.equal(nodes.sidebar.attributes['aria-hidden'], 'false');
    assert.equal(document.activeElement, nodes['sidebar-toggle']);
    assert.equal(nodes['sidebar-backdrop'].classList.contains('active'), true);
    assert.ok(views.every(view => view.inert === true), 'the drawer must block focus in every background view');
    nodes['mobile-menu-btn'].focus();
    assert.equal(document.activeElement, nodes['sidebar-toggle'], 'background controls cannot steal drawer focus');
    assert.ok(controls.every(control => control.attributes['aria-controls'] === 'sidebar' && control.attributes['aria-expanded'] === 'true'));
    sidebarItem.focus();
    document.dispatch('keydown', { key: 'Escape' });
    assert.equal(document.activeElement, nodes['mobile-menu-btn']);
    assert.equal(nodes.sidebar.inert, true);
    assert.equal(nodes['sidebar-backdrop'].classList.contains('active'), false);
    assert.ok(views.every(view => view.inert === false), 'background inert state must clear before restoring focus');
});

test('sidebar close skips hidden chat and first page triggers after switching to workspace', () => {
    const { app, document, nodes, settingsMenu, workspaceMenu } = fixture();
    app.initListeners();
    nodes['mobile-menu-btn'].focus();
    app.setSidebarOpen(true);
    nodes['mobile-menu-btn'].visible = false;
    settingsMenu.visible = false;
    workspaceMenu.visible = true;
    assert.equal(document.querySelector('.workspace-mobile-menu'), settingsMenu,
        'the first matching trigger belongs to the hidden Settings page');
    app.setSidebarOpen(false);
    assert.equal(document.activeElement, workspaceMenu, 'focus must reach the second, visible page trigger');
    assert.equal(nodes.sidebar.inert, true);
});

test('breakpoint changes close the mobile overlay while preserving accessible desktop navigation', () => {
    const { app, nodes, media, controls, views } = fixture();
    app.initListeners();
    app.setSidebarOpen(true);
    media.matches = false;
    media.dispatch('change');
    assert.equal(nodes.sidebar.classList.contains('open'), false);
    assert.equal(nodes.sidebar.inert, false);
    assert.equal(nodes.sidebar.attributes['aria-hidden'], 'false');
    assert.ok(controls.every(control => control.attributes['aria-expanded'] === 'true'));
    assert.equal(nodes['sidebar-backdrop'].classList.contains('active'), false);
    assert.ok(views.every(view => view.inert === false));
    media.matches = true;
    media.dispatch('change');
    assert.equal(nodes.sidebar.inert, true);
    assert.equal(nodes.sidebar.attributes['aria-hidden'], 'true');
    assert.ok(controls.every(control => control.attributes['aria-expanded'] === 'false'));
});

test('composer retains send, Shift+Enter and the touch Enter preference', () => {
    const { app, nodes, sends, stored } = fixture();
    app.initListeners();
    nodes['chat-input'].value = 'hello';
    nodes['chat-input'].dispatch('input');
    assert.equal(nodes['btn-send'].disabled, false);
    const enter = shiftKey => ({ key: 'Enter', shiftKey, prevented: false, preventDefault() { this.prevented = true; } });
    const newline = enter(true);
    nodes['chat-input'].dispatch('keydown', newline);
    assert.equal(newline.prevented, false);
    assert.equal(sends.length, 0);
    const submit = enter(false);
    nodes['chat-input'].dispatch('keydown', submit);
    assert.equal(submit.prevented, true);
    assert.deepEqual(sends, ['hello']);
    stored.shibaclaw_mobile_enter_newline = 'true';
    const mobileNewline = enter(false);
    nodes['chat-input'].dispatch('keydown', mobileNewline);
    assert.equal(mobileNewline.prevented, false);
    assert.equal(sends.length, 1);
    nodes['btn-send'].dispatch('click');
    assert.deepEqual(sends, ['hello', 'hello'], 'explicit send remains available with Enter set to newline');
    app.navigator.maxTouchPoints = 0;
    const desktopSubmit = enter(false);
    nodes['chat-input'].dispatch('keydown', desktopSubmit);
    assert.equal(desktopSubmit.prevented, true);
    assert.equal(sends.length, 3, 'touch preference must not change desktop Enter');
});
