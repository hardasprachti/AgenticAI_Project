import { useConfig, useRuns } from "../../api/hooks";
import { DataUnavailable } from "../../components/DataUnavailable";
import { useRunControl } from "../../components/RunControlContext";
import { KpiTiles } from "./KpiTiles";
import { RunsTable } from "./RunsTable";
import { TrendChart } from "./TrendChart";

export function RunHistoryPage() {
  const runs = useRuns();
  const config = useConfig();
  const { open } = useRunControl();

  return (
    <div>
      <header className="mb-space-lg">
        <h1 className="font-headline-xl text-headline-xl">Run history</h1>
      </header>
      {runs.isPending && <p role="status">Loading runs…</p>}
      {runs.isError && <DataUnavailable what="Runs" />}
      {runs.data && runs.data.length === 0 && (
        <section className="rounded-xl border border-outline-variant bg-surface-container-lowest p-space-xl text-center">
          <h2 className="font-headline-lg text-headline-lg">No runs yet</h2>
          <button
            type="button"
            onClick={open}
            className="mt-space-md rounded-lg bg-primary-container px-space-md py-space-sm text-label-lg text-on-primary-container hover:opacity-90"
          >
            Run a dry run
          </button>
        </section>
      )}
      {runs.data && runs.data.length > 0 && (
        <>
          <KpiTiles runs={runs.data} maxWords={config.data?.pulse.max_words ?? null} />
          <TrendChart runs={runs.data} />
          <RunsTable runs={runs.data} />
        </>
      )}
    </div>
  );
}
