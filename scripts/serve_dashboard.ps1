<#
.SYNOPSIS
  Serves the whole dashboard from one address: http://127.0.0.1:8000

.DESCRIPTION
  Builds the web app (web\dist) and starts the API, which serves both /api and the built pages.
  No Vite dev server, no second terminal. Use -NoBuild to reuse the existing web\dist.
  Binds 127.0.0.1 only and runs without --reload (a reload would orphan a CLI run the API started).

  Needs the project virtualenv with the api extra:  pip install -e ".[dev,api]"  and  npm install  in web\.
#>
param([switch]$NoBuild)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

if (-not $NoBuild) {
  Push-Location (Join-Path $repo "web")
  try { npm run build; if ($LASTEXITCODE -ne 0) { throw "web build failed" } } finally { Pop-Location }
}

Write-Host "Dashboard: http://127.0.0.1:8000  (Ctrl+C to stop)"
& $python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
