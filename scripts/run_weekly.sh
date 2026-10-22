#!/usr/bin/env bash
# Weekly trigger for the Groww Review Pulse (Linux/macOS/WSL). Intended for cron, e.g.
#
#   0 9 * * 1  /path/to/Groww-AI-Agent/scripts/run_weekly.sh
#
# Appends output to data/logs/weekly-<date>.log and exits with the pulse's exit code:
#   0 published or already published   1 failed/partial   2 bad arguments   3 manual ledger check
# Extra arguments are passed through (e.g. --fallback-csv export.csv).
set -u
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"
python="$repo/.venv/bin/python"
[ -x "$python" ] || python=python3

mkdir -p data/logs
log="data/logs/weekly-$(date +%F).log"
echo "=== $(date -u +%FT%TZ) python -m pulse run --source play --week current $*" >>"$log"
PYTHONIOENCODING=utf-8 "$python" -m pulse run --source play --week current "$@" >>"$log" 2>&1
code=$?
echo "=== exit code $code" >>"$log"
exit "$code"
