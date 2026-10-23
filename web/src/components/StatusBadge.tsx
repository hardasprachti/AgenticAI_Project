import {
  AlertTriangle,
  Check,
  FlaskConical,
  Info,
  Loader2,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { RunStatus } from "../api/types";
import { statusPresentation, type StatusIcon } from "../lib/status";

const ICONS: Record<StatusIcon, LucideIcon> = {
  check: Check,
  spinner: Loader2,
  warning: AlertTriangle,
  cross: XCircle,
  flask: FlaskConical,
  info: Info,
};

/** Tailwind needs whole class names in the source to generate them. */
const TOKEN_CLASSES = {
  completed: "border-status-completed-border bg-status-completed-bg text-status-completed-fg",
  running: "border-status-running-border bg-status-running-bg text-status-running-fg",
  partial: "border-status-partial-border bg-status-partial-bg text-status-partial-fg",
  failed: "border-status-failed-border bg-status-failed-bg text-status-failed-fg",
  dryrun: "border-status-dryrun-border bg-status-dryrun-bg text-status-dryrun-fg",
  pending: "border-status-pending-border bg-status-pending-bg text-status-pending-fg",
} as const;

/**
 * Icon + text, never colour alone. Without the run we cannot tell a dry run from a published one,
 * so a completed status is shown plainly as "Completed" rather than guessed.
 */
export function StatusBadge({
  status,
  run,
  short = false,
}: {
  status: RunStatus;
  run?: { doc_url: string | null };
  /** Table form: "Dry run" instead of "Completed · Dry run, nothing published". */
  short?: boolean;
}) {
  const presentation = statusPresentation({
    status,
    doc_url: run ? run.doc_url : "unknown", // non-null: never claim a dry run we cannot see
  });
  const Icon = ICONS[presentation.icon];
  const label = short
    ? presentation.token === "dryrun"
      ? "Dry run"
      : presentation.label.split(" · ")[0]
    : presentation.label;
  return (
    <span
      className={`inline-flex items-center gap-space-xs rounded-full border px-space-sm py-space-xxs text-label-sm ${TOKEN_CLASSES[presentation.token]}`}
    >
      {status === "running" ? (
        <span
          data-pulse-dot
          aria-hidden="true"
          className="h-2 w-2 rounded-full bg-current animate-pulse motion-reduce:animate-none"
        />
      ) : null}
      <Icon size={14} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}
