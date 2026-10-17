/// Telegram-style window from chat_history_window.js. Page size is 30.
class HistoryWindow {
  HistoryWindow(int total) : renderedFrom = total <= page ? 0 : total - page;

  static const page = 30;
  int renderedFrom;

  bool get hasOlder => renderedFrom > 0;

  void prependOlder() {
    if (renderedFrom <= 0) return;
    final next = renderedFrom - page;
    renderedFrom = next < 0 ? 0 : next;
  }
}
