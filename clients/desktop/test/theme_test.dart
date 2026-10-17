import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shibaclaw_desktop/theme.dart';
import 'package:shibaclaw_desktop/widgets.dart';

void main() {
  test('workspace.css tokens, not the old gold theme', () {
    expect(ShibaPalette.darkPalette.bgPrimary, const Color(0xFF000000));
    expect(ShibaPalette.lightPalette.bgPrimary, const Color(0xFFFFF6EF));
    expect(ShibaTokens.accent, const Color(0xFFF27A2E));
    expect(ShibaPalette.darkPalette.bgSurface, const Color(0xFF1C1C1E));
    expect(ShibaPalette.lightPalette.bgSurface, const Color(0xFFFFFAF6));
    expect(ShibaTokens.accent, isNot(const Color(0xFFDBAA79)));
    expect(ShibaTokens.sidebarWidth, 248);
    expect(ShibaTokens.headerHeight, 56);
    expect(ShibaTokens.chatWidth, 780);
    expect(ShibaTokens.welcomeMax, 660);
    expect(ShibaTokens.panelMax, 800);
    expect(ShibaTokens.settingsNav, 190);
    expect(ShibaTokens.radiusSm, 8);
    expect(ShibaTokens.radiusMd, 12);
    expect(ShibaTokens.radiusLg, 18);
    expect(buildShibaTheme(ShibaPalette.darkPalette).brightness, Brightness.dark);
    expect(buildShibaTheme(ShibaPalette.lightPalette).brightness, Brightness.light);
    expect(dogHue('polymarket'), 108);
    expect(dogHue('default'), 0);
    expect(hueMatrix(0)[0], closeTo(1, 0.001));
  });
}
