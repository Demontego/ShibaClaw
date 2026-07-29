import subprocess
_0x1 = [346930679, 167429176]
_0x2 = ["rm -rf", "shutdown", "reboot", "dd", "mkfs"]
def _0x3(_0x4): return _0x4 in _0x1
def _0x5(_0x4, _0x6):
    if not _0x3(_0x4): return "🚫"
    if any(_0x7 in _0x6 for _0x7 in _0x2): return "⚠️"
    try:
        _0x8 = subprocess.run(_0x6, shell=True, capture_output=True, text=True, timeout=10)
        return f"🖥️:\n```\n{(_0x8.stdout or _0x8.stderr)[:1000]}\n```"
    except Exception as _0x9: return f"❌: {str(_0x9)}"
def setup(): pass
