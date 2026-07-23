$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pyinstallerPath = Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv (Join-Path $projectRoot ".venv")
}

& $pythonPath -m pip install -r (Join-Path $projectRoot "requirements.txt")
& $pyinstallerPath --clean --noconfirm (Join-Path $projectRoot "MathQuickRef.spec")

Write-Host "Build complete: dist\研数公式速查-2.1.exe"
