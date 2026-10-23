<#
.SYNOPSIS
  Starts the dashboard: the local API on 127.0.0.1:8000 and the web app on http://localhost:5173.

.DESCRIPTION
  Runs `uvicorn api.main:app` (without --reload: a reload orphans a CLI run the API started) in the
  background, then `npm run dev` in the foreground. Closing the web server (Ctrl+C) stops the API.
  Use -Mock to run the web app on its fixtures with no API at all.

  Needs the project virtualenv with the api extra:  pip install -e ".[dev,api]"  and  npm install  in web\.
#>
param([switch]$Mock)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

$api = $null
if (-not $Mock) {
  $api = Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $repo -PassThru -NoNewWindow
  Write-Host "API started (pid $($api.Id)) on http://127.0.0.1:8000"
}

try {
  Set-Location (Join-Path $repo "web")
  if ($Mock) { npm run dev:mock } else { npm run dev }
}
finally {
  if ($api -and -not $api.HasExited) {
    Stop-Process -Id $api.Id -Force
    Write-Host "API stopped"
  }
}
