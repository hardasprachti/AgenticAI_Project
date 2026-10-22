<#
.SYNOPSIS
  Registers (or replaces) a weekly Windows Task Scheduler job that runs scripts\run_weekly.ps1.

.EXAMPLE
  .\scripts\register_weekly_task.ps1                      # Mondays 09:00
  .\scripts\register_weekly_task.ps1 -Day Friday -At 17:30
  Unregister-ScheduledTask -TaskName GrowwWeeklyPulse -Confirm:$false   # remove it

.NOTES
  Runs as the current user, only while logged on (the MCP server's Google tokens live in that
  user's checkout). StartWhenAvailable makes a missed run (laptop asleep at 09:00) happen at next
  wake-up; the ledger makes a duplicate trigger harmless.
#>
param(
  [string]$TaskName = "GrowwWeeklyPulse",
  [ValidateSet("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")]
  [string]$Day = "Monday",
  [string]$At = "09:00"
)
$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "run_weekly.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
  -Description "Groww Weekly Review Pulse: python -m pulse run --source play" -Force | Out-Null
Write-Host "Registered '$TaskName': every $Day at $At. Logs: data\logs\. Test now with:"
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
