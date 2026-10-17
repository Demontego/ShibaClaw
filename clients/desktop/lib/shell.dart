import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'chat_page.dart';
import 'desk.dart';
import 'i18n.dart';
import 'plugins_page.dart';
import 'settings_page.dart';
import 'theme.dart';
import 'widgets.dart';
import 'workspace_pages.dart';

class Shell extends StatelessWidget {
  const Shell({super.key});

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final palette = paletteOf(context);
    final width = desk.sidebarOpen ? ShibaTokens.sidebarWidth : 72.0;
    return Row(
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          width: width,
          child: _Sidebar(compact: !desk.sidebarOpen),
        ),
        Expanded(
          child: Column(
            children: [
              if (desk.page != 'settings') _Header(palette: palette),
              if (desk.error.isNotEmpty)
                Container(
                  width: double.infinity,
                  color: palette.bgSurface,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  child: Row(
                    children: [
                      Expanded(child: Text(desk.error, style: TextStyle(color: palette.red, fontSize: 13))),
                      TextButton(onPressed: desk.clearError, child: Text(desk.t('common.close'))),
                    ],
                  ),
                ),
              Expanded(child: _body(desk.page)),
            ],
          ),
        ),
      ],
    );
  }

  Widget _body(String page) {
    return switch (page) {
      'agents' => const AgentsPage(),
      'automations' => const AutomationsPage(),
      'library' => const LibraryPage(),
      'plugins' => const PluginsPage(),
      'evolution' => const EvolutionPage(),
      'settings' => const SettingsPage(),
      _ => const ChatPage(),
    };
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.compact});
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final palette = paletteOf(context);
    return Glass(
      radius: 0,
      color: palette.bgSecondary,
      child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 14, 12, 6),
                child: Row(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(14),
                      child: Image.asset('assets/shibaclaw_logo.webp', width: 36, height: 36),
                    ),
                    if (!compact) ...[
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('ShibaClaw', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16, color: palette.textPrimary, height: 1.15)),
                            const SizedBox(height: 2),
                            Row(
                              children: [
                                if (desk.version.isNotEmpty)
                                  Text('v${desk.version}', style: TextStyle(fontSize: 11, color: palette.textSecondary)),
                                const SizedBox(width: 6),
                                Icon(Icons.circle, size: 6, color: desk.connected ? palette.green : palette.red),
                                const SizedBox(width: 4),
                                Flexible(
                                  child: Text(
                                    desk.connected ? desk.t('status.ready') : desk.t('status.connecting'),
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(fontSize: 11, color: palette.textSecondary),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                    SizedBox(
                      width: 34,
                      height: 34,
                      child: IconButton(
                        tooltip: desk.t('chrome.toggle_sidebar'),
                        padding: EdgeInsets.zero,
                        onPressed: desk.toggleSidebar,
                        icon: Icon(compact ? Icons.chevron_right : Icons.chevron_left, size: 18),
                        style: IconButton.styleFrom(
                          side: BorderSide(color: palette.border),
                          shape: const CircleBorder(),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 6, 16, 4),
                child: compact
                    ? IconButton(onPressed: () => desk.newChat(), icon: Icon(Icons.add, color: ShibaTokens.accent), tooltip: desk.t('workspace.new_chat'))
                    : SizedBox(
                        width: double.infinity,
                        height: ShibaTokens.newChatHeight,
                        child: OutlinedButton.icon(
                        onPressed: () => desk.newChat(),
                        icon: const Icon(Icons.add, color: ShibaTokens.accent),
                        label: Align(alignment: Alignment.centerLeft, child: Text(desk.t('workspace.new_chat'))),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: palette.textPrimary,
                          alignment: Alignment.centerLeft,
                          side: BorderSide(color: palette.border),
                          minimumSize: const Size(double.infinity, ShibaTokens.newChatHeight),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(ShibaTokens.newChatRadius)),
                        ),
                      ),
                      ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(10, 4, 10, 8),
                child: Row(
                  children: [
                    for (final item in _nav)
                      Expanded(
                        child: _NavButton(id: item.$1, icon: item.$2, label: desk.t(item.$3), compact: true, selected: desk.page == item.$1),
                      ),
                  ],
                ),
              ),
              if (!compact)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                  child: TextField(
                    onChanged: desk.onSearch,
                    style: TextStyle(color: palette.textPrimary, fontSize: 13),
                    decoration: InputDecoration(
                      isDense: true,
                      hintText: desk.t('nav.filter_sessions'),
                      prefixIcon: const Icon(Icons.search, size: 18),
                      contentPadding: const EdgeInsets.symmetric(vertical: 8),
                    ),
                  ),
                ),
              Expanded(child: compact ? const SizedBox.shrink() : const _SessionList()),
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 0, 8, 10),
                child: Row(
                  children: [
                    IconButton(
                      tooltip: desk.t('workspace.theme'),
                      onPressed: desk.cycleTheme,
                      icon: Icon(desk.themeMode == 'light' ? Icons.light_mode : desk.themeMode == 'dark' ? Icons.dark_mode : Icons.brightness_auto),
                    ),
                    if (!compact)
                      PopupMenuButton<String>(
                        tooltip: desk.t('footer.language'),
                        icon: const Icon(Icons.translate),
                        onSelected: desk.setLocale,
                        itemBuilder: (context) => [
                          for (final spec in shibaLocales)
                            PopupMenuItem(value: spec.id, child: Text('${spec.short}  ${spec.label}')),
                        ],
                      ),
                    const Spacer(),
                    IconButton(
                      tooltip: desk.t('workspace.settings'),
                      onPressed: () => desk.setPage('settings'),
                      icon: Icon(Icons.settings_outlined, color: desk.page == 'settings' ? ShibaTokens.accent : null),
                    ),
                    IconButton(tooltip: desk.t('footer.logout'), onPressed: desk.logout, icon: const Icon(Icons.logout)),
                    if (!compact) const _Clock(),
                  ],
                ),
              ),
            ],
      ),
    );
  }
}

const _nav = <(String, IconData, String)>[
  ('chat', Icons.chat_bubble_outline, 'workspace.conversations'),
  ('agents', Icons.pets_outlined, 'workspace.agents'),
  ('automations', Icons.schedule, 'workspace.automations'),
  ('library', Icons.folder_open, 'workspace.library'),
  ('plugins', Icons.extension_outlined, 'apps.nav_title'),
  ('evolution', Icons.auto_awesome, 'workspace.evolution'),
];

class _NavButton extends StatelessWidget {
  const _NavButton({required this.id, required this.icon, required this.label, required this.compact, required this.selected});

  final String id;
  final IconData icon;
  final String label;
  final bool compact;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final palette = paletteOf(context);
    final color = selected ? ShibaTokens.accent : palette.textSecondary;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 1),
      child: Material(
        color: selected ? palette.accentDim : Colors.transparent,
        borderRadius: BorderRadius.circular(ShibaTokens.navRadius),
        child: InkWell(
          borderRadius: BorderRadius.circular(ShibaTokens.navRadius),
          onTap: () => DeskScope.of(context).setPage(id),
          child: Tooltip(
            message: label,
            child: SizedBox(
            height: ShibaTokens.navItem,
            child: Row(
              mainAxisAlignment: compact ? MainAxisAlignment.center : MainAxisAlignment.start,
              children: [
                Icon(icon, color: color, size: 19),
                if (!compact) ...[
                  const SizedBox(width: 8),
                  Expanded(child: Text(label, overflow: TextOverflow.ellipsis, style: TextStyle(color: color, fontWeight: selected ? FontWeight.w600 : FontWeight.w400))),
                ],
              ],
            ),
          ),
          ),
        ),
      ),
    );
  }
}

class _SessionList extends StatelessWidget {
  const _SessionList();

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final palette = paletteOf(context);
    final rows = desk.visibleSessions;
    final groups = <String, List<Map<String, dynamic>>>{};
    for (final id in desk.profileLabels.keys) {
      groups[id] = [];
    }
    for (final session in rows) {
      final raw = session['profile_id']?.toString().trim() ?? '';
      final id = raw.isEmpty ? 'default' : raw;
      (groups[id] ??= []).add(session);
    }
    final ids = groups.keys.toList()
      ..sort((a, b) {
        if (a == 'default') return -1;
        if (b == 'default') return 1;
        return desk.profileLabel(a).compareTo(desk.profileLabel(b));
      });
    return ListView(
      padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
      children: [
        for (final hit in desk.hits)
          ListTile(
            dense: true,
            title: Text(hit['session_key']?.toString() ?? '', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)),
            subtitle: Text(hit['snippet']?.toString() ?? '', maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12, color: palette.textSecondary)),
            onTap: () => desk.openSession(hit['session_key']?.toString() ?? ''),
          ),
        if (!desk.sessionsLoaded)
          Padding(padding: const EdgeInsets.all(12), child: Text(desk.t('nav.loading'), style: TextStyle(color: palette.textSecondary, fontSize: 12))),
        for (final id in ids)
          if ((groups[id] ?? const []).isNotEmpty) ...[
            _ProfileHeader(id: id, count: groups[id]!.length, open: !desk.collapsedProfiles.contains(id)),
            if (!desk.collapsedProfiles.contains(id))
              for (final session in groups[id]!)
                _SessionTile(session: session, active: session['key'] == desk.sessionId),
          ],
      ],
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  const _ProfileHeader({required this.id, required this.count, required this.open});
  final String id;
  final int count;
  final bool open;

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final palette = paletteOf(context);
    return InkWell(
      borderRadius: BorderRadius.circular(12),
      onTap: () => desk.toggleProfile(id),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 6, 4, 6),
        child: Row(
          children: [
            dogAvatar(id),
            const SizedBox(width: 8),
            Expanded(child: Text(desk.profileLabel(id), maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 13, fontWeight: id == 'default' ? FontWeight.w600 : FontWeight.w500, color: palette.textPrimary))),
            Text('$count', style: TextStyle(fontSize: 11, color: palette.textSecondary)),
            IconButton(
              tooltip: desk.t('workspace.new_chat'),
              visualDensity: VisualDensity.compact,
              onPressed: () => desk.newChat(id),
              icon: Icon(Icons.add, size: 16, color: palette.textSecondary),
            ),
            Icon(open ? Icons.expand_more : Icons.chevron_right, size: 18, color: palette.textSecondary),
          ],
        ),
      ),
    );
  }
}

class _Clock extends StatefulWidget {
  const _Clock();

  @override
  State<_Clock> createState() => _ClockState();
}

class _ClockState extends State<_Clock> {
  late Timer _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _timer.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final now = TimeOfDay.now().format(context);
    return Padding(
      padding: const EdgeInsets.only(left: 4),
      child: Text(now, style: TextStyle(fontSize: 12, color: paletteOf(context).textSecondary)),
    );
  }
}

class _SessionTile extends StatelessWidget {
  const _SessionTile({required this.session, required this.active});
  final Map<String, dynamic> session;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final palette = paletteOf(context);
    final key = session['key']?.toString() ?? '';
    return Material(
      color: active ? palette.bgSurfaceHover : Colors.transparent,
      borderRadius: BorderRadius.circular(ShibaTokens.radiusSm),
      child: ListTile(
        dense: true,
        title: Text(sessionLabel(session), maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)),
        onTap: () => desk.openSession(key),
        trailing: PopupMenuButton<String>(
          icon: Icon(Icons.more_horiz, size: 18, color: palette.textSecondary),
          onSelected: (action) async {
            if (action == 'delete' && await confirm(context, desk.t('sessions.delete'), key)) {
              await desk.deleteSession(key);
            } else if (action == 'archive') {
              await desk.archiveSession(key);
            }
          },
          itemBuilder: (context) => [
            PopupMenuItem(value: 'archive', child: Text(desk.t('sessions.archive'))),
            PopupMenuItem(value: 'delete', child: Text(desk.t('sessions.delete'))),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.palette});
  final ShibaPalette palette;

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final title = desk.page == 'chat'
        ? (desk.sessionTitle.isEmpty ? desk.t('workspace.conversations') : desk.sessionTitle)
        : desk.t(_titleKey(desk.page));
    return SizedBox(
      height: ShibaTokens.headerHeight,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Row(
          children: [
            const SizedBox(width: 16),
            Expanded(
              child: desk.page == 'chat'
                  ? _TitleField(initial: title)
                  : Text(title, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: palette.textPrimary)),
            ),
            if (desk.page == 'chat')
              IconButton(
                tooltip: desk.t('chat.context'),
                onPressed: desk.loadContext,
                icon: const Icon(Icons.psychology_outlined),
              ),
            Icon(
              Icons.circle,
              size: 10,
              color: desk.connected ? palette.green : palette.red,
            ),
            const SizedBox(width: 8),
          ],
        ),
      ),
    );
  }
}

String _titleKey(String page) {
  return switch (page) {
    'agents' => 'workspace.agents',
    'automations' => 'workspace.automations',
    'library' => 'workspace.library',
    'plugins' => 'apps.nav_title',
    'evolution' => 'workspace.evolution',
    'settings' => 'workspace.settings',
    _ => 'workspace.conversations',
  };
}

class _TitleField extends StatefulWidget {
  const _TitleField({required this.initial});
  final String initial;

  @override
  State<_TitleField> createState() => _TitleFieldState();
}

class _TitleFieldState extends State<_TitleField> {
  late final TextEditingController _controller = TextEditingController(text: widget.initial);

  @override
  void didUpdateWidget(covariant _TitleField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initial != widget.initial && _controller.text != widget.initial) {
      _controller.text = widget.initial;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = paletteOf(context);
    return TextField(
      controller: _controller,
      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: palette.textPrimary),
      decoration: const InputDecoration(border: InputBorder.none, enabledBorder: InputBorder.none, focusedBorder: InputBorder.none, filled: false),
      onSubmitted: DeskScope.of(context).renameSession,
    );
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _base = TextEditingController();
  final _user = TextEditingController();
  final _pass = TextEditingController();
  String _error = '';
  bool _busy = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final desk = DeskScope.of(context);
    if (_base.text.isEmpty) _base.text = desk.baseUrl;
  }

  @override
  void dispose() {
    _base.dispose();
    _user.dispose();
    _pass.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final desk = DeskScope.of(context);
    setState(() {
      _busy = true;
      _error = '';
    });
    await desk.setBase(_base.text);
    final err = await desk.submitAuth(username: _user.text.trim(), password: _pass.text, setup: desk.needsSetup);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _error = err ?? '';
    });
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final palette = paletteOf(context);
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Glass(
          radius: ShibaTokens.radiusLg,
          padding: const EdgeInsets.all(24),
            child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Center(child: ClipRRect(borderRadius: BorderRadius.circular(20), child: Image.asset('assets/shibaclaw_logo.webp', width: 72, height: 72))),
              const SizedBox(height: 12),
              Text('ShibaClaw', textAlign: TextAlign.center, style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: palette.textPrimary)),
              const SizedBox(height: 6),
              Text(desk.needsSetup ? desk.t('login.setup_subtitle') : desk.t('login.subtitle'), textAlign: TextAlign.center, style: TextStyle(fontSize: 13, color: palette.textSecondary)),
              const SizedBox(height: 12),
              StatusText(_error.isEmpty ? desk.error : _error, error: true),
              if (!kIsWeb) ...[
                ShibaField(controller: _base, label: desk.t('settings.tab.gateway')),
                const SizedBox(height: 8),
              ],
              ShibaField(controller: _user, label: desk.t('login.username')),
              const SizedBox(height: 8),
              ShibaField(controller: _pass, label: desk.t('login.password'), obscure: true, onSubmit: (_) => _submit()),
              const SizedBox(height: 16),
              FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: palette.textPrimary,
                  foregroundColor: palette.bgPrimary,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(ShibaTokens.radiusSm)),
                ),
                onPressed: _busy ? null : _submit,
                child: Text(_busy ? desk.t('nav.loading') : (desk.needsSetup ? desk.t('login.setup_connect') : desk.t('login.connect'))),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
