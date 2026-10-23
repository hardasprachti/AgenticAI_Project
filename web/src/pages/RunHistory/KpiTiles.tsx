import type { RunSummary } from "../../api/types";
import { formatDuration, formatInt, formatPercent } from "../../lib/format";

function mean(values: number[]): number | null {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

function Tile({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-space-lg">
      <h2 className="text-label-sm uppercase text-on-surface-variant">{label}</h2>
      <div className="mt-space-xs flex flex-col gap-space-xxs">{children}</div>
    </div>
  );
}

/** Everything here is computed from the run list. A delta appears only when both runs have the number. */
export function KpiTiles({ runs, maxWords }: { runs: RunSummary[]; maxWords: number | null }) {
  const completed = runs.filter((r) => r.status === "completed");
  const count = (status: RunSummary["status"]) => runs.filter((r) => r.status === status).length;
  const avgDuration = mean(completed.map((r) => r.duration_s).filter((d): d is number => d !== null));
  const avgWords = mean(completed.map((r) => r.word_count).filter((w): w is number => w !== null));
  const [latest, previous] = runs;
  const delta =
    latest?.fetched != null && previous?.fetched != null ? latest.fetched - previous.fetched : null;

  return (
    <section aria-label="Summary" className="mb-space-lg grid grid-cols-1 gap-space-md md:grid-cols-2 xl:grid-cols-5">
      <Tile label="Runs">
        <p className="font-data-metric text-headline-md">{runs.length} runs</p>
        <p className="text-body-sm text-on-surface-variant">Success rate</p>
        <p className="font-label-lg text-label-lg">
          {runs.length ? formatPercent(completed.length / runs.length, 0) : "—"}
        </p>
      </Tile>
      <Tile label="Anomalies">
        <p className="font-data-metric text-headline-md">{count("failed")} failed</p>
        <p className="text-body-sm text-on-surface-variant">{count("failed_validation")} failed validation</p>
        <p className="text-body-sm text-on-surface-variant">{count("partial")} partial</p>
      </Tile>
      <Tile label="Average duration (completed)">
        <p className="font-data-metric text-headline-md">
          {avgDuration === null ? "—" : formatDuration(avgDuration)}
        </p>
      </Tile>
      <Tile label="Latest run">
        <p className="font-data-metric text-headline-md">{formatInt(latest?.fetched ?? null)} fetched</p>
        <p className="text-body-sm text-on-surface-variant">{formatInt(latest?.clean ?? null)} clean</p>
        {delta !== null && (
          <p className="text-body-sm text-on-surface-variant">
            {delta >= 0 ? "+" : "−"}
            {formatInt(Math.abs(delta))} fetched vs previous run
          </p>
        )}
      </Tile>
      <Tile label="Average words (completed)">
        <p className="font-data-metric text-headline-md">
          {avgWords === null ? "—" : `${formatInt(avgWords)} words`}
        </p>
        <p className="text-body-sm text-on-surface-variant">
          limit {maxWords === null ? "—" : formatInt(maxWords)}
        </p>
      </Tile>
    </section>
  );
}
