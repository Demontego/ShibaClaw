"""Exercise installer steps without installing the app or changing Windows settings."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.fixture(params=["pwsh", "powershell"])
def run_installer_step(request, tmp_path):
    shell = shutil.which(request.param)
    if shell is None:
        pytest.skip(f"{request.param} is not installed")

    def run(body):
        script = tmp_path / "check-step.ps1"
        script.write_text(
            r'''
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $args[0], [ref]$tokens, [ref]$parseErrors
)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
# Load only the actual helper definitions, never the installation body.
$functions = $ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -in @("Show-InstallProgress", "Invoke-LoggedStep")
}, $false)
if ($functions.Count -ne 2) { throw "Installer step helpers not found" }
foreach ($function in $functions) {
    . ([scriptblock]::Create($function.Extent.Text))
}
$installLog = $args[1]
'''
            + body,
            encoding="utf-8",
        )
        return subprocess.run(
            [
                shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(script),
                str(Path(__file__).resolve().parents[1] / "scripts/install/install.ps1"),
                str(tmp_path / "install.log"), sys.executable,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    return run


def test_successful_step_ignores_previous_native_failure(run_installer_step):
    result = run_installer_step(r'''
& $args[2] -c "import sys; sys.exit(37)"
if ($LASTEXITCODE -ne 37) { throw "Could not seed a previous native failure" }
$downloadPath = Join-Path (Split-Path $installLog) "download.zip"
Invoke-LoggedStep -Message "Downloading package" -Step 2 -Total 6 -Action {
    Set-Content -LiteralPath $downloadPath -Value "download completed"
}
if (!(Test-Path -LiteralPath $downloadPath)) { throw "Step did not run" }
$log = Get-Content -LiteralPath $installLog -Raw
if ($log -notmatch "Downloading package") { throw "Successful step was not logged" }
''')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("action", [
    'throw "HTTP 403: download blocked"',
    'Write-Error "HTTP 403: download blocked"',
])
def test_failed_step_logs_and_preserves_original_error(run_installer_step, action):
    result = run_installer_step(
        r'''
$caught = $null
try {
    Invoke-LoggedStep -Message "Downloading package" -Step 2 -Total 6 -Action {
        "Partial download output"
'''
        + action
        + r'''
        throw "Step continued after failure"
    }
} catch { $caught = $_ }
if ($null -eq $caught) { throw "Download error was swallowed" }
if ($caught.Exception.Message -notmatch "HTTP 403: download blocked") {
    throw "Original download error was replaced"
}
$log = Get-Content -LiteralPath $installLog -Raw
foreach ($expected in @("Downloading package", "Partial download output", "HTTP 403: download blocked")) {
    if ($log -notmatch [regex]::Escape($expected)) { throw "Missing log detail: $expected" }
}
'''
    )
    assert result.returncode == 0, result.stdout + result.stderr
