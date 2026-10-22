# Groww Weekly Review Pulse

Reads the last 8-12 weeks of public Google Play reviews for Groww, finds the top themes, and every
week appends a one-page note (3 themes, 3 verbatim user quotes, 3 action ideas, 250 words at most)
to a Google Doc and leaves a Gmail **draft** pointing at it. Nothing is ever sent.

```
Play reviews -> sanitize (PII out) -> theme -> rank -> compose + validate -> note
                                                                  |
                                       Google Workspace MCP server (stdio)
                                          |                          |
                          Google Doc (one section per week)    Gmail draft
```

The design is in [docs/architecture.md](docs/architecture.md), the build plan in
[docs/implementation-plan.md](docs/implementation-plan.md), and hardening results in
[docs/hardening-report.md](docs/hardening-report.md).

## What you need

| | |
| --- | --- |
| Python 3.11+ | the pipeline (`pip install -e ".[dev]"`) |
| Node.js 20+ | to run the Google Workspace MCP server |
| A Groq API key | theming, composing and the eval judge |
| A Google Cloud project | Gmail API and Google Docs API enabled, OAuth client credentials |

This repo holds **no Google code and no Google credentials**. Google is reached only through
[mcp-server-4](https://github.com/saksham20189575/mcp-server-4), which owns the OAuth tokens.

## Setup

### 1. This project

```
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
copy .env.example .env            # then set GROQ_API_KEY
python -m pulse check-config
python -m pulse check-llm         # confirms the key and that each configured model exists
```

### 2. The MCP server (once)

1. Clone it **outside** this repo and use the pinned commit:
   `git clone https://github.com/saksham20189575/mcp-server-4 && cd mcp-server-4 && git checkout 203fa75`.
   Do not modify it.
2. `npm install` then `npm run build`.
3. In Google Cloud: enable the **Gmail API** and **Google Docs API**; configure the OAuth consent
   screen (while the app is in "testing", add the Google account you will use as a test user); create
   an OAuth client with redirect URI `http://localhost:3000/oauth/callback`.
4. In the server directory: `copy .env.example .env` and set `GOOGLE_CLIENT_ID`,
   `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`. Keep `MCP_TRANSPORT=stdio`.
5. `npm run auth` (or `npm run auth -- --callback-server`) and approve in the browser. Tokens are
   written to the server's own `tokens.json`. The scopes are `gmail.compose` and `documents`.
6. Create the Google Doc **by hand** (the server cannot create Docs), for example "Groww Weekly
   Pulse", in the authorised account. Copy the id from its URL (`/document/d/<ID>/edit`).
7. In this repo's [config.yaml](config.yaml) set `mcp.server_dir` (the clone's path),
   `mcp.document_id`, and `draft_to`.
8. Verify: `python -m pulse check-mcp`. It starts the server, lists its tools and calls none. You
   should see the two allowed tools `ok` and `gmail_send_email` listed as `blocked`.

#### When the Google token expires or is revoked

A run fails with `GOOGLE_AUTH_REQUIRED` (or `INSUFFICIENT_SCOPE`) and says what to do: in the MCP
server directory run `npm run auth` again, then rerun. Nothing was written, so the rerun is safe.
Testing-mode OAuth apps expire refresh tokens after 7 days; publishing the consent screen avoids that.
`DOC_PERMISSION_DENIED` means the authorised account lacks edit access to the Doc: share it.

## Configuration

Everything is in [config.yaml](config.yaml) (commented). The ones you are likely to change:

| Setting | Meaning |
| --- | --- |
| `window_weeks` | review window, 8 to 12 |
| `max_themes` | hard cap on clustering themes (5) |
| `pulse.max_words` / `pulse.min_reviews` | note length limit; fewer clean reviews than this stops the run |
| `pulse.max_analysed` | reviews sent to the model; a larger window is sampled and the note says so |
| `models.*` | Groq model ids per task; verify with `check-llm` (Groq retires models) |
| `mcp.*` | server directory, Doc id, the two allowed tool names |
| `draft_to` | who the draft is addressed to |

Secrets are environment variables only (`GROQ_API_KEY`, in `.env`, which is git-ignored).

## Running

```
python -m pulse run --source csv --dry-run          # fixture data, writes data/runs/<id>/ only
python -m pulse run --source play --dry-run         # live reviews, nothing published
python -m pulse run --source play                   # the real thing: Doc section + Gmail draft
python -m pulse run --source play --fallback-csv export.csv   # use a Play Console export if the live fetch fails
python -m pulse run --resume <run_id>               # continue a saved run (below)
python -m pulse audit <run_id>                      # privacy audit of a run (below)
```

`--dry-run` never starts the MCP server, never reads or writes the ledger, and is the safe way to
iterate. A run exits 0 on success, 1 on failure or `partial`, 2 on bad arguments, 3 when it stopped
for a manual ledger check.

**Weekly schedule:** see [docs/scheduling.md](docs/scheduling.md) (Windows Task Scheduler and cron).

### The ledger, and what losing it means

The MCP server can neither read a Doc nor update a draft, and neither of its write tools is
idempotent. So `data/ledger.json` is the **only** protection against a second Doc section or a
second draft for the same week. Per ISO week it records `doc` (`pending` / `appended`) and `draft`
(`pending` / `created`), written before each call and updated right after.

- Rerunning a published week does nothing (no fetch, no model call).
- A week with the Doc section but no draft finishes from the note already in the Doc.
- A step left `pending` (the process died mid-call, or the outcome was unclear) **stops the run**.
  Check the Doc or Drafts folder, then:
  `python -m pulse ledger confirm <week> <doc|draft>` if it is there, or
  `python -m pulse ledger clear <week> <doc|draft>` if it is not. `python -m pulse ledger show` lists everything.
- **If `data/ledger.json` is deleted, the protection is gone**: the next run of an already-published
  week will append and draft again. Back up `data/` if that matters. A corrupt ledger is an error,
  never treated as empty.

### Resume

`--resume <run_id>` (a folder under `data/runs/`) continues a run. If its analysis finished
(`pulse.json` and `note.txt` exist) it goes straight to publishing that note; otherwise the analysis
reruns in the same folder, quickly, because theme assignments are cached. Steps the ledger shows as
done are skipped.

## Reading a run record

Every run writes `data/runs/<run_id>/`:

| File | What it is |
| --- | --- |
| `run.json` | the run record (below) |
| `sanitized.json` | the reviews the model saw: no names or ids, PII replaced by `[redacted]` |
| `themes.json` | themes and each review's assignment |
| `ranking.json` | themes ranked, with the score components |
| `pulse.json` | the structured pulse (3 themes, quotes, actions) |
| `note.txt` | the exact text appended to the Doc |

`run.json` fields: `status` (`completed`, `already_published`, `failed_validation`, `failed`,
`partial`); `stages` (each with `duration_s`, `counts` such as `fetched`/`kept`/`clean`/`themes`,
and `notes`); `theme_scores` (volume, recency, severity and total per theme); `prompt_versions`;
`retries` (compose retries) and `violations` (what failed validation, or why a write failed);
`word_count`; `llm_usage` (calls, tokens, retries, rate limits per task); and `doc_id`, `doc_url`,
`doc_revision_id`, `draft_id` once published.

Statuses: `failed_validation` published nothing. `failed` means the analysis failed, or the Doc
append failed so no draft was tried. `partial` means the Doc section is in place but the draft is
missing; fix the cause and rerun (or `--resume <run_id>`), which retries only the draft.

## Privacy

Reviewer names and ids exist only in the raw fetch (`data/raw/<run_id>/reviews.json`, git-ignored,
kept because sanitizing needs the name to scrub it from review text). `Review`, the model prompts,
the run files, the Doc and the draft carry none of it. To check a run:

```
python -m pulse audit <run_id>                       # against the run's raw cache (live runs)
python -m pulse audit <run_id> --raw-csv file.csv    # against a CSV source
```

It searches every run file, the ledger, logs, and the two texts that leave the machine (the Doc
section and the draft body) for reviewer names, store ids, and the emails, phone numbers, URLs and long
digit strings found in the raw reviews. Findings name the file and kind, never the value. Exit 1 on
any finding.

## Evals

```
pytest                                     # unit tests + the offline deterministic evals (no keys, no network)
python evals/run_golden.py                 # live golden-set run against Groq, with the advisory judge
python evals/run_golden.py --no-judge      # deterministic checks only
python evals/run_golden.py --degrade theme_assign   # must FAIL: proves the evals catch a bad prompt
python evals/run_golden.py --save-baseline          # after an intended change, record a new baseline
```

Change a prompt or a model id only after a golden run passes. The threshold is in
[evals/thresholds.yaml](evals/thresholds.yaml); the recorded baseline in [evals/baseline.json](evals/baseline.json).
CI (`.github/workflows/ci.yml`) runs lint and the offline suite.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `Groq tokens-per-day limit reached` | A daily quota: wait for the stated time, or point that task at another model in `config.yaml` |
| `MCP server is not built` | `npm install && npm run build` in `mcp.server_dir` |
| `GOOGLE_AUTH_REQUIRED` | `npm run auth` in `mcp.server_dir`, then rerun |
| `DOC_PERMISSION_DENIED` | Share the Doc with the account authorised in the MCP server |
| `Stopped: ... marked pending in the ledger` | See "The ledger" above |
| `Only N usable reviews` | Fewer than `pulse.min_reviews` clean reviews in the window; nothing was published |
| Live fetch fails | Retry later, or pass a Play Console export with `--fallback-csv` |
