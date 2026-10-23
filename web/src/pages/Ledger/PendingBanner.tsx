import { AlertTriangle } from "lucide-react";
import { CopyButton } from "../../components/CopyButton";
import { Mono } from "../../components/Mono";
import { ledgerCommands, type LedgerStep } from "../../lib/ledger";

const STEP_LABEL: Record<LedgerStep, string> = { doc: "Google Doc section", draft: "Gmail draft" };

/**
 * A step left `pending` means the process died between writing the marker and recording the result,
 * so nobody knows whether the Doc/Drafts folder has it. A person looks, then runs one command.
 * The dashboard only shows the commands; it never edits the ledger.
 */
export function PendingBanner({
  week,
  step,
  commandsSafe,
}: {
  week: string;
  step: LedgerStep;
  commandsSafe: boolean;
}) {
  return (
    <section
      aria-label={`Pending ${STEP_LABEL[step]} for ${week}`}
      className="mb-space-md rounded-xl border border-status-partial-border bg-status-partial-bg p-space-lg text-status-partial-fg"
    >
      <h2 className="flex items-center gap-space-sm font-headline-md text-headline-md">
        <AlertTriangle size={20} aria-hidden="true" />
        {week} · {STEP_LABEL[step]} is pending
      </h2>
      <p className="mt-space-sm text-body-md">
        Outcome unknown: an earlier run died while writing. Check the Doc or Drafts folder, then run
        one of these:
      </p>
      {commandsSafe ? (
        <CommandChoices week={week} step={step} />
      ) : (
        <p className="mt-space-sm text-body-md">
          This week label is not in the usual form, so no command is offered. Fix the ledger file by
          hand.
        </p>
      )}
    </section>
  );
}

function CommandChoices({ week, step }: { week: string; step: LedgerStep }) {
  const { confirm, clear } = ledgerCommands(week, step);
  return (
    <dl className="m-0 mt-space-sm grid grid-cols-1 gap-space-md md:grid-cols-2">
      {[
        { when: "If it is there", command: confirm, label: "Copy: it is there" },
        { when: "If it is not there", command: clear, label: "Copy: it is not there" },
      ].map(({ when, command, label }) => (
        <div key={label} className="flex flex-col gap-space-xs">
          <dt className="text-label-lg">{when}</dt>
          <dd className="m-0 flex flex-wrap items-center gap-space-sm">
            <Mono className="rounded bg-surface-container-lowest px-space-sm py-space-xs text-on-surface">
              {command}
            </Mono>
            <CopyButton text={command} label={label} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
