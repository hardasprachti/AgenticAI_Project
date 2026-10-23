import { AlertTriangle, XCircle } from "lucide-react";
import type { Run } from "../../api/types";
import { Card } from "../../components/Card";

/**
 * The run's violations, verbatim. On a run that failed they are the reason (an error, announced);
 * on one that completed they are guardrail messages the note got past (a warning).
 */
export function Violations({ run }: { run: Run }) {
  const failed = run.status === "failed" || run.status === "failed_validation";
  const Icon = failed ? XCircle : AlertTriangle;
  return (
    <Card title="Violations" eyebrow={failed ? "Why the run stopped" : "Guardrail messages"} className="mb-space-lg">
      {run.violations.length === 0 ? (
        <p className="text-on-surface-variant">No violations recorded</p>
      ) : (
        <ul
          role={failed ? "alert" : undefined}
          className={`m-0 flex list-none flex-col gap-space-sm p-0 ${failed ? "text-status-failed-fg" : "text-status-partial-fg"}`}
        >
          {run.violations.map((violation, i) => (
            <li
              key={i}
              className={`flex items-start gap-space-sm rounded-lg border p-space-md ${failed ? "border-status-failed-border bg-status-failed-bg" : "border-status-partial-border bg-status-partial-bg"}`}
            >
              <Icon size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span>{violation}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
