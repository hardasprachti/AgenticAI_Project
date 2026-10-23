/**
 * Mock API for `npm run dev:mock` and tests: serves web/fixtures/ through the same signatures as
 * the HTTP client. It mirrors the derivations in api/runs.py and api/reviews.py closely enough that
 * the pages cannot tell the difference. Fixture explorer totals (150) differ from the run's
 * `analysed` (500); see web/fixtures/README.md.
 */
import { ApiError, type Api } from "./client";
import type {
  ActiveRun,
  ConfigView,
  LedgerView,
  Pulse,
  Ranking,
  ReviewPage,
  ReviewParams,
  ReviewRow,
  ReviewSummary,
  Run,
  RunDetail,
  RunSummary,
  StartRunBody,
  ThemesFile,
} from "./types";

const files = import.meta.glob("../../fixtures/**/*.{json,txt}", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const RUN_FILE = /fixtures\/runs\/([^/]+)\/([^/]+)$/;

function runFile(runId: string, name: string): string | undefined {
  for (const [path, text] of Object.entries(files)) {
    const match = RUN_FILE.exec(path);
    if (match && match[1] === runId && match[2] === name) return text;
  }
  return undefined;
}

function topFile(name: string): string {
  const hit = Object.entries(files).find(([path]) => path.endsWith(`/fixtures/${name}`));
  if (!hit) throw new Error(`fixture ${name} is missing`);
  return hit[1];
}

function runIds(): string[] {
  const ids = new Set<string>();
  for (const path of Object.keys(files)) {
    const match = RUN_FILE.exec(path);
    if (match) ids.add(match[1]);
  }
  return [...ids].sort().reverse();
}

function parse<T>(text: string | undefined): T | null {
  return text === undefined ? null : (JSON.parse(text) as T);
}

function stageCount(run: Run, stage: string, key: string): number | null {
  const value = run.stages.find((s) => s.name === stage)?.counts[key];
  return typeof value === "number" ? value : null;
}

function summarise(runId: string): RunSummary {
  const run = parse<Run>(runFile(runId, "run.json"));
  if (!run) throw new ApiError(404, "Run not found");
  const duration = run.stages.reduce((total, s) => total + s.duration_s, 0);
  return {
    run_id: run.run_id,
    week_label: run.week_label,
    status: run.status,
    started_at: run.started_at,
    duration_s: run.stages.length ? Math.round(duration * 1000) / 1000 : null,
    fetched: stageCount(run, "ingest", "fetched"),
    clean: stageCount(run, "sanitize", "clean"),
    analysed: stageCount(run, "sanitize", "analysed"),
    word_count: run.word_count ?? null,
    has_pulse: runFile(runId, "pulse.json") !== undefined,
    doc_url: run.doc_url,
    draft_id: run.draft_id,
    is_dry_run: run.status === "completed" && run.doc_url === null,
  };
}

function reviewsFor(runId: string): ReviewRow[] {
  const sample = parse<Omit<ReviewRow, "theme_id">[]>(runFile(runId, "sanitized.json")) ?? [];
  const themes = parse<ThemesFile>(runFile(runId, "themes.json"));
  const themeOf = new Map((themes?.assignments ?? []).map((a) => [a.review_id, a.theme_id]));
  return sample.map((r) => ({
    review_id: r.review_id,
    rating: r.rating,
    title: r.title,
    text: r.text,
    date: r.date,
    app_version: r.app_version,
    theme_id: themeOf.get(r.review_id) ?? null,
  }));
}

function requireRun(runId: string): void {
  if (runFile(runId, "run.json") === undefined) throw new ApiError(404, "Run not found");
}

function mondayOf(date: string): string {
  const d = new Date(`${date}T00:00:00Z`);
  const offset = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - offset);
  return d.toISOString().slice(0, 10);
}

function average(values: number[]): number | null {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

// A start in mock mode pretends to run for a few seconds, then reports a finished run.
const FAKE_RUN_MS = 4000;
let fakeRun: { startedAt: number } | null = null;

export const mockApi: Api = {
  async listRuns() {
    return runIds().map(summarise);
  },

  async getRun(runId): Promise<RunDetail> {
    requireRun(runId);
    const run = parse<Run>(runFile(runId, "run.json"));
    return {
      run,
      status: run?.status ?? "unreadable",
      pulse: parse<Pulse>(runFile(runId, "pulse.json")),
      note: runFile(runId, "note.txt") ?? null,
      ranking: parse<Ranking>(runFile(runId, "ranking.json")),
      themes: parse<ThemesFile>(runFile(runId, "themes.json")),
      file_errors: {},
    };
  },

  async getReviews(runId, params: ReviewParams = {}): Promise<ReviewPage> {
    requireRun(runId);
    const page = params.page ?? 1;
    const pageSize = params.page_size ?? 25;
    const needle = params.q?.toLowerCase();
    const matches = reviewsFor(runId).filter(
      (r) =>
        (!params.theme?.length || (r.theme_id !== null && params.theme.includes(r.theme_id))) &&
        (!params.rating?.length || (r.rating !== null && params.rating.includes(r.rating))) &&
        (!params.review_id?.length || params.review_id.includes(r.review_id)) &&
        (!needle || `${r.title} ${r.text}`.toLowerCase().includes(needle)),
    );
    const start = (page - 1) * pageSize;
    return { items: matches.slice(start, start + pageSize), total: matches.length, page, page_size: pageSize };
  },

  async getReviewsSummary(runId): Promise<ReviewSummary> {
    requireRun(runId);
    const rows = reviewsFor(runId);
    const rating: Record<string, number> = { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 };
    const weeks = new Map<string, number[]>();
    const themes = new Map<string | null, number[]>();
    for (const r of rows) {
      if (r.rating !== null) rating[String(r.rating)] += 1;
      const stars = r.rating === null ? [] : [r.rating];
      if (r.date) weeks.set(mondayOf(r.date), [...(weeks.get(mondayOf(r.date)) ?? []), ...stars]);
      themes.set(r.theme_id, [...(themes.get(r.theme_id) ?? []), ...stars]);
    }
    const counts = (key: string | null) => rows.filter((r) => r.theme_id === key).length;
    return {
      total: rows.length,
      rating,
      weekly: [...weeks.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([week_start, stars]) => ({
          week_start,
          count: rows.filter((r) => r.date && mondayOf(r.date) === week_start).length,
          avg_rating: average(stars),
        })),
      by_theme: [...themes.entries()].map(([theme_id, stars]) => ({
        theme_id,
        count: counts(theme_id),
        avg_rating: average(stars),
      })),
    };
  },

  async getLedger() {
    return { weeks: JSON.parse(topFile("ledger.json")), error: null } as LedgerView;
  },

  async getConfig() {
    return JSON.parse(topFile("config.json")) as ConfigView;
  },

  async startRun(body: StartRunBody) {
    if (body.dry_run === false && body.confirm !== "publish") {
      throw new ApiError(422, 'a real run needs confirm: "publish"');
    }
    if (fakeRun && Date.now() - fakeRun.startedAt < FAKE_RUN_MS) {
      throw new ApiError(409, "A run is already in progress");
    }
    fakeRun = { startedAt: Date.now() };
    return { pid: 4242, started_at: new Date(fakeRun.startedAt).toISOString() };
  },

  async getActive(): Promise<ActiveRun> {
    const idle: ActiveRun = {
      active: false,
      elapsed_s: null,
      last_line: null,
      started_by_api: false,
      exit_code: null,
      exit_message: null,
      new_run_id: null,
      stderr_tail: [],
    };
    if (!fakeRun) return idle;
    const elapsed = (Date.now() - fakeRun.startedAt) / 1000;
    if (elapsed * 1000 < FAKE_RUN_MS) {
      return { ...idle, active: true, elapsed_s: elapsed, started_by_api: true, last_line: "Mock run in progress" };
    }
    return {
      ...idle,
      started_by_api: true,
      exit_code: 0,
      exit_message: "Run finished",
      new_run_id: runIds()[1] ?? null,
    };
  },
};
