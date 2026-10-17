import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

import 'desk.dart';
import 'history_window.dart';
import 'theme.dart';
import 'transcript.dart';

class ChatPage extends StatefulWidget {
  const ChatPage({super.key});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _scroll = ScrollController();
  final _input = TextEditingController();
  final _focus = FocusNode();
  HistoryWindow _window = HistoryWindow(0);
  int _epoch = -1;
  int _count = 0;
  bool _pin = true;
  bool _loadingOlder = false;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_onScroll);
    _focus.addListener(() {
      if (mounted) setState(() {});
    });
    _focus.onKeyEvent = (node, event) {
      if (event is KeyDownEvent && event.logicalKey == LogicalKeyboardKey.enter && !HardwareKeyboard.instance.isShiftPressed) {
        _send();
        return KeyEventResult.handled;
      }
      return KeyEventResult.ignored;
    };
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final desk = DeskScope.of(context);
    final count = desk.items.length;
    if (_epoch != desk.transcriptEpoch) {
      _epoch = desk.transcriptEpoch;
      _count = count;
      _window = HistoryWindow(count);
      _pin = true;
      WidgetsBinding.instance.addPostFrameCallback((_) => _jumpBottom());
    } else if (count != _count) {
      _count = count;
      if (_pin) WidgetsBinding.instance.addPostFrameCallback((_) => _jumpBottom());
    }
  }

  void _jumpBottom() {
    if (!_scroll.hasClients) return;
    _scroll.jumpTo(_scroll.position.maxScrollExtent);
  }

  void _onScroll() {
    if (!_scroll.hasClients || _loadingOlder) return;
    final pos = _scroll.position;
    _pin = pos.pixels >= pos.maxScrollExtent - 80;
    if (pos.pixels >= 80 || !_window.hasOlder) return;
    _loadingOlder = true;
    final beforeMax = pos.maxScrollExtent;
    final before = pos.pixels;
    setState(() => _window.prependOlder());
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        final delta = _scroll.position.maxScrollExtent - beforeMax;
        _scroll.jumpTo(before + delta);
      }
      _loadingOlder = false;
    });
  }

  void _send() {
    final desk = DeskScope.of(context);
    desk.send(_input.text);
    _input.clear();
  }

  @override
  void dispose() {
    _scroll.dispose();
    _input.dispose();
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final palette = paletteOf(context);
    final visible = desk.items.sublist(_window.renderedFrom.clamp(0, desk.items.length));
    return Stack(
      children: [
        Column(
          children: [
            Expanded(
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: ShibaTokens.chatWidth),
                  child: visible.isEmpty
                      ? _Welcome(
                          palette: palette,
                          onPrompt: (text) {
                            _input.text = text;
                            _input.selection = TextSelection.collapsed(offset: text.length);
                            _focus.requestFocus();
                          },
                        )
                      : ListView.builder(
                          controller: _scroll,
                          padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                          itemCount: visible.length,
                          itemBuilder: (context, index) => _Bubble(item: visible[index]),
                        ),
                ),
              ),
            ),
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: ShibaTokens.chatWidth),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: palette.bgSurface.withValues(alpha: 0.86),
                      borderRadius: BorderRadius.circular(ShibaTokens.composerRadius),
                      border: Border.all(color: _focus.hasFocus ? palette.borderHighlight : palette.border),
                      boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.28), blurRadius: 40, offset: const Offset(0, 12))],
                    ),
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(8, 8, 8, 6),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          if (desk.pending.isNotEmpty)
                            Wrap(
                              spacing: 6,
                              children: [
                                for (var i = 0; i < desk.pending.length; i++)
                                  InputChip(
                                    label: Text(desk.pending[i]['name']?.toString() ?? 'file'),
                                    onDeleted: () => desk.removePending(i),
                                  ),
                              ],
                            ),
                          TextField(
                            controller: _input,
                            focusNode: _focus,
                            minLines: 1,
                            maxLines: 6,
                            style: TextStyle(color: palette.textPrimary),
                            spellCheckConfiguration: const SpellCheckConfiguration.disabled(),
                            decoration: InputDecoration(
                              hintText: desk.t('workspace.chat_placeholder'),
                              border: InputBorder.none,
                              enabledBorder: InputBorder.none,
                              focusedBorder: InputBorder.none,
                              filled: false,
                              isDense: true,
                              contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                            ),
                          ),
                          Row(
                            children: [
                              IconButton(tooltip: desk.t('chat.attach'), onPressed: desk.attachFiles, icon: const Icon(Icons.add)),
                              IconButton(
                                // shortcut: icon only, wire STT when this client records audio
                                tooltip: desk.t('chat.voice'),
                                onPressed: () {},
                                icon: const Icon(Icons.mic_none),
                              ),
                              const Spacer(),
                              TextButton(
                                onPressed: desk.loadContext,
                                child: Text(_tokenLabel(desk), style: TextStyle(fontSize: 12, color: palette.textSecondary)),
                              ),
                              IconButton(
                                tooltip: desk.processing ? desk.t('chat.stop_title') : desk.t('chat.send'),
                                onPressed: desk.processing ? desk.stop : _send,
                                icon: Icon(desk.processing ? Icons.stop_circle : Icons.arrow_upward, color: ShibaTokens.accent),
                              ),
                            ],
                          ),
                          Padding(
                            padding: const EdgeInsets.fromLTRB(8, 2, 8, 2),
                            child: Row(
                              children: [
                                Icon(Icons.verified_user, size: 12, color: palette.textSecondary),
                                const SizedBox(width: 4),
                                Text(desk.t('workspace.control'), style: TextStyle(fontSize: 11, color: palette.textSecondary)),
                                const Spacer(),
                                Text(desk.t('chat.shift_enter'), style: TextStyle(fontSize: 11, color: palette.textSecondary)),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
        if (desk.resultOpen)
          Positioned(
            top: 8,
            right: 12,
            bottom: 12,
            width: 420,
            child: Glass(
              radius: ShibaTokens.radiusLg,
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(12, 8, 4, 8),
                    child: Row(
                      children: [
                        Expanded(child: Text(desk.resultTitle.isEmpty ? 'Result' : desk.resultTitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600))),
                        IconButton(tooltip: desk.t('common.close'), onPressed: desk.closeResult, icon: const Icon(Icons.close)),
                      ],
                    ),
                  ),
                  const Divider(height: 1),
                  Expanded(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(14),
                      child: SelectableText(desk.resultBody, style: TextStyle(fontSize: 13, height: 1.45, color: palette.textPrimary)),
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

String _fmtTokens(int n) {
  if (n < 1000) return '$n';
  final text = (n / 1000).toStringAsFixed(1);
  final trimmed = text.endsWith('.0') ? text.substring(0, text.length - 2) : text;
  return '${trimmed}k';
}

String _tokenLabel(Desk desk) {
  if (desk.tokenWindow <= 0) return '-- / --';
  return '${_fmtTokens(desk.tokenUsed)} / ${_fmtTokens(desk.tokenWindow)} · ${desk.tokenPct}%';
}

class _Welcome extends StatelessWidget {
  const _Welcome({required this.palette, required this.onPrompt});
  final ShibaPalette palette;
  final ValueChanged<String> onPrompt;

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    return Align(
      alignment: Alignment.center,
        child: SizedBox(
        width: ShibaTokens.welcomeMax,
        child: ListView(
        shrinkWrap: true,
        padding: const EdgeInsets.fromLTRB(0, 30, 0, 12),
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, size: 17, color: ShibaTokens.accent),
              const SizedBox(width: 8),
              Text(desk.t('workspace.welcome_eyebrow'), style: const TextStyle(fontSize: 12, color: ShibaTokens.accent)),
            ],
          ),
          const SizedBox(height: 19),
          Text(desk.t('workspace.welcome_title'), style: TextStyle(fontSize: 32, height: 1.15, fontWeight: FontWeight.w600, letterSpacing: -0.8, color: palette.textPrimary)),
          const SizedBox(height: 10),
          Text(desk.t('workspace.welcome_subtitle'), style: TextStyle(fontSize: 15, height: 1.5, color: palette.textSecondary)),
          const SizedBox(height: 26),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              _Hint(icon: Icons.folder_open, title: desk.t('workspace.hint_project'), body: desk.t('workspace.hint_project_desc'), onTap: () => onPrompt(desk.t('workspace.hint_project_prompt'))),
              _Hint(icon: Icons.travel_explore, title: desk.t('workspace.hint_research'), body: desk.t('workspace.hint_research_desc'), onTap: () => onPrompt(desk.t('workspace.hint_research_prompt'))),
              _Hint(icon: Icons.schedule, title: desk.t('workspace.hint_automation'), body: desk.t('workspace.hint_automation_desc'), onTap: () => desk.setPage('automations')),
              _Hint(icon: Icons.pets_outlined, title: desk.t('workspace.hint_agents'), body: desk.t('workspace.hint_agents_desc'), onTap: () => desk.setPage('agents')),
            ],
          ),
        ],
      ),
      ),
    );
  }
}

class _Hint extends StatelessWidget {
  const _Hint({required this.icon, required this.title, required this.body, required this.onTap});
  final IconData icon;
  final String title;
  final String body;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final palette = paletteOf(context);
    return SizedBox(
      width: (ShibaTokens.welcomeMax - 10) / 2,
      child: Material(
        color: palette.bgSurface.withValues(alpha: 0.62),
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: onTap,
          child: Container(
            constraints: const BoxConstraints(minHeight: ShibaTokens.hintHeight),
            padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(ShibaTokens.hintRadius), border: Border.all(color: palette.border)),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(icon, size: 20, color: ShibaTokens.accent),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: palette.textPrimary)),
                      const SizedBox(height: 2),
                      Text(body, style: TextStyle(fontSize: 12, color: palette.textSecondary)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.item});
  final ChatItem item;

  @override
  Widget build(BuildContext context) {
    final palette = paletteOf(context);
    final desk = DeskScope.of(context);
    if (item.role == 'step') {
      return Align(
        alignment: Alignment.centerLeft,
        child: TextButton(
          onPressed: () => desk.showResult(item.text, item.detail.isEmpty ? item.text : item.detail),
          child: Text(item.text, maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(color: palette.textSecondary, fontSize: 12)),
        ),
      );
    }
    if (item.role == 'error') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Text(item.text, style: TextStyle(color: palette.red)),
      );
    }
    if (item.role == 'interactive') return _InteractiveCard(item: item);
    final mine = item.role == 'user';
    final bubble = Container(
      margin: const EdgeInsets.symmetric(vertical: 6),
      padding: const EdgeInsets.fromLTRB(16, 11, 16, 11),
      decoration: BoxDecoration(
        color: mine ? palette.accentDim : Color.alphaBlend(ShibaTokens.accent.withValues(alpha: 0.18), palette.bgSurface),
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(22),
          topRight: const Radius.circular(22),
          bottomRight: Radius.circular(mine ? 6 : 22),
          bottomLeft: Radius.circular(mine ? 22 : 6),
        ),
        border: Border.all(color: mine ? palette.border : palette.borderHighlight),
      ),
      child: mine
          ? SelectableText(item.text, style: TextStyle(color: palette.textPrimary, height: 1.4))
          : MarkdownBody( // shortcut: flutter_markdown 0.7 is discontinued, switch package if the SDK drops it
              data: item.text.isEmpty && item.streaming ? '…' : item.text,
              selectable: true,
              styleSheet: MarkdownStyleSheet(
                p: TextStyle(color: palette.textPrimary, fontSize: 15, height: 1.45, fontFamily: 'Inter'),
                code: TextStyle(color: palette.textCode, fontFamily: 'monospace', backgroundColor: palette.bgSurface),
                a: const TextStyle(color: ShibaTokens.accent),
              ),
            ),
    );
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: mine ? ShibaTokens.chatWidth * 0.78 : ShibaTokens.chatWidth),
        child: bubble,
      ),
    );
  }
}

class _InteractiveCard extends StatefulWidget {
  const _InteractiveCard({required this.item});
  final ChatItem item;

  @override
  State<_InteractiveCard> createState() => _InteractiveCardState();
}

class _InteractiveCardState extends State<_InteractiveCard> {
  final _text = TextEditingController();

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final desk = DeskScope.of(context);
    final palette = paletteOf(context);
    final payload = widget.item.payload ?? const {};
    final requestId = payload['request_id']?.toString() ?? widget.item.id;
    final prompt = payload['prompt']?.toString() ?? payload['message']?.toString() ?? payload['question']?.toString() ?? '';
    final options = payload['options'];
    return Glass(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (prompt.isNotEmpty) Text(prompt, style: TextStyle(color: palette.textPrimary)),
          if (options is List)
            Wrap(
              spacing: 6,
              children: [
                for (final option in options)
                  ShibaChoice(
                    label: option is Map ? (option['label'] ?? option['value'] ?? option).toString() : option.toString(),
                    onPressed: () => desk.replyInteractive(requestId, option is Map ? (option['value'] ?? option['label'] ?? option) : option),
                  ),
              ],
            ),
          Row(
            children: [
              Expanded(child: TextField(controller: _text, decoration: const InputDecoration(isDense: true))),
              IconButton(
                onPressed: () => desk.replyInteractive(requestId, _text.text),
                icon: const Icon(Icons.send, color: ShibaTokens.accent),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class ShibaChoice extends StatelessWidget {
  const ShibaChoice({super.key, required this.label, required this.onPressed});
  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: OutlinedButton(onPressed: onPressed, child: Text(label)),
    );
  }
}
