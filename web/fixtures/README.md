# Web fixtures

Real files from two runs under `data/runs/`, used by mock mode (`npm run dev:mock`) and the web
tests. Regenerate with `python scripts/make_web_fixtures.py`.

| Path | Source |
| --- | --- |
| `runs/20261022-121514/` | A completed dry run: `run.json`, `pulse.json`, `note.txt`, `ranking.json`, `themes.json`, `sanitized.json` |
| `runs/20261022-151338/` | A failed run (Groq daily token limit): `run.json`, `sanitized.json` |
| `config.json` | The `GET /api/config` view of `config.yaml` |
| `ledger.json` | **Synthetic.** Not from a real ledger; the real `data/ledger.json` does not exist yet. It uses the real format and has one `pending` draft (2026-W39) so the banner is visible in mock mode. |

What was changed from the real files:

- `sanitized.json` is trimmed to 150 reviews: the three quoted reviews plus an even spread of the
  rest. `themes.json` assignments are filtered to the same ids. **Mock explorer totals (150)
  therefore differ from the run's `analysed` count (500).** Reviews that look like they contain an
  email address or a 10-digit number are never sampled.
- The ingest stage's cache-location note is removed (it is a filesystem path).
- `config.json` has a placeholder recipient (`product-leads@example.com`) and Doc id
  (`EXAMPLE_DOCUMENT_ID`) in place of the real ones.
- Nothing is copied from the downloaded-review cache; no reviewer names, emails or device data are present.
