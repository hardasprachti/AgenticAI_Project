import { AlertTriangle, CheckCircle2, Clock, XCircle } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import type { Run } from "../../api/types";
import { CopyButton } from "../../components/CopyButton";
import { Mono } from "../../components/Mono";
import { formatDuration } from "../../lib/format";
import { STAGE_LABELS, stageRows } from "../../lib/stages";

function Panel({
  tone,
  icon,
  title,
  children,
}: {
  tone: "failed" | "partial" | "pending" | "running";
  icon: ReactNode;
  title: string;
  children?: ReactNode;
}) {
  const colours = {
    failed: "border-status-failed-border bg-status-failed-bg text-status-failed-fg",
    partial: "border-status-partial-border bg-status-partial-bg text-status-partial-fg",
    pending: "border-status-pending-border bg-status-pending-bg text-status-pending-fg",
    running: "border-status-running-border bg-status-running-bg text-status-running-fg",
  }[tone];
  return (
    <section className={`mb-space-lg rounded-xl border p-space-lg ${colours}`}>
      <h2 className="flex items-center gap-space-sm font-headline-md text-headline-md">
        {icon}
        {title}
      </h2>
      {children && <div className="mt-space-sm text-body-md">{children}</div>}
    </section>
  );
}

function Violations({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="m-0 mt-space-sm list-disc pl-space-lg">
      {items.map((v, i) => (
        <li key={i}>{v}</li>
      ))}
    </ul>
  );
}

/** The run died partway: name the stage, quote the reason, and say what was not produced. */
export function FailedPanel({ run }: { run: Run }) {
  const failed = stageRows(run).find((r) => r.state === "failed");
  return (
    <Panel tone="failed" icon={<XCircle size={20} aria-hidden="true" />} title={
      failed ? `Stopped at: ${STAGE_LABELS[failed.name]}` : "Stopped before any stage was recorded"
    }>
      <Violations items={run.violations} />
      <p className="mt-space-sm">
        Not produced: the themes, quotes, actions and the published note. Nothing was published.
      </p>
    </Panel>
  );
}

export function FailedValidationPanel({ run }: { run: Run }) {
  return (
    <Panel tone="failed" icon={<XCircle size={20} aria-hidden="true" />} title="The note failed validation">
      <p>
        {run.retries} {run.retries === 1 ? "retry" : "retries"} used. Nothing was published.
      </p>
      <Violations items={run.violations} />
    </Panel>
  );
}

/** The Doc has the section, the draft failed. The UI never resumes; it shows the command. */
export function PartialPanel({ run }: { run: Run }) {
  const command = `python -m pulse run --resume ${run.run_id}`;
  return (
    <Panel tone="partial" icon={<AlertTriangle size={20} aria-hidden="true" />} title="Doc published, draft missing">
      <p>The Google Doc section was added, but the Gmail draft was not created. Finish it from a terminal:</p>
      <p className="mt-space-sm flex flex-wrap items-center gap-space-sm">
        <Mono className="rounded bg-surface-container-lowest px-space-sm py-space-xs text-on-surface">{command}</Mono>
        <CopyButton text={command} label="Copy command" />
      </p>
      <Violations items={run.violations} />
    </Panel>
  );
}

export function AlreadyPublishedPanel({ run }: { run: Run }) {
  return (
    <Panel tone="pending" icon={<CheckCircle2 size={20} aria-hidden="true" />} title={`Already published for ${run.week_label}`}>
      <p>This week is already in the Google Doc, so nothing new was written.</p>
      <dl className="m-0 mt-space-sm grid grid-cols-[auto_1fr] gap-x-space-md gap-y-space-xs">
        {run.doc_url && (
          <>
            <dt>Google Doc</dt>
            <dd className="m-0">
              <a href={run.doc_url} target="_blank" rel="noreferrer noopener" className="underline">
                Open Google Doc
              </a>
            </dd>
          </>
        )}
        {run.draft_id && (
          <>
            <dt>Draft id</dt>
            <dd className="m-0">
              <Mono>{run.draft_id}</Mono>
            </dd>
          </>
        )}
      </dl>
    </Panel>
  );
}

function useElapsed(startedAt: string | null): number | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  if (!startedAt) return null;
  const started = new Date(startedAt).getTime();
  return Number.isNaN(started) ? null : Math.max(0, (now - started) / 1000);
}

export function RunningPanel({ startedAt }: { startedAt: string | null }) {
  const elapsed = useElapsed(startedAt);
  return (
    <Panel tone="running" icon={<Clock size={20} aria-hidden="true" />} title="Run in progress">
      <p>
        Elapsed: {elapsed === null ? "—" : formatDuration(elapsed)}. Numbers appear when the analysis
        ends (usually 6-8 minutes).
      </p>
    </Panel>
  );
}

export function InterruptedPanel() {
  return (
    <Panel tone="failed" icon={<AlertTriangle size={20} aria-hidden="true" />} title="Run interrupted">
      <p>No run record; the process ended early</p>
    </Panel>
  );
}
