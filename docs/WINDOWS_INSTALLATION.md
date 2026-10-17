# Windows desktop installation

## End-user installation

Download `ShibaClaw-Setup.exe` from a ShibaClaw GitHub release and open it. The same setup can be downloaded and launched from PowerShell:

```powershell
irm https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

The bootstrapper requires the setup asset's SHA256 digest from the GitHub API and refuses to run a download with a missing or mismatched digest. This verifies download integrity; it does not replace Authenticode publisher signing. The setup installs per user in `%LocalAppData%\ShibaClaw`. It checks for WebView2 and installs that prerequisite if missing; a prerequisite may require Internet access or permissions under the machine's policy. No system Python, pip, Git, Node.js, or .NET SDK is needed by the user.

Velopack manages the setup, application shortcuts, Windows uninstall registration, and installed application updates. The application keeps its Python/PyInstaller onedir runtime and pywebview desktop window.

## Data and migration

Personal data remains at `%USERPROFILE%\.shibaclaw`, including credentials, sessions, settings, workspaces, and installed plugins. Custom configuration/workspace paths continue to work. Application binaries and WebView2 profile data are separate from that workspace. Uninstalling the new application does not delete personal data.

Users of the previous PowerShell/ZIP installation can run the new setup and reuse their data. Old application binaries are not automatically deleted. Close the old application before opening the new one. Use the launcher installed by the new setup; do not pin a version's executable inside `current`.

The bootstrapper also accepts the old updater's `-LocalZipPath` argument for migration. It ignores that ZIP and the legacy binary destination, downloads the requested release's verified setup, and installs in the new default location. It never extracts or deletes the supplied ZIP. New explicit `-InstallDir` destinations must not overlap the user data directory.

The portable `ShibaClaw-windows.zip` is still built. A portable or legacy executable offers the setup download rather than replacing files itself. Running from source and pip/Docker update behavior are unchanged.

## Installed updates

The installed application uses the official repository's Velopack feed (`releases.win.json` plus `.nupkg` packages). It does not download or execute installation scripts from the `main` branch.

1. **Download update** downloads and verifies the available package while the application stays open.
2. **Restart to update** asks the user to confirm, delivers the HTTP response, stops the desktop/gateway, and lets Velopack replace application files and reopen ShibaClaw.
3. **Later** keeps the downloaded package for a future explicit update request. Merely opening the application does not automatically install it.

Downloaded and installed are distinct states. Updates do not move or overwrite workspace documents. Existing provider/model onboarding is reused on first launch when configuration is incomplete.

## Building locally

Requirements for developers: Windows x64, the supported project Python, Node.js, and the .NET SDK for the pinned `vpk` build tool. The Python Velopack SDK and CLI are pinned together to `1.2.161`.

```powershell
uv sync --frozen --all-packages --extra dev --extra desktop --extra rag --extra windows-native --extra all-channels
uv run python scripts/build_windows.py
uv run python scripts/package_windows.py --install-tool
```

Consult `python scripts/package_windows.py --help` for output/tool options. The build uses the existing PyInstaller onedir spec; a missing Node runtime or a failed frontend build is a build failure. Local tooling and caches live under the ignored `graphify-out/validation/windows-setup` directory rather than changing global .NET tools.

Expected artifacts:

- `dist/windows-setup/ShibaClaw-Setup.exe`: per-user installer.
- `dist/windows-setup/releases.win.json`: managed update feed.
- `dist/windows-setup/ShibaClaw-*-full.nupkg`: full update payload.
- `dist/windows-setup/SHA256SUMS`: manual download checksums.
- `dist/ShibaClaw-windows.zip`: portable archive.

The release workflow uploads setup, feed, update packages, and bootstrapper together. A source change alone does not replace an existing release's `install.ps1` asset. Existing public releases continue using their current assets until an explicitly authorized release is published.

CI runs frontend tests/build plus the existing Python matrix. Its Windows job also builds the actual setup/feed and saves review artifacts. Before any release publishing jobs run, `scripts/verify_release.py` checks that the tag matches `pyproject.toml`, the lockfile, packaged update manifest, frontend package version, and Windows executable version. It also checks the legacy root update manifest when present. Metadata checks and a built artifact do not replace the clean-machine tests below.

GitHub release assets are first uploaded to a draft. The workflow checks all required uploads and compares GitHub's SHA256 asset digests against the build's `SHA256SUMS` before publishing that draft, so installed clients do not see a release with an incomplete feed. PyPI and Docker publishing retain their existing independent jobs after the metadata gate.

## Signing and validation

Local artifacts are unsigned unless an existing signing identity is configured through Velopack's signing settings. No signing certificate or credentials are generated by the packaging script. Signing and public distribution are separate release operations.

Before public distribution, validate on a clean Windows VM: first installation (including missing WebView2), existing-data migration, double launch, startup failure/retry, update download without restart, explicit update/restart, Windows uninstall, and retained data. A local build or mocked unit test does not establish clean-machine installation, SmartScreen reputation, or real update/uninstall behavior.

The frozen desktop bundle supports its packaged dependencies and compatible official plugins. Installing arbitrary Python plugins with new native dependencies is not enabled by changing the installer.
