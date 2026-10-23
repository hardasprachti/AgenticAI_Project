import type { RunStatus } from "../api/types";
import type { StatusKey } from "../styles/tokens";

export type StatusIcon = "check" | "spinner" | "warning" | "cross" | "flask" | "info";

export interface StatusPresentation {
  label: string;
  icon: StatusIcon;
  token: StatusKey;
}

type StatusLike = { status: RunStatus; doc_url: string | null };

/** A dry run has no flag of its own: it is a completed run that never published to the Doc. */
export function isDryRun(run: StatusLike): boolean {
  return run.status === "completed" && run.doc_url === null;
}

export function statusPresentation(run: StatusLike): StatusPresentation {
  switch (run.status) {
    case "completed":
      return isDryRun(run)
        ? { label: "Completed · Dry run, nothing published", icon: "flask", token: "dryrun" }
        : { label: "Completed", icon: "check", token: "completed" };
    case "running":
      return { label: "Running", icon: "spinner", token: "running" };
    case "partial":
      return { label: "Partial · Doc published, draft missing", icon: "warning", token: "partial" };
    case "failed":
      return { label: "Failed", icon: "cross", token: "failed" };
    case "failed_validation":
      return { label: "Failed validation · nothing published", icon: "cross", token: "failed" };
    case "already_published":
      return { label: "Already published", icon: "info", token: "pending" };
    case "interrupted":
      return { label: "Interrupted · no run record", icon: "warning", token: "failed" };
    case "unreadable":
      return { label: "Unreadable run record", icon: "warning", token: "failed" };
  }
}
