import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'desk.dart';
import 'theme.dart';

const _dogHue = {'default': 0, 'polymarket': 108, 'dungeon': 248, 'gym': 332, 'boardnight': 196};

int dogHue(String id) {
  final known = _dogHue[id];
  if (known != null) return known;
  var hue = 0;
  for (final unit in id.codeUnits) {
    hue = (hue * 33 + unit) % 360;
  }
  return hue;
}

List<double> hueMatrix(int degrees) {
  final a = degrees * math.pi / 180;
  final c = math.cos(a);
  final s = math.sin(a);
  return [
    0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928, 0, 0,
    0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.140, 0.072 - c * 0.072 - s * 0.283, 0, 0,
    0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072, 0, 0,
    0, 0, 0, 1, 0,
  ];
}

Widget dogAvatar(String id, {double size = 28}) {
  final image = ClipOval(
    child: Image.asset('assets/shibaclaw_logo.webp', width: size, height: size, fit: BoxFit.cover),
  );
  final hue = dogHue(id);
  if (hue == 0) return image;
  return ColorFiltered(colorFilter: ColorFilter.matrix(hueMatrix(hue)), child: image);
}

class ShibaField extends StatelessWidget {
  const ShibaField({
    super.key,
    required this.controller,
    this.label,
    this.hint,
    this.obscure = false,
    this.maxLines = 1,
    this.expands = false,
    this.onSubmit,
  });

  final TextEditingController controller;
  final String? label;
  final String? hint;
  final bool obscure;
  final int maxLines;
  final bool expands;
  final ValueChanged<String>? onSubmit;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      obscureText: obscure,
      minLines: expands ? null : 1,
      maxLines: expands ? null : (obscure ? 1 : maxLines),
      expands: expands,
      textAlignVertical: expands ? TextAlignVertical.top : null,
      onSubmitted: onSubmit,
      spellCheckConfiguration: const SpellCheckConfiguration.disabled(),
      style: TextStyle(color: paletteOf(context).textPrimary, fontSize: 14),
      decoration: InputDecoration(labelText: label, hintText: hint),
    );
  }
}

class ShibaButton extends StatelessWidget {
  const ShibaButton({super.key, required this.label, required this.onPressed, this.filled = true});

  final String label;
  final VoidCallback? onPressed;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    final palette = paletteOf(context);
    final style = filled
        ? FilledButton.styleFrom(
            backgroundColor: ShibaTokens.accent,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(ShibaTokens.radiusSm)),
          )
        : OutlinedButton.styleFrom(
            foregroundColor: palette.textPrimary,
            side: BorderSide(color: palette.border),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(ShibaTokens.radiusSm)),
          );
    final child = Text(label);
    return filled ? FilledButton(onPressed: onPressed, style: style, child: child) : OutlinedButton(onPressed: onPressed, style: style, child: child);
  }
}

class StatusText extends StatelessWidget {
  const StatusText(this.text, {super.key, this.error = false});

  final String text;
  final bool error;

  @override
  Widget build(BuildContext context) {
    if (text.isEmpty) return const SizedBox.shrink();
    final palette = paletteOf(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(text, style: TextStyle(color: error ? palette.red : palette.textSecondary, fontSize: 13)),
    );
  }
}

class PageFrame extends StatelessWidget {
  const PageFrame({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: ShibaTokens.panelMax),
        child: child,
      ),
    );
  }
}

class EmptyHint extends StatelessWidget {
  const EmptyHint(this.text, {super.key});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Center(child: Text(text, style: TextStyle(color: paletteOf(context).textSecondary)));
  }
}

Future<bool> confirm(BuildContext context, String title, String body) async {
  final desk = DeskScope.of(context);
  final answer = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: Text(body),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: Text(desk.t('common.cancel'))),
        TextButton(onPressed: () => Navigator.pop(context, true), child: Text(desk.t('common.confirm'))),
      ],
    ),
  );
  return answer == true;
}

String sessionLabel(Map<String, dynamic> session) {
  final nick = session['nickname']?.toString() ?? '';
  if (nick.isNotEmpty) return nick;
  return session['key']?.toString() ?? '';
}
