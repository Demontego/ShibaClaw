class ChatItem {
  ChatItem({
    required this.role,
    this.text = '',
    this.id = '',
    this.streaming = false,
    this.detail = '',
    this.payload,
  });

  final String role;
  String text;
  String id;
  bool streaming;
  String detail;
  Map<String, dynamic>? payload;
}

/// Turns a session `messages` array into rows the chat column can paint.
List<ChatItem> parseTranscript(List<dynamic> messages) {
  final out = <ChatItem>[];
  String? lastUser;
  for (final raw in messages) {
    if (raw is! Map) continue;
    final msg = Map<String, dynamic>.from(raw);
    final role = msg['role']?.toString() ?? '';
    if (role == 'user') {
      final meta = msg['metadata'];
      if (meta is Map && meta['hidden'] == true) continue;
      final content = msg['content']?.toString() ?? '';
      if (content.isEmpty || content == lastUser) continue;
      lastUser = content;
      out.add(ChatItem(role: 'user', text: content));
      continue;
    }
    if (role == 'tool') {
      final content = msg['content']?.toString() ?? '';
      final name = msg['name']?.toString() ?? 'tool';
      out.add(ChatItem(role: 'step', text: name, detail: content));
      continue;
    }
    if (role != 'assistant') continue;
    final reasoning = msg['reasoning_content']?.toString() ?? '';
    if (reasoning.isNotEmpty) {
      final preview = reasoning.length > 160 ? reasoning.substring(0, 160) : reasoning;
      out.add(ChatItem(role: 'step', text: preview, detail: reasoning));
    }
    final calls = msg['tool_calls'];
    if (calls is List) {
      for (final call in calls) {
        if (call is! Map) continue;
        final fnMap = call['function'];
        final name = fnMap is Map ? (fnMap['name']?.toString() ?? 'tool') : 'tool';
        if (name == 'message') continue;
        final args = fnMap is Map ? (fnMap['arguments']?.toString() ?? '') : '';
        out.add(ChatItem(role: 'step', text: name, detail: args.isEmpty ? name : '$name\n$args'));
      }
    }
    final content = msg['content']?.toString() ?? '';
    if (content.isNotEmpty) out.add(ChatItem(role: 'assistant', text: content));
  }
  return out;
}
