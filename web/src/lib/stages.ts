import { STAGE_NAMES, type Run, type Stage, type StageCounts, type StageName } from "../api/types";

export const STAGE_ORDER: readonly StageName[] = STAGE_NAMES;

export const STAGE_LABELS: Record<StageName, string> = {
  ingest: "Ingest",
  sanitize: "Sanitize",
  theme: "Theme",
  rank: "Rank",
  compose: "Compose",
  render: "Render",
  publish_doc: "Publish to Doc",
  publish_draft: "Create draft",
};

export interface StageRow {
  name: StageName;
  state: "done" | "failed" | "not_run";
  duration_s: number | null;
  counts: StageCounts;
  notes: string[];
}

function isKnown(name: string): name is StageName {
  return (STAGE_ORDER as readonly string[]).includes(name);
}

/** The recorded stages the run knows about, in pipeline order. */
function recorded(run: Run): Stage[] {
  return run.stages.filter((s) => isKnown(s.name));
}

/**
 * One row per known stage. A failed run records stages up to and including the one that died, so
 * the last recorded stage is the failed one; later stages never ran. A `partial` run is the other
 * case the backend can produce: the Doc section went in and the draft step failed.
 */
export function stageRows(run: Run): StageRow[] {
  const stages = recorded(run);
  const lastName = stages.at(-1)?.name;
  const diedAtLast = run.status === "failed" || run.status === "failed_validation";
  return STAGE_ORDER.map((name): StageRow => {
    const stage = stages.find((s) => s.name === name);
    if (!stage) return { name, state: "not_run", duration_s: null, counts: {}, notes: [] };
    const failed = (diedAtLast && name === lastName) || (run.status === "partial" && name === "publish_draft");
    return {
      name,
      state: failed ? "failed" : "done",
      duration_s: stage.duration_s,
      counts: stage.counts ?? {},
      notes: stage.notes ?? [],
    };
  });
}

export function totalDuration(run: Run): number {
  return run.stages.reduce((sum, s) => sum + (Number.isFinite(s.duration_s) ? s.duration_s : 0), 0);
}

/** The slowest stage and its share of the total, in percent (77.1, not 0.771). */
export function slowestStage(run: Run): { name: string; pct: number } | null {
  const total = totalDuration(run);
  if (total <= 0) return null;
  const slowest = run.stages.reduce((best, s) => (s.duration_s > best.duration_s ? s : best));
  return { name: slowest.name, pct: (slowest.duration_s / total) * 100 };
}
