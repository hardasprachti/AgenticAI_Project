<#
.SYNOPSIS
  Weekly trigger for the Groww Review Pulse (Windows). Called by Task Scheduler; safe to run by hand.

.DESCRIPTION
  Runs `python -m pulse run --source play` from the repo root with the project's virtualenv, appends
  the output to data\logs\weekly-<date>.log, and exits with the pulse's own exit code so the
  scheduler shows failures:
    0  published, or this week was already published (a duplicate trigger is harmless)
    1  the run failed or ended partial (see the log; the log names the --resume command)
    2  bad arguments / nothing to resume
    3  stopped for a manual ledger check (python -m pulse ledger show)

  Extra arguments are passed through, e.g.  .\scripts\run_weekly.ps1 --fallback-csv export.csv
#>
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

$logDir = Join-Path $repo "data\logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("weekly-{0:yyyy-MM-dd}.log" -f (Get-Date))

"=== {0:u} python -m pulse run --source play --week current {1}" -f (Get-Date), ($args -join " ") |
  Out-File -FilePath $log -Append -Encoding utf8

# Python writes UTF-8; native stderr is merged into the log by cmd so PowerShell 5.1 does not wrap
# each line in an ErrorRecord.
$env:PYTHONIOENCODING = "utf-8"
$quoted = ($args | ForEach-Object { '"{0}"' -f $_ }) -join " "
cmd /c "`"$python`" -m pulse run --source play --week current $quoted >> `"$log`" 2>&1"
$code = $LASTEXITCODE
"=== exit code $code" | Out-File -FilePath $log -Append -Encoding utf8
exit $code
