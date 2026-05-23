# Launch backend + frontend in two new PowerShell windows.
# Usage:  .\scripts\dev.ps1
# Stop:   close each window (Ctrl+C also works).

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Python venv not found. Run setup steps from README first." -ForegroundColor Yellow
    exit 1
}

$pyArgs  = "-NoExit", "-Command", "Set-Location '$root'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000"
$npmArgs = "-NoExit", "-Command", "Set-Location '$root'; npm run dev --prefix .\frontend"

Start-Process powershell -ArgumentList $pyArgs
Start-Process powershell -ArgumentList $npmArgs

Write-Host "Backend  -> http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Frontend -> http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "Close the two new windows to stop." -ForegroundColor DarkGray
