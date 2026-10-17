import 'dart:ui';

import 'package:flutter/material.dart';

/// Tokens from shibaclaw/webui/frontend/css/workspace.css (.workspace-ui).
class ShibaTokens {
  static const accent = Color(0xFFF27A2E);
  static const accentLight = Color(0xFFF6A15A);
  static const sidebarWidth = 248.0;
  static const headerHeight = 56.0;
  static const chatWidth = 780.0;
  static const welcomeMax = 660.0;
  static const panelMax = 800.0;
  static const settingsNav = 190.0;
  static const settingsHeader = 64.0;
  static const navItem = 34.0;
  static const navRadius = 11.0;
  static const newChatHeight = 40.0;
  static const newChatRadius = 14.0;
  static const hintHeight = 82.0;
  static const hintRadius = 20.0;
  static const composerRadius = 28.0;
  static const radiusSm = 8.0;
  static const radiusMd = 12.0;
  static const radiusLg = 18.0;
  static const glassBlur = 28.0;
}

class ShibaPalette {
  const ShibaPalette({
    required this.light,
    required this.bgPrimary,
    required this.bgSecondary,
    required this.bgSurface,
    required this.bgSurfaceHover,
    required this.textPrimary,
    required this.textSecondary,
    required this.textCode,
    required this.border,
    required this.borderHighlight,
    required this.accentDim,
    required this.green,
    required this.red,
    required this.blue,
    required this.purple,
    required this.liquid,
  });

  final bool light;
  final Color bgPrimary;
  final Color bgSecondary;
  final Color bgSurface;
  final Color bgSurfaceHover;
  final Color textPrimary;
  final Color textSecondary;
  final Color textCode;
  final Color border;
  final Color borderHighlight;
  final Color accentDim;
  final Color green;
  final Color red;
  final Color blue;
  final Color purple;
  final List<Color> liquid;

  static const darkPalette = ShibaPalette(
    light: false,
    bgPrimary: Color(0xFF000000),
    bgSecondary: Color.fromRGBO(28, 28, 30, 0.52),
    bgSurface: Color(0xFF1C1C1E),
    bgSurfaceHover: Color(0xFF2C2C2E),
    textPrimary: Color(0xFFF5F5F7),
    textSecondary: Color.fromRGBO(235, 235, 245, 0.6),
    textCode: Color(0xFFF5F5F7),
    border: Color.fromRGBO(255, 255, 255, 0.12),
    borderHighlight: Color.fromRGBO(232, 98, 28, 0.6),
    accentDim: Color.fromRGBO(232, 100, 32, 0.36),
    green: Color(0xFF3D8A82),
    red: Color(0xFFFB7185),
    blue: Color(0xFF22D3EE),
    purple: Color(0xFFC4A86A),
    liquid: [
      Color.fromRGBO(242, 122, 46, 0.72),
      Color.fromRGBO(242, 122, 46, 0.22),
      Color.fromRGBO(196, 72, 18, 0.55),
    ],
  );

  static const lightPalette = ShibaPalette(
    light: true,
    bgPrimary: Color(0xFFFFF6EF),
    bgSecondary: Color.fromRGBO(255, 255, 255, 0.46),
    bgSurface: Color(0xFFFFFAF6),
    bgSurfaceHover: Color(0xFFFFF1E6),
    textPrimary: Color(0xFF1D1D1F),
    textSecondary: Color(0xFF3A3A3C),
    textCode: Color(0xFF1D1D1F),
    border: Color.fromRGBO(242, 122, 46, 0.22),
    borderHighlight: Color.fromRGBO(242, 122, 46, 0.55),
    accentDim: Color.fromRGBO(242, 122, 46, 0.22),
    green: Color(0xFF1F6B63),
    red: Color(0xFFB42318),
    blue: Color(0xFF1F6B63),
    purple: Color(0xFFA88858),
    liquid: [
      Color.fromRGBO(242, 122, 46, 0.55),
      Color.fromRGBO(242, 122, 46, 0.20),
      Color.fromRGBO(196, 72, 18, 0.38),
    ],
  );
}

ShibaPalette paletteOf(BuildContext context) {
  final light = Theme.of(context).brightness == Brightness.light;
  return light ? ShibaPalette.lightPalette : ShibaPalette.darkPalette;
}

ThemeData buildShibaTheme(ShibaPalette palette) {
  final scheme = ColorScheme(
    brightness: palette.light ? Brightness.light : Brightness.dark,
    primary: ShibaTokens.accent,
    onPrimary: Colors.white,
    secondary: ShibaTokens.accentLight,
    onSecondary: const Color(0xFF1D1D1F),
    error: palette.red,
    onError: Colors.white,
    surface: palette.bgSurface,
    onSurface: palette.textPrimary,
  );
  final base = ThemeData(
    useMaterial3: true,
    brightness: scheme.brightness,
    colorScheme: scheme,
    scaffoldBackgroundColor: Colors.transparent,
    fontFamily: 'Inter',
    splashFactory: InkSparkle.splashFactory,
  );
  return base.copyWith(
    textTheme: base.textTheme.apply(
      fontFamily: 'Inter',
      bodyColor: palette.textPrimary,
      displayColor: palette.textPrimary,
      decoration: TextDecoration.none,
    ),
    iconTheme: IconThemeData(color: palette.textSecondary, size: 19),
    dividerColor: palette.border,
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: palette.bgSurface,
      hintStyle: TextStyle(color: palette.textSecondary),
      labelStyle: TextStyle(color: palette.textSecondary),
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(ShibaTokens.radiusSm),
        borderSide: BorderSide(color: palette.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(ShibaTokens.radiusSm),
        borderSide: BorderSide(color: palette.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(ShibaTokens.radiusSm),
        borderSide: const BorderSide(color: ShibaTokens.accent, width: 1.4),
      ),
    ),
  );
}

class LiquidBackground extends StatelessWidget {
  const LiquidBackground({super.key, required this.palette, required this.child});

  final ShibaPalette palette;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: palette.bgPrimary,
        gradient: RadialGradient(
          center: const Alignment(1, -1),
          radius: 1.15,
          colors: [palette.liquid[0], palette.bgPrimary],
          stops: const [0, 0.58],
        ),
      ),
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: RadialGradient(
            center: const Alignment(-1, -1),
            radius: 0.9,
            colors: [palette.liquid[1], Colors.transparent],
            stops: const [0, 0.62],
          ),
        ),
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: RadialGradient(
              center: const Alignment(0.56, 1.1),
              radius: 1.05,
              colors: [palette.liquid[2], Colors.transparent],
              stops: const [0, 0.6],
            ),
          ),
          child: child,
        ),
      ),
    );
  }
}

class Glass extends StatelessWidget {
  const Glass({
    super.key,
    required this.child,
    this.radius = ShibaTokens.radiusMd,
    this.padding,
    this.color,
  });

  final Widget child;
  final double radius;
  final EdgeInsetsGeometry? padding;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final palette = paletteOf(context);
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: ShibaTokens.glassBlur, sigmaY: ShibaTokens.glassBlur),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: color ?? palette.bgSecondary,
            borderRadius: BorderRadius.circular(radius),
            border: Border.all(color: palette.border),
          ),
          child: Padding(padding: padding ?? EdgeInsets.zero, child: child),
        ),
      ),
    );
  }
}
