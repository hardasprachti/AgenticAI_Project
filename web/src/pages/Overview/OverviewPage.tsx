import { useConfig, useRun, useRuns } from "../../api/hooks";
import type { ConfigView, RunDetail, RunSummary } from "../../api/types";
import { DataUnavailable } from "../../components/DataUnavailable";
import { useRunControl } from "../../components/RunControlContext";
import { computeFunnel } from "../../lib/funnel";
import { isDryRun } from "../../lib/status";
import { ActionCards } from "./ActionCards";
import { Funnel } from "./Funnel";
import { GuardrailChecklist } from "./GuardrailChecklist";
import { PublishedNote } from "./PublishedNote";
import { PublishingStatus } from "./PublishingStatus";
import { QuoteCards } from "./QuoteCards";
import { ThemeCards } from "./ThemeCards";
import { RunHeader } from "./RunHeader";
import {
  AlreadyPublishedPanel,
  FailedPanel,
  FailedValidationPanel,
  InterruptedPanel,
  PartialPanel,
  RunningPanel,
} from "./StatePanels";

function EmptyState() {
  const { open } = useRunControl();
  return (
    <section className="rounded-xl border border-outline-variant bg-surface-container-lowest p-space-xl text-center">
      <h1 className="font-headline-lg text-headline-lg">No runs yet</h1>
      <p className="mt-space-sm text-on-surface-variant">
        Nothing has been analysed. A dry run fetches and analyses reviews but publishes nothing.
      </p>
      <button
        type="button"
        onClick={open}
        className="mt-space-md rounded-lg bg-primary-container px-space-md py-space-sm text-label-lg text-on-primary-container hover:opacity-90"
      >
        Run a dry run
      </button>
    </section>
  );
}

function Findings({ detail, config }: { detail: RunDetail; config: ConfigView | undefined }) {
  const run = detail.run;
  if (!run) return null;
  if (!detail.pulse) {
    return <DataUnavailable what={detail.file_errors.pulse ? "Pulse (unreadable file)" : "Pulse"} />;
  }
  if (!config) return <DataUnavailable what="Config (needed for the score weights and limits)" />;
  return (
    <>
      <ThemeCards pulse={detail.pulse} ranking={detail.ranking} config={config} />
      <QuoteCards pulse={detail.pulse} runId={run.run_id} />
      <ActionCards pulse={detail.pulse} />
      <PublishedNote
        note={detail.note}
        wordCount={run.word_count}
        maxWords={config.pulse.max_words}
        dryRun={isDryRun(run)}
      />
      <PublishingStatus run={run} config={config} />
      <GuardrailChecklist runId={run.run_id} run={run} pulse={detail.pulse} config={config} />
    </>
  );
}

function RunBody({
  summary,
  detail,
  config,
}: {
  summary: RunSummary;
  detail: RunDetail;
  config: ConfigView | undefined;
}) {
  const minReviews = config?.pulse.min_reviews ?? null;
  const { run } = detail;
  const status = detail.status;

  if (status === "running") return <RunningPanel startedAt={summary.started_at} />;
  if (status === "interrupted") return <InterruptedPanel />;
  if (!run) return <DataUnavailable what="Run record" />;
  if (status === "already_published") return <AlreadyPublishedPanel run={run} />;

  const funnel = computeFunnel(run, minReviews ?? 0);
  return (
    <>
      {status === "failed" && <FailedPanel run={run} />}
      {status === "failed_validation" && <FailedValidationPanel run={run} />}
      {status === "partial" && <PartialPanel run={run} />}
      {status !== "failed_validation" && <Funnel funnel={funnel} minReviews={minReviews} />}
      {(status === "completed" || status === "partial") && (
        <Findings detail={detail} config={config} />
      )}
      {(status === "failed" || status === "failed_validation") && config && (
        <PublishingStatus run={run} config={config} />
      )}
    </>
  );
}

export function OverviewPage() {
  const runs = useRuns();
  const latest = runs.data?.[0];
  const detail = useRun(latest?.run_id);
  const config = useConfig();

  if (runs.isPending) return <p role="status">Loading the latest run…</p>;
  if (runs.isError) return <DataUnavailable what="Runs" />;
  if (!latest) return <EmptyState />;

  return (
    <div>
      <RunHeader summary={latest} pulse={detail.data?.pulse ?? null} />
      {detail.isPending && <p role="status">Loading run details…</p>}
      {detail.isError && <DataUnavailable what="Run details" />}
      {detail.data && (
        <RunBody
          summary={latest}
          detail={detail.data}
          config={config.data}
        />
      )}
    </div>
  );
}
