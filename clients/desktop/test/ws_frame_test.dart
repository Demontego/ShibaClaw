import 'package:flutter_test/flutter_test.dart';
import 'package:shibaclaw_desktop/api.dart';
import 'package:shibaclaw_desktop/history_window.dart';
import 'package:shibaclaw_desktop/i18n.dart';
import 'package:shibaclaw_desktop/transcript.dart';
import 'package:shibaclaw_desktop/ws_frame.dart';

void main() {
  test('parses /ws frames the WebUI client sends and receives', () {
    final auth = authFrame(token: 'tok', sessionId: 'webui:abc');
    expect(encodeWs(auth), contains('"type":"auth"'));
    expect(parseWsFrame(encodeWs(pingFrame()))?.type, 'ping');

    final connected = parseWsFrame('{"type":"connected","session_id":"webui:1","profile_id":"default"}');
    expect(connected?.type, 'connected');
    expect(connected?.sessionId, 'webui:1');

    final chunk = parseWsFrame('{"type":"response_chunk","id":"m1","content":"hi","session_key":"webui:1"}');
    expect(chunk?.type, 'response_chunk');
    expect(chunk?.content, 'hi');
    expect(chunk?.id, 'm1');

    final response = parseWsFrame('{"type":"response","id":"m1","content":"done","finish_reason":"stop"}');
    expect(response?.content, 'done');

    expect(parseWsFrame('{"type":"pong"}')?.type, 'pong');
    expect(parseWsFrame('{"type":"thinking","content":"look"}')?.content, 'look');
    expect(parseWsFrame('{"type":"tool","content":"exec"}')?.type, 'tool');
    expect(parseWsFrame('not json'), isNull);
    expect(parseWsFrame(''), isNull);
    expect(parseWsFrame('[]'), isNull);
    expect(parseWsFrame('{"content":"no type"}'), isNull);

    final event = parseWsFrame('{"type":"event","name":"agent","payload":{"content":"step"}}');
    expect(event?.name, 'agent');
    expect(event?.payload?['content'], 'step');
  });

  test('history opens on the latest page and grows upward', () {
    final window = HistoryWindow(100);
    expect(window.renderedFrom, 70);
    expect(window.hasOlder, isTrue);
    window.prependOlder();
    expect(window.renderedFrom, 40);
    window.prependOlder();
    expect(window.renderedFrom, 10);
    window.prependOlder();
    expect(window.renderedFrom, 0);
    expect(window.hasOlder, isFalse);
    window.prependOlder();
    expect(window.renderedFrom, 0);
    expect(HistoryWindow(10).renderedFrom, 0);
    expect(HistoryWindow(30).renderedFrom, 0);
  });

  test('transcript skips hidden and duplicate user rows', () {
    final rows = parseTranscript([
      {'role': 'user', 'content': 'hello'},
      {'role': 'user', 'content': 'hello'},
      {'role': 'user', 'content': 'secret', 'metadata': {'hidden': true}},
      {
        'role': 'assistant',
        'reasoning_content': 'think',
        'tool_calls': [
          {'function': {'name': 'exec', 'arguments': '{"cmd":"ls"}'}},
          {'function': {'name': 'message', 'arguments': '{}'}},
        ],
        'content': 'done',
      },
      {'role': 'tool', 'name': 'exec', 'content': 'file.txt'},
    ]);
    expect(rows.map((row) => row.role).toList(), ['user', 'step', 'step', 'assistant', 'step']);
    expect(rows.first.text, 'hello');
    expect(rows[1].text, 'think');
    expect(rows[2].text, 'exec');
    expect(rows[3].text, 'done');
    expect(rows[4].detail, 'file.txt');
  });

  test('catalog parser and redacted settings filter', () {
    final catalogs = parseCatalogs('// Auto-generated\nwindow.__I18N_CATALOGS__ = {"en":{"workspace.agents":"Agents"},"ru":{"workspace.agents":"Агенты"}};');
    expect(translate(catalogs, 'ru', 'workspace.agents'), 'Агенты');
    expect(translate(catalogs, 'ru', 'missing'), 'missing');
    expect(normalizeLocale('pt', catalogs.keys.toSet()), isNull);
    expect(normalizeLocale('ru', catalogs.keys.toSet()), 'ru');
    expect(normalizeLocale('zh-Hans', {'zh-CN'}), 'zh-CN');
    expect(stripRedacted({'apiKey': '***', 'apiBase': 'http://x', 'nested': {'token': '****'}}), {'apiBase': 'http://x', 'nested': {}});
  });
}
