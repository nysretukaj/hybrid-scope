# One-time setup: Python venv + backend deps, frontend deps.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Push-Location "$root\backend"
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python -m pip install -r requirements.txt
Pop-Location

Push-Location "$root\frontend"
npm install
Pop-Location

Write-Host "Setup done. Run .\start.ps1"
