import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'desk.dart';
import 'theme.dart';
import 'widgets.dart';

class AgentsPage extends StatefulWidget {
  const AgentsPage({super.key});

  @override
  State<AgentsPage> createState() => _AgentsPageState();
}

class _AgentsPageState extends State<AgentsPage> {
  final _id = TextEditingController();
  final _label = TextEditingController();
  final _description = TextEditingController();
  final _soul = TextEditingController();
  List<Map<String, dynamic>> _profiles = [];
  String _error = '';
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final res = await DeskScope.of(context).api.get('/api/profiles');
    if (!mounted) return;
    setState(() {
      _loading = false;
      _error = res.ok ? '' : res.error;
      _profiles = asMaps(res.map['profiles']);
    });
  }

  Future<void> _create() async {
    final desk = DeskScope.of(context);
    final res = await desk.api.post('/api/profiles', {
      'id': _id.text.trim(),
      'label': _label.text.trim(),
      'description': _description.text.trim(),
      'soul': _soul.text,
    });
    if (!mounted) return;
    if (!res.ok) {
      setState(() => _error = res.error);
      return;
    }
    _id.clear();
    _label.clear();
    _description.clear();
    _soul.clear();
    await _load();
  }

  @override
  void dispose() {
    _id.dispose();
    _label.dispose();
    _description.dispose();
    _soul.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    if (_loading) return const Center(child: CircularProgressIndicator());
    return PageFrame(child: ListView(
      padding: const EdgeInsets.all(32),
      children: [
        StatusText(_error, error: true),
        for (final profile in _profiles)
          ListTile(
            title: Text(profile['label']?.toString() ?? profile['id']?.toString() ?? ''),
            subtitle: Text(profile['description']?.toString() ?? profile['id']?.toString() ?? ''),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  tooltip: desk.t('workspace.new_chat'),
                  onPressed: () => desk.newChat(profile['id']?.toString()),
                  icon: const Icon(Icons.add_comment_outlined),
                ),
                IconButton(
                  onPressed: () async {
                    final id = profile['id']?.toString() ?? '';
                    if (id.isEmpty || !await confirm(context, desk.t('sessions.delete'), id)) return;
                    await desk.api.delete('/api/profiles/${Uri.encodeComponent(id)}');
                    await _load();
                  },
                  icon: Icon(Icons.delete_outline, color: paletteOf(context).red),
                ),
              ],
            ),
          ),
        const SizedBox(height: 12),
        ShibaField(controller: _id, label: 'id'),
        const SizedBox(height: 8),
        ShibaField(controller: _label, label: desk.t('workspace.agents')),
        const SizedBox(height: 8),
        ShibaField(controller: _description, label: desk.t('workspace.agents_subtitle')),
        const SizedBox(height: 8),
        ShibaField(controller: _soul, label: 'SOUL', maxLines: 6),
        const SizedBox(height: 8),
        Align(alignment: Alignment.centerLeft, child: ShibaButton(label: desk.t('common.confirm'), onPressed: _create)),
      ],
    ));
  }
}

class AutomationsPage extends StatefulWidget {
  const AutomationsPage({super.key});

  @override
  State<AutomationsPage> createState() => _AutomationsPageState();
}

class _AutomationsPageState extends State<AutomationsPage> {
  final _name = TextEditingController();
  final _cron = TextEditingController(text: '0 9 * * *');
  final _message = TextEditingController();
  List<Map<String, dynamic>> _jobs = [];
  String _status = '';
  String _error = '';
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final api = DeskScope.of(context).api;
    final status = await api.get('/api/automation/status');
    final jobs = await api.get('/api/automation/jobs');
    if (!mounted) return;
    setState(() {
      _loading = false;
      _error = jobs.ok ? '' : jobs.error;
      _status = status.ok ? (status.map['reachable'] == false ? 'gateway_unreachable' : 'ok') : status.error;
      _jobs = asMaps(jobs.map['jobs']);
    });
  }

  Future<void> _create() async {
    final res = await DeskScope.of(context).api.post('/api/automation/jobs', {
      'name': _name.text.trim(),
      'enabled': true,
      'deleteAfterRun': false,
      'schedule': {'kind': 'cron', 'expr': _cron.text.trim(), 'tz': null},
      'payload': {
        'kind': 'scheduled',
        'message': _message.text,
        'deliver': false,
        'channel': null,
        'to': null,
        'targets': {},
      },
    });
    if (!mounted) return;
    if (!res.ok) {
      setState(() => _error = res.error);
      return;
    }
    _name.clear();
    _message.clear();
    await _load();
  }

  @override
  void dispose() {
    _name.dispose();
    _cron.dispose();
    _message.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    if (_loading) return const Center(child: CircularProgressIndicator());
    return PageFrame(child: ListView(
      padding: const EdgeInsets.all(32),
      children: [
        StatusText(_status),
        StatusText(_error, error: true),
        for (final job in _jobs)
          ListTile(
            title: Text(job['name']?.toString() ?? job['id']?.toString() ?? ''),
            subtitle: Text(job['schedule'] is Map ? jsonEncode(job['schedule']) : ''),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Switch(
                  value: job['enabled'] == true,
                  activeThumbColor: ShibaTokens.accent,
                  onChanged: (value) async {
                    await desk.api.patch('/api/automation/jobs/${Uri.encodeComponent(job['id'].toString())}', {'enabled': value});
                    await _load();
                  },
                ),
                IconButton(
                  onPressed: () async {
                    await desk.api.post('/api/automation/jobs/${Uri.encodeComponent(job['id'].toString())}/trigger');
                    await _load();
                  },
                  icon: const Icon(Icons.play_arrow),
                ),
                IconButton(
                  onPressed: () async {
                    final id = job['id'].toString();
                    if (!await confirm(context, desk.t('sessions.delete'), id)) return;
                    await desk.api.delete('/api/automation/jobs/${Uri.encodeComponent(id)}');
                    await _load();
                  },
                  icon: Icon(Icons.delete_outline, color: paletteOf(context).red),
                ),
              ],
            ),
          ),
        const SizedBox(height: 12),
        ShibaField(controller: _name, label: desk.t('workspace.automations')),
        const SizedBox(height: 8),
        ShibaField(controller: _cron, label: 'cron'),
        const SizedBox(height: 8),
        ShibaField(controller: _message, label: desk.t('chat.send'), maxLines: 3),
        const SizedBox(height: 8),
        Align(alignment: Alignment.centerLeft, child: ShibaButton(label: desk.t('common.confirm'), onPressed: _create)),
      ],
    ));
  }
}

class LibraryPage extends StatefulWidget {
  const LibraryPage({super.key});

  @override
  State<LibraryPage> createState() => _LibraryPageState();
}

class _LibraryPageState extends State<LibraryPage> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
          child: SegmentedButton<int>(
            segments: [
              ButtonSegment(value: 0, label: Text(desk.t('chat.collections'))),
              ButtonSegment(value: 1, label: Text(desk.t('workspace.library'))),
              ButtonSegment(value: 2, label: Text(desk.t('memory.title'))),
            ],
            selected: {_tab},
            onSelectionChanged: (value) => setState(() => _tab = value.first),
          ),
        ),
        Expanded(
          child: switch (_tab) {
            1 => const _FilesPane(),
            2 => const _MemoryPane(),
            _ => const _KnowledgePane(),
          },
        ),
      ],
    );
  }
}

class _KnowledgePane extends StatefulWidget {
  const _KnowledgePane();

  @override
  State<_KnowledgePane> createState() => _KnowledgePaneState();
}

class _KnowledgePaneState extends State<_KnowledgePane> {
  final _id = TextEditingController();
  final _name = TextEditingController();
  final _description = TextEditingController();
  List<Map<String, dynamic>> _items = [];
  String _error = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final res = await DeskScope.of(context).api.get('/api/knowledge');
    if (!mounted) return;
    setState(() {
      _error = res.ok ? '' : res.error;
      _items = asMaps(res.map['collections']);
    });
  }

  @override
  void dispose() {
    _id.dispose();
    _name.dispose();
    _description.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    return PageFrame(child: ListView(
      padding: const EdgeInsets.all(32),
      children: [
        StatusText(_error, error: true),
        for (final item in _items)
          ListTile(
            title: Text(item['name']?.toString() ?? item['id']?.toString() ?? ''),
            subtitle: Text(item['description']?.toString() ?? ''),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  onPressed: () async {
                    final id = item['id']?.toString() ?? '';
                    final picked = await FilePicker.platform.pickFiles();
                    final path = picked?.files.single.path;
                    if (path == null || id.isEmpty) return;
                    final res = await desk.api.upload('/api/knowledge/${Uri.encodeComponent(id)}/upload', path);
                    if (!mounted) return;
                    setState(() => _error = res.ok ? '' : res.error);
                  },
                  icon: const Icon(Icons.upload_file),
                ),
                IconButton(
                  onPressed: () async {
                    final id = item['id']?.toString() ?? '';
                    if (!await confirm(context, desk.t('sessions.delete'), id)) return;
                    await desk.api.delete('/api/knowledge/${Uri.encodeComponent(id)}');
                    await _load();
                  },
                  icon: Icon(Icons.delete_outline, color: paletteOf(context).red),
                ),
              ],
            ),
          ),
        ShibaField(controller: _id, label: 'id'),
        const SizedBox(height: 8),
        ShibaField(controller: _name, label: desk.t('chat.collections')),
        const SizedBox(height: 8),
        ShibaField(controller: _description, maxLines: 2),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerLeft,
          child: ShibaButton(
            label: desk.t('common.confirm'),
            onPressed: () async {
              final res = await desk.api.post('/api/knowledge', {
                'id': _id.text.trim(),
                'name': _name.text.trim(),
                'description': _description.text.trim(),
              });
              if (!res.ok) {
                setState(() => _error = res.error);
                return;
              }
              _id.clear();
              _name.clear();
              _description.clear();
              await _load();
            },
          ),
        ),
      ],
    ));
  }
}

class _FilesPane extends StatefulWidget {
  const _FilesPane();

  @override
  State<_FilesPane> createState() => _FilesPaneState();
}

class _FilesPaneState extends State<_FilesPane> {
  String _path = '.';
  String? _parent;
  List<Map<String, dynamic>> _items = [];
  String _error = '';
  final _editor = TextEditingController();
  String _openPath = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load('.'));
  }

  Future<void> _load(String path) async {
    final res = await DeskScope.of(context).api.get('/api/fs/explore?path=${Uri.encodeQueryComponent(path)}');
    if (!mounted) return;
    setState(() {
      _error = res.ok ? '' : res.error;
      _path = res.map['current_path']?.toString() ?? path;
      _parent = res.map['parent_path']?.toString();
      _items = asMaps(res.map['items']);
    });
  }

  Future<void> _open(String path) async {
    final res = await DeskScope.of(context).api.get('/api/file-get?path=${Uri.encodeQueryComponent(path)}');
    if (!mounted) return;
    setState(() {
      _openPath = path;
      _editor.text = res.data?.toString() ?? '';
      _error = res.ok ? '' : res.error;
    });
  }

  @override
  void dispose() {
    _editor.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    return Row(
      children: [
        SizedBox(
          width: 320,
          child: ListView(
            children: [
              ListTile(title: Text(_path), subtitle: _parent == null ? null : Text(_parent!), onTap: _parent == null ? null : () => _load(_parent!)),
              StatusText(_error, error: true),
              for (final item in _items)
                ListTile(
                  leading: Icon(item['is_dir'] == true ? Icons.folder : Icons.description_outlined),
                  title: Text(item['name']?.toString() ?? ''),
                  onTap: () {
                    final path = item['path']?.toString() ?? '';
                    if (item['is_dir'] == true) {
                      _load(path);
                    } else {
                      _open(path);
                    }
                  },
                ),
            ],
          ),
        ),
        const VerticalDivider(width: 1),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              children: [
                Expanded(child: ShibaField(controller: _editor, expands: true)),
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerRight,
                  child: ShibaButton(
                    label: desk.t('settings.save_changes'),
                    onPressed: _openPath.isEmpty
                        ? null
                        : () async {
                            final res = await desk.api.post('/api/file-save', {'path': _openPath, 'content': _editor.text});
                            if (!mounted) return;
                            setState(() => _error = res.ok ? '' : res.error);
                          },
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _MemoryPane extends StatefulWidget {
  const _MemoryPane();

  @override
  State<_MemoryPane> createState() => _MemoryPaneState();
}

class _MemoryPaneState extends State<_MemoryPane> {
  final _body = TextEditingController();
  final _needle = TextEditingController();
  String _file = 'MEMORY.md';
  String _error = '';
  String _note = '';
  Map<String, dynamic> _data = {};

  static const _files = ['MEMORY.md', 'USER.md', 'HISTORY.md', 'DREAM_DIARY.md'];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  String _keyFor(String file) {
    return switch (file) {
      'USER.md' => 'user',
      'HISTORY.md' => 'history',
      'DREAM_DIARY.md' => 'diary',
      _ => 'memory',
    };
  }

  Future<void> _load() async {
    final res = await DeskScope.of(context).api.get('/api/memory');
    if (!mounted) return;
    setState(() {
      _error = res.ok ? '' : res.error;
      _data = res.map;
      _body.text = res.map[_keyFor(_file)]?.toString() ?? '';
      final tokens = res.map['tokens'];
      _note = tokens == null ? '' : '$tokens / ${res.map['max_tokens']}';
    });
  }

  @override
  void dispose() {
    _body.dispose();
    _needle.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          StatusText(_error, error: true),
          StatusText(_note),
          Wrap(
            spacing: 6,
            children: [
              for (final file in _files)
                ChoiceChip(
                  label: Text(file),
                  selected: _file == file,
                  onSelected: (_) {
                    setState(() {
                      _file = file;
                      _body.text = _data[_keyFor(file)]?.toString() ?? '';
                    });
                  },
                ),
            ],
          ),
          const SizedBox(height: 8),
          Expanded(child: ShibaField(controller: _body, maxLines: 40)),
          const SizedBox(height: 8),
          Row(
            children: [
              ShibaButton(
                label: desk.t('settings.save_changes'),
                onPressed: () async {
                  final res = await desk.api.post('/api/memory/save', {'file': _file, 'content': _body.text});
                  if (!mounted) return;
                  setState(() => _error = res.ok ? '' : res.error);
                  if (res.ok) await _load();
                },
              ),
              const SizedBox(width: 8),
              Expanded(child: ShibaField(controller: _needle, hint: desk.t('memory.title'))),
              const SizedBox(width: 8),
              ShibaButton(
                label: desk.t('common.confirm'),
                filled: false,
                onPressed: () async {
                  final host = context;
                  final preview = await desk.api.post('/api/memory/forget', {'needle': _needle.text.trim(), 'confirm': false});
                  if (!host.mounted) return;
                  if (!preview.ok) {
                    setState(() => _error = preview.error);
                    return;
                  }
                  final ok = await confirm(host, desk.t('memory.title'), preview.map.toString());
                  if (!host.mounted || !ok) return;
                  final done = await desk.api.post('/api/memory/forget', {'needle': _needle.text.trim(), 'confirm': true});
                  if (!mounted) return;
                  setState(() => _error = done.ok ? '' : done.error);
                  if (done.ok) await _load();
                },
              ),
            ],
          ),
        ],
      ),
    );
  }
}
