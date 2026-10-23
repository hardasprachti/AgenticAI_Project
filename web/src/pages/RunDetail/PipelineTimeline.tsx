import { CheckCircle2, MinusCircle, XCircle } from "lucide-react";
import { useId } from "react";
import type { Run } from "../../api/types";
import { Card } from "../../components/Card";
import { formatDuration, formatInt } from "../../lib/format";
import { slowestStage, STAGE_LABELS, stageRows, totalDuration, type StageRow } from "../../lib/stages";
import type { StageName } from "../../api/types";

const STATE = {
  done: { text: "Done", Icon: CheckCircle2, tone: "text-status-completed-fg" },
  failed: { text: "Failed", Icon: XCircle, tone: "text-status-failed-fg" },
  not_run: { text: "Not run", Icon: MinusCircle, tone: "text-on-surface-variant" },
} as const;

const humanize = (key: string) => key.replace(/_/g, " ");

/** A note that names a filesystem path (the ingest stage records its cache location) is not shown. */
const isShowable = (note: string) => !/^raw cache:/i.test(note);

function StageCard({ row }: { row: StageRow }) {
  const id = useId();
  const { text, Icon, tone } = STATE[row.state];
  const counts = Object.entries(row.counts);
  const notes = row.notes.filter(isShowable);
  return (
    <li
      aria-labelledby={id}
      className="flex flex-col gap-space-xs rounded-lg border border-outline-variant p-space-md"
    >
      <div className="flex items-center justify-between gap-space-sm">
        <h3 id={id} className="font-label-lg text-label-lg">
          {STAGE_LABELS[row.name as StageName]}
        </h3>
        <span className={`inline-flex items-center gap-space-xs text-label-md ${tone}`}>
          <Icon size={14} aria-hidden="true" />
          {text}
        </span>
      </div>
      {row.duration_s !== null && (
        <p className="font-data-metric text-headline-md">{row.duration_s.toFixed(1)}s</p>
      )}
      {counts.length > 0 && (
        <dl className="m-0 grid grid-cols-[1fr_auto] gap-x-space-md gap-y-space-xxs text-body-sm">
          {counts.map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-on-surface-variant">{humanize(key)}</dt>
              <dd className="m-0 text-right">{formatInt(value)}</dd>
            </div>
          ))}
        </dl>
      )}
      {notes.map((note) => (
        <p key={note} className="text-body-sm text-on-surface-variant">
          {note}
        </p>
      ))}
    </li>
  );
}

export function PipelineTimeline({ run }: { run: Run }) {
  const slowest = slowestStage(run);
  const total = totalDuration(run);
  return (
    <Card title="Pipeline timeline" eyebrow="Eight stages, in order" className="mb-space-lg">
      <div>
        <p className="mb-space-md flex flex-wrap gap-x-space-lg text-body-md">
          <span>Total time: {formatDuration(total)}</span>
          {slowest && (
            <span>
              Slowest: {STAGE_LABELS[slowest.name as StageName] ?? slowest.name} (
              {slowest.pct.toFixed(1)}% of {formatDuration(total)})
            </span>
          )}
        </p>
        <ol className="m-0 grid list-none grid-cols-1 gap-space-md p-0 md:grid-cols-2 xl:grid-cols-4">
          {stageRows(run).map((row) => (
            <StageCard key={row.name} row={row} />
          ))}
        </ol>
      </div>
    </Card>
  );
}
