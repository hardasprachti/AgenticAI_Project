import { Info } from "lucide-react";

/** Small inline notice for data that is missing or unreadable. Never a blank gap. */
export function DataUnavailable({ what }: { what: string }) {
  return (
    <p className="flex items-center gap-space-xs text-body-sm text-on-surface-variant">
      <Info size={14} aria-hidden="true" />
      <span>{what} unavailable</span>
    </p>
  );
}
