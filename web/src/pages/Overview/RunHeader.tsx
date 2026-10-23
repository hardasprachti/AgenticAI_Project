import { ExternalLink, Play } from "lucide-react";
import type { Pulse, RunSummary } from "../../api/types";
import { Mono } from "../../components/Mono";
import { StatusBadge } from "../../components/StatusBadge";
import { useRunControl } from "../../components/RunControlContext";
import { StartTime } from "../../components/StartTime";
import { formatDuration, formatWindow, windowWeeks } from "../../lib/format";

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-space-xxs">
      <dt className="text-label-sm uppercase text-on-surface-variant">{label}</dt>
      <dd className="m-0 text-body-md text-on-surface">{children}</dd>
    </div>
  );
}

export function RunHeader({ summary, pulse }: { summary: RunSummary; pulse: Pulse | null }) {
  const { open } = useRunControl();
  const weeks = pulse ? windowWeeks(pulse.window_start, pulse.window_end) : NaN;
  return (
    <header className="mb-space-lg flex flex-col gap-space-md">
      <div className="flex flex-wrap items-center justify-between gap-space-md">
        <div className="flex flex-wrap items-center gap-space-md">
          <h1 className="font-headline-xl text-headline-xl">Latest run</h1>
          {summary.week_label && (
            <span className="rounded-full bg-primary-container px-space-md py-space-xs font-data-metric text-label-lg text-on-primary-container">
              {summary.week_label}
            </span>
          )}
          <StatusBadge status={summary.status} run={summary} />
        </div>
        <div className="flex flex-wrap items-center gap-space-sm">
          {summary.doc_url && summary.status !== "already_published" && (
            <a
              href={summary.doc_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-space-xs rounded-lg border border-outline-variant px-space-md py-space-sm text-label-lg text-primary hover:bg-surface-container-low"
            >
              <ExternalLink size={16} aria-hidden="true" />
              Open Google Doc
            </a>
          )}
          <button
            type="button"
            onClick={open}
            className="inline-flex items-center gap-space-xs rounded-lg bg-primary-container px-space-md py-space-sm text-label-lg text-on-primary-container hover:opacity-90"
          >
            <Play size={16} aria-hidden="true" />
            Run now
          </button>
        </div>
      </div>
      <dl className="m-0 grid grid-cols-2 gap-space-md md:grid-cols-4">
        <Fact label="Run id">
          <Mono>{summary.run_id}</Mono>
        </Fact>
        {pulse && Number.isFinite(weeks) && (
          <Fact label="Window">
            {formatWindow(pulse.window_start, pulse.window_end)} ({weeks} weeks)
          </Fact>
        )}
        {summary.started_at && (
          <Fact label="Started">
            <StartTime iso={summary.started_at} />
          </Fact>
        )}
        {summary.duration_s !== null && (
          <Fact label="Duration">{formatDuration(summary.duration_s)}</Fact>
        )}
      </dl>
    </header>
  );
}
