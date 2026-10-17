import 'dart:io';

Future<void> openExternalUrl(String url) async {
  if (Platform.isLinux) {
    await Process.run('xdg-open', [url]);
  } else if (Platform.isMacOS) {
    await Process.run('open', [url]);
  } else if (Platform.isWindows) {
    await Process.run('cmd', ['/c', 'start', '', url]);
  }
}
