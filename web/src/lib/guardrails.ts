import type { ConfigView, Pulse, ReviewRow, Run } from "../api/types";
import { formatInt, truncateId, windowWeeks } from "./format";
import { CATCH_ALL_THEME_ID } from "./themes";

export type GuardrailId =
  | "themes"
  | "quotes"
  | "actions"
  | "words"
  | "identity"
  | "window"
  | "compose";

export interface Guardrail {
  id: GuardrailId;
  label: string;
  /** `unavailable` means the data to judge it is missing; it is never counted as a pass. */
  status: "pass" | "fail" | "unavailable";
  detail: string;
  /** Evidence to list under the detail (redaction counts, violations). */
  items?: string[];
}

export interface GuardrailInput {
  run: Run | null;
  pulse: Pulse | null;
  /** The analysed reviews the pulse quotes, keyed by review_id; null while they are loading. */
  reviewsById: Record<string, ReviewRow> | null;
  config: ConfigView;
}

/** The note's shape, from the problem statement (the same constants the backend validates). */
const REQUIRED_THEMES = 3;
const REQUIRED_QUOTES = 3;
const REQUIRED_ACTIONS = 3;
/** The review window must span 8 to 12 weeks. */
const MIN_WINDOW_WEEKS = 8;
const MAX_WINDOW_WEEKS = 12;

/** Whitespace collapsed, lower-cased, curly quotes and dashes folded to plain ones. */
export function normalize(text: string): string {
  return text
    .replace(/[‘’‚′]/g, "'")
    .replace(/[“”„″]/g, '"')
    .replace(/[‐‑‒–—―−]/g, "-")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

const unavailable = (id: GuardrailId, label: string, detail: string): Guardrail => ({
  id,
  label,
  status: "unavailable",
  detail,
});

const noPulse = "Not produced: this run has no pulse.";

function themesGuardrail({ run, pulse, config }: GuardrailInput): Guardrail {
  const label = `${REQUIRED_THEMES} themes in the note, at most ${config.max_themes} clustering themes`;
  if (!pulse) return unavailable("themes", label, noPulse);
  const scored = Object.keys(run?.theme_scores ?? {});
  if (scored.length === 0) return unavailable("themes", label, "The run recorded no theme scores.");
  const clustering = scored.filter((id) => id !== CATCH_ALL_THEME_ID).length;
  const problems: string[] = [];
  if (pulse.themes.length !== REQUIRED_THEMES) {
    problems.push(`the note has ${pulse.themes.length} themes, needs ${REQUIRED_THEMES}`);
  }
  if (clustering > config.max_themes) {
    problems.push(`${clustering} clustering themes exceeds the maximum of ${config.max_themes}`);
  }
  return {
    id: "themes",
    label,
    status: problems.length ? "fail" : "pass",
    detail: problems.length
      ? `Failed: ${problems.join("; ")}.`
      : `${pulse.themes.length} themes in the note; ${clustering} clustering themes (Other excluded), maximum ${config.max_themes}.`,
  };
}

function quotesGuardrail({ pulse, reviewsById }: GuardrailInput): Guardrail {
  const label = `${REQUIRED_QUOTES} verbatim quotes from analysed reviews`;
  if (!pulse) return unavailable("quotes", label, noPulse);
  if (!reviewsById) return unavailable("quotes", label, "The source reviews have not loaded.");
  const problems: string[] = [];
  if (pulse.quotes.length !== REQUIRED_QUOTES) {
    problems.push(`${pulse.quotes.length} quotes, needs ${REQUIRED_QUOTES}`);
  }
  for (const quote of pulse.quotes) {
    const review = reviewsById[quote.review_id];
    if (!review) {
      problems.push(`review ${truncateId(quote.review_id)} is not in the analysed set`);
    } else if (!normalize(review.text).includes(normalize(quote.text))) {
      problems.push(`the quote from review ${truncateId(quote.review_id)} is not verbatim`);
    } else if (!quote.theme_id) {
      problems.push(`the quote from review ${truncateId(quote.review_id)} has no theme`);
    }
  }
  return {
    id: "quotes",
    label,
    status: problems.length ? "fail" : "pass",
    detail: problems.length
      ? `Failed: ${problems.join("; ")}.`
      : "Each quote was found, ignoring case and spacing, in the review it cites.",
  };
}

function actionsGuardrail({ pulse }: GuardrailInput): Guardrail {
  const label = `${REQUIRED_ACTIONS} actions, each on a top theme`;
  if (!pulse) return unavailable("actions", label, noPulse);
  const top = new Set(pulse.themes.map((t) => t.theme_id));
  const problems: string[] = [];
  if (pulse.actions.length !== REQUIRED_ACTIONS) {
    problems.push(`${pulse.actions.length} actions, needs ${REQUIRED_ACTIONS}`);
  }
  pulse.actions.forEach((action, index) => {
    if (!top.has(action.theme_id)) {
      problems.push(`action ${index + 1} is on ${action.theme_id}, which is not a top theme`);
    }
  });
  return {
    id: "actions",
    label,
    status: problems.length ? "fail" : "pass",
    detail: problems.length
      ? `Failed: ${problems.join("; ")}.`
      : "Every action belongs to one of the top themes.",
  };
}

function wordsGuardrail({ run, pulse, config }: GuardrailInput): Guardrail {
  const max = config.pulse.max_words;
  const label = `At most ${max} words`;
  if (!pulse || !run) return unavailable("words", label, noPulse);
  const ok = run.word_count <= max;
  return {
    id: "words",
    label,
    status: ok ? "pass" : "fail",
    detail: `${formatInt(run.word_count)} of ${formatInt(max)} words.`,
  };
}

const REDACTIONS: [key: string, singular: string, plural: string][] = [
  ["redacted_author_name", "reviewer name", "reviewer names"],
  ["redacted_email", "email", "emails"],
  ["redacted_handle", "handle", "handles"],
  ["redacted_id_token", "ID token", "ID tokens"],
  ["redacted_number", "number", "numbers"],
];

function identityGuardrail({ run }: GuardrailInput): Guardrail {
  const label = "No reviewer identity";
  const counts = run?.stages.find((s) => s.name === "sanitize")?.counts;
  if (!counts) return unavailable("identity", label, "The run recorded no sanitize stage.");
  const items = REDACTIONS.map(([key, one, many]) => {
    const n = counts[key] ?? 0;
    return `${formatInt(n)} ${n === 1 ? one : many}`;
  });
  return {
    id: "identity",
    label,
    status: "pass",
    detail: `Scrubbed before analysis: ${items.join(", ")}. Raw reviews are never shown here.`,
    items,
  };
}

function windowGuardrail({ pulse }: GuardrailInput): Guardrail {
  const label = `Review window of ${MIN_WINDOW_WEEKS} to ${MAX_WINDOW_WEEKS} weeks`;
  if (!pulse) return unavailable("window", label, noPulse);
  const weeks = windowWeeks(pulse.window_start, pulse.window_end);
  if (Number.isNaN(weeks)) return unavailable("window", label, "The window dates are unreadable.");
  const ok = weeks >= MIN_WINDOW_WEEKS && weeks <= MAX_WINDOW_WEEKS;
  return {
    id: "window",
    label,
    status: ok ? "pass" : "fail",
    detail: `${weeks} weeks.`,
  };
}

function composeGuardrail({ run }: GuardrailInput): Guardrail {
  const label = "Compose retries and violations";
  if (!run) return unavailable("compose", label, "No run record.");
  const composed = run.stages.some((s) => s.name === "compose");
  if (!composed && run.status !== "failed_validation") {
    return unavailable("compose", label, "The note was not composed in this run.");
  }
  const violations = run.violations ?? [];
  const failed = run.status === "failed_validation";
  const count = `${violations.length} violation${violations.length === 1 ? "" : "s"}`;
  return {
    id: "compose",
    label,
    status: failed ? "fail" : "pass",
    detail: `Compose retries: ${run.retries}. ${violations.length ? count + "." : "No violations."}`,
    items: violations.length ? violations : undefined,
  };
}

export function evaluateGuardrails(input: GuardrailInput): Guardrail[] {
  return [
    themesGuardrail(input),
    quotesGuardrail(input),
    actionsGuardrail(input),
    wordsGuardrail(input),
    identityGuardrail(input),
    windowGuardrail(input),
    composeGuardrail(input),
  ];
}

/** Header tally: an unavailable guardrail is counted on its own, never as a pass. */
export function tallyGuardrails(guardrails: Guardrail[]) {
  const count = (status: Guardrail["status"]) => guardrails.filter((g) => g.status === status).length;
  return {
    pass: count("pass"),
    fail: count("fail"),
    unavailable: count("unavailable"),
    total: guardrails.length,
  };
}
