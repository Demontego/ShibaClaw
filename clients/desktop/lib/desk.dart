import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'api.dart';
import 'i18n.dart';
import 'open_url_io.dart' if (dart.library.js_interop) 'open_url_web.dart';
import 'transcript.dart';
import 'ws_frame.dart';

class Desk extends ChangeNotifier {
  Desk({WebApi? api}) : api = api ?? WebApi();

  final WebApi api;
  SharedPreferences? _prefs;

  bool booted = false;
  bool authed = false;
  bool authRequired = true;
  bool needsSetup = false;
  bool connected = false;
  bool processing = false;
  String error = '';
  String baseUrl = defaultBaseUrl;
  String token = '';
  String themeMode = 'dark';
  String locale = 'en';
  String page = 'chat';
  bool sidebarOpen = true;

  Map<String, Map<String, String>> catalogs = {};
  bool sessionsLoaded = false;
  List<Map<String, dynamic>> sessions = [];
  Map<String, String> profileLabels = {'default': 'ShibaClaw'};
  final collapsedProfiles = <String>{};
  bool _seededCollapse = false;
  String version = '';
  int tokenUsed = 0;
  int tokenWindow = 0;
  int tokenPct = 0;
  List<Map<String, dynamic>> hits = [];
  String sessionQuery = '';
  String sessionId = '';
  String sessionTitle = '';
  String profileId = 'default';
  List<ChatItem> items = [];
  int transcriptEpoch = 0;
  List<Map<String, dynamic>> pending = [];

  bool resultOpen = false;
  String resultTitle = '';
  String resultBody = '';

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _sub;
  Timer? _ping;
  Timer? _reconnect;
  Timer? _searchTimer;
  int _gen = 0;
  int _loadGen = 0;
  int _searchGen = 0;
  bool _wantWs = false;
  int _delayMs = 1000;

  String t(String key, [Map<String, Object>? vars]) => translate(catalogs, locale, key, vars);

  Future<void> boot() async {
    _prefs = await SharedPreferences.getInstance();
    final saved = _prefs?.getString('shibaclaw_base');
    baseUrl = kIsWeb && (saved == null || saved == defaultBaseUrl) ? Uri.base.origin : (saved ?? defaultBaseUrl);
    token = _prefs?.getString('shibaclaw_token') ?? '';
    themeMode = _prefs?.getString('shibaclaw_theme') ?? 'dark';
    locale = _prefs?.getString('shibaclaw_locale') ?? 'en';
    sessionId = _prefs?.getString('shiba_session_id') ?? '';
    api.base = baseUrl;
    api.token = token;
    try {
      catalogs = parseCatalogs(await rootBundle.loadString('assets/i18n_catalogs.js'));
      final ids = catalogs.keys.toSet();
      locale = normalizeLocale(locale, ids) ?? 'en';
    } catch (err) {
      error = err.toString();
    }
    try {
      final status = await api.get('/api/auth/status');
      authRequired = status.map['auth_required'] == true;
      needsSetup = status.map['needs_setup'] == true;
      if (!authRequired) {
        authed = true;
      } else if (token.isNotEmpty) {
        final verified = await api.post('/api/auth/verify', {'token': token});
        authed = verified.map['valid'] == true;
        if (!authed) await _clearToken();
      }
    } catch (err) {
      error = err.toString();
    }
    booted = true;
    notifyListeners();
    if (authed) {
      await connectWs();
      await loadSessions();
      if (sessionId.isNotEmpty) await openSession(sessionId);
    }
  }

  Future<void> setBase(String value) async {
    baseUrl = value.trim().isEmpty ? defaultBaseUrl : value.trim();
    api.base = baseUrl;
    await _prefs?.setString('shibaclaw_base', baseUrl);
    notifyListeners();
  }

  Future<String?> submitAuth({required String username, required String password, required bool setup}) async {
    await setBase(baseUrl);
    final path = setup ? '/api/auth/setup' : '/api/auth/login';
    final res = await api.post(path, {'username': username, 'password': password});
    if (!res.ok) return res.error.isEmpty ? 'HTTP ${res.status}' : res.error;
    token = res.map['session_token']?.toString() ?? '';
    api.token = token;
    await _prefs?.setString('shibaclaw_token', token);
    authed = true;
    needsSetup = false;
    error = '';
    notifyListeners();
    await connectWs();
    await loadSessions();
    return null;
  }

  Future<void> logout() async {
    _wantWs = false;
    _reconnect?.cancel();
    await _closeWs();
    await _clearToken();
    authed = false;
    items = [];
    sessions = [];
    sessionId = '';
    notifyListeners();
  }

  Future<void> _clearToken() async {
    token = '';
    api.token = '';
    await _prefs?.remove('shibaclaw_token');
  }

  Future<void> setTheme(String mode) async {
    themeMode = mode;
    await _prefs?.setString('shibaclaw_theme', mode);
    notifyListeners();
  }

  Future<void> cycleTheme() {
    const order = ['dark', 'light', 'system'];
    final next = order[(order.indexOf(themeMode) + 1) % order.length];
    return setTheme(next);
  }

  Future<void> setLocale(String id) async {
    locale = id;
    await _prefs?.setString('shibaclaw_locale', id);
    notifyListeners();
  }

  void clearError() {
    error = '';
    notifyListeners();
  }

  void setPage(String next) {
    page = next;
    notifyListeners();
  }

  void toggleSidebar() {
    sidebarOpen = !sidebarOpen;
    notifyListeners();
  }

  Future<void> connectWs() async {
    _wantWs = true;
    _delayMs = 1000;
    await _openWs();
  }

  Future<void> _openWs() async {
    final gen = ++_gen;
    await _closeWs(keepGen: true);
    if (gen != _gen) return;
    final channel = WebSocketChannel.connect(wsUrl(baseUrl));
    _channel = channel;
    try {
      await channel.ready.timeout(const Duration(seconds: 8));
    } catch (err) {
      if (gen != _gen) return;
      error = err.toString();
      connected = false;
      notifyListeners();
      _scheduleReconnect();
      return;
    }
    if (gen != _gen) return;
    _sub = channel.stream.listen(
      (data) {
        final frame = parseWsFrame(data.toString());
        if (frame != null) _onFrame(frame);
      },
      onDone: () {
        if (gen != _gen || !_wantWs) return;
        connected = false;
        notifyListeners();
        _scheduleReconnect();
      },
      onError: (Object err) {
        if (gen != _gen) return;
        error = err.toString();
        notifyListeners();
      },
    );
    _send(authFrame(token: token, sessionId: sessionId));
  }

  void _scheduleReconnect() {
    if (!_wantWs || _reconnect != null) return;
    _reconnect = Timer(Duration(milliseconds: _delayMs), () {
      _reconnect = null;
      _delayMs = (_delayMs * 1.5).round().clamp(1000, 15000);
      _openWs();
    });
  }

  Future<void> _closeWs({bool keepGen = false}) async {
    if (!keepGen) _gen++;
    _ping?.cancel();
    _ping = null;
    await _sub?.cancel();
    _sub = null;
    try {
      await _channel?.sink.close();
    } catch (_) {}
    _channel = null;
  }

  void _send(Map<String, dynamic> message) {
    _channel?.sink.add(encodeWs(message));
  }

  void _startPing() {
    _ping?.cancel();
    _ping = Timer.periodic(const Duration(seconds: 25), (_) => _send(pingFrame()));
  }

  void _onFrame(WsFrame frame) {
    final type = frame.type;
    if (type == 'pong') return;
    if (type == 'connected') {
      connected = true;
      error = '';
      _delayMs = 1000;
      if (frame.sessionId.isNotEmpty) sessionId = frame.sessionId;
      if (frame.raw['profile_id'] != null) profileId = frame.raw['profile_id'].toString();
      _prefs?.setString('shiba_session_id', sessionId);
      _startPing();
    } else if (type == 'error') {
      error = frame.message.isEmpty ? frame.content : frame.message;
      if (error.toLowerCase().contains('unauthorized')) {
        logout();
        return;
      }
      items.add(ChatItem(role: 'error', text: error));
      processing = false;
      _finishStream();
    } else if (type == 'response_chunk') {
      processing = true;
      _streamBubble(frame.id).text += frame.content;
    } else if (type == 'response') {
      processing = false;
      final bubble = _streamBubble(frame.id);
      if (frame.content.isNotEmpty) bubble.text = frame.content;
      bubble.streaming = false;
      loadSessions();
    } else if (type == 'thinking' || type == 'tool') {
      processing = true;
      _insertStep(frame);
    } else if (type == 'interactive') {
      items.add(ChatItem(role: 'interactive', payload: frame.payload ?? frame.raw, id: frame.id));
    } else if (type == 'session_reset') {
      sessionId = frame.sessionId;
      profileId = frame.raw['profile_id']?.toString() ?? profileId;
      sessionTitle = '';
      items = [];
      transcriptEpoch++;
      processing = false;
      _prefs?.setString('shiba_session_id', sessionId);
      loadSessions();
    } else if (type == 'session_status') {
      if (frame.sessionId.isEmpty || frame.sessionId == sessionId) {
        processing = frame.processing;
        if (!processing) _finishStream();
      }
    } else if (type == 'event' && frame.name.isNotEmpty) {
      final payload = frame.payload;
      final text = payload?['content']?.toString() ?? payload?['message']?.toString() ?? '';
      if (text.isNotEmpty) items.add(ChatItem(role: 'step', text: frame.name, detail: text));
    }
    notifyListeners();
  }

  ChatItem _streamBubble(String id) {
    for (var i = items.length - 1; i >= 0; i--) {
      final item = items[i];
      if (item.role == 'assistant' && item.streaming && (id.isEmpty || item.id.isEmpty || item.id == id)) {
        if (item.id.isEmpty) item.id = id;
        return item;
      }
    }
    final created = ChatItem(role: 'assistant', id: id, streaming: true);
    items.add(created);
    return created;
  }

  void _finishStream() {
    for (final item in items) {
      if (item.streaming) item.streaming = false;
    }
  }

  void _insertStep(WsFrame frame) {
    final step = ChatItem(
      role: 'step',
      text: frame.content.isEmpty ? frame.type : frame.content,
      detail: frame.content,
      id: frame.id,
    );
    final index = items.lastIndexWhere((item) => item.role == 'assistant' && item.streaming);
    if (index >= 0) {
      items.insert(index, step);
    } else {
      items.add(step);
    }
    if (frame.type == 'tool') showResult(frame.type, frame.content);
  }

  Future<void> loadSessions() async {
    final res = await api.get('/api/sessions');
    if (!res.ok) {
      error = res.error;
      sessionsLoaded = true;
      notifyListeners();
      return;
    }
    sessions = asMaps(res.map['sessions']);
    final profiles = await api.get('/api/profiles');
    if (profiles.ok) {
      profileLabels = {'default': 'ShibaClaw'};
      for (final profile in asMaps(profiles.map['profiles'])) {
        final id = profile['id']?.toString() ?? '';
        if (id.isEmpty) continue;
        profileLabels[id] = (profile['label']?.toString() ?? '').isEmpty ? id : profile['label'].toString();
      }
    }
    final status = await api.get('/api/status');
    if (status.ok && status.map['version'] != null) version = status.map['version'].toString();
    if (!_seededCollapse) {
      collapsedProfiles.addAll(profileLabels.keys);
      for (final session in sessions) {
        final id = session['profile_id']?.toString().trim() ?? '';
        collapsedProfiles.add(id.isEmpty ? 'default' : id);
      }
      _seededCollapse = true;
    }
    sessionsLoaded = true;
    notifyListeners();
  }

  void toggleProfile(String id) {
    if (!collapsedProfiles.remove(id)) collapsedProfiles.add(id);
    notifyListeners();
  }

  String profileLabel(String id) => profileLabels[id] ?? (id == 'default' ? 'ShibaClaw' : id);

  void onSearch(String query) {
    sessionQuery = query;
    hits = [];
    notifyListeners();
    _searchTimer?.cancel();
    final q = query.trim();
    if (q.length < 2) return;
    final gen = ++_searchGen;
    _searchTimer = Timer(const Duration(milliseconds: 280), () async {
      final res = await api.get('/api/sessions/search?q=${Uri.encodeQueryComponent(q)}&limit=12');
      if (gen != _searchGen || !res.ok) return;
      hits = asMaps(res.map['hits']);
      notifyListeners();
    });
  }

  List<Map<String, dynamic>> get visibleSessions {
    final q = sessionQuery.trim().toLowerCase();
    if (q.isEmpty) return sessions;
    return sessions.where((session) {
      final hay = '${session['nickname'] ?? ''} ${session['key'] ?? ''}'.toLowerCase();
      return hay.contains(q);
    }).toList();
  }

  Future<void> openSession(String id) async {
    final gen = ++_loadGen;
    page = 'chat';
    sessionId = id;
    await _prefs?.setString('shiba_session_id', id);
    final res = await api.get('/api/sessions/${Uri.encodeComponent(id)}');
    if (gen != _loadGen) return;
    if (!res.ok) {
      error = res.error;
      notifyListeners();
      return;
    }
    sessionTitle = res.map['nickname']?.toString() ?? '';
    profileId = res.map['profile_id']?.toString() ?? 'default';
    items = parseTranscript(res.map['messages'] is List ? res.map['messages'] as List : const []);
    transcriptEpoch++;
    processing = false;
    notifyListeners();
    _send({'type': 'switch_session', 'session_id': id});
    await refreshTokens();
  }

  Future<void> refreshTokens() async {
    if (sessionId.isEmpty) {
      tokenUsed = 0;
      tokenWindow = 0;
      tokenPct = 0;
      notifyListeners();
      return;
    }
    final res = await api.get('/api/context?session_id=${Uri.encodeQueryComponent(sessionId)}&summary=1');
    if (!res.ok || res.map['tokens'] is! Map) return;
    final tokens = Map<String, dynamic>.from(res.map['tokens'] as Map);
    tokenUsed = (tokens['total'] as num?)?.round() ?? 0;
    tokenWindow = (tokens['context_window'] as num?)?.round() ?? 0;
    tokenPct = (tokens['usage_pct'] as num?)?.round() ?? 0;
    notifyListeners();
  }

  Future<void> newChat([String? nextProfile]) async {
    page = 'chat';
    items = [];
    sessionTitle = '';
    pending = [];
    transcriptEpoch++;
    processing = false;
    profileId = nextProfile ?? 'default';
    tokenUsed = 0;
    tokenWindow = 0;
    tokenPct = 0;
    notifyListeners();
    _send({'type': 'new_session', 'profile_id': profileId});
  }

  Future<void> renameSession(String nickname) async {
    if (sessionId.isEmpty) return;
    sessionTitle = nickname;
    notifyListeners();
    await api.patch('/api/sessions/${Uri.encodeComponent(sessionId)}', {'nickname': nickname});
    await loadSessions();
  }

  Future<void> deleteSession(String id) async {
    await api.delete('/api/sessions/${Uri.encodeComponent(id)}');
    if (sessionId == id) {
      sessionId = '';
      items = [];
      transcriptEpoch++;
    }
    await loadSessions();
  }

  Future<void> archiveSession(String id) async {
    await api.post('/api/sessions/${Uri.encodeComponent(id)}/archive');
    await loadSessions();
  }

  Future<void> attachFiles() async {
    final picked = await FilePicker.platform.pickFiles(allowMultiple: true);
    if (picked == null) return;
    for (final file in picked.files) {
      final path = file.path;
      if (path == null) continue;
      final res = await api.upload('/api/upload', path);
      if (!res.ok) {
        error = res.error;
        continue;
      }
      for (final saved in asMaps(res.map['files'])) {
        pending.add({
          'name': saved['filename'] ?? file.name,
          'url': saved['url'] ?? '',
          'type': 'file',
        });
      }
    }
    notifyListeners();
  }

  void removePending(int index) {
    if (index < 0 || index >= pending.length) return;
    pending.removeAt(index);
    notifyListeners();
  }

  void send(String text) {
    final content = text.trim();
    if (content.isEmpty && pending.isEmpty) return;
    if (!connected) {
      error = t('chat.gateway_offline');
      notifyListeners();
      return;
    }
    final attachments = pending.map((item) => Map<String, dynamic>.from(item)).toList();
    items.add(ChatItem(role: 'user', text: content));
    items.add(ChatItem(role: 'assistant', streaming: true));
    pending = [];
    processing = true;
    _send(chatFrame(content, attachments: attachments));
    notifyListeners();
  }

  void stop() {
    _send({'type': 'stop'});
    processing = false;
    _finishStream();
    notifyListeners();
  }

  void replyInteractive(String requestId, Object response) {
    _send({
      'type': 'interactive_reply',
      'request_id': requestId,
      'session_key': sessionId,
      'response': response,
    });
    items.removeWhere((item) => item.role == 'interactive' && (item.payload?['request_id']?.toString() == requestId));
    notifyListeners();
  }

  void showResult(String title, String body) {
    resultTitle = title;
    resultBody = body;
    resultOpen = true;
    notifyListeners();
  }

  void closeResult() {
    resultOpen = false;
    notifyListeners();
  }

  Future<void> loadContext() async {
    final path = sessionId.isEmpty ? '/api/context' : '/api/context?session_id=${Uri.encodeQueryComponent(sessionId)}';
    final res = await api.get(path);
    if (!res.ok) {
      error = res.error;
      notifyListeners();
      return;
    }
    final title = t('chat.result');
    showResult(title == 'chat.result' ? 'Result' : title, res.map['context']?.toString() ?? '');
  }

  Future<void> openExternal(String url) async {
    if (url.isEmpty) return;
    await openExternalUrl(url);
  }

  @override
  void dispose() {
    _wantWs = false;
    _reconnect?.cancel();
    _searchTimer?.cancel();
    _ping?.cancel();
    _sub?.cancel();
    _channel?.sink.close();
    api.close();
    super.dispose();
  }
}

class DeskScope extends InheritedNotifier<Desk> {
  const DeskScope({super.key, required Desk desk, required super.child}) : super(notifier: desk);

  static Desk of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<DeskScope>();
    assert(scope != null, 'DeskScope missing');
    return scope!.notifier!;
  }
}
