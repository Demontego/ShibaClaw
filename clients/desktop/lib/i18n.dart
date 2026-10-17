import 'dart:convert';

class LocaleSpec {
  const LocaleSpec(this.id, this.label, this.short);
  final String id;
  final String label;
  final String short;
}

const shibaLocales = <LocaleSpec>[
  LocaleSpec('en', 'English', 'EN'),
  LocaleSpec('zh-CN', '简体中文', '中文'),
  LocaleSpec('es', 'Español', 'ES'),
  LocaleSpec('pt-BR', 'Português (BR)', 'PT'),
  LocaleSpec('ja', '日本語', 'JA'),
  LocaleSpec('de', 'Deutsch', 'DE'),
  LocaleSpec('fr', 'Français', 'FR'),
  LocaleSpec('ru', 'Русский', 'RU'),
];

/// Parses `window.__I18N_CATALOGS__ = {...};` from the WebUI catalog file.
Map<String, Map<String, String>> parseCatalogs(String source) {
  final stripped = source.split('\n').where((line) => !line.trimLeft().startsWith('//')).join('\n').trim();
  var text = stripped;
  const prefix = 'window.__I18N_CATALOGS__ =';
  final at = text.indexOf(prefix);
  if (at >= 0) text = text.substring(at + prefix.length).trim();
  if (text.endsWith(';')) text = text.substring(0, text.length - 1).trim();
  final decoded = jsonDecode(text);
  if (decoded is! Map) return {};
  final out = <String, Map<String, String>>{};
  decoded.forEach((key, value) {
    if (value is! Map) return;
    out[key.toString()] = value.map((itemKey, itemValue) => MapEntry(itemKey.toString(), itemValue.toString()));
  });
  return out;
}

String? normalizeLocale(String? raw, Set<String> ids) {
  if (raw == null) return null;
  final text = raw.trim();
  if (text.isEmpty) return null;
  if (ids.contains(text)) return text;
  final lower = text.toLowerCase();
  if (lower == 'zh' || lower.startsWith('zh-')) return ids.contains('zh-CN') ? 'zh-CN' : null;
  if (lower == 'pt' || lower.startsWith('pt-')) return ids.contains('pt-BR') ? 'pt-BR' : null;
  final base = lower.split('-').first;
  for (final spec in shibaLocales) {
    final id = spec.id.toLowerCase();
    if ((id == lower || id.startsWith(base)) && ids.contains(spec.id)) return spec.id;
  }
  return null;
}

String translate(Map<String, Map<String, String>> catalogs, String locale, String key, [Map<String, Object>? vars]) {
  final local = catalogs[locale] ?? const {};
  final en = catalogs['en'] ?? const {};
  var text = local[key] ?? en[key] ?? key;
  vars?.forEach((name, value) {
    text = text.replaceAll('{$name}', value.toString());
  });
  return text;
}
