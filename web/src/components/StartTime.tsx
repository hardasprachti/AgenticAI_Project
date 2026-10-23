import { useId } from "react";
import { formatIst } from "../lib/format";

/** Start time in IST; UTC is in a tooltip that opens on hover and on keyboard focus. */
export function StartTime({ iso }: { iso: string }) {
  const tooltipId = useId();
  const { ist, utc } = formatIst(iso);
  return (
    <span className="group relative inline-block">
      <span
        tabIndex={0}
        aria-describedby={tooltipId}
        className="cursor-help rounded underline decoration-dotted underline-offset-4"
      >
        {ist}
      </span>
      <span
        role="tooltip"
        id={tooltipId}
        className="pointer-events-none absolute left-0 top-full z-10 mt-space-xs hidden whitespace-nowrap rounded-lg bg-inverse-surface px-space-sm py-space-xs text-label-md text-inverse-on-surface group-focus-within:block group-hover:block"
      >
        {utc}
      </span>
    </span>
  );
}
