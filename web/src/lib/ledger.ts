import type { LedgerView, StepView } from "../api/types";

export type LedgerStep = "doc" | "draft";
export type LedgerOutcome = "complete" | "draft_missing" | "action_required" | "in_progress";

export interface LedgerRow {
  week: string;
  doc: StepView | null;
  draft: StepView | null;
  outcome: LedgerOutcome;
  /** For `draft_missing`: the run that wrote the Doc section, whose note `--resume` reuses. */
  resumeRunId: string | null;
  /** False when the week key is not a plain `YYYY-Www`; the UI must not offer commands for it. */
  commandsSafe: boolean;
}

const WEEK_RE = /^\d{4}-W\d{2}$/;
const isWeek = (week: string) => WEEK_RE.test(week);

function outcomeOf(doc: StepView | null, draft: StepView | null, activeRunId?: string | null) {
  if (doc?.state === "pending" || draft?.state === "pending") return "action_required";
  if (!doc) return "action_required"; // a draft with no Doc section: the orchestrator never does this
  if (draft) return "complete";
  return activeRunId && doc.run_id === activeRunId ? "in_progress" : "draft_missing";
}

/**
 * One row per week that has at least one step, newest first. An unreadable ledger yields no rows:
 * the page shows that duplicate protection is unknown rather than an empty table.
 */
export function ledgerRows(view: LedgerView, activeRunId?: string | null): LedgerRow[] {
  if (view.error) return [];
  return Object.entries(view.weeks)
    .filter(([, steps]) => steps.doc || steps.draft)
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([week, steps]): LedgerRow => {
      const outcome = outcomeOf(steps.doc, steps.draft, activeRunId);
      return {
        week,
        doc: steps.doc,
        draft: steps.draft,
        outcome,
        resumeRunId: outcome === "draft_missing" ? (steps.doc?.run_id ?? null) : null,
        commandsSafe: isWeek(week),
      };
    });
}

/** The CLI commands for a stuck step. The UI shows them to copy; it never runs them. */
export function ledgerCommands(week: string, step: LedgerStep): { confirm: string; clear: string } {
  if (!isWeek(week)) throw new RangeError(`not a week label: ${week}`);
  if (step !== "doc" && step !== "draft") throw new RangeError(`not a ledger step: ${step}`);
  return {
    confirm: `python -m pulse ledger confirm ${week} ${step}`,
    clear: `python -m pulse ledger clear ${week} ${step}`,
  };
}
