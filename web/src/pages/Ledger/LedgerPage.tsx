import { ExternalLink, Lock } from "lucide-react";
import { Link } from "react-router-dom";
import { useConfig, useLedger } from "../../api/hooks";
import type { StepView } from "../../api/types";
import { Card } from "../../components/Card";
import { CopyButton } from "../../components/CopyButton";
import { DataUnavailable } from "../../components/DataUnavailable";
import { Mono } from "../../components/Mono";
import { formatInt } from "../../lib/format";
import { ledgerRows, type LedgerOutcome, type LedgerRow, type LedgerStep } from "../../lib/ledger";
import { PendingBanner } from "./PendingBanner";

const DOC_WORDS = { appended: "Appended", pending: "Pending", created: "Created" } as const;
const OUTCOME_LABEL: Record<LedgerOutcome, string> = {
  complete: "Complete",
  draft_missing: "Draft missing",
  action_required: "Action required",
  in_progress: "In progress",
};
const OUTCOME_TONE: Record<LedgerOutcome, string> = {
  complete: "text-status-completed-fg",
  draft_missing: "text-status-partial-fg",
  action_required: "text-status-failed-fg",
  in_progress: "text-status-running-fg",
};

function StepState({ step }: { step: StepView | null }) {
  return (
    <>
      {step ? DOC_WORDS[step.state] : "Not started"}
      {step?.confirmed_by_hand && (
        <span className="ml-space-xs rounded-full bg-status-dryrun-bg px-space-sm py-space-xxs text-label-sm text-status-dryrun-fg">
          Confirmed by hand
        </span>
      )}
    </>
  );
}

function Row({ row, docUrl }: { row: LedgerRow; docUrl: string | null }) {
  const runIds = [...new Set([row.doc?.run_id, row.draft?.run_id].filter((id): id is string => !!id))];
  const resume = row.resumeRunId ? `python -m pulse run --resume ${row.resumeRunId}` : null;
  return (
    <tr className="align-top">
      <th scope="row" className="py-space-sm pr-space-md text-left font-data-metric text-label-lg">
        {row.week}
      </th>
      <td className="py-space-sm pr-space-md">
        <StepState step={row.doc} />
      </td>
      <td className="py-space-sm pr-space-md">
        {row.doc?.revision_id ? <Mono>{row.doc.revision_id}</Mono> : "—"}
      </td>
      <td className="py-space-sm pr-space-md">{formatInt(row.doc?.characters_appended ?? null)}</td>
      <td className="py-space-sm pr-space-md">
        <StepState step={row.draft} />
      </td>
      <td className="py-space-sm pr-space-md">
        {row.draft?.draft_id ? <Mono>{row.draft.draft_id}</Mono> : "—"}
      </td>
      <td className="py-space-sm pr-space-md">
        {runIds.length === 0
          ? "—"
          : runIds.map((id) => (
              <div key={id}>
                <Link to={`/runs/${id}`} className="font-data-code text-data-code text-primary underline">
                  {id}
                </Link>
              </div>
            ))}
      </td>
      <td className="py-space-sm pr-space-md">
        {docUrl && row.doc ? (
          <a
            href={docUrl}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-space-xs text-primary underline"
          >
            <ExternalLink size={14} aria-hidden="true" />
            Open doc
          </a>
        ) : (
          "—"
        )}
      </td>
      <td className="py-space-sm">
        <span className={`font-label-lg text-label-lg ${OUTCOME_TONE[row.outcome]}`}>
          {OUTCOME_LABEL[row.outcome]}
        </span>
        {resume && (
          <div className="mt-space-xs flex flex-wrap items-center gap-space-xs">
            <Mono className="rounded bg-surface-container px-space-sm py-space-xs">{resume}</Mono>
            <CopyButton text={resume} label="Copy command" />
          </div>
        )}
      </td>
    </tr>
  );
}

export function LedgerPage() {
  const ledger = useLedger();
  const config = useConfig();

  const view = ledger.data;
  const rows = view ? ledgerRows(view) : [];
  const pending = rows.flatMap((row) =>
    (["doc", "draft"] as LedgerStep[])
      .filter((step) => row[step]?.state === "pending")
      .map((step) => ({ week: row.week, step, commandsSafe: row.commandsSafe })),
  );

  return (
    <div>
      <header className="mb-space-lg flex flex-wrap items-center gap-space-md">
        <h1 className="font-headline-xl text-headline-xl">Publishing Ledger</h1>
        <span className="inline-flex items-center gap-space-xs rounded-full border border-outline-variant px-space-sm py-space-xs text-label-md text-on-surface-variant">
          <Lock size={12} aria-hidden="true" />
          Read-only
        </span>
      </header>

      {ledger.isPending && <p role="status">Loading the ledger…</p>}
      {ledger.isError && <DataUnavailable what="Ledger" />}

      {view?.error === "ledger_unreadable" && (
        <p
          role="alert"
          className="mb-space-lg rounded-xl border border-status-failed-border bg-status-failed-bg p-space-lg text-body-md text-status-failed-fg"
        >
          The ledger file cannot be read. Duplicate protection is unknown until it is fixed or
          restored.
        </p>
      )}

      {pending.map((p) => (
        <PendingBanner key={`${p.week}-${p.step}`} {...p} />
      ))}

      {view && !view.error && rows.length === 0 && (
        <Card title="Nothing published from this machine" className="mb-space-lg">
          <p className="text-on-surface-variant">
            The ledger records each week once its Google Doc section and Gmail draft exist. It has no
            weeks yet.
          </p>
        </Card>
      )}

      {rows.length > 0 && (
        <Card title="Weeks" className="mb-space-lg">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[56rem] text-left text-body-sm">
              <thead>
                <tr className="text-label-md text-on-surface-variant">
                  {[
                    "Week",
                    "Doc",
                    "Revision",
                    "Characters",
                    "Draft",
                    "Draft id",
                    "Run",
                    "Doc link",
                    "Outcome",
                  ].map((h) => (
                    <th key={h} scope="col" className="border-b border-outline-variant py-space-sm pr-space-md">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <Row key={row.week} row={row} docUrl={config.data?.doc_url ?? null} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card title="About this file">
        <p className="text-body-md">
          Losing data/ledger.json loses duplicate protection: the next run could append the same week
          to the Doc again. The file is git-ignored on purpose, so back it up outside Git.
        </p>
      </Card>
    </div>
  );
}
