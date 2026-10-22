# Scheduling the weekly run

The app does not schedule itself (architecture 4.10). An external scheduler calls one command:

```
python -m pulse run --source play --week current
```

A duplicate or late trigger is harmless: the week is looked up in the publishing ledger first, and a
week that is already published ends in `already_published` without fetching or calling the model.

## Windows (Task Scheduler)

```powershell
.\scripts\register_weekly_task.ps1                  # Mondays 09:00, as the current user
.\scripts\register_weekly_task.ps1 -Day Friday -At 17:30
Start-ScheduledTask -TaskName GrowwWeeklyPulse      # run it now to test the job
Unregister-ScheduledTask -TaskName GrowwWeeklyPulse -Confirm:$false
```

The job runs [scripts/run_weekly.ps1](../scripts/run_weekly.ps1), which uses the repo's `.venv`,
appends to `data/logs/weekly-<date>.log`, and returns the pulse's exit code. "Last Run Result" in
Task Scheduler then shows whether the week worked. It runs only while the user is logged on, and
`StartWhenAvailable` catches up a run missed while the machine was off.

## Linux / macOS (cron)

```
0 9 * * 1  /path/to/repo/scripts/run_weekly.sh
```

## Why not a CI schedule

The Google OAuth tokens live in the MCP server's checkout and the duplicate-protection ledger is a
local file, so the run has to happen on the machine that holds them. A CI runner would start with an
empty ledger every time.

## Exit codes and what to do

| Code | Meaning | Action |
| --- | --- | --- |
| 0 | Published, or the week was already published | None |
| 1 | Failed, `partial`, or `failed_validation` | Read the log. For `partial` or a rejected Google call, fix the cause and run `python -m pulse run --resume <run_id>` (the log prints it); this publishes the saved note without analysing again |
| 2 | Bad arguments, or `--resume` names a run that does not exist | Fix the command |
| 3 | Stopped for a manual check: a previous run died mid-write | `python -m pulse ledger show`, check the Doc / Drafts folder, then `ledger confirm` or `ledger clear` as the message says |

A typical fix for exit 1 is re-authorising Google (`npm run auth` in the MCP server directory) or
sharing the Doc with the authorised account; the error line says which.

## The ledger

`data/ledger.json` (git-ignored) records, per ISO week, whether the Doc section was appended and the
draft created. It is the only protection against a second section or draft, because the MCP server
can read neither. If the file is deleted, the next run for an already-published week publishes
again. Back it up with the rest of `data/` if that matters to you.
