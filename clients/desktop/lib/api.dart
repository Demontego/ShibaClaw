import 'dart:convert';

import 'package:http/http.dart' as http;

const defaultBaseUrl = 'http://127.0.0.1:3000';

dynamic stripRedacted(dynamic data) {
  if (data is Map) {
    final out = <String, dynamic>{};
    data.forEach((key, value) {
      if (value == '***' || value == '****') return;
      out[key.toString()] = stripRedacted(value);
    });
    return out;
  }
  if (data is List) return data.map(stripRedacted).toList();
  return data;
}

List<Map<String, dynamic>> asMaps(dynamic raw) {
  if (raw is! List) return const [];
  return [
    for (final item in raw)
      if (item is Map) Map<String, dynamic>.from(item),
  ];
}

class ApiBody {
  const ApiBody(this.status, this.data);

  final int status;
  final dynamic data;

  bool get ok => status >= 200 && status < 300;

  Map<String, dynamic> get map => data is Map ? Map<String, dynamic>.from(data) : const {};

  String get error {
    if (data is Map && data['error'] != null) return data['error'].toString();
    if (!ok) return 'HTTP $status';
    return '';
  }
}

class WebApi {
  WebApi({this.base = defaultBaseUrl, this.token = ''});

  String base;
  String token;
  final http.Client client = http.Client();

  Uri uri(String path) {
    final root = base.endsWith('/') ? base.substring(0, base.length - 1) : base;
    return Uri.parse('$root$path');
  }

  Map<String, String> _headers({bool json = false}) => {
        if (token.isNotEmpty) 'Authorization': 'Bearer $token',
        if (json) 'Content-Type': 'application/json',
        'Accept': 'application/json, text/plain, */*',
      };

  Future<ApiBody> call(String method, String path, {Object? jsonBody}) async {
    final request = http.Request(method, uri(path));
    request.headers.addAll(_headers(json: jsonBody != null));
    if (jsonBody != null) request.body = jsonEncode(stripRedacted(jsonBody));
    final streamed = await client.send(request).timeout(const Duration(seconds: 45));
    final text = await streamed.stream.bytesToString();
    dynamic data = text;
    if (text.isNotEmpty) {
      try {
        data = jsonDecode(text);
      } catch (_) {
        data = text;
      }
    }
    return ApiBody(streamed.statusCode, data);
  }

  Future<ApiBody> get(String path) => call('GET', path);

  Future<ApiBody> post(String path, [Object? jsonBody]) => call('POST', path, jsonBody: jsonBody ?? const {});

  Future<ApiBody> put(String path, Object jsonBody) => call('PUT', path, jsonBody: jsonBody);

  Future<ApiBody> patch(String path, Object jsonBody) => call('PATCH', path, jsonBody: jsonBody);

  Future<ApiBody> delete(String path) => call('DELETE', path);

  Future<ApiBody> upload(String path, String filePath, {String field = 'file', Map<String, String> fields = const {}}) async {
    final request = http.MultipartRequest('POST', uri(path));
    if (token.isNotEmpty) request.headers['Authorization'] = 'Bearer $token';
    request.fields.addAll(fields);
    request.files.add(await http.MultipartFile.fromPath(field, filePath));
    final streamed = await client.send(request).timeout(const Duration(minutes: 2));
    final text = await streamed.stream.bytesToString();
    dynamic data = text;
    try {
      data = jsonDecode(text);
    } catch (_) {}
    return ApiBody(streamed.statusCode, data);
  }

  void close() => client.close();
}

Uri wsUrl(String base) {
  final parsed = Uri.parse(base.endsWith('/') ? base.substring(0, base.length - 1) : base);
  final scheme = parsed.scheme == 'https' ? 'wss' : 'ws';
  return parsed.replace(scheme: scheme, path: '/ws', query: '');
}
