import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'desk.dart';
import 'theme.dart';
import 'widgets.dart';

class PluginsPage extends StatefulWidget {
  const PluginsPage({super.key});

  @override
  State<PluginsPage> createState() => _PluginsPageState();
}

class _PluginsPageState extends State<PluginsPage> {
  final _query = TextEditingController();
  final _custom = TextEditingController();
  List<Map<String, dynamic>> _apps = [];
  String _error = '';
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final res = await DeskScope.of(context).api.get('/api/apps');
    if (!mounted) return;
    setState(() {
      _loading = false;
      _error = res.ok ? '' : res.error;
      _apps = asMaps(res.map['apps']);
    });
  }

  Future<void> _act(String id, String action, [Object? body]) async {
    final res = await DeskScope.of(context).api.post('/api/apps/${Uri.encodeComponent(id)}/$action', body);
    if (!mounted) return;
    setState(() => _error = res.ok ? '' : res.error);
    if (res.map['auth_url'] != null) await DeskScope.of(context).openExternal(res.map['auth_url'].toString());
    await _load();
  }

  @override
  void dispose() {
    _query.dispose();
    _custom.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final q = _query.text.trim().toLowerCase();
    final apps = _apps.where((app) {
      if (q.isEmpty) return true;
      final hay = '${app['name']} ${app['id']} ${app['category']} ${app['description']}'.toLowerCase();
      return hay.contains(q);
    }).toList();
    if (_loading) return const Center(child: CircularProgressIndicator());
    return PageFrame(child: ListView(
      padding: const EdgeInsets.all(32),
      children: [
        TextField(controller: _query, onChanged: (_) => setState(() {}), decoration: InputDecoration(hintText: desk.t('apps.search_placeholder'))),
        const SizedBox(height: 8),
        StatusText(_error, error: true),
        if (apps.isEmpty) EmptyHint(desk.t('apps.empty')),
        for (final app in apps)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(app['name']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
                Text('${app['category'] ?? ''} · ${app['connected'] == true ? desk.t('apps.status.connected') : desk.t('apps.status.setup_required')}'),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    ShibaButton(label: desk.t('apps.install'), filled: false, onPressed: () => _act(app['id'].toString(), 'install')),
                    ShibaButton(label: desk.t('apps.configure'), filled: false, onPressed: () => _act(app['id'].toString(), 'connect', const {})),
                    ShibaButton(
                      label: app['enabled'] == true ? desk.t('apps.disable') : desk.t('apps.enable'),
                      filled: false,
                      onPressed: () => _act(app['id'].toString(), app['enabled'] == true ? 'disable' : 'enable'),
                    ),
                    ShibaButton(label: desk.t('apps.uninstall'), filled: false, onPressed: () => _act(app['id'].toString(), 'uninstall')),
                  ],
                ),
              ],
            ),
          ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: ShibaField(controller: _custom, hint: desk.t('apps.add_plugin'))),
            const SizedBox(width: 8),
            ShibaButton(
              label: desk.t('apps.add_plugin'),
              onPressed: () async {
                final res = await desk.api.post('/api/apps/custom', {'server_name': _custom.text.trim()});
                if (!mounted) return;
                setState(() => _error = res.ok ? '' : res.error);
                if (res.ok) {
                  _custom.clear();
                  await _load();
                }
              },
            ),
          ],
        ),
      ],
    ));
  }
}

class EvolutionPage extends StatefulWidget {
  const EvolutionPage({super.key});

  @override
  State<EvolutionPage> createState() => _EvolutionPageState();
}

class _EvolutionPageState extends State<EvolutionPage> {
  final _campaign = TextEditingController();
  final _model = TextEditingController();
  final _minutes = TextEditingController();
  Map<String, dynamic> _view = {};
  List<String> _mcps = [];
  String _error = '';
  bool _loading = true;
  bool _enabled = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final res = await DeskScope.of(context).api.get('/api/evolve');
    if (!mounted) return;
    final settings = res.map['settings'] is Map ? Map<String, dynamic>.from(res.map['settings'] as Map) : <String, dynamic>{};
    setState(() {
      _loading = false;
      _error = res.ok ? '' : res.error;
      _view = res.map;
      _enabled = res.map['enabled'] == true;
      _campaign.text = res.map['campaign']?.toString() ?? '';
      _model.text = settings['model']?.toString() ?? '';
      _minutes.text = settings['every_min']?.toString() ?? '';
      _mcps = [for (final item in (settings['mcps'] as List? ?? const [])) item.toString()];
    });
  }

  @override
  void dispose() {
    _campaign.dispose();
    _model.dispose();
    _minutes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final palette = paletteOf(context);
    if (_loading) return const Center(child: CircularProgressIndicator());
    final catalog = [for (final item in (_view['mcp_servers'] as List? ?? const [])) item.toString()];
    return PageFrame(child: ListView(
      padding: const EdgeInsets.all(32),
      children: [
        Text(_view['label']?.toString() ?? '', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: palette.textPrimary)),
        StatusText(_error, error: true),
        SwitchListTile(
          title: Text(desk.t('workspace.evolution')),
          value: _enabled,
          activeThumbColor: ShibaTokens.accent,
          onChanged: (value) async {
            final res = await desk.api.post('/api/evolve', {'enabled': value});
            if (!mounted) return;
            setState(() => _error = res.ok ? '' : res.error);
            if (res.ok) await _load();
          },
        ),
        ShibaField(controller: _minutes, label: 'every_min'),
        const SizedBox(height: 8),
        ShibaField(controller: _model, label: desk.t('settings.tab.agent')),
        const SizedBox(height: 8),
        ShibaField(controller: _campaign, label: desk.t('workspace.evolution'), maxLines: 6),
        const SizedBox(height: 8),
        for (final name in catalog)
          CheckboxListTile(
            title: Text(name),
            value: _mcps.contains(name),
            onChanged: (checked) {
              setState(() {
                if (checked == true) {
                  _mcps.add(name);
                } else {
                  _mcps.remove(name);
                }
              });
            },
          ),
        Align(
          alignment: Alignment.centerLeft,
          child: ShibaButton(
            label: desk.t('settings.save_changes'),
            onPressed: () async {
              final minutes = int.tryParse(_minutes.text.trim());
              final body = <String, dynamic>{
                'campaign': _campaign.text,
                'model': _model.text.trim(),
                'mcps': _mcps,
                'every_min': ?minutes,
              };
              final res = await desk.api.post('/api/evolve', body);
              if (!mounted) return;
              setState(() => _error = res.ok ? '' : res.error);
              if (res.ok) await _load();
            },
          ),
        ),
        const SizedBox(height: 16),
        SelectableText(_view['chronicle']?.toString() ?? '', style: TextStyle(color: palette.textSecondary, fontSize: 13)),
        const SizedBox(height: 8),
        SelectableText(_view['backlog']?.toString() ?? '', style: TextStyle(color: palette.textSecondary, fontSize: 13)),
      ],
    ));
  }
}

class PluginSettings extends StatefulWidget {
  const PluginSettings({super.key});

  @override
  State<PluginSettings> createState() => _PluginSettingsState();
}

class _PluginSettingsState extends State<PluginSettings> {
  final _package = TextEditingController();
  List<Map<String, dynamic>> _installed = [];
  List<Map<String, dynamic>> _available = [];
  String _error = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final res = await DeskScope.of(context).api.get('/api/plugins');
    if (!mounted) return;
    setState(() {
      _error = res.ok ? '' : res.error;
      _installed = asMaps(res.map['plugins']);
      _available = asMaps(res.map['available']);
    });
  }

  @override
  void dispose() {
    _package.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        StatusText(_error, error: true),
        for (final plugin in _installed)
          ListTile(
            title: Text(plugin['display_name']?.toString() ?? plugin['name']?.toString() ?? ''),
            subtitle: Text('${plugin['type'] ?? ''} · ${plugin['enabled'] == true ? desk.t('apps.enable') : desk.t('apps.disable')}'),
            trailing: IconButton(
              onPressed: () async {
                final name = plugin['name']?.toString() ?? '';
                final res = await desk.api.post('/api/plugins/uninstall', {'package': name});
                if (!mounted) return;
                setState(() => _error = res.ok ? '' : res.error);
                await _load();
              },
              icon: const Icon(Icons.delete_outline),
            ),
          ),
        for (final plugin in _available)
          ListTile(
            title: Text(plugin['display_name']?.toString() ?? ''),
            subtitle: Text(plugin['description']?.toString() ?? ''),
            trailing: ShibaButton(
              label: desk.t('apps.install'),
              filled: false,
              onPressed: () async {
                final res = await desk.api.post('/api/plugins/install', {'package': plugin['name']});
                if (!mounted) return;
                setState(() => _error = res.ok ? '' : res.error);
                await _load();
              },
            ),
          ),
        Row(
          children: [
            Expanded(child: ShibaField(controller: _package, hint: 'shibaclaw-…')),
            IconButton(
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: _package.text));
              },
              icon: const Icon(Icons.copy),
            ),
            ShibaButton(
              label: desk.t('apps.install'),
              onPressed: () async {
                final res = await desk.api.post('/api/plugins/install', {'package': _package.text.trim()});
                if (!mounted) return;
                setState(() => _error = res.ok ? '' : res.error);
                await _load();
              },
            ),
          ],
        ),
      ],
    );
  }
}
