/** Types mirroring the API (api/schemas.py) and the run files it passes through. */

export type RunStatus =
  | "running"
  | "completed"
  | "failed_validation"
  | "partial"
  | "failed"
  | "already_published"
  | "interrupted"
  | "unreadable";

export const STAGE_NAMES = [
  "ingest",
  "sanitize",
  "theme",
  "rank",
  "compose",
  "render",
  "publish_doc",
  "publish_draft",
] as const;
export type StageName = (typeof STAGE_NAMES)[number];

/** Counts are free-form per stage; a stage that failed early records `{}`. */
export type StageCounts = Record<string, number>;

export interface Stage {
  name: string;
  duration_s: number;
  counts: StageCounts;
  notes: string[];
}

export interface ThemeScore {
  volume: number;
  recency: number;
  severity: number;
  score: number;
  review_count: number;
  avg_rating: number;
}

export interface LlmUsage {
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  retries: number;
  rate_limited: number;
  invalid_replies: number;
  waited_s: number;
}

/** run.json. Models are not recorded in it; the UI reads them from /api/config. */
export interface Run {
  run_id: string;
  week_label: string;
  status: RunStatus;
  started_at: string;
  stages: Stage[];
  theme_scores: Record<string, ThemeScore>;
  prompt_versions: Record<string, string>;
  retries: number;
  violations: string[];
  word_count: number;
  llm_usage: Record<string, LlmUsage>;
  doc_id: string | null;
  doc_url: string | null;
  doc_revision_id: string | null;
  draft_id: string | null;
}

export interface PulseTheme {
  theme_id: string;
  label: string;
  summary: string;
  share: number;
}

export interface PulseQuote {
  text: string;
  theme_id: string;
  rating: number;
  review_id: string;
}

export interface PulseAction {
  text: string;
  theme_id: string;
}

/** pulse.json */
export interface Pulse {
  week_label: string;
  window_start: string;
  window_end: string;
  review_count: number;
  themes: PulseTheme[];
  quotes: PulseQuote[];
  actions: PulseAction[];
  analysed_count: number;
}

export interface ThemeDef {
  theme_id: string;
  label: string;
  description: string;
}

export interface RankedTheme {
  theme: ThemeDef;
  review_count: number;
  share: number;
  avg_rating: number;
  score: number;
  components: { volume: number; recency: number; severity: number };
}

/** ranking.json */
export interface Ranking {
  ranked: RankedTheme[];
  top: string[];
}

/** themes.json */
export interface ThemesFile {
  themes: ThemeDef[];
  assignments: { review_id: string; theme_id: string }[];
}

export interface ReviewRow {
  review_id: string;
  rating: number | null;
  title: string;
  text: string;
  date: string | null;
  app_version: string | null;
  theme_id: string | null;
}

export interface ReviewPage {
  items: ReviewRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface ReviewSummary {
  total: number;
  rating: Record<string, number>;
  weekly: { week_start: string; count: number; avg_rating: number | null }[];
  by_theme: { theme_id: string | null; count: number; avg_rating: number | null }[];
}

export interface ReviewParams {
  theme?: string[];
  rating?: number[];
  review_id?: string[];
  q?: string;
  page?: number;
  page_size?: number;
}

export interface RunSummary {
  run_id: string;
  week_label: string | null;
  status: RunStatus;
  started_at: string | null;
  duration_s: number | null;
  fetched: number | null;
  clean: number | null;
  analysed: number | null;
  word_count: number | null;
  has_pulse: boolean;
  doc_url: string | null;
  draft_id: string | null;
  is_dry_run: boolean;
}

export interface RunDetail {
  run: Run | null;
  status: RunStatus;
  pulse: Pulse | null;
  note: string | null;
  ranking: Ranking | null;
  themes: ThemesFile | null;
  file_errors: Record<string, string>;
}

export type StepState = "appended" | "created" | "pending";

export interface StepView {
  state: StepState;
  run_id?: string | null;
  document_id?: string | null;
  revision_id?: string | null;
  characters_appended?: number | null;
  draft_id?: string | null;
  thread_id?: string | null;
  subject?: string | null;
  confirmed_by_hand?: boolean | null;
}

export interface WeekView {
  doc: StepView | null;
  draft: StepView | null;
}

export interface LedgerView {
  weeks: Record<string, WeekView>;
  error: "ledger_unreadable" | null;
}

export interface ConfigView {
  app: { play_package: string; play_lang: string; play_country: string };
  window_weeks: number;
  max_themes: number;
  taxonomy: string[];
  ranking: {
    weights: { volume: number; recency: number; severity: number };
    recency_window_weeks: number;
  };
  pulse: { max_words: number; min_reviews: number; min_words: number; max_analysed: number };
  models: { theme_assign: string | null; compose: string | null; judge: string | null };
  batch_size: number;
  draft_to: string | null;
  doc_url: string | null;
}

export interface StartRunBody {
  source: "play" | "csv";
  dry_run?: boolean;
  as_of?: string | null;
  confirm?: string | null;
}

export interface StartRunResponse {
  pid: number;
  started_at: string;
}

export interface ActiveRun {
  active: boolean;
  elapsed_s: number | null;
  last_line: string | null;
  started_by_api: boolean;
  exit_code: number | null;
  exit_message: string | null;
  new_run_id: string | null;
  stderr_tail: string[];
}
