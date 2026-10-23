# Prompt: Build the frontend for Groww Weekly Review Pulse

Paste everything below the line into a coding agent opened at the repo root.

---

## Your task

Build a web frontend (a dashboard) for the existing **Groww Weekly Review Pulse** backend in this repo. The backend turns the last ~10 weeks of public Google Play reviews of the Groww app into a one-page weekly note (top 3 themes, 3 verbatim quotes, 3 action ideas, at most 250 words), appends it to a Google Doc, and creates an unsent Gmail draft. The dashboard lets a product or support lead see **what the latest run did, how many reviews it fetched and kept at each step, what it concluded, and whether it was published**, and lets them start a safe dry run.

Read these first, in order: `docs/problemStatement.md`, `docs/architecture.md`, `src/pulse/models.py`, `src/pulse/pipeline.py`, `src/pulse/orchestrator.py`, `src/pulse/mcp/ledger.py`, `config.yaml`. Then look at one real completed run and one real failed run under `data/runs/` (for example `20261022-121514` completed, `20261022-151338` failed) so you build against real data, not guesses.

## What the backend actually is (constraints that shape the frontend)

- It is a **Python CLI** (`python -m pulse ...`), not a web service. There is **no HTTP API**. All state is files under `data/`.
- Each run writes `data/runs/<run_id>/`. `run_id` is `<window_end YYYYMMDD>-<start HHMMSS UTC>`, with a `-2` style suffix on a collision.

  | File | Present when | Contents |
  | --- | --- | --- |
  | `run.json` | Always, written at the end of the analysis and again after publishing | The run record (shape below) |
  | `sanitized.json` | The run got past sanitizing | The reviews that were analysed (at most 500), shape `Review` below |
  | `themes.json` | Theme stage finished | `{themes: [{theme_id, label, description}], assignments: [{review_id, theme_id}]}` |
  | `ranking.json` | Rank stage finished | `{ranked: [{theme, review_count, share, avg_rating, score, components:{volume,recency,severity}}], top: [theme_id x3]}` |
  | `pulse.json` | Compose and validate passed | The pulse (shape below) |
  | `note.txt` | Same | The exact plain-text note that was published |

- `run.json` is **not written until the analysis ends**, so a run in progress has a folder but no `run.json`. You cannot show per-stage live progress without changing the backend. Show a "running" state with elapsed time and poll for `run.json` to appear. (Typical durations: ingest ~70-80 s, theme ~5-6 min, compose ~20 s.)
- `data/ledger.json` is the publishing ledger, keyed by week label then step (`doc`, `draft`). It only exists after the first non-dry-run publish. Each step has a state (`appended`/`created` = done, `pending` = outcome unknown) plus details (`run_id`, `document_id`, `revision_id`, `characters_appended`, `draft_id`, `thread_id`, `subject`). Read `src/pulse/mcp/ledger.py` for the exact file format before parsing it. Treat a missing file as "nothing published from this machine".
- `config.yaml` holds the settings the dashboard should show read-only.

### Privacy and safety rules (non-negotiable)

1. **Never read or serve `data/raw/`.** It is the raw review cache and contains reviewer names. The frontend and its API must not touch it.
2. Never show or invent reviewer names, emails, device ids or any identity. `review_id` is an anonymous salted hash; it is fine to show truncated.
3. The API is **read-only by default**. The only write action is starting a run, and it **defaults to `--dry-run`**. Publishing (a run without `--dry-run`) needs an explicit confirmation dialog stating that it appends a section to the Google Doc and creates a Gmail draft, and that nothing is emailed. Do not add any "send email" feature; the backend deliberately cannot send.
4. Do not edit the ledger from the UI. When a step is `pending`, show the exact CLI commands to run by hand (see "Ledger" below) with copy buttons.
5. Do not add Google, OAuth or Gmail code to the frontend or API. Doc and draft links come from `run.json`.
6. Never print `.env` values or `GROQ_API_KEY`. Do not expose `mcp.server_dir`.

## Architecture to build

Create two new top-level folders and leave `src/pulse/` unchanged.

- `api/`: a small **FastAPI** app (Python 3.13, same virtualenv). It only reads `data/` and `config.yaml` (use `pulse.config.load_config` so paths match) and, for the one write action, spawns `python -m pulse run ...` as a subprocess. Bind to `127.0.0.1`. Allow CORS for the Vite dev origin only.
- `web/`: **React + TypeScript + Vite**, Tailwind, TanStack Query for fetching/polling, Recharts for charts. Light and dark mode. Responsive down to tablet. Accessible (labels, contrast, keyboard focus, chart data also available as a table).

### API endpoints

| Endpoint | Returns |
| --- | --- |
| `GET /api/runs` | Newest first. Per run: `run_id`, `week_label`, `status`, `started_at`, `duration_s` (sum of stages), `fetched`, `clean`, `analysed`, `word_count`, `has_pulse`, `doc_url`, `draft_id` |
| `GET /api/runs/{run_id}` | `run.json` plus `pulse`, `note`, `ranking` and `themes` when those files exist (null otherwise) |
| `GET /api/runs/{run_id}/reviews` | The analysed reviews joined to their theme: `review_id`, `rating`, `title`, `text`, `date`, `app_version`, `theme_id`. Supports `theme`, `rating`, `q` filters and pagination. Reads `sanitized.json` and `themes.json` only |
| `GET /api/ledger` | Weeks and their `doc` / `draft` state and details, or an empty object |
| `GET /api/config` | The read-only subset of `config.yaml` listed under "Settings" |
| `POST /api/runs` | Body `{source: "play"|"csv", dry_run: true, as_of?: "YYYY-MM-DD"}`. Spawns the CLI, returns `{pid, started_at}`. Refuse if a run is already active. `dry_run: false` must also require `confirm: "publish"` in the body |
| `GET /api/runs/active` | Whether a run is in progress, its elapsed seconds, and the CLI's last output line if captured |

Validate every `run_id` against `^\d{8}-\d{6}(-\d+)?$` and every path against the runs directory (no path traversal). Handle half-written or missing files without a 500: return what exists.

The CLI exit codes are `0` success, `1` failed / partial / validation failed, `2` bad arguments or cannot resume, `3` stopped for a manual ledger check. Map them to clear messages.

## Data model (what the files contain)

```ts
type RunStatus = "running" | "completed" | "failed_validation" | "partial" | "failed" | "already_published";

interface Run {                      // run.json, contains no PII
  run_id: string; week_label: string;           // "2026-W43"
  status: RunStatus;
  started_at: string;                           // ISO, UTC
  stages: { name: "ingest"|"sanitize"|"theme"|"rank"|"compose"|"render"|"publish_doc"|"publish_draft";
            duration_s: number; counts: Record<string, number>; notes: string[] }[];
  theme_scores: Record<theme_id, { volume: number; recency: number; severity: number;
                                   score: number; review_count: number; avg_rating: number }>;
  prompt_versions: { theme_assign: string; compose: string };   // "theme_assign@1"
  retries: number;                              // compose retries
  violations: string[];                         // failure reasons or guardrail messages
  word_count: number;
  llm_usage: Record<"theme_assign"|"compose", { calls; prompt_tokens; completion_tokens; retries;
                                               rate_limited; invalid_replies; waited_s }>;
  doc_id: string|null; doc_url: string|null; doc_revision_id: string|null; draft_id: string|null;
}
interface Pulse {                    // pulse.json
  week_label: string; window_start: string; window_end: string;   // ISO dates
  review_count: number;             // clean reviews in the window
  analysed_count: number|null;      // set when only a sample was analysed
  themes: { theme_id; label; summary; share }[];                  // exactly 3
  quotes: { text; theme_id; rating; review_id }[];                // exactly 3, verbatim
  actions: { text; theme_id }[];                                  // exactly 3
}
interface Review { review_id; store; rating: 1|2|3|4|5; title; text; date; app_version: string|null }
```

Stage `counts` keys you must understand (from a real run):

- `ingest`: `fetched` (reviews kept from the store), `pages`, `items_seen`, `outside_window` (seen but older than the window, so dropped), `duplicates`, `invalid`, `retries`, `truncated` (1 if a page or review limit cut the fetch short), `window_start_reached` (1 if the fetch reached the start of the window; 0 means the oldest reviews may be missing).
- `sanitize`: `fetched` (in), `dropped_short` (under 4 words), `dropped_non_english`, `dropped_duplicate`, `dropped_invalid`, `clean` (= usable reviews, what the pulse calls `review_count`), `analysed` (sample sent to the model, capped at 500), and PII redaction counts `redacted_author_name`, `redacted_email`, `redacted_handle`, `redacted_id_token`, `redacted_number`.
- `theme`: `themes` (including the "Other" bucket), `llm_calls`, `cache_hits`, `unknown_labels`, `unlabeled_defaulted`.
- `rank`: `ranked`, `selected` (3). `compose`: `attempts`. `render`: `words`.
- `publish_doc` has `characters_appended`; its `notes` may say it was skipped because the ledger already had it.

## Screens and what each must show

### 1. Overview (the home page: the latest run)

A header with the **week label**, the **review window** (`window_start` to `window_end`, formatted like "13 Aug - 22 Oct 2026", plus "10 weeks"), the run's **status badge**, when it ran (show in IST and UTC on hover), and total duration. Then:

**A. Review count funnel for this run** (this is the key requirement). Show it as a horizontal funnel or stepped bar with a number and percentage at every step, computed from the latest run:

1. **Fetched from Google Play**: `ingest.fetched` (e.g. 10,332), with sub-facts: pages, reviews seen vs. kept, `outside_window` dropped. Show a warning chip if `window_start_reached` is 0 or `truncated` is 1: "Fetch stopped early, oldest reviews may be missing".
2. **Dropped during cleaning**, itemised: too short (`dropped_short`), non-English, duplicate, invalid. Check that fetched minus these equals `clean`; if it does not, show the discrepancy instead of hiding it.
3. **Clean reviews**: `sanitize.clean` (e.g. 3,029). This is the pulse's `review_count`.
4. **Analysed by the model**: `sanitize.analysed` (e.g. 500). If it is less than `clean`, say plainly: "A fixed random sample of 500 of 3,029 clean reviews was analysed."

Also show the **minimum-reviews rule** (`pulse.min_reviews`, 20): a run with fewer clean reviews stops, so show the margin.

**B. Top themes** (exactly 3 cards, ranked): label, one-sentence summary, share, review count, average rating (stars), and the score with its three components (volume, recency, severity) as a small stacked bar with a tooltip explaining the formula `0.5 x volume + 0.2 x recency + 0.3 x severity` (take weights from `/api/config`, do not hardcode). **Important accuracy detail:** `share` is a fraction of the *analysed sample* (44 of 500 = 8.8%), but the published note calls it "% of reviews". Label it "of analysed reviews" in the UI, and show the sample size next to it.

**C. User quotes** (3): the verbatim quote, star rating, theme chip. Clicking a quote opens the source review (via `review_id` from the reviews endpoint) with the quote highlighted inside the full text.

**D. Action ideas** (3): the text with its theme chip, numbered.

**E. The published note**: render `note.txt` exactly as published (monospace or document style), with a word counter gauge "192 / 250 words" (limit from config), a copy button, and a "what was published" label.

**F. Publishing status card**: Google Doc (link from `doc_url`, section appended Y/N, `doc_revision_id`, characters appended), Gmail draft (draft id, recipient from config, subject `Groww Weekly Review Pulse - <week>`, and a fixed line "Draft only - never sent"). For `already_published`, `partial` and failed states see "Run states" below.

**G. Guardrail checklist**: a row of pass/fail items for the run, each derived from the data (do not just print "pass" for everything):

- 3 themes in the note (and at most 5 clustering themes excluding "Other")
- 3 quotes, each tied to a theme, all verbatim from analysed reviews (check each `quote.text` appears, case/whitespace-insensitive, in the review with that `review_id` from `/reviews`)
- 3 actions, each referencing one of the 3 top themes
- Word count at most `max_words`
- No reviewer identity: show the redaction counts (`redacted_author_name`, `redacted_email`, `redacted_handle`, `redacted_id_token`, `redacted_number`) as evidence that scrubbing happened, and a one-line statement that raw reviews are never shown here
- Review window between 8 and 12 weeks (compute from `window_start`/`window_end`)
- Compose retries used and any `violations`

### 2. Run detail (`/runs/:runId`)

- **Pipeline timeline**: one row per stage with duration, key counts, and `notes` (for example "analysing a sample of 500 of 3029 reviews"). Show the slowest stage. Total time.
- **Theme table (all themes incl. "Other")**: review count, share, average rating, score, volume/recency/severity, and a marker for "selected top 3" or "excluded". Explain beside it that "Other" is a catch-all and is never one of the top 3 even when it scores highest (in run `20261022-121514`, "Other" is 60% of the sample and ranks first by score, so this will confuse people unless explained).
- **LLM usage**: per task (`theme_assign`, `compose`) calls, prompt and completion tokens, retries, rate-limit hits, invalid replies, seconds waited; the model ids and `prompt_versions`. Take model ids from config.
- **Violations**: list `violations` verbatim, styled by severity.
- **Analysed reviews explorer**: a filterable, paginated table of the reviews the model saw (rating, date, app version, theme, title and text), with filters for theme and rating, text search, and a link from each top-3 quote. Show charts: rating distribution (1-5), reviews per week across the window, and average rating per theme. These come from `sanitized.json` plus `themes.json`, so they describe the **analysed sample**, and the chart titles must say so.

### 3. Run history (`/runs`)

A table of every run folder, newest first: run id, week, status badge, started, duration, fetched, clean, analysed, words, doc link, draft id. Filter by status. A trend chart across completed runs of fetched, clean and analysed counts, and word count. Failed runs stay visible (they have ingest and sanitize counts even when the model step failed). Group or mark runs sharing a `week_label`, because several runs can exist for one week.

### 4. Publishing ledger (`/ledger`)

One row per week with the `doc` and `draft` states (done / pending / not started), with ids, the run that wrote it, and a link to the Doc. If any step is `pending`, show a prominent banner: "Outcome unknown: an earlier run died while writing. Check the Doc or Drafts folder, then run one of these:" with copy-able commands:

```
python -m pulse ledger confirm <week> <doc|draft>   # it is there
python -m pulse ledger clear <week> <doc|draft>     # it is not there
```

Add a short explainer that losing `data/ledger.json` loses duplicate protection.

### 5. Settings (`/settings`, read-only)

From `/api/config`: app package (`com.nextbillion.groww`, `en`/`in`), `window_weeks`, `max_themes`, the taxonomy list, ranking weights and recency window, `max_words`, `min_reviews`, `min_words`, `max_analysed`, model ids per task, batch size, `draft_to`, and the Doc link built from `mcp.document_id` (`https://docs.google.com/document/d/<id>/edit`). Do not include secrets or filesystem paths.

### 6. Run control (a panel or modal on Overview)

A "Run now" button with: source (Play Store live / CSV fixture), optional "as of" date, and a **Dry run** toggle that is on by default. While running: elapsed timer, indeterminate progress, disabled button, and a note "run files appear when the analysis ends (usually 6-8 minutes)". When finished, jump to the new run. Turning dry run off opens the confirmation dialog described under "Privacy and safety rules". Surface the CLI's stderr summary on failure.

## Run states the UI must handle (design each explicitly)

| Status | What to show |
| --- | --- |
| `completed` | Full overview. Doc and draft links if published. A dry run is `completed` with `doc_url` and `draft_id` null: label it "Dry run - nothing published" |
| `already_published` | The week was already in the ledger so nothing was fetched or analysed. Show the Doc link and draft id from the ledger, and no funnel (stages are empty). Say "Already published for 2026-Wxx" |
| `failed` | Show whatever stages ran. Run `20261022-151338` has full ingest and sanitize counts but no themes because the model hit Groq's daily token limit; show the funnel up to the failure point, the stage that stopped, and `violations` as the reason. Offer no publish action |
| `failed_validation` | The note failed the guardrails after retries. Nothing was published. Show the violations and retry count |
| `partial` | The note is in the Google Doc but the Gmail draft failed. Show the Doc as done, the draft as failed, and the CLI command `python -m pulse run --resume <run_id>` to retry only the draft |
| `running` | Folder exists but no `run.json` yet. Elapsed time, no numbers |
| ledger step `pending` | The manual-check banner described above |

Also handle: no runs at all (empty state with a "Run a dry run" call to action), and malformed or partial files (show a small "data unavailable" message in that card, not a broken page).

## Formatting rules

- Numbers with thousands separators (`10,332`), percentages with at most one decimal, ratings as stars with the numeric value.
- Dates like "13 Aug - 22 Oct 2026"; times in IST with UTC on hover.
- Status colours and icons that do not rely on colour alone.
- Show `week_label` (ISO week, `2026-W43`) prominently; it is the unit the ledger uses.
- Use the real current run's numbers as realistic seed values for tests, not lorem ipsum.

## Deliverables

1. `api/` and `web/` with a README section on running both (`uvicorn` and `npm run dev`) on Windows, from the repo root, using the existing `.venv`.
2. Fixtures in `web/fixtures/` copied from one completed and one failed run folder (copy only `run.json`, `pulse.json`, `note.txt`, `ranking.json`, `themes.json`, and a trimmed `sanitized.json`; never `data/raw/`). Add a mock mode so the UI runs without the backend.
3. Tests: API tests with `pytest` using a temporary `data/` directory (including a path-traversal attempt, a missing file, a half-written run, and a `pending` ledger entry); component tests for the funnel arithmetic and each run state.
4. A final check that **nothing in `api/` or `web/` reads `data/raw/`**, and that the `POST /api/runs` with `dry_run: false` is refused without confirmation.

Before writing code, give me a short plan (screens, components, endpoint list) and wait for my confirmation if anything above conflicts with the repo as you find it.
