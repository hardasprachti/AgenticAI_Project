import { Link, useParams } from "react-router-dom";
import { useConfig, useRun, useRuns } from "../../api/hooks";
import { DataUnavailable } from "../../components/DataUnavailable";
import { Mono } from "../../components/Mono";
import { StatusBadge } from "../../components/StatusBadge";
import { LlmUsage } from "./LlmUsage";
import { PipelineTimeline } from "./PipelineTimeline";
import { ReviewExplorer } from "./ReviewExplorer";
import { ThemeTable } from "./ThemeTable";
import { Violations } from "./Violations";

/** `/runs/latest` is the nav shortcut: it shows whichever run is newest. */
export function RunDetailPage() {
  const { runId: param } = useParams();
  const wantsLatest = param === "latest";
  const runs = useRuns();
  const runId = wantsLatest ? runs.data?.[0]?.run_id : param;
  const detail = useRun(runId);
  const config = useConfig();

  if (wantsLatest && runs.isPending) return <p role="status">Loading the latest run…</p>;
  if (wantsLatest && !runId) return <DataUnavailable what="Latest run (there are no runs yet)" />;
  if (detail.isPending) return <p role="status">Loading run details…</p>;
  if (detail.isError || !detail.data) return <DataUnavailable what="Run details" />;

  const { run, pulse, ranking, themes } = detail.data;
  const labels = Object.fromEntries(
    (themes?.themes ?? ranking?.ranked.map((r) => r.theme) ?? []).map((t) => [t.theme_id, t.label]),
  );

  return (
    <div>
      <header className="mb-space-lg flex flex-wrap items-center gap-space-md">
        <h1 className="font-headline-xl text-headline-xl">Run detail</h1>
        <Mono>{runId}</Mono>
        {run && <span className="text-label-lg">{run.week_label}</span>}
        <StatusBadge status={detail.data.status} run={run ?? undefined} />
        <Link to="/runs" className="ml-auto text-label-lg text-primary underline">
          All runs
        </Link>
      </header>

      {!run ? (
        <DataUnavailable what="Run record" />
      ) : (
        <>
          <PipelineTimeline run={run} />
          {ranking && config.data ? (
            <ThemeTable ranking={ranking} config={config.data} />
          ) : (
            <p className="mb-space-lg">
              <DataUnavailable what="Theme scores" />
            </p>
          )}
          <LlmUsage run={run} config={config.data} />
          <Violations run={run} />
          {runId && <ReviewExplorer runId={runId} pulse={pulse} themeLabels={labels} />}
        </>
      )}
    </div>
  );
}
