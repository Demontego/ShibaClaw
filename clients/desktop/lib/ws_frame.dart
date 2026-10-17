import 'dart:convert';

/// One JSON frame from the WebUI `/ws` protocol in realtime.js.
class WsFrame {
  const WsFrame(this.type, this.raw);

  final String type;
  final Map<String, dynamic> raw;

  String get content => raw['content']?.toString() ?? '';
  String get id => raw['id']?.toString() ?? '';
  String get message => raw['message']?.toString() ?? '';
  String get sessionId => (raw['session_id'] ?? raw['session_key'] ?? '').toString();
  String get name => raw['name']?.toString() ?? '';
  bool get processing => raw['processing'] == true;

  Map<String, dynamic>? get payload {
    final value = raw['payload'];
    if (value is Map) return Map<String, dynamic>.from(value);
    return null;
  }
}

/// Returns null for empty input, invalid JSON, or a value that is not an object with `type`.
WsFrame? parseWsFrame(String raw) {
  final text = raw.trim();
  if (text.isEmpty) return null;
  Object? decoded;
  try {
    decoded = jsonDecode(text);
  } catch (_) {
    return null;
  }
  if (decoded is! Map) return null;
  final map = Map<String, dynamic>.from(decoded);
  final type = map['type']?.toString() ?? '';
  if (type.isEmpty) return null;
  return WsFrame(type, map);
}

String encodeWs(Map<String, dynamic> message) => jsonEncode(message);

Map<String, dynamic> authFrame({required String token, String sessionId = ''}) => {
      'type': 'auth',
      'token': token,
      'session_id': sessionId,
    };

Map<String, dynamic> pingFrame() => {'type': 'ping'};

Map<String, dynamic> chatFrame(
  String content, {
  List<Map<String, dynamic>> attachments = const [],
}) =>
    {
      'type': 'message',
      'content': content,
      'attachments': attachments,
    };
