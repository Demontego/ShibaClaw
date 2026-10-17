"""Keep an explicit ShibaClaw logout separate from the Codex CLI login."""

from pathlib import Path


def _disconnect_marker() -> Path:
    return Path.home() / ".shibaclaw" / "openai_codex" / "disconnected"


def get_codex_token():
    from oauth_cli_kit import get_token
    from oauth_cli_kit.providers import OPENAI_CODEX_PROVIDER
    from oauth_cli_kit.storage import FileTokenStorage

    if not _disconnect_marker().exists():
        return get_token()
    # The library normally imports ~/.codex/auth.json when its own token is
    # missing. An explicit ShibaClaw logout must survive that fallback.
    return get_token(storage=FileTokenStorage(
        token_filename=OPENAI_CODEX_PROVIDER.token_filename,
        import_codex_cli=False,
    ))


def allow_codex_login() -> None:
    """Restore normal login behavior after an explicit successful login."""
    _disconnect_marker().unlink(missing_ok=True)


def disconnect_codex() -> None:
    from oauth_cli_kit.providers import OPENAI_CODEX_PROVIDER
    from oauth_cli_kit.storage import FileTokenStorage

    marker = _disconnect_marker()
    marker.parent.mkdir(parents=True, exist_ok=True)
    already_disconnected = marker.exists()
    marker.touch()
    try:
        storage = FileTokenStorage(token_filename=OPENAI_CODEX_PROVIDER.token_filename)
        Path(storage.get_token_path()).unlink(missing_ok=True)
        mirror = Path.home() / ".config" / "shibaclaw" / "openai_codex" / "credentials.json"
        mirror.unlink(missing_ok=True)
    except Exception:
        if not already_disconnected:
            marker.unlink(missing_ok=True)
        raise
