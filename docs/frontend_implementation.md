# Groww Weekly Review Pulse Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Commit steps run only when the person has asked for commits.

**Goal:** A read-only web dashboard (plus a small local API) that shows what the latest Groww Weekly Review Pulse run fetched, kept, concluded and published, and can start a safe dry run.

**Architecture:** The backend is a Python CLI with no HTTP surface; all state is files under `data/`. A new `api/` FastAPI app reads those files (never `data/raw/`) and spawns `python -m pulse run` for the one write action. A new `web/` React app renders them, using the Stitch mockups for layout and the design system for tokens, but with real numbers and without the mockups' invented features (see "Where the mockups are wrong").

**Tech Stack:** Python 3.13, FastAPI, uvicorn, pytest + httpx TestClient; React 18, TypeScript, Vite, Tailwind 3.4 (JS config, as in the mockups), TanStack Query 5, React Router 6, Recharts 2, Vitest + Testing Library + vitest-axe, `@fontsource` fonts, `lucide-react` icons. Pin exact versions at install time.

**Spec:**
- `docs/frontend-prompt.md` (behaviour; wins on any conflict)
- `docs/implementation-plan.md` and `docs/architecture.md` (backend contract: ledger protocol in Phase 6, statuses in section 11)
- `stitch_groww_review_pulse_dashboard/emerald_pulse_analytics/DESIGN.md` (tokens, components)
- `stitch_groww_review_pulse_dashboard/{overview,run_detail,run_history,publishing_ledger}_groww_review_pulse/{screen.png,code.html}` (layout reference only)

## Global Constraints

Every task's requirements include these.

- `src/pulse/` is **not modified**. Only `api/`, `web/`, `tests/api/`, `pyproject.toml` (one optional-dependency extra) and docs are touched.
- **Never read, list or serve `data/raw/`.** No identity is ever shown or invented: no reviewer names, emails, device ids, device models. `review_id` is shown truncated (`209a66…2916a18` form: first 6, last 7 is fine; be consistent).
- API binds `127.0.0.1`; CORS allows only the Vite dev origins (`http://localhost:5173`, `http://127.0.0.1:5173`).
- API is read-only except `POST /api/runs`, which **defaults to `--dry-run`**. `dry_run: false` additionally requires body `confirm: "publish"` and a UI confirmation dialog saying it appends a section to the Google Doc and creates a Gmail draft and that **nothing is emailed**. No "send email" feature anywhere.
- The UI never edits the ledger and never runs `--resume`; for `pending` steps and `partial` runs it shows copyable CLI commands.
- No Google, OAuth or Gmail code in `api/` or `web/`. Doc/draft links come from `run.json`. Never expose `.env` values, `GROQ_API_KEY`, `mcp.server_dir`, filesystem paths, or `Config.raw`.
- Every `run_id` matches `^\d{8}-\d{6}(-\d+)?$` and every resolved path stays inside `<data_dir>/runs/`. Missing or half-written files never produce a 500: return what exists.
- **All JSON files are read with `encoding="utf-8"`.** `data/runs/20261022-121514/sanitized.json` raises `UnicodeDecodeError` under Windows' default cp1252.
- CLI exit codes: `0` success, `1` failed/partial/validation failed, `2` bad arguments or cannot resume, `3` stopped for a manual ledger check.
- Formatting: thousands separators (`10,332`); percentages at most one decimal; ratings as stars **plus** the number; dates like `13 Aug - 22 Oct 2026` (hyphen, as the spec writes it); times in IST (`Asia/Kolkata`) with UTC on hover; `week_label` (`2026-W43`) prominent; status never conveyed by colour alone (icon + text).
- Ranking weights, `max_words`, `min_reviews`, model ids, etc. come from `GET /api/config`; **no constant is hardcoded in the web app**.
- Light and dark mode; responsive down to tablet (768px); keyboard-focusable; each chart has a "View as table" toggle.

## Review Focus

Failure modes the spec implies but no screen describes, most likely first. Each has its pinning test in the task named in brackets.

1. **Windows default encoding.** Reading `sanitized.json` without `encoding="utf-8"` crashes on the real data (observed). Reviews contain `₹`, Hinglish and emoji. [Task 3]
2. **A run that died leaves a folder with no `run.json` forever**, which the spec's rule would show as "running" indefinitely and which would block `POST /api/runs`. Needs a staleness rule. [Task 2, Task 5]
3. **Corrupt or half-written `ledger.json` / `run.json` / `themes.json`.** The CLI refuses to treat a corrupt ledger as empty because that silently disables duplicate protection; the API must not report "nothing published" either. [Task 2, Task 4]
4. **Missing counts and divide-by-zero in the funnel.** The failed run's `theme` stage has `counts: {}` and `duration_s: 0.0`; an empty window gives `fetched: 0`; pre-sanitize failures have no `sanitize` stage at all. No `NaN%`, no crash. [Task 9]
5. **Double submit and concurrent runs.** Double-clicking "Run now", two browser tabs, or a CLI run started by hand or by the scheduler must not start two runs, and the publish confirmation must not be bypassable by a stale form state. [Task 5, Task 12]

---

## What the real repo says (read before coding)

Facts verified against the repo on 2026-10-22 that shape the build:

- `data/` holds 10 run folders, all `2026-W43`: 4 `completed` (none published: `doc_url`, `draft_id` are `null`), 6 `failed` (each has `run.json` + `sanitized.json` only; stages `ingest`, `sanitize`, `theme`). **There is no `data/ledger.json`**, no `partial`, `failed_validation` or `already_published` run on disk. Those states exist only in code, so they are built from factories and hand-made fixtures (Task 8).
- A **dry run has no flag in `run.json`**. It is `status == "completed"` with `doc_url == null`. `isDryRun(run)` encodes that and only that.
- `run.json` is written at the end (`pipeline.py:116`); the folder is created at the start (`pipeline.py:102`). `already_published` runs also get a folder and `run.json` with empty `stages` (`orchestrator.py:190`).
- Ledger on disk: `{ "<week>": { "doc": {state, run_id, document_id, revision_id, characters_appended}, "draft": {state, run_id, draft_id, thread_id, subject} } }`, `state` ∈ `appended|created|pending`. An unambiguous failed write **clears** the entry, so the ledger has no "failed" state; a draft that failed shows up as a week with `doc` done and no `draft`. A step done by `ledger confirm` carries `confirmed_by_hand: true`.
- `Config` is `pulse.config.load_config`; `ranking` is flat (`cfg.ranking.volume/recency/severity/recency_window_weeks`), models are `cfg.models`, batch size `cfg.llm.batch_size`. `run.json` does **not** record model ids, so the UI labels them "configured now".
- `sanitize.fetched − (dropped_short + dropped_non_english + dropped_duplicate + dropped_invalid) = clean` holds on real data (10,332 − 7,303 = 3,029). `ingest.items_seen − outside_window − duplicates − invalid = fetched` also holds (10,400 − 68 = 10,332).
- `theme_scores[id].volume` equals the theme's share of the analysed sample (302/500 = 0.604 for `other`), and `score = 0.5·volume + 0.2·recency + 0.3·severity` (customer-support: 0.044 + 0.0154 + 0.2795 = 0.339). Theme counts sum to the sample (302+44+84+48+13+9 = 500).
- The sample is "the first 500 by salted-hash id" (`pipeline.py:79`), i.e. a uniform random draw with no seed to display.
- Real top 3 (order by score, `Other` excluded): Customer Support, Trading Experience and App Performance, Payments and Withdrawals. `Other` is 60.4% and scores highest (0.493) yet is excluded.
- Real total duration of `20261022-121514` is 435.8 s (7m 16s); the theme stage is 77.1% of it. Real LLM waiting: `theme_assign` 13 calls, 15 rate-limit retries, 286 s waited.
- The failed run `20261022-151338` stops at `theme` (last recorded stage, zero counts); `violations[0]` is the Groq tokens-per-day message.

## Where the mockups are wrong (decisions)

The mockups are layout and style references. Their data is invented. Build the layout; do not copy the content.

| Mockup shows | Reality / rule | Decision |
| --- | --- | --- |
| Themes "SIP Auto-Pay", "Market Open Lag", "Instant Withdrawal"; scores 0.742/0.698/0.621 | Real themes and scores differ (see above) | Render from `pulse.json` / `ranking.json`. Show score as the three **weighted contributions** (`weight × component`) in a stacked bar on a 0–1 scale, not normalised to the top score. |
| "14.2% share · 71 of 500 reviews", star "1.8 / 5.0" | `share` is of the analysed sample; note.txt says "% of reviews" | "8.8% of analysed reviews · 44 of 500", avg rating as stars + `1.3`. Footnote: the published note labels this "% of reviews". |
| Status "COMPLETED (Published)" with Doc link for the real run | Real run is a dry run | Label `Completed · Dry run, nothing published`; hide "Open Google Doc" when `doc_url` is null. |
| Duration 6m 42s | Sum of stage durations is 7m 16s | Compute from `stages`. |
| Funnel: seen 14,820, outside window −4,488, dropped 3,842 / 2,109 / 1,240 / 112 | Real: seen 10,400, outside −68, dropped 7,159 / 82 / 62 / 0 | Real counts; keep the "10,332 − 7,303 = 3,029" arithmetic line as a **computed** check that shows the discrepancy when it fails. |
| "Integrity Hash", "SHA-256", "Seed: 42", "Deterministic Determinism v2.8", "Pipeline Engine v2.8.4 / Telemetry Synced", "Sync: 0 errors / Active lock: None", ledger checksum | Not in any data | Remove all. Sidebar footer shows API connection state (and a "Mock data" pill in mock mode). |
| "Sample capped … to prevent rate spikes" | Config says a fixed sample keeps shares unbiased | Copy: "A fixed random sample of 500 of 3,029 clean reviews was analysed." |
| Action cards with "Banking Infrastructure Pod", titles, "Impact: High", "T-Shirt: M" | Actions are `{text, theme_id}` only | Number + text + theme chip. |
| Quote "Inspect" alert with timestamp, "Google Play India", device | Reviews have rating, title, text, date, `app_version` only | Side drawer: stars, date, app version, theme, title, full text with the quote highlighted. No devices. |
| Note text in a different format; Copy copies a third text | The published artifact is `note.txt` | Render and copy **exactly** `note.txt`. |
| Doc title, `rev_8492041`, "1,284 chars", recipient `product-leads@groww.in` | Revision from `run.json`; chars from the `publish_doc` stage counts; recipient is `draft_to` | Use those. Drop the doc title. |
| "7 / 7 Gates Passed", "4,821 names, 189 emails, 92 tokens" | Gates are computed; real redactions are 34/3/3/2/3 | Count passes honestly; an unavailable gate is neutral, never a pass. |
| Run detail: 8 stage cards incl. publish, "Bottleneck 79.1%", "Llama 3.3 70B", "Est. Cost $0.0384", "Chunk 45", "Temperature 0.20", "Schema Check: Passed", weights 0.40/0.30/0.30 | A dry run records 6 stages; theme is 77.1%; models are gpt-oss; batch is 40; no cost, temperature or schema data; weights are 0.5/0.2/0.3 | Show the 8 known stage names in order; unrecorded ones are "Not run". Models/weights/batch from `/api/config`, labelled "configured now". Show total tokens (53,771) and waited seconds, no cost. |
| Matrix with "Rank Cutoff #4/#5", Other as "—" | Other has a real score rank (#1) | Columns: score rank, theme, reviews, share, avg rating, volume, recency, severity, score, status (`Selected (Top n)` / `Not selected` / `Excluded: catch-all`). Explainer beside it. |
| Explorer: "Android 14", "iOS 18", "stratified", "Export Sample CSV", weekly counts of 10,332 | No device data; sample is random; per-week counts exist only for the 500 | No devices, no export; chart titles say "analysed sample". |
| History: "24 runs", 8-week bars W36–W43, "-18s vs previous", "12,410+ ingested", "Cadence" dropdown, "Export CSV", SHA-256 footer, `--force-republish` | 10 runs, all one week; no such flag | KPI tiles computed from real runs; trend is per **completed run** (x = started_at); week filter from real weeks; no export, no hash, no `--force-republish`. |
| History: failed run shows analysed `0` | `sanitize.analysed` is 500 even though the model stage failed | Show 500 muted with tooltip "sampled; model step failed". |
| History: "Resume Draft" button, "Terminal logs" link | UI never runs `--resume`; no logs exist | Copyable `python -m pulse run --resume <run_id>`; no logs link. |
| Ledger: 5 fake weeks, "Failed" draft state, `unverified_lock`, "View Raw JSON" toast | No file; no failed state | Empty state when absent; outcomes derived from real states (see Task 15). |
| Ledger card "commit data/ledger.json… S3 snapshots" | `data/*` is git-ignored on purpose | Replace with: losing `data/ledger.json` loses duplicate protection; back it up outside Git. |
| Hosted logo image (googleusercontent URL), Docs/GitHub links, avatar, "Read Policy Doc" | Hotlinking and dead links | Inline SVG mark; none of the rest. |
| Hidden scrollbars (`::-webkit-scrollbar{display:none}`), pulsing `animate-ping`, 10px text | Accessibility | Do not port; respect `prefers-reduced-motion`; minimum text 11px (`label-sm`). |

**Design-token conflicts (resolved here, once):**

- DESIGN.md prose says primary `#00B386`; its frontmatter and the mockup's Tailwind config say `primary #006c4f`, `primary-container #00b386`. Port the **mockup's `tailwind.config`** (it rendered the screenshots): `primary #006c4f` for text/active nav, `primary-container #00b386` for fills.
- White text on `#00B386` is about 2.7:1, below AA. Primary buttons use `on-primary-container #003d2c` on `#00b386` (as the mockup does), not the white text DESIGN.md states.
- Status badge colours come from the DESIGN.md prose (Completed `#00875A` on `#E3FCEF`, Running `#0052CC` on `#DEEBFF`, Partial `#B76E00` on `#FFF0B3`, Failed `#DE350B` on `#FFEBE6`, Dry Run `#5243AA` on `#EAE6FF`, Pending `#475569` on `#F1F5F9`). Task 7 tests every pair at 11px against 4.5:1; where one fails, darken the text hex until it passes and note the change in `tokens.ts`.
- There is no dark design. Derive dark tokens (Task 7): `surface` family from `#0b1c30`/`#213145`, keep emerald as the accent.

## File Structure

```
api/
  __init__.py
  main.py            create_app(settings) -> FastAPI; CORS; router wiring
  settings.py        Settings (data_dir, repo_root, config) from pulse.config.load_config
  safe_paths.py      RUN_ID_RE, run_dir(settings, run_id) -> Path (raises NotFound)
  files.py           read_json(path) -> tuple[Any|None, str|None]  (utf-8; never raises)
  schemas.py         Pydantic response models (explicit allow-lists)
  runs.py            list_runs, get_run, run_status derivation, durations
  reviews.py         reviews(run_id, filters), reviews_summary(run_id)
  ledger_view.py     read_ledger(settings) -> LedgerView
  controller.py      RunController: start(), active(), exit-code messages
  routes.py          APIRouter with the 7 endpoints
tests/api/
  conftest.py        tmp data dir builder, client fixture, sentinel-name raw cache
  test_safe_paths.py test_config_frontend.py test_runs.py test_reviews.py
  test_ledger_frontend.py test_controller.py test_privacy.py
web/
  fixtures/          real run files (see Task 8) + synthetic ledger
  src/
    styles/tokens.ts, index.css, tailwind.config.ts (root)
    lib/ format.ts, funnel.ts, themes.ts, stages.ts, guardrails.ts, status.ts, ledger.ts
    api/ client.ts, types.ts, mock.ts, hooks.ts
    components/ AppShell, StatusBadge, Stars, ThemeChip, Card, CopyButton, ChartFrame, DataUnavailable, ConfirmPublishDialog, RunControl, ReviewDrawer
    pages/ Overview/, RunDetail/, RunHistory/, Ledger/, Settings/
    test/ factories.ts, setup.ts
```

---

## Task 1: API scaffold, safe paths, `/api/config`

**Files:**
- Create: `api/__init__.py`, `api/main.py`, `api/settings.py`, `api/safe_paths.py`, `api/files.py`, `api/schemas.py`, `api/routes.py`, `tests/api/conftest.py`, `tests/api/test_safe_paths.py`, `tests/api/test_config_frontend.py`
- Modify: `pyproject.toml` (add `api = ["fastapi>=0.115", "uvicorn>=0.30", "httpx>=0.27"]` under `[project.optional-dependencies]`)

**Interfaces:**
- Produces: `Settings(config: Config, data_dir: Path, repo_root: Path)` + `Settings.load(config_path: Path = DEFAULT_CONFIG_PATH) -> Settings`; `create_app(settings: Settings | None = None) -> FastAPI`; `RUN_ID_RE = re.compile(r"^\d{8}-\d{6}(-\d+)?$")`; `safe_run_dir(settings, run_id: str) -> Path` raising `RunNotFound`; `read_json(path: Path) -> tuple[Any | None, str | None]` returning `(data, None)` or `(None, "missing" | "unreadable")`; `ConfigView` schema (below). `conftest.py` provides `make_data_dir(tmp_path) -> Settings` and `client` fixture.

`ConfigView`: `app{play_package, play_lang, play_country}`, `window_weeks`, `max_themes`, `taxonomy[]`, `ranking{weights{volume,recency,severity}, recency_window_weeks}`, `pulse{max_words,min_reviews,min_words,max_analysed}`, `models{theme_assign,compose,judge}`, `batch_size`, `draft_to`, `doc_url` (built as `https://docs.google.com/document/d/<mcp.document_id>/edit`, or `null`). Nothing else.

- [ ] **Step 1: Write failing tests**
  - `test_run_id_regex_accepts`: `20261022-121514`, `20261022-121514-2`.
  - `test_run_id_regex_rejects`: `..`, `20261022-121514/..`, `20261022-12151`, `20261022-121514-`, `2026-10-22`, `20261022-121514\..\x`.
  - `test_traversal_is_404`: `client.get("/api/runs/..%2f..%2fconfig.yaml")` and `client.get("/api/runs/%2e%2e")` return 404 (not 500, not file contents).
  - `test_config_is_allow_list`: response keys equal exactly the `ConfigView` keys; response text contains neither `server_dir` nor the configured server path nor `GROQ`; `doc_url` ends with `/edit`; `ranking.weights == {"volume": 0.5, "recency": 0.2, "severity": 0.3}` for the repo `config.yaml`.
  - `test_read_json_missing_and_garbage`: `(None, "missing")` for absent, `(None, "unreadable")` for `{"a":` .
- [ ] **Step 2: Run** `pytest tests/api -v` → FAIL (`ModuleNotFoundError: api`).
- [ ] **Step 3: Implement** the modules above. `safe_run_dir` checks the regex first, then `resolve()`s and asserts the result's parent is `(data_dir/"runs").resolve()`; the `GET /api/config` route builds `ConfigView` field by field from `Settings.config` (never `model_dump` of `Config`). Install the CORS middleware with the two Vite origins only.
- [ ] **Step 4: Run** `pytest tests/api -v` → PASS.
- [ ] **Step 5: Commit** `feat(api): scaffold, safe run-id paths, read-only config endpoint`

## Task 2: Run list and run detail

**Files:**
- Create: `api/runs.py`, `tests/api/test_runs.py`
- Modify: `api/schemas.py`, `api/routes.py`

**Interfaces:**
- Consumes: `safe_run_dir`, `read_json`, `Settings`.
- Produces: `RunSummary` (`run_id, week_label, status, started_at, duration_s, fetched, clean, analysed, word_count, has_pulse, doc_url, draft_id, is_dry_run`); `RunDetail` (`run: dict | None`, `status`, `pulse`, `note: str | None`, `ranking`, `themes`, `file_errors: dict[str, str]`); `derive_status(run_json: dict | None, folder: Path, now: float, active_run_id: str | None) -> str`; constant `RUNNING_STALE_AFTER_S = 1800`.

`status` is one of the six backend values plus two derived values the spec lacks: `interrupted` (no `run.json`, not the controller's active run, newest file/folder mtime older than `RUNNING_STALE_AFTER_S`) and `unreadable` (`run.json` exists but is not valid JSON). A folder with no `run.json` and a fresh mtime, or owned by the controller, is `running`. For a run without `run.json`: `started_at` = folder creation time (ISO, UTC), `week_label` = ISO week of the date in `run_id`, all counts `null`. `duration_s` = sum of `stages[].duration_s` (rounded to 3 places). `fetched/clean/analysed` come from `ingest.fetched`, `sanitize.clean`, `sanitize.analysed` (null when the stage is missing). `is_dry_run = status == "completed" and doc_url is None`. List is newest first by `run_id`.

- [ ] **Step 1: Write failing tests** (build run folders in `tmp_path` from copies of the real `run.json` shapes)
  - `test_list_newest_first_with_counts`: completed run → `fetched 10332, clean 3029, analysed 500, word_count 192, has_pulse True, is_dry_run True, duration_s 435.81`.
  - `test_failed_run_keeps_funnel_counts`: failed run → `fetched 10366, clean 3038, analysed 500, has_pulse False`.
  - `test_running_folder_without_run_json`: fresh folder, no `run.json` → `status == "running"`, counts null, no exception.
  - `test_stale_folder_is_interrupted`: same folder with mtime 40 min old → `interrupted`.
  - `test_half_written_run_json`: `run.json` truncated mid-object → `unreadable` in the list, 200 on detail with `run is None` and `file_errors == {"run": "unreadable"}`.
  - `test_detail_returns_what_exists`: only `run.json` + `sanitized.json` → `pulse/note/ranking/themes` are `null`, no `file_errors` entries for absent files; a garbage `pulse.json` gives `file_errors["pulse"] == "unreadable"` and the rest still load.
  - `test_unknown_run_404`, `test_already_published_run`: empty `stages` → counts null, `doc_url`/`draft_id` passed through.
  - `test_note_read_as_utf8`: a `note.txt` containing `₹` round-trips.
- [ ] **Step 2: Run** `pytest tests/api/test_runs.py -v` → FAIL.
- [ ] **Step 3: Implement** `list_runs(settings, active_run_id)` and `get_run(settings, run_id, active_run_id)`; wire `GET /api/runs` and `GET /api/runs/{run_id}`. Do not enumerate anything under `data/` except `data/runs/*`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(api): run list and detail tolerant of missing and half-written files`

## Task 3: Analysed reviews, filters and summary

**Files:**
- Create: `api/reviews.py`, `tests/api/test_reviews.py`
- Modify: `api/schemas.py`, `api/routes.py`

**Interfaces:**
- Consumes: `safe_run_dir`, `read_json`.
- Produces: `GET /api/runs/{run_id}/reviews?theme=&rating=&q=&review_id=&page=1&page_size=25` → `{items: ReviewRow[], total, page, page_size}` where `ReviewRow = {review_id, rating, title, text, date, app_version, theme_id}` (exactly these keys; `store` is dropped). `theme` and `rating` and `review_id` are repeatable; `q` is a case-insensitive substring over `title` + `text`; `page_size` max 100 (422 above). `GET /api/runs/{run_id}/reviews/summary` → `{total, rating: {"1":n,…,"5":n}, weekly: [{week_start, count, avg_rating}], by_theme: [{theme_id, count, avg_rating}]}` computed over the whole sample (weeks start Monday, sorted ascending). Reads `sanitized.json` and `themes.json` only; a review with no assignment gets `theme_id: null`.

- [ ] **Step 1: Write failing tests**
  - `test_reads_non_ascii_reviews`: reviews with `₹295`, `सही है`, an emoji → returned intact (**Review Focus 1**; this fails if `open()` uses the default codec).
  - `test_filters_compose`: `theme=customer-support&rating=1&q=reply` returns only matching rows; `total` is the filtered total.
  - `test_review_id_filter_repeatable`: three `review_id=` params return those three.
  - `test_pagination`: 500 rows, `page=20&page_size=25` → 25 items, `total 500`; `page_size=101` → 422.
  - `test_summary_matches_sample`: rating buckets sum to `total`; by_theme counts sum to `total`.
  - `test_missing_sanitized_returns_empty_not_500`: run with no `sanitized.json` → `{items: [], total: 0, …}`; with a missing `themes.json` rows have `theme_id null`.
  - `test_never_touches_raw` (see Task 6 for the global version): create `data/raw/<run_id>/reviews.json` containing the string `Sentinel Reviewer`; no reviews response contains it.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** with a small in-process cache keyed by `(path, mtime_ns)` so paging does not re-parse 140 KB per request.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(api): analysed reviews explorer and summary endpoints`

## Task 4: Ledger endpoint

**Files:**
- Create: `api/ledger_view.py`, `tests/api/test_ledger_frontend.py`
- Modify: `api/schemas.py`, `api/routes.py`

**Interfaces:**
- Consumes: `pulse.mcp.ledger.Ledger`/`LedgerError` (read-only: only `Ledger.weeks()` may be called; never `mark_*`, `clear`).
- Produces: `GET /api/ledger` → `{weeks: {<week>: {doc: StepView | null, draft: StepView | null}}, error: null | "ledger_unreadable"}` with `StepView = {state: "appended"|"created"|"pending", run_id, document_id?, revision_id?, characters_appended?, draft_id?, thread_id?, subject?, confirmed_by_hand?: bool}`. File absent → `{weeks: {}, error: null}`. Corrupt or non-object file → `{weeks: {}, error: "ledger_unreadable"}` (**not** an empty ledger: the UI must say duplicate protection state is unknown).

- [ ] **Step 1: Write failing tests**
  - `test_absent_ledger_is_empty`.
  - `test_ledger_shape_and_pending`: file with W43 `doc: appended` + `draft: created`, and W39 `doc: appended` + `draft: pending` → both returned verbatim, pending preserved.
  - `test_corrupt_ledger_is_error_not_empty`: `{"2026-W43":` → `error == "ledger_unreadable"` (**Review Focus 3**).
  - `test_get_never_writes_ledger`: bytes and mtime of `ledger.json` unchanged after hitting every GET endpoint.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(api): read-only ledger endpoint`

## Task 5: Run control (`POST /api/runs`, `GET /api/runs/active`)

**Files:**
- Create: `api/controller.py`, `tests/api/test_controller.py`
- Modify: `api/routes.py`, `api/schemas.py`, `api/main.py` (one `RunController` on `app.state`)

**Interfaces:**
- Consumes: `Settings`, `derive_status`-style staleness helper from Task 2 (`has_live_foreign_run(settings, now) -> bool`: any run folder with no `run.json` and mtime within `RUNNING_STALE_AFTER_S`).
- Produces: `StartRequest {source: "play"|"csv", dry_run: bool = True, as_of: date | None, confirm: str | None}`; `RunController(settings, spawn: Callable[[list[str], Path], Process] = default_spawn)`; `.start(req) -> {pid, started_at}`; `.active() -> {active: bool, elapsed_s: float | None, last_line: str | None, started_by_api: bool, exit_code: int | None, exit_message: str | None, new_run_id: str | None}`; `exit_message(code: int) -> str`.

Rules: argv is a **list** `[sys.executable, "-m", "pulse", "run", "--source", source, ("--dry-run")?, ("--as-of", iso)?]` with `cwd=repo_root` (the CLI loads `.env` itself; the API never reads it). `--path` and `--fallback-csv` are never passed from the request (default fixture only). `dry_run=false` requires `confirm == "publish"` (else 422). `as_of` must be a valid date not in the future. A second start while the controller's process is alive **or** `has_live_foreign_run` is true → 409. Output is read on a background thread (`encoding="utf-8", errors="replace"`, stderr merged), keeping only the last non-empty line and the last 6 lines of stderr for the failure summary. When the process exits, `new_run_id` is the newest run folder created after spawn. Messages: 0 "Run finished", 1 "Run failed, was partial, or failed validation. See the run record", 2 "Bad arguments, or the run could not be resumed", 3 "Stopped: a ledger step is pending. Check the Doc or Drafts folder, then use the ledger commands"; unknown codes "Exited with code N".

- [ ] **Step 1: Write failing tests** (inject a fake `spawn`; never start the real CLI)
  - `test_defaults_to_dry_run`: body `{"source":"csv"}` → argv contains `--dry-run`.
  - `test_publish_requires_confirm`: `dry_run:false` without confirm → 422 and **spawn not called**; with `confirm:"publish"` → argv has no `--dry-run`; `confirm:"yes"` → 422.
  - `test_rejects_bad_input`: `source:"x"`, `as_of:"2026-13-40"`, a future `as_of`, extra field `path` → 422, spawn not called.
  - `test_second_start_is_409` and `test_double_submit_starts_once`: two rapid POSTs → exactly one spawn (**Review Focus 5**).
  - `test_foreign_live_run_blocks_start`: a fresh run folder without `run.json` → 409.
  - `test_stale_folder_does_not_block`: the same folder 40 min old → start allowed (**Review Focus 2**).
  - `test_active_reports_elapsed_last_line_and_exit`: fake process emitting lines then exit 3 → `last_line` last output, `exit_message` is the ledger message, `new_run_id` set when a folder appears.
  - `test_exit_messages`: codes 0–3 map as above.
  - `test_argv_is_a_list_with_no_shell`: assert `shell` is not set and no request string is concatenated into one argv element.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** `default_spawn` with `subprocess.Popen(..., stdout=PIPE, stderr=STDOUT, text=True, encoding="utf-8", errors="replace")`. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(api): guarded run control with dry-run default and single-flight`

## Task 6: Privacy and safety regression suite

**Files:**
- Create: `tests/api/test_privacy.py`

**Interfaces:** Consumes the whole app. Produces the deliverable-4 "final check".

- [ ] **Step 1: Write the tests** (they should already pass; if one fails, fix the offending module, not the test)
  - `test_no_endpoint_leaks_raw_cache`: `data/raw/<id>/reviews.json` holds `Sentinel Reviewer` and `sentinel@example.com`; call every GET endpoint (runs, detail, reviews, summary, ledger, config, active) and assert neither string appears in any body.
  - `test_api_source_never_references_raw`: scan `api/**/*.py`; no occurrence of `"raw"`, `'raw'`, `/raw`, `\raw` or `Config.raw`/`.raw` attribute use (allow-list the word in comments only if a failing line is justified inline).
  - `test_web_source_never_references_raw`: same scan over `web/src` and `web/fixtures` for the path `data/raw`.
  - `test_no_google_code`: scan `api/` and `web/src` for `googleapis`, `oauth`, `gmail_send`, `google.auth` (case-insensitive).
  - `test_no_send_email_route`: the OpenAPI schema has exactly the 7 spec routes + `/reviews/summary`; the only non-GET route is `POST /api/runs`.
  - `test_cors_only_vite_origins`: preflight from `http://evil.example` has no `access-control-allow-origin`; from `http://localhost:5173` it does.
  - `test_no_secret_in_responses`: set `GROQ_API_KEY=sk-test-secret` in the env, call every GET, assert absent.
- [ ] **Step 2: Run** `pytest tests/api -v` → PASS (all API tasks).
- [ ] **Step 3: Commit** `test(api): privacy and safety regression suite`

---

## Task 7: Web scaffold, tokens, shell, theme

**Files:**
- Create: `web/` (Vite react-ts template), `web/tailwind.config.ts`, `web/src/styles/tokens.ts`, `web/src/styles/index.css`, `web/src/components/AppShell.tsx`, `web/src/lib/theme.ts`, `web/src/test/setup.ts`, tests beside each
- Modify: `web/vite.config.ts` (dev server `127.0.0.1:5173`, proxy `/api` → `http://127.0.0.1:8000`, Vitest `jsdom` + `setupFiles`)

**Interfaces:**
- Produces: Tailwind theme ported **verbatim** from the `tailwind-config` script in `overview_groww_review_pulse/code.html` (colors, `space-*` spacing, `fontSize` tokens such as `text-headline-md`/`text-label-sm`, `fontFamily` tokens) plus status tokens `status.{completed,running,partial,failed,dryrun,pending}.{fg,bg,border}` and a `dark:` variant via `darkMode: "class"`; `useTheme(): {theme: "light"|"dark"|"system", resolved: "light"|"dark", setTheme}` (follows `prefers-color-scheme`; persists to `localStorage` inside try/catch; sets `class="dark"` on `<html>`); `<AppShell>`: top bar, 256px fixed sidebar ≥1280px, drawer below; nav items Overview `/`, Run Detail (latest run), Run History `/runs`, Publishing Ledger `/ledger`, Settings `/settings`; routes declared with placeholder pages.
- Fonts: `@fontsource-variable/inter`, `@fontsource-variable/plus-jakarta-sans`, `@fontsource/jetbrains-mono` imported in `index.css` (no CDN, no hotlinked images). Icons from `lucide-react`.

- [ ] **Step 1: Write failing tests**
  - `contrast.test.ts`: for every status pair and for `on-surface`/`surface`, `primary`/`surface-container-lowest`, `on-primary-container`/`primary-container`, `secondary`/`surface`, in light **and** dark tokens, WCAG ratio ≥ 4.5 (use a small `contrastRatio(hexA, hexB)` helper in `tokens.ts`). The suite is expected to fail on at least one raw DESIGN.md pair at first; fix the hex, not the threshold.
  - `AppShell.test.tsx`: nav shows the five labels; the active route has `aria-current="page"`; the skip link "Skip to content" is the first focusable element; below 1280px width the sidebar is hidden behind a button labelled "Open navigation".
  - `theme.test.ts`: `setTheme("dark")` adds `dark` to `document.documentElement` and survives `localStorage` throwing (no exception, class still applied).
- [ ] **Step 2: Run** `npm test` → FAIL. **Step 3: Implement.** **Step 4: Run** `npm test` and `npm run build` → PASS.
- [ ] **Step 5: Commit** `feat(web): scaffold, design tokens, app shell, light/dark theme`

## Task 8: Types, API client, mock mode, fixtures

**Files:**
- Create: `web/src/api/types.ts`, `web/src/api/client.ts`, `web/src/api/mock.ts`, `web/src/api/hooks.ts`, `web/src/test/factories.ts`, `scripts/make_web_fixtures.py`, `web/fixtures/**`, `web/src/api/mock.test.ts`, `tests/api/test_fixtures_clean.py`

**Interfaces:**
- Produces TS types mirroring the API: `RunStatus = "running"|"completed"|"failed_validation"|"partial"|"failed"|"already_published"|"interrupted"|"unreadable"`, `Run`, `Pulse`, `ReviewRow`, `RunSummary`, `RunDetail`, `LedgerView`, `ConfigView`, `ActiveRun` (shapes as in the prompt's data model and Tasks 1–5); `api` object with `listRuns()`, `getRun(id)`, `getReviews(id, params)`, `getReviewsSummary(id)`, `getLedger()`, `getConfig()`, `startRun(body)`, `getActive()`; hooks `useRuns()`, `useRun(id)`, `useReviews(id, params)`, `useLedger()`, `useConfig()`, `useActive()` (polls every 5 s only while `active`), all TanStack Query. `VITE_MOCK=1` swaps `api` for `mock.ts`, which serves `web/fixtures/` through the same signatures and shows a "Mock data" pill in the shell; `npm run dev:mock` sets it. `factories.ts`: `makeRun(overrides)`, `makePulse(overrides)`, `makeConfig(overrides)` built from the real `20261022-121514` values, plus `makeFailedRun()` from `20261022-151338`, `makePartialRun()`, `makeAlreadyPublishedRun()`, `makeLedger({pending?})`.
- Fixtures (`web/fixtures/`): `runs/20261022-121514/{run.json,pulse.json,note.txt,ranking.json,themes.json,sanitized.json}` and `runs/20261022-151338/{run.json,sanitized.json}`; `config.json`; `ledger.json` (**synthetic**, in the real ledger format, with one `pending` draft week so the banner is visible in mock mode; keep the format pure and say it is synthetic in `web/fixtures/README.md`). `sanitized.json` is trimmed to 150 reviews: the three quote reviews plus every Nth review, and `themes.json` assignments filtered to the same ids; the README states that mock explorer totals (150) differ from the run's `analysed` (500). `scripts/make_web_fixtures.py` produces them from `data/runs/` and copies only those files, never `data/raw/`.

- [ ] **Step 1: Write failing tests**
  - `mock.test.ts`: in mock mode `listRuns()` returns two runs newest first; `getRun("20261022-151338")` has `status "failed"` and `pulse === null`; `getReviews` filters by `theme`.
  - `tests/api/test_fixtures_clean.py`: every fixture review has exactly the keys `review_id, store, rating, title, text, date, app_version`; no fixture text matches an email or 10-digit phone regex; `web/fixtures` contains no `raw` path; `run.json` fixtures contain no `author` key; the three `pulse.json` quotes appear verbatim (whitespace/case-insensitive) in the fixture `sanitized.json`.
- [ ] **Step 2: Run** `npm test`, `pytest tests/api/test_fixtures_clean.py` → FAIL.
- [ ] **Step 3: Implement** the script (read with `encoding="utf-8"`, write with `ensure_ascii=False`), run it, then the client/mock/hooks.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(web): typed API client, mock mode, real-run fixtures`

## Task 9: Domain logic (pure functions)

**Files:**
- Create: `web/src/lib/{format,funnel,themes,stages,guardrails,status,ledger}.ts` and a `*.test.ts` for each

**Interfaces:** all pure, no React, no fetch. Signatures:

- `format.ts`: `formatInt(n: number|null): string` (`10,332`, `—` for null); `formatPercent(x: number|null, digits = 1): string` (max one decimal, trailing `.0` dropped, `—` for null/NaN); `formatWindow(start: string, end: string): string` (`13 Aug - 22 Oct 2026`; across years `30 Dec 2025 - 12 Mar 2026`); `windowWeeks(start, end): number` (70 days → `10`); `formatDuration(s: number): string` (`7m 16s`, `72s` → `1m 12s`, `4s`); `formatIst(iso: string): {ist: string, utc: string}` (`22 Oct 2026, 17:45:14 IST` / `2026-10-22 12:15:14 UTC`); `truncateId(id: string): string`.
- `funnel.ts`: `computeFunnel(run: Run, minReviews: number): Funnel` where `Funnel = {fetched, pages, itemsSeen, outsideWindow, dropped: {short, nonEnglish, duplicate, invalid, total}, clean, analysed, sampled: boolean, marginOverMin, pct: {dropped, clean, analysedOfClean}, checks: {cleaning: {ok, expectedClean, actualClean}, ingest: {ok, …}}, warnings: ("fetch_stopped_early")[], reachedStage: StageName | null}`; every unavailable value is `null`.
- `themes.ts`: `weightedContributions(scores, weights) -> {volume, recency, severity}` (weight × component); `splitSelected(ranking, top) -> {selected, notSelected, excludedOther}`.
- `stages.ts`: `STAGE_ORDER` (`ingest, sanitize, theme, rank, compose, render, publish_doc, publish_draft`); `stageRows(run): {name, state: "done"|"failed"|"not_run", duration_s|null, counts, notes}[]` (for `status` `failed`/`failed_validation` the **last recorded** stage is `failed`; later stages `not_run`); `slowestStage(run) -> {name, pct}`; `totalDuration(run)`.
- `guardrails.ts`: `evaluateGuardrails(input: {run, pulse, reviewsById, config}): Guardrail[]` with `Guardrail = {id, label, status: "pass"|"fail"|"unavailable", detail}`; ids: `themes`, `quotes`, `actions`, `words`, `identity`, `window`, `compose`; `normalize(text)` collapses whitespace, lower-cases, folds curly quotes/dashes.
- `status.ts`: `isDryRun(run)`; `statusPresentation(run) -> {label, icon, token}` (`Completed · Dry run, nothing published` for a dry run; `Already published`; etc.).
- `ledger.ts`: `ledgerRows(view): {week, doc, draft, outcome: "complete"|"draft_missing"|"action_required"|"in_progress", resumeRunId|null}[]` and `ledgerCommands(week, step) -> {confirm, clear}` returning exactly `python -m pulse ledger confirm <week> <step>` / `python -m pulse ledger clear <week> <step>`.

- [ ] **Step 1: Write failing tests** (values from the real run)
  - `computeFunnel(makeRun(), 20)` → `fetched 10332, itemsSeen 10400, outsideWindow 68, pages 52, dropped {short 7159, nonEnglish 82, duplicate 62, invalid 0, total 7303}, clean 3029, analysed 500, sampled true, marginOverMin 3009`, `pct.dropped` formats to `70.7%`, `pct.clean` to `29.3%`, `checks.cleaning.ok` true.
  - Discrepancy: `makeRun` with `dropped_short` changed to 7000 → `checks.cleaning.ok false`, `expectedClean 3190`, `actualClean 3029` (shown, not hidden).
  - Warning: `truncated 1` or `window_start_reached 0` → `warnings` contains `fetch_stopped_early`.
  - **Missing data (Review Focus 4):** `makeFailedRun()` (theme `counts: {}`) → funnel through `analysed 500` computed, `reachedStage "theme"`; a run with no `sanitize` stage → `clean/analysed null`, all `pct` null, no `NaN`; `fetched: 0` → `pct.dropped null`; `formatPercent(NaN)` is `—`.
  - `stageRows(makeRun())` has 8 entries, last two `not_run`; for the failed run `theme` is `failed`, `rank..publish_draft` `not_run`; `slowestStage(makeRun())` → `{name: "theme", pct: 77.1}` (compare formatted to one decimal); `totalDuration` formats `7m 16s`; failed run `1m 12s`.
  - `weightedContributions` for customer-support with weights 0.5/0.2/0.3 → `0.044 / 0.015 / 0.280` (3 dp), summing to `0.339`.
  - `splitSelected`: `other` is in `excludedOther` although it has the highest score; selected order is customer-support, trading…, payments.
  - Format: `formatWindow("2026-08-13","2026-10-22") === "13 Aug - 22 Oct 2026"`; `windowWeeks(...) === 10`; `formatIst("2026-10-22T12:15:14.967424+00:00")` → IST `22 Oct 2026, 17:45:14 IST`, UTC `2026-10-22 12:15:14 UTC`.
  - Guardrails (real run): `quotes` pass when all three `review_id`s are in `reviewsById` and each text is found after `normalize`; fails when a quote's review is **absent** from the analysed set (fail with detail, not a crash), when text differs by a word, and passes when the only difference is double spaces/case/curly apostrophe; `themes` counts clustering themes **excluding Other** (5 ≤ `max_themes` 5 → pass; 6 → fail); `actions` fails if an action's `theme_id` is not one of the 3 top themes; `words` uses `run.word_count ≤ config.max_words`; `window` passes at 10.0 weeks, fails at 7 and 13; `identity` shows the five redaction counts (34/3/3/2/3) and never `fail`; `compose` shows `retries 0` and lists `violations`; if `pulse` is null every pulse-dependent guardrail is `unavailable`, and an `unavailable` never counts as a pass in the header tally.
  - `isDryRun`: true for completed + null `doc_url`; false when `doc_url` set; false for `failed`.
  - `ledgerRows`: doc `appended` + draft `created` → `complete`; doc `appended` + no draft → `draft_missing` with `resumeRunId` = the doc's `run_id`; any `pending` → `action_required`; both absent → not listed. `ledgerCommands("2026-W39","draft").confirm === "python -m pulse ledger confirm 2026-W39 draft"`.
- [ ] **Step 2: Run** `npm test` → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(web): funnel, stage, theme, guardrail and ledger domain logic`

## Task 10: Shared components

**Files:**
- Create: `web/src/components/{StatusBadge,Stars,ThemeChip,Card,CopyButton,ChartFrame,DataUnavailable,Mono}.tsx` + tests

**Interfaces:**
- `StatusBadge({status, run?})` (icon + text; Running has a pulsing dot that stops under `prefers-reduced-motion`); `Stars({value, max = 5})` renders filled stars **and** `value.toFixed(1)` with `aria-label="3.4 out of 5"`; `ThemeChip({themeId, label})`; `Card({title, eyebrow?, children})` using `surface-container-lowest`, 1px `outline-variant` hairline (DESIGN.md Level 1, no shadow); `CopyButton({text, label?})` uses `navigator.clipboard.writeText`, swaps to "Copied" for 2 s, and falls back to selecting text if the clipboard API rejects; `ChartFrame({title, sampleNote?, table, children})` with a "View as table" toggle (button, `aria-pressed`); `DataUnavailable({what})` small inline message; `Mono` for run ids and hashes (`font-data-code`).
- [ ] **Step 1: Write failing tests**: each status has visible text and an `svg` icon (not colour only); `Stars value=1.27` shows `1.3` and the aria label; `CopyButton` writes exactly the given `text` (spy on `navigator.clipboard.writeText`) and still renders when the clipboard rejects; `ChartFrame` toggles between chart and `<table>` with the same data; `vitest-axe` reports no violations for each.
- [ ] **Step 2–4: Run → FAIL, implement, PASS.**
- [ ] **Step 5: Commit** `feat(web): shared status, stars, chip, chart-frame and copy components`

## Task 11: Overview (a): header, funnel, minimum-reviews rule

**Files:**
- Create: `web/src/pages/Overview/{OverviewPage,RunHeader,Funnel}.tsx` + tests
- Modify: router (index route)

**Interfaces:**
- Consumes: `useRuns()`, `useRun(latest)`, `useConfig()`, `computeFunnel`, `formatWindow`, `formatIst`, `statusPresentation`.
- `OverviewPage` picks the first run of `/api/runs` (latest); states below. `RunHeader`: week label pill, status badge, run id (`Mono`), window with "(10 weeks)", started (IST; UTC in a tooltip that is also keyboard-reachable), total duration, "Open Google Doc" only when `doc_url`, "Run now" opening the control (Task 12). `Funnel`: four stage cards as in the mockup (Fetched / Dropped itemised / Clean / Analysed) with number + percentage on each, the ingest sub-facts (pages, seen, kept, outside window), the arithmetic line from `funnel.checks`, the min-reviews margin ("3,029 clean reviews, 3,009 above the minimum of 20"), the sample sentence, and the `fetch_stopped_early` warning chip: "Fetch stopped early, oldest reviews may be missing".

Run states on this page (each explicit):

| Status | Rendering |
| --- | --- |
| `completed`, dry run | Full page; badge "Completed · Dry run, nothing published"; no Doc link |
| `completed`, published | Full page; Doc link |
| `already_published` | No funnel. Panel "Already published for 2026-Wxx" with Doc link and draft id |
| `failed` | Funnel up to the failure point; the failing stage named ("Stopped at: Theme"); `violations` shown as the reason; later sections replaced by "Not produced"; **no** publish action |
| `failed_validation` | Violations and retry count; "Nothing was published" |
| `partial` | Doc done, draft failed; command `python -m pulse run --resume <run_id>` with copy button |
| `running` / `interrupted` | Elapsed time (or "No run record; the process ended early"), no numbers |
| no runs | Empty state with "Run a dry run" button |
| `unreadable` | `DataUnavailable` in place of the cards |

- [ ] **Step 1: Write failing tests**: with `makeRun()` the page shows `10,332`, `7,303`, `3,029`, `500`, `70.7%`, `29.3%`, `3,009`, `52 pages`, `10,400`, "A fixed random sample of 500 of 3,029 clean reviews was analysed."; `makeRun` with `window_start_reached: 0` shows the early-stop chip; the failed run shows "Stopped at: Theme", the Groq message, funnel counts `10,366` and `3,038`, and no Doc/draft/publish controls; `already_published` shows no funnel; `partial` shows the resume command and `CopyButton` text equals it; empty `useRuns()` shows "Run a dry run"; a funnel discrepancy renders the expected-vs-actual line.
- [ ] **Step 2–4: Run → FAIL, implement, PASS.** (Load the `dataviz` skill before drawing the stepped funnel bars; emerald steps `#00B386 → #00D09C → #A7F3D0` per DESIGN.md.)
- [ ] **Step 5: Commit** `feat(web): overview header and review-count funnel with run states`

## Task 12: Run control panel and publish confirmation

**Files:**
- Create: `web/src/components/{RunControl,ConfirmPublishDialog}.tsx` + tests
- Modify: `AppShell` ("New Run (Dry Run)" button opens `RunControl`)

**Interfaces:**
- `RunControl`: modal (DESIGN.md Level 3). Fields: source (`Play Store live` → `play` / `CSV fixture` → `csv`), optional "As of" date (max today), **Dry run toggle ON by default**. Submit disabled while a run is active or while the POST is pending (prevents double submit). While active: elapsed timer, indeterminate progress, "Run files appear when the analysis ends (usually 6-8 minutes)", `last_line`. On finish: `exit_message`, the last stderr lines on failure, and a "Go to run" link to `new_run_id`; query caches for runs are invalidated. Turning the toggle off and submitting opens `ConfirmPublishDialog`, which states: appends a section to the Google Doc, creates a Gmail draft, **nothing is emailed**; the confirm button reads "Publish week 2026-Wxx" and only then sends `{dry_run:false, confirm:"publish"}`. Cancel and Escape send nothing. 409 → "A run is already in progress".
- [ ] **Step 1: Write failing tests** (mock `api.startRun`): default submit sends `{source:"play", dry_run:true}` with no `confirm`; toggling off then submitting sends nothing until the dialog is confirmed, then sends `confirm:"publish"`; Escape/Cancel on the dialog sends nothing and the toggle stays off but the next open resets to ON; double-click on submit calls `startRun` once (**Review Focus 5**); when `useActive` is active the submit is disabled and the timer renders; exit code 3 shows the ledger message; dialog is focus-trapped and `axe` clean.
- [ ] **Step 2–4: Run → FAIL, implement, PASS.**
- [ ] **Step 5: Commit** `feat(web): run control with dry-run default and publish confirmation`

## Task 13: Overview (b): themes, quotes, actions

**Files:**
- Create: `web/src/pages/Overview/{ThemeCards,QuoteCards,ActionCards}.tsx`, `web/src/components/ReviewDrawer.tsx` + tests

**Interfaces:**
- `ThemeCards`: exactly 3 ranked cards from `pulse.themes` joined to `ranking`: label, summary, "8.8% of analysed reviews", "44 of 500", `Stars` (avg 1.27 → 1.3), score with a stacked bar of `weightedContributions` (tooltip: `0.5 × volume + 0.2 × recency + 0.3 × severity` with weights **from config**), and a footnote that the published note calls this "% of reviews".
- `QuoteCards`: verbatim quote, stars, `ThemeChip`, truncated `review_id`; clicking opens `ReviewDrawer` (fetches `getReviews(id, {review_id})`), shows rating, date, app version, theme, title, full text with the quote highlighted (case/whitespace-insensitive match via `normalize` offsets). If the review is absent: "Source review not in the analysed set".
- `ActionCards`: number, text, theme chip. Nothing else.
- [ ] **Step 1: Write failing tests**: three theme cards in score order (Customer Support first), the `8.8% of analysed reviews` text and `44 of 500`; changing config weights changes the tooltip text (no hardcoded 0.5); a quote click opens the drawer with the quote wrapped in `<mark>` even when the stored text has double spaces; missing review shows the fallback; action cards contain no "Impact" or "T-Shirt" text; `axe` clean.
- [ ] **Step 2–4: Run → FAIL, implement, PASS.**
- [ ] **Step 5: Commit** `feat(web): overview themes, quotes with source drawer, actions`

## Task 14: Overview (c): published note, publishing status, guardrails

**Files:**
- Create: `web/src/pages/Overview/{PublishedNote,PublishingStatus,GuardrailChecklist}.tsx` + tests

**Interfaces:**
- `PublishedNote`: `note.txt` verbatim in a mono, `whitespace-pre-wrap` block; gauge `192 / 250 words` (limit from config; bar plus text); `CopyButton text={note}`; label "What was published". For a dry run, the label reads "What would be published (dry run)". Note null → `DataUnavailable`.
- `PublishingStatus`: Google Doc (link from `doc_url`, "Section appended: Yes/No", `doc_revision_id`, characters from the `publish_doc` stage counts), Gmail draft (draft id, recipient = `config.draft_to`, subject `Groww Weekly Review Pulse - <week>`, fixed line "Draft only - never sent"). Dry run → both "Not published (dry run)". `partial` → Doc done, draft "Failed" + resume command. Failed → "Nothing published".
- `GuardrailChecklist`: from `evaluateGuardrails`; header "n / 7 passed" counting only `pass`; `fail` and `unavailable` have distinct icon + text; the identity row lists the five redaction counts and "Raw reviews are never shown here".
- [ ] **Step 1: Write failing tests**: copy writes the exact `note.txt` (compare the spy's argument to the fixture string, including the `-` characters); `192 / 250`; dry run shows "Not published (dry run)" and no link; `partial` shows the Doc link, a failed draft and the resume command; guardrail header is `7 / 7` for the real run and `6 / 7` when one quote text is altered, with the failing row text naming the quote; identity row contains `34`, `3`, `3`, `2`, `3`; with `pulse` null the dependent rows are "Unavailable" and not counted.
- [ ] **Step 2–4: Run → FAIL, implement, PASS.**
- [ ] **Step 5: Commit** `feat(web): published note, publishing status and computed guardrails`

## Task 15: Publishing ledger page

**Files:**
- Create: `web/src/pages/Ledger/{LedgerPage,PendingBanner}.tsx` + tests

**Interfaces:**
- Table (one row per week, newest first): week, Doc state (`Appended`/`Pending`/`Not started`), revision id, characters, Draft state (`Created`/`Pending`/`Not started`), draft id, run id (links to `/runs/:id`), Doc link (built from `config.doc_url`, since the ledger holds only `document_id`), outcome from `ledgerRows`. `confirmed_by_hand` shows a "Confirmed by hand" tag. `PendingBanner` for each pending step: "Outcome unknown: an earlier run died while writing. Check the Doc or Drafts folder, then run one of these:" and two `CopyButton` commands from `ledgerCommands` ("it is there" → confirm, "it is not there" → clear). `error == "ledger_unreadable"` → red banner "The ledger file cannot be read. Duplicate protection is unknown until it is fixed or restored." (never the empty state). Absent ledger → "Nothing published from this machine" empty state. Explainer: losing `data/ledger.json` loses duplicate protection; back it up outside Git (it is git-ignored). A `draft_missing` week shows `python -m pulse run --resume <run_id>`. A "Read-only" chip in the header; no action buttons.
- [ ] **Step 1: Write failing tests**: pending draft for `2026-W39` → banner with `python -m pulse ledger confirm 2026-W39 draft` and `python -m pulse ledger clear 2026-W39 draft` (exact strings via `CopyButton` props); two pending steps → two banners; empty ledger → empty state; `ledger_unreadable` → the error banner and **not** the empty state (**Review Focus 3**); `draft_missing` row shows the resume command; there is no `button` in the table that is not a copy button.
- [ ] **Step 2–4: Run → FAIL, implement, PASS.**
- [ ] **Step 5: Commit** `feat(web): publishing ledger page with manual-check commands`

## Task 16: Run detail page

**Files:**
- Create: `web/src/pages/RunDetail/{RunDetailPage,PipelineTimeline,ThemeTable,LlmUsage,Violations,ReviewExplorer}.tsx` + tests

**Interfaces:**
- `PipelineTimeline`: `stageRows` as cards (state icon + text, duration, key counts, `notes`), "Slowest: Theme (77.1% of 7m 16s)", total time; unrecorded stages "Not run". Do not print `notes` that contain filesystem paths: filter out any note starting with `raw cache:` (it names `data\raw\…`).
- `ThemeTable`: all themes including `Other`, columns per the decision table; stacked weighted-contribution bars; explainer: "Other is a catch-all and is never one of the top 3, even when it scores highest (here it is 60.4% of the sample)."; weights from config.
- `LlmUsage`: per task calls, prompt/completion tokens, retries, rate-limited, invalid replies, seconds waited; model ids from `/api/config` labelled "Configured now (not recorded per run)"; `prompt_versions`; total tokens (53,771 for the real run). No cost estimate.
- `Violations`: verbatim list; `failed`/`failed_validation` styled as errors, guardrail messages as warnings.
- `ReviewExplorer`: filterable (theme, rating, text search, debounced 250 ms), paginated (25) table via `useReviews`; each top-3 quote has a "Show in explorer" link that sets `review_id`; three charts (rating distribution 1–5, reviews per week, average rating per theme) from `/reviews/summary`, each in `ChartFrame` with titles ending "analysed sample (500 reviews)" using the real `total`, plus table toggle. No export, no device fields.
- [ ] **Step 1: Write failing tests**: timeline shows `ingest 79.7s`, theme slowest at `77.1%`, last two stages "Not run", no text containing `raw cache`; failed run shows the failed Theme stage and the violation; theme table lists 6 rows, `Other` status "Excluded: catch-all" with score `0.493` and score rank `1`, the three selected rows in score order; LLM usage shows `286` waited seconds, `15` rate-limited, `53,771` total tokens and `openai/gpt-oss-20b` with the "Configured now" label; explorer filter by rating 1 calls the API with `rating=1` and shows the filtered total; chart title contains "analysed sample"; every chart has a table toggle; `axe` clean.
- [ ] **Step 2–4: Run → FAIL, implement, PASS.** (Load the `dataviz` skill first.)
- [ ] **Step 5: Commit** `feat(web): run detail with timeline, theme matrix, LLM usage and review explorer`

## Task 17: Run history page

**Files:**
- Create: `web/src/pages/RunHistory/{RunHistoryPage,KpiTiles,TrendChart,RunsTable}.tsx` + tests

**Interfaces:**
- `KpiTiles` (computed, no deltas except where both runs exist): total runs and success rate (`completed / total`), anomalies by status (failed / failed_validation / partial), average duration of completed runs, latest fetched with latest clean, average words of completed runs vs the limit.
- `TrendChart`: x = completed runs by `started_at` (label `22 Oct 17:45`), bars fetched and clean, line analysed, dashed line word count on a right axis; table toggle; empty state if no completed runs.
- `RunsTable`: all folders newest first: run id (copy), week, status badge (`Dry run` for dry runs), started (IST, UTC on hover), duration, fetched / clean / analysed (analysed muted with tooltip when the run failed before the model stage), words, Doc link, draft id, "View detail". Failed and `interrupted` rows stay visible. Rows sharing a `week_label` are grouped under a week header with "N runs this week". Filters: status tabs (All, Completed, Dry run, Failed, Partial, Other) with counts, week select, search by run id/week. `partial` rows show the resume command (copy), never a run button. Pagination 25.
- [ ] **Step 1: Write failing tests** (10 real runs): KPI "10 runs", "40%" success (4 completed), "6 failed"; all 10 rows under one `2026-W43` header "10 runs this week"; status tab "Failed (6)"; "Dry run (4)"; search `151338` leaves one row; failed row shows `10,366 / 3,038 / 500` with the muted analysed cell and duration `1m 12s`; no element offers a run/resume action; chart has 4 completed points and a table toggle; empty history shows the empty state.
- [ ] **Step 2–4: Run → FAIL, implement, PASS.**
- [ ] **Step 5: Commit** `feat(web): run history with computed KPIs, trend chart and grouped table`

## Task 18: Settings page

**Files:**
- Create: `web/src/pages/Settings/SettingsPage.tsx` + test

**Interfaces:**
- Read-only definition lists from `useConfig()`: app package and locale (`com.nextbillion.groww`, `en`/`in`), `window_weeks`, `max_themes`, taxonomy list, ranking weights and recency window, `max_words`, `min_reviews`, `min_words`, `max_analysed`, models per task, batch size, `draft_to`, Doc link (`doc_url`). A line stating the dashboard never shows secrets or paths. No inputs, no save button.
- [ ] **Step 1: Write failing test**: renders every listed value from `makeConfig()`; the Doc link `href` equals `config.doc_url`; there is no `input`, `select` or `textarea`; the page text contains neither `server_dir` nor `GROQ`.
- [ ] **Step 2–4: Run → FAIL, implement, PASS.**
- [ ] **Step 5: Commit** `feat(web): read-only settings page`

## Task 19: README, run scripts, final verification

**Files:**
- Modify: `README.md` (new section "Dashboard")
- Create: `scripts/run_dashboard.ps1`
- Modify: `web/package.json` (scripts `dev`, `dev:mock`, `build`, `test`, `lint`)

**Interfaces:** README documents, for Windows from the repo root: `.\.venv\Scripts\Activate.ps1`; `pip install -e ".[dev,api]"`; `uvicorn api.main:app --host 127.0.0.1 --port 8000` (note: do not use `--reload` while a run is in progress, since a reload orphans the CLI process); `cd web; npm install; npm run dev` (open `http://localhost:5173`); `npm run dev:mock` for the no-backend mode; that `data/raw/` is never read; that publishing needs the confirmation dialog; that losing `data/ledger.json` loses duplicate protection; the derived `interrupted` and `unreadable` statuses; and that model ids on the Run detail page are "configured now".

- [ ] **Step 1: Verify the whole system**
  - `pytest` → all existing backend tests and `tests/api` pass.
  - `cd web; npm test; npm run build; npm run lint` → clean.
  - `python scripts/make_web_fixtures.py --check` (if implemented as a dry listing) or `pytest tests/api/test_fixtures_clean.py` → pass.
  - Start `uvicorn` + `npm run dev` and, with the real `data/`, confirm in a browser (Playwright MCP is available) that Overview shows `10,332 → 7,303 → 3,029 → 500`, the three real themes, "Completed · Dry run, nothing published", and an empty Ledger; resize to 768px and to dark mode; check keyboard tab order on the run control and confirm dialog.
  - `curl -X POST http://127.0.0.1:8000/api/runs -H "Content-Type: application/json" -d "{\"source\":\"csv\",\"dry_run\":false}"` returns 422 and starts nothing.
  - `git status` shows no changes under `src/pulse/`.
- [ ] **Step 2: Commit** `docs: dashboard run instructions and final verification`

---

## Self-Review

**Spec coverage** (`docs/frontend-prompt.md`):
- Endpoints (7) → Tasks 1–5 (+ `/reviews/summary`, a deliberate addition for the charts).
- Overview A–G → Tasks 11, 13, 14; Run control → 12; Run detail → 16; History → 17; Ledger → 15; Settings → 18.
- Run states table (completed/dry run, already_published, failed, failed_validation, partial, running, pending, empty, malformed) → Tasks 2, 9, 11, 14, 15.
- Privacy rules 1–6 → Global Constraints + Tasks 1, 5, 6; deliverable 4 → Tasks 6, 19.
- Fixtures + mock mode → Task 8; tests (traversal, missing file, half-written, pending ledger, funnel arithmetic, run states) → Tasks 1, 2, 4, 9, 11.
- Formatting rules → Task 9 (`format.ts`) and Global Constraints.

**Deliberate deviations from the prompt** (each needed by the real repo):
1. Statuses `interrupted` and `unreadable` added (a dead run would otherwise be "running" forever).
2. `GET /api/ledger` carries an `error` field (a corrupt ledger must not read as empty).
3. `GET /api/runs/{id}/reviews/summary` added, and `/reviews` takes `review_id` (charts over the whole sample; quote verification and drawer).
4. Fixture `sanitized.json` is trimmed to 150 reviews, so mock-mode explorer totals differ from `analysed: 500`.
5. `GET /api/runs/{id}` also returns `file_errors` and `status`.

**Type consistency:** `RunStatus` (Task 8) is the one union used by Tasks 9–17; `Funnel`/`computeFunnel` (Task 9) is consumed by Tasks 11 and 17; `Guardrail`/`evaluateGuardrails` by Task 14; `ledgerRows`/`ledgerCommands` by Task 15; `ConfigView` fields (Task 1) are exactly what Tasks 11–18 read; `is_dry_run` (API, Task 2) and `isDryRun` (web, Task 9) use the same rule.

**Review Focus coverage:** 1 → Task 3, 2 → Tasks 2 and 5, 3 → Tasks 2, 4, 15, 4 → Task 9, 5 → Tasks 5 and 12.

**Open decisions to confirm before starting** (none block Tasks 1–6):
- Plan location: saved as `docs/frontend_implementation.md` next to `implementation-plan.md`.
- Whether to commit the untracked `stitch_groww_review_pulse_dashboard/` design folder (the plan only reads it).
- Whether fixtures built from real (already sanitised, public) review text may be committed; if not, replace the 150 reviews with hand-written ones and keep the same keys.
