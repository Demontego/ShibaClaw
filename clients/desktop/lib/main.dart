import 'package:flutter/material.dart';

import 'desk.dart';
import 'shell.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final desk = Desk();
  runApp(DeskScope(desk: desk, child: const ShibaApp()));
  await desk.boot();
}

class ShibaApp extends StatelessWidget {
  const ShibaApp({super.key});

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final platformDark = MediaQuery.platformBrightnessOf(context) == Brightness.dark;
    final light = desk.themeMode == 'light' || (desk.themeMode == 'system' && !platformDark);
    final palette = light ? ShibaPalette.lightPalette : ShibaPalette.darkPalette;
    return MaterialApp(
      title: 'ShibaClaw',
      debugShowCheckedModeBanner: false,
      theme: buildShibaTheme(palette),
      builder: (context, child) => DefaultTextStyle.merge(
        style: const TextStyle(decoration: TextDecoration.none),
        child: child ?? const SizedBox.shrink(),
      ),
      home: LiquidBackground(
        palette: palette,
        child: !desk.booted
            ? const Center(child: CircularProgressIndicator(color: ShibaTokens.accent))
            : desk.authed
                ? const Shell()
                : const LoginPage(),
      ),
    );
  }
}
