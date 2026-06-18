# Start VLP local web API + frontend dev servers.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "Starting VLP Web API on http://127.0.0.1:8765"
Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "Set-Location '$Root'; uvicorn web.api.main:app --reload --host 127.0.0.1 --port 8765"
) | Out-Null

Start-Sleep -Seconds 2

Write-Host "Starting VLP frontend on http://127.0.0.1:5550"
Set-Location "$Root/web/frontend"
if (-not (Test-Path "node_modules")) {
  npm install
}
npm run dev
