import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'desk.dart';
import 'plugins_page.dart';
import 'theme.dart';
import 'widgets.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  static const _sections = <(String, List<(String, IconData)>)>[
    ('settings.sec.ai', [('providers', Icons.key_outlined), ('oauth', Icons.lock_open)]),
    ('settings.sec.connectivity', [('channels', Icons.forum_outlined), ('gateway', Icons.dns_outlined)]),
    ('settings.sec.core', [('agent', Icons.pets_outlined), ('audio', Icons.mic_none)]),
    ('settings.sec.capabilities', [('extensions', Icons.extension_outlined)]),
    ('settings.sec.system', [('update', Icons.system_update_alt)]),
  ];

  String _tab = 'agent';
  String _ext = 'skills';
  bool _loading = true;
  String _error = '';
  String _note = '';
  Map<String, dynamic> _cfg = {};
  final _fields = <String, TextEditingController>{};
  List<Map<String, dynamic>> _oauth = [];
  Map<String, dynamic> _oauthJob = {};
  List<Map<String, dynamic>> _skills = [];
  List<String> _pinned = [];
  List<Map<String, dynamic>> _mcp = [];
  Map<String, dynamic> _update = {};
  final _mcpName = TextEditingController();
  final _mcpCommand = TextEditingController();
  final _mcpUrl = TextEditingController();
  final _oauthCode = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  TextEditingController _field(String key, String value) {
    final existing = _fields[key];
    if (existing != null) return existing;
    final created = TextEditingController(text: value);
    _fields[key] = created;
    return created;
  }

  void _set(String key, String value) {
    final existing = _fields[key];
    if (existing == null) {
      _fields[key] = TextEditingController(text: value);
    } else if (existing.text != value) {
      existing.text = value;
    }
  }

  Map<String, dynamic> get _defaults => _cfg['agents'] is Map && (_cfg['agents'] as Map)['defaults'] is Map
      ? Map<String, dynamic>.from((_cfg['agents'] as Map)['defaults'] as Map)
      : {};

  Future<void> _load() async {
    final res = await DeskScope.of(context).api.get('/api/settings');
    if (!mounted) return;
    setState(() {
      _loading = false;
      _error = res.ok ? '' : res.error;
      _cfg = res.map;
    });
    final d = _defaults;
    _set('model', d['model']?.toString() ?? '');
    _set('consolidationModel', d['consolidationModel']?.toString() ?? '');
    _set('temperature', '${d['temperature'] ?? 0.1}');
    _set('maxTokens', '${d['maxTokens'] ?? 8192}');
    _set('contextWindowTokens', '${d['contextWindowTokens'] ?? 65536}');
    _set('maxToolIterations', '${d['maxToolIterations'] ?? 40}');
    _set('toolTimeout', '${d['toolTimeout'] ?? 0}');
    _set('loopWallTimeout', '${d['loopWallTimeout'] ?? 0}');
    _set('subagentTimeout', '${d['subagentTimeout'] ?? 0}');
    _set('workspace', d['workspace']?.toString() ?? '');
    _set('reasoningEffort', d['reasoningEffort']?.toString() ?? '');
    final gw = _cfg['gateway'] is Map ? Map<String, dynamic>.from(_cfg['gateway'] as Map) : {};
    _set('gwHost', gw['host']?.toString() ?? '127.0.0.1');
    _set('gwPort', '${gw['port'] ?? 19999}');
    final audio = _cfg['audio'] is Map ? Map<String, dynamic>.from(_cfg['audio'] as Map) : {};
    _set('audioUrl', audio['providerUrl']?.toString() ?? '');
    _set('audioKey', audio['apiKey']?.toString() ?? '');
    _set('audioModel', audio['model']?.toString() ?? '');
    _set('ttsProvider', audio['ttsProvider']?.toString() ?? 'browser');
    _set('ttsVoice', audio['ttsVoice']?.toString() ?? '');
    _set('ttsLang', audio['ttsLang']?.toString() ?? 'en');
    _set('ttsSpeed', '${audio['ttsSpeed'] ?? 1.0}');
    _set('ttsEnabled', audio['ttsEnabled'] == true ? 'true' : 'false');
    if (_tab == 'oauth') await _loadOauth();
    if (_tab == 'extensions') await _loadExt();
    if (_tab == 'update') await _loadUpdate();
  }

  Future<void> _save(Map<String, dynamic> patch) async {
    final res = await DeskScope.of(context).api.post('/api/settings', stripRedacted(patch));
    if (!mounted) return;
    setState(() {
      _error = res.ok ? '' : res.error;
      _note = res.ok ? DeskScope.of(context).t('settings.saved') : '';
    });
    if (res.ok) await _load();
  }

  Future<void> _loadOauth() async {
    final res = await DeskScope.of(context).api.get('/api/oauth/providers');
    if (!mounted) return;
    setState(() => _oauth = asMaps(res.map['providers']));
  }

  Future<void> _loadExt() async {
    final desk = DeskScope.of(context);
    final skills = await desk.api.get('/api/skills?profile_id=${Uri.encodeQueryComponent(desk.profileId)}');
    final mcp = await desk.api.get('/api/mcp/servers');
    if (!mounted) return;
    setState(() {
      _skills = asMaps(skills.map['skills']);
      _pinned = [for (final name in (skills.map['pinned_skills'] as List? ?? const [])) name.toString()];
      _mcp = asMaps(mcp.map['servers']);
    });
  }

  Future<void> _loadUpdate() async {
    final res = await DeskScope.of(context).api.get('/api/update/check');
    if (!mounted) return;
    setState(() => _update = res.map);
  }

  @override
  void dispose() {
    for (final controller in _fields.values) {
      controller.dispose();
    }
    _mcpName.dispose();
    _mcpCommand.dispose();
    _mcpUrl.dispose();
    _oauthCode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final palette = paletteOf(context);
    if (_loading) return const Center(child: CircularProgressIndicator());
    final labelKey = 'settings.tab.${_tab == 'providers' ? 'provider' : _tab}';
    return Column(
      children: [
        SizedBox(
          height: ShibaTokens.settingsHeader,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 28),
            child: Row(
              children: [
                IconButton(tooltip: desk.t('settings.back_chat'), onPressed: () => desk.setPage('chat'), icon: const Icon(Icons.arrow_back, size: 20)),
                const SizedBox(width: 8),
                Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(desk.t('settings.title'), style: TextStyle(fontSize: 18, fontWeight: FontWeight.w500, color: palette.textPrimary)),
                    Text(desk.t(labelKey), style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: ShibaTokens.accent)),
                  ],
                ),
              ],
            ),
          ),
        ),
        Divider(height: 1, color: palette.border),
        Expanded(
          child: Row(
            children: [
              Container(
                width: ShibaTokens.settingsNav,
                decoration: BoxDecoration(border: Border(right: BorderSide(color: palette.border))),
                child: ListView(
                  padding: const EdgeInsets.only(bottom: 16),
                  children: [
                    for (final section in _sections) ...[
                      Padding(
                        padding: const EdgeInsets.fromLTRB(20, 20, 12, 6),
                        child: Text(desk.t(section.$1), style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, letterSpacing: 0.6, color: palette.textSecondary)),
                      ),
                      for (final item in section.$2) _navItem(desk, item.$1, item.$2),
                    ],
                  ],
                ),
              ),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.all(32),
                  children: [
                    Align(
                      alignment: Alignment.topLeft,
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: ShibaTokens.panelMax),
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            color: palette.bgSecondary,
                            borderRadius: BorderRadius.circular(ShibaTokens.radiusMd),
                            border: Border.all(color: palette.border),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.fromLTRB(32, 28, 32, 28),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                StatusText(_note),
                                StatusText(_error, error: _error.isNotEmpty),
                                _panel(desk, palette),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _navItem(Desk desk, String tab, IconData icon) {
    final on = _tab == tab;
    final palette = paletteOf(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
      child: Material(
        color: on ? palette.bgSurfaceHover : Colors.transparent,
        borderRadius: BorderRadius.circular(ShibaTokens.radiusSm),
        child: InkWell(
          borderRadius: BorderRadius.circular(ShibaTokens.radiusSm),
          onTap: () {
            setState(() => _tab = tab);
            if (tab == 'oauth') _loadOauth();
            if (tab == 'extensions') _loadExt();
            if (tab == 'update') _loadUpdate();
          },
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 9, 12, 9),
            child: Row(
              children: [
                Icon(icon, size: 16, color: on ? palette.textPrimary : palette.textSecondary),
                const SizedBox(width: 8),
                Expanded(child: Text(desk.t('settings.tab.${tab == 'providers' ? 'provider' : tab}'), style: TextStyle(fontSize: 12, color: on ? palette.textPrimary : palette.textSecondary))),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _panel(Desk desk, ShibaPalette palette) {
    return switch (_tab) {
      'providers' => _providers(desk),
      'oauth' => _oauthPane(desk),
      'channels' => _channels(desk),
      'gateway' => _gateway(desk),
      'audio' => _audio(desk),
      'extensions' => _extensions(desk),
      'update' => _updatePane(desk),
      _ => _agent(desk),
    };
  }

  Widget _agent(Desk desk) {
    return Column(
      children: [
        for (final key in ['model', 'consolidationModel', 'temperature', 'maxTokens', 'contextWindowTokens', 'maxToolIterations', 'toolTimeout', 'loopWallTimeout', 'subagentTimeout', 'workspace', 'reasoningEffort']) ...[
          ShibaField(controller: _field(key, ''), label: key),
          const SizedBox(height: 8),
        ],
        Align(
          alignment: Alignment.centerLeft,
          child: ShibaButton(
            label: desk.t('settings.save_changes'),
            onPressed: () {
              final defaults = <String, dynamic>{
                'model': _field('model', '').text.trim(),
                'consolidationModel': _emptyNull('consolidationModel'),
                'workspace': _field('workspace', '').text.trim(),
                'reasoningEffort': _emptyNull('reasoningEffort'),
              };
              void put(String key, num? value) {
                if (value != null) defaults[key] = value;
              }
              put('temperature', double.tryParse(_field('temperature', '').text.trim()));
              put('maxTokens', int.tryParse(_field('maxTokens', '').text.trim()));
              put('contextWindowTokens', int.tryParse(_field('contextWindowTokens', '').text.trim()));
              put('maxToolIterations', int.tryParse(_field('maxToolIterations', '').text.trim()));
              put('toolTimeout', int.tryParse(_field('toolTimeout', '').text.trim()));
              put('loopWallTimeout', int.tryParse(_field('loopWallTimeout', '').text.trim()));
              put('subagentTimeout', int.tryParse(_field('subagentTimeout', '').text.trim()));
              _save({'agents': {'defaults': defaults}});
            },
          ),
        ),
      ],
    );
  }

  String? _emptyNull(String key) {
    final text = _field(key, '').text.trim();
    return text.isEmpty ? null : text;
  }

  Widget _providers(Desk desk) {
    final providers = _cfg['providers'] is Map ? Map<String, dynamic>.from(_cfg['providers'] as Map) : {};
    return Column(
      children: [
        for (final entry in providers.entries)
          if (entry.value is Map) ...[
            Text(entry.key, style: const TextStyle(fontWeight: FontWeight.w600)),
            ShibaField(controller: _field('prov-key-${entry.key}', (entry.value as Map)['apiKey']?.toString() ?? ''), label: 'apiKey', obscure: true),
            const SizedBox(height: 6),
            ShibaField(controller: _field('prov-base-${entry.key}', (entry.value as Map)['apiBase']?.toString() ?? ''), label: 'apiBase'),
            const SizedBox(height: 12),
          ],
        Align(
          alignment: Alignment.centerLeft,
          child: ShibaButton(
            label: desk.t('settings.save_changes'),
            onPressed: () {
              final patch = <String, dynamic>{};
              for (final entry in providers.entries) {
                if (entry.value is! Map) continue;
                final key = _field('prov-key-${entry.key}', '').text.trim();
                final base = _field('prov-base-${entry.key}', '').text.trim();
                final item = <String, dynamic>{};
                if (key.isNotEmpty && key != '***' && key != '****') item['apiKey'] = key;
                final original = (entry.value as Map)['apiBase']?.toString() ?? '';
                if (base != original) item['apiBase'] = base.isEmpty ? null : base;
                if (item.isNotEmpty) patch[entry.key] = item;
              }
              _save({'providers': patch});
            },
          ),
        ),
      ],
    );
  }

  Widget _oauthPane(Desk desk) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final provider in _oauth)
          ListTile(
            title: Text(provider['label']?.toString() ?? provider['name']?.toString() ?? ''),
            subtitle: Text('${provider['status'] ?? ''} ${provider['message'] ?? ''}'),
            trailing: Wrap(
              spacing: 6,
              children: [
                ShibaButton(
                  label: desk.t('login.connect'),
                  filled: false,
                  onPressed: () async {
                    final res = await desk.api.post('/api/oauth/login', {'provider': provider['name']});
                    if (!mounted) return;
                    setState(() {
                      _oauthJob = res.map;
                      _error = res.ok ? '' : res.error;
                    });
                    final url = res.map['verification_uri']?.toString() ?? res.map['console_url']?.toString() ?? res.map['url']?.toString() ?? '';
                    if (url.isNotEmpty) await desk.openExternal(url);
                  },
                ),
                ShibaButton(
                  label: desk.t('footer.logout'),
                  filled: false,
                  onPressed: () async {
                    final res = await desk.api.post('/api/oauth/disconnect', {'provider': provider['name']});
                    if (!mounted) return;
                    setState(() => _error = res.ok ? '' : res.error);
                    await _loadOauth();
                  },
                ),
              ],
            ),
          ),
        if (_oauthJob.isNotEmpty) SelectableText(const JsonEncoder.withIndent('  ').convert(_oauthJob)),
        if (_oauthJob['user_code'] != null)
          Row(
            children: [
              SelectableText(_oauthJob['user_code'].toString(), style: const TextStyle(fontSize: 22, color: ShibaTokens.accent, fontWeight: FontWeight.w600)),
              IconButton(
                onPressed: () => Clipboard.setData(ClipboardData(text: _oauthJob['user_code'].toString())),
                icon: const Icon(Icons.copy),
              ),
            ],
          ),
        if (_oauthJob['job_id'] != null) ...[
          ShibaField(controller: _oauthCode, label: desk.t('login.password')),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: ShibaButton(
              label: desk.t('common.confirm'),
              onPressed: () async {
                final res = await desk.api.post('/api/oauth/code', {'job_id': _oauthJob['job_id'], 'code': _oauthCode.text.trim()});
                if (!mounted) return;
                setState(() => _error = res.ok ? '' : res.error);
                await _loadOauth();
              },
            ),
          ),
        ],
      ],
    );
  }

  Widget _channels(Desk desk) {
    final channels = _cfg['channels'] is Map ? Map<String, dynamic>.from(_cfg['channels'] as Map) : {};
    return Column(
      children: [
        for (final entry in channels.entries) ...[
          Text(entry.key, style: const TextStyle(fontWeight: FontWeight.w600)),
          if (entry.value is bool)
            SwitchListTile(
              title: Text(entry.key),
              value: _field('ch-${entry.key}', entry.value == true ? 'true' : 'false').text == 'true',
              activeThumbColor: ShibaTokens.accent,
              onChanged: (value) => setState(() => _field('ch-${entry.key}', '').text = value ? 'true' : 'false'),
            )
          else
            ShibaField(
              controller: _field('ch-${entry.key}', entry.value is Map ? const JsonEncoder.withIndent('  ').convert(entry.value) : entry.value.toString()),
              maxLines: 8,
            ),
          const SizedBox(height: 8),
        ],
        Align(
          alignment: Alignment.centerLeft,
          child: ShibaButton(
            label: desk.t('settings.save_changes'),
            onPressed: () {
              final patch = <String, dynamic>{};
              for (final entry in channels.entries) {
                final text = _field('ch-${entry.key}', '').text.trim();
                if (entry.value is bool) {
                  patch[entry.key] = text == 'true';
                } else if (entry.value is Map) {
                  try {
                    final decoded = jsonDecode(text);
                    if (decoded is Map) patch[entry.key] = stripRedacted(decoded);
                  } catch (err) {
                    setState(() => _error = err.toString());
                    return;
                  }
                }
              }
              _save({'channels': patch});
            },
          ),
        ),
      ],
    );
  }

  Widget _gateway(Desk desk) {
    return Column(
      children: [
        ShibaField(controller: _field('gwHost', ''), label: 'host'),
        const SizedBox(height: 8),
        ShibaField(controller: _field('gwPort', ''), label: 'port'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: [
            ShibaButton(
              label: desk.t('settings.save_changes'),
              onPressed: () {
                final gateway = <String, dynamic>{'host': _field('gwHost', '').text.trim()};
                final port = int.tryParse(_field('gwPort', '').text.trim());
                if (port != null) gateway['port'] = port;
                _save({'gateway': gateway});
              },
            ),
            ShibaButton(
              label: desk.t('settings.tab.gateway'),
              filled: false,
              onPressed: () async {
                final res = await desk.api.get('/api/gateway-health');
                if (!mounted) return;
                setState(() => _note = res.data.toString());
              },
            ),
            ShibaButton(
              label: desk.t('common.confirm'),
              filled: false,
              onPressed: () async {
                final res = await desk.api.post('/api/gateway-restart');
                if (!mounted) return;
                setState(() => _error = res.ok ? '' : res.error);
              },
            ),
          ],
        ),
      ],
    );
  }

  Widget _audio(Desk desk) {
    return Column(
      children: [
        for (final key in ['audioUrl', 'audioKey', 'audioModel', 'ttsProvider', 'ttsVoice', 'ttsLang', 'ttsSpeed']) ...[
          ShibaField(controller: _field(key, ''), label: key, obscure: key == 'audioKey'),
          const SizedBox(height: 8),
        ],
        SwitchListTile(
          title: Text(desk.t('settings.tab.audio')),
          value: _field('ttsEnabled', 'false').text == 'true',
          activeThumbColor: ShibaTokens.accent,
          onChanged: (value) => setState(() => _field('ttsEnabled', '').text = value ? 'true' : 'false'),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: ShibaButton(
            label: desk.t('settings.save_changes'),
            onPressed: () => _save({
              'audio': {
                'providerUrl': _emptyNull('audioUrl'),
                'apiKey': _emptyNull('audioKey'),
                'model': _field('audioModel', '').text.trim(),
                'ttsProvider': _field('ttsProvider', '').text.trim(),
                'ttsVoice': _field('ttsVoice', '').text.trim(),
                'ttsLang': _field('ttsLang', '').text.trim(),
                'ttsSpeed': double.tryParse(_field('ttsSpeed', '').text.trim()) ?? 1.0,
                'ttsEnabled': _field('ttsEnabled', '').text == 'true',
              },
            }),
          ),
        ),
      ],
    );
  }

  Widget _extensions(Desk desk) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'skills', label: Text('skills')),
            ButtonSegment(value: 'plugins', label: Text('plugins')),
            ButtonSegment(value: 'mcp', label: Text('MCP')),
          ],
          selected: {_ext},
          onSelectionChanged: (value) => setState(() => _ext = value.first),
        ),
        const SizedBox(height: 12),
        if (_ext == 'skills') _skillsPane(desk) else if (_ext == 'plugins') const PluginSettings() else _mcpPane(desk),
      ],
    );
  }

  Widget _skillsPane(Desk desk) {
    return Column(
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: ShibaButton(
            label: desk.t('apps.install'),
            filled: false,
            onPressed: () async {
              final picked = await FilePicker.platform.pickFiles();
              final path = picked?.files.single.path;
              if (path == null) return;
              final res = await desk.api.upload('/api/skills/import', path, fields: const {'conflict': 'overwrite'});
              if (!mounted) return;
              setState(() => _error = res.ok ? '' : res.error);
              await _loadExt();
            },
          ),
        ),
        for (final skill in _skills)
          CheckboxListTile(
            title: Text(skill['name']?.toString() ?? ''),
            subtitle: Text(skill['description']?.toString() ?? ''),
            value: _pinned.contains(skill['name']?.toString()),
            onChanged: (checked) async {
              final name = skill['name']?.toString() ?? '';
              final next = [..._pinned];
              if (checked == true) {
                if (!next.contains(name)) next.add(name);
              } else {
                next.remove(name);
              }
              final res = await desk.api.post('/api/skills/pin', {'pinned_skills': next, 'profile_id': desk.profileId});
              if (!mounted) return;
              setState(() => _error = res.ok ? '' : res.error);
              await _loadExt();
            },
            secondary: IconButton(
              onPressed: () async {
                final name = skill['name']?.toString() ?? '';
                if (!await confirm(context, desk.t('sessions.delete'), name)) return;
                await desk.api.delete('/api/skills/${Uri.encodeComponent(name)}');
                await _loadExt();
              },
              icon: const Icon(Icons.delete_outline),
            ),
          ),
      ],
    );
  }

  Widget _mcpPane(Desk desk) {
    return Column(
      children: [
        for (final server in _mcp)
          ListTile(
            title: Text(server['_name']?.toString() ?? ''),
            subtitle: Text(server['url']?.toString() ?? server['command']?.toString() ?? ''),
            trailing: Wrap(
              spacing: 4,
              children: [
                IconButton(
                  onPressed: () async {
                    final name = server['_name']?.toString() ?? '';
                    final res = await desk.api.post('/api/mcp/servers/${Uri.encodeComponent(name)}/test');
                    if (!mounted) return;
                    setState(() => _note = res.data.toString());
                  },
                  icon: const Icon(Icons.cable),
                ),
                IconButton(
                  onPressed: () async {
                    final name = server['_name']?.toString() ?? '';
                    if (!await confirm(context, desk.t('sessions.delete'), name)) return;
                    await desk.api.delete('/api/mcp/servers/${Uri.encodeComponent(name)}');
                    await _loadExt();
                  },
                  icon: const Icon(Icons.delete_outline),
                ),
              ],
            ),
          ),
        ShibaField(controller: _mcpName, label: 'name'),
        const SizedBox(height: 8),
        ShibaField(controller: _mcpCommand, label: 'command'),
        const SizedBox(height: 8),
        ShibaField(controller: _mcpUrl, label: 'url'),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerLeft,
          child: ShibaButton(
            label: desk.t('common.confirm'),
            onPressed: () async {
              final name = _mcpName.text.trim();
              if (name.isEmpty) return;
              final body = <String, dynamic>{};
              if (_mcpUrl.text.trim().isNotEmpty) body['url'] = _mcpUrl.text.trim();
              if (_mcpCommand.text.trim().isNotEmpty) {
                final parts = _mcpCommand.text.trim().split(RegExp(r'\s+'));
                body['command'] = parts.first;
                if (parts.length > 1) body['args'] = parts.sublist(1);
              }
              final res = await desk.api.put('/api/mcp/servers/${Uri.encodeComponent(name)}', body);
              if (!mounted) return;
              setState(() => _error = res.ok ? '' : res.error);
              if (res.ok) {
                _mcpName.clear();
                _mcpCommand.clear();
                _mcpUrl.clear();
                await _loadExt();
              }
            },
          ),
        ),
      ],
    );
  }

  Widget _updatePane(Desk desk) {
    final current = _update['display_current'] ?? _update['current'] ?? '';
    final latest = _update['display_latest'] ?? _update['latest'] ?? '';
    final summary = _update['summary']?.toString() ?? '';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('$current → $latest'),
        const SizedBox(height: 8),
        Text(summary),
        const SizedBox(height: 8),
        if (_update['release_notes'] != null) SelectableText(_update['release_notes'].toString()),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          children: [
            ShibaButton(label: desk.t('common.confirm'), filled: false, onPressed: _loadUpdate),
            if (_update['update_available'] == true)
              ShibaButton(
                label: desk.t('settings.tab.update'),
                onPressed: () async {
                  final res = await desk.api.post('/api/update/apply');
                  if (!mounted) return;
                  setState(() => _error = res.ok ? '' : res.error);
                },
              ),
          ],
        ),
      ],
    );
  }
}
