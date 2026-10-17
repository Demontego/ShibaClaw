"""Run the real downloader functions in PS 5.1 and PS 7 without installing anything."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.fixture(params=["pwsh", "powershell"])
def run_installer(request, tmp_path):
    shell = shutil.which(request.param)
    if shell is None:
        pytest.skip(f"{request.param} is not installed")

    def run(body):
        script = tmp_path / "check-setup.ps1"
        script.write_text(r'''
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
# Load functions only: no actual network, process, registry, PATH or shortcuts.
foreach ($function in $ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst]
}, $false)) { . ([scriptblock]::Create($function.Extent.Text)) }
$fixture = Join-Path $args[1] 'trusted setup.exe'
[IO.File]::WriteAllText($fixture, 'mock setup bytes')
$hash = (Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash
$script:launches = @()
$script:downloads = @()
$script:exitCode = 0
$script:setupWaits = 0
$script:apiUrl = $null
$script:release = [pscustomobject]@{ assets = @([pscustomobject]@{
    name = 'ShibaClaw-Setup.exe'; digest = ('sha256:' + $hash)
    browser_download_url = 'https://github.com/RikyZ90/ShibaClaw/releases/download/v1.0.6/ShibaClaw-Setup.exe'
}) }
function Invoke-RestMethod {
    [CmdletBinding()] param($Uri, $Headers, [switch]$UseBasicParsing)
    $script:apiUrl = $Uri
    return $script:release
}
function Invoke-WebRequest {
    [CmdletBinding()] param($Uri, $OutFile, [switch]$UseBasicParsing)
    $script:downloads += $OutFile
    Copy-Item -LiteralPath $fixture -Destination $OutFile
}
function Start-Process {
    [CmdletBinding()] param($FilePath, $ArgumentList, [switch]$Wait, [switch]$PassThru)
    if ($Wait) { throw 'Start-Process -Wait would wait for the launched app too' }
    if (-not $PassThru) { throw 'Setup process handle is required' }
    Assert-ShibaClawSetupHash -Path $FilePath -ExpectedSha256 $hash
    $process = [pscustomobject]@{ ExitCode = $null; Waited = $false; Refreshed = $false }
    $process | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value {
        $this.Waited = $true
        $this.ExitCode = $script:exitCode
        $script:setupWaits++
    }
    $process | Add-Member -MemberType ScriptMethod -Name Refresh -Value {
        if (-not $this.Waited) { throw 'Setup status refreshed before awaiting completion' }
        $this.Refreshed = $true
    }
    $script:launches += [pscustomobject]@{ Path = $FilePath; Arguments = $ArgumentList; Process = $process }
    return $process
}
''' + body, encoding="utf-8")
        env = {**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)}
        if request.param == "powershell":
            # PS7's module search path must not shadow Windows PS5.1's Utility module.
            env = {key: value for key, value in env.items() if key.lower() != "psmodulepath"}
        return subprocess.run([
            shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(script),
            str(Path(__file__).resolve().parents[1] / "scripts/install/install.ps1"),
            str(tmp_path), sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/install/uninstall.ps1"),
        ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

    return run


def assert_success(result):
    assert result.returncode == 0, result.stdout + result.stderr


def test_verified_latest_setup_ignores_stale_native_exit_and_uses_unique_temp(run_installer):
    assert_success(run_installer(r'''
& $args[2] -c "import sys; sys.exit(37)"
Install-ShibaClawSetup
Install-ShibaClawSetup
if ($script:apiUrl -notmatch '/releases/latest$') { throw 'Wrong latest release API' }
if ($script:launches.Count -ne 2) { throw 'Verified setup was not launched' }
if ($script:launches[0].Path -eq $script:launches[1].Path) { throw 'Temporary path was reused' }
foreach ($launch in $script:launches) {
    if (Test-Path -LiteralPath (Split-Path $launch.Path)) { throw 'Temporary directory was not cleaned' }
}
if (-not (Test-Path -LiteralPath $fixture)) { throw 'Original local input was removed' }
'''))


def test_explicit_version_and_install_directory_are_forwarded(run_installer):
    assert_success(run_installer(r'''
$destination = Join-Path $args[1] 'custom app'
Install-ShibaClawSetup -RequestedVersion '1.0.6' -Destination $destination
if ($script:apiUrl -notmatch '/releases/tags/v1.0.6$') { throw 'Wrong version API' }
if ($script:launches[0].Arguments[0] -ne '--installto') { throw 'InstallDir was not forwarded' }
if ($script:launches[0].Arguments[1] -ne ('"' + $destination + '"')) { throw 'InstallDir quoting failed' }
'''))


def test_downloader_returns_after_setup_while_launched_app_is_still_running(run_installer):
    assert_success(run_installer(r'''
$script:desktopAppRunning = $true
Install-ShibaClawSetup
if (-not $script:desktopAppRunning) { throw 'Downloader waited for or stopped the desktop app' }
if ($script:setupWaits -ne 1) { throw 'Setup was not awaited exactly once' }
if (-not $script:launches[0].Process.Refreshed) { throw 'Setup exit status was not refreshed' }
if (Test-Path -LiteralPath (Split-Path $script:launches[0].Path)) { throw 'Temporary setup was not cleaned' }
'''))


def test_old_updater_arguments_migrate_to_verified_setup_without_accessing_zip(run_installer):
    assert_success(run_installer(r'''
$legacyZip = Join-Path $args[1] 'legacy updater package.zip'
[IO.File]::WriteAllText($legacyZip, 'legacy zip must not be read or extracted')
$legacyRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.shibaclaw'
function Test-Path {
    [CmdletBinding()] param($LiteralPath, $Path, $PathType)
    if ($LiteralPath -eq $legacyZip -or $Path -eq $legacyZip) { throw 'Legacy ZIP was accessed' }
    return Microsoft.PowerShell.Management\Test-Path @PSBoundParameters
}
# Dot-source the full entry point so the mocked cmdlets share this script scope.
. $args[0] -Version '1.0.6' -LocalZipPath $legacyZip -InstallDir $legacyRoot
if ($script:apiUrl -notmatch '/releases/tags/v1.0.6$') { throw 'Legacy requested version was lost' }
if ($script:launches.Count -ne 1) { throw 'Verified setup was not launched' }
if ($script:launches[0].Arguments.Count) { throw 'Unsafe legacy InstallDir was forwarded' }
if ([IO.File]::ReadAllText($legacyZip) -ne 'legacy zip must not be read or extracted') { throw 'Legacy ZIP was changed or removed' }
'''))


def test_legacy_zip_and_local_setup_are_rejected_as_ambiguous(run_installer):
    assert_success(run_installer(r'''
$caught = $null
try { & $args[0] -LocalZipPath 'old.zip' -LocalSetupPath $fixture -SetupSha256 $hash } catch { $caught = $_ }
if ($null -eq $caught -or $caught.Exception.Message -notmatch 'cannot be combined') { throw 'Ambiguous local inputs were accepted' }
if ($script:apiUrl -or $script:downloads.Count -or $script:launches.Count) { throw 'Ambiguous input caused side effects' }
'''))


@pytest.mark.parametrize("failure", ["digest", "asset", "url", "duplicate", "hash", "download", "exit"])
def test_download_or_setup_failure_is_not_reported_as_success(run_installer, failure):
    setup = {
        "digest": "$script:release.assets[0].digest = $null",
        "asset": "$script:release.assets[0].name = 'ShibaClaw-windows.zip'",
        "url": "$script:release.assets[0].browser_download_url = 'https://example.org/ShibaClaw-Setup.exe'",
        "duplicate": "$script:release.assets += $script:release.assets[0]",
        "hash": "$script:release.assets[0].digest = 'sha256:' + ('0' * 64)",
        "download": "function Invoke-WebRequest { throw 'HTTP 403: download blocked' }",
        "exit": "$script:exitCode = 37",
    }[failure]
    expected_launches = 1 if failure == "exit" else 0
    assert_success(run_installer(setup + rf'''
$caught = $null
try {{ Install-ShibaClawSetup }} catch {{ $caught = $_ }}
if ($null -eq $caught) {{ throw 'Failure was swallowed' }}
if ($script:launches.Count -ne {expected_launches}) {{ throw 'Unverified setup was launched' }}
foreach ($download in $script:downloads) {{
    if (Test-Path -LiteralPath (Split-Path $download)) {{ throw 'Failed download was not cleaned' }}
}}
'''))


@pytest.mark.parametrize("hash_option", ["missing", "wrong", "valid"])
def test_local_setup_requires_matching_explicit_hash_and_preserves_source(run_installer, hash_option):
    digest = {"missing": "''", "wrong": "('0' * 64)", "valid": "$hash"}[hash_option]
    expected_launches = 1 if hash_option == "valid" else 0
    assert_success(run_installer(rf'''
$caught = $null
try {{ Install-ShibaClawSetup -LocalPath $fixture -LocalSha256 {digest} }} catch {{ $caught = $_ }}
if ($script:launches.Count -ne {expected_launches}) {{ throw 'Wrong local launch count' }}
if ({expected_launches} -eq 0 -and $null -eq $caught) {{ throw 'Invalid local hash was accepted' }}
if ($script:apiUrl -or $script:downloads.Count) {{ throw 'Local setup accessed the network' }}
if (-not (Test-Path -LiteralPath $fixture)) {{ throw 'Source setup was deleted' }}
'''))


@pytest.mark.parametrize("relationship", ["equal", "ancestor", "descendant", "home_env", "userprofile_env"])
def test_user_data_directory_cannot_overlap_install_root(run_installer, relationship):
    destination = {
        "equal": "$dataPath",
        "ancestor": "(Split-Path $dataPath)",
        "descendant": "(Join-Path $dataPath 'app')",
        "home_env": "(Join-Path $env:HOME '.shibaclaw')",
        "userprofile_env": "(Join-Path $env:USERPROFILE '.shibaclaw')",
    }[relationship]
    assert_success(run_installer(r'''
$env:HOME = Join-Path $args[1] 'different home'
$env:USERPROFILE = Join-Path $args[1] 'different profile'
$dataPath = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.shibaclaw'
$caught = $null
''' + "try { Install-ShibaClawSetup -Destination " + destination + r''' } catch { $caught = $_ }
if ($null -eq $caught) { throw 'Data directory was accepted as the uninstallable application root' }
if ($script:apiUrl -or $script:launches.Count) { throw 'Invalid destination was used' }
'''))


@pytest.mark.parametrize("source", ["override", "registry"])
def test_legacy_uninstaller_leaves_managed_install_and_shared_registration_alone(run_installer, source):
    install_arg = "-InstallDir $managed" if source == "override" else ""
    assert_success(run_installer(r'''
$managed = Join-Path $args[1] 'custom managed root'
New-Item -ItemType Directory -Path (Join-Path $managed 'current') -Force | Out-Null
Set-Content -LiteralPath (Join-Path $managed 'Update.exe') -Value 'mock updater'
Set-Content -LiteralPath (Join-Path $managed 'current\sq.version') -Value 'mock manifest'
function Get-ItemProperty { param($LiteralPath, $ErrorAction); return [pscustomobject]@{InstallLocation = $managed} }
function Remove-Item { throw 'Legacy uninstaller attempted to delete a shared artifact' }
''' + "& $args[3] -Force " + install_arg + r'''
if (-not (Test-Path -LiteralPath (Join-Path $managed 'Update.exe'))) { throw 'Managed installation was modified' }
'''))
