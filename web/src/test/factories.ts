/**
 * Test data built from the real fixtures: `makeRun()` is run 20261022-121514 (a dry run),
 * `makeFailedRun()` is 20261022-151338. Every call returns a fresh deep copy, so a test may mutate
 * its result. The partial, already-published and ledger shapes have no run on disk; they are
 * derived from the real run following the orchestrator's code (orchestrator.py).
 */
import configJson from "../../fixtures/config.json";
import failedRunJson from "../../fixtures/runs/20261022-151338/run.json";
import pulseJson from "../../fixtures/runs/20261022-121514/pulse.json";
import rankingJson from "../../fixtures/runs/20261022-121514/ranking.json";
import runJson from "../../fixtures/runs/20261022-121514/run.json";
import sanitizedJson from "../../fixtures/runs/20261022-121514/sanitized.json";
import noteText from "../../fixtures/runs/20261022-121514/note.txt?raw";
import themesJson from "../../fixtures/runs/20261022-121514/themes.json";
import type {
  ConfigView,
  LedgerView,
  Pulse,
  Ranking,
  ReviewRow,
  Run,
  RunDetail,
  RunSummary,
  StageCounts,
  ThemesFile,
} from "../api/types";

const copy = <T>(value: unknown): T => structuredClone(value) as T;

export function makeRun(overrides: Partial<Run> = {}): Run {
  return { ...copy<Run>(runJson), ...overrides };
}

export function makeFailedRun(overrides: Partial<Run> = {}): Run {
  return { ...copy<Run>(failedRunJson), ...overrides };
}

export function makePulse(overrides: Partial<Pulse> = {}): Pulse {
  return { ...copy<Pulse>(pulseJson), ...overrides };
}

export function makeRanking(overrides: Partial<Ranking> = {}): Ranking {
  return { ...copy<Ranking>(rankingJson), ...overrides };
}

export function makeThemes(): ThemesFile {
  return copy<ThemesFile>(themesJson);
}

export function makeConfig(overrides: Partial<ConfigView> = {}): ConfigView {
  return { ...copy<ConfigView>(configJson), ...overrides };
}

/** The 150 analysed reviews in the fixture, keyed by review_id (themes joined in). */
export function makeReviewsById(): Record<string, ReviewRow> {
  const themeOf = new Map(makeThemes().assignments.map((a) => [a.review_id, a.theme_id]));
  const rows = copy<Omit<ReviewRow, "theme_id">[]>(sanitizedJson);
  return Object.fromEntries(
    rows.map((r) => [r.review_id, { ...r, theme_id: themeOf.get(r.review_id) ?? null }]),
  );
}

/** Merge `counts` into one stage's counts (the stage must exist). */
export function withStageCounts(run: Run, stage: string, counts: StageCounts): Run {
  const target = run.stages.find((s) => s.name === stage);
  if (!target) throw new Error(`run has no ${stage} stage`);
  target.counts = { ...target.counts, ...counts };
  return run;
}

export function withoutStage(run: Run, stage: string): Run {
  run.stages = run.stages.filter((s) => s.name !== stage);
  return run;
}

const DOC_URL = "https://docs.google.com/document/d/EXAMPLE_DOCUMENT_ID/edit";

/**
 * Doc section appended, Gmail draft failed. The orchestrator records the draft failure in
 * `violations` and leaves `draft_id` null; the run is `partial` and is finished with `--resume`.
 */
export function makePartialRun(overrides: Partial<Run> = {}): Run {
  const run = makeRun({
    status: "partial",
    doc_id: "EXAMPLE_DOCUMENT_ID",
    doc_url: DOC_URL,
    doc_revision_id: "rev_sample_43",
    draft_id: null,
    violations: ["Gmail draft failed: the MCP server did not respond."],
  });
  run.stages.push(
    { name: "publish_doc", duration_s: 2.4, counts: { characters_appended: 1184 }, notes: [] },
    { name: "publish_draft", duration_s: 0.9, counts: {}, notes: [] },
  );
  return { ...run, ...overrides };
}

/** The week was already published: a folder and run.json exist, but no stage ran. */
export function makeAlreadyPublishedRun(overrides: Partial<Run> = {}): Run {
  return makeRun({
    status: "already_published",
    stages: [],
    theme_scores: {},
    prompt_versions: {},
    llm_usage: {},
    word_count: 0,
    violations: [],
    doc_id: "EXAMPLE_DOCUMENT_ID",
    doc_url: DOC_URL,
    doc_revision_id: "rev_sample_43",
    draft_id: "draft_sample_43",
    ...overrides,
  });
}

/** A complete week; with `pending`, a second week whose draft step was left `pending`. */
export function makeLedger(options: { pending?: boolean } = {}): LedgerView {
  const weeks: LedgerView["weeks"] = {
    "2026-W43": {
      doc: {
        state: "appended",
        run_id: "20261022-121514",
        document_id: "EXAMPLE_DOCUMENT_ID",
        revision_id: "rev_sample_43",
        characters_appended: 1184,
      },
      draft: {
        state: "created",
        run_id: "20261022-121514",
        draft_id: "draft_sample_43",
        thread_id: "thread_sample_43",
        subject: "Groww Weekly Review Pulse - 2026-W43",
      },
    },
  };
  if (options.pending) {
    weeks["2026-W39"] = {
      doc: {
        state: "appended",
        run_id: "20260924-090009",
        document_id: "EXAMPLE_DOCUMENT_ID",
        revision_id: "rev_sample_39",
        characters_appended: 1254,
      },
      draft: { state: "pending", run_id: "20260924-090009" },
    };
  }
  return { weeks, error: null };
}

/** What GET /api/runs says about a run (mirrors api/runs.py). */
export function makeSummary(run: Run, overrides: Partial<RunSummary> = {}): RunSummary {
  const count = (stage: string, key: string) => run.stages.find((s) => s.name === stage)?.counts[key] ?? null;
  return {
    run_id: run.run_id,
    week_label: run.week_label,
    status: run.status,
    started_at: run.started_at,
    duration_s: run.stages.length ? run.stages.reduce((t, s) => t + s.duration_s, 0) : null,
    fetched: count("ingest", "fetched"),
    clean: count("sanitize", "clean"),
    analysed: count("sanitize", "analysed"),
    word_count: run.word_count,
    has_pulse: run.status === "completed" || run.status === "partial",
    doc_url: run.doc_url,
    draft_id: run.draft_id,
    is_dry_run: run.status === "completed" && run.doc_url === null,
    ...overrides,
  };
}

/** What GET /api/runs/{id} says: the real completed run's files unless overridden. */
export function makeDetail(run: Run = makeRun(), overrides: Partial<RunDetail> = {}): RunDetail {
  return {
    run,
    status: run.status,
    pulse: makePulse(),
    note: noteText,
    ranking: makeRanking(),
    themes: makeThemes(),
    file_errors: {},
    ...overrides,
  };
}

/** A run that stopped early: its folder has run.json (and sanitized.json) but no pulse files. */
export function makeFailedDetail(run: Run = makeFailedRun()): RunDetail {
  return makeDetail(run, { pulse: null, note: null, ranking: null, themes: null });
}

/**
 * Ten runs of the same week, shaped like data/runs on 2026-10-22: four completed dry runs and six
 * that failed at the model step. Newest first, as GET /api/runs returns them.
 */
export function makeHistory(): RunSummary[] {
  const completedIds = ["20261022-121514", "20261022-121335", "20261019-140147", "20261019-105133"];
  const failedIds = [
    "20261022-151338",
    "20261022-144815",
    "20261022-142323",
    "20261019-104645",
    "20261019-104352",
    "20261019-104153",
  ];
  const stamp = (id: string) =>
    `${id.slice(0, 4)}-${id.slice(4, 6)}-${id.slice(6, 8)}T${id.slice(9, 11)}:${id.slice(11, 13)}:${id.slice(13, 15)}+00:00`;
  const runs = [
    ...completedIds.map((id) => makeSummary(makeRun({ run_id: id, started_at: stamp(id) }))),
    ...failedIds.map((id) => makeSummary(makeFailedRun({ run_id: id, started_at: stamp(id) }))),
  ];
  return runs.sort((a, b) => b.run_id.localeCompare(a.run_id));
}
